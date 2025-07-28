#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script fetches personal Fitbit data (e.g., heart rate, sleep, steps, activity)
via the Fitbit API and writes it to an InfluxDB 2.x database. It's designed
to be run once daily at the end of the day via a cron job.
"""

import base64
import requests
import time
import json
import pytz
import logging
import os
import sys
from requests.exceptions import ConnectionError
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# =============================================================================
# ## ⚙️ Configuration Variables
# =============================================================================

# --- Logging Configuration ---
FITBIT_LOG_FILE_PATH = os.environ.get("FITBIT_LOG_FILE_PATH")
# OVERWRITE_LOG_FILE: Set to True to clear the log file on each run / Set to False to append to the log file
OVERWRITE_LOG_FILE = True

# --- Fitbit API Configuration ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE_PATH = os.getenv("TOKEN_FILE_PATH")
FITBIT_LANGUAGE = os.getenv("FITBIT_LANGUAGE", "en_US")
DEVICENAME = os.getenv("DEVICENAME", "PixelWatch3")

# --- InfluxDB 2.x Configuration ---
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# --- Script Behavior ---
REQUEST_DELAY_SECONDS = 2
SERVER_ERROR_MAX_RETRY = 3
EXPIRED_TOKEN_MAX_RETRY = 5
SKIP_REQUEST_ON_SERVER_ERROR = True

# --- Global Variables (do not change) ---
ACCESS_TOKEN = ""
LOCAL_TIMEZONE = None
collected_records = []
API_REQUEST_COUNT = 0

# =============================================================================
# ## 📝 Logging Setup
# =============================================================================
if OVERWRITE_LOG_FILE:
    with open(FITBIT_LOG_FILE_PATH, "w"): pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(FITBIT_LOG_FILE_PATH, mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

# =============================================================================
# ## 🌐 API and Database Functions
# =============================================================================

def request_data_from_fitbit(url, headers={}, params={}, data={}, request_type="get"):
    """Generic function to make requests to the Fitbit API with error handling."""
    global ACCESS_TOKEN, API_REQUEST_COUNT
    retry_attempts = 0

    time.sleep(REQUEST_DELAY_SECONDS)

    logging.debug(f"Requesting data from Fitbit: {url}")
    while True:
        if request_type == "get" and not headers:
            headers = {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Accept": "application/json",
                'Accept-Language': FITBIT_LANGUAGE
            }
        try:
            if request_type == "get":
                response = requests.get(url, headers=headers, params=params, data=data)
            elif request_type == "post":
                response = requests.post(url, headers=headers, params=params, data=data)
            else:
                raise Exception(f"Invalid request type: {request_type}")

            API_REQUEST_COUNT += 1
            logging.info(f"API request count for this run: {API_REQUEST_COUNT}")

            if response.status_code == 200:
                return response.text if url.endswith(".tcx") else response.json()

            elif response.status_code == 401:
                logging.warning("Access Token expired. Refreshing now...")
                if retry_attempts >= EXPIRED_TOKEN_MAX_RETRY:
                    raise Exception("Unable to solve the 401 Error after multiple retries.")
                ACCESS_TOKEN = refresh_fitbit_tokens(CLIENT_ID, CLIENT_SECRET)
                headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
                retry_attempts += 1
                time.sleep(10)

            elif response.status_code == 429:
                retry_after = int(response.headers.get("Fitbit-Rate-Limit-Reset", 60)) + 30
                logging.warning(f"Rate limit reached. Retrying in {retry_after} seconds.")
                time.sleep(retry_after)

            elif response.status_code in [500, 502, 503, 504]:
                logging.warning(f"Server Error ({response.status_code}). Retrying in 120 seconds...")
                if retry_attempts >= SERVER_ERROR_MAX_RETRY:
                    if SKIP_REQUEST_ON_SERVER_ERROR:
                        logging.error(f"Server error retry limit reached. Skipping request: {url}")
                        return None
                    else:
                        raise Exception("Unable to solve server error after multiple retries.")
                retry_attempts += 1
                time.sleep(120)

            else:
                logging.error(f"Fitbit API request failed: {response.status_code} {response.text}")
                response.raise_for_status()
                return None

        except ConnectionError as e:
            logging.error(f"Connection error: {e}. Retrying in 5 minutes...")
            time.sleep(300)
            retry_attempts += 1


def refresh_fitbit_tokens(client_id, client_secret):
    """Refreshes the Fitbit access token using the refresh token."""
    logging.info("Attempting to refresh Fitbit tokens...")
    try:
        with open(TOKEN_FILE_PATH, "r") as file:
            tokens = json.load(file)
        refresh_token = tokens["refresh_token"]
    except (FileNotFoundError, KeyError):
        logging.error(f"Token file not found or invalid at {TOKEN_FILE_PATH}.")
        sys.exit("Error: Could not find a valid refresh token. Please ensure tokens.json exists and is correct.")

    url = "https://api.fitbit.com/oauth2/token"
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode(),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

    response_data = request_data_from_fitbit(url, headers=headers, data=data, request_type="post")

    if response_data:
        new_access_token = response_data["access_token"]
        new_refresh_token = response_data["refresh_token"]

        with open(TOKEN_FILE_PATH, "w") as file:
            json.dump({"access_token": new_access_token, "refresh_token": new_refresh_token}, file)

        logging.info("Fitbit token refresh successful!")
        return new_access_token
    else:
        raise Exception("Failed to refresh Fitbit tokens.")


def write_points_to_influxdb(points, client, write_api):
    """Writes a list of data points to InfluxDB 2.x."""
    if not points:
        logging.info("No new points to write to InfluxDB.")
        return
    try:
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)
        logging.info(f"Successfully wrote {len(points)} points to InfluxDB.")
    except InfluxDBError as e:
        logging.error(f"Error writing to InfluxDB: {e}")
        # Log the full error details from the server
        if e.response:
            logging.error(f"Reason: {e.response.reason}")
            logging.error(f"HTTP response headers: {e.response.headers}")
            logging.error(f"HTTP response body: {e.response.data}")
        sys.exit("Exiting due to InfluxDB write error.")


def get_user_timezone():
    """Fetches the user's timezone from their Fitbit profile."""
    global ACCESS_TOKEN
    profile_data = request_data_from_fitbit("https://api.fitbit.com/1/user/-/profile.json")
    if profile_data and "user" in profile_data:
        return pytz.timezone(profile_data["user"]["timezone"])
    else:
        logging.error("Could not fetch user profile to determine timezone. Defaulting to UTC.")
        return pytz.utc


