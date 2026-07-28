# Project Progress Report
## Occupancy Volatility & Segment Insights Dashboard

**Project:** Occupancy Volatility Index  
**Repository:** https://github.com/akhilk49/Occupancy-Volatility-Index  
**Author:** Akhil K Kurian  
**Report Date:** Day 9 checkpoint (post Day 9 PR)  
**Sprint Duration:** 20 working days (17 remaining solo from Day 8)

---

## 1. Executive Summary

This project builds a data pipeline and interactive Streamlit dashboard to answer:
> **Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors explain it?**

The pipeline ingests three raw CSV datasets (bookings, cancellations, seasonal pricing), cleans and joins them into a single enriched fact table, loads the result into SQLite, and exposes 8 KPI metrics through a parameterised query layer to the dashboard.

**Current status:** Pipeline core is complete (Days 1–9). The query layer, dashboard, tests, and documentation remain.

---

## 2. Progress by Day

### ✅ Week 1 — Discovery, PRD & Pipeline Design

| Day | Branch | What was built | Status |
|-----|--------|---------------|--------|
| 1 | `day-01-akhil` | Repo scaffold (all directories, stubs, CI, `.gitignore`, `requirements.txt`); `notebooks/01_bookings_profile.ipynb` — profiling notebook for `bookings.csv` | ✅ Merged |
| 1 | `day-01-manuel` | Team charter in `README.md`; `notebooks/02_cancellations_pricing_profile.ipynb` | ✅ Merged |
| 2 | `day-02-akhil` | Data quality findings for `bookings.csv` (duplicates, mixed date formats, segment label variants, null columns) appended to `docs/data_quality_notes.md` | ✅ Merged |
| 2 | `day-02-manuel` | Data quality findings for `cancellations.csv` and `seasonal_pricing.csv`; segment definition resolved (booking channel) | ✅ Merged |
| 3 | `day-03-akhil` | `src/ingest.py` — full typed function signatures with docstrings, `check_primary_key()` and `ingest_all()` added | ✅ Merged |
| 3 | `day-03-manuel` | `notebooks/03_dashboard_wireframe_and_metrics.md` — volatility metric definitions and dashboard wireframe | ✅ Merged |
| 4 | `day-04-akhil` | Pipeline architecture written into `SPEC.md` Section 11 (data flow diagram, tool choices, 4 architecture decisions); `PRD.md` created; `src/config.py` updated with `ASSUMED_TOTAL_ROOMS` and `CANONICAL_SEGMENTS` | ✅ Merged |
| 4 | `day-04-manuel` | `docs/pipeline_review_manuel.md` — identified 3 gaps: daily explosion for Metric #8, capacity assumption, season join rule | ✅ Merged |
| 5 | `day-05-akhil` | `sql/schema.sql` finalised — `dim_segment`, `fact_bookings_enriched` with all metric input columns, 5 indexes, 6 KPI views | ✅ Merged |

**Week 1 outcome:** PRD, SPEC, and full database schema confirmed against real-data profiling. All open questions from Section 4 resolved. Architecture decisions documented.

---

### ✅ Week 2 — Cleaning & Feature Engineering

