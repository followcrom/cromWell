# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CromWell is a personal health observability pipeline that:
- Fetches Fitbit health data (sleep, activity, HR, SpO2, etc.) via the Fitbit API
- Stores data in AWS S3 as gzipped JSON backups (daily files)
- Provides Jupyter notebooks for exploratory data analysis (EDA)

## Development Environment

### Virtual Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv cw_venv
source cw_venv/bin/activate
pip install -r requirements.txt
```

### Running Jupyter Lab
```bash
source cw_venv/bin/activate
jupyter lab
```

### Update Jupyter Lab
```bash
jupyter lab --version
pip install --upgrade jupyterlab
```

## Core Scripts

### fitbit2s3.py
Main Python script that orchestrates the entire data collection and backup pipeline.

**Key functions:**
- `refresh_fitbit_tokens()` - Handles OAuth token refresh using tokens.json
- `request_data_from_fitbit()` - Generic API request handler with retry logic and rate limiting
- `get_intraday_data()` - Fetches intraday heart rate (1sec) and steps (1min)
- `get_daily_summaries()` - Fetches HRV, breathing rate, skin temp, weight, SpO2
- `get_activity_summaries()` - Fetches steps, calories, distance, HR zones
- `get_sleep_data()` - Fetches sleep stages (deep, light, REM, wake) and efficiency
- `fetch_activities_for_date()` - Fetches logged activities with GPS data
- `get_tcx_data()` - Parses TCX files for GPS trackpoints
- `backup_to_s3_daily()` - Uploads records to S3 as gzipped JSON
- `get_user_timezone()` - Fetches user timezone from Fitbit profile

**Data flow:**
1. Validates required environment variables (CLIENT_ID, CLIENT_SECRET)
2. Refreshes Fitbit OAuth tokens
3. Fetches user timezone from Fitbit profile
4. Collects data for target date (defaults to yesterday)
5. Stores all records in `collected_records` list
6. Backs up to S3 as `cromwell/fitbit/fitbit_backup_YYYY-MM-DD.json.gz`

**Important timezone handling:**
- Daily measurements use noon (12:00:00) in local timezone to avoid BST/UTC date shifting issues
- Intraday data uses actual timestamps converted to UTC
- Sleep data preserves original timestamps from Fitbit API

**Running manually:**
```bash
source cw_venv/bin/activate
python fitbit2s3.py
```

### run_fitbit2s3.sh
Shell wrapper that runs fitbit2s3.py with error handling and email notifications.

**Key features:**
- Activates virtual environment
- Sends email alert on failure (to followcrom@gmail.com)
- Success email notification is commented out
- Designed to run via cron job at 2 AM daily

**Deployment on server:**
```bash
chmod 755 run_fitbit2s3.sh
chown root:root run_fitbit2s3.sh
```

## Data Storage Architecture

### S3 Bucket Structure
```
s3://followcrom/cromwell/fitbit/
├── fitbit_backup_2025-10-03.json.gz
├── fitbit_backup_2025-10-04.json.gz
└── ...
```

Each file contains all measurements for a single day as a JSON array of records.

### Record Format
```json
{
  "measurement": "HeartRate_Intraday",
  "time": "2025-10-08T12:34:56+00:00",
  "tags": {"Device": "PixelWatch3"},
  "fields": {"value": 72.0}
}
```

### Measurement Types
**Intraday data (high frequency):**
- `HeartRate_Intraday` - 1 second resolution (~34,000 records/day)
- `Steps_Intraday` - 1 minute resolution (~1,440 records/day)

**Daily summaries (1 record/day):**
- `HRV` - Heart rate variability (dailyRmssd, deepRmssd)
- `BreathingRate` - Breaths per minute
- `SkinTemperature` - Nightly relative temperature
- `SPO2_Daily` - Blood oxygen (avg, max, min)
- `RestingHR` - Resting heart rate
- `DeviceBatteryLevel` - Device battery percentage
- `Weight` - Weight in kg and BMI
- `Activity-*` - Steps, calories, distance, minutes by activity level
- `HR_Zones` - Minutes in each heart rate zone

**Sleep data:**
- `SleepSummary` - Efficiency, minutes asleep/awake/deep/light/REM, endTime
- `SleepLevels` - Timestamped sleep stage transitions with durations

**Activity data:**
- `ActivityRecords` - Logged activities (walks, runs, etc.)
- `GPS` - GPS trackpoints from TCX files (lat, lon, altitude, distance, heart_rate)

## Notebooks Directory

### Structure
```
notebooks/
├── functions/
│   ├── import_data.py           # S3 data fetching and parsing utilities
│   ├── sleep/
│   │   └── sleep_functions.py   # Sleep visualization functions
│   └── various/
│       └── various_metrics_functions.py
├── SLEEP ANALYSIS.ipynb          # Sleep stages, efficiency, timelines
├── SLEEP ANALYSIS 2.ipynb
├── HEART RATE VISUALIZATION.ipynb
├── PERFORMANCE ANALYSIS.ipynb
├── Steps_Analysis.ipynb
├── VARIOUS_METRICS.ipynb
└── vC/                          # Version control / experimental notebooks
```

### Key Functions in import_data.py

**`get_fitbit_data_for_date(date_str)`**
- Fetches data for specific date from S3
- Uses boto3 profile 'surface'
- Returns dict of DataFrames by measurement type
```python
dfs = get_fitbit_data_for_date('2025-10-08')
# Returns: {'HeartRate_Intraday': df, 'SleepSummary': df, ...}
```

**`parse_fitbit_data(data)`**
- Parses raw JSON records into pandas DataFrames
- Flattens tags and fields into columns
- Converts time strings to pandas datetime with timezone
- **Automatically converts activity distances from miles to kilometers**

### Distance Unit Conversion (Important!)

**Issue:** Fitbit API returns ALL activity distances in **MILES**, regardless of activity type:
- GPS-tracked runs: miles
- Treadmill runs: miles
- Swimming: miles
- Walking: miles

**Solution:** The `parse_fitbit_data()` function automatically converts all activity distances to kilometers and recalculates pace/speed accordingly.

**Implementation:**
- Original distance (miles) stored in `distance_miles` field
- Converted distance (km) in `distance` field
- Pace recalculated as seconds/km
- Speed recalculated as km/h

**Example:**
```python
# API returns: distance = 2.619 miles (GPS run)
# After parsing:
#   distance_miles = 2.619
#   distance = 4.215 km
#   pace = 763 sec/km (12:43 min/km)
#   speed = 4.72 km/h
```

**Note for Treadmill Runs:**
- GPS distance is unreliable for treadmill runs (measures position drift, not actual distance)
- Use "Treadmill" activity type instead of "Run" on your watch
- Treadmill's built-in distance measurement is most accurate
- Fitbit app may show different distance than GPS due to step-counting algorithms

### Typical Notebook Workflow
1. Import boto3 and configure S3 session with profile='surface'
2. Use `get_fitbit_data_for_date()` or directly fetch from S3
3. Parse with `parse_fitbit_data()`
4. Convert timezones from UTC to 'Europe/London' as needed
5. Visualize with matplotlib/seaborn

## Environment Variables (.env)

Required variables for fitbit2s3.py:
- `CLIENT_ID` - Fitbit OAuth client ID (required)
- `CLIENT_SECRET` - Fitbit OAuth client secret (required)
- `TOKEN_FILE_PATH` - Path to tokens.json
- `FITBIT_LOG_FILE_PATH` - Path to log file
- `FITBIT_LANGUAGE` - Language for API (default: "en_US")
- `DEVICENAME` - Device name (default: "PixelWatch3")

## OAuth Token Management

The script uses `tokens.json` to store Fitbit OAuth tokens:
```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

