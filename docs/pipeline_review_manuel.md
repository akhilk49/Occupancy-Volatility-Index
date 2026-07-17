# Day 4: Pipeline Design Review (Manuel)

## Overview
I have reviewed the pipeline architecture and proposed data flow, specifically checking if the schema will support all Streamlit dashboard requirements and the volatility metrics defined on Day 3.

## Identified Gaps & Review Comments

1. **Date Granularity for Metrics:**
   - *Issue:* Metric #8 (Revenue Volatility Index) requires `daily_room_revenue`. The pipeline output (`fact_bookings_enriched`) is defined at the **reservation grain**, not the **room-night grain**. 
   - *Action Required:* We either need the SQL layer (`kpi_queries.sql`) to dynamically explode bookings into daily rows, or the Python pipeline (`features.py`) needs to output an exploded table so we can accurately sum revenue by day.

2. **Total Rooms Available Missing:**
   - *Issue:* During Day 1 profiling, we noted that `total_rooms_available` does not actually exist in the raw `bookings.csv`.
   - *Action Required:* The pipeline needs an explicit assumption or a hardcoded mapping (e.g., in `config.py`) for total capacity. Otherwise, Occupancy Rate (Metric #1) will fail to calculate.

3. **Season Tag Join Logic:**
   - *Issue:* The spec says `bookings JOIN seasonal_pricing ON check_in_date = date`. However, many bookings will span multiple seasons.
   - *Action Required:* Ensure the join logic safely handles bookings that span season boundaries, or document in the PRD that we classify the entire booking's season based strictly on its `check_in_date`.

## Conclusion
The overall data flow from raw CSVs to SQLite is solid. However, we must resolve the **daily explosion logic** and **capacity assumption** before implementing `features.py` in Week 2.
