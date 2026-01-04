# Fitbit Data

## Simple One-Command Update

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
python sync_from_s3.py --dry-run
```

### Download Only (Don't Process Yet)

```bash
python sync_from_s3.py --download-only
```

### Process Already-Downloaded Files

```bash
python update_parquet_lowmem.py
```

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

**Last Updated**: 2026-01-03

**Status**: ✅ Production Ready
