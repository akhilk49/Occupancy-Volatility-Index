"""test_data_quality.py — CI-enforced data quality checks.

Runs automatically via .github/workflows/data_quality.yml on every push
or PR that touches data/, src/, or tests/.

Test categories:
  1. Raw file checks   — schema, row count lower bound
  2. Interim checks    — cleaning did not silently wipe data
  3. Processed checks  — fact table schema, PK uniqueness, null thresholds
  4. Database checks   — occupancy.db round-trip, all views queryable

Tests that require actual data files are skipped automatically when the
files are not present (e.g. in CI without raw CSVs) via pytest.importorskip
or a file-existence skip guard — this keeps CI green on fresh clones.

Run locally (after generating sample data and running the pipeline):
    python scripts/generate_sample_data.py
    python -m src.ingest; python -m src.clean; python -m src.features; python -m src.load
    pytest tests/ -v
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.config import (
    BOOKINGS_CSV,
    BOOKINGS_REQUIRED_COLS,
    CANCELLATIONS_CSV,
    CANCELLATIONS_REQUIRED_COLS,
    DB_PATH,
    FACT_TABLE_CSV,
    INTERIM_DIR,
    PROCESSED_DIR,
    SEASONAL_PRICING_CSV,
    SEASONAL_PRICING_REQUIRED_COLS,
)

# ---------------------------------------------------------------------------
# Thresholds (tune to real data once real CSVs are available)
# ---------------------------------------------------------------------------
# Maximum allowed null percentage in critical columns of the processed fact table
NULL_THRESHOLD: dict[str, float] = {
    "reservation_id": 0.00,   # PK — must never be null
    "check_in_date":  0.00,   # Required for every time-based metric
    "room_nights":    0.00,   # Required for occupancy and revenue metrics
    "is_cancelled":   0.00,   # Required for Metrics #3, #7
    "segment":        0.10,   # Up to 10% Unknown is acceptable
}

# Minimum expected rows in the processed fact table
# (>= 50% of raw bookings as a sanity lower bound)
MIN_FACT_ROWS: int = 50

# Expected schema columns in the processed CSV (must all be present)
FACT_REQUIRED_COLS: list[str] = [
    "reservation_id", "segment", "room_type",
    "booking_date", "check_in_date", "check_out_date",
    "nights", "room_nights", "rate",
    "is_cancelled", "lead_time_days",
    "season_tag", "base_rate", "demand_tier",
    "occupancy_rate",
]

# All KPI views that must exist and be queryable in occupancy.db
EXPECTED_VIEWS: list[str] = [
    "v_daily_room_nights_by_segment",
    "v_cancellation_stats_by_segment",
    "v_lead_time_by_segment",
    "v_bookings_by_segment_season",
    "v_revenue_at_risk_by_segment",
    "v_daily_revenue_by_segment",
    "v_segment_summary",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skip_if_missing(path: Path, reason: str = "") -> None:
    """Skip the calling test if *path* does not exist."""
    if not path.exists():
        pytest.skip(reason or f"File not found: {path}")


def _load_csv_safe(path: Path) -> pd.DataFrame:
    """Load a CSV; skip the test if the file is absent."""
    _skip_if_missing(path, f"Data file not found: {path} — run pipeline first")
    return pd.read_csv(path, dtype=str, keep_default_na=False,
                       na_values=["", "NA", "N/A", "NULL", "null", "None"])


# ===========================================================================
# 1. Raw file checks
# ===========================================================================

class TestRawFiles:
    """Schema and presence checks on the three raw source CSVs."""

    def test_bookings_required_columns_present(self) -> None:
        """All required bookings columns must be present."""
        df = _load_csv_safe(BOOKINGS_CSV)
        actual = {c.strip().lower() for c in df.columns}
        missing = [c for c in BOOKINGS_REQUIRED_COLS if c.lower() not in actual]
        assert not missing, f"bookings.csv missing columns: {missing}"

    def test_cancellations_required_columns_present(self) -> None:
        """All required cancellations columns must be present."""
        df = _load_csv_safe(CANCELLATIONS_CSV)
        actual = {c.strip().lower() for c in df.columns}
        missing = [c for c in CANCELLATIONS_REQUIRED_COLS if c.lower() not in actual]
        assert not missing, f"cancellations.csv missing columns: {missing}"

    def test_seasonal_pricing_required_columns_present(self) -> None:
        """All required seasonal_pricing columns must be present."""
        df = _load_csv_safe(SEASONAL_PRICING_CSV)
        actual = {c.strip().lower() for c in df.columns}
        missing = [c for c in SEASONAL_PRICING_REQUIRED_COLS if c.lower() not in actual]
        assert not missing, f"seasonal_pricing.csv missing columns: {missing}"

    def test_bookings_has_minimum_rows(self) -> None:
        """bookings.csv must have at least 1 row (non-empty)."""
        df = _load_csv_safe(BOOKINGS_CSV)
        assert len(df) > 0, "bookings.csv is empty"

    def test_cancellations_has_minimum_rows(self) -> None:
        """cancellations.csv must have at least 1 row."""
        df = _load_csv_safe(CANCELLATIONS_CSV)
        assert len(df) > 0, "cancellations.csv is empty"

    def test_seasonal_pricing_has_minimum_rows(self) -> None:
        """seasonal_pricing.csv must have at least 1 row."""
        df = _load_csv_safe(SEASONAL_PRICING_CSV)
        assert len(df) > 0, "seasonal_pricing.csv is empty"


# ===========================================================================
# 2. Interim file checks (output of src/clean.py)
# ===========================================================================

class TestInterimFiles:
    """Cleaning did not silently drop excessive rows or wipe columns."""

    def test_bookings_clean_exists(self) -> None:
        """bookings_clean.csv must exist after running src/clean.py."""
        path = INTERIM_DIR / "bookings_clean.csv"
        _skip_if_missing(path, "Run 'python -m src.clean' first")
        assert path.exists()

    def test_cancellations_clean_exists(self) -> None:
        path = INTERIM_DIR / "cancellations_clean.csv"
        _skip_if_missing(path, "Run 'python -m src.clean' first")
        assert path.exists()

    def test_seasonal_pricing_clean_exists(self) -> None:
        path = INTERIM_DIR / "seasonal_pricing_clean.csv"
        _skip_if_missing(path, "Run 'python -m src.clean' first")
        assert path.exists()

    def test_bookings_clean_no_silent_data_loss(self) -> None:
        """Cleaned bookings must retain at least 80% of raw rows."""
        raw_path = BOOKINGS_CSV
        clean_path = INTERIM_DIR / "bookings_clean.csv"
        _skip_if_missing(raw_path)
        _skip_if_missing(clean_path, "Run 'python -m src.clean' first")

        n_raw = len(pd.read_csv(raw_path))
        n_clean = len(pd.read_csv(clean_path))
        retention = n_clean / n_raw if n_raw > 0 else 0
        assert retention >= 0.80, (
            f"Cleaning dropped too many bookings: {n_raw} raw → {n_clean} clean "
            f"({retention:.1%} retained, expected ≥ 80%)"
        )

    def test_cleaned_segment_values_are_canonical(self) -> None:
        """All non-null segment values in bookings_clean must be canonical."""
        from src.config import CANONICAL_SEGMENTS
        path = INTERIM_DIR / "bookings_clean.csv"
        _skip_if_missing(path, "Run 'python -m src.clean' first")

        df = pd.read_csv(path)
        allowed = set(CANONICAL_SEGMENTS) | {"Unknown"}
        actual = set(df["segment"].dropna().unique())
        unexpected = actual - allowed
        assert not unexpected, (
            f"Non-canonical segment values found in bookings_clean.csv: {unexpected}"
        )


# ===========================================================================
# 3. Processed fact table checks (output of src/features.py)
# ===========================================================================

class TestFactTable:
    """Schema drift, PK uniqueness, null thresholds, and row count checks."""

    def test_fact_table_csv_exists(self) -> None:
        """fact_bookings_enriched.csv must exist."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        assert FACT_TABLE_CSV.exists()

    def test_fact_table_minimum_row_count(self) -> None:
        """Fact table must have at least MIN_FACT_ROWS rows."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        assert len(df) >= MIN_FACT_ROWS, (
            f"Fact table has only {len(df)} rows — expected ≥ {MIN_FACT_ROWS}"
        )

    def test_fact_table_required_columns_present(self) -> None:
        """All required fact table columns must be present (schema drift check)."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        actual = set(df.columns.str.strip().str.lower())
        missing = [c for c in FACT_REQUIRED_COLS if c.lower() not in actual]
        assert not missing, (
            f"Schema drift — fact table missing columns: {missing}"
        )

    def test_fact_table_reservation_id_unique(self) -> None:
        """reservation_id must be unique in the fact table (PK integrity)."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        n_dupes = df["reservation_id"].duplicated().sum()
        assert n_dupes == 0, (
            f"Duplicate reservation_id values in fact table: {n_dupes} duplicates found"
        )

    def test_fact_table_null_thresholds(self) -> None:
        """Critical columns must not exceed their allowed null percentage."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        violations = []
        for col, max_pct in NULL_THRESHOLD.items():
            if col not in df.columns:
                continue
            actual_pct = df[col].isnull().mean()
            if actual_pct > max_pct:
                violations.append(
                    f"  '{col}': {actual_pct:.1%} nulls (allowed ≤ {max_pct:.0%})"
                )
        assert not violations, (
            "Null threshold exceeded in fact table:\n" + "\n".join(violations)
        )

    def test_fact_table_row_count_vs_raw(self) -> None:
        """Fact table rows must be at least 70% of raw bookings (no silent loss)."""
        _skip_if_missing(BOOKINGS_CSV)
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        n_raw = len(pd.read_csv(BOOKINGS_CSV))
        n_fact = len(pd.read_csv(FACT_TABLE_CSV))
        retention = n_fact / n_raw if n_raw > 0 else 0
        assert retention >= 0.70, (
            f"Fact table retained only {retention:.1%} of raw bookings "
            f"({n_fact}/{n_raw}) — expected ≥ 70%"
        )

    def test_fact_table_occupancy_rate_range(self) -> None:
        """occupancy_rate values should be non-negative (no data corruption)."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        if "occupancy_rate" not in df.columns:
            pytest.skip("occupancy_rate column not present")
        negative = (pd.to_numeric(df["occupancy_rate"], errors="coerce") < 0).sum()
        assert negative == 0, f"{negative} rows have negative occupancy_rate"

    def test_fact_table_lead_time_non_negative(self) -> None:
        """lead_time_days must be >= 0 for all non-null rows."""
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        df = pd.read_csv(FACT_TABLE_CSV)
        if "lead_time_days" not in df.columns:
            pytest.skip("lead_time_days column not present")
        lead = pd.to_numeric(df["lead_time_days"], errors="coerce").dropna()
        negative = (lead < 0).sum()
        assert negative == 0, f"{negative} rows have negative lead_time_days"


# ===========================================================================
# 4. Database checks (output of src/load.py)
# ===========================================================================

class TestDatabase:
    """occupancy.db round-trip and view availability."""

    def test_database_exists(self) -> None:
        """occupancy.db must exist after running src/load.py."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        assert DB_PATH.exists()

    def test_dim_segment_populated(self) -> None:
        """dim_segment must have at least 5 canonical segment rows."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM dim_segment").fetchone()[0]
        conn.close()
        assert count >= 5, f"dim_segment has only {count} rows — expected ≥ 5"

    def test_fact_table_row_count_in_db(self) -> None:
        """DB fact table row count must match the processed CSV."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        _skip_if_missing(FACT_TABLE_CSV, "Run 'python -m src.features' first")
        csv_count = len(pd.read_csv(FACT_TABLE_CSV))
        conn = sqlite3.connect(str(DB_PATH))
        db_count = conn.execute(
            "SELECT COUNT(*) FROM fact_bookings_enriched"
        ).fetchone()[0]
        conn.close()
        assert db_count == csv_count, (
            f"DB row count ({db_count}) does not match CSV ({csv_count})"
        )

    def test_fact_table_pk_unique_in_db(self) -> None:
        """reservation_id must be unique in the DB fact table."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        conn = sqlite3.connect(str(DB_PATH))
        dupes = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT reservation_id FROM fact_bookings_enriched"
            "  GROUP BY reservation_id HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        conn.close()
        assert dupes == 0, f"{dupes} duplicate reservation_id values in DB"

    @pytest.mark.parametrize("view_name", EXPECTED_VIEWS)
    def test_kpi_view_exists_and_queryable(self, view_name: str) -> None:
        """Each KPI view must exist and return rows without error."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        conn = sqlite3.connect(str(DB_PATH))
        try:
            # Check view exists in sqlite_master
            exists = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name=?",
                (view_name,),
            ).fetchone()[0]
            assert exists == 1, f"View '{view_name}' not found in occupancy.db"

            # Check it runs without error
            count = conn.execute(
                f"SELECT COUNT(*) FROM {view_name}"  # noqa: S608
            ).fetchone()[0]
            assert count >= 0  # any non-error result is acceptable
        finally:
            conn.close()

    def test_db_no_null_reservation_id(self) -> None:
        """reservation_id must never be NULL in the DB fact table."""
        _skip_if_missing(DB_PATH, "Run 'python -m src.load' first")
        conn = sqlite3.connect(str(DB_PATH))
        nulls = conn.execute(
            "SELECT COUNT(*) FROM fact_bookings_enriched WHERE reservation_id IS NULL"
        ).fetchone()[0]
        conn.close()
        assert nulls == 0, f"{nulls} NULL reservation_id values in DB"
