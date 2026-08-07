# Occupancy Volatility Index

**Author:** Akhil K Kurian  
**Core Question:** Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors explain it?

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/akhilk49/Occupancy-Volatility-Index
cd Occupancy-Volatility-Index
pip install -r requirements.txt

# 2. Add raw CSVs to data/raw/
#    bookings.csv | cancellations.csv | seasonal_pricing.csv
#    (or generate sample data for a demo)
python scripts/generate_sample_data.py

# 3. Run the pipeline
python -m src.ingest      # validate schema, log row/null counts
python -m src.clean       # dedup, date standardisation, segment normalisation
python -m src.features    # join fact table, derive features
python -m src.load        # load into SQLite occupancy.db

# 4. Launch the dashboard
streamlit run app/dashboard.py
```

Open **http://localhost:8501** in your browser.

---

## Repository Structure

```
Occupancy-Volatility-Index/
├── data/
│   ├── raw/                     # original CSVs — gitignored, add manually
│   ├── interim/                 # cleaned files (output of src/clean.py)
│   └── processed/               # fact table CSV + occupancy.db
├── src/
│   ├── config.py                # all paths and constants (no hardcoded paths elsewhere)
│   ├── ingest.py                # schema validation, null/PK logging
│   ├── clean.py                 # dedup, dates, segment normalisation
│   ├── features.py              # join logic, cancel flag, lead time, occupancy rate
│   ├── load.py                  # SQLite loader (idempotent)
│   └── queries.py               # all 8 parameterised metric functions
├── sql/
│   ├── schema.sql               # DDL: tables, 5 indexes, 7 KPI views
│   └── kpi_queries.sql          # reference SQL for all 8 metrics
├── app/
│   └── dashboard.py             # Streamlit dashboard (9 sections, all 8 metrics)
├── tests/
│   └── test_data_quality.py     # 31 CI checks (row counts, nulls, schema, PK, views)
├── notebooks/
│   ├── 01_bookings_profile.ipynb
│   ├── 02_cancellations_pricing_profile.ipynb
│   ├── 03_dashboard_wireframe_and_metrics.md
│   └── 04_eda_occupancy_trends.ipynb
├── scripts/
│   ├── generate_sample_data.py  # creates demo CSVs with intentional DQ issues
│   └── spot_check.py            # quick DB query verification
├── docs/
│   ├── data_quality_notes.md
│   ├── findings_summary.md
│   └── project_progress_report.md
├── .github/workflows/
│   └── data_quality.yml         # CI: pytest on every push/PR
├── PRD.md
├── SPEC.md
└── requirements.txt
```

---

## Dashboard Sections

| Section | Content | Metrics |
|---------|---------|---------|
| A | KPI cards — occupancy rate, revenue at risk, most volatile segment, highest cancel rate | #1, #3, #6, #7 |
| B | Segment ranking table — all 8 metrics side by side | All |
| C | Daily occupancy rate line chart + CoV cards | #1, #2 |
| D | Volatility contribution bar chart (headline metric) | #6 |
| E | Revenue at risk bar chart | #7 |
| F | Revenue Volatility Index bar chart + table | #8 |
| G | Seasonal Concentration Index | #5 |
| H | Average lead time bar chart + table | #4 |
| I | Cancellation rate bar chart + table | #3 |

All sections respond to the sidebar filters (date range, segment).

---

## Data Contracts

| File | Schema |
|------|--------|
| `bookings.csv` | `reservation_id, segment, room_type, booking_date, check_in_date, check_out_date, nights, rate` |
| `cancellations.csv` | `reservation_id, cancellation_date, reason, refund_status` |
| `seasonal_pricing.csv` | `date, season_tag, base_rate, demand_tier` |

`total_rooms_available` is absent from the raw data. Capacity is assumed as `ASSUMED_TOTAL_ROOMS = 100` in `src/config.py`. Update this value if the real capacity is known.

---

## Key Architecture Decisions

| # | Decision |
|---|----------|
| D1 | Daily revenue explosion (Metric #8) handled in SQL view — fact table stays at reservation grain |
| D2 | Capacity = `ASSUMED_TOTAL_ROOMS = 100` in `config.py` |
| D3 | Season tag classified by `check_in_date` only (no multi-season ambiguity) |
| D4 | Null segment → `'Unknown'`; retained in fact table, excluded from segment aggregations |

---

## Metrics

| # | Metric | Formula |
|---|--------|---------|
| 1 | Occupancy Rate | `booked_room_nights / ASSUMED_TOTAL_ROOMS` per day |
| 2 | Occupancy Volatility (CoV) | `stddev(occupancy_rate) / mean(occupancy_rate)` per segment |
| 3 | Cancellation Rate | `cancelled / total bookings` per segment |
| 4 | Avg Lead Time | `mean(check_in_date - booking_date)` per segment |
| 5 | Seasonal Concentration Index | top-2 season share / even baseline |
| 6 | Segment Volatility Contribution | `segment_variance / total_variance` — **headline** |
| 7 | Revenue at Risk | `SUM(room_nights * rate)` where `is_cancelled = TRUE` |
| 8 | Revenue Volatility Index | `stddev(daily_revenue) / mean(daily_revenue)` per segment |

---

## Running Tests

```bash
pytest tests/ -v
```

31 tests covering raw file schema, cleaning retention, fact table PK/nulls/schema drift, and all 7 DB views. Tests skip gracefully when data files are absent (CI-safe on fresh clones).

---

## Team Charter

**Project:** Occupancy Volatility Index  
**Sprint:** 4 weeks / 20 working days  
**Solo from Day 8:** Akhil K Kurian (Manuel Beracah contributed Days 1–6)

**Individual contribution commitment:**
- One PR per working day, each with a clear scope and done-when criteria
- No direct pushes to `main` — all work goes through reviewed PRs
- Every cleaning/architectural decision is documented in code comments and `SPEC.md`
