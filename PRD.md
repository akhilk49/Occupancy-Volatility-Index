# PRD.md — Occupancy Volatility & Segment Insights Dashboard

> The full PRD is in `PRD_HotelOccupancyVolatility_updated.docx`. This markdown version captures the pipeline design decisions confirmed during Week 1 (Days 1–4) and is the living reference for implementation.

---

## Problem Statement

A hotel chain collects booking trends, cancellation history, and seasonal pricing records, but revenue teams cannot identify which customer segments contribute most to occupancy volatility.

## Objective

Build a data pipeline and interactive dashboard that joins booking, cancellation, and seasonal pricing data to answer:

> **Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors explain it?**

---

## Confirmed Data Schema (post Day 1–2 profiling)

### bookings.csv
| Column | Type | Notes |
|---|---|---|
| reservation_id | string | PK — duplicates found, dedup in clean.py |
| segment | string | Booking channel: Travel Agency / Direct / Corporate / Group / Walk-in |
| room_type | string | Minor nulls — fill with 'Unknown' |
| booking_date | date | Mixed formats — standardise to ISO 8601 |
| check_in_date | date | Mixed formats — standardise to ISO 8601 |
| check_out_date | date | Mixed formats — standardise to ISO 8601 |
| nights | integer | Cross-check against (check_out - check_in).days |
| rate | numeric | Some nulls — impute from base_rate where possible |
| ~~total_rooms_available~~ | — | **Absent** — use `ASSUMED_TOTAL_ROOMS = 100` from config.py |

### cancellations.csv
| Column | Type | Notes |
|---|---|---|
| reservation_id | string | FK to bookings — a few duplicates (keep latest cancellation_date) |
| cancellation_date | date | Mixed formats (ISO + MM/DD/YYYY) — standardise |
| reason | string | ~15% nulls — retain as-is |
| refund_status | string | Minor nulls |

### seasonal_pricing.csv
| Column | Type | Notes |
|---|---|---|
| date | date | Consistently ISO 8601 |
| season_tag | string | Clean |
| base_rate | numeric | Clean |
| demand_tier | string | Clean — exact duplicate rows, drop in cleaning |

---

## Pipeline Architecture

See `SPEC.md` Section 11 for the full data flow diagram, tool choices, and architecture decisions.

### Key decisions

| # | Decision | Detail |
|---|---|---|
| D1 | Daily revenue explosion for Metric #8 | Handled in SQL layer via date-spine CTE — fact table stays at reservation grain |
| D2 | Capacity assumption | `ASSUMED_TOTAL_ROOMS = 100` in `config.py` — update if real capacity obtained |
| D3 | Season tag join | Classify booking by `check_in_date` only — no multi-season explosion |
| D4 | Null segment handling | Retain as `'Unknown'` in fact table; exclude from segment-level aggregations |

---

## Metrics

| # | Metric | Formula | Grain |
|---|---|---|---|
| 1 | Occupancy Rate | `booked_room_nights / ASSUMED_TOTAL_ROOMS` | Per day |
| 2 | Occupancy Volatility (CoV) | `stddev(occupancy_rate) / mean(occupancy_rate)` | Rolling window, per segment |
| 3 | Cancellation Rate | `cancelled / total bookings` | Per segment |
| 4 | Avg Lead Time | `mean(check_in_date - booking_date)` | Per segment |
| 5 | Seasonal Concentration Index | Share of bookings in top-2 seasons vs even spread | Per segment |
| 6 | Segment Volatility Contribution | `segment_variance / total_variance` | Per segment — headline metric |
| 7 | Revenue at Risk | `SUM(room_nights * rate)` where `is_cancelled = TRUE` | Per segment |
| 8 | Revenue Volatility Index | `stddev(daily_room_revenue) / mean(daily_room_revenue)` | Per segment |

---

## Pipeline Run Sequence (for reference — full implementation Week 2+)

```bash
python -m src.ingest        # Day 6
python -m src.clean         # Days 7–8
python -m src.features      # Days 9–10
python -m src.load          # Day 11
streamlit run app/dashboard.py  # Days 16+
```

---

## Out of Scope

- Predictive / forecasting models
- Pricing recommendation engine
- Real-time / streaming ingestion
- Authentication or multi-tenant features
- Any UI framework other than Streamlit
