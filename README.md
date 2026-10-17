# 🏃‍♂️ CromWell 🍋🥝🍌🍐🥥🍈

Fetch and analyze your Fitbit health data. The project automatically pulls data from the Google Health API, backs it up to AWS S3 as gzipped JSON, and processes it into Parquet format for efficient analysis with Jupyter notebooks. All automated via a cron job that runs once a day. It's your personal health data pipeline! 🚀

### Google Health API

Data comes from the Google Health API v4 (`https://health.googleapis.com/v4`). The legacy Fitbit Web API (used by `fitbit2s3.py`) is switched off on 2026-10-30.

- Data types: https://developers.google.com/health/data-types
- Fitbit migration guide: https://developers.google.com/health/migration

### Fitbit Help & Community

https://support.google.com/fitbit/#topic=14236398


## 🚀 Workflow

1. **Data Collection** - The `health2s3.py` script runs daily via cron, fetching:
   - Heart rate (daily summary and intraday)
   - Sleep data (levels, stages, and summaries)
   - Steps (daily and intraday)
   - Activities and GPS data
   - Daily summary metrics

2. **Cloud Backup** - Data is compressed (gzip) and uploaded to AWS S3

3. **Local Processing** - Use `data_tools/update_fitbit_data.sh` to download and convert JSON to Parquet format

4. **Analysis** - Open Jupyter notebooks for exploratory data analysis and visualization

## 🛠️ Local EDA

Just activate the venv and run jupyter lab:

```bash
source cw_venv/bin/activate
jupyter lab
```

#### Update jupyter lab

```bash
jupyter lab --version
pip install --upgrade jupyterlab
```

## 🐍 Create Virtual Environment

```bash
python3 -m venv cw_venv  
source cw_venv/bin/activate  
pip install -r requirements.txt  
```

## 🔐 Configuration

### Google Health API Credentials
Run the one-off consent flow on a machine with a browser (`cd api-migration && python probe.py`), then copy `api-migration/token.json` to the server. The collector only refreshes it.

- `GOOGLE_TOKEN_FILE` - Path to the token (default: `api-migration/token.json`)
- `HEALTH_S3_PREFIX` - S3 key prefix (default: `cromwell/fitbit/fitbit_backup`)
- `DEVICENAME` - Your device name (e.g., PixelWatch3)

### AWS S3 Configuration
Configure AWS credentials for S3 backup:

- `AWS_ACCESS_KEY_ID` - Your AWS access key
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
- `S3_BUCKET_NAME` - S3 bucket for data storage
- `AWS_REGION` - AWS region (if needed)

### Logging
- `HEALTH_LOG_FILE_PATH` - Path for log file output

All credentials should be stored securely in a `.env` file (not committed to git).

## 🖥️ Server Deployment

On the server (dobox), `run_health2s3.sh` runs from `followcrom`'s crontab at 02:45:

```bash
chmod 755 run_health2s3.sh
```

The script includes email notifications on failures and comprehensive error logging.

## 📁 Project Structure

```
cromWell/
├── health2s3.py              # Main script to fetch Google Health data and upload to S3
├── run_health2s3.sh          # Cron job wrapper script with error handling
├── fitbit2s3.py              # Legacy Fitbit API collector (API off 2026-10-30)
├── requirements.txt          # Python dependencies
├── data/                     # Local Parquet data storage
│   ├── daily_summaries.parquet
│   ├── gps.parquet
│   ├── sleep_levels.parquet
│   ├── heartrate_intraday/   # Intraday heart rate data
│   └── steps_intraday/       # Intraday steps data
├── data_tools/               # Data management utilities
│   ├── split_parquet.py      # Split large Parquet files
│   ├── sync_from_s3.py       # Sync data from S3 to local
│   ├── update_parquet_lowmem.py  # Memory-efficient incremental updates
│   └── update_fitbit_data.sh # Update script
├── notebooks/                # Jupyter notebooks for analysis
│   ├── SLEEP_ANALYSIS.ipynb  # Sleep data analysis
│   ├── Activities_Refine.ipynb
│   ├── Sleep_Redux.ipynb
│   └── functions/            # Helper functions for notebooks
│       ├── load_data.py      # Data loading utilities
│       └── sleep/            # Sleep analysis helpers
│           └── sleep_helpers.py
└── docs/                     # Documentation files
    ├── fitbit-tokens.txt
    └── sleep-values.txt
```

## ✨ Key Features

- **Automated Data Collection**: Daily cron job fetches data from the Google Health API
- **Cloud Backup**: Gzipped JSON files stored in AWS S3
- **Efficient Storage**: Parquet format for fast querying and analysis
- **Memory-Efficient Updates**: Incremental data updates without loading entire datasets
- **Comprehensive Analysis**: Jupyter notebooks for sleep, activity, and health metrics
- **Error Handling**: Email notifications on job failures

## 🔧 Data Tools

The `data_tools/` directory contains utilities for managing your Fitbit data.

## 📅 Commit Activity 🕹️

![GitHub last commit](https://img.shields.io/github/last-commit/followcrom/cromWell)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/followcrom/cromWell)
![GitHub repo size](https://img.shields.io/github/repo-size/followcrom/cromWell)

## ✍ Authors 

🌍 followCrom: [followcrom.com](https://followcrom.com/index.html) 🌐

📫 followCrom: [get in touch](https://followcrom.com/contact/contact.php) 👋

[![Static Badge](https://img.shields.io/badge/followcrom-online-blue)](http://followcrom.com)