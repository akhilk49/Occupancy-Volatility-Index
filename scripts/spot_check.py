import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

print("=== Segment Summary ===")
rows = conn.execute("SELECT * FROM v_segment_summary ORDER BY total_bookings DESC").fetchall()
for r in rows:
    print(
        f"  {r['segment_name']:<16} "
        f"bookings={r['total_bookings']:>3}  "
        f"cancel={r['cancellation_rate']:.1%}  "
        f"lead={r['avg_lead_time_days']:.0f}d  "
        f"rev_at_risk=${r['revenue_at_risk']:,.0f}"
    )

print("\n=== Revenue at Risk ===")
rows = conn.execute("SELECT * FROM v_revenue_at_risk_by_segment ORDER BY revenue_at_risk DESC").fetchall()
for r in rows:
    print(f"  {r['segment_name']:<16} ${r['revenue_at_risk']:,.2f}")

print("\n=== Seasonal Booking Concentration ===")
rows = conn.execute(
    "SELECT segment_name, season_tag, booking_count "
    "FROM v_bookings_by_segment_season ORDER BY segment_name, booking_count DESC"
).fetchall()
for r in rows:
    print(f"  {r['segment_name']:<16} {r['season_tag']:<8} count={r['booking_count']:>3}")

conn.close()
