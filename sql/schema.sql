-- schema.sql — Source of truth for all table, index, and view definitions.
--
-- Rules:
--   • Postgres-portable: no SQLite-specific syntax (no AUTOINCREMENT, no
--     PRAGMA, no SQLite type affinities beyond TEXT/INTEGER/NUMERIC/DATE/BOOLEAN).
--   • This file is executed by src/load.py on every pipeline run (idempotent —
--     all statements use IF NOT EXISTS / IF EXISTS guards).
--   • Column set matches the confirmed real-data schema (Day 1–2 profiling)
--     and supplies every input column required by the 8 metrics in SPEC Section 5.
--
-- Finalised: Day 5 (Akhil)
-- Last updated: Day 5

-- ===========================================================================
-- 1. DIMENSION TABLES
-- ===========================================================================

-- dim_segment: one row per canonical booking channel
-- Canonical values: Travel Agency | Direct | Corporate | Group | Walk-in | Unknown
-- 'Unknown' reserved for rows where segment was null in the raw data (Decision D4, SPEC 11.3)
CREATE TABLE IF NOT EXISTS dim_segment (
    segment_id   INTEGER PRIMARY KEY,
    segment_name TEXT    NOT NULL UNIQUE
);

-- ===========================================================================
-- 2. FACT TABLE
-- ===========================================================================

-- fact_bookings_enriched: one row per reservation (reservation grain)
-- Populated by src/load.py from data/processed/fact_bookings_enriched.csv
--
-- Column inventory vs. metric inputs (SPEC Section 5):
--   Metric #1  — check_in_date, room_nights, is_cancelled         ✓
--   Metric #2  — check_in_date, room_nights, segment_id           ✓  (CoV computed in queries)
--   Metric #3  — is_cancelled, segment_id                         ✓
--   Metric #4  — lead_time_days, segment_id                       ✓
--   Metric #5  — season_tag, segment_id, booking_date             ✓
--   Metric #6  — room_nights, segment_id (variance in queries)    ✓
--   Metric #7  — room_nights, rate, is_cancelled, segment_id      ✓
--   Metric #8  — room_nights, rate, check_in_date, segment_id     ✓  (daily explosion in view)
CREATE TABLE IF NOT EXISTS fact_bookings_enriched (
    -- identity
    reservation_id      TEXT    PRIMARY KEY,
    segment_id          INTEGER NOT NULL REFERENCES dim_segment(segment_id),

    -- booking attributes
    room_type           TEXT,                    -- 'Unknown' where null in raw
    booking_date        DATE    NOT NULL,
    check_in_date       DATE    NOT NULL,
    check_out_date      DATE    NOT NULL,
    nights              INTEGER NOT NULL,         -- raw value from bookings.csv
    room_nights         INTEGER NOT NULL,         -- = nights; kept as explicit column so
                                                  -- metric queries read room_nights uniformly
                                                  -- without casting or deriving on the fly
    rate                NUMERIC,                 -- NULL where raw rate was missing and
                                                  -- base_rate imputation was not possible

    -- cancellation (from LEFT JOIN with cancellations.csv)
    is_cancelled        BOOLEAN NOT NULL DEFAULT FALSE,
    cancellation_date   DATE,                    -- NULL when is_cancelled = FALSE
    cancellation_reason TEXT,                    -- NULL when is_cancelled = FALSE; ~15% null even when cancelled
    refund_status       TEXT,                    -- NULL when is_cancelled = FALSE

    -- derived features (added by src/features.py)
    lead_time_days      INTEGER,                 -- check_in_date - booking_date in days; NULL if either date missing

    -- seasonal pricing (from JOIN with seasonal_pricing.csv on check_in_date)
    -- Join rule: classify booking by check_in_date only (Decision D3, SPEC 11.3)
    season_tag          TEXT,                    -- NULL if no matching seasonal_pricing row
    base_rate           NUMERIC,                 -- from seasonal_pricing; used to impute missing rate
    demand_tier         TEXT
);

-- ===========================================================================
-- 3. INDEXES
-- ===========================================================================
-- These indexes are the primary performance levers for dashboard queries.
-- All dashboard filters (segment, date range, season) map to one of these.

-- Segment filter — used by every GROUP BY segment_id query
CREATE INDEX IF NOT EXISTS idx_fact_segment
    ON fact_bookings_enriched (segment_id);

-- Date range filter — used by time-series and occupancy trend queries
CREATE INDEX IF NOT EXISTS idx_fact_check_in_date
    ON fact_bookings_enriched (check_in_date);

