-- schema.sql — Source of truth for table and view definitions.
-- Postgres-portable: no SQLite-specific types used.
-- Finalised in Day 5; referenced by load.py for DDL.

-- ---------------------------------------------------------------------------
-- Dimension tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_segment (
    segment_id   INTEGER PRIMARY KEY,
    segment_name TEXT NOT NULL          -- e.g. Travel Agency, Direct, Corporate, Group, Walk-in
);

-- ---------------------------------------------------------------------------
-- Fact table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_bookings_enriched (
    reservation_id    TEXT    PRIMARY KEY,
    segment_id        INTEGER REFERENCES dim_segment(segment_id),
    room_type         TEXT,
    booking_date      DATE,
    check_in_date     DATE,
    check_out_date    DATE,
    nights            INTEGER,
    rate              NUMERIC,
    is_cancelled      BOOLEAN,
    cancellation_date DATE,
    cancellation_reason TEXT,
    refund_status     TEXT,
    lead_time_days    INTEGER,          -- check_in_date - booking_date
    season_tag        TEXT,             -- joined from seasonal_pricing
    base_rate         NUMERIC,          -- from seasonal_pricing
    demand_tier       TEXT,             -- from seasonal_pricing
    room_nights       INTEGER           -- nights (alias kept for metric queries)
);

-- ---------------------------------------------------------------------------
-- KPI views (mirrors kpi_queries.sql for convenience)
-- ---------------------------------------------------------------------------

-- Daily booked room-nights per segment (feeds Metric #1)
CREATE VIEW IF NOT EXISTS v_occupancy_by_segment_day AS
SELECT
    s.segment_name,
    f.check_in_date  AS date,
    SUM(f.room_nights) AS booked_room_nights
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.is_cancelled = FALSE
GROUP BY s.segment_name, f.check_in_date;

-- Revenue at risk from cancellations per segment (Metric #7)
CREATE VIEW IF NOT EXISTS v_revenue_at_risk_by_segment AS
SELECT
    s.segment_name,
    SUM(f.room_nights * f.rate) AS revenue_at_risk
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
WHERE f.is_cancelled = TRUE
GROUP BY s.segment_name;
