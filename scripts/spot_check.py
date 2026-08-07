import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DB_PATH
from src.queries import get_occupancy_volatility_cov, get_segment_volatility_contribution

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

print("=== Segment Summary ===")
rows = conn.execute("SELECT * FROM v_segment_summary ORDER BY total_bookings DESC").fetchall()
for r in rows:
    rar = r["revenue_at_risk"] or 0
    print(
        f"  {r['segment_name']:<16} "
        f"bookings={r['total_bookings']:>3}  "
        f"cancel={r['cancellation_rate']:.1%}  "
        f"lead={r['avg_lead_time_days']:.0f}d  "
        f"rev_at_risk=${rar:,.0f}"
    )

print("\n=== Revenue at Risk ===")
rows = conn.execute("SELECT * FROM v_revenue_at_risk_by_segment ORDER BY revenue_at_risk DESC").fetchall()
for r in rows:
    print(f"  {r['segment_name']:<16} ${r['revenue_at_risk']:,.2f}")

cov = get_occupancy_volatility_cov(DB_PATH)
print("\n=== CoV (Metric #2) ===")
print(cov.to_string(index=False))

contrib = get_segment_volatility_contribution(DB_PATH)
print("\n=== Volatility Contribution (Metric #6) ===")
print(contrib.to_string(index=False))

conn.close()