| Day | Branch | What was built | Status |
|-----|--------|---------------|--------|
| 6 | `day-06-akhil` | `src/ingest.py` fully implemented — `load_csv()`, `validate_schema()`, `log_ingestion_summary()`, `check_primary_key()`, three `ingest_*()` functions, `ingest_all()`, `__main__` script | ✅ Merged |
| 7 | `day-07-akhil` | `src/clean.py` fully implemented (solo, absorbing Manuel's Day 7–8 scope) — `clean_bookings()`, `clean_cancellations()`, `clean_seasonal_pricing()`, `normalise_segments()`; SPEC revised for solo roadmap | ✅ Merged |
| 8 | `day-08-akhil` | `src/features.py` fully implemented — `join_fact_table()`, `add_cancel_flag()`, `add_lead_time()`, `add_occupancy_rate()`, `build_fact_table()`, `__main__` script | ✅ Merged |

**Week 2 outcome:** Full cleaning and feature engineering pipeline is runnable. `python -m src.ingest → clean → features` produces `data/processed/fact_bookings_enriched.csv`.

---

### ⏳ Week 3 — SQL, Load & Metrics (in progress)

| Day | Branch | What was built | Status |
|-----|--------|---------------|--------|
| 9 | `day-09-akhil` | `src/load.py` implemented — `load_to_sqlite()`, `verify_db()`, `_build_dim_segment()`, `_prepare_fact_df()`, `__main__` script; `sql/kpi_queries.sql` finalised with all 8 metric queries | ⏳ PR open, pending merge |
| 10 | — | `src/queries.py` — all 8 parameterised metric functions | 🔲 Next |
| 11 | — | `tests/test_data_quality.py` — CI data quality checks | 🔲 Planned |

---

### 🔲 Week 4 — Dashboard & Delivery (planned)

| Day | Scope |
|-----|-------|
| 12 | `app/dashboard.py` — sidebar filters, KPI cards, segment ranking table |
| 13 | Dashboard — CoV trend chart (Metric #2), Revenue Volatility Index chart (Metric #8) |
| 14 | Dashboard — seasonal concentration, lead time, polish; all 8 metrics visible |
| 15 | SQL optimisation + EDA notebook (cross-check SQL vs pandas) |
| 16 | Full pipeline run-through, README, `docs/findings_summary.md` |
| 17 | Viva prep, final merge |

---

## 3. What Has Been Built

### Repository structure (current state)

```
Occupancy-Volatility-Index/
├── data/
│   ├── raw/                         # CSVs placed here before running pipeline
│   ├── interim/                     # Output of src/clean.py
│   └── processed/                   # Output of src/features.py + src/load.py
├── src/
│   ├── config.py        ✅          # Paths, constants (ASSUMED_TOTAL_ROOMS, CANONICAL_SEGMENTS)
│   ├── ingest.py        ✅          # Schema validation, ingestion log, PK checks
│   ├── clean.py         ✅          # Full cleaning for all 3 source files
│   ├── features.py      ✅          # Join logic, cancel flag, lead time, occupancy rate
│   ├── load.py          ✅ (PR#13)  # SQLite loader, dim_segment, row-count verification
│   └── queries.py       🔲          # Parameterised query functions (Day 10)
├── sql/
│   ├── schema.sql       ✅          # DDL: tables, 5 indexes, 6 KPI views
│   └── kpi_queries.sql  ✅ (PR#13)  # All 8 metric queries (reference + parameterised)
├── app/
│   └── dashboard.py     🔲          # Streamlit app scaffold (Days 12–14)
├── tests/
│   └── test_data_quality.py 🔲      # CI checks (Day 11)
├── notebooks/
│   ├── 01_bookings_profile.ipynb    ✅
│   ├── 02_cancellations_pricing_profile.ipynb ✅
│   └── 03_dashboard_wireframe_and_metrics.md  ✅
├── docs/
│   ├── data_quality_notes.md        ✅
│   ├── pipeline_review_manuel.md    ✅
│   └── project_progress_report.md   ✅ (this file)
├── .github/workflows/data_quality.yml ✅
├── PRD.md               ✅
├── SPEC.md              ✅ (revised for solo)
└── requirements.txt     ✅
```

---

## 4. Pipeline — Current Run Sequence

```bash
# Step 1 — Ingest (validates schema, logs row/null counts)
python -m src.ingest

# Step 2 — Clean (dedup, date standardisation, segment normalisation)
python -m src.clean

# Step 3 — Feature engineering (joins + derived columns)
python -m src.features
# Output: data/processed/fact_bookings_enriched.csv

# Step 4 — Load into SQLite
python -m src.load
# Output: data/processed/occupancy.db

# Step 5 — Dashboard (Day 14+)
streamlit run app/dashboard.py
```

---

## 5. Architecture Decisions (confirmed)

| # | Decision | Detail |
|---|---|---|
| D1 | Daily revenue explosion (Metric #8) | Handled in SQL layer via `v_daily_revenue_by_segment` view — fact table stays at reservation grain |
| D2 | Capacity assumption (Metric #1) | `ASSUMED_TOTAL_ROOMS = 100` in `config.py` — update if real capacity obtained |
| D3 | Season tag join | Classify booking by `check_in_date` only — no multi-season ambiguity |
| D4 | Null segment handling | Null → `'Unknown'`; retained in fact table, excluded from segment aggregations |

---

## 6. Metrics Status

| # | Metric | Formula | SQL view | queries.py |
|---|--------|---------|----------|------------|
| 1 | Occupancy Rate | `booked_room_nights / 100` | `v_daily_room_nights_by_segment` ✅ | 🔲 Day 10 |
| 2 | Occupancy Volatility (CoV) | `stddev / mean` (pandas) | M1 view ✅ | 🔲 Day 10 |
| 3 | Cancellation Rate | `cancelled / total` | `v_cancellation_stats_by_segment` ✅ | 🔲 Day 10 |
| 4 | Avg Lead Time | `mean(check_in - booking_date)` | `v_lead_time_by_segment` ✅ | 🔲 Day 10 |
| 5 | Seasonal Concentration Index | top-2 seasons share (pandas) | `v_bookings_by_segment_season` ✅ | 🔲 Day 10 |
| 6 | Segment Volatility Contribution | `segment_var / total_var` (pandas) | M1 view ✅ | 🔲 Day 10 |
| 7 | Revenue at Risk | `SUM(room_nights * rate)` cancelled | `v_revenue_at_risk_by_segment` ✅ | 🔲 Day 10 |
| 8 | Revenue Volatility Index | `stddev / mean` daily revenue (pandas) | `v_daily_revenue_by_segment` ✅ | 🔲 Day 10 |

---

## 7. Key Data Quality Findings

| File | Issue | Resolution |
|------|-------|------------|
| `bookings.csv` | Mixed date formats (ISO + DD/MM/YYYY) | `pd.to_datetime(format="mixed")` in `clean.py` |
| `bookings.csv` | Duplicate `reservation_id` (non-exact) | Keep row with latest `booking_date` |
| `bookings.csv` | `total_rooms_available` absent | `ASSUMED_TOTAL_ROOMS = 100` in `config.py` |
| `bookings.csv` | Null `segment` (~some %) | Fill `'Unknown'`, retain in fact table |
| `bookings.csv` | Null `rate` | Imputed from `base_rate` after seasonal pricing join |
| `cancellations.csv` | ~15% null `reason` | Fill `'Unknown'` |
| `cancellations.csv` | Duplicate cancellation records | Keep latest `cancellation_date` |
| `cancellations.csv` | Mixed date formats | `pd.to_datetime(format="mixed")` |
| `seasonal_pricing.csv` | Exact duplicate rows | Dropped — confirmed safe |
| Segment labels | Mixed casing / abbreviations (e.g. `TA`, `Corp`) | Canonical map in `clean.py` |

---

## 8. What Remains (Days 10–17)

| Day | Deliverable | Effort |
|-----|------------|--------|
| 10 | `src/queries.py` — 10 functions, all 8 metrics | Medium |
| 11 | `tests/test_data_quality.py` — 4 CI checks | Small |
| 12 | `app/dashboard.py` — filters, KPI cards, ranking table | Medium |
| 13 | Dashboard — CoV trend + Revenue Volatility charts | Medium |
| 14 | Dashboard — seasonal concentration, lead time, polish | Medium |
| 15 | SQL index review + EDA notebook | Small |
| 16 | Full pipeline run-through + README + findings summary | Small |
| 17 | Viva preparation + final merge | Small |
