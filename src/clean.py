"""clean.py — Null handling, deduplication, date standardisation, segment normalisation.

Stub file. Implementation split across Days 7–8.
"""

from __future__ import annotations

import pandas as pd


def clean_bookings(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw bookings DataFrame.

    Steps (to be implemented Day 7–8):
    - Drop exact duplicate rows; log count removed.
    - Standardise date columns (booking_date, check_in_date, check_out_date) to ISO 8601.
    - Handle nulls in critical columns (segment, booking_date, check_in_date).
    - Normalise segment labels to a canonical set (see Day 8).

    Args:
        df: Raw bookings DataFrame from ``ingest.ingest_bookings()``.

    Returns:
        Cleaned DataFrame written to ``data/interim/bookings_clean.csv``.
    """
    raise NotImplementedError("Implement in Day 7")


def clean_cancellations(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw cancellations DataFrame.

    Steps (to be implemented Day 7):
    - Verify all reservation_id values match those in bookings.
    - Standardise cancellation_date to ISO 8601.
    - Handle nulls in reason / refund_status.

    Args:
        df: Raw cancellations DataFrame from ``ingest.ingest_cancellations()``.

    Returns:
        Cleaned DataFrame written to ``data/interim/cancellations_clean.csv``.
    """
    raise NotImplementedError("Implement in Day 7")


def clean_seasonal_pricing(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw seasonal pricing DataFrame.

    Steps (to be implemented Day 8):
    - Standardise date column to ISO 8601.
    - Align date range with bookings date range.
    - Handle nulls in base_rate / demand_tier.

    Args:
        df: Raw seasonal pricing DataFrame from ``ingest.ingest_seasonal_pricing()``.

    Returns:
        Cleaned DataFrame written to ``data/interim/seasonal_pricing_clean.csv``.
    """
    raise NotImplementedError("Implement in Day 8")


def normalise_segments(df: pd.DataFrame, canonical_map: dict[str, str]) -> pd.DataFrame:
    """Remap segment label variants to their canonical form.

    Example: {"travel agency": "Travel Agency", "ta": "Travel Agency", ...}

    Args:
        df: DataFrame that contains a ``segment`` column.
        canonical_map: Mapping from any observed spelling/casing to the canonical label.

    Returns:
        DataFrame with ``segment`` values replaced by canonical labels.
        Unmapped values are left as-is and logged as warnings.
    """
    raise NotImplementedError("Implement in Day 8")
