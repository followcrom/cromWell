# Fitbit Data

## Simple One-Command Update

In data_tools/ run:

```bash
./update_fitbit_data.sh
```

That's it! This script:
- ✅ Connects to S3 using your `surface` AWS profile
- ✅ Checks `compilation_state.json` to see what you have
- ✅ Downloads ONLY new files (ones you haven't processed)
- ✅ Updates the  structure incrementally
- ✅ **No sorting needed** - data is already  by date!


## Manual Operations

### Dry Run (See What Would Be Downloaded)

```bash
py sync_from_s3.py --dry-run
```

### Download Only (Don't Process Yet)

```bash
py sync_from_s3.py --download-only
```

### Process Already-Downloaded Files

```bash
py update_parquet_lowmem.py
```

### Check GPS Tracks Are Fully Fetched

After a sync, spot-check that GPS walks fetched completely rather than eyeballing
maps. A healthy Fitbit track logs a point every ~1s, so the longest hole between
consecutive points (`max_gap_s`) is the reliable tell — a multi-minute gap means a
dropped/delayed segment (usually slow phone uploads).

```bash
py qa_gps.py            # last 20 tracks + flags suspects
py qa_gps.py --days 30  # only the last 30 days
py qa_gps.py --all      # every track
```

Anything flagged with a gap over 60s is a *candidate* to investigate, not a
confirmed failure — a gap can also be genuine signal loss (tunnel, urban canyon).
Cross-check the map; if the route looks complete, it's fine. If a gap persists
after re-fetching, it was real signal loss, not a download problem.

## Data Structure

```
data/
├── heartrate_intraday/          # Date-
│   ├── date=2025-10-03/
│   ├── date=2025-10-04/
│   └── ...
├── steps_intraday/              # Date-
│   ├── date=2025-10-03/
│   └── ...
├── gps.parquet                  # Single file
├── sleep_levels.parquet         # Single file
├── daily_summaries.parquet      # All low-frequency metrics
└── compilation_state_.json      # Tracks what we've processed
```

## State Tracking

The `compilation_state.json` file keeps track of:
- Which dates have been processed
- Total record count
- Last update time

**Important**: Don't delete this file! It prevents re-downloading files you already have.

## AWS

List contents of the Fitbit S3 bucket to verify access:

```bash
aws s3 ls s3://followcrom/cromwell/fitbit/ --profile surface
```

## Troubleshooting

### "No new files to download"
✅ You're already up to date!

### "Error connecting to S3"
- Check AWS profile: `aws configure list --profile surface`
- Test S3 access: `aws s3 ls s3://followcrom/cromwell/fitbit/ --profile surface`

### "Error loading [measurement]"
- Check partition directories exist: `ls heartrate_intraday/`
- Verify date format: Should be `date=YYYY-MM-DD`

### Want to Reprocess Everything?
```bash
# Backup state file
cp compilation_state.json compilation_state.json.backup

# Edit state file to remove dates you want to reprocess
# Or delete it entirely to reprocess all files
rm compilation_state.json

# Run sync
./update_fitbit_data.sh
```

---

<br>

## Files Overview

| File | Purpose |
|------|---------|
| `update_fitbit_data.sh` | One-click entire job wrapper |
| `sync_from_s3.py` | Download from S3 + update partitions |
| `update_parquet_lowmem.py` | Process local files only |
| `compile_fitbit_data.py` | Full recompilation (rarely needed) |
| `compilation_state.json` | State tracking (don't delete!) |

---
    
<br>

### Parquet Cleanup Script

We ran this on 2026-01-17 to remove unused columns from Parquet files to save space. We should not need to run it again.

  1. First, see what would be removed (dry run):

  `python3 cleanup_parquet_columns.py --show`

  2. If it looks good, actually clean up:

  `python3 cleanup_parquet_columns.py`

  3. If something goes wrong, restore from backup:
  
  `python3 cleanup_parquet_columns.py --restore`

  The script creates timestamped backups before modifying anything, so it's safe to test!


---

<br>

**Last Updated**: 2026-01-03

**Status**: ✅ Production Ready
