#!/bin/bash
# Full compilation of all Fitbit data files into a single Parquet file

# Activate virtual environment
source cw_venv/bin/activate

# Run full compilation
echo "Compiling all Fitbit data files..."
python data/compile_fitbit_data.py --compile --data-dir data

# Check exit status
if [ $? -eq 0 ]; then
    echo "✅ Full compilation complete!"
else
    echo "❌ Compilation failed"
    exit 1
fi
