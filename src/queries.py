"""queries.py — Parameterised query functions used by the Streamlit dashboard.

Stub file. Implementation in Days 12–15.
"""

from __future__ import annotations

import pandas as pd


def get_occupancy_by_segment_day(db_path: str, segment: str | None = None) -> pd.DataFrame:
    """Return daily booked room-nights per segment (Metric #1).

    Args:
        db_path: Path to the SQLite database.
        segment: Optional segment filter; None returns all segments.

    Returns:
        DataFrame with columns: segment_name, date, booked_room_nights.
    """
    raise NotImplementedError("Implement in Day 12")


def get_cancellation_rate_by_segment(db_path: str) -> pd.DataFrame:
    """Return cancellation rate per segment (Metric #3).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame with columns: segment_name, total_bookings, cancelled_bookings, cancellation_rate.
    """
    raise NotImplementedError("Implement in Day 13")


def get_avg_lead_time_by_segment(db_path: str) -> pd.DataFrame:
    """Return average lead time in days per segment (Metric #4).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame with columns: segment_name, avg_lead_time_days.
    """
    raise NotImplementedError("Implement in Day 13")


def get_seasonal_concentration(db_path: str) -> pd.DataFrame:
    """Return seasonal concentration index per segment (Metric #5).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame with columns: segment_name, seasonal_concentration_index.
    """
    raise NotImplementedError("Implement in Day 14")


def get_revenue_at_risk(db_path: str) -> pd.DataFrame:
    """Return revenue at risk from cancellations per segment (Metric #7).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame with columns: segment_name, revenue_at_risk.
    """
    raise NotImplementedError("Implement in Day 14")