# =============================================================================
# ## 📊 Fitbit Data Fetching Functions
# =============================================================================

def get_battery_level():
    """Gets the latest battery level from the user's device."""
    devices = request_data_from_fitbit("https://api.fitbit.com/1/user/-/devices.json")
    if devices:
        device = devices[0]
        collected_records.append({
            "measurement": "DeviceBatteryLevel",
            "time": LOCAL_TIMEZONE.localize(datetime.fromisoformat(device['lastSyncTime'])).astimezone(pytz.utc).isoformat(),
            "fields": {"value": float(device['batteryLevel'])},
            "tags": {"Device": DEVICENAME}
        })
        logging.info(f"Recorded battery level: {device['batteryLevel']}%")

def get_intraday_data(date_str, measurement_list):
    """Fetches intraday data (e.g., heart rate, steps) for a specific day."""
    for measurement, measurement_name, detail_level in measurement_list:
        url = f'https://api.fitbit.com/1/user/-/activities/{measurement}/date/{date_str}/1d/{detail_level}.json'
        response = request_data_from_fitbit(url)
        if response and f"activities-{measurement}-intraday" in response:
            data = response[f"activities-{measurement}-intraday"]['dataset']
            for value in data:
                log_time = datetime.fromisoformat(f"{date_str}T{value['time']}")
                utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append({
                    "measurement": measurement_name,
                    "time": utc_time,
                    "tags": {"Device": DEVICENAME},
                    "fields": {"value": float(value['value'])} # Cast to float
                })
            logging.info(f"Recorded {len(data)} points for {measurement_name} on {date_str}")

