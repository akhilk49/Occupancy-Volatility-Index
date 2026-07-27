-- kpi_queries.sql — All 8 KPI and volatility queries.
--
-- Rules:
--   • Postgres-portable: no SQLite-specific syntax.
--   • Parameterised versions of these queries live in src/queries.py.
--     This file is the human-readable reference; queries.py wraps them
--     with Python parameter binding (never string interpolation).
--   • Metrics #2, #6, #8 require stddev/mean over multiple rows — these are
--     fetched as raw daily series from the views and computed in pandas
--     (src/queries.py) because SQLite has no built-in stddev aggregate.
--
-- Finalised: Day 9

-- ===========================================================================
-- Metric #1 — Occupancy Rate: booked_room_nights / available_room_nights
-- Denominator (ASSUMED_TOTAL_ROOMS) is substituted by queries.py.
-- Returns one row per segment per day, non-cancelled bookings only.
-- ===========================================================================
-- [M1] Daily occupancy rate by segment
SELECT
    v.segment_name,
    v.date,
    v.booked_room_nights,
    v.booked_room_nights * 1.0 / :total_rooms  AS occupancy_rate
FROM v_daily_room_nights_by_segment v
ORDER BY v.segment_name, v.date;

-- ===========================================================================
-- Metric #2 — Occupancy Volatility (CoV)
-- stddev(occupancy_rate) / mean(occupancy_rate), per segment, rolling window.
-- SQLite has no stddev — fetch the daily series and compute in pandas.
-- ===========================================================================
-- [M2] Raw daily occupancy series per segment (input for CoV computation)
SELECT
    v.segment_name,
    v.date,
    v.booked_room_nights * 1.0 / :total_rooms  AS occupancy_rate
FROM v_daily_room_nights_by_segment v
ORDER BY v.segment_name, v.date;

-- ===========================================================================
-- Metric #3 — Cancellation Rate: cancelled_bookings / total_bookings
-- ===========================================================================
-- [M3] Cancellation rate by segment
SELECT
    segment_name,
    total_bookings,
    cancelled_bookings,
    ROUND(cancellation_rate, 4)  AS cancellation_rate
FROM v_cancellation_stats_by_segment
ORDER BY cancellation_rate DESC;

-- ===========================================================================
-- Metric #4 — Average Lead Time: mean(check_in_date - booking_date)
-- ===========================================================================
-- [M4] Average lead time by segment
SELECT
    segment_name,
    ROUND(avg_lead_time_days, 1)  AS avg_lead_time_days,
    min_lead_time_days,
    max_lead_time_days
FROM v_lead_time_by_segment
ORDER BY avg_lead_time_days DESC;

-- ===========================================================================
-- Metric #5 — Seasonal Concentration Index
-- Share of segment bookings in its top-2 seasons vs. an even spread.
-- The final index is computed in queries.py; this query supplies the
-- per-segment per-season booking counts.
-- ===========================================================================
-- [M5] Booking counts per segment per season (input for concentration index)
SELECT
    segment_name,
    season_tag,
    booking_count,
    room_nights,
    ROUND(booking_count * 1.0 / SUM(booking_count) OVER (PARTITION BY segment_name), 4)
        AS season_share
FROM v_bookings_by_segment_season
ORDER BY segment_name, booking_count DESC;

-- ===========================================================================
-- Metric #6 — Segment Volatility Contribution: segment_variance / total_variance
-- Requires variance of daily occupancy_rate per segment and overall.
-- Fetched as the Metric #2 series and computed in pandas (queries.py).
-- ===========================================================================
-- [M6] Same daily series as M2 — grouped by segment for variance calculation
SELECT
    v.segment_name,
    v.date,
    v.booked_room_nights * 1.0 / :total_rooms  AS occupancy_rate
FROM v_daily_room_nights_by_segment v
ORDER BY v.segment_name, v.date;

-- ===========================================================================
-- Metric #7 — Revenue at Risk: SUM(room_nights * rate) where is_cancelled
-- ===========================================================================
-- [M7] Revenue at risk by segment
SELECT
    segment_name,
    ROUND(revenue_at_risk, 2)  AS revenue_at_risk
FROM v_revenue_at_risk_by_segment
ORDER BY revenue_at_risk DESC;

-- ===========================================================================
-- Metric #8 — Revenue Volatility Index: stddev(daily_revenue) / mean(daily_revenue)
-- SQLite has no stddev — fetch daily series and compute CoV in pandas.
-- ===========================================================================
-- [M8] Raw daily revenue series per segment (input for Revenue Volatility Index)
SELECT
    segment_name,
    date,
    ROUND(daily_room_revenue, 2)  AS daily_room_revenue
FROM v_daily_revenue_by_segment
ORDER BY segment_name, date;

-- ===========================================================================
-- Segment Summary — all per-segment aggregates in one query
-- Used by the dashboard segment ranking table (Section B of wireframe).
-- Metrics #2, #6, #8 are added in Python after fetching the daily series.
-- ===========================================================================
-- [SUMMARY] Full segment summary
SELECT
    segment_name,
    total_bookings,
    total_room_nights,
    ROUND(cancellation_rate, 4)   AS cancellation_rate,
    ROUND(avg_lead_time_days, 1)  AS avg_lead_time_days,
    ROUND(revenue_at_risk, 2)     AS revenue_at_risk
FROM v_segment_summary
ORDER BY total_bookings DESC;
