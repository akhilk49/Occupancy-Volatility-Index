# Data Quality Notes

## Segment Definition Resolution (Joint Day 2)
**Resolution:** Discussed with the mentor. The `segment` field represents a **booking channel** (e.g., Travel Agency, Direct, Corporate, Group, Walk-in) rather than a demographic customer type.

## Manuel's Findings (cancellations.csv & seasonal_pricing.csv)

### `cancellations.csv`
- **Missing values:** `reason` field has ~15% nulls. `refund_status` is mostly populated but some older records have it missing.
- **Date formats:** `cancellation_date` is mostly ISO (YYYY-MM-DD), but some stray rows use MM/DD/YYYY. Will need standardization in the pipeline.
- **Duplicates:** A few duplicate `reservation_id`s found where a cancellation was logged twice. We'll need to deduplicate by keeping the most recent `cancellation_date`.

### `seasonal_pricing.csv`
- **Missing values:** No missing values observed in key columns (`date`, `season_tag`, `base_rate`).
- **Date formats:** Consistently YYYY-MM-DD.
- **Duplicates:** Exact duplicate rows found for a few dates. These can be safely dropped during the clean phase.

## Akhil's Findings (bookings.csv)

### Duplicates
- **Exact duplicate rows:** A small number of fully duplicate rows exist (identical across all columns). Decision: drop exact duplicates, keeping the first occurrence — no information is lost since every field is identical.
- **Duplicate `reservation_id` (non-exact):** Some `reservation_id` values appear more than once with differing field values (e.g., different `rate` or `room_type`). These are likely data entry errors or re-bookings logged under the same ID. Decision: flag these rows in the ingestion log and keep the row with the latest `booking_date`; document count in the cleaning report.

### Bad / inconsistent dates
- **`booking_date`, `check_in_date`, `check_out_date`:** Majority of records are ISO 8601 (YYYY-MM-DD), but a subset use DD/MM/YYYY or MM-DD-YYYY formats. Decision: parse all three columns with `pd.to_datetime(..., dayfirst=False, errors='coerce')`, then manually inspect and re-parse any that coerce to NaT.
- **Logical inconsistencies:** Some rows have `check_out_date <= check_in_date` or `booking_date > check_in_date` (booked after check-in). Decision: flag these as invalid and exclude from the fact table; log the count.
- **`nights` cross-check:** Where `nights` is present, verify it equals `(check_out_date - check_in_date).days`. Mismatches will be flagged and the derived value used over the raw `nights` column.

### Inconsistent segment labels
- **Confirmed resolution (joint Day 2):** `segment` represents booking channel — canonical values are: `Travel Agency`, `Direct`, `Corporate`, `Group`, `Walk-in`.
- **Observed variants in raw data:** Mixed casing (e.g., `travel agency`, `CORPORATE`), abbreviations (e.g., `TA`, `Corp`), and leading/trailing whitespace. Decision: normalise with a canonical mapping dict in `clean.py:normalise_segments()` (case-insensitive strip + map). Any unmapped value gets logged as a WARNING and left as-is for manual review.

### Nulls
- **`segment`:** Non-trivial null % observed. Decision: rows with null `segment` cannot be attributed to any channel — exclude from segment-level analysis but retain in the fact table with `segment = 'Unknown'` so row counts are preserved.
- **`rate`:** Some nulls present. Decision: impute with the `base_rate` from `seasonal_pricing` on the same `check_in_date` where available; otherwise flag as missing and exclude from revenue metrics only.
- **`room_type`:** Minor nulls. Decision: fill with `'Unknown'` — `room_type` is not a primary groupby dimension for this analysis.
- **`total_rooms_available`:** Column absent from this file (confirmed Day 1). Capacity will be derived or assumed — to be resolved before Day 10 feature engineering.

### Open questions resolved
- **Segment type:** Booking channel. Downstream `GROUP BY segment` logic confirmed. ✅
- **Occupancy grain:** Room-night grain (`nights` column) — each booking contributes `nights` room-nights. ✅ (to be validated in Day 10 once joined fact table is built)
- **`total_rooms_available`:** Not present — escalated; capacity assumption to be finalised by Day 5 before schema sign-off.
- **Date range consistency across files:** To be confirmed in Day 9 join validation (Manuel's scope).
