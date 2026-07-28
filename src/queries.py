"""queries.py — Parameterised query functions for the Streamlit dashboard.

This is the sole interface between occupancy.db and the dashboard layer.
No SQL strings appear in app/dashboard.py — all queries live here.

Design rules:
  • All filters (segment, start_date, end_date, season_tag) are optional kwargs.
    None means no filter applied.
  • SQL uses ? placeholders (sqlite3 parameterised) — never f-strings with
    user-supplied values.
  • Metrics #2, #6, #8 require stddev/mean — SQLite has no STDDEV aggregate,
    so these fetch the raw daily series from the views and compute in pandas.
  • Every function returns a pd.DataFrame (never a list of tuples).

Usage:
    from src.queries import get_segment_summary
    from src.config import DB_PATH
    df = get_segment_summary(DB_PATH)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import ASSUMED_TOTAL_ROOMS, DB_PATH


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a read-only-safe SQLite connection with row factory set.

    Args:
        db_path: Path to occupancy.db.

    Returns:
        sqlite3.Connection with Row row_factory enabled.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Run 'python -m src.load' first to create occupancy.db."
        )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _build_where(
    filters: dict[str, str | None],
    col_map: dict[str, str],
) -> tuple[str, list]:
    """Build a WHERE clause and params list from optional filter values.

    Args:
        filters: Dict of filter_name → value (None = skip).
        col_map: Dict of filter_name → SQL column expression.

    Returns:
        Tuple of (where_clause_string, params_list).
        where_clause_string is "" if no filters apply.
    """
    clauses, params = [], []
    for name, val in filters.items():
        if val is not None:
            clauses.append(f"{col_map[name]} = ?")
            params.append(val)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _date_range_clause(
    start_date: str | None,
    end_date: str | None,
    col: str,
    existing_where: bool = False,
) -> tuple[str, list]:
    """Build date range filter fragment.

    Args:
        start_date: ISO date string lower bound (inclusive), or None.
        end_date:   ISO date string upper bound (inclusive), or None.
        col:        SQL column to filter on (e.g. ``"f.check_in_date"``).
        existing_where: True if a WHERE clause is already in the query.

    Returns:
        Tuple of (sql_fragment, params).
    """
    parts, params = [], []
    if start_date:
        parts.append(f"{col} >= ?")
        params.append(start_date)
    if end_date:
        parts.append(f"{col} <= ?")
        params.append(end_date)
    if not parts:
        return "", []
    connector = "AND" if existing_where else "WHERE"
    return connector + " " + " AND ".join(parts), params


# ===========================================================================
# Metric #1 — Occupancy Rate
# ===========================================================================

def get_occupancy_by_segment_day(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return daily occupancy rate per segment (Metric #1).

    Occupancy rate = booked_room_nights / ASSUMED_TOTAL_ROOMS per day.

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment name, or None for all.
        start_date: ISO date lower bound on check_in_date (inclusive).
        end_date:   ISO date upper bound on check_in_date (inclusive).

    Returns:
        DataFrame with columns:
            segment_name, date, booked_room_nights, occupancy_rate
    """
    conn = _connect(db_path)
    try:
        seg_filter = "AND v.segment_name = ?" if segment else ""
        date_parts, date_params = [], []
        if start_date:
            date_parts.append("v.date >= ?")
            date_params.append(start_date)
        if end_date:
            date_parts.append("v.date <= ?")
            date_params.append(end_date)
        date_filter = ("AND " + " AND ".join(date_parts)) if date_parts else ""

        params = []
        if segment:
            params.append(segment)
        params.extend(date_params)

        sql = f"""
            SELECT
                v.segment_name,
                v.date,
                v.booked_room_nights,
                ROUND(v.booked_room_nights * 1.0 / ?, 4) AS occupancy_rate
            FROM v_daily_room_nights_by_segment v
            WHERE 1=1
            {seg_filter}
            {date_filter}
            ORDER BY v.segment_name, v.date
        """
        df = pd.read_sql_query(sql, conn, params=[ASSUMED_TOTAL_ROOMS] + params)
        df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()