-- Season filter — used by seasonal concentration (Metric #5) queries
CREATE INDEX IF NOT EXISTS idx_fact_season_tag
    ON fact_bookings_enriched (season_tag);

-- Cancellation filter — used by revenue-at-risk (Metric #7) and cancellation rate (Metric #3)
CREATE INDEX IF NOT EXISTS idx_fact_is_cancelled
    ON fact_bookings_enriched (is_cancelled);

-- Composite: segment + date — covers the most common dashboard query pattern
CREATE INDEX IF NOT EXISTS idx_fact_segment_date
    ON fact_bookings_enriched (segment_id, check_in_date);

-- ===========================================================================
-- 4. KPI VIEWS
-- ===========================================================================
-- Views are thin query wrappers — no business logic lives here that isn't
-- already expressible as a single SELECT. Complex multi-step metrics
-- (CoV, Segment Volatility Contribution) are computed in src/queries.py
-- using pandas after fetching the raw daily series from these views.

-- ---------------------------------------------------------------------------
-- Metric #1 input: daily booked room-nights per segment
-- Denominator (ASSUMED_TOTAL_ROOMS) is applied in src/queries.py, not here,
-- so the constant stays in one place (config.py).
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_daily_room_nights_by_segment;
CREATE VIEW v_daily_room_nights_by_segment AS
SELECT
    s.segment_name,
    f.check_in_date              AS date,
    SUM(f.room_nights)           AS booked_room_nights
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.is_cancelled = FALSE
GROUP BY s.segment_name, f.check_in_date;

-- ---------------------------------------------------------------------------
-- Metric #3: cancellation rate inputs per segment
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_cancellation_stats_by_segment;
CREATE VIEW v_cancellation_stats_by_segment AS
SELECT
    s.segment_name,
    COUNT(*)                                             AS total_bookings,
    SUM(CASE WHEN f.is_cancelled THEN 1 ELSE 0 END)     AS cancelled_bookings,
    SUM(CASE WHEN f.is_cancelled THEN 1 ELSE 0 END) * 1.0
        / NULLIF(COUNT(*), 0)                            AS cancellation_rate
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
GROUP BY s.segment_name;

-- ---------------------------------------------------------------------------
-- Metric #4: average lead time per segment
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_lead_time_by_segment;
CREATE VIEW v_lead_time_by_segment AS
SELECT
    s.segment_name,
    AVG(f.lead_time_days)        AS avg_lead_time_days,
    MIN(f.lead_time_days)        AS min_lead_time_days,
    MAX(f.lead_time_days)        AS max_lead_time_days
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.lead_time_days IS NOT NULL
GROUP BY s.segment_name;

-- ---------------------------------------------------------------------------
-- Metric #5 input: booking counts per segment per season
-- The Seasonal Concentration Index itself is computed in src/queries.py
-- (requires top-2 seasons logic that is cleaner in pandas than in SQL).
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_bookings_by_segment_season;
CREATE VIEW v_bookings_by_segment_season AS
SELECT
    s.segment_name,
    f.season_tag,
    COUNT(*)                     AS booking_count,
    SUM(f.room_nights)           AS room_nights
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.season_tag IS NOT NULL
GROUP BY s.segment_name, f.season_tag;

-- ---------------------------------------------------------------------------
-- Metric #7: revenue at risk per segment
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_revenue_at_risk_by_segment;
CREATE VIEW v_revenue_at_risk_by_segment AS
SELECT
    s.segment_name,
    SUM(f.room_nights * f.rate)  AS revenue_at_risk
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.is_cancelled = TRUE
  AND f.rate IS NOT NULL
GROUP BY s.segment_name;

-- ---------------------------------------------------------------------------
-- Metric #8 input: daily room revenue per segment
-- Explodes each reservation into one row per check-in date.
-- Decision D1 (SPEC 11.3): daily explosion handled here in SQL, not in
-- the Python pipeline, so fact_bookings_enriched stays at reservation grain.
--
-- Approach: attribute the full booking revenue to the check_in_date day.
-- For a more precise per-night split, replace (room_nights * rate) with
-- (rate) and generate a date series — revisit if Metric #8 numbers look off.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_daily_revenue_by_segment;
CREATE VIEW v_daily_revenue_by_segment AS
SELECT
    s.segment_name,
    f.check_in_date              AS date,
    SUM(f.room_nights * f.rate)  AS daily_room_revenue
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.is_cancelled = FALSE
  AND f.rate IS NOT NULL
GROUP BY s.segment_name, f.check_in_date;

-- ---------------------------------------------------------------------------
-- Segment summary: all per-segment aggregates in one place
-- Used by the dashboard's segment ranking table (Section B of wireframe).
-- Metrics #2, #6, #8 (CoV, variance-based) are not included here —
-- they require multi-row stddev/mean and are computed in src/queries.py.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_segment_summary;
CREATE VIEW v_segment_summary AS
SELECT
    s.segment_name,
    COUNT(*)                                             AS total_bookings,
    SUM(f.room_nights)                                   AS total_room_nights,
    SUM(CASE WHEN f.is_cancelled THEN 1 ELSE 0 END) * 1.0
        / NULLIF(COUNT(*), 0)                            AS cancellation_rate,
    AVG(f.lead_time_days)                                AS avg_lead_time_days,
    SUM(CASE WHEN f.is_cancelled AND f.rate IS NOT NULL
             THEN f.room_nights * f.rate ELSE 0 END)     AS revenue_at_risk
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
GROUP BY s.segment_name;
