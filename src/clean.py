"""clean.py — Null handling, deduplication, date standardisation, segment normalisation.

Covers cleaning for all three raw files:
  - bookings.csv      → clean_bookings()
  - cancellations.csv → clean_cancellations()
  - seasonal_pricing.csv → clean_seasonal_pricing()

Each function writes its output to data/interim/ and returns the cleaned DataFrame.
Every cleaning decision has an inline comment explaining *why*, not just *what*.

Usage:
    from src.clean import clean_bookings, clean_cancellations, clean_seasonal_pricing
    bookings_clean    = clean_bookings(raw_bookings)
    cancellations_clean = clean_cancellations(raw_cancellations, bookings_clean)
    pricing_clean     = clean_seasonal_pricing(raw_pricing, bookings_clean)

Or run as a script (requires raw CSVs in data/raw/):
    python -m src.clean
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from src.config import (
    ASSUMED_TOTAL_ROOMS,
    CANONICAL_SEGMENTS,
    INTERIM_DIR,
    BOOKINGS_CSV,
    CANCELLATIONS_CSV,
    SEASONAL_PRICING_CSV,
)
from src.ingest import ingest_bookings, ingest_cancellations, ingest_seasonal_pricing

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [clean] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical segment mapping
# Keys: every observed raw variant (lowercased, stripped).
# Values: canonical label from CANONICAL_SEGMENTS in config.py.
# Add new variants here as they are discovered — do not change the values.
# (Decision confirmed Day 2: segment = booking channel, not customer type)
# ---------------------------------------------------------------------------
SEGMENT_CANONICAL_MAP: dict[str, str] = {
    # Travel Agency variants
    "travel agency": "Travel Agency",
    "travelagency":  "Travel Agency",
    "travel_agency": "Travel Agency",
    "ta":            "Travel Agency",
    "t/a":           "Travel Agency",
    "travel agent":  "Travel Agency",
    # Direct variants
    "direct":        "Direct",
    "direct booking": "Direct",
    "direct book":   "Direct",
    # Corporate variants
    "corporate":     "Corporate",
    "corp":          "Corporate",
    "corporate booking": "Corporate",
    # Group variants
    "group":         "Group",
    "grp":           "Group",
    "groups":        "Group",
    # Walk-in variants
    "walk-in":       "Walk-in",
    "walkin":        "Walk-in",
    "walk in":       "Walk-in",
    "walk_in":       "Walk-in",
}

# Date columns that need ISO 8601 standardisation in bookings
BOOKINGS_DATE_COLS: list[str] = ["booking_date", "check_in_date", "check_out_date"]


# ===========================================================================
# Internal helpers
# ===========================================================================

def _parse_dates(series: pd.Series, col_name: str) -> pd.Series:
    """Parse a string date series to datetime64, handling mixed formats.

    Tries ISO 8601 first (fast path), then falls back to dateutil inference
    for any rows that failed. Rows that cannot be parsed at all become NaT
    and are logged so the count is visible.

    Args:
        series: Raw string series from the DataFrame.
        col_name: Column name used in log messages.

    Returns:
        datetime64[ns] Series.
    """
    # First pass: let pandas infer — catches YYYY-MM-DD and most common formats
    # infer_datetime_format removed in pandas 3.x; format="mixed" handles varied formats
    parsed = pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=False)

    n_failed = parsed.isna().sum() - series.isna().sum()
    if n_failed > 0:
        logger.warning(
            "Column '%s': %d values could not be parsed to dates and set to NaT",
            col_name, n_failed,
        )
    else:
        logger.info("Column '%s': all values parsed successfully", col_name)

    return parsed


def _write_interim(df: pd.DataFrame, filename: str) -> Path:
    """Write *df* to data/interim/<filename> and return the path.

    Creates data/interim/ if it does not already exist.
    """
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INTERIM_DIR / filename
    df.to_csv(out_path, index=False)
    logger.info("Written %d rows → %s", len(df), out_path)
    return out_path


# ===========================================================================
# Public API
# ===========================================================================

def normalise_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Remap raw segment label variants to their canonical form.

    Uses SEGMENT_CANONICAL_MAP (case-insensitive, whitespace-stripped).
    Rows with null segment are set to 'Unknown' so they are retained in the
    fact table without polluting any real segment group (Decision D4, SPEC 11.3).
    Any non-null value that has no mapping is left as-is and logged as a WARNING
    so it can be added to the map manually.

    Args:
        df: DataFrame containing a ``segment`` column.

    Returns:
        DataFrame with ``segment`` normalised in place.
    """
    if "segment" not in df.columns:
        logger.warning("'segment' column not found — skipping normalisation")
        return df

    # Null → 'Unknown': retain row but exclude from segment aggregations
    null_count = df["segment"].isna().sum()
    if null_count:
        logger.warning(
            "%d null segment values → set to 'Unknown' (retained in fact table, "
            "excluded from segment-level metrics per Decision D4)",
            null_count,
        )
    df["segment"] = df["segment"].fillna("Unknown")

    def _map(val: str) -> str:
        key = val.strip().lower()
        mapped = SEGMENT_CANONICAL_MAP.get(key)
        if mapped:
            return mapped
        if val != "Unknown":
            logger.warning(
                "Unmapped segment value '%s' — add to SEGMENT_CANONICAL_MAP if this is a valid variant",
                val,
            )
        return val

    df["segment"] = df["segment"].apply(_map)

    canonical_plus_unknown = set(CANONICAL_SEGMENTS) | {"Unknown"}
    found = set(df["segment"].unique())
    logger.info("Segment values after normalisation: %s", sorted(found))
    unexpected = found - canonical_plus_unknown
    if unexpected:
        logger.warning("Unexpected segment values remaining: %s", unexpected)

    return df


