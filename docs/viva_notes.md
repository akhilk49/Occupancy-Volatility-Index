# Viva Preparation Notes
## Occupancy Volatility Index — Akhil K Kurian

---

## 1. Pipeline Decisions

### Why SQLite and not Postgres/MySQL?
SQLite requires zero setup for local dev and the project spec explicitly allows it. The schema is written Postgres-portable (no SQLite-specific types or AUTOINCREMENT) so migration is a one-line connection string change.

### Why pandas for cleaning and not SQL?
Cleaning decisions (dedup, date parsing, segment normalisation) need to be auditable, testable, and versioned. Pandas functions are small, single-purpose, and independently unit-testable. SQL would mix transformation and storage concerns.

### Why is the fact table at reservation grain, not room-night grain?
Keeping it at reservation grain avoids exploding the dataset and keeps the pipeline fast. Metrics that need room-night grain (Metric #8 daily revenue) are computed in the SQL view layer using aggregation — the fact table doesn't need to change.

### Why is `total_rooms_available` a constant in config.py?
The column was absent from the raw data (confirmed Day 1 profiling). Rather than silently failing or hardcoding a number buried in the code, we made the assumption explicit as `ASSUMED_TOTAL_ROOMS = 100` in `config.py` — one place to change when real capacity is known.

### Why LEFT JOIN for cancellations?
Most bookings don't cancel. A INNER JOIN would silently drop all non-cancelled bookings from the fact table. LEFT JOIN preserves every booking and sets cancellation columns to NULL for non-cancelled rows — `is_cancelled` is then derived from whether `cancellation_date` is populated.

---

## 2. Every Metric Formula

**Metric #1 — Occupancy Rate**
`booked_room_nights / ASSUMED_TOTAL_ROOMS` per day, per segment. "Booked" means non-cancelled only. Denominator is a constant because `total_rooms_available` was absent from raw data.

**Metric #2 — Occupancy Volatility (CoV)**
`stddev(occupancy_rate) / mean(occupancy_rate)` per segment, computed across the selected date range. SQLite has no stddev aggregate — we fetch the daily series from `v_daily_room_nights_by_segment` and compute in pandas. Higher CoV = more erratic daily occupancy.

**Metric #3 — Cancellation Rate**
`cancelled_bookings / total_bookings` per segment. Straight count ratio. Sources from `v_cancellation_stats_by_segment`.

**Metric #4 — Average Lead Time**
`mean(check_in_date - booking_date)` in integer days per segment. Negative values (booking after check-in) are set to NaN and logged. Sources from `v_lead_time_by_segment`.

**Metric #5 — Seasonal Concentration Index**
1. Count bookings per segment per season.
2. Sum the top-2 seasons → `top2_share`.
3. Even baseline = `min(2, N_seasons) / N_seasons`.
4. Index = `top2_share / even_baseline`. Values > 1.0 mean bookings are more concentrated than a flat spread.

**Metric #6 — Segment Volatility Contribution (Headline)**
`variance(occupancy_rate for segment) / sum(variance for all segments)`. Uses sample variance (ddof=1). This tells us what fraction of the total occupancy variance is "caused by" each segment. Computed in pandas because SQLite has no VARIANCE aggregate.

**Metric #7 — Revenue at Risk**
`SUM(room_nights * rate)` where `is_cancelled = TRUE` per segment. Rate is imputed from `base_rate` in `features.py` where missing. Sources from `v_revenue_at_risk_by_segment`.

**Metric #8 — Revenue Volatility Index**
`stddev(daily_room_revenue) / mean(daily_room_revenue)` per segment. `daily_room_revenue` is `SUM(room_nights * rate)` per segment per check-in date, from `v_daily_revenue_by_segment`. Computed in pandas same reason as Metric #2.

---

## 3. Every Cleaning Decision

| Decision | Why |
|----------|-----|
| Drop exact duplicate rows | Identical rows add no information; all field values are the same |
| Duplicate `reservation_id` (non-exact): keep latest `booking_date` | Most recent record is the authoritative version of the booking |
| Mixed date formats → `pd.to_datetime(format="mixed")` | pandas 3.x removed `infer_datetime_format`; `format="mixed"` handles ISO + DD/MM/YYYY + MM-DD-YYYY |
| Drop rows with null `check_in_date` or `booking_date` | Cannot contribute to any time-based metric; keeping them would silently corrupt aggregations |
| Drop rows where `check_out_date <= check_in_date` | Logically impossible stay; treating as a data entry error |
| `room_nights` derived from `(check_out - check_in).days` | More reliable than the raw `nights` column which may be stale |
| Null `rate` → kept as NaN, imputed from `base_rate` after join | Imputation only possible after joining with seasonal_pricing; doing it early would lose the join-based value |
| Null `segment` → `'Unknown'` | Retain the booking in the fact table but don't pollute segment aggregations |
| Segment variants normalised via `SEGMENT_CANONICAL_MAP` | "TA", "travel agency", "T/A" all mean the same thing; inconsistent labels break GROUP BY |
| Cancellation duplicate: keep latest `cancellation_date` | Same cancellation logged twice; most recent is authoritative |
| Orphan cancellations (no matching booking) → retained | Explicit about data loss; they become unmatched in the LEFT JOIN |
| Seasonal pricing exact duplicates → dropped | Confirmed safe per Day 2 profiling notes (Manuel) |

---

## 4. SQL/Index Choices

**Why 5 indexes?**
- `idx_fact_segment` — every `GROUP BY segment_id` query
- `idx_fact_check_in_date` — every date-range filter
- `idx_fact_season_tag` — Metric #5 seasonal queries
- `idx_fact_is_cancelled` — Metrics #3, #7 cancellation filters
- `idx_fact_segment_date` (composite) — the most common dashboard pattern: filter by segment AND date range

**Why views instead of materialised tables?**
SQLite doesn't support materialised views. Regular views are recalculated on each query but our dataset is small (< 200 rows sample, realistically < 100k rows) so query time is well under 1 second without materialisation.

**Why is Metric #1 denominator not in the view?**
`ASSUMED_TOTAL_ROOMS` is a Python constant in `config.py`. If we bake it into the SQL view, changing the capacity assumption requires editing SQL. By keeping it in Python and passing it as a parameter, a single config change propagates everywhere.

---

## 5. Dashboard Design Rationale

**Why 9 sections?**
The SPEC wireframe defines sections A–C. The remaining sections (D–I) were added to ensure all 8 metrics are visible and filterable, which is a Global Definition of Done requirement.

**Why `st.bar_chart` / `st.line_chart` instead of plotly?**
Plotly was unavailable due to network issues during development. Streamlit's native charts are sufficient for the diagnostic purpose — this is not a production BI tool.

**Why `@st.cache_data`?**
Without caching, every sidebar widget interaction triggers a full DB query. With `ttl=60`, queries are cached for 60 seconds — the dashboard feels instant and the DB is not hammered.

**Why is the segment filter on every section?**
The dashboard's purpose is letting a revenue manager drill into a specific channel. Every visual must respond to the same filter to avoid confusing mixed-context comparisons.

---

## 6. Git/PR Conventions Rationale

**Why one PR per day?**
Grading/viva requires individual visible contribution. One daily PR makes the scope, commit history, and authorship of each day's work unambiguous.

**Why `day-XX-akhil` branch naming?**
Sorts chronologically in GitHub's branch list and immediately communicates whose work it is and which day it corresponds to.

**Why rebase instead of merge for the second merger?**
Keeps a linear, readable commit history. A merge commit between two daily branches would add noise to `git log`.
