"""ingest.py — Read raw CSVs, validate schema, and log ingestion metadata.

Stub signatures with docstrings; implementation comes in Day 6.
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
    """Read a CSV from *path* and return a DataFrame.

    Does not modify the source file — raw data is always treated as read-only.

    Args:
        path: Absolute or relative path to the CSV file.

    Returns:
        A raw DataFrame with no transformations applied.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    raise NotImplementedError("Implement in Day 6")


def validate_schema(df: pd.DataFrame, required_cols: list[str], source_name: str) -> None:
    """Assert that *df* contains every column in *required_cols*.

    Logs a WARNING for each missing column but does not raise — the pipeline
    should continue so all issues surface in a single run, not one at a time.

    Args:
        df: DataFrame to inspect.
        required_cols: Column names that must be present.
        source_name: Human-readable label used in log messages (e.g. "bookings").
    """
    raise NotImplementedError("Implement in Day 6")


def log_ingestion_summary(df: pd.DataFrame, source_name: str) -> None:
    """Log row count, column count, and per-column null counts for *df*.

    Args:
        df: DataFrame that was just loaded.
        source_name: Label used in log lines (e.g. "bookings").
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_bookings() -> pd.DataFrame:
    """Load, validate, and log ``bookings.csv``.

    Returns:
        Raw bookings DataFrame (no cleaning applied).
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_cancellations() -> pd.DataFrame:
    """Load, validate, and log ``cancellations.csv``.

    Returns:
        Raw cancellations DataFrame (no cleaning applied).
    """
    raise NotImplementedError("Implement in Day 6")


def ingest_seasonal_pricing() -> pd.DataFrame:
    """Load, validate, and log ``seasonal_pricing.csv``.

    Returns:
        Raw seasonal pricing DataFrame (no cleaning applied).
    """
    raise NotImplementedError("Implement in Day 6")
