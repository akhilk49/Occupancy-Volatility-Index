"""dashboard.py — Streamlit entry point for the Occupancy Volatility Index dashboard.

Sections:
  Sidebar  — global filters (date range, season, segment)
  Section A — KPI cards (occupancy rate, revenue at risk, most volatile segment)
  Section B — Segment ranking table (all 8 metrics, sortable)
  Section C — Volatility trend chart (CoV over time, Metric #2)
  Section D — Revenue at Risk bar chart (Metric #7)

Run with:
    streamlit run app/dashboard.py

Requires occupancy.db to exist:
    python scripts/generate_sample_data.py
    python -m src.ingest && python -m src.clean && python -m src.features && python -m src.load
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make src/ importable when run from repo root or app/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ASSUMED_TOTAL_ROOMS, CANONICAL_SEGMENTS, DB_PATH
from src.queries import (
    get_avg_lead_time_by_segment,
    get_cancellation_rate_by_segment,
    get_occupancy_by_segment_day,
    get_occupancy_volatility_cov,
    get_revenue_at_risk,
    get_revenue_volatility_index,
    get_seasonal_concentration,
    get_segment_summary,
    get_segment_volatility_contribution,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Occupancy Volatility Index",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# DB availability check
# ---------------------------------------------------------------------------
if not DB_PATH.exists():
    st.error(
        f"**Database not found:** `{DB_PATH}`\n\n"
        "Run the pipeline first:\n"
        "```\n"
        "python scripts/generate_sample_data.py\n"
        "python -m src.ingest\n"
        "python -m src.clean\n"
        "python -m src.features\n"
        "python -m src.load\n"
        "```"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — Global Filters
# ---------------------------------------------------------------------------
st.sidebar.title("🔍 Filters")
st.sidebar.caption(f"Capacity assumption: **{ASSUMED_TOTAL_ROOMS} rooms** (config.py)")

# Date range
st.sidebar.subheader("Date Range")
col_s, col_e = st.sidebar.columns(2)
start_date = col_s.date_input("From", value=pd.Timestamp("2023-01-01"))
end_date   = col_e.date_input("To",   value=pd.Timestamp("2023-12-31"))
start_str = str(start_date)
end_str   = str(end_date)

# Segment filter
st.sidebar.subheader("Segment")
all_segments_option = "All Segments"
segment_options = [all_segments_option] + CANONICAL_SEGMENTS + ["Unknown"]
selected_segment = st.sidebar.selectbox("Booking Channel", segment_options)
seg_filter: str | None = None if selected_segment == all_segments_option else selected_segment

st.sidebar.divider()
st.sidebar.caption(
    "**Core question:** Which customer segments contribute most to occupancy volatility, "
    "and what behaviors explain it?"
)

# ---------------------------------------------------------------------------
# Data loading (cached so filters don't re-query on every widget interaction)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_summary(start: str, end: str) -> pd.DataFrame:
    return get_segment_summary(DB_PATH, start_date=start, end_date=end)


@st.cache_data(ttl=60)
def load_daily_occupancy(seg: str | None, start: str, end: str) -> pd.DataFrame:
    return get_occupancy_by_segment_day(DB_PATH, segment=seg, start_date=start, end_date=end)


@st.cache_data(ttl=60)
def load_revenue_at_risk(seg: str | None) -> pd.DataFrame:
    return get_revenue_at_risk(DB_PATH, segment=seg)


summary_df  = load_summary(start_str, end_str)
daily_df    = load_daily_occupancy(seg_filter, start_str, end_str)
rar_df      = load_revenue_at_risk(seg_filter)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏨 Occupancy Volatility & Segment Insights")
st.caption(
    "Which customer segments contribute most to occupancy volatility, "
    "and what booking/cancellation behaviors explain it?"
)
st.divider()

# ---------------------------------------------------------------------------
# Section A — KPI Cards
# ---------------------------------------------------------------------------
st.subheader("📊 Executive Summary")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

# Overall occupancy rate (mean across all active days)
if not daily_df.empty:
    mean_occ = daily_df["occupancy_rate"].mean()
    kpi1.metric(
        "Overall Occupancy Rate",
        f"{mean_occ:.1%}",
        help=f"Mean daily occupancy rate. Capacity = {ASSUMED_TOTAL_ROOMS} rooms (assumed).",
    )
else:
    kpi1.metric("Overall Occupancy Rate", "—")

# Total revenue at risk
total_rar = rar_df["revenue_at_risk"].sum() if not rar_df.empty else 0
kpi2.metric(
    "Total Revenue at Risk",
    f"${total_rar:,.0f}",
    help="Sum of (room_nights * rate) for all cancelled bookings in the selected period.",
)

# Most volatile segment (highest volatility contribution)
if not summary_df.empty and "volatility_contribution" in summary_df.columns:
    top_seg = summary_df.dropna(subset=["volatility_contribution"])
    if not top_seg.empty:
        top_row = top_seg.iloc[0]
        kpi3.metric(
            "Most Volatile Segment",
            top_row["segment_name"],
            help=f"Segment with highest volatility contribution (Metric #6). "
                 f"Contributes {top_row['volatility_contribution']:.1%} of total occupancy variance.",
        )
    else:
        kpi3.metric("Most Volatile Segment", "—")
else:
    kpi3.metric("Most Volatile Segment", "—")

# Highest cancellation rate segment
if not summary_df.empty and "cancellation_rate" in summary_df.columns:
    top_cancel = summary_df.dropna(subset=["cancellation_rate"]).sort_values(
        "cancellation_rate", ascending=False
    )
    if not top_cancel.empty:
        tc = top_cancel.iloc[0]
        kpi4.metric(
            "Highest Cancellation Rate",
            f"{tc['cancellation_rate']:.1%}",
            delta=tc["segment_name"],
            delta_color="off",
            help="Segment with the highest cancellation rate (Metric #3).",
        )
    else:
        kpi4.metric("Highest Cancellation Rate", "—")
else:
    kpi4.metric("Highest Cancellation Rate", "—")

st.divider()

# ---------------------------------------------------------------------------
# Section B — Segment Ranking Table
# ---------------------------------------------------------------------------
st.subheader("📋 Segment Ranking — All Metrics")
st.caption(
    "Sorted by **Volatility Contribution** (Metric #6 — headline metric). "
    "Higher = this segment explains more of total occupancy variance."
)

if summary_df.empty:
    st.warning("No data for the selected filters.")
else:
    # Format for display
    display_df = summary_df.copy()

    col_rename = {
        "segment_name":                "Segment",
        "total_bookings":              "Bookings",
        "total_room_nights":           "Room Nights",
        "cancellation_rate":           "Cancel Rate",
        "avg_lead_time_days":          "Avg Lead (days)",
        "revenue_at_risk":             "Revenue at Risk ($)",
        "cov":                         "Occ. Volatility (CoV)",
        "volatility_contribution":     "Volatility Contribution",
        "rvi":                         "Revenue Volatility (RVI)",
        "seasonal_concentration_index":"Seasonal Concentration",
    }
    display_df = display_df.rename(columns={k: v for k, v in col_rename.items() if k in display_df.columns})

    # Format percentages and currency
    if "Cancel Rate" in display_df.columns:
        display_df["Cancel Rate"] = display_df["Cancel Rate"].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "—"
        )
    if "Volatility Contribution" in display_df.columns:
        display_df["Volatility Contribution"] = display_df["Volatility Contribution"].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "—"
        )
    if "Revenue at Risk ($)" in display_df.columns:
        display_df["Revenue at Risk ($)"] = display_df["Revenue at Risk ($)"].apply(
            lambda x: f"${x:,.2f}" if pd.notna(x) else "—"
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Section C — Occupancy Volatility Trend (CoV time series)
# ---------------------------------------------------------------------------
st.subheader("📈 Daily Occupancy Rate by Segment")
st.caption(
    "Non-cancelled bookings only. "
    f"Denominator = {ASSUMED_TOTAL_ROOMS} rooms (ASSUMED_TOTAL_ROOMS in config.py)."
)

if daily_df.empty:
    st.info("No occupancy data for the selected filters.")
else:
    pivot = (
        daily_df.pivot_table(
            index="date", columns="segment_name", values="occupancy_rate", aggfunc="mean"
        )
        .fillna(0)
    )
    # Filter to selected segment if one is chosen
    if seg_filter and seg_filter in pivot.columns:
        pivot = pivot[[seg_filter]]

    st.line_chart(pivot, use_container_width=True)

    # CoV summary below the chart
    cov_df = get_occupancy_volatility_cov(DB_PATH, segment=seg_filter, start_date=start_str, end_date=end_str)
    if not cov_df.empty:
        st.caption("**Coefficient of Variation (CoV)** — stddev / mean of daily occupancy rate per segment:")
        cov_cols = st.columns(min(len(cov_df), 5))
        for i, row in cov_df.iterrows():
            cov_cols[i % len(cov_cols)].metric(
                row["segment_name"],
                f"{row['cov']:.3f}",
                help="Higher CoV = more volatile occupancy",
            )

st.divider()

# ---------------------------------------------------------------------------
# Section D — Revenue at Risk
# ---------------------------------------------------------------------------
st.subheader("💸 Revenue at Risk by Segment (Metric #7)")
st.caption("Total revenue lost to cancellations = SUM(room_nights * rate) where is_cancelled = TRUE.")

if rar_df.empty:
    st.info("No cancellation revenue data for the selected filters.")
else:
    rar_chart = rar_df.set_index("segment_name")["revenue_at_risk"]
    st.bar_chart(rar_chart, use_container_width=True)

    total = rar_df["revenue_at_risk"].sum()
    st.caption(f"**Total revenue at risk: ${total:,.2f}**")

st.divider()
st.caption(
    "Data source: `data/processed/occupancy.db` · "
    "Pipeline: ingest → clean → features → load · "
    "Repo: github.com/akhilk49/Occupancy-Volatility-Index"
)
