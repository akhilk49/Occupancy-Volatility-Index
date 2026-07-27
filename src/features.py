"""features.py — Join logic and feature engineering.

Builds ``fact_bookings_enriched``: one row per reservation with all
columns required by the 8 metrics in SPEC Section 5.

Pipeline:
    cleaned bookings + cancellations + seasonal_pricing
        → join_fact_table()   # LEFT JOIN + season tag JOIN
        → add_cancel_flag()   # is_cancelled boolean
        → add_lead_time()     # lead_time_days integer
        → add_occupancy_rate() # occupancy_rate float per check_in_date
        → write to data/processed/fact_bookings_enriched.csv

Usage:
    from src.features import build_fact_table
    fact = build_fact_table(bookings_clean, cancellations_clean, pricing_clean)

Or run as a script (requires cleaned CSVs in data/interim/):
    python -m src.features
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from src.config import (
    ASSUMED_TOTAL_ROOMS,
    FACT_TABLE_CSV,
    INTERIM_DIR,
    PROCESSED_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [features] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_interim(filename: str) -> pd.DataFrame:
    """Read a cleaned CSV from data/interim/.

    Args:
        filename: Basename of the file (e.g. ``"bookings_clean.csv"``).

    Returns:
        DataFrame with date columns parsed to datetime64.

    Raises:
        FileNotFoundError: If the file does not exist in data/interim/.
    """
    path = INTERIM_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned file not found: {path}\n"
            "Run 'python -m src.clean' first to produce interim files."
        )
    df = pd.read_csv(path)
    # Re-parse date columns — they are stored as strings in CSV
    date_cols = [c for c in df.columns if "date" in c.lower() or c == "date"]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=False)
    return df


# ---------------------------------------------------------------------------
# Feature functions (each is independently testable)
# ---------------------------------------------------------------------------

def add_cancel_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean ``is_cancelled`` column.

    Derived from the LEFT JOIN with cancellations: a row has is_cancelled=True
    when ``cancellation_date`` is not null (i.e. a cancellation record was matched).

    Args:
        df: Fact table DataFrame after LEFT JOIN with cancellations.

    Returns:
        DataFrame with new boolean column ``is_cancelled``.
    """
    # cancellation_date is populated only for rows that matched a cancellation record
    df["is_cancelled"] = df["cancellation_date"].notna()
    n_cancelled = df["is_cancelled"].sum()
    logger.info(
        "is_cancelled: %d cancelled / %d total (%.1f%%)",
        n_cancelled, len(df), n_cancelled / len(df) * 100 if len(df) else 0,
    )
    return df


def add_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """Add integer ``lead_time_days`` column: check_in_date minus booking_date.

    Negative values (booking_date after check_in_date) are set to NaN and
    logged — they indicate data quality issues that were not caught in clean.py.

    Args:
        df: DataFrame with datetime64 columns ``check_in_date`` and ``booking_date``.

    Returns:
        DataFrame with new integer column ``lead_time_days``.
    """
    if "check_in_date" not in df.columns or "booking_date" not in df.columns:
        logger.warning(
            "Cannot compute lead_time_days — check_in_date or booking_date missing"
        )
        df["lead_time_days"] = pd.NA
        return df

    df["lead_time_days"] = (df["check_in_date"] - df["booking_date"]).dt.days

    # Negative lead time = booked after check-in — flag as invalid
    neg_mask = df["lead_time_days"] < 0
    n_neg = neg_mask.sum()
    if n_neg:
        logger.warning(
            "%d rows have negative lead_time_days (booking_date > check_in_date) → set to NaN",
            n_neg,
        )
        df.loc[neg_mask, "lead_time_days"] = pd.NA

    df["lead_time_days"] = df["lead_time_days"].astype("Int64")  # nullable integer
    logger.info(
        "lead_time_days: min=%s, max=%s, mean=%.1f, nulls=%d",
        df["lead_time_days"].min(),
        df["lead_time_days"].max(),
        df["lead_time_days"].mean(),
        df["lead_time_days"].isna().sum(),
    )
    return df


