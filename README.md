# 🏃‍♂️ CromWell 🍋🥝🍌🍐🥥🍈

Pull Fitbit health data and store it in AWS S3 as gzipped JSON backups. Analyze your health metrics with Jupyter notebooks. All automated via a cron job that runs once a day. It's your personal observability pipeline! 🚀

**Recent Migration**: This project has migrated from InfluxDB to S3 storage for better data persistence and portability.

### Fitbit Web API Reference

https://dev.fitbit.com/build/reference/web-api/

### Fitbit Help & Community

https://support.google.com/fitbit/#topic=14236398

## 🛠️ Data Analysis with Jupyter Notebooks

The `notebooks/` directory contains interactive Jupyter notebooks for exploratory data analysis (EDA) of your Fitbit health data.

### Available Notebooks

- **SLEEP-ANALYSIS.ipynb** - 24-hour sleep timeline visualization with stage analysis (Deep, Light, REM, Awake), sleep efficiency metrics, and nap detection
- **HEART RATE VISUALIZATION.ipynb** - Heart rate analysis and visualization
- **PERFORMANCE ANALYSIS.ipynb** - Activity and performance metrics
- **Steps_ANALYSIS.ipynb** - Step count analysis and trends
- **VARIOUS_METRICS.ipynb** - Additional health metrics (HRV, SpO2, skin temperature, etc.)

### Running Jupyter Lab

```bash
source cw_venv/bin/activate
jupyter lab
```

The notebooks automatically fetch data from S3 using the `get_fitbit_data_for_date()` function. Simply enter a date in `YYYY-MM-DD` format when prompted.

**Recent Improvements to SLEEP-CLAUDE.ipynb**:
- Added robust error handling for dates with missing sleep data
- Graceful fallback when sleep stages or summary data is unavailable
- Prevents `NoneType` errors by checking data existence before processing

#### Update Jupyter Lab

```bash
jupyter lab --version
pip install --upgrade jupyterlab
```

## 📦 Project Overview

### Main Scripts

**`fitbit2s3.py`** - Main data collection script that:

✅ Authenticates with the Fitbit API using OAuth tokens
📥 Pulls detailed health metrics (sleep, activity, HR, SpO₂, HRV, etc.)
🗜️ Compresses data as gzipped JSON
☁️ Backs up to AWS S3 (`s3://followcrom/cromwell/fitbit/`)
⏰ Runs daily via cron job at 2-3 AM

**`run_fitbit2s3.sh`** - Shell wrapper that:

🔄 Activates the virtual environment
📬 Sends email alerts on failure
📝 Handles error logging

### Deployment on Server

```bash
chmod 755 run_fitbit2s3.sh
chown root:root run_fitbit2s3.sh
```

---

## 🐍 Create Virtual Environment

```bash
python3 -m venv cw_venv  
source cw_venv/bin/activate  
pip install -r requirements.txt  
```

## 🔐 Fitbit API Credentials
Make sure you've registered an app on the Fitbit developer portal and have:

- client_id
- client_secret
- A valid access token (or refresh logic)

These should be stored securely in a .env file or secure vault, loaded by the script.

## 📁 Project Structure

```
cromwell/
├── fitbit2s3.py            # Main data collection script (migrated from fitbit2influx.py)
├── run_fitbit2s3.sh        # Shell wrapper with error handling and email alerts
├── cw_venv/                # Python virtual environment
├── notebooks/              # Jupyter notebooks for data analysis
│   ├── SLEEP-CLAUDE.ipynb         # Sleep analysis with 24-hour timelines
│   ├── HEART RATE VISUALIZATION.ipynb
│   ├── PERFORMANCE ANALYSIS.ipynb
│   ├── Steps_Analysis.ipynb
│   ├── VARIOUS_METRICS.ipynb
│   ├── functions/          # Helper functions for notebooks
│   │   ├── import_data.py         # S3 data fetching utilities
│   │   ├── sleep/
│   │   │   └── sleep_functions.py
│   │   └── various/
│   │       └── various_metrics_functions.py
│   └── imgs/               # Images for notebook headers
├── fitbit_data.log         # Log file for Fitbit data collection
├── cromwell_cron.log       # Log file for cron job execution
├── tokens.json             # OAuth tokens (auto-refreshed)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (CLIENT_ID, CLIENT_SECRET, etc.)
├── CLAUDE.md               # Instructions for Claude Code (AI assistant)
├── .gitignore
└── README.md
```

## ☁️ AWS S3 Data Storage

### S3 Bucket Structure

```
s3://followcrom/cromwell/fitbit/
├── fitbit_backup_2025-01-15.json.gz
├── fitbit_backup_2025-01-16.json.gz
├── fitbit_backup_2025-01-17.json.gz
└── ...
```

Each file contains all measurements for a single day as a gzipped JSON array.

### Record Format

Each measurement record follows this structure:

```json
{
  "measurement": "HeartRate_Intraday",
  "time": "2025-10-08T12:34:56+00:00",
  "tags": {"Device": "PixelWatch3"},
  "fields": {"value": 72.0}
}
```

### Available Measurement Types

**Intraday data (high frequency):**
- `HeartRate_Intraday` - 1 second resolution (~20,000+ records/day)
- `Steps_Intraday` - 1 minute resolution (~1,440 records/day)

