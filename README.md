# 🏃‍♂️ CromWell 🍋🥝🍌🍐🥥🍈

Pull Fitbit health data into InfluxDB and visualize it with Grafana. All automated via a cron job that runs once a day. It’s your personal observability pipeline! 🚀

##  🖼️ Grafana Visualization

📊 [Dashboard](https://followcrom.grafana.net/d/97b9809e-408a-4f96-8f92-333e7167d952/cromwell-s-fitbit-board)


## 🛠️ Local EDA

Just activate the venv and run jupyter lab:

```bash
source cw_venv/bin/activate
jupyter lab
```

## 📦 Project Overview

`fitbit2influx.py` is a Python script that:

✅ Authenticates with the Fitbit API  
📥 Pulls detailed health metrics (sleep, activity, HR, SpO₂, etc.)  
🛢 Stores that data in InfluxDB  
📈 Feeds your Grafana dashboards with up-to-date personal metrics  

`run_fitbit2influx.sh` is a shell script that:

📬 Sends an email alert if anything goes wrong

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
├── fitbit2influx.py        # Main Python script
├── run_fitbit2influx.sh    # Shell wrapper for running the script with logging and error handling
├── cw_venv/                # Python virtual environment
├── data/                   # JSON data files
├── fitbit_data.log         # Log file for Fitbit data
├── cromwell_cron.log       # Log file for cron job execution
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables for configuration
├── .gitignore              # Git ignore file
└── README.md
```

## InfluxDB

```bash
influx bucket list
```

List Measurements:

```bash
influx query 'import "influxdata/influxdb/schema"
  schema.measurements(bucket: "cromwell-fitbit-2")'
```

List Tag Keys:
Tags are key-value pairs that store metadata and are indexed for fast querying. To see all the tag keys for a specific measurement:

```bash
influx query 'import "influxdata/influxdb/schema"
schema.measurementTagKeys(
bucket: "cromwell-fitbit-2",
measurement: "HRV"
)'
```

List Field Keys:
Fields are the key-value pairs that store your actual time series data (e.g., temperature, pressure). Unlike tags, fields are not indexed. To see the field keys for a measurement:

```bash
influx query 'import "influxdata/influxdb/schema"
  schema.measurementFieldKeys(
    bucket: "cromwell-fitbit-2",
    measurement: "HRV"
  )'
```

List Series:
A series is a unique combination of measurement, tag set, and field key. To see all series in a bucket:

```bash
influx query 'from(bucket: "cromwell-fitbit-2") |> range(start: -1d) |> filter(fn: (r) => r._measurement == "HeartRate_Intraday") |> sort(columns: ["_time"]) |> limit(n: 200)'
```

---

<br>

## 📅 Commit Activity 🕹️

![GitHub last commit](https://img.shields.io/github/last-commit/followcrom/cromWell)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/followcrom/cromWell)
![GitHub repo size](https://img.shields.io/github/repo-size/followcrom/cromWell)

## ✍ Authors 

🌍 followCrom: [followcrom.com](https://followcrom.com/index.html) 🌐

📫 followCrom: [get in touch](https://followcrom.com/contact/contact.php) 👋

[![Static Badge](https://img.shields.io/badge/followcrom-online-blue)](http://followcrom.com)