# SPEC.md — Occupancy Volatility Index

**Purpose of this file:** This is the authoritative build spec for an agentic coding IDE (Claude Code, Cursor, etc.) working on this repository. Read this fully before generating or modifying any code. When asked to "implement Day N," find Day N in Section 7 and build exactly that scope — nothing from later days, nothing skipped from earlier ones.

Repo: https://github.com/akhilk49/Occupancy-Volatility-Index
Team: Akhil K Kurian, Manuel Beracah

---

## 1. Problem & Objective

A hotel chain collects booking trends, cancellation history, and seasonal pricing records, but revenue teams cannot tell which customer segments contribute most to occupancy volatility.

Build a pipeline + dashboard that joins bookings, cancellations, and seasonal pricing data to answer:

> **Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors — including revenue impact — explain it?**

The deliverable is a Streamlit dashboard, backed by a SQL layer, backed by a Python/Pandas cleaning pipeline, with CI-enforced data quality.

## 2. Non-Goals

Do not build any of the following, even if it seems like a natural extension:
- Predictive/forecasting models (this project is diagnostic, not predictive)
- A pricing recommendation engine
- Real-time or streaming ingestion — batch/static CSVs only
- Authentication, multi-tenant, or user-management features
- Any UI framework other than Streamlit for the dashboard

## 3. Tech Stack (fixed — do not substitute)

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Ingestion & validation | Python (stdlib + pandas) |
| Cleaning & transformation | Pandas |
| Storage | SQLite for local dev (`data/processed/occupancy.db`); schema must be Postgres-portable |
| Dashboard | Streamlit |
| CI | GitHub Actions |
| Testing | pytest |
| Dependency management | `requirements.txt` (pinned versions) |

Do not introduce additional frameworks (no Django/Flask, no dbt, no Airflow) — this is a small, direct pipeline by design.

## 4. Data Contracts

Raw files live in `data/raw/` and are **never modified in place**. Schema below reflects confirmed findings from Day 1–2 profiling.

### `bookings.csv` (1 row per reservation)
`reservation_id, segment, room_type, booking_date, check_in_date, check_out_date, nights, rate`

> **Day 1 update:** `total_rooms_available` is **absent** from the raw file. Capacity is handled via `ASSUMED_TOTAL_ROOMS` in `src/config.py` (see Section 11).

### `cancellations.csv` (1 row per cancellation event)
`reservation_id, cancellation_date, reason, refund_status`

### `seasonal_pricing.csv` (1 row per date/period)
`date, season_tag, base_rate, demand_tier`

### Join logic
- `bookings` LEFT JOIN `cancellations` ON `reservation_id` (most bookings do not cancel)
- `bookings` JOIN `seasonal_pricing` ON `check_in_date = date` (classification based on check-in date only — see Section 11 decision D3)
- Output: single fact table `fact_bookings_enriched`, one row per reservation