**Daily summaries (1 record/day):**
- `HRV` - Heart rate variability (dailyRmssd, deepRmssd)
- `BreathingRate` - Breaths per minute
- `SkinTemperature` - Nightly relative temperature
- `SPO2_Daily` - Blood oxygen saturation (avg, max, min)
- `RestingHR` - Resting heart rate
- `DeviceBatteryLevel` - Device battery percentage
- `Weight` - Weight in kg and BMI
- `Activity-*` - Steps, calories, distance, active minutes
- `HR_Zones` - Minutes in each heart rate zone

**Sleep data:**
- `SleepSummary` - Efficiency, minutes asleep/awake/deep/light/REM
- `SleepLevels` - Timestamped sleep stage transitions with durations

**Activity data:**
- `ActivityRecords` - Logged activities (walks, runs, etc.)
- `GPS` - GPS trackpoints from activities (lat, lon, altitude, HR)

### Accessing Data from Notebooks

```python
from functions.import_data import get_fitbit_data_for_date

# Fetch data for a specific date
dfs = get_fitbit_data_for_date('2025-10-08')

# Access specific measurement types
df_hr = dfs.get('HeartRate_Intraday')
df_sleep_summary = dfs.get('SleepSummary')
df_sleep_levels = dfs.get('SleepLevels')
```

The `get_fitbit_data_for_date()` function:
- Fetches the gzipped file from S3 using boto3 (profile: 'surface')
- Parses JSON into pandas DataFrames grouped by measurement type
- Converts timestamps to timezone-aware datetime objects

<br>

## ⚙️ Timezone Handling

### BST = UTC+1 - The Solution

Instead of using midnight (00:00:00), the script uses noon (12:00:00) in your local timezone for daily measurements. Why noon? Because noon BST (12:00:00+01:00) converts to 11:00:00 UTC - still on the correct date!

- Before: 2025-08-02T23:00:00+00:00 ❌ (wrong date when viewing in BST)
- After: 2025-08-03T11:00:00+00:00 ✅ (correct date in all timezones)

Many data systems use this approach - assigning canonical timestamps to daily aggregates to avoid date shifting issues.

### Example Timeline:

- **August 3rd**: You live your day, Fitbit tracks everything
- **August 4th 3:00 AM**: Cron job runs `fitbit2s3.py` and collects yesterday's data
- **August 4th 3:05 AM**: Data gets written to S3 as `fitbit_backup_2025-08-03.json.gz`
- **Daily measurements**: Timestamped as "August 3rd 11:00 AM UTC" (noon in local time)
- **Intraday data**: Uses actual timestamps from Fitbit API
- **Sleep data**: Preserves original timestamps from Fitbit API

<br>

## 📊 Data Visualization

All data visualization is now handled through Jupyter notebooks in the `notebooks/` directory. The notebooks provide:

- **Interactive plots** using matplotlib and seaborn
- **24-hour sleep timelines** with stage-by-stage breakdown
- **Heart rate zones** and trends over time
- **Activity metrics** and performance analysis
- **Custom time windows** and date selection

**Example visualization from SLEEP-CLAUDE.ipynb:**
- Horizontal timeline showing Deep, Light, REM, and Awake stages
- Sleep efficiency metrics with color-coded ratings
- Pie charts for sleep stage distribution
- Nap detection and analysis
- Stacked bar charts for sleep composition

The notebook-based approach provides more flexibility than static dashboards and allows for custom analysis tailored to your specific questions.

---

## 🆕 Recent Updates

### January 2025 - Migration to S3 Storage
- **Migrated from InfluxDB to AWS S3** for better data persistence and portability
- Renamed scripts: `fitbit2influx.py` → `fitbit2s3.py`
- Implemented gzipped JSON backups for efficient storage
- Updated notebooks to fetch data directly from S3 using boto3

### SLEEP-CLAUDE.ipynb Error Handling Improvements
- **Added robust error handling** for dates with missing sleep data
- **Graceful fallbacks** when `SleepLevels` or `SleepSummary` data is unavailable
- **Conditional processing** - all data processing cells now check if data exists before attempting operations
- **Prevents NoneType errors** by validating data existence throughout the workflow
- **User-friendly messages** when no sleep data is found for a specific date

**Example:**
```python
# Before (would crash)
df_sleep_levels['end_time'] = df_sleep_levels['time'] + ...

# After (gracefully handles missing data)
if df_sleep_levels is not None:
    df_sleep_levels['end_time'] = df_sleep_levels['time'] + ...
else:
    print("⚠️  Skipping processing - no sleep data available for this date")
```

---

## 📅 Commit Activity 🕹️

![GitHub last commit](https://img.shields.io/github/last-commit/followcrom/cromWell/S3)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/followcrom/cromWell)
![GitHub repo size](https://img.shields.io/github/repo-size/followcrom/cromWell)

## ✍ Authors 

🌍 followCrom: [followcrom.com](https://followcrom.com/index.html) 🌐

📫 followCrom: [get in touch](https://followcrom.com/contact/contact.php) 👋

[![Static Badge](https://img.shields.io/badge/followcrom-online-blue)](http://followcrom.com)