# ===========================================================================
# Metric #2 — Occupancy Volatility (CoV)
# ===========================================================================

def get_occupancy_volatility_cov(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_days: int | None = 30,
) -> pd.DataFrame:
    """Return Occupancy Volatility (CoV) per segment (Metric #2).

    CoV = stddev(occupancy_rate) / mean(occupancy_rate).
    Computed in pandas because SQLite has no STDDEV aggregate.

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.
        start_date: ISO date lower bound.
        end_date:   ISO date upper bound.
        rolling_days: Window size for rolling CoV. None = whole-period CoV only.

    Returns:
        DataFrame with columns:
            segment_name, cov  (whole-period coefficient of variation)
        If rolling_days is set, also includes a ``rolling_cov`` series
        returned as a separate key in a dict — use get_occupancy_daily_series()
        for chart data.
    """
    daily = get_occupancy_by_segment_day(db_path, segment, start_date, end_date)
    if daily.empty:
        return pd.DataFrame(columns=["segment_name", "cov"])

    # Whole-period CoV per segment
    result = (
        daily.groupby("segment_name")["occupancy_rate"]
        .agg(mean="mean", std="std")
        .reset_index()
    )
    result["cov"] = (result["std"] / result["mean"]).round(4)
    result = result.drop(columns=["mean", "std"])
    return result.sort_values("cov", ascending=False).reset_index(drop=True)


# ===========================================================================
# Metric #3 — Cancellation Rate
# ===========================================================================

def get_cancellation_rate_by_segment(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
) -> pd.DataFrame:
    """Return cancellation rate per segment (Metric #3).

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.

    Returns:
        DataFrame with columns:
            segment_name, total_bookings, cancelled_bookings, cancellation_rate
    """
    conn = _connect(db_path)
    try:
        seg_filter = "WHERE segment_name = ?" if segment else ""
        params = [segment] if segment else []
        sql = f"""
            SELECT
                segment_name,
                total_bookings,
                cancelled_bookings,
                ROUND(cancellation_rate, 4) AS cancellation_rate
            FROM v_cancellation_stats_by_segment
            {seg_filter}
            ORDER BY cancellation_rate DESC
        """
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


# ===========================================================================
# Metric #4 — Average Lead Time
# ===========================================================================

def get_avg_lead_time_by_segment(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
) -> pd.DataFrame:
    """Return average lead time in days per segment (Metric #4).

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.

    Returns:
        DataFrame with columns:
            segment_name, avg_lead_time_days, min_lead_time_days, max_lead_time_days
    """
    conn = _connect(db_path)
    try:
        seg_filter = "WHERE segment_name = ?" if segment else ""
        params = [segment] if segment else []
        sql = f"""
            SELECT
                segment_name,
                ROUND(avg_lead_time_days, 1) AS avg_lead_time_days,
                min_lead_time_days,
                max_lead_time_days
            FROM v_lead_time_by_segment
            {seg_filter}
            ORDER BY avg_lead_time_days DESC
        """
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


# ===========================================================================
# Metric #5 — Seasonal Concentration Index
# ===========================================================================