### Open questions resolved (Day 1–2)
| Question | Resolution |
|---|---|
| Is `segment` channel or customer-type? | **Booking channel** — canonical values: `Travel Agency`, `Direct`, `Corporate`, `Group`, `Walk-in` |
| Occupancy grain? | **Room-night grain** — each booking contributes `nights` room-nights |
| Does `total_rooms_available` exist? | **No** — use `ASSUMED_TOTAL_ROOMS` constant from `config.py` |
| Consistent date range across files? | To be validated in Day 9 join step (Manuel's scope) |

## 5. Metrics — Exact Definitions

Implement these exactly; do not invent alternate formulas.

| # | Metric | Formula |
|---|---|---|
| 1 | Occupancy Rate | `booked_room_nights / available_room_nights` (per day) |
| 2 | Occupancy Volatility (CoV) | `stddev(occupancy_rate) / mean(occupancy_rate)` over a rolling window, per segment |
| 3 | Cancellation Rate | `cancelled_bookings / total_bookings`, per segment |
| 4 | Avg Lead Time | `mean(check_in_date - booking_date)`, per segment |
| 5 | Seasonal Concentration Index | share of a segment's bookings falling in its top-2 seasons vs. an even spread |
| 6 | Segment Volatility Contribution | `segment_variance / total_variance` — **the headline metric** |
| 7 | Revenue at Risk | `SUM(room_nights * rate)` where `is_cancelled = TRUE`, per segment |
| 8 | Revenue Volatility Index | `stddev(daily_room_revenue) / mean(daily_room_revenue)`, per segment |

## 6. Repository Structure (authoritative — do not reorganize without updating this file)

```
Occupancy-Volatility-Index/
├── data/
│   ├── raw/                  # original CSVs, untouched, gitignored except .gitkeep
│   ├── interim/               # after cleaning, before feature engineering
│   └── processed/             # final fact table + occupancy.db, ready for SQL load
├── src/
│   ├── ingest.py              # reads raw CSVs, validates schema, logs issues
│   ├── clean.py                # nulls, dedup, date standardization, segment normalization
│   ├── features.py             # occupancy_rate, lead_time, cancel_flag, season_tag join
│   ├── load.py                  # loads processed data into SQLite
│   └── queries.py                # parameterized query functions used by the Streamlit app
├── sql/
│   ├── schema.sql                # table + view definitions (source of truth)
│   └── kpi_queries.sql            # reusable KPI + volatility queries
├── app/
│   └── dashboard.py                # Streamlit entry point
├── tests/
│   └── test_data_quality.py         # row count, null %, schema-drift checks — used by CI
├── .github/
│   ├── workflows/data_quality.yml    # CI: runs tests on every push/PR
│   └── PULL_REQUEST_TEMPLATE.md
├── notebooks/                        # EDA only — never import from here in src/
├── README.md
├── PRD.md
├── SPEC.md                            # this file
└── requirements.txt
```

## 7. Day-by-Day Build Roadmap (4 weeks / 20 working days)

> **Solo from Day 8 onwards.** Manuel left the project after Day 6. Days 1–7 are complete.
> From Day 8, all work is Akhil's sole responsibility. Each day is a single PR (`day-XX-akhil`).
> The plan below absorbs all remaining Manuel scope into the solo schedule.

### ✅ Week 1 — Discovery, PRD & Pipeline Design (COMPLETE)

- **Day 1** ✅ Repo scaffold + `bookings.csv` profiling notebook
- **Day 2** ✅ Document `bookings.csv` data quality issues; segment definition resolved
- **Day 3** ✅ Draft `ingest.py` function signatures and docstrings
- **Day 4** ✅ Pipeline architecture written into `SPEC.md` / `PRD.md`; Manuel's review gaps addressed
- **Day 5** ✅ `sql/schema.sql` finalised — all metric input columns, 5 indexes, 6 KPI views

### ✅ Week 2 — Data Cleaning & Feature Engineering (Days 6–7 complete)

- **Day 6** ✅ Implement `ingest.py` — schema validation, ingestion log, PK check
- **Day 7** ✅ Implement full `clean.py` — bookings, cancellations, seasonal pricing, segment normalisation

---

### 🔨 Week 2 continued — Feature Engineering (solo)

- **Day 8** — Implement `features.py`: join logic + all feature columns
  - `join_fact_table()` — bookings LEFT JOIN cancellations, JOIN seasonal_pricing on check_in_date
  - `add_cancel_flag()` — boolean is_cancelled from join result
  - `add_lead_time()` — check_in_date minus booking_date in days
  - `add_occupancy_rate()` — room_nights / ASSUMED_TOTAL_ROOMS per day
  - Write fact table to `data/processed/fact_bookings_enriched.csv`
  - Validate: row count matches bookings (no silent drops); log any unmatched reservation_ids
  - *Done when:* `python -m src.features` produces `fact_bookings_enriched.csv` with all columns from SPEC Section 5

### 🔨 Week 3 — SQL, Load & Metrics (solo)

- **Day 9** — Implement `load.py` + full `sql/kpi_queries.sql`
  - `load_to_sqlite()` — execute `schema.sql` DDL, populate `dim_segment` + `fact_bookings_enriched`
  - `kpi_queries.sql` — complete all 8 metric queries (Metrics #1–#8), including CoV and daily revenue explosion
  - *Done when:* `data/processed/occupancy.db` exists; all views return results; every query in `kpi_queries.sql` runs without error

- **Day 10** — Implement `src/queries.py` — all parameterised query functions
  - `get_occupancy_by_segment_day()` — Metric #1
  - `get_occupancy_volatility_cov()` — Metric #2 (rolling CoV computed in pandas after SQL fetch)
  - `get_cancellation_rate_by_segment()` — Metric #3
  - `get_avg_lead_time_by_segment()` — Metric #4
  - `get_seasonal_concentration()` — Metric #5
  - `get_segment_volatility_contribution()` — Metric #6 (headline metric)
  - `get_revenue_at_risk()` — Metric #7
  - `get_revenue_volatility_index()` — Metric #8
  - *Done when:* every function returns a non-empty DataFrame when called against `occupancy.db`

- **Day 11** — Write `tests/test_data_quality.py` + CI validation
  - Row count checks: processed fact table within expected range of raw input
  - Null % checks: critical columns (`segment_id`, `check_in_date`, `room_nights`) below threshold
  - Schema drift check: all required columns present in `fact_bookings_enriched`
  - Duplicate PK check: `reservation_id` unique in processed fact table
  - Update `.github/workflows/data_quality.yml` to also run against processed data
  - *Done when:* `pytest tests/ -v` passes locally and CI badge is green

### 🔨 Week 4 — Dashboard, Polish & Delivery (solo)

- **Day 12** — Implement `app/dashboard.py` — structure + segment ranking view
  - Page config, sidebar with global filters (date range, season, segment)
  - Section A: KPI cards — overall occupancy rate, total revenue at risk, most volatile segment
  - Section B: segment volatility ranking table (Metric #6) with cancellation rate, lead time, revenue at risk
  - *Done when:* `streamlit run app/dashboard.py` boots without errors and Section B renders with real data

- **Day 13** — Add volatility trend chart + revenue views to dashboard
  - Section C: time-series CoV chart per segment (Metric #2), segment overlay
  - Revenue Volatility Index chart (Metric #8)
  - All charts respect sidebar filters
  - *Done when:* every chart renders; segment filter updates all visuals

- **Day 14** — Add remaining metric views + polish
  - Seasonal concentration chart (Metric #5)
  - Lead time distribution per segment (Metric #4)
  - Narrative text / tooltips explaining each metric
  - Visual polish: consistent colour scheme, axis labels, responsive layout
  - *Done when:* all 8 metrics from SPEC Section 5 are visible and filterable in the running app

- **Day 15** — SQL optimisation + EDA notebook
  - Review query plans; add any missing indexes identified during dashboard testing
  - `notebooks/04_eda_occupancy_trends.ipynb` — segment occupancy trends, CoV cross-check against SQL
  - Validate SQL output vs notebook output for at least one spot-checked segment
  - *Done when:* every dashboard query returns under 1 second; notebook runs end-to-end

- **Day 16** — Final pipeline run-through + documentation
  - Run full pipeline from scratch: `python -m src.ingest` → `clean` → `features` → `load` → `streamlit run`
  - Document the one-command sequence in `README.md`
  - Update `SPEC.md` Section 11.4 ownership table to reflect solo authorship
  - Write `docs/findings_summary.md` — which segments are most volatile, why
  - *Done when:* a person with no prior context can clone the repo and get the dashboard running using only `README.md`; findings summary answers the core business question

- **Day 17** — Viva preparation
  - Write viva answer notes covering: every pipeline decision, every metric formula, every cleaning decision, every SQL/index choice, dashboard design rationale
  - Final PR merged, README verified verbatim
  - *Done when:* can explain every technical decision independently without referring to code

## 8. Git & PR Conventions (solo from Day 8)

One PR per day, branch named `day-XX-akhil`, merged into `main`.

### Branching
- Each day: `git checkout main && git pull origin main`
- Create branch: `git checkout -b day-XX-akhil`
- Push: `git push -u origin day-XX-akhil`
- Open PR titled `Day N (Akhil): <scope>`

### Commit message format
`day-XX-akhil: <what was built>`

Example: `day-08-akhil: implement features.py — join logic and all feature columns`

### Merge rule
- Do not merge a PR unless the day's "done when" criteria are fully met.
- Carry incomplete work forward rather than faking completion.

## 9. Coding Conventions

- PEP 8, type hints on all function signatures, docstrings on all public functions.
- Small, single-purpose functions in `src/` — no notebook-style top-to-bottom scripts.
- No hardcoded file paths — read from a `config.py` or constants at the top of each module.
- Every cleaning decision (null handling, dedup, imputation) needs an inline comment explaining *why*, not just *what*.
- `notebooks/` is for exploration only. Anything reused in the pipeline gets promoted into `src/`.

## 11. Pipeline Architecture (confirmed Day 4)

### 11.1 Data Flow

```
data/raw/
  bookings.csv
  cancellations.csv          ──► src/ingest.py
  seasonal_pricing.csv            │
                                  │  • load_csv() — read-only, no transforms
                                  │  • validate_schema() — flag missing cols
                                  │  • log_ingestion_summary() — row/null counts
                                  │  • check_primary_key() — flag duplicate IDs
                                  ▼
                             src/clean.py
                                  │
                                  │  bookings:  dedup, date standardisation,
                                  │             null handling, segment normalisation
                                  │  cancellations: dedup, date standardisation
                                  │  seasonal_pricing: dedup, date alignment
                                  ▼
                             data/interim/
                               bookings_clean.csv
                               cancellations_clean.csv
                               seasonal_pricing_clean.csv
                                  │
                                  ▼
                             src/features.py
                                  │
                                  │  • join_fact_table() — LEFT JOIN + season JOIN
                                  │  • add_cancel_flag() — is_cancelled boolean
                                  │  • add_lead_time() — check_in - booking_date
                                  │  • add_occupancy_rate() — room-night grain
                                  ▼
                             data/processed/
                               fact_bookings_enriched.csv
                                  │
                                  ▼
                             src/load.py
                                  │
                                  │  • Executes sql/schema.sql DDL
                                  │  • Populates dim_segment + fact_bookings_enriched
                                  ▼
                             data/processed/occupancy.db  (SQLite)
                                  │
                                  ▼
                             src/queries.py  ◄──── app/dashboard.py
                                  │
                                  │  Parameterised query functions — no raw SQL
                                  │  in the Streamlit layer
                                  ▼
                             Streamlit dashboard
```

### 11.2 Tool choices and rationale

| Step | Tool | Rationale |
|---|---|---|
| Ingestion & validation | pandas + stdlib | Sufficient for static CSVs; no streaming or scheduling needed |
| Cleaning & transformation | pandas | Familiar, auditable, one function per decision |
| Storage | SQLite (local) | Zero-setup for dev; schema written Postgres-portable for easy migration |
| SQL layer | SQLAlchemy (text queries) | Keeps queries in `.sql` files, not f-strings; safe parameterisation |
| Dashboard | Streamlit | Specified in SPEC — not substitutable |
| CI | GitHub Actions | Free for public repos; runs pytest on every push/PR |

### 11.3 Architecture decisions (Day 4)

**D1 — Daily revenue explosion for Metric #8 (Revenue Volatility Index)**

Manuel's Day 4 review flagged that `fact_bookings_enriched` is at reservation grain, but Metric #8 requires `daily_room_revenue`. Decision: **handle this in the SQL layer, not the Python pipeline**. `kpi_queries.sql` will join the fact table with a date-spine (generated via a recursive CTE or a `dim_date` table) to explode multi-night bookings into daily revenue rows for this metric only. The fact table stays at reservation grain — simpler pipeline, no intermediate exploded CSV.

**D2 — Capacity assumption for Metric #1 (Occupancy Rate)**

`total_rooms_available` is absent from `bookings.csv` (confirmed Day 1). Decision: introduce `ASSUMED_TOTAL_ROOMS: int = 100` in `src/config.py` as an explicit, documented constant. All occupancy rate calculations use this value. If the real capacity figure is obtained later, it is updated in one place. This assumption is flagged in every query and dashboard tooltip that uses Metric #1.

**D3 — Season tag join on check-in date only**

Manuel's review noted that bookings spanning multiple seasons create ambiguity. Decision: classify the entire booking's season based strictly on its `check_in_date`. This is the simplest consistent rule, avoids exploding the fact table for the join, and matches how the hotel operationally assigns a season to a stay. Documented here so it is not re-debated downstream.

**D4 — Segment null handling**

Rows where `segment` is null cannot be attributed to any channel. Decision: retain these rows in the fact table with `segment_name = 'Unknown'` so total row counts are preserved. They are excluded from segment-level metric aggregations (GROUP BY will not group them with any real segment).

### 11.4 File-level ownership (pipeline modules)

> Solo from Day 8. All files owned by Akhil K Kurian.

| File | Implemented | Status |
|---|---|---|
| `src/config.py` | Day 1 | ✅ |
| `src/ingest.py` | Day 6 | ✅ |
| `src/clean.py` — all three files | Day 7 | ✅ |
| `src/features.py` — full | Day 8 | ✅ |
| `src/load.py` | Day 9 | ✅ |
| `src/queries.py` — all 8 metrics | Day 10 | ✅ |
| `sql/schema.sql` | Day 5 | ✅ |
| `sql/kpi_queries.sql` | Day 9 | ✅ |
| `tests/test_data_quality.py` | Day 11 | ✅ |
| `app/dashboard.py` — full (9 sections, all 8 metrics) | Days 12–14 | ✅ |
| `notebooks/04_eda_occupancy_trends.ipynb` | Day 15 | ✅ |
| `docs/findings_summary.md` | Day 16 | ✅ |
| `docs/viva_notes.md` | Day 17 | ✅ |
| `README.md` — complete run guide | Day 16 | ✅ |

## 10. Global Definition of Done (Sprint 1)

- Clean, joined, version-controlled dataset with documented cleaning decisions
- SQL layer with reproducible KPI, volatility, and revenue-at-risk queries
- Live Streamlit dashboard covering all 8 metrics in Section 5, filterable by segment/season/date
- GitHub Actions passing data quality checks on every push
- Both team members can independently explain every technical decision during viva
