# Project Showcase — Speaker Notes
## Occupancy Volatility Index
### Akhil K Kurian

---

> **How to use this doc:** Each slide heading is what goes on screen. The text under it is what you say. Timing estimates are rough guides. Adjust based on your slot length.

---

## SLIDE 1 — Title
**On screen:** Occupancy Volatility Index · Akhil K Kurian

**Say:**
Good [morning/afternoon]. My name is Akhil. This project is called the Occupancy Volatility Index — a data pipeline and analytics dashboard built for a hotel revenue team.

The question it answers is: which customer segments are driving occupancy instability, and what's causing it? That's the entire motivation and the thread that runs through every technical decision I'll walk you through today.

---

## SLIDE 2 — Problem Statement
**On screen:** A hotel chain has booking, cancellation, and pricing data — but can't tell which segments drive occupancy volatility.

**Say:**
The hotel has three datasets — bookings, cancellations, and seasonal pricing. They have the data but no way to connect it into a single view.

The revenue team's actual problem is this: some days the hotel is at 80% occupancy, other days it drops to 20%, and they don't know why or which customer type is responsible. They can't price correctly, can't forecast staffing, and can't make segment-specific policy decisions.

The core question we're answering is: which booking channels contribute most to occupancy volatility, and what behaviours — cancellation patterns, booking timing, seasonal clustering — explain it?

This is a diagnostic project, not a predictive one. We're not forecasting; we're explaining what's already happened.

---

## SLIDE 3 — What We Built
**On screen:** Pipeline → SQLite DB → Streamlit Dashboard · 8 KPI metrics · CI-enforced data quality

**Say:**
The deliverable is three things:

One — a Python data pipeline that takes three raw CSVs, cleans them, joins them into a single fact table, and loads that into a SQLite database. Every step is auditable, every cleaning decision is documented.

Two — a SQL layer with 7 views and 5 indexes covering all 8 metrics. The schema is Postgres-portable, so it can be migrated to a production database without rewriting anything.

Three — a Streamlit dashboard that lets a revenue manager filter by date range and booking channel and see all 8 metrics in one place.

The whole thing runs with five commands. I'll show you that shortly.

---

## SLIDE 4 — Architecture
**On screen:** raw CSVs → ingest → clean → features → SQLite → queries.py → dashboard

**Say:**
The pipeline has five stages.

Ingest: reads the three CSVs, validates that required columns are present, logs row counts and null percentages, and flags duplicate primary keys. It doesn't touch the data — that's clean.py's job.

Clean: handles nulls, exact duplicates, non-exact duplicates, mixed date formats, logically invalid stays, and segment label variants. Every decision has an inline comment explaining why, not just what.

Features: joins the three cleaned files into one fact table — bookings LEFT JOIN cancellations, then LEFT JOIN seasonal pricing on check-in date. Derives cancel flag, lead time, and occupancy rate as new columns.

Load: executes the schema DDL, populates the segment dimension table, and inserts the fact table into SQLite. Verifies the row count matches after load.

Queries: eight parameterised functions, one per metric. The dashboard never writes SQL — it only calls these functions.

I'll point out one deliberate decision here: the fact table stays at reservation grain, not room-night grain. For most metrics that's fine. For Metric 8 — Revenue Volatility Index — we need daily revenue, so we handle that in a SQL view rather than exploding the Python dataset. That keeps the pipeline simple without sacrificing correctness.

---

## SLIDE 5 — The Data Challenge
**On screen:** What we found in the raw data before we could build anything

**Say:**
Before I could write a single line of pipeline code, I spent two days profiling the raw data and documenting what was wrong with it. Here's what we found.

In bookings.csv: date columns had three different formats — ISO, DD/MM/YYYY, and MM-DD-YYYY mixed within the same column. There were exact duplicate rows, and also duplicate reservation IDs with different field values — meaning the same reservation was logged twice with a different rate. The total_rooms_available column was listed in the schema but completely absent from the actual file. Segment labels had 15+ variants — "TA", "travel agency", "T/A" — all meaning the same thing.