def add_occupancy_rate(
    df: pd.DataFrame,
    total_rooms_available: int | None = None,
) -> pd.DataFrame:
    """Add ``occupancy_rate`` per check_in_date: booked_room_nights / available_room_nights.

    Occupancy rate is computed at the *day* grain — each check_in_date gets the
    ratio of total booked room-nights (across all non-cancelled bookings that
    check in that day) divided by the total rooms available.

    Capacity source (in priority order):
    1. ``total_rooms_available`` argument if provided.
    2. ``ASSUMED_TOTAL_ROOMS`` from ``config.py`` (Decision D2, SPEC 11.3).

    Note: occupancy_rate > 1.0 is possible if ASSUMED_TOTAL_ROOMS underestimates
    real capacity. These values are retained and flagged, not capped.

    Args:
        df: Fact table DataFrame with ``room_nights``, ``is_cancelled``,
            and ``check_in_date`` columns.
        total_rooms_available: Override capacity constant; None uses config value.

    Returns:
        DataFrame with new float column ``occupancy_rate`` (per-reservation row,
        carrying the daily rate for that reservation's check_in_date).
    """
    capacity = total_rooms_available if total_rooms_available is not None else ASSUMED_TOTAL_ROOMS
    logger.info("Computing occupancy_rate with capacity = %d rooms", capacity)

    if "room_nights" not in df.columns or "is_cancelled" not in df.columns:
        logger.warning(
            "Cannot compute occupancy_rate — room_nights or is_cancelled column missing"
        )
        df["occupancy_rate"] = pd.NA
        return df

    # Daily booked room-nights = sum of room_nights for non-cancelled bookings per check_in_date
    active = df[~df["is_cancelled"]].copy()
    daily_booked = (
        active.groupby("check_in_date")["room_nights"]
        .sum()
        .rename("daily_booked_room_nights")
    )

    # Merge daily totals back to the full fact table (cancelled rows get the day's rate too
    # so the column is consistent — cancellation filter is applied in SQL/query layer)
    df = df.merge(daily_booked, on="check_in_date", how="left")
    df["occupancy_rate"] = df["daily_booked_room_nights"] / capacity
    df = df.drop(columns=["daily_booked_room_nights"])

    n_over = (df["occupancy_rate"] > 1.0).sum()
    if n_over:
        logger.warning(
            "%d rows have occupancy_rate > 1.0 — ASSUMED_TOTAL_ROOMS (%d) may be too low",
            n_over, capacity,
        )

    logger.info(
        "occupancy_rate: min=%.3f, max=%.3f, mean=%.3f",
        df["occupancy_rate"].min(),
        df["occupancy_rate"].max(),
        df["occupancy_rate"].mean(),
    )
    return df


