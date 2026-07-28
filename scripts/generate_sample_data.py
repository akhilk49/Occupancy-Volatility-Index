"""generate_sample_data.py — Generate realistic sample CSVs for pipeline demo.

Intentionally introduces the data quality issues documented in
docs/data_quality_notes.md so the pipeline's cleaning decisions are visible
in the logs during a presentation.

Issues planted:
  bookings.csv
    - Mixed date formats (ISO, DD/MM/YYYY, MM-DD-YYYY)
    - Exact duplicate rows
    - Duplicate reservation_id with differing rate (non-exact dupe)
    - Null segment values
    - Null rate values
    - Segment label variants (TA, corp, DIRECT, etc.)
    - One logically invalid stay (check_out <= check_in)

  cancellations.csv
    - Duplicate cancellation record for one reservation_id
    - Mixed date format on one row (MM/DD/YYYY)
    - Null reason (~15%)

  seasonal_pricing.csv
    - Exact duplicate rows for two dates

Run from repo root:
    python scripts/generate_sample_data.py
"""

import csv
import random
from pathlib import Path

random.seed(42)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iso(y, m, d):
    return f"{y}-{m:02d}-{d:02d}"

def dmy(y, m, d):
    """DD/MM/YYYY format — alternate that clean.py must handle."""
    return f"{d:02d}/{m:02d}/{y}"

def mdy(y, m, d):
    """MM-DD-YYYY format — another variant."""
    return f"{m:02d}-{d:02d}-{y}"


# ---------------------------------------------------------------------------
# bookings.csv  (200 rows)
# ---------------------------------------------------------------------------

SEGMENTS_CLEAN = ["Travel Agency", "Direct", "Corporate", "Group", "Walk-in"]
# Raw variants that normalise_segments() must map
SEGMENT_VARIANTS = {
    "Travel Agency": ["Travel Agency", "TA", "travel agency", "T/A"],
    "Direct":        ["Direct", "DIRECT", "direct booking"],
    "Corporate":     ["Corporate", "corp", "CORPORATE"],
    "Group":         ["Group", "GROUP", "grp"],
    "Walk-in":       ["Walk-in", "Walk In", "walkin", "walk_in"],
}

ROOM_TYPES = ["Single", "Double", "Suite", "Twin", "Deluxe"]
SEASONS = {
    (1, 2, 3):   ("Winter", 90),
    (4, 5, 6):   ("Spring", 110),
    (7, 8, 9):   ("Summer", 150),
    (10, 11, 12):("Autumn", 100),
}

bookings = []
res_id = 1000

for i in range(195):
    seg_canonical = random.choice(SEGMENTS_CLEAN)
    seg_raw = random.choice(SEGMENT_VARIANTS[seg_canonical])

    check_in_month = random.randint(1, 12)
    check_in_day   = random.randint(1, 28)
    check_in_year  = 2023
    nights         = random.randint(1, 7)
    check_out_day  = check_in_day + nights

    # Wrap month/day overflow simply (keep it within same month for simplicity)
    if check_out_day > 28:
        check_out_day = 28
        nights = check_out_day - check_in_day or 1

    booking_lead   = random.randint(1, 90)
    booking_month  = check_in_month
    booking_day    = max(1, check_in_day - booking_lead)

    # Rate — occasionally null
    rate = round(random.uniform(80, 200), 2) if random.random() > 0.05 else ""

    # Date format variation: ~80% ISO, ~15% DD/MM/YYYY, ~5% MM-DD-YYYY
    r = random.random()
    if r < 0.80:
        fmt = iso
    elif r < 0.95:
        fmt = dmy
    else:
        fmt = mdy

    booking_date   = fmt(check_in_year, booking_month, booking_day)
    check_in_date  = fmt(check_in_year, check_in_month, check_in_day)
    check_out_date = fmt(check_in_year, check_in_month, check_out_day)

    # Segment null: ~4% of rows
    if random.random() < 0.04:
        seg_raw = ""

    bookings.append({
        "reservation_id": f"RES{res_id}",
        "segment":        seg_raw,
        "room_type":      random.choice(ROOM_TYPES),
        "booking_date":   booking_date,
        "check_in_date":  check_in_date,
        "check_out_date": check_out_date,
        "nights":         nights,
        "rate":           rate,
    })
    res_id += 1

# --- Plant issues ---

# 1. Exact duplicate row (copy row 0)
bookings.append(bookings[0].copy())

