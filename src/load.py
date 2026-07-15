"""load.py — Load the processed fact table into SQLite (occupancy.db).

Stub file. Implementation in Day 11.
"""

from __future__ import annotations

import pandas as pd


def load_to_sqlite(df: pd.DataFrame, db_path: str) -> None:
    """Create ``dim_segment`` and ``fact_bookings_enriched`` in SQLite from *df*.

    Uses ``sql/schema.sql`` as the source of truth for DDL.
    Existing tables are replaced on each run (idempotent).

    Args:
        df: Fully enriched fact DataFrame from ``features.join_fact_table()``.
        db_path: Absolute path to the SQLite database file.
    """
    raise NotImplementedError("Implement in Day 11")
