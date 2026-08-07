# Findings Summary — Occupancy Volatility Index

**Project:** Occupancy Volatility & Segment Insights Dashboard  
**Author:** Akhil K Kurian  
**Data:** Sample dataset (199 raw bookings → 186 clean → loaded into occupancy.db)  
**Core Question:** Which customer segments contribute most to occupancy volatility, and what booking/cancellation behaviors explain it?

---

## 1. Headline Answer

**Corporate is the most volatile segment**, contributing **59.7% of total occupancy variance** despite representing only 23% of bookings. Walk-in and Group are the next most volatile segments.

**Travel Agency has the highest revenue at risk** ($9,902) despite a moderate cancellation rate — because its average booking rate is higher, each cancelled reservation costs more.

---

## 2. Segment-by-Segment Analysis

| Segment | Bookings | Cancel Rate | Avg Lead (days) | Rev at Risk | CoV | Volatility Contrib |
|---------|----------|-------------|----------------|-------------|-----|-------------------|
| **Corporate** | 43 | **34.9%** | 35 | $8,396 | **3.48** | **59.7%** |
| Walk-in | 38 | 10.5% | 32 | $5,277 | 2.61 | 14.8% |
| Group | 35 | 34.3% | 34 | $5,020 | 2.23 | 5.2% |
| Direct | 32 | 15.6% | **24** | $1,796 | 0.54 | 0.2% |
| Travel Agency | 30 | 33.3% | 30 | **$9,902** | 0.60 | 0.2% |
| Unknown | 8 | 25.0% | 30 | $1,081 | 1.91 | 19.9% |

---

## 3. What Explains Corporate's High Volatility?

**High cancellation rate (34.9%):** Nearly 1 in 3 Corporate bookings cancels. This creates unpredictable gaps in occupancy — some days are heavily occupied, others drop sharply when batch cancellations occur.

**Moderate-to-long lead time (35 days):** Corporate bookings are made 5 weeks ahead on average. Long lead-time bookings are more likely to be cancelled when business plans change, amplifying the occupancy swings.

**Seasonal concentration (index 1.35):** Corporate bookings cluster in Spring and Winter, creating peaks and troughs rather than a steady year-round pattern. This seasonal bunching further drives CoV upward.

---

## 4. Why Travel Agency Has the Highest Revenue at Risk

Travel Agency has a 33.3% cancellation rate — similar to Corporate — but its rate per booking is higher on average. The combination of high rate × high room_nights per cancelled booking produces the largest revenue loss. This segment warrants specific attention for cancellation policy tightening or deposit requirements.

---

## 5. Walk-in vs Direct: The Stability Contrast

- **Direct** has the lowest CoV (0.54) and lowest average lead time (24 days). Short-notice, direct bookings create surprisingly stable occupancy — customers book and show up.
- **Walk-in** has a high CoV (2.61) but only 10.5% cancellation rate. Walk-in volatility comes from *demand unpredictability* rather than cancellations — some days bring many walk-ins, others none.

---

## 6. Seasonal Patterns

All segments are more concentrated than an even seasonal spread (all indices > 1.0):
- **Corporate (1.35):** Concentrated in Spring + Winter — business travel season.
- **Travel Agency (1.33):** Spring + Summer peak — leisure/holiday travel patterns.
- **Walk-in (1.21):** Autumn + Winter — possibly local/regional travel in slower seasons.

---

## 7. Recommendations for the Revenue Team

1. **Corporate:** Implement non-refundable rate tiers or deposit requirements for bookings > 30 days out. Even reducing Corporate cancellations by 10% would materially reduce overall occupancy variance.

2. **Travel Agency:** Review commission structures — high revenue at risk suggests cancellations are disproportionately costly. Consider tighter cancellation windows.

3. **Walk-in:** Cannot be controlled through policy. Build buffer capacity forecasting specifically for high-demand walk-in seasons (Autumn/Winter).

4. **Direct:** This segment is already well-behaved. Incentivise direct bookings (loyalty rates, direct-only promotions) to grow its share and improve overall stability.

---

## 8. Metric Cross-Check (pandas vs SQL)

All 8 metrics were independently computed in `notebooks/04_eda_occupancy_trends.ipynb` using pandas on the raw fact table CSV and cross-checked against the SQL query layer (`src/queries.py` → `occupancy.db`). Maximum CoV discrepancy between pandas and SQL: < 0.001 (floating point rounding only).

---

*Generated from sample data for demonstration. Replace `data/raw/` CSVs with real hotel data and re-run the pipeline to get production findings.*