Tokens are automatically refreshed when expired (401 error) and written back to tokens.json.

## Error Handling and Retry Logic

**Server errors (500, 502, 503, 504):**
- Retries up to 3 times with 120s delays
- Skips request if `SKIP_REQUEST_ON_SERVER_ERROR=True`

**Rate limiting (429):**
- Respects `Fitbit-Rate-Limit-Reset` header
- Adds 30s buffer to retry delay

**Expired tokens (401):**
- Refreshes tokens up to 5 times
- Updates tokens.json automatically

**Connection errors:**
- Retries up to 3 times with 5-minute delays

## Important Notes

### Timezone Handling
- **Critical**: Daily measurements use noon (12:00 local time) to avoid BST/UTC date shifting
  - Before: 2025-08-02T23:00:00+00:00 (wrong date when viewing in BST)
  - After: 2025-08-03T11:00:00+00:00 (correct date in all timezones)
- Intraday data uses actual timestamps
- Sleep data timestamps are preserved from Fitbit API

### Data Collection Timing
- Cron job runs at 2-3 AM daily
- Collects data for yesterday (n-1 days)
- Uses local timezone for date calculation

### AWS Configuration
- S3 bucket: `followcrom`
- Prefix: `cromwell/fitbit/`
- Files are gzipped JSON for compression
- Boto3 profile: `surface` (used in notebooks)

### API Request Limits
- 2-second delay between requests (`REQUEST_DELAY_SECONDS`)
- Tracks total requests via `API_REQUEST_COUNT`
- GPS data limited to 10 activities per run (`tcx_fetch_limit`)
