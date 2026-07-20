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

Each day splits into an **Akhil scope** and a **Manuel scope** — each becomes its own branch and its own PR (see Section 8). Where a day also has a joint item (repo setup, mentor submission), it's folded into one of the two PRs, alternating whose PR carries it.

### Week 1 — Discovery, PRD & Pipeline Design
Gate: nothing in `src/` beyond stubs/exploration until PRD + this spec are confirmed against the real data.

- **Day 1**
  - *Akhil:* Profile `bookings.csv` — columns, nulls, dtypes, duplicates, date formats. *Done when:* profiling notes committed under `notebooks/`.
  - *Manuel:* Profile `cancellations.csv` and `seasonal_pricing.csv` — same checks. *Done when:* profiling notes committed under `notebooks/`.
  - *Joint (in Akhil's PR):* repo scaffold confirmed, branch protection, Kanban board set up.
  - *Joint (in Manuel's PR):* Team Charter filled into `README.md`.

- **Day 2**
  - *Akhil:* Document data quality issues found in `bookings.csv` (duplicates, bad dates, inconsistent segment labels).
  - *Manuel:* Document data quality issues in `cancellations.csv` + `seasonal_pricing.csv`.
  - *Both, done when:* each person's findings appended to `docs/data_quality_notes.md` under their own name/section; segment-definition open question (Section 4) discussed and resolved or escalated to mentor.

- **Day 3**
  - *Akhil:* Draft `ingest.py` function signatures + docstrings (no implementation yet).
  - *Manuel:* Draft volatility metric definitions (Section 5) and dashboard wireframe/user flow.
  - *Done when:* `src/ingest.py` has stub signatures; a wireframe sketch or notes file exists under `notebooks/`.

- **Day 4**
  - *Akhil:* Write the pipeline architecture section (data flow, tool choices) into `SPEC.md`/`PRD.md`.
  - *Manuel:* Review pipeline design against dashboard needs; flag gaps.
  - *Done when:* both docs reflect the confirmed real-data schema; Manuel's review comments addressed in Akhil's PR or a follow-up commit.

- **Day 5**
  - *Akhil:* Finalize `sql/schema.sql`.
  - *Manuel:* Finalize the metric list + wireframe; help proofread PRD/SPEC before mentor submission.
  - *Done when:* schema file matches Section 4/5; PRD + pipeline design submitted for mentor approval.

### Week 2 — Data Cleaning & Feature Engineering
- **Day 6**
  - *Akhil:* Implement `ingest.py` — schema validation + ingestion log. *Done when:* running it against `data/raw/*.csv` prints row counts and flags missing required columns.
  - *Manuel:* Set up `data/interim/` and `data/processed/` folder conventions; write the loader stub in `notebooks/` for early EDA. *Done when:* folder structure committed, EDA notebook can read from `data/raw/`.

- **Day 7**
  - *Akhil:* Implement `clean.py` for `bookings.csv` — nulls, duplicates, date standardization.
  - *Manuel:* Implement `clean.py` for `cancellations.csv` — match reservation IDs, standardize dates.
  - *Done when:* each person's cleaned output lands in `data/interim/`; every cleaning decision has a one-line justification comment in their own function.

- **Day 8**
  - *Akhil:* Normalize segment labels (spelling/casing inconsistencies) into one canonical list.
  - *Manuel:* Clean `seasonal_pricing.csv`; align its date range with bookings.
  - *Done when:* a single canonical segment list exists and both people's cleaned files use it.

- **Day 9**
  - *Akhil:* Implement the join logic in `features.py` — bookings + cancellations + seasonal pricing into one fact table.
  - *Manuel:* Validate the joined fact table's row counts against raw inputs (catch silent drops); write a short validation report.
  - *Done when:* joined table written to `data/processed/`; Manuel's validation confirms no unexplained row loss.

- **Day 10**
  - *Akhil:* Engineer `lead_time_days` and `is_cancelled` flag.
  - *Manuel:* Engineer `occupancy_rate` (at the grain confirmed Day 1) and `season_tag`.
  - *Done when:* the processed fact table has every column listed in Section 5's metric inputs.

### Week 3 — SQL, Metrics & Analysis
- **Day 11**
  - *Akhil:* Implement `load.py` — create `dim_segment` + `fact_bookings_enriched` in SQLite from `schema.sql`.
  - *Manuel:* Draft the EDA notebook — first look at occupancy trends by segment, independent of the SQL layer (used to cross-check later).
  - *Done when:* `data/processed/occupancy.db` exists and round-trips correctly; EDA notebook runs end-to-end.

- **Day 12**
  - *Akhil:* Write KPI queries — occupancy rate by segment/day (Metric #1) — in `sql/kpi_queries.sql` and `src/queries.py`.
  - *Manuel:* Compute rolling CoV of occupancy per segment (Metric #2) in the EDA notebook.
  - *Done when:* SQL output and notebook output agree on the same numbers for a spot-checked segment.

- **Day 13**
  - *Akhil:* Write cancellation-rate and lead-time queries by segment (Metrics #3, #4).
  - *Manuel:* Rank segments by volatility contribution (Metric #6); identify the top 2-3 volatile segments.
  - *Done when:* every segment has values for Metrics #3, #4, #6, backed by both the SQL layer and the notebook.

- **Day 14**
  - *Akhil:* Write the seasonal concentration query (Metric #5) and Revenue at Risk query (Metric #7).
  - *Manuel:* Write the Revenue Volatility Index (Metric #8) in the notebook; dig into *why* top segments are volatile.
  - *Done when:* every segment has a complete row across all 8 metrics.

- **Day 15**
  - *Akhil:* Optimize/index the SQL layer for dashboard-speed queries.
  - *Manuel:* Draft the 1-page findings summary ("which segments, why").
  - *Done when:* every query used by the app returns in well under 1 second; findings summary validated against the core business question.

### Week 4 — Dashboard, Testing & Delivery
- **Day 16**
  - *Akhil:* Set up `.github/workflows/data_quality.yml`.
  - *Manuel:* Scaffold `app/dashboard.py` — layout, segment ranking view.
  - *Done when:* CI runs `pytest tests/` on every push; dashboard boots with `streamlit run app/dashboard.py`.

- **Day 17**
  - *Akhil:* Write `tests/test_data_quality.py` (row counts, null %, schema drift, duplicate PK).
  - *Manuel:* Build the volatility trend chart + segment filter in the dashboard.
  - *Done when:* tests pass locally and in CI; trend chart renders with working filter.

- **Day 18**
  - *Akhil:* SQL query tuning to keep the dashboard responsive.
  - *Manuel:* Add season/date-range filters and revenue-at-risk KPI cards to the dashboard.
  - *Done when:* every metric in Section 5 is visible and filterable in the running app.

- **Day 19**
  - *Akhil:* Final pipeline run-through — raw CSV to dashboard, one documented command sequence.
  - *Manuel:* Polish visuals, labels, and narrative text in the app.
  - *Done when:* a teammate who didn't write the code can run it from a clean clone and get the same dashboard.

- **Day 20**
  - *Akhil:* Prepare viva answers for pipeline & SQL decisions.
  - *Manuel:* Prepare viva answers for analysis & dashboard decisions.
  - *Done when:* final PRs merged; README's "how to run this" section works verbatim; both can explain every decision independently.

## 8. Git & PR Conventions — Individual Daily PRs

Both teammates contribute equally and visibly: **each person opens their own PR every day**, not one shared team PR. This makes individual contribution obvious in the commit history and satisfies "who did what" for grading/viva.

### Branching
- Each morning, both pull latest `main`: `git checkout main && git pull`
- Each creates their own branch off `main`: `day-XX-akhil` and `day-XX-manuel` (e.g. `day-07-akhil`, `day-07-manuel`)
- Work only inside your own branch/scope for the day (see Section 7 — the day-wise plan already splits tasks by person for exactly this reason)

### Opening PRs
- Each person opens their own PR from their branch into `main`, titled `Day N (Akhil): <scope>` or `Day N (Manuel): <scope>`
- Each PR is reviewed by the *other* teammate before merge — this is what makes it a review, not a rubber stamp
- Both PRs for the day should be open and visible before either is merged, so the day's full scope is reviewable together

### Merge order & avoiding conflicts
- Decide each morning who merges first for that day (alternate, or whoever finishes first) — call this the "first merger"
- The **first merger** merges their PR into `main` once reviewed
- The **second merger** then runs `git checkout day-XX-<name> && git pull --rebase origin main`, resolves any conflicts locally, pushes with `git push --force-with-lease`, and merges
- To minimize conflicts in the first place: if a day's tasks touch the same file (check Section 7's per-day split), the two of you briefly agree who owns which function/section before starting, rather than discovering the overlap at merge time

### Joint tasks (repo setup, standups, shared docs)
- Days with a "Joint / Team" column in Section 7 (e.g. Day 1 repo setup, Day 5 PRD submission) still get logged as work, but don't need a third PR
- Split joint items across the two individual PRs that day (e.g. Akhil's PR includes the branch-protection setup, Manuel's PR includes the Team Charter fill-in) — alternate who carries the joint item each day so it's not always the same person's PR

### Commit & PR conventions
- Commit messages: `day-07-akhil: standardize booking_date and check_in_date formats`
- PR description must state: what was built, which Section 7 "done when" criteria are met (your half of them), and who reviewed
- No direct pushes to `main` — every day's work goes through a PR, even if scopes don't overlap
- Do not merge a PR if its portion of the day's "done when" criteria isn't met — carry it forward rather than faking completion

### Daily checklist
1. Pull `main`, branch as `day-XX-<yourname>`
2. Do your assigned scope from Section 7
3. Push, open your PR, tag the other person as reviewer
4. Review the other person's PR
5. Merge in agreed order, rebase-and-resolve if needed
6. Both submit individual daily journal entries (per PRD Block 1 standard)

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

| File | Owner | Implemented |
|---|---|---|
| `src/config.py` | Akhil | Day 1 |
| `src/ingest.py` | Akhil | Day 6 |
| `src/clean.py` — bookings | Akhil | Day 7–8 |
| `src/clean.py` — cancellations | Manuel | Day 7 |
| `src/clean.py` — seasonal_pricing | Manuel | Day 8 |
| `src/features.py` — join | Akhil | Day 9 |
| `src/features.py` — lead_time, cancel_flag | Akhil | Day 10 |
| `src/features.py` — occupancy_rate, season_tag | Manuel | Day 10 |
| `src/load.py` | Akhil | Day 11 |
| `src/queries.py` | Akhil | Days 12–14 |
| `sql/schema.sql` | Akhil | Day 5 |
| `sql/kpi_queries.sql` | Akhil | Days 12–14 |
| `app/dashboard.py` | Manuel | Days 16–19 |
| `tests/test_data_quality.py` | Akhil | Day 17 |

## 10. Global Definition of Done (Sprint 1)

- Clean, joined, version-controlled dataset with documented cleaning decisions
- SQL layer with reproducible KPI, volatility, and revenue-at-risk queries
- Live Streamlit dashboard covering all 8 metrics in Section 5, filterable by segment/season/date
- GitHub Actions passing data quality checks on every push
- Both team members can independently explain every technical decision during viva
