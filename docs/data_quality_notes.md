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
