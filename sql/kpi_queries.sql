-- kpi_queries.sql — Reusable KPI and volatility queries.
-- All queries are Postgres-portable.
-- Parameterised versions live in src/queries.py.

-- ---------------------------------------------------------------------------
-- Metric #1: Daily occupancy rate by segment
-- (requires available_room_nights — TBD from Day 1 profiling)
-- ---------------------------------------------------------------------------
-- SELECT
--     segment_name,
--     date,
--     booked_room_nights,
--     <available_room_nights> AS available_room_nights,
--     booked_room_nights * 1.0 / <available_room_nights> AS occupancy_rate
-- FROM v_occupancy_by_segment_day;

-- ---------------------------------------------------------------------------
-- Metric #3: Cancellation rate by segment
-- ---------------------------------------------------------------------------
SELECT
    s.segment_name,
    COUNT(*)                                      AS total_bookings,
    SUM(CASE WHEN f.is_cancelled THEN 1 ELSE 0 END) AS cancelled_bookings,
    SUM(CASE WHEN f.is_cancelled THEN 1 ELSE 0 END) * 1.0
        / COUNT(*)                                AS cancellation_rate
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
GROUP BY s.segment_name;

-- ---------------------------------------------------------------------------
-- Metric #4: Average lead time by segment
-- ---------------------------------------------------------------------------
SELECT
    s.segment_name,
    AVG(f.lead_time_days) AS avg_lead_time_days
FROM fact_bookings_enriched f
JOIN dim_segment s ON f.segment_id = s.segment_id
GROUP BY s.segment_name;

-- ---------------------------------------------------------------------------
-- Metric #7: Revenue at risk by segment
-- ---------------------------------------------------------------------------
SELECT
    segment_name,
    revenue_at_risk
FROM v_revenue_at_risk_by_segment
ORDER BY revenue_at_risk DESC;
