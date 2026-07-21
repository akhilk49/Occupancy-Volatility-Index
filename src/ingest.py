"""ingest.py — Read raw CSVs, validate schema, and log ingestion metadata.

Responsibilities:
- Load each raw CSV without modifying the source file.
- Validate that required columns are present (schema contract from SPEC Section 4).
- Log row counts, column counts, and per-column null counts for every file loaded.
- Surface all schema issues in a single pass (do not raise on first error).

Usage:
    from src.ingest import ingest_all
    bookings, cancellations, seasonal_pricing = ingest_all()

Or run as a script to verify raw files:
    python -m src.ingest
"""

from __future__ import annotations

import logging
import sys
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

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [ingest] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV file and return a raw DataFrame.

    All columns are read as ``object`` (string) dtype — explicit type coercion
    and date parsing happen in ``clean.py``, not here. This ensures the raw
    data is never silently mangled during ingestion.

    The source file is never modified — all files under ``data/raw/`` are
    treated as read-only throughout the pipeline.

    Args:
        path: Absolute or relative path to the CSV file.

    Returns:
        Raw DataFrame with dtype=object for all columns.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file is empty (zero rows after the header).
    """
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")

    # dtype=str keeps everything as object — no silent date/numeric coercion
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NA", "N/A", "NULL", "null", "None"])

    if df.empty:
        raise ValueError(f"File loaded but contains zero rows: {path}")

    logger.info("Loaded '%s'  (%d rows, %d columns)", path.name, len(df), len(df.columns))
    return df


def validate_schema(
    df: pd.DataFrame,
    required_cols: list[str],
    source_name: str,
) -> list[str]:
    """Check that *df* contains every column in *required_cols*.

    Comparison is case-insensitive and strips leading/trailing whitespace from
    the actual column names to guard against common CSV export quirks.

    Logs a WARNING for each missing column but does not raise, so the pipeline
    surfaces all issues in one run rather than halting on the first problem.

    Args:
        df: DataFrame to inspect.
        required_cols: Column names that must be present (from ``config.py``).
        source_name: Human-readable label for log messages (e.g. ``"bookings"``).

    Returns:
        List of missing column names (lowercased). Empty list = schema valid.
    """
    # Normalise actual columns for comparison
    actual = {c.strip().lower() for c in df.columns}
    missing = [c for c in required_cols if c.lower() not in actual]

    if missing:
        for col in missing:
            logger.warning("[%s] Missing required column: '%s'", source_name, col)
    else:
        logger.info("[%s] Schema check passed — all required columns present", source_name)

    return missing


def log_ingestion_summary(df: pd.DataFrame, source_name: str) -> None:
    """Log a structured summary of a freshly loaded DataFrame.

    Emits at INFO level:
    - Row count and column count
    - Per-column null count and null % for any column where nulls > 0

    Args:
        df: DataFrame returned by ``load_csv()``.
        source_name: Label for log lines (e.g. ``"bookings"``).
    """
    logger.info("[%s] Rows: %d  |  Columns: %d", source_name, len(df), len(df.columns))

    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]

    if null_cols.empty:
        logger.info("[%s] No null values found in any column", source_name)
    else:
        for col, n in null_cols.items():
            pct = n / len(df) * 100
            logger.warning("[%s] Column '%s': %d nulls (%.1f%%)", source_name, col, n, pct)


def check_primary_key(df: pd.DataFrame, pk_col: str, source_name: str) -> int:
    """Check for duplicate values in *pk_col* (expected to be a unique key).

    Duplicate ``reservation_id`` values in bookings are a known data quality
    issue documented in ``docs/data_quality_notes.md`` (Akhil, Day 2).

    Args:
        df: DataFrame to inspect.
        pk_col: Name of the column expected to hold unique values.
        source_name: Label for log messages.

    Returns:
        Count of duplicate PK values (0 = clean).
    """
    if pk_col not in df.columns:
        logger.warning("[%s] PK column '%s' not found — skipping PK check", source_name, pk_col)
        return 0

    n_dupes = int(df[pk_col].duplicated().sum())
    if n_dupes:
        logger.warning(
            "[%s] %d duplicate '%s' values found — will be resolved in clean.py",
            source_name, n_dupes, pk_col,
        )
    else:
        logger.info("[%s] PK check passed — '%s' is unique", source_name, pk_col)

    return n_dupes


def ingest_bookings() -> pd.DataFrame:
    """Load, validate, and log ``bookings.csv``.

    Runs the full ingestion sequence:
    ``load_csv`` → ``validate_schema`` → ``log_ingestion_summary`` → ``check_primary_key``

    Known issues surfaced (Day 2 profiling):
    - Mixed date formats across ``booking_date``, ``check_in_date``, ``check_out_date``.
    - Duplicate ``reservation_id`` values with differing field values.
    - ``total_rooms_available`` is absent — logged as INFO (not an error; capacity
      handled via ``ASSUMED_TOTAL_ROOMS`` in ``config.py``).
    - Null values expected in ``segment`` and ``rate`` columns.

    Returns:
        Raw bookings DataFrame (no cleaning applied).
        Pass to ``clean.clean_bookings()`` as the next step.
    """
    df = load_csv(BOOKINGS_CSV)
    validate_schema(df, BOOKINGS_REQUIRED_COLS, "bookings")
    log_ingestion_summary(df, "bookings")
    check_primary_key(df, "reservation_id", "bookings")

    # total_rooms_available is confirmed absent — log once so it's visible
    if "total_rooms_available" not in [c.strip().lower() for c in df.columns]:
        logger.info(
            "[bookings] 'total_rooms_available' not present — "
            "occupancy rate will use ASSUMED_TOTAL_ROOMS from config.py (Decision D2)"
        )

    return df


def ingest_cancellations() -> pd.DataFrame:
    """Load, validate, and log ``cancellations.csv``.

    Known issues surfaced (Day 2 profiling — Manuel):
    - ~15% nulls in the ``reason`` column.
    - Mixed date formats in ``cancellation_date`` (ISO 8601 and MM/DD/YYYY).
    - Duplicate ``reservation_id`` entries where a cancellation was logged twice.

    Returns:
        Raw cancellations DataFrame (no cleaning applied).
        Pass to ``clean.clean_cancellations()`` as the next step.
    """
    df = load_csv(CANCELLATIONS_CSV)
    validate_schema(df, CANCELLATIONS_REQUIRED_COLS, "cancellations")
    log_ingestion_summary(df, "cancellations")
    check_primary_key(df, "reservation_id", "cancellations")
    return df


def ingest_seasonal_pricing() -> pd.DataFrame:
    """Load, validate, and log ``seasonal_pricing.csv``.

    Known issues surfaced (Day 2 profiling — Manuel):
    - Exact duplicate rows for a few dates (safe to drop in cleaning).
    - Date format is consistently YYYY-MM-DD — no mixed formats expected.

    Returns:
        Raw seasonal pricing DataFrame (no cleaning applied).
        Pass to ``clean.clean_seasonal_pricing()`` as the next step.
    """
    df = load_csv(SEASONAL_PRICING_CSV)
    validate_schema(df, SEASONAL_PRICING_REQUIRED_COLS, "seasonal_pricing")
    log_ingestion_summary(df, "seasonal_pricing")
    # seasonal_pricing has no single PK column — duplicate row check is done
    # in clean.py where exact-duplicate rows are dropped
    return df


def ingest_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convenience wrapper — ingest all three raw files in one call.

    Returns:
        Tuple of ``(bookings, cancellations, seasonal_pricing)`` raw DataFrames.
        All three are unmodified — pass each to the corresponding clean function.
    """
    bookings = ingest_bookings()
    cancellations = ingest_cancellations()
    seasonal_pricing = ingest_seasonal_pricing()
    return bookings, cancellations, seasonal_pricing


# ---------------------------------------------------------------------------
# Script entry point — run with: python -m src.ingest
# Prints row counts and flags missing required columns for all three files.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=== Ingestion check — verifying data/raw/*.csv ===")
    try:
        bookings, cancellations, seasonal_pricing = ingest_all()
        logger.info(
            "=== Done: bookings=%d rows | cancellations=%d rows | seasonal_pricing=%d rows ===",
            len(bookings), len(cancellations), len(seasonal_pricing),
        )
    except FileNotFoundError as exc:
        logger.error("Cannot run ingestion: %s", exc)
        logger.error("Place the raw CSV files in data/raw/ and try again.")
        sys.exit(1)