def get_seasonal_concentration(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
) -> pd.DataFrame:
    """Return Seasonal Concentration Index per segment (Metric #5).

    Index = (share of bookings in top-2 seasons) / (1 / N_seasons).
    A value > 1 means more concentrated than even spread.
    Computed in pandas because it requires ranking within groups.

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.

    Returns:
        DataFrame with columns:
            segment_name, n_seasons, top2_share, even_share,
            seasonal_concentration_index
    """
    conn = _connect(db_path)
    try:
        seg_filter = "WHERE segment_name = ?" if segment else ""
        params = [segment] if segment else []
        sql = f"""
            SELECT segment_name, season_tag, booking_count
            FROM v_bookings_by_segment_season
            {seg_filter}
        """
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame(columns=[
            "segment_name", "n_seasons", "top2_share",
            "even_share", "seasonal_concentration_index",
        ])

    rows = []
    for seg, grp in df.groupby("segment_name"):
        total = grp["booking_count"].sum()
        n_seasons = len(grp)
        if total == 0 or n_seasons == 0:
            continue
        # Top-2 seasons by booking count
        top2 = grp.nlargest(2, "booking_count")["booking_count"].sum()
        top2_share = top2 / total
        even_share = min(2, n_seasons) / n_seasons  # even spread baseline for top-2
        index = round(top2_share / even_share, 4) if even_share > 0 else None
        rows.append({
            "segment_name": seg,
            "n_seasons": n_seasons,
            "top2_share": round(top2_share, 4),
            "even_share": round(even_share, 4),
            "seasonal_concentration_index": index,
        })

    return (
        pd.DataFrame(rows)
        .sort_values("seasonal_concentration_index", ascending=False)
        .reset_index(drop=True)
    )


# ===========================================================================
# Metric #6 — Segment Volatility Contribution
# ===========================================================================