In cancellations.csv: about 15% of the reason field was null. One reservation had its cancellation logged twice. Some dates were in MM/DD/YYYY format.

In seasonal_pricing.csv: exact duplicate rows for a few dates. Otherwise clean.

The reason I'm telling you this is because the pipeline isn't just a loader — it's a documented set of decisions about how to handle real-world data quality problems. Every one of those issues has a specific resolution that I can point to in the code.

---

## SLIDE 6 — Key Data Quality Decisions
**On screen:** 12 documented cleaning decisions — each one has a reason

**Say:**
Let me call out the ones that matter most.

Mixed date formats — we use pandas to_datetime with format equals "mixed". In pandas 3.x, the old infer_datetime_format parameter was removed, so we had to adapt to the new API. That's not obvious from the docs and it caused a real failure during development.

Duplicate reservation IDs with different values — we keep the row with the latest booking date, because that's the most recent and therefore authoritative record. The earlier record was likely a data entry error.

Total rooms available being absent — rather than silently failing, we made the assumption explicit as ASSUMED_TOTAL_ROOMS equals 100 in config.py. It's a single constant in one file. Anyone who has the real capacity figure changes one line and the entire pipeline recalculates correctly.

Null segments — we don't drop them, because dropping them would lose booking records and corrupt row counts. We set them to "Unknown" so they're visible in the data but excluded from segment-level aggregations.

Rate nulls — we don't impute them at clean time, because the correct imputation is the base_rate from seasonal pricing, and that's only available after the join. So we hold the nulls through cleaning and impute in features.py post-join.

---

## SLIDE 7 — Live Demo: Running the Pipeline
**On screen:** Terminal — five commands

**Say:**
Let me actually run this.

[Run in terminal:]
```
python scripts/generate_sample_data.py
python -m src.ingest
python -m src.clean
python -m src.features
python -m src.load
```

[Point at ingest output:]
Look at what ingest is reporting — 199 rows loaded from bookings.csv, 9 null segments flagged, 2 duplicate reservation IDs found. It's not silently succeeding; it's giving us a full audit trail of what it found.

[Point at clean output:]
Clean dropped 1 exact duplicate, resolved the non-exact PK duplicate, dropped 11 rows where check-out was on or before check-in, and normalised all segment label variants. 199 raw rows became 186 clean rows. Every row that was dropped is accounted for.

[Point at features output:]
Features joined all three files, imputed the 4 null rates from base_rate, flagged 48 cancellations out of 186 total, and computed lead time and occupancy rate. 186 rows in, 186 rows out — no silent data loss.

[Point at load output:]
Load applied the schema, populated the segment dimension table, cleared and reloaded the fact table, and verified the row count matches. Six segment values, seven KPI views, all confirmed.

---

## SLIDE 8 — The Database Layer
**On screen:** schema.sql — dim_segment + fact_bookings_enriched + 5 indexes + 7 views

**Say:**
The database has two tables and seven views.

The fact table has one row per reservation. It contains everything needed for all eight metrics: booking dates, room nights, rate, cancellation data, lead time, season tag, and occupancy rate.

The five indexes cover the four most common filter patterns — segment, date, season, cancellation status, and the composite segment plus date which covers the most frequent dashboard query.

The views are where the metric logic lives. Each view maps directly to one or more of the eight SPEC metrics. They're thin SQL wrappers — no business logic that can't be read in a single SELECT.

One design decision worth highlighting: the denominator for occupancy rate is not in the SQL view. It stays in Python's config.py. If I put it in the SQL, then changing the capacity assumption means editing both Python and SQL. Keeping it in one place means one edit, and the SQL parametrises it at query time.

---

