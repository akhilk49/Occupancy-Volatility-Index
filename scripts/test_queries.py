"""Verify all 8 metric query functions return non-empty DataFrames."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DB_PATH
from src.queries import (
    get_occupancy_by_segment_day,
    get_occupancy_volatility_cov,
    get_cancellation_rate_by_segment,
    get_avg_lead_time_by_segment,
    get_seasonal_concentration,
    get_segment_volatility_contribution,
    get_revenue_at_risk,
    get_revenue_volatility_index,
    get_segment_summary,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def check(name, df, required_cols=None):
    ok = not df.empty
    if required_cols:
        ok = ok and all(c in df.columns for c in required_cols)
    print(f"  [{PASS if ok else FAIL}] {name}  ({len(df)} rows, cols: {list(df.columns)})")
    if not ok:
        print(f"         MISSING: {[c for c in (required_cols or []) if c not in df.columns]}")
    return ok

print(f"\nDB: {DB_PATH}\n")
all_ok = True

df = get_occupancy_by_segment_day(DB_PATH)
all_ok &= check("M1  get_occupancy_by_segment_day", df, ["segment_name","date","booked_room_nights","occupancy_rate"])
print(df.head(3).to_string(index=False))

df = get_occupancy_volatility_cov(DB_PATH)
all_ok &= check("M2  get_occupancy_volatility_cov", df, ["segment_name","cov"])
print(df.to_string(index=False))

df = get_cancellation_rate_by_segment(DB_PATH)
all_ok &= check("M3  get_cancellation_rate_by_segment", df, ["segment_name","cancellation_rate"])
print(df.to_string(index=False))

df = get_avg_lead_time_by_segment(DB_PATH)
all_ok &= check("M4  get_avg_lead_time_by_segment", df, ["segment_name","avg_lead_time_days"])
print(df.to_string(index=False))

df = get_seasonal_concentration(DB_PATH)
all_ok &= check("M5  get_seasonal_concentration", df, ["segment_name","seasonal_concentration_index"])
print(df.to_string(index=False))

df = get_segment_volatility_contribution(DB_PATH)
all_ok &= check("M6  get_segment_volatility_contribution", df, ["segment_name","volatility_contribution"])
print(df.to_string(index=False))

df = get_revenue_at_risk(DB_PATH)
all_ok &= check("M7  get_revenue_at_risk", df, ["segment_name","revenue_at_risk"])
print(df.to_string(index=False))

df = get_revenue_volatility_index(DB_PATH)
all_ok &= check("M8  get_revenue_volatility_index", df, ["segment_name","rvi"])
print(df.to_string(index=False))

df = get_segment_summary(DB_PATH)
all_ok &= check("ALL get_segment_summary", df, [
    "segment_name","total_bookings","cancellation_rate","avg_lead_time_days",
    "revenue_at_risk","cov","volatility_contribution","rvi","seasonal_concentration_index"
])
print(df.to_string(index=False))

print(f"\n{'All queries PASSED' if all_ok else 'SOME QUERIES FAILED'}")
