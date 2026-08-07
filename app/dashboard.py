"""dashboard.py — Streamlit dashboard for the Occupancy Volatility Index.

All 8 metrics from SPEC Section 5 are visible and filterable.

Sections:
  Sidebar  — date range, season, segment filters
  A — KPI cards (occupancy rate, revenue at risk, most volatile segment, cancel rate)
  B — Segment ranking table (all 8 metrics)
  C — Daily occupancy trend + CoV cards (Metrics #1, #2)
  D — Volatility contribution bar chart (Metric #6 — headline)
  E — Revenue at Risk bar chart (Metric #7)
  F — Revenue Volatility Index (Metric #8)
  G — Seasonal Concentration (Metric #5)
  H — Lead Time distribution (Metric #4)
  I — Cancellation Rate (Metric #3)

Run with:
    streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

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

# Custom CSS — subtle improvements without adding dependencies
st.markdown("""
<style>
    .metric-label { font-size: 0.85rem !important; }
    .block-container { padding-top: 1.5rem; }
    h2 { margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB check
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
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.title("🔍 Filters")
st.sidebar.caption(f"Capacity: **{ASSUMED_TOTAL_ROOMS} rooms** (ASSUMED_TOTAL_ROOMS)")

st.sidebar.subheader("Date Range")
c1, c2 = st.sidebar.columns(2)
start_date = c1.date_input("From", value=pd.Timestamp("2023-01-01"))
end_date   = c2.date_input("To",   value=pd.Timestamp("2023-12-31"))
start_str, end_str = str(start_date), str(end_date)

st.sidebar.subheader("Segment")
seg_options = ["All Segments"] + CANONICAL_SEGMENTS + ["Unknown"]
selected_seg = st.sidebar.selectbox("Booking Channel", seg_options)
seg_filter: str | None = None if selected_seg == "All Segments" else selected_seg

st.sidebar.divider()
st.sidebar.info(
    "**Core question:**\n\n"
    "Which customer segments contribute most to occupancy volatility, "
    "and what behaviors explain it?"
)
st.sidebar.caption("Repo: github.com/akhilk49/Occupancy-Volatility-Index")

# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _summary(start: str, end: str) -> pd.DataFrame:
    return get_segment_summary(DB_PATH, start_date=start, end_date=end)

@st.cache_data(ttl=60)
def _daily_occ(seg: str | None, start: str, end: str) -> pd.DataFrame:
    return get_occupancy_by_segment_day(DB_PATH, segment=seg, start_date=start, end_date=end)

@st.cache_data(ttl=60)
def _cov(seg: str | None, start: str, end: str) -> pd.DataFrame:
    return get_occupancy_volatility_cov(DB_PATH, segment=seg, start_date=start, end_date=end)

@st.cache_data(ttl=60)
def _contrib(start: str, end: str) -> pd.DataFrame:
    return get_segment_volatility_contribution(DB_PATH, start_date=start, end_date=end)

@st.cache_data(ttl=60)
def _rar(seg: str | None) -> pd.DataFrame:
    return get_revenue_at_risk(DB_PATH, segment=seg)

@st.cache_data(ttl=60)
def _rvi(seg: str | None, start: str, end: str) -> pd.DataFrame:
    return get_revenue_volatility_index(DB_PATH, segment=seg, start_date=start, end_date=end)

@st.cache_data(ttl=60)
def _seasonal(seg: str | None) -> pd.DataFrame:
    return get_seasonal_concentration(DB_PATH, segment=seg)

@st.cache_data(ttl=60)
def _lead(seg: str | None) -> pd.DataFrame:
    return get_avg_lead_time_by_segment(DB_PATH, segment=seg)

@st.cache_data(ttl=60)
def _cancel(seg: str | None) -> pd.DataFrame:
    return get_cancellation_rate_by_segment(DB_PATH, segment=seg)


summary_df = _summary(start_str, end_str)
daily_df   = _daily_occ(seg_filter, start_str, end_str)
cov_df     = _cov(seg_filter, start_str, end_str)
contrib_df = _contrib(start_str, end_str)
rar_df     = _rar(seg_filter)
rvi_df     = _rvi(seg_filter, start_str, end_str)
seasonal_df = _seasonal(seg_filter)
lead_df    = _lead(seg_filter)
cancel_df  = _cancel(seg_filter)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏨 Occupancy Volatility & Segment Insights")
st.caption(
    "Which customer segments contribute most to occupancy volatility, "
    "and what booking/cancellation behaviors explain it?"
)
st.divider()

# ===========================================================================
# A — KPI Cards
# ===========================================================================
st.subheader("A  Executive Summary")

k1, k2, k3, k4 = st.columns(4)

mean_occ = daily_df["occupancy_rate"].mean() if not daily_df.empty else None
k1.metric(
    "Avg Occupancy Rate",
    f"{mean_occ:.1%}" if mean_occ is not None else "—",
    help=f"Mean daily occupancy rate across filtered period. Capacity = {ASSUMED_TOTAL_ROOMS} rooms.",
)

total_rar = rar_df["revenue_at_risk"].sum() if not rar_df.empty else 0
k2.metric(
    "Revenue at Risk",
    f"${total_rar:,.0f}",
    help="SUM(room_nights * rate) for all cancelled bookings (Metric #7).",
)

if not summary_df.empty and "volatility_contribution" in summary_df.columns:
    top = summary_df.dropna(subset=["volatility_contribution"])
    if not top.empty:
        r = top.iloc[0]
        k3.metric(
            "Most Volatile Segment",
            r["segment_name"],
            delta=f"{r['volatility_contribution']:.1%} of variance",
            delta_color="off",
            help="Segment with highest Segment Volatility Contribution (Metric #6).",
        )
    else:
        k3.metric("Most Volatile Segment", "—")
else:
    k3.metric("Most Volatile Segment", "—")

if not summary_df.empty and "cancellation_rate" in summary_df.columns:
    tc = summary_df.dropna(subset=["cancellation_rate"]).sort_values(
        "cancellation_rate", ascending=False
    )
    if not tc.empty:
        row = tc.iloc[0]
        k4.metric(
            "Highest Cancel Rate",
            f"{row['cancellation_rate']:.1%}",
            delta=row["segment_name"],
            delta_color="off",
            help="Segment with the highest cancellation rate (Metric #3).",
        )
    else:
        k4.metric("Highest Cancel Rate", "—")
else:
    k4.metric("Highest Cancel Rate", "—")

st.divider()

# ===========================================================================
# B — Segment Ranking Table (all 8 metrics)
# ===========================================================================
st.subheader("B  Segment Ranking — All 8 Metrics")
st.caption(
    "Sorted by **Volatility Contribution** (Metric #6 — headline). "
    "Each column maps to one of the 8 metrics in SPEC Section 5."
)

if summary_df.empty:
    st.warning("No data for the selected filters.")
else:
    disp = summary_df.copy()
    disp = disp.rename(columns={
        "segment_name":                "Segment",
        "total_bookings":              "Bookings (#3 base)",
        "total_room_nights":           "Room Nights",
        "cancellation_rate":           "Cancel Rate (M3)",
        "avg_lead_time_days":          "Avg Lead Days (M4)",
        "revenue_at_risk":             "Rev at Risk $ (M7)",
        "cov":                         "Occ CoV (M2)",
        "volatility_contribution":     "Volatility Contrib (M6)",
        "rvi":                         "Rev Volatility (M8)",
        "seasonal_concentration_index":"Seasonal Conc (M5)",
    })
    for pct_col in ["Cancel Rate (M3)", "Volatility Contrib (M6)"]:
        if pct_col in disp.columns:
            disp[pct_col] = disp[pct_col].apply(
                lambda x: f"{x:.1%}" if pd.notna(x) else "—"
            )
    if "Rev at Risk $ (M7)" in disp.columns:
        disp["Rev at Risk $ (M7)"] = disp["Rev at Risk $ (M7)"].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
        )
    for num_col in ["Occ CoV (M2)", "Rev Volatility (M8)", "Seasonal Conc (M5)", "Avg Lead Days (M4)"]:
        if num_col in disp.columns:
            disp[num_col] = disp[num_col].apply(
                lambda x: f"{x:.3f}" if pd.notna(x) else "—"
            )
    st.dataframe(disp, use_container_width=True, hide_index=True)

