"""load.py — Load the processed fact table into SQLite (occupancy.db).

Reads data/processed/fact_bookings_enriched.csv, executes sql/schema.sql
DDL, populates dim_segment and fact_bookings_enriched tables, and verifies
the round-trip row count.

Every run is idempotent: existing tables and views are dropped/recreated so
the DB always reflects the latest processed data.

Usage:
    from src.load import load_to_sqlite
    load_to_sqlite(fact_df, str(DB_PATH))

Or run as a script:
    python -m src.load
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from src.config import (
    CANONICAL_SEGMENTS,
    DB_PATH,
    FACT_TABLE_CSV,
    PROCESSED_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [load] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Path to the DDL file — schema.sql is the single source of truth
SCHEMA_SQL: Path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign key enforcement enabled.

    Args:
        db_path: Path to the SQLite database file. Created if absent.

    Returns:
        Open sqlite3.Connection.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    # Use WAL journal for better concurrent read performance
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _execute_schema(conn: sqlite3.Connection) -> None:
    """Execute sql/schema.sql DDL against *conn*.

    The schema uses DROP VIEW IF EXISTS + CREATE VIEW (not IF NOT EXISTS) for
    views, so views are always refreshed to pick up any definition changes.
    Tables use CREATE TABLE IF NOT EXISTS so existing data is preserved until
    explicitly replaced by the INSERT step.

    Args:
        conn: Open SQLite connection.
    """
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()
    logger.info("Schema applied from %s", SCHEMA_SQL.name)


def _build_dim_segment(conn: sqlite3.Connection) -> dict[str, int]:
    """Populate dim_segment with canonical segment values and return name→id map.

    Inserts canonical segments + 'Unknown' using INSERT OR IGNORE so existing
    rows are never overwritten (idempotent). Returns the full name→id mapping
    for use when inserting fact rows.

    Args:
        conn: Open SQLite connection with schema already applied.

    Returns:
        Dict mapping segment_name → segment_id.
    """
    all_segments = CANONICAL_SEGMENTS + ["Unknown"]
    conn.executemany(
        "INSERT OR IGNORE INTO dim_segment (segment_name) VALUES (?)",
        [(s,) for s in all_segments],
    )
    conn.commit()

    rows = conn.execute("SELECT segment_id, segment_name FROM dim_segment").fetchall()
    segment_map = {name: sid for sid, name in rows}
    logger.info("dim_segment populated: %d segments — %s", len(segment_map), sorted(segment_map))
    return segment_map


def _prepare_fact_df(
    df: pd.DataFrame,
    segment_map: dict[str, int],
) -> pd.DataFrame:
    """Map segment names to IDs and ensure column types match the schema.

    Args:
        df: Enriched fact DataFrame from features.py.
        segment_map: segment_name → segment_id from dim_segment.

    Returns:
        DataFrame ready for INSERT into fact_bookings_enriched.
    """
    out = df.copy()

    # Map segment name → segment_id; unmapped → Unknown's id
    unknown_id = segment_map.get("Unknown", 0)
    out["segment_id"] = out["segment"].map(segment_map).fillna(unknown_id).astype(int)

    # Coerce date columns to string (ISO 8601) — SQLite stores DATE as TEXT
    date_cols = ["booking_date", "check_in_date", "check_out_date", "cancellation_date"]
    for col in date_cols:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
            # pd.NaT → "NaT" string — replace with None for SQL NULL
            out[col] = out[col].where(out[col] != "NaT", other=None)

    # Coerce boolean is_cancelled to integer 0/1 (SQLite has no native BOOL)
    if "is_cancelled" in out.columns:
        out["is_cancelled"] = out["is_cancelled"].astype(int)

    # Coerce numeric columns
    for col in ["nights", "room_nights", "rate", "base_rate", "lead_time_days"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def load_to_sqlite(df: pd.DataFrame, db_path: str | Path = DB_PATH) -> None:
    """Load *df* into the SQLite database at *db_path*.

    Steps:
    1. Apply schema DDL (sql/schema.sql) — creates tables, indexes, views.
    2. Populate dim_segment with canonical values.
    3. Clear and reload fact_bookings_enriched (full replace on each run).
    4. Verify round-trip: row count in DB matches input DataFrame.

    The operation is idempotent — running it twice produces the same result.

    Args:
        df: Fully enriched fact DataFrame from ``features.build_fact_table()``.
        db_path: Path to the SQLite database file. Defaults to ``config.DB_PATH``.

    Raises:
        RuntimeError: If the post-load row count doesn't match the input.
    """
    db_path = Path(db_path)
    logger.info("Loading %d rows into %s", len(df), db_path)

    conn = _get_connection(db_path)
    try:
        # Step 1: apply schema
        _execute_schema(conn)

        # Step 2: populate dim_segment
        segment_map = _build_dim_segment(conn)

        # Step 3: clear fact table and reload (full replace — pipeline is batch/idempotent)
        conn.execute("DELETE FROM fact_bookings_enriched")
        conn.commit()
        logger.info("Cleared existing fact_bookings_enriched rows")

        fact_df = _prepare_fact_df(df, segment_map)

        # Select only columns that exist in the schema
        schema_cols = [
            "reservation_id", "segment_id", "room_type",
            "booking_date", "check_in_date", "check_out_date",
            "nights", "room_nights", "rate",
            "is_cancelled", "cancellation_date", "cancellation_reason", "refund_status",
            "lead_time_days", "season_tag", "base_rate", "demand_tier",
        ]
        insert_cols = [c for c in schema_cols if c in fact_df.columns]
        fact_df[insert_cols].to_sql(
            "fact_bookings_enriched",
            conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )
        conn.commit()

        # Step 4: verify row count
        db_count = conn.execute(
            "SELECT COUNT(*) FROM fact_bookings_enriched"
        ).fetchone()[0]

        if db_count != len(df):
            raise RuntimeError(
                f"Row count mismatch after load: inserted {len(df)}, "
                f"found {db_count} in DB"
            )

        logger.info(
            "Load complete: %d rows in fact_bookings_enriched | DB: %s",
            db_count, db_path,
        )

        # Log view availability
        views = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        logger.info("Views available: %s", [v[0] for v in views])

    finally:
        conn.close()


def verify_db(db_path: str | Path = DB_PATH) -> None:
    """Quick sanity check: log row counts for tables and spot-check each view.

    Args:
        db_path: Path to the SQLite database to verify.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return

    conn = sqlite3.connect(str(db_path))
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (tbl,) in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]  # noqa: S608
            logger.info("  Table %-35s %d rows", tbl, count)

        views = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        for (view,) in views:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]  # noqa: S608
                logger.info("  View  %-35s %d rows", view, count)
            except sqlite3.OperationalError as exc:
                logger.warning("  View  %-35s ERROR: %s", view, exc)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Script entry point — python -m src.load
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=== Loading pipeline — reading from data/processed/ ===")

    fact_path = FACT_TABLE_CSV
    if not fact_path.exists():
        logger.error(
            "Fact table CSV not found: %s\n"
            "Run 'python -m src.features' first.",
            fact_path,
        )
        sys.exit(1)

    fact_df = pd.read_csv(fact_path)
    logger.info("Read %d rows from %s", len(fact_df), fact_path)

    load_to_sqlite(fact_df, DB_PATH)
    verify_db(DB_PATH)
    logger.info("=== Load complete: %s ===", DB_PATH)
