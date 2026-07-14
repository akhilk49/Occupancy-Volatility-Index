"""features.py — Join logic and feature engineering.

Stub file. Implementation split across Days 9–10.
"""

from __future__ import annotations

import pandas as pd


def join_fact_table(
    bookings: pd.DataFrame,
    cancellations: pd.DataFrame,
    seasonal_pricing: pd.DataFrame,
) -> pd.DataFrame:
    """Build ``fact_bookings_enriched``: one row per reservation.

    Join logic (SPEC Section 4):
    - bookings LEFT JOIN cancellations ON reservation_id
    - bookings JOIN seasonal_pricing ON check_in_date = date
      (or nearest date within season window)

    Args:
        bookings: Cleaned bookings DataFrame.
        cancellations: Cleaned cancellations DataFrame.
        seasonal_pricing: Cleaned seasonal pricing DataFrame.

    Returns:
        Enriched fact DataFrame written to ``data/processed/fact_bookings_enriched.csv``.
    """
    raise NotImplementedError("Implement in Day 9")


def add_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``lead_time_days`` column: check_in_date minus booking_date.

    Args:
        df: Fact table DataFrame containing booking_date and check_in_date.

    Returns:
        DataFrame with new integer column ``lead_time_days``.
    """
    raise NotImplementedError("Implement in Day 10")


def add_cancel_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean ``is_cancelled`` column derived from the cancellations join.

    True when a matching cancellation record exists, False otherwise.

    Args:
        df: Fact table DataFrame after the LEFT JOIN with cancellations.

    Returns:
        DataFrame with new boolean column ``is_cancelled``.
    """
    raise NotImplementedError("Implement in Day 10")


def add_occupancy_rate(df: pd.DataFrame, total_rooms_available: int | None = None) -> pd.DataFrame:
    """Add ``occupancy_rate`` per day: booked_room_nights / available_room_nights.

    If ``total_rooms_available`` is None, derive capacity from the data or
    from the ``total_rooms_available`` column if it exists (resolve Day 1 open question).

    Args:
        df: Fact table DataFrame.
        total_rooms_available: Override for fixed capacity; pass None to derive.

    Returns:
        DataFrame with new float column ``occupancy_rate``.
    """
    raise NotImplementedError("Implement in Day 10")