st.divider()

# ===========================================================================
# C — Daily Occupancy Rate + CoV (Metrics #1, #2)
# ===========================================================================
st.subheader("C  Daily Occupancy Rate by Segment  (Metrics #1 & #2)")
st.caption(
    "Non-cancelled bookings only. "
    f"Denominator = {ASSUMED_TOTAL_ROOMS} rooms. "
    "CoV cards below = stddev / mean (higher = more volatile)."
)

if daily_df.empty:
    st.info("No occupancy data for the selected filters.")
else:
    pivot = (
        daily_df.pivot_table(index="date", columns="segment_name",
                              values="occupancy_rate", aggfunc="mean")
        .fillna(0)
    )
    if seg_filter and seg_filter in pivot.columns:
        pivot = pivot[[seg_filter]]
    st.line_chart(pivot, use_container_width=True)

    if not cov_df.empty:
        st.caption("**Coefficient of Variation (CoV) — Metric #2:**")
        cols = st.columns(min(len(cov_df), 6))
        for i, row in cov_df.reset_index(drop=True).iterrows():
            cols[i % len(cols)].metric(
                row["segment_name"], f"{row['cov']:.3f}",
                help="Higher CoV = more volatile daily occupancy"
            )

st.divider()

# ===========================================================================
# D — Volatility Contribution (Metric #6)
# ===========================================================================
st.subheader("D  Segment Volatility Contribution  (Metric #6 — Headline)")
st.caption(
    "segment_variance(occupancy_rate) / total_variance. "
    "This is the primary answer to the core business question."
)

if contrib_df.empty:
    st.info("No contribution data available.")