def clean_bookings(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw bookings DataFrame and write to data/interim/bookings_clean.csv.

    Steps (in order):
    1. Strip whitespace from all column names.
    2. Drop exact duplicate rows — identical rows add no information.
    3. Resolve duplicate reservation_id (non-exact): keep row with the latest
       booking_date, as it is most likely the authoritative record.
    4. Standardise date columns to datetime64 (ISO 8601 output).
    5. Drop rows where check_in_date or booking_date is NaT — these cannot
       contribute to any metric that requires dates.
    6. Drop rows where check_out_date <= check_in_date — logically invalid stays.
    7. Derive room_nights from (check_out_date - check_in_date).days; use raw
       ``nights`` as fallback if derivation fails.
    8. Handle null ``rate``: keep as NaN — imputation from base_rate happens in
       features.py after the seasonal_pricing join.
    9. Handle null ``room_type``: fill with 'Unknown'.
    10. Normalise segment labels via normalise_segments().

    Args:
        df: Raw bookings DataFrame from ``ingest.ingest_bookings()``.

    Returns:
        Cleaned DataFrame. Also written to data/interim/bookings_clean.csv.
    """
    logger.info("--- Cleaning bookings ---")
    n_raw = len(df)

    # 1. Strip column name whitespace (CSV export sometimes adds spaces)
    df.columns = df.columns.str.strip()

    # 2. Drop exact duplicate rows
    n_before = len(df)
    df = df.drop_duplicates()
    n_exact_dupes = n_before - len(df)
    if n_exact_dupes:
        logger.info("Dropped %d exact duplicate rows", n_exact_dupes)

    # 3. Resolve duplicate reservation_id keeping latest booking_date
    #    — parse booking_date first (temp) to sort, then re-parse cleanly below
    if "booking_date" in df.columns:
        df["_booking_date_tmp"] = pd.to_datetime(df["booking_date"], errors="coerce", format="mixed", dayfirst=False)
        n_before = len(df)
        df = (
            df.sort_values("_booking_date_tmp", ascending=False)
              .drop_duplicates(subset=["reservation_id"], keep="first")
              .drop(columns=["_booking_date_tmp"])
        )
        n_pk_dupes = n_before - len(df)
        if n_pk_dupes:
            logger.info(
                "Resolved %d duplicate reservation_id rows — kept row with latest booking_date",
                n_pk_dupes,
            )

    # 4. Standardise date columns
    for col in BOOKINGS_DATE_COLS:
        if col in df.columns:
            df[col] = _parse_dates(df[col], col)

    # 5. Drop rows with missing critical dates — cannot be used in any time-based metric
    n_before = len(df)
    df = df.dropna(subset=["check_in_date", "booking_date"])
    n_dropped = n_before - len(df)
    if n_dropped:
        logger.warning(
            "Dropped %d rows with null check_in_date or booking_date "
            "— cannot attribute to any time period",
            n_dropped,
        )

    # 6. Drop logically invalid rows: check_out_date <= check_in_date
    if "check_out_date" in df.columns:
        n_before = len(df)
        invalid_mask = df["check_out_date"].notna() & (df["check_out_date"] <= df["check_in_date"])
        df = df[~invalid_mask]
        n_invalid = n_before - len(df)
        if n_invalid:
            logger.warning(
                "Dropped %d rows where check_out_date <= check_in_date — logically invalid",
                n_invalid,
            )

    # 7. Derive room_nights from date difference; fall back to raw ``nights``
    if "check_out_date" in df.columns:
        df["room_nights"] = (df["check_out_date"] - df["check_in_date"]).dt.days
        # Where derivation gives 0 or negative (shouldn't happen after step 6), fill from nights
        if "nights" in df.columns:
            nights_numeric = pd.to_numeric(df["nights"], errors="coerce")
            fallback_mask = df["room_nights"].isna() | (df["room_nights"] <= 0)
            df.loc[fallback_mask, "room_nights"] = nights_numeric[fallback_mask]
            n_fallback = fallback_mask.sum()
            if n_fallback:
                logger.info(
                    "%d rows used raw 'nights' as fallback for room_nights", n_fallback
                )
    elif "nights" in df.columns:
        # check_out_date absent — use raw nights column directly
        df["room_nights"] = pd.to_numeric(df["nights"], errors="coerce")

    # Convert nights to numeric if present
    if "nights" in df.columns:
        df["nights"] = pd.to_numeric(df["nights"], errors="coerce")

    # 8. rate: keep NaN — imputation happens in features.py after seasonal_pricing join
    if "rate" in df.columns:
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        n_null_rate = df["rate"].isna().sum()
        if n_null_rate:
            logger.warning(
                "%d null rate values retained — will be imputed from base_rate in features.py",
                n_null_rate,
            )

    # 9. room_type: fill nulls with 'Unknown' — not a primary groupby dimension
    if "room_type" in df.columns:
        n_null_rt = df["room_type"].isna().sum()
        if n_null_rt:
            df["room_type"] = df["room_type"].fillna("Unknown")
            logger.info(
                "%d null room_type values → 'Unknown' (not a primary analysis dimension)",
                n_null_rt,
            )

    # 10. Normalise segment labels
    df = normalise_segments(df)

    logger.info(
        "Bookings cleaning complete: %d raw → %d clean rows", n_raw, len(df)
    )
    _write_interim(df, "bookings_clean.csv")
    return df


def clean_cancellations(
    df: pd.DataFrame,
    bookings_clean: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Clean the raw cancellations DataFrame and write to data/interim/cancellations_clean.csv.

    Steps (in order):
    1. Strip whitespace from column names.
    2. Drop exact duplicate rows.
    3. Resolve duplicate reservation_id: keep row with the latest cancellation_date
       — same reservation logged twice, most recent record wins.
    4. Standardise cancellation_date to datetime64.
    5. Drop rows where cancellation_date is NaT — unusable for time-based analysis.
    6. If bookings_clean is provided, flag reservation_ids that have no matching
       booking (orphan cancellations) — log count but retain them so data loss
       is explicit; they will become unmatched in the LEFT JOIN.
    7. Fill null ``reason`` with 'Unknown' — ~15% nulls expected (Manuel Day 2).
    8. Fill null ``refund_status`` with 'Unknown'.

    Args:
        df: Raw cancellations DataFrame from ``ingest.ingest_cancellations()``.
        bookings_clean: Optional cleaned bookings DataFrame used to detect orphan IDs.

    Returns:
        Cleaned DataFrame. Also written to data/interim/cancellations_clean.csv.
    """
    logger.info("--- Cleaning cancellations ---")
    n_raw = len(df)

    # 1. Strip column names
    df.columns = df.columns.str.strip()

    # 2. Drop exact duplicates
    n_before = len(df)
    df = df.drop_duplicates()
    n_exact = n_before - len(df)
    if n_exact:
        logger.info("Dropped %d exact duplicate rows", n_exact)

    # 3. Resolve duplicate reservation_id — keep latest cancellation_date
    if "cancellation_date" in df.columns:
        df["_cancel_date_tmp"] = pd.to_datetime(
            df["cancellation_date"], errors="coerce", format="mixed", dayfirst=False
        )
        n_before = len(df)
        df = (
            df.sort_values("_cancel_date_tmp", ascending=False)
              .drop_duplicates(subset=["reservation_id"], keep="first")
              .drop(columns=["_cancel_date_tmp"])
        )
        n_pk_dupes = n_before - len(df)
        if n_pk_dupes:
            logger.info(
                "Resolved %d duplicate reservation_id rows — kept latest cancellation_date",
                n_pk_dupes,
            )

    # 4. Standardise cancellation_date
    if "cancellation_date" in df.columns:
        df["cancellation_date"] = _parse_dates(df["cancellation_date"], "cancellation_date")

    # 5. Drop rows with null cancellation_date — unusable for any time-based metric
    n_before = len(df)
    df = df.dropna(subset=["cancellation_date"])
    n_dropped = n_before - len(df)
    if n_dropped:
        logger.warning(
            "Dropped %d rows with null cancellation_date", n_dropped
        )

    # 6. Flag orphan cancellation IDs (no matching booking)
    if bookings_clean is not None and "reservation_id" in bookings_clean.columns:
        booking_ids = set(bookings_clean["reservation_id"].dropna())
        orphan_mask = ~df["reservation_id"].isin(booking_ids)
        n_orphan = orphan_mask.sum()
        if n_orphan:
            logger.warning(
                "%d cancellation rows have no matching reservation_id in bookings_clean "
                "— retained but will be unmatched in the LEFT JOIN",
                n_orphan,
            )

    # 7. Fill null reason — ~15% expected; retain as 'Unknown' for completeness
    if "reason" in df.columns:
        n_null = df["reason"].isna().sum()
        if n_null:
            df["reason"] = df["reason"].fillna("Unknown")
            logger.info("%d null reason values → 'Unknown'", n_null)

    # 8. Fill null refund_status
    if "refund_status" in df.columns:
        n_null = df["refund_status"].isna().sum()
        if n_null:
            df["refund_status"] = df["refund_status"].fillna("Unknown")
            logger.info("%d null refund_status values → 'Unknown'", n_null)

    logger.info(
        "Cancellations cleaning complete: %d raw → %d clean rows", n_raw, len(df)
    )
    _write_interim(df, "cancellations_clean.csv")
    return df


def clean_seasonal_pricing(
    df: pd.DataFrame,
    bookings_clean: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Clean the raw seasonal pricing DataFrame and write to data/interim/seasonal_pricing_clean.csv.

    Steps (in order):
    1. Strip whitespace from column names.
    2. Drop exact duplicate rows — a few duplicate dates were found (Manuel Day 2).
    3. Standardise ``date`` column to datetime64.
    4. Drop rows where date is NaT.
    5. If bookings_clean is provided, log whether the pricing date range fully
       covers the bookings check_in_date range (warn if gaps exist).
    6. Convert base_rate to numeric; flag and retain nulls.
    7. Fill null demand_tier with 'Unknown'.

    Args:
        df: Raw seasonal pricing DataFrame from ``ingest.ingest_seasonal_pricing()``.
        bookings_clean: Optional cleaned bookings used for date-range alignment check.

    Returns:
        Cleaned DataFrame. Also written to data/interim/seasonal_pricing_clean.csv.
    """
    logger.info("--- Cleaning seasonal_pricing ---")
    n_raw = len(df)

    # 1. Strip column names
    df.columns = df.columns.str.strip()

    # 2. Drop exact duplicate rows — safe per Manuel Day 2 profiling
    n_before = len(df)
    df = df.drop_duplicates()
    n_exact = n_before - len(df)
    if n_exact:
        logger.info(
            "Dropped %d exact duplicate rows (confirmed safe — Manuel Day 2 profiling)",
            n_exact,
        )

    # 3. Standardise date column
    if "date" in df.columns:
        df["date"] = _parse_dates(df["date"], "date")

    # 4. Drop rows with null date
    n_before = len(df)
    df = df.dropna(subset=["date"])
    n_dropped = n_before - len(df)
    if n_dropped:
        logger.warning("Dropped %d rows with null date", n_dropped)

    # 5. Date range alignment check against bookings
    if bookings_clean is not None and "check_in_date" in bookings_clean.columns:
        booking_min = bookings_clean["check_in_date"].min()
        booking_max = bookings_clean["check_in_date"].max()
        pricing_min = df["date"].min()
        pricing_max = df["date"].max()

        logger.info(
            "Bookings check_in range: %s → %s", booking_min.date(), booking_max.date()
        )
        logger.info(
            "Pricing date range:      %s → %s", pricing_min.date(), pricing_max.date()
        )

        if pricing_min > booking_min:
            logger.warning(
                "Pricing data starts %s after earliest booking check_in (%s) "
                "— some bookings will have null season_tag after join",
                pricing_min.date(), booking_min.date(),
            )
        if pricing_max < booking_max:
            logger.warning(
                "Pricing data ends %s before latest booking check_in (%s) "
                "— some bookings will have null season_tag after join",
                pricing_max.date(), booking_max.date(),
            )

    # 6. Convert base_rate to numeric; keep NaN visible (don't silently drop)
    if "base_rate" in df.columns:
        df["base_rate"] = pd.to_numeric(df["base_rate"], errors="coerce")
        n_null = df["base_rate"].isna().sum()
        if n_null:
            logger.warning("%d null base_rate values retained", n_null)

    # 7. Fill null demand_tier with 'Unknown'
    if "demand_tier" in df.columns:
        n_null = df["demand_tier"].isna().sum()
        if n_null:
            df["demand_tier"] = df["demand_tier"].fillna("Unknown")
            logger.info("%d null demand_tier values → 'Unknown'", n_null)

    logger.info(
        "Seasonal pricing cleaning complete: %d raw → %d clean rows", n_raw, len(df)
    )
    _write_interim(df, "seasonal_pricing_clean.csv")
    return df


# ===========================================================================
# Script entry point — python -m src.clean
# ===========================================================================
if __name__ == "__main__":
    logger.info("=== Cleaning pipeline — reading from data/raw/ ===")
    try:
        raw_bookings = ingest_bookings()
        raw_cancellations = ingest_cancellations()
        raw_pricing = ingest_seasonal_pricing()
    except FileNotFoundError as exc:
        logger.error("Cannot run cleaning: %s", exc)
        logger.error("Place the raw CSV files in data/raw/ and try again.")
        sys.exit(1)

    bookings_clean = clean_bookings(raw_bookings)
    cancellations_clean = clean_cancellations(raw_cancellations, bookings_clean)
    clean_seasonal_pricing(raw_pricing, bookings_clean)

    logger.info(
        "=== Cleaning complete: bookings=%d | cancellations=%d rows ===",
        len(bookings_clean), len(cancellations_clean),
    )
