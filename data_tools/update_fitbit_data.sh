#!/bin/bash
#
# Daily update script for Fitbit data
#
# This script:
# 1. Downloads new files from S3 (only files we don't have yet)
# 2. Updates the Parquet structure
# 3. No sorting needed!
#
# Usage:
#   ./update_fitbit_data.sh
#
# For cron (daily at 3 AM):
#   0 3 * * * /home/followcrom/projects/cromWell/data/update_fitbit_data.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "Fitbit Data Update - $(date)"
echo "=================================================="

# Activate virtual environment
source ../cw_venv/bin/activate

# Run sync script
python sync_from_s3.py

echo ""
echo "✅ Update complete at $(date)"
