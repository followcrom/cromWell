#!/bin/bash
# Update the compiled Fitbit Parquet file with new daily data
# Uses low-memory version to avoid OOM issues

# Activate virtual environment
source cw_venv/bin/activate

# Run incremental update (low-memory version)
echo "Updating compiled Fitbit data (low-memory mode)..."
cd data && python3 update_parquet_lowmem.py

# Check exit status
if [ $? -eq 0 ]; then
    echo "✅ Data update complete!"
else
    echo "❌ Data update failed"
    exit 1
fi
