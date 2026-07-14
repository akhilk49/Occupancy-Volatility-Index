# Occupancy Volatility Index

**Team:** Akhil K Kurian, Manuel Beracah  
**Sprint:** 4 weeks / 20 working days  
**Core Question:** Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors explain it?

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Place raw CSVs in data/raw/
#    bookings.csv | cancellations.csv | seasonal_pricing.csv

# 3. Run the pipeline (available from Day 6+)
python -m src.ingest
python -m src.clean
python -m src.features
python -m src.load

# 4. Launch the dashboard (available from Day 16+)
streamlit run app/dashboard.py
```

## Repository Structure

```
Occupancy-Volatility-Index/
├── data/
│   ├── raw/           # original CSVs — gitignored, add manually
│   ├── interim/       # cleaned files, before feature engineering
│   └── processed/     # fact table + occupancy.db
├── src/               # pipeline modules
├── sql/               # schema + KPI queries
├── app/               # Streamlit dashboard
├── tests/             # pytest data quality checks
├── notebooks/         # EDA exploration only
└── .github/workflows/ # CI
```

## Team Charter

<!-- Manuel fills in on Day 1 -->

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| Day 1 | Repo scaffold committed under day-01-akhil | Joint task per SPEC Section 7 |