else:
    chart_data = contrib_df.set_index("segment_name")["volatility_contribution"]
    st.bar_chart(chart_data, use_container_width=True)

    cols = st.columns(min(len(contrib_df), 6))
    for i, row in contrib_df.reset_index(drop=True).iterrows():
        cols[i % len(cols)].metric(
            row["segment_name"],
            f"{row['volatility_contribution']:.1%}",
            help=f"Variance: {row['variance']:.6f}",
        )

st.divider()

# ===========================================================================
# E — Revenue at Risk (Metric #7)
# ===========================================================================
st.subheader("E  Revenue at Risk by Segment  (Metric #7)")
st.caption("SUM(room_nights * rate) where is_cancelled = TRUE. Revenue the hotel lost to cancellations.")

if rar_df.empty:
    st.info("No cancellation data for the selected filters.")
else:
    st.bar_chart(rar_df.set_index("segment_name")["revenue_at_risk"], use_container_width=True)
    total = rar_df["revenue_at_risk"].sum()
    st.caption(f"**Total revenue at risk: ${total:,.2f}**")

st.divider()

# ===========================================================================
# F — Revenue Volatility Index (Metric #8)
# ===========================================================================
st.subheader("F  Revenue Volatility Index  (Metric #8)")
st.caption(
    "RVI = stddev(daily_room_revenue) / mean(daily_room_revenue) per segment. "
    "High RVI = erratic daily revenue even if total is high."
)

if rvi_df.empty:
    st.info("No revenue data for the selected filters.")
else:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.bar_chart(rvi_df.set_index("segment_name")["rvi"], use_container_width=True)
    with col_r:
        st.dataframe(
            rvi_df.rename(columns={
                "segment_name": "Segment",
                "mean_daily_revenue": "Mean Daily Rev ($)",
                "rvi": "RVI"
            }),
            use_container_width=True, hide_index=True,
        )

st.divider()

# ===========================================================================
# G — Seasonal Concentration (Metric #5)
# ===========================================================================
st.subheader("G  Seasonal Concentration Index  (Metric #5)")
st.caption(
    "Index = (share of bookings in top-2 seasons) / (1/N_seasons even baseline). "
    "> 1.0 means more concentrated than a flat even spread across seasons."
)

if seasonal_df.empty:
    st.info("No seasonal data available.")
else:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        sci_chart = seasonal_df.set_index("segment_name")["seasonal_concentration_index"]
        st.bar_chart(sci_chart, use_container_width=True)
        # Reference line annotation
        st.caption("Reference: 1.0 = perfectly even seasonal spread")
    with col_r:
        st.dataframe(
            seasonal_df[["segment_name", "top2_share", "seasonal_concentration_index"]].rename(
                columns={
                    "segment_name": "Segment",
                    "top2_share": "Top-2 Season Share",
                    "seasonal_concentration_index": "Conc. Index",
                }
            ).assign(**{
                "Top-2 Season Share": lambda d: d["Top-2 Season Share"].apply(lambda x: f"{x:.1%}"),
            }),
            use_container_width=True, hide_index=True,
        )

st.divider()

# ===========================================================================
# H — Lead Time Distribution (Metric #4)
# ===========================================================================
st.subheader("H  Average Lead Time by Segment  (Metric #4)")
st.caption(
    "mean(check_in_date - booking_date) in days. "
    "Longer lead time = more advance planning = potentially more stable occupancy."
)

if lead_df.empty:
    st.info("No lead time data available.")
else:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.bar_chart(
            lead_df.set_index("segment_name")["avg_lead_time_days"],
            use_container_width=True,
        )
    with col_r:
        st.dataframe(
            lead_df.rename(columns={
                "segment_name": "Segment",
                "avg_lead_time_days": "Avg Lead (days)",
                "min_lead_time_days": "Min",
                "max_lead_time_days": "Max",
            }),
            use_container_width=True, hide_index=True,
        )

st.divider()

# ===========================================================================
# I — Cancellation Rate (Metric #3)
# ===========================================================================
st.subheader("I  Cancellation Rate by Segment  (Metric #3)")
st.caption("cancelled_bookings / total_bookings per segment.")

if cancel_df.empty:
    st.info("No cancellation data available.")
else:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.bar_chart(
            cancel_df.set_index("segment_name")["cancellation_rate"],
            use_container_width=True,
        )
    with col_r:
        disp_c = cancel_df.copy().rename(columns={
            "segment_name": "Segment",
            "total_bookings": "Total",
            "cancelled_bookings": "Cancelled",
            "cancellation_rate": "Rate",
        })
        disp_c["Rate"] = disp_c["Rate"].apply(lambda x: f"{x:.1%}")
        st.dataframe(disp_c, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.caption(
    "Data: `data/processed/occupancy.db`  ·  "
    "Pipeline: ingest → clean → features → load  ·  "
    "All 8 metrics per SPEC Section 5  ·  "
    "Repo: github.com/akhilk49/Occupancy-Volatility-Index"
)