def get_segment_volatility_contribution(
    db_path: str | Path = DB_PATH,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return Segment Volatility Contribution for all segments (Metric #6).

    Contribution = segment_variance(occupancy_rate) / total_variance.
    Total variance = sum of all per-segment variances.
    Computed in pandas (SQLite has no VARIANCE aggregate).

    Args:
        db_path: Path to occupancy.db.
        start_date: ISO date lower bound.
        end_date:   ISO date upper bound.

    Returns:
        DataFrame with columns:
            segment_name, variance, volatility_contribution
        Sorted descending by volatility_contribution (headline metric).
    """
    daily = get_occupancy_by_segment_day(db_path, start_date=start_date, end_date=end_date)
    if daily.empty:
        return pd.DataFrame(columns=["segment_name", "variance", "volatility_contribution"])

    # Variance per segment (use ddof=1 for sample variance)
    var_by_seg = (
        daily.groupby("segment_name")["occupancy_rate"]
        .var(ddof=1)
        .reset_index()
        .rename(columns={"occupancy_rate": "variance"})
    )
    total_var = var_by_seg["variance"].sum()

    if total_var == 0:
        var_by_seg["volatility_contribution"] = 0.0
    else:
        var_by_seg["volatility_contribution"] = (
            var_by_seg["variance"] / total_var
        ).round(4)

    var_by_seg["variance"] = var_by_seg["variance"].round(6)
    return var_by_seg.sort_values("volatility_contribution", ascending=False).reset_index(drop=True)


# ===========================================================================
# Metric #7 — Revenue at Risk
# ===========================================================================

def get_revenue_at_risk(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
) -> pd.DataFrame:
    """Return revenue at risk from cancellations per segment (Metric #7).

    Revenue at risk = SUM(room_nights * rate) where is_cancelled = TRUE.

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.

    Returns:
        DataFrame with columns: segment_name, revenue_at_risk
    """
    conn = _connect(db_path)
    try:
        seg_filter = "WHERE segment_name = ?" if segment else ""
        params = [segment] if segment else []
        sql = f"""
            SELECT
                segment_name,
                ROUND(revenue_at_risk, 2) AS revenue_at_risk
            FROM v_revenue_at_risk_by_segment
            {seg_filter}
            ORDER BY revenue_at_risk DESC
        """
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


# ===========================================================================
# Metric #8 — Revenue Volatility Index
# ===========================================================================

def get_revenue_volatility_index(
    db_path: str | Path = DB_PATH,
    segment: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return Revenue Volatility Index per segment (Metric #8).

    RVI = stddev(daily_room_revenue) / mean(daily_room_revenue).
    Computed in pandas (SQLite has no STDDEV aggregate).

    Args:
        db_path: Path to occupancy.db.
        segment: Filter to a single segment, or None for all.
        start_date: ISO date lower bound.
        end_date:   ISO date upper bound.

    Returns:
        DataFrame with columns: segment_name, mean_daily_revenue, rvi
    """
    conn = _connect(db_path)
    try:
        seg_filter = "AND segment_name = ?" if segment else ""
        date_parts, date_params = [], []
        if start_date:
            date_parts.append("date >= ?")
            date_params.append(start_date)
        if end_date:
            date_parts.append("date <= ?")
            date_params.append(end_date)
        date_filter = ("AND " + " AND ".join(date_parts)) if date_parts else ""

        params = []
        if segment:
            params.append(segment)
        params.extend(date_params)

        sql = f"""
            SELECT segment_name, date, daily_room_revenue
            FROM v_daily_revenue_by_segment
            WHERE 1=1
            {seg_filter}
            {date_filter}
            ORDER BY segment_name, date
        """
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame(columns=["segment_name", "mean_daily_revenue", "rvi"])

    result = (
        df.groupby("segment_name")["daily_room_revenue"]
        .agg(mean="mean", std="std")
        .reset_index()
    )
    result["rvi"] = (result["std"] / result["mean"]).round(4)
    result["mean_daily_revenue"] = result["mean"].round(2)
    return (
        result[["segment_name", "mean_daily_revenue", "rvi"]]
        .sort_values("rvi", ascending=False)
        .reset_index(drop=True)
    )


# ===========================================================================
# Combined segment summary (dashboard ranking table)
# ===========================================================================

def get_segment_summary(
    db_path: str | Path = DB_PATH,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return a full per-segment summary with all 8 metrics (Metric #1–#8).

    SQL aggregates (Metrics #3, #4, #7) are fetched from v_segment_summary.
    Pandas-computed metrics (CoV #2, Volatility Contribution #6, RVI #8)
    are computed from their daily series and joined in.

    This is the primary data source for the dashboard's segment ranking table.

    Args:
        db_path: Path to occupancy.db.
        start_date: ISO date lower bound on check_in_date.
        end_date:   ISO date upper bound on check_in_date.

    Returns:
        DataFrame with columns:
            segment_name, total_bookings, cancellation_rate,
            avg_lead_time_days, revenue_at_risk,
            cov, volatility_contribution, rvi,
            seasonal_concentration_index
        One row per segment, sorted by volatility_contribution descending.
    """
    # --- SQL aggregates ---
    conn = _connect(db_path)
    try:
        sql = """
            SELECT
                segment_name,
                total_bookings,
                total_room_nights,
                ROUND(cancellation_rate, 4)   AS cancellation_rate,
                ROUND(avg_lead_time_days, 1)  AS avg_lead_time_days,
                ROUND(revenue_at_risk, 2)     AS revenue_at_risk
            FROM v_segment_summary
            ORDER BY total_bookings DESC
        """
        summary = pd.read_sql_query(sql, conn)
    finally:
        conn.close()

    if summary.empty:
        return summary

    # --- Pandas-computed metrics ---
    cov_df = get_occupancy_volatility_cov(db_path, start_date=start_date, end_date=end_date)
    contrib_df = get_segment_volatility_contribution(db_path, start_date=start_date, end_date=end_date)
    rvi_df = get_revenue_volatility_index(db_path, start_date=start_date, end_date=end_date)
    sci_df = get_seasonal_concentration(db_path)

    # Join them all onto the base summary
    summary = summary.merge(cov_df[["segment_name", "cov"]], on="segment_name", how="left")
    summary = summary.merge(
        contrib_df[["segment_name", "volatility_contribution"]],
        on="segment_name", how="left",
    )
    summary = summary.merge(
        rvi_df[["segment_name", "rvi"]],
        on="segment_name", how="left",
    )
    summary = summary.merge(
        sci_df[["segment_name", "seasonal_concentration_index"]],
        on="segment_name", how="left",
    )

    return (
        summary.sort_values("volatility_contribution", ascending=False)
        .reset_index(drop=True)
    )
