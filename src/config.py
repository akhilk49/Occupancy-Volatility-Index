"""Central path + constant configuration for the pipeline.

All modules import paths from here — no hardcoded file paths anywhere else.
"""

from pathlib import Path

# Repository root
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# Data directories
RAW_DIR: Path = ROOT_DIR / "data" / "raw"
INTERIM_DIR: Path = ROOT_DIR / "data" / "interim"
PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"

# Raw source files
BOOKINGS_CSV: Path = RAW_DIR / "bookings.csv"
CANCELLATIONS_CSV: Path = RAW_DIR / "cancellations.csv"
SEASONAL_PRICING_CSV: Path = RAW_DIR / "seasonal_pricing.csv"

# Processed outputs
FACT_TABLE_CSV: Path = PROCESSED_DIR / "fact_bookings_enriched.csv"
DB_PATH: Path = PROCESSED_DIR / "occupancy.db"

# Expected schema contracts (source of truth from SPEC Section 4)
BOOKINGS_REQUIRED_COLS: list[str] = [
    "reservation_id",
    "segment",
    "room_type",
    "booking_date",
    "check_in_date",
    "check_out_date",
    "nights",
    "rate",
]

CANCELLATIONS_REQUIRED_COLS: list[str] = [
    "reservation_id",
    "cancellation_date",
    "reason",
    "refund_status",
]

SEASONAL_PRICING_REQUIRED_COLS: list[str] = [
    "date",
    "season_tag",
    "base_rate",
    "demand_tier",
]
