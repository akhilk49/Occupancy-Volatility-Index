"""ingest.py — Read raw CSVs, validate schema, and log ingestion metadata.

Responsibilities:
- Load each raw CSV without modifying the source file.
- Validate that required columns are present (schema contract from SPEC Section 4).
- Log row counts, column counts, and per-column null counts for every file loaded.
- Surface all schema issues in a single pass (do not raise on first error).

Implementation: Day 6.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.config import (
    BOOKINGS_CSV,
    BOOKINGS_REQUIRED_COLS,
    CANCELLATIONS_CSV,
    CANCELLATIONS_REQUIRED_COLS,
    SEASONAL_PRICING_CSV,
    SEASONAL_PRICING_REQUIRED_COLS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV file and return a raw DataFrame.

    The source file is never modified — all raw files under ``data/raw/`` are
    treated as read-only inputs throughout the pipeline.

    Args:
        path: Absolute or relative path to the CSV file.

    Returns:
        Raw DataFrame with no dtype coercion or transformations applied.
        All columns are read as ``object`` (string) initially so that
        date parsing and type casting happen explicitly in ``clean.py``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file is empty (zero rows after header).
    """
    raise NotImplementedError("Implement in Day 6")


def validate_schema(
    df: pd.DataFrame,
    required_cols: list[str],
    source_name: str,
) -> list[str]:
    """Check that *df* contains every column in *required_cols*.

    Logs a WARNING for each missing column but does not raise, so the
    pipeline surfaces all issues in one run rather than halting on the first.

    Args:
        df: DataFrame to inspect.
        required_cols: Column names that must be present (from ``config.py``).
        source_name: Human-readable label used in log messages (e.g. ``"bookings"``).

    Returns:
        List of column names that are missing. Empty list means schema is valid.
    """
    raise NotImplementedError("Implement in Day 6")


def log_ingestion_summary(df: pd.DataFrame, source_name: str) -> None:
    """Log a summary of a freshly loaded DataFrame.

    Emits the following at INFO level:
    - Source name and file path
    - Row count and column count
    - Per-column null count and null percentage for any column with nulls > 0

    Args:
        df: DataFrame that was just loaded by ``load_csv()``.
        source_name: Label used in log lines (e.g. ``"bookings"``).
    """
    raise NotImplementedError("Implement in Day 6")


def check_primary_key(df: pd.DataFrame, pk_col: str, source_name: str) -> int:
    """Check for duplicate values in the primary key column *pk_col*.

    Logs a WARNING with the count of duplicates if any are found.
    Duplicate ``reservation_id`` values in bookings are a known data quality
    issue (documented in ``docs/data_quality_notes.md`` — Akhil Day 2).

    Args:
        df: DataFrame to inspect.
        pk_col: Name of the column expected to be a unique primary key.
        source_name: Label used in log messages.

    Returns:
        Count of duplicate PK values (0 means clean).
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_bookings() -> pd.DataFrame:
    """Load, validate, and log ``bookings.csv``.

    Calls ``load_csv()``, ``validate_schema()``, ``log_ingestion_summary()``,
    and ``check_primary_key()`` in sequence.

    Known data quality issues to surface (from Day 2 profiling):
    - Mixed date formats across ``booking_date``, ``check_in_date``, ``check_out_date``.
    - Duplicate ``reservation_id`` values with differing field values.
    - ``total_rooms_available`` column is absent — logged as a WARNING.
    - Null values in ``segment`` and ``rate`` columns.

    Returns:
        Raw bookings DataFrame. No cleaning applied — output is passed
        directly to ``clean.clean_bookings()``.
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_cancellations() -> pd.DataFrame:
    """Load, validate, and log ``cancellations.csv``.

    Known data quality issues to surface (from Day 2 profiling — Manuel):
    - ~15% nulls in ``reason`` column.
    - Mixed date formats in ``cancellation_date`` (ISO and MM/DD/YYYY).
    - Duplicate ``reservation_id`` entries (same cancellation logged twice).

    Returns:
        Raw cancellations DataFrame. No cleaning applied — output is passed
        directly to ``clean.clean_cancellations()``.
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_seasonal_pricing() -> pd.DataFrame:
    """Load, validate, and log ``seasonal_pricing.csv``.

    Known data quality issues to surface (from Day 2 profiling — Manuel):
    - Exact duplicate rows for a few dates (safe to drop in cleaning).
    - Date format is consistently YYYY-MM-DD — no mixed formats expected.

    Returns:
        Raw seasonal pricing DataFrame. No cleaning applied — output is passed
        directly to ``clean.clean_seasonal_pricing()``.
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convenience wrapper: ingest all three raw files in one call.

    Returns:
        Tuple of ``(bookings, cancellations, seasonal_pricing)`` raw DataFrames.
        All three are unmodified — pass each to the corresponding clean function.
    """
    raise NotImplementedError("Implement in Day 6")