def get_daily_summaries(start_date_str, end_date_str):
    """Fetches various daily summaries (HRV, SpO2, Skin Temp, etc.) in a date range."""
    endpoints = {
        "HRV": 'https://api.fitbit.com/1/user/-/hrv/date/{start}/{end}.json',
        "BreathingRate": 'https://api.fitbit.com/1/user/-/br/date/{start}/{end}.json',
        "SkinTemperature": 'https://api.fitbit.com/1/user/-/temp/skin/date/{start}/{end}.json',
        "Weight": 'https://api.fitbit.com/1/user/-/body/log/weight/date/{start}/{end}.json',
        "SPO2_Daily": 'https://api.fitbit.com/1/user/-/spo2/date/{start}/{end}.json'
    }

    # HRV
    hrv_data = request_data_from_fitbit(endpoints["HRV"].format(start=start_date_str, end=end_date_str))
    if hrv_data and 'hrv' in hrv_data:
        for item in hrv_data['hrv']:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
            # Ensure all numeric values in the 'value' dictionary are floats
            fields = {k: float(v) for k, v in item["value"].items() if isinstance(v, (int, float))}
            if fields:
                collected_records.append({"measurement": "HRV", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": fields})
        logging.info("Recorded HRV summary.")

    # Breathing Rate
    br_data = request_data_from_fitbit(endpoints["BreathingRate"].format(start=start_date_str, end=end_date_str))
    if br_data and 'br' in br_data:
        for item in br_data['br']:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
            collected_records.append({"measurement": "BreathingRate", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": {"value": float(item["value"]["breathingRate"])}}) # Cast to float
        logging.info("Recorded Breathing Rate summary.")

    # Skin Temperature
    skin_temp_data = request_data_from_fitbit(endpoints["SkinTemperature"].format(start=start_date_str, end=end_date_str))
    if skin_temp_data and 'tempSkin' in skin_temp_data:
        for item in skin_temp_data['tempSkin']:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
            collected_records.append({"measurement": "SkinTemperature", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": {"nightlyRelative": float(item["value"]["nightlyRelative"])}}) # Cast to float
        logging.info("Recorded Skin Temperature summary.")
    
    # Weight and BMI
    weight_data = request_data_from_fitbit(endpoints["Weight"].format(start=start_date_str, end=end_date_str))
    if weight_data and 'weight' in weight_data:
        for item in weight_data['weight']:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(f"{item['date']}T{item['time']}")).astimezone(pytz.utc).isoformat()
            collected_records.append({"measurement": "Weight", "time": utc_time, "tags": {"Source": item['source']}, "fields": {"weight_kg": float(item['weight']), "bmi": float(item['bmi'])}}) # Cast to float
        logging.info("Recorded Weight and BMI summary.")
        
    # SPO2 Daily Average
    spo2_daily = request_data_from_fitbit(endpoints["SPO2_Daily"].format(start=start_date_str, end=end_date_str))
    if spo2_daily:
        for item in spo2_daily:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
            # Ensure all numeric values in the 'value' dictionary are floats
            fields = {k: float(v) for k, v in item['value'].items() if isinstance(v, (int, float))}
            if fields:
                collected_records.append({"measurement": "SPO2_Daily", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": fields})
        logging.info("Recorded Daily SpO2 summary.")


def get_activity_summaries(start_date_str, end_date_str):
    """Fetches daily activity summaries (steps, distance, calories, zones)."""
    activity_types = ["minutesSedentary", "minutesLightlyActive", "minutesFairlyActive", "minutesVeryActive", "steps", "calories", "distance"]
    for act_type in activity_types:
        url = f"https://api.fitbit.com/1/user/-/activities/tracker/{act_type}/date/{start_date_str}/{end_date_str}.json"
        data = request_data_from_fitbit(url)
        if data and f"activities-tracker-{act_type}" in data:
            for item in data[f"activities-tracker-{act_type}"]:
                utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
                collected_records.append({"measurement": f"Activity-{act_type}", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": {"value": float(item['value'])}})
            logging.info(f"Recorded Activity summary for {act_type}.")

    # Heart Rate Zones and Resting Heart Rate
    url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{start_date_str}/{end_date_str}.json"
    hr_data = request_data_from_fitbit(url)
    if hr_data and 'activities-heart' in hr_data:
        for item in hr_data['activities-heart']:
            utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(item["dateTime"] + "T00:00:00")).astimezone(pytz.utc).isoformat()
            # Ensure zone minutes are floats
            zones = {zone.get('name'): float(zone.get('minutes', 0)) for zone in item['value'].get('heartRateZones', [])}
            collected_records.append({"measurement": "HR_Zones", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": zones})
            if "restingHeartRate" in item['value']:
                # Ensure resting heart rate is a float
                collected_records.append({"measurement": "RestingHR", "time": utc_time, "tags": {"Device": DEVICENAME}, "fields": {"value": float(item['value']['restingHeartRate'])}})
        logging.info("Recorded Heart Rate Zone and Resting HR summaries.")

def get_sleep_data(start_date_str, end_date_str):
    """Fetches detailed sleep data, including stages and efficiency."""
    url = f'https://api.fitbit.com/1.2/user/-/sleep/date/{start_date_str}/{end_date_str}.json'
    sleep_data = request_data_from_fitbit(url)
    if not (sleep_data and 'sleep' in sleep_data):
        logging.warning("No sleep data found for the specified period.")
        return

    sleep_level_map = {'wake': 3, 'rem': 2, 'light': 1, 'deep': 0, 'asleep': 1, 'restless': 2, 'awake': 3}
    for record in sleep_data['sleep']:
        utc_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(record["startTime"])).astimezone(pytz.utc).isoformat()
        summary_levels = record.get('levels', {}).get('summary', {})
        
        minutes_light = summary_levels.get('light', {}).get('minutes', summary_levels.get('asleep', {}).get('minutes', 0))
        minutes_rem = summary_levels.get('rem', {}).get('minutes', summary_levels.get('restless', {}).get('minutes', 0))
        minutes_deep = summary_levels.get('deep', {}).get('minutes', 0)

        collected_records.append({
            "measurement": "SleepSummary",
            "time": utc_time,
            "tags": {"Device": DEVICENAME, "isMainSleep": record["isMainSleep"]},
            # Ensure all summary fields are floats
            "fields": {
                'efficiency': float(record["efficiency"]),
                'minutesAsleep': float(record['minutesAsleep']),
                'minutesInBed': float(record['timeInBed']),
                'minutesAwake': float(record['minutesAwake']),
                'minutesLight': float(minutes_light),
                'minutesREM': float(minutes_rem),
                'minutesDeep': float(minutes_deep),
            }
        })

        if 'data' in record.get('levels', {}):
            for stage in record['levels']['data']:
                stage_time = LOCAL_TIMEZONE.localize(datetime.fromisoformat(stage["dateTime"])).astimezone(pytz.utc).isoformat()
                collected_records.append({
                    "measurement": "SleepLevels",
                    "time": stage_time,
                    "tags": {"Device": DEVICENAME, "isMainSleep": record["isMainSleep"]},
                    # Ensure level and duration are floats
                    "fields": {
                        'level': float(sleep_level_map.get(stage["level"], -1)),
                        'duration_seconds': float(stage["seconds"])
                    }
                })
    logging.info(f"Recorded {len(sleep_data['sleep'])} sleep logs.")

def fetch_latest_activities(end_date_str):
    """Fetches the 50 most recent activities and their GPS data if available."""
    next_day = (datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api.fitbit.com/1/user/-/activities/list.json?beforeDate={next_day}&sort=desc&limit=50&offset=0"
    activities_data = request_data_from_fitbit(url)
    if not (activities_data and 'activities' in activities_data):
        logging.warning("Could not fetch recent activities.")
        return
        
    logging.info(f"Fetched {len(activities_data['activities'])} recent activity logs.")
    tcx_fetch_limit = 10
    tcx_fetched_count = 0

    for activity in activities_data['activities']:
        # Ensure all numeric fields are floats
        fields = {k: float(v) for k, v in activity.items() if isinstance(v, (int, float)) and k not in ['logId', 'activityTypeId']}
        utc_time = datetime.fromisoformat(activity['startTime'].strip("Z")).replace(tzinfo=pytz.utc).isoformat()
        activity_id = f"{utc_time}-{activity['activityName']}"
        
        collected_records.append({
            "measurement": "ActivityRecords",
            "time": utc_time,
            "tags": {"ActivityName": activity['activityName']},
            "fields": fields
        })

        if activity.get("hasGps") and activity.get("tcxLink") and tcx_fetched_count < tcx_fetch_limit:
            logging.info(f"Found GPS data for activity: {activity['activityName']}. Attempting to fetch.")
            get_tcx_data(activity["tcxLink"], activity_id)
            tcx_fetched_count += 1

def get_tcx_data(tcx_url, activity_id):
    """Parses a TCX file for GPS trackpoints."""
    tcx_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response_text = request_data_from_fitbit(tcx_url, headers=tcx_headers)
    if not response_text:
        logging.error(f"Failed to fetch TCX data for {activity_id}")
        return

    root = ET.fromstring(response_text)
    namespace = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    trackpoints = root.findall(".//ns:Trackpoint", namespace)
    
    for trkpt in trackpoints:
        time_elem = trkpt.find("ns:Time", namespace)
        lat_elem = trkpt.find(".//ns:LatitudeDegrees", namespace)
        lon_elem = trkpt.find(".//ns:LongitudeDegrees", namespace)
        
        if time_elem is not None and lat_elem is not None and lon_elem is not None:
            utc_time = datetime.fromisoformat(time_elem.text.strip("Z")).replace(tzinfo=pytz.utc).isoformat()
            # Ensure all GPS fields are floats
            fields = {
                "lat": float(lat_elem.text),
                "lon": float(lon_elem.text),
                "altitude": float(alt.text) if (alt := trkpt.find("ns:AltitudeMeters", namespace)) is not None else None,
                "distance": float(dist.text) if (dist := trkpt.find("ns:DistanceMeters", namespace)) is not None else None,
                "heart_rate": float(hr.text) if (hr := trkpt.find(".//ns:HeartRateBpm/ns:Value", namespace)) is not None else None,
            }
            fields = {k: v for k, v in fields.items() if v is not None}
            collected_records.append({
                "measurement": "GPS",
                "tags": {"ActivityID": activity_id},
                "time": utc_time,
                "fields": fields
            })
    logging.info(f"Recorded {len(trackpoints)} GPS points for {activity_id}")

# =============================================================================
# ## 🚀 Main Execution
# =============================================================================

def main():
    """Main function to orchestrate the data fetching and writing process."""
    global ACCESS_TOKEN, LOCAL_TIMEZONE, collected_records
    
    logging.info("--- Starting Fitbit data sync script ---")

    required_vars = ['CLIENT_ID', 'CLIENT_SECRET', 'INFLUXDB_URL', 'INFLUXDB_TOKEN', 'INFLUXDB_ORG', 'INFLUXDB_BUCKET']
    missing_vars = [var for var in required_vars if not globals().get(var)]
    if missing_vars:
        logging.error(f"Fatal: The following required environment variables are not set: {', '.join(missing_vars)}")
        sys.exit(1)

    try:
        influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        influx_write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        logging.info("Successfully connected to InfluxDB.")
    except Exception as e:
        logging.error(f"Fatal: Could not connect to InfluxDB. Aborting. Error: {e}")
        sys.exit(1)

    ACCESS_TOKEN = refresh_fitbit_tokens(CLIENT_ID, CLIENT_SECRET)
    LOCAL_TIMEZONE = get_user_timezone()

    # Recommended: run after midnight for the previous day
    target_date = datetime.now(LOCAL_TIMEZONE) - timedelta(days=1)
    date_str = target_date.strftime("%Y-%m-%d")

    start_date_str = date_str
    end_date_str = date_str
    date_list = [date_str]
    
    logging.info(f"Fetching data for date: {date_str}.")

    logging.info("--- Fetching intraday data ---")
    for date_str_item in date_list:
        get_intraday_data(date_str_item, [
            ('heart', 'HeartRate_Intraday', '1sec'),
            ('steps', 'Steps_Intraday', '1min')
        ])
    
    logging.info("--- Fetching daily and summary data ---")
    get_daily_summaries(start_date_str, end_date_str)
    get_activity_summaries(start_date_str, end_date_str)
    get_sleep_data(start_date_str, end_date_str)
    get_battery_level()
    fetch_latest_activities(end_date_str)

    write_points_to_influxdb(collected_records, influx_client, influx_write_api)

    logging.info(f"--- Script finished successfully. Total API requests made: {API_REQUEST_COUNT} ---")

if __name__ == "__main__":
    main()