## SLIDE 9 — The 8 Metrics
**On screen:** Metrics table from SPEC Section 5

**Say:**
We're computing eight metrics. Let me explain the ones that aren't self-explanatory.

Occupancy Volatility, Metric 2, is the coefficient of variation — standard deviation divided by mean of the daily occupancy rate per segment. It's dimensionless, which means we can compare volatility across segments even if their absolute occupancy levels are different.

Seasonal Concentration Index, Metric 5 — this measures whether a segment's bookings are spread evenly across seasons or clustered. A value of 1.0 means perfectly even. Values above 1.0 mean more concentrated. Corporate scores 1.35, meaning its bookings are 35% more concentrated in its top two seasons than a flat distribution would be.

Segment Volatility Contribution, Metric 6 — this is the headline metric. It answers the core question directly. It's segment variance over total variance. It tells you what fraction of the hotel's total occupancy instability can be attributed to each segment.

Revenue Volatility Index, Metric 8 — same formula as CoV but applied to daily revenue instead of daily occupancy rate. This separates "volatile in bookings" from "volatile in revenue."

Three of these — Metrics 2, 6, and 8 — require standard deviation, which SQLite doesn't support natively. So we fetch the raw daily series from the SQL views and compute them in pandas.

---

## SLIDE 10 — Live Demo: The Dashboard
**On screen:** Dashboard at localhost:8501

**Say:**
Let me open the dashboard.

