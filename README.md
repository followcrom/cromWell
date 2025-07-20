# 🏃‍♂️ CromWell 🍋🥝🍌🍐🥥🍈

Pull Fitbit health data into InfluxDB and visualize it with Grafana – effortlessly, reliably, and twice a day!

All automated via a cron job that runs twice daily. It’s your personal observability pipeline! 🚀

##  🖼️ See it in action

📊 [Dashboard](https://followcrom.com/cromwell)

👉 [On followCrom](https://followcrom.com/cromwell)

---

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