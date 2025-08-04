#!/bin/bash
set -o pipefail

# Load InfluxDB environment config
# Make sure `~/.influxdbv2/configs` is properly configured with your active profile

S3_BUCKET="s3://followcrom/cromwell"
FILENAME="cromwell_data-$(date +%Y-%m-%d).json"
FILENAME="${FILENAME%.json}.gz"  # Compress the JSON file
# FILENAME="cromwell_data-$(date +%Y-%m-%d).csv"
S3_PATH="$S3_BUCKET/$FILENAME"

# Time range for the backup. Examples:
# -30d = Last 30 days
# -7d  = Last 7 days
# -1d  = Yesterday
TIME_RANGE="-1d"

echo "📦 Starting InfluxDB backup to S3 for time range: $TIME_RANGE"

# Execute Influx query and upload csv to S3
# influx query "from(bucket: \"cromwell-fitbit-2\") |> range(start: $TIME_RANGE)" \
#   | aws s3 cp - "$S3_PATH" --content-type text/csv
  
# Execute Influx query and upload json to S3
# influx query "from(bucket: \"cromwell-fitbit\") |> range(start: $TIME_RANGE)" \
#   | aws s3 cp - "$S3_PATH" --content-type application/json

# Compress the output and upload to S3
influx query "from(bucket: \"cromwell-fitbit-2\") |> range(start: $TIME_RANGE)" \
  | gzip \
  | aws s3 cp - "${S3_PATH}.gz" --content-encoding gzip --content-type application/json

# Check exit status
if [ $? -eq 0 ]; then
    echo "✅ Successfully backed up data to $S3_PATH"
else
    echo "❌ Backup failed."
fi

exit 0