def join_fact_table(
    bookings: pd.DataFrame,
    cancellations: pd.DataFrame,
    seasonal_pricing: pd.DataFrame,
) -> pd.DataFrame:
    """Build ``fact_bookings_enriched``: one row per reservation.

    Join sequence (SPEC Section 4, Decision D3):
    1. bookings LEFT JOIN cancellations ON reservation_id
       → all bookings retained; cancelled ones get cancellation columns populated
    2. result LEFT JOIN seasonal_pricing ON check_in_date = date
       → season tag classified by check_in_date only (Decision D3)
    3. add_cancel_flag() → is_cancelled boolean
    4. add_lead_time()   → lead_time_days integer
    5. add_occupancy_rate() → occupancy_rate float

    Row count validation: logs a warning if output rows ≠ input bookings rows
    (a silent drop indicates a join bug).

    Args:
        bookings: Cleaned bookings DataFrame (from clean.clean_bookings).
        cancellations: Cleaned cancellations DataFrame (from clean.clean_cancellations).
        seasonal_pricing: Cleaned seasonal pricing DataFrame (from clean.clean_seasonal_pricing).

    Returns:
        Enriched fact DataFrame. Also written to data/processed/fact_bookings_enriched.csv.
    """
    n_bookings = len(bookings)
    logger.info("--- Building fact_bookings_enriched ---")
    logger.info("Input: %d bookings, %d cancellations, %d pricing rows",
                n_bookings, len(cancellations), len(seasonal_pricing))

    # ------------------------------------------------------------------
    # Step 1: bookings LEFT JOIN cancellations ON reservation_id
    # Suffix _cancel distinguishes overlapping column names (e.g. if any)
    # ------------------------------------------------------------------
    cancel_cols = ["reservation_id", "cancellation_date", "reason", "refund_status"]
    cancel_subset = cancellations[[c for c in cancel_cols if c in cancellations.columns]].copy()
    # Rename non-key columns to avoid clashes
    cancel_subset = cancel_subset.rename(columns={
        "reason":        "cancellation_reason",
        "refund_status": "refund_status",
    })

    fact = bookings.merge(cancel_subset, on="reservation_id", how="left")

    if len(fact) != n_bookings:
        logger.warning(
            "Row count changed after cancellations join: %d → %d "
            "(possible duplicate reservation_id in cancellations — check clean.py output)",
            n_bookings, len(fact),
        )
    else:
        logger.info("Cancellations join: row count preserved (%d)", len(fact))

    # ------------------------------------------------------------------
    # Step 2: result LEFT JOIN seasonal_pricing ON check_in_date = date
    # Decision D3: classify booking by check_in_date only, not stay duration
    # ------------------------------------------------------------------
    pricing_cols = ["date", "season_tag", "base_rate", "demand_tier"]
    pricing_subset = seasonal_pricing[[c for c in pricing_cols if c in seasonal_pricing.columns]].copy()

    # Ensure check_in_date and pricing date are the same dtype for the merge
    if "check_in_date" in fact.columns:
        fact["check_in_date"] = pd.to_datetime(fact["check_in_date"], errors="coerce", format="mixed", dayfirst=False)
    if "date" in pricing_subset.columns:
        pricing_subset["date"] = pd.to_datetime(pricing_subset["date"], errors="coerce", format="mixed", dayfirst=False)

    fact = fact.merge(
        pricing_subset,
        left_on="check_in_date",
        right_on="date",
        how="left",
    )
    # Drop the redundant 'date' column from seasonal_pricing (same as check_in_date)
    fact = fact.drop(columns=["date"], errors="ignore")

    n_null_season = fact["season_tag"].isna().sum() if "season_tag" in fact.columns else 0
    if n_null_season:
        logger.warning(
            "%d rows have null season_tag after pricing join "
            "— check_in_date outside seasonal_pricing date range",
            n_null_season,
        )
    else:
        logger.info("Seasonal pricing join: all rows matched a season_tag")

    if len(fact) != n_bookings:
        logger.warning(
            "Row count changed after pricing join: %d → %d "
            "(possible duplicate dates in seasonal_pricing — check clean.py output)",
            n_bookings, len(fact),
        )

    # ------------------------------------------------------------------
    # Step 3: impute null rate from base_rate where possible
    # (Decision: rate nulls from bookings.csv imputed here after join)
    # ------------------------------------------------------------------
    if "rate" in fact.columns and "base_rate" in fact.columns:
        null_rate_mask = fact["rate"].isna()
        n_null_rate = null_rate_mask.sum()
        if n_null_rate:
            fact.loc[null_rate_mask, "rate"] = fact.loc[null_rate_mask, "base_rate"]
            still_null = fact["rate"].isna().sum()
            logger.info(
                "Imputed %d null rate values from base_rate; %d still null after imputation",
                n_null_rate - still_null, still_null,
            )

    # ------------------------------------------------------------------
    # Steps 4–6: derived feature columns
    # ------------------------------------------------------------------
    fact = add_cancel_flag(fact)
    fact = add_lead_time(fact)
    fact = add_occupancy_rate(fact)

    # ------------------------------------------------------------------
    # Final column ordering — matches schema.sql column order
    # ------------------------------------------------------------------
    ordered_cols = [
        "reservation_id", "segment", "room_type",
        "booking_date", "check_in_date", "check_out_date",
        "nights", "room_nights", "rate",
        "is_cancelled", "cancellation_date", "cancellation_reason", "refund_status",
        "lead_time_days", "season_tag", "base_rate", "demand_tier",
        "occupancy_rate",
    ]
    # Keep only columns that actually exist (graceful if a source file was missing a column)
    final_cols = [c for c in ordered_cols if c in fact.columns]
    # Append any extra columns not in the ordered list (don't silently drop them)
    extra_cols = [c for c in fact.columns if c not in final_cols]
    fact = fact[final_cols + extra_cols]

    logger.info(
        "fact_bookings_enriched: %d rows, %d columns — columns: %s",
        len(fact), len(fact.columns), list(fact.columns),
    )

    # ------------------------------------------------------------------
    # Write to data/processed/
    # ------------------------------------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fact.to_csv(FACT_TABLE_CSV, index=False)
    logger.info("Written → %s", FACT_TABLE_CSV)

    return fact


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def build_fact_table(
    bookings: pd.DataFrame,
    cancellations: pd.DataFrame,
    seasonal_pricing: pd.DataFrame,
) -> pd.DataFrame:
    """Alias for ``join_fact_table`` — single entry point for the pipeline runner.

    Args:
        bookings: Cleaned bookings DataFrame.
        cancellations: Cleaned cancellations DataFrame.
        seasonal_pricing: Cleaned seasonal pricing DataFrame.

    Returns:
        Fully enriched fact DataFrame written to data/processed/.
    """
    return join_fact_table(bookings, cancellations, seasonal_pricing)


# ---------------------------------------------------------------------------
# Script entry point — python -m src.features
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=== Feature engineering — reading from data/interim/ ===")
    try:
        bookings = _load_interim("bookings_clean.csv")
        cancellations = _load_interim("cancellations_clean.csv")
        seasonal_pricing = _load_interim("seasonal_pricing_clean.csv")
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    fact = build_fact_table(bookings, cancellations, seasonal_pricing)
    logger.info(
        "=== Done: fact_bookings_enriched has %d rows and %d columns ===",
        len(fact), len(fact.columns),
    )