[Open http://localhost:8501]

The top section shows four KPI numbers — overall occupancy rate, total revenue at risk, the most volatile segment, and the highest cancellation rate.

The segment ranking table below it has all eight metrics in one row per segment, sorted by volatility contribution. This is the primary answer to the core question.

Corporate is at the top with 59.7% of total variance. That means if you could fix Corporate's behaviour, you'd eliminate more than half of the hotel's occupancy instability. Walk-in is second at 14.8%.

[Use the sidebar to filter to Corporate]

When I filter to just Corporate, every chart updates — the occupancy trend shows Corporate's specific pattern, the revenue chart shows its contribution, the cancellation rate shows 34.9%.

[Switch back to All Segments]

The daily occupancy chart shows five segment lines. Notice how Corporate has the widest swings — it has days with high occupancy and days where it drops sharply. Compare that to Direct, which is much flatter. That's the CoV difference showing up visually — Corporate is 3.48, Direct is 0.54.

The bottom three charts show the behavioural metrics — cancellation rate, average lead time, and seasonal concentration. These explain why Corporate is volatile: high cancellation rate, long lead time that gives more time to cancel, and seasonal clustering.

---

## SLIDE 11 — Key Findings
**On screen:** Corporate drives 59.7% of variance · Travel Agency has highest revenue at risk · Direct is the most stable channel

**Say:**
The findings, in plain language.

Corporate is the most volatile segment. It drives 59.7% of total occupancy variance despite being only 23% of bookings. The reason is a 34.9% cancellation rate combined with 35-day average lead time. Long lead-time bookings cancel more because business plans change. And when they cancel, they create large unpredictable gaps.

Travel Agency has the highest revenue at risk at $9,902. Not because it cancels most often — its cancellation rate of 33% is similar to Corporate — but because its room rates are higher. Each cancelled Travel Agency booking costs more.

Direct bookings are the most stable. CoV of 0.54, 15.6% cancellation rate, shortest lead time of 24 days. Short lead-time customers book close to their check-in date and almost always show up.

Walk-in volatility is different in nature from Corporate volatility. Walk-ins have a low cancellation rate — only 10.5% — but high CoV of 2.61. Their volatility comes from demand unpredictability, not cancellations. Some days you get many, some days none. That can't be fixed with cancellation policy.

---

## SLIDE 12 — Problems Faced
**On screen:** What broke, what we had to rethink, and what we learned

**Say:**
I want to be honest about the problems we ran into.

First: pandas 3.x API change. We were using infer_datetime_format equals True for date parsing. That parameter was silently removed in pandas 3.0. The first time we ran the cleaning pipeline on the real data, every single date column came back as NaT. The fix was to use format equals "mixed" — but that's not documented prominently and took time to find.

Second: the capacity column not existing. The schema contract in the spec listed total_rooms_available as a column. It wasn't there. This forced a design decision mid-project — do we fail the pipeline, do we estimate it from the data, or do we make the assumption explicit? We chose explicit, which is defensible. But it's an assumption that affects every occupancy rate calculation and needs to be called out.

Third: the team situation. Manuel left the project after Day 6. That meant absorbing Days 7 through 20 of planned work as a solo developer. It forced us to restructure the roadmap and absorb his scope into combined days. Every remaining day became a full-stack PR instead of a parallel half.

Fourth: a subtle join bug. When the seasonal pricing table had duplicate dates — which it did, we found them in profiling — a LEFT JOIN would silently multiply rows. The fact table would come out with more rows than the input bookings. We caught this because we added explicit row-count validation after every join step. Without that check, we'd have inflated metrics and never known why.

Fifth: SQLite has no STDDEV aggregate. We only discovered this when we tried to compute CoV and Revenue Volatility Index in SQL. The fallback — fetch the raw daily series and compute in pandas — actually turned out to be better, because it gave us more flexibility and we could independently verify the numbers in a notebook.

---

## SLIDE 13 — Technical Stack & Why
**On screen:** Python · pandas · SQLite · Streamlit · pytest · GitHub Actions

**Say:**
Every tool choice was deliberate and constrained by the spec.

Python for everything. No surprises there — pandas for cleaning and transformation, stdlib for ingestion.

SQLite for local dev, Postgres-portable schema. The schema uses standard SQL types — no SQLite-specific syntax. Any engineer can take the schema.sql file and run it on Postgres without changes.

Streamlit for the dashboard. Not plotly, not Dash, not a React frontend. Streamlit. The spec required it and it's the right tool for a diagnostic internal analytics tool.

pytest with 31 tests. Four categories — raw file schema checks, cleaning retention checks, fact table quality checks including null thresholds and PK uniqueness, and database round-trip checks including all seven views. CI runs them on every push.

GitHub Actions for CI. Free, integrated with GitHub, runs pytest automatically. The workflow triggers on changes to src, sql, or tests — not on data changes, because the CSVs are gitignored.

No dbt, no Airflow, no Django, no Flask. The spec explicitly forbids them and it's the right call — this is a small, direct pipeline. Adding orchestration or a web framework would be complexity without benefit.

---

## SLIDE 14 — Git & PR Discipline
**On screen:** 17 merged PRs · one per day · day-XX-akhil naming convention

**Say:**
One thing I want to highlight is the development discipline.

Every day's work is a separate branch named day-XX-akhil, opened as a PR into main, and merged with a clear commit message describing what was built. You can go to the GitHub repo and look at the PR history and see exactly what was built on each day, in what order, with what rationale.

This matters for two reasons. One, it makes individual contribution completely visible — there's no ambiguity about who built what and when. Two, it forces you to be deliberate about scope. If the day's done-when criteria aren't met, you don't merge. You carry it forward. That discipline kept the project clean.

The branch naming sorts chronologically in GitHub's interface, which means the build history is immediately readable without any additional documentation.

---

## SLIDE 15 — What Would Be Different With Real Data
**On screen:** This was built with sample data. Here's what changes when you plug in real CSVs.

**Say:**
The pipeline was built and tested with generated sample data — 199 bookings, 50 cancellations, a year of pricing data. The data has realistic quality issues planted intentionally: mixed date formats, duplicate rows, segment variants.

When you plug in real hotel data, nothing in the pipeline changes except the data files. Drop the real CSVs in data/raw and run the five commands. The pipeline will process them, the DB will be populated, and the dashboard will show real numbers.

Two things you'd need to update: the ASSUMED_TOTAL_ROOMS constant in config.py, once you know the real hotel capacity. And the NULL_THRESHOLD values in the test file, once you know what null percentages are acceptable for the specific dataset.

Everything else — the schema, the metrics, the SQL views, the dashboard — is production-ready as built.

---

## SLIDE 16 — Closing
**On screen:** github.com/akhilk49/Occupancy-Volatility-Index

**Say:**
To summarise.

We started with three messy CSVs and a business question. We built a documented pipeline that cleans the data with explicit, justified decisions, joins it into a single fact table, loads it into SQLite, computes eight metrics, and surfaces them in an interactive dashboard.

The headline answer is that Corporate drives 59.7% of occupancy variance, primarily due to a 34.9% cancellation rate and long booking lead times. Travel Agency has the highest revenue at risk. Direct bookings are the most stable and should be incentivised.

The repo is public. Everything is there — the spec, the PRD, the pipeline, the tests, the notebook cross-checks, the findings summary, and these speaker notes.

Happy to take questions.

---

## ANTICIPATED QUESTIONS & ANSWERS

**Q: Why not use a proper database like PostgreSQL from the start?**
A: The spec required SQLite for local dev, but the schema is Postgres-portable. There's no AUTOINCREMENT, no SQLite-specific syntax, no pragma statements. You can take schema.sql and run it on Postgres without editing a line. For a project of this scale — under 100k rows — SQLite is entirely appropriate and zero-setup.

**Q: How do you know your metrics are correct?**
A: Two ways. First, every metric was independently computed in pandas in notebook 04 using the raw CSV, then cross-checked against the SQL query layer. The maximum CoV difference was less than 0.001 — floating point rounding only. Second, the 31 CI tests include schema drift checks, null threshold checks, and PK uniqueness checks, so if the pipeline produces bad data, the tests catch it before anything reaches the dashboard.

**Q: What happens if a new segment type appears in the data?**
A: The segment normalisation map in clean.py logs a WARNING for any unmapped value and leaves it as-is. It doesn't fail silently. The unmapped value stays in the fact table and is visible in the dashboard — it won't be bucketed into a wrong segment. The fix is to add the new variant to the SEGMENT_CANONICAL_MAP dictionary in one place.

**Q: Why is the capacity hardcoded at 100 rooms?**
A: Because total_rooms_available was absent from the raw data — that's confirmed in the Day 1 profiling notes. We had three options: fail the pipeline, estimate from the data, or make the assumption explicit. We chose explicit. The constant is named ASSUMED_TOTAL_ROOMS and sits in config.py with a comment explaining why it exists. Any occupancy rate calculation that uses it can be corrected by changing one number. The alternative — silently using a derived estimate — would be harder to audit and harder to correct.

**Q: Could this be extended to forecasting?**
A: Deliberately not. The spec explicitly rules out predictive models. This project is diagnostic — it explains what happened. Forecasting would require different data (more history, external factors like events and holidays), different models, and a different evaluation framework. Building a diagnostic tool correctly is a prerequisite for building a forecasting tool on top of it.

**Q: What was the hardest part technically?**
A: Honestly, the pandas API change was the most frustrating — a silent removal of a parameter that caused every date to parse as NaT. But architecturally, the trickiest decision was handling the capacity assumption. We knew from Day 1 that total_rooms_available was missing. Every subsequent metric — occupancy rate, CoV, volatility contribution — depends on that denominator. Getting the design right for that constraint, with a single config constant that propagates everywhere, took deliberate thought.

**Q: How long did the project take?**
A: 17 working days. Days 1–6 were split with a second team member who then left the project. From Day 7 onwards it was solo. The spec had a 20-day timeline split between two people — absorbing the second person's scope into the remaining 11 days meant rescheduling the roadmap and front-loading some work that was originally planned for later weeks.