# 2. Duplicate reservation_id with different rate (non-exact dupe)
dupe = bookings[5].copy()
dupe["rate"] = round(float(dupe["rate"] or 120) + 20, 2)
dupe["booking_date"] = iso(2023, 1, 15)  # later booking_date — this one should be kept
bookings.append(dupe)

# 3. One logically invalid stay: check_out <= check_in (same day)
bookings.append({
    "reservation_id": f"RES{res_id}",
    "segment":        "Direct",
    "room_type":      "Single",
    "booking_date":   "2023-03-01",
    "check_in_date":  "2023-04-10",
    "check_out_date": "2023-04-10",   # invalid — same as check_in
    "nights":         0,
    "rate":           100,
})
res_id += 1

# 4. Row with null room_type
bookings.append({
    "reservation_id": f"RES{res_id}",
    "segment":        "Corporate",
    "room_type":      "",
    "booking_date":   "2023-05-01",
    "check_in_date":  "2023-06-15",
    "check_out_date": "2023-06-17",
    "nights":         2,
    "rate":           130,
})
res_id += 1

# Shuffle so planted rows aren't obviously at the end
random.shuffle(bookings)

bookings_path = RAW_DIR / "bookings.csv"
with open(bookings_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "reservation_id","segment","room_type",
        "booking_date","check_in_date","check_out_date",
        "nights","rate"
    ])
    writer.writeheader()
    writer.writerows(bookings)

print(f"bookings.csv    → {len(bookings)} rows  ({bookings_path})")


# ---------------------------------------------------------------------------
# cancellations.csv  (~25% of bookings cancel)
# ---------------------------------------------------------------------------

# Pick a random 25% of unique reservation_ids to cancel
unique_ids = list({b["reservation_id"] for b in bookings})
cancel_ids = random.sample(unique_ids, k=len(unique_ids) // 4)

REASONS = ["Price", "Personal", "Travel change", "Found better deal", "Work conflict", ""]

cancellations = []
for rid in cancel_ids:
    # Find check_in_date for this reservation to set a plausible cancellation_date
    bk = next((b for b in bookings if b["reservation_id"] == rid), None)
    if not bk:
        continue

    # Cancellation date: 1–30 days before check_in
    cancel_offset = random.randint(1, 30)

    # Mostly ISO, but one MM/DD/YYYY variant planted
    if random.random() < 0.08:
        cancel_date = f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/2023"
    else:
        cancel_date = iso(2023, random.randint(1, 11), random.randint(1, 28))

    reason = random.choice(REASONS)   # ~1/6 chance of empty (null)

    cancellations.append({
        "reservation_id":    rid,
        "cancellation_date": cancel_date,
        "reason":            reason,
        "refund_status":     random.choice(["Full", "Partial", "None", ""]),
    })

# Plant duplicate cancellation record for one reservation_id
if cancellations:
    dup_cancel = cancellations[0].copy()
    dup_cancel["cancellation_date"] = iso(2023, 1, 20)  # earlier date — should be dropped
    cancellations.append(dup_cancel)

random.shuffle(cancellations)

cancellations_path = RAW_DIR / "cancellations.csv"
with open(cancellations_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "reservation_id","cancellation_date","reason","refund_status"
    ])
    writer.writeheader()
    writer.writerows(cancellations)

print(f"cancellations.csv → {len(cancellations)} rows  ({cancellations_path})")


# ---------------------------------------------------------------------------
# seasonal_pricing.csv  (one row per day for 2023)
# ---------------------------------------------------------------------------

pricing = []
for month in range(1, 13):
    for season_months, (season_tag, base) in SEASONS.items():
        if month in season_months:
            break
    for day in range(1, 29):   # keep it simple, 28 days per month
        pricing.append({
            "date":        iso(2023, month, day),
            "season_tag":  season_tag,
            "base_rate":   round(base + random.uniform(-10, 10), 2),
            "demand_tier": random.choice(["Low", "Medium", "High"]),
        })

# Plant exact duplicate rows for 2 dates
pricing.append(pricing[10].copy())
pricing.append(pricing[45].copy())

random.shuffle(pricing)

pricing_path = RAW_DIR / "seasonal_pricing.csv"
with open(pricing_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["date","season_tag","base_rate","demand_tier"])
    writer.writeheader()
    writer.writerows(pricing)

print(f"seasonal_pricing.csv → {len(pricing)} rows  ({pricing_path})")
print("\nSample data written to data/raw/. Run the pipeline:")
print("  python -m src.ingest")
print("  python -m src.clean")
print("  python -m src.features")
print("  python -m src.load")
