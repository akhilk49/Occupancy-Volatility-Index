# Day 3: Volatility Metrics & Dashboard Wireframe (Manuel)

## 1. Volatility Metric Definitions (Draft)
Based on SPEC.md Section 5, here are the exact mathematical definitions required for the Streamlit dashboard. These definitions will guide our SQL query structure and pandas feature engineering:

1. **Occupancy Rate:** `booked_room_nights / available_room_nights` (calculated per day)
2. **Occupancy Volatility (CoV):** `stddev(occupancy_rate) / mean(occupancy_rate)` (calculated over a rolling window, per segment)
3. **Cancellation Rate:** `cancelled_bookings / total_bookings` (calculated per segment)
4. **Avg Lead Time:** `mean(check_in_date - booking_date)` (calculated per segment)
5. **Seasonal Concentration Index:** Share of a segment's bookings falling in its top-2 seasons vs. an even spread
6. **Segment Volatility Contribution (Headline Metric):** `segment_variance / total_variance`
7. **Revenue at Risk:** `SUM(room_nights * rate)` where `is_cancelled = TRUE` (calculated per segment)
8. **Revenue Volatility Index:** `stddev(daily_room_revenue) / mean(daily_room_revenue)` (calculated per segment)

## 2. Dashboard Wireframe & User Flow

### General Layout
The Streamlit app will feature a top-level sidebar for global filters and a main content area structured to guide the user from high-level impact down to specific trends.

### Sidebar (Global Filters)
- **Date Range Picker:** Select the time window for the analysis.
- **Season Filter:** Multi-select dropdown to filter by `season_tag`.
- **Segment Filter:** Multi-select dropdown to drill down into specific booking channels.

### Main Content Area

#### Section A: Executive Summary (KPI Cards)
Displayed prominently at the top to give immediate context:
- Overall Occupancy Rate
- Total Revenue at Risk
- Most Volatile Segment (Displays the segment with the highest Volatility Contribution)

#### Section B: Segment Volatility Ranking
- **Visual:** Bar Chart or Data Table ranking segments by **Metric #6 (Segment Volatility Contribution)**.
- **Context Columns:** Cancellation Rate, Avg Lead Time, and Revenue at Risk.
- **Purpose:** Directly answers the core business question: "Which customer segments contribute most to occupancy volatility?"

#### Section C: Volatility Trends & Behavior
- **Time-Series Chart:** Shows Occupancy Volatility (CoV) over the selected rolling window.
- **Interaction:** Allows the user to select specific segments to overlay and compare their volatility trends over time.
- **Revenue Impact View:** Correlates the Revenue Volatility Index with Occupancy Volatility to show financial impact.
