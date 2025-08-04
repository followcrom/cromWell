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
OVERWRITE_LOG_FILE = False

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

def safe_float_convert(value, default=0.0):
    """Safely convert a value to float with error handling."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        logging.warning(f"Could not convert '{value}' to float, using default {default}")
        return default

def safe_datetime_parse(date_string, add_time=True, daily_measurement=False):
    """Safely parse datetime strings with error handling."""
    if not date_string or len(date_string) < 8:
        logging.warning(f"safe_datetime_parse: Input '{date_string}' is not a valid datetime string.")
        return None
    try:
        # For daily measurements, keep as date at noon in local timezone to avoid timezone shifting issues
        if daily_measurement and len(date_string) == 10:  # YYYY-MM-DD format
            dt = datetime.strptime(date_string, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
            dt = LOCAL_TIMEZONE.localize(dt)
            return dt.astimezone(pytz.utc).isoformat()
        
        # Defensive programming: if we encounter an unexpected date-only string, treat it like a daily measurement
        if add_time and 'T' not in date_string and len(date_string) == 10:
            logging.warning(f"Unexpected date-only string '{date_string}' - treating as daily measurement to avoid timezone issues")
            dt = datetime.strptime(date_string, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
            dt = LOCAL_TIMEZONE.localize(dt)
            return dt.astimezone(pytz.utc).isoformat()
        
        # Handle timezone-aware strings
        if date_string.endswith('Z'):
            dt = datetime.fromisoformat(date_string.rstrip('Z')).replace(tzinfo=pytz.utc)
            return dt.isoformat()
        else:
            dt = datetime.fromisoformat(date_string)
            if dt.tzinfo is None:
                dt = LOCAL_TIMEZONE.localize(dt)
            return dt.astimezone(pytz.utc).isoformat()
    except (ValueError, AttributeError) as e:
        logging.warning(f"Failed to parse datetime '{date_string}': {e}")
        return None

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
                response = requests.get(url, headers=headers, params=params, data=data, timeout=30)
            elif request_type == "post":
                response = requests.post(url, headers=headers, params=params, data=data, timeout=30)
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
                if retry_attempts >= 3:
                    return None
                retry_attempts += 1
                time.sleep(30)

        except ConnectionError as e:
            logging.error(f"Connection error: {e}. Retrying in 5 minutes...")
            if retry_attempts >= 3:
                return None
            time.sleep(300)
            retry_attempts += 1
        except Exception as e:
            logging.error(f"Unexpected error in API request: {e}")
            if retry_attempts >= 3:
                return None
            retry_attempts += 1
            time.sleep(30)


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

    if response_data and "access_token" in response_data:
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
        for device in devices:
            if device.get('deviceVersion') == DEVICENAME or device.get('type') == DEVICENAME:
                time_str = safe_datetime_parse(device.get('lastSyncTime'))
                if time_str:
                    record = {
                        "measurement": "DeviceBatteryLevel",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": {"value": safe_float_convert(device.get('batteryLevel', 0))}
                    }
                    collected_records.append(record)
                    logging.info(f"Recorded battery level: {device.get('batteryLevel', 0)}%")
                break
        else:
            # If no matching device found, use first device
            if devices:
                device = devices[0]
                time_str = safe_datetime_parse(device.get('lastSyncTime'))
                if time_str:
                    record = {
                        "measurement": "DeviceBatteryLevel",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": {"value": safe_float_convert(device.get('batteryLevel', 0))}
                    }
                    collected_records.append(record)
                    logging.info(f"Recorded battery level: {device.get('batteryLevel', 0)}%")

def get_intraday_data(date_str, measurement_list):
    """Fetches intraday data (e.g., heart rate, steps) for a specific day."""
    for measurement, measurement_name, detail_level in measurement_list:
        url = f'https://api.fitbit.com/1/user/-/activities/{measurement}/date/{date_str}/1d/{detail_level}.json'
        response = request_data_from_fitbit(url)
        if response and f"activities-{measurement}-intraday" in response:
            data = response[f"activities-{measurement}-intraday"]['dataset']
            for value in data:
                log_time = safe_datetime_parse(f"{date_str}T{value['time']}", add_time=False)
                if log_time:
                    record = {
                        "measurement": measurement_name,
                        "time": log_time,
                        "tags": {"Device": DEVICENAME},
                        "fields": {"value": safe_float_convert(value.get('value', 0))}
                    }
                    collected_records.append(record)
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
            time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
            if time_str and "value" in item:
                # Ensure all numeric values in the 'value' dictionary are floats
                fields = {}
                for k, v in item["value"].items():
                    if isinstance(v, (int, float, str)):
                        fields[k] = safe_float_convert(v)
                
                if fields:
                    record = {
                        "measurement": "HRV",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": fields
                    }
                    collected_records.append(record)
        logging.info("Recorded HRV summary.")

    # Breathing Rate
    br_data = request_data_from_fitbit(endpoints["BreathingRate"].format(start=start_date_str, end=end_date_str))
    if br_data and 'br' in br_data:
        for item in br_data['br']:
            time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
            if time_str and "value" in item:
                breathing_rate = safe_float_convert(item["value"].get("breathingRate", 0))
                record = {
                    "measurement": "BreathingRate",
                    "time": time_str,
                    "tags": {"Device": DEVICENAME},
                    "fields": {"value": breathing_rate}
                }
                collected_records.append(record)
        logging.info("Recorded Breathing Rate summary.")

    # Skin Temperature
    skin_temp_data = request_data_from_fitbit(endpoints["SkinTemperature"].format(start=start_date_str, end=end_date_str))
    if skin_temp_data and 'tempSkin' in skin_temp_data:
        for item in skin_temp_data['tempSkin']:
            time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
            if time_str and "value" in item:
                nightly_relative = safe_float_convert(item["value"].get("nightlyRelative", 0))
                record = {
                    "measurement": "SkinTemperature",
                    "time": time_str,
                    "tags": {"Device": DEVICENAME},
                    "fields": {"nightlyRelative": nightly_relative}
                }
                collected_records.append(record)
        logging.info("Recorded Skin Temperature summary.")
    
    # Weight and BMI
    weight_data = request_data_from_fitbit(endpoints["Weight"].format(start=start_date_str, end=end_date_str))
    if weight_data and 'weight' in weight_data:
        for item in weight_data['weight']:
            time_str = safe_datetime_parse(f"{item.get('date', '')}T{item.get('time', '00:00:00')}", add_time=False)
            if time_str:
                record = {
                    "measurement": "Weight",
                    "time": time_str,
                    "tags": {"Source": item.get('source', 'Unknown')},
                    "fields": {
                        "weight_kg": safe_float_convert(item.get('weight', 0)),
                        "bmi": safe_float_convert(item.get('bmi', 0))
                    }
                }
                collected_records.append(record)
        logging.info("Recorded Weight and BMI summary.")
        
    # SPO2 Daily Average
    spo2_daily = request_data_from_fitbit(endpoints["SPO2_Daily"].format(start=start_date_str, end=end_date_str))
    if spo2_daily:
        for item in spo2_daily:
            time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
            if time_str and "value" in item:
                # Ensure all numeric values in the 'value' dictionary are floats
                fields = {}
                for k, v in item['value'].items():
                    if isinstance(v, (int, float, str)):
                        fields[k] = safe_float_convert(v)
                
                if fields:
                    record = {
                        "measurement": "SPO2_Daily",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": fields
                    }
                    collected_records.append(record)
        logging.info("Recorded Daily SpO2 summary.")


def get_activity_summaries(start_date_str, end_date_str):
    """Fetches daily activity summaries (steps, distance, calories, zones)."""
    activity_types = ["minutesSedentary", "minutesLightlyActive", "minutesFairlyActive", "minutesVeryActive", "steps", "calories", "distance"]
    for act_type in activity_types:
        url = f"https://api.fitbit.com/1/user/-/activities/tracker/{act_type}/date/{start_date_str}/{end_date_str}.json"
        data = request_data_from_fitbit(url)
        if data and f"activities-tracker-{act_type}" in data:
            for item in data[f"activities-tracker-{act_type}"]:
                time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
                if time_str:
                    record = {
                        "measurement": f"Activity-{act_type}",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": {"value": safe_float_convert(item.get('value', 0))}
                    }
                    collected_records.append(record)
            logging.info(f"Recorded Activity summary for {act_type}.")

    # Heart Rate Zones and Resting Heart Rate
    url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{start_date_str}/{end_date_str}.json"
    hr_data = request_data_from_fitbit(url)
    if hr_data and 'activities-heart' in hr_data:
        for item in hr_data['activities-heart']:
            time_str = safe_datetime_parse(item.get("dateTime"), daily_measurement=True)
            if time_str and "value" in item:
                # Heart Rate Zones
                zones = {}
                for zone in item['value'].get('heartRateZones', []):
                    zone_name = zone.get('name', 'Unknown')
                    zones[zone_name] = safe_float_convert(zone.get('minutes', 0))
                
                if zones:
                    record = {
                        "measurement": "HR_Zones",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": zones
                    }
                    collected_records.append(record)
                
                # Resting Heart Rate
                if "restingHeartRate" in item['value']:
                    record = {
                        "measurement": "RestingHR",
                        "time": time_str,
                        "tags": {"Device": DEVICENAME},
                        "fields": {"value": safe_float_convert(item['value']['restingHeartRate'])}
                    }
                    collected_records.append(record)
        logging.info("Recorded Heart Rate Zone and Resting HR summaries.")

def get_sleep_data(start_date_str, end_date_str):
    """Fetches detailed sleep data, including stages and efficiency."""
    url = f'https://api.fitbit.com/1.2/user/-/sleep/date/{start_date_str}/{end_date_str}.json'
    sleep_data = request_data_from_fitbit(url)
    if not (sleep_data and 'sleep' in sleep_data):
        logging.warning("No sleep data found for the specified period.")
        return

    sleep_level_map = {'wake': 3, 'rem': 2, 'light': 1, 'deep': 0, 'asleep': 1, 'restless': 2, 'awake': 3}
    for sleep_record in sleep_data['sleep']:
        time_str = safe_datetime_parse(sleep_record.get("startTime"), add_time=False)
        if not time_str:
            continue
            
        summary_levels = sleep_record.get('levels', {}).get('summary', {})
        
        minutes_light = safe_float_convert(
            summary_levels.get('light', {}).get('minutes', 
            summary_levels.get('asleep', {}).get('minutes', 0))
        )
        minutes_rem = safe_float_convert(
            summary_levels.get('rem', {}).get('minutes', 
            summary_levels.get('restless', {}).get('minutes', 0))
        )
        minutes_deep = safe_float_convert(summary_levels.get('deep', {}).get('minutes', 0))

        record = {
            "measurement": "SleepSummary",
            "time": time_str,
            "tags": {"Device": DEVICENAME, "isMainSleep": str(sleep_record.get("isMainSleep", False))},
            "fields": {
                'efficiency': safe_float_convert(sleep_record.get("efficiency", 0)),
                'minutesAsleep': safe_float_convert(sleep_record.get('minutesAsleep', 0)),
                'minutesInBed': safe_float_convert(sleep_record.get('timeInBed', 0)),
                'minutesAwake': safe_float_convert(sleep_record.get('minutesAwake', 0)),
                'minutesLight': minutes_light,
                'minutesREM': minutes_rem,
                'minutesDeep': minutes_deep,
            }
        }
        collected_records.append(record)

        # Sleep stages detail
        if 'data' in sleep_record.get('levels', {}):
            for stage in sleep_record['levels']['data']:
                stage_time = safe_datetime_parse(stage.get("dateTime"), add_time=False)
                if stage_time:
                    record = {
                        "measurement": "SleepLevels",
                        "time": stage_time,
                        "tags": {"Device": DEVICENAME, "isMainSleep": str(sleep_record.get("isMainSleep", False))},
                        "fields": {
                            'level': safe_float_convert(sleep_level_map.get(stage.get("level"), -1)),
                            'duration_seconds': safe_float_convert(stage.get("seconds", 0))
                        }
                    }
                    collected_records.append(record)
    logging.info(f"Recorded {len(sleep_data['sleep'])} sleep logs.")

def fetch_activities_for_date(start_date_str, end_date_str):
    """Fetches activities for the specified date using the detailed activities list endpoint."""
    # Use the detailed endpoint but filter results to the target date
    next_day = (datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    # Fetch more activities to ensure we get all from the target date
    url = f"https://api.fitbit.com/1/user/-/activities/list.json?beforeDate={next_day}&sort=desc&limit=20&offset=0"
    activities_data = request_data_from_fitbit(url)
    if not (activities_data and 'activities' in activities_data):
        logging.warning(f"Could not fetch activities for {start_date_str}.")
        return
    
    # Filter activities to only include those from the target date
    target_activities = []
    for activity in activities_data['activities']:
        activity_date = activity['startTime'][:10]  # Extract YYYY-MM-DD from startTime
        if activity_date == start_date_str:
            target_activities.append(activity)
        elif activity_date < start_date_str:
            # Since activities are sorted desc by date, we can break when we hit older dates
            break
    
    if not target_activities:
        logging.info(f"No activities found for {start_date_str}.")
        return
        
    logging.info(f"Fetched {len(target_activities)} activity logs for {start_date_str}.")
    tcx_fetch_limit = 10
    tcx_fetched_count = 0

    for activity in target_activities:
        # Ensure all numeric fields are floats
        fields = {k: float(v) for k, v in activity.items() if isinstance(v, (int, float)) and k not in ['logId', 'activityTypeId']}
        utc_time = datetime.fromisoformat(activity['startTime'].strip("Z")).replace(tzinfo=pytz.utc).isoformat()
        activity_id = f"{utc_time}-{activity['activityName']}"
        # Add the activity record to the collected records
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

    try:
        root = ET.fromstring(response_text)
        namespace = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
        trackpoints = root.findall(".//ns:Trackpoint", namespace)
        
        points_added = 0
        for trkpt in trackpoints:
            time_elem = trkpt.find("ns:Time", namespace)
            lat_elem = trkpt.find(".//ns:LatitudeDegrees", namespace)
            lon_elem = trkpt.find(".//ns:LongitudeDegrees", namespace)
            
            if time_elem is not None and lat_elem is not None and lon_elem is not None:
                time_str = safe_datetime_parse(time_elem.text, add_time=False)
                if time_str:
                    # Ensure all GPS fields are floats
                    fields = {
                        "lat": safe_float_convert(lat_elem.text),
                        "lon": safe_float_convert(lon_elem.text),
                    }
                    
                    # Optional fields
                    alt_elem = trkpt.find("ns:AltitudeMeters", namespace)
                    if alt_elem is not None:
                        fields["altitude"] = safe_float_convert(alt_elem.text)
                    
                    dist_elem = trkpt.find("ns:DistanceMeters", namespace)
                    if dist_elem is not None:
                        fields["distance"] = safe_float_convert(dist_elem.text)
                    
                    hr_elem = trkpt.find(".//ns:HeartRateBpm/ns:Value", namespace)
                    if hr_elem is not None:
                        fields["heart_rate"] = safe_float_convert(hr_elem.text)
                    
                    record = {
                        "measurement": "GPS",
                        "time": time_str,
                        "tags": {"ActivityID": activity_id},
                        "fields": fields
                    }
                    collected_records.append(record)
                    points_added += 1
        
        logging.info(f"Recorded {points_added} GPS points for {activity_id}")
    except ET.ParseError as e:
        logging.error(f"Failed to parse TCX XML for {activity_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing TCX data for {activity_id}: {e}")

# =============================================================================
# ## 🚀 Main Execution
# =============================================================================

def main():
    """Main function to orchestrate the data fetching and writing process."""
    global ACCESS_TOKEN, LOCAL_TIMEZONE, collected_records
    
    logging.info("\n--- Starting Fitbit data sync script ---")

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

    try:
        ACCESS_TOKEN = refresh_fitbit_tokens(CLIENT_ID, CLIENT_SECRET)
        LOCAL_TIMEZONE = get_user_timezone()

        # --- DATE HANDLING ---
        # For example, to fetch data from 5 days ago:
        # target_date = datetime.now(LOCAL_TIMEZONE) - timedelta(days=5)
        # To fetch data for a specific date, you can set it directly:
        # target_date = datetime(2023, 10, 1, tzinfo=LOCAL_TIMEZONE)
        target_date = datetime.now(LOCAL_TIMEZONE) - timedelta(days=1)
        date_str = target_date.strftime("%Y-%m-%d")

        start_date_str = date_str
        end_date_str = date_str
        date_list = [date_str]
        
        logging.info(f"Fetching data for date: {date_str} (timezone: {LOCAL_TIMEZONE})")

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
        
        logging.info("--- Fetching activities for target date ---")
        fetch_activities_for_date(start_date_str, end_date_str)

        # Filter out any None records before writing
        valid_records = [record for record in collected_records if record is not None]
        
        if valid_records:
            # For development: write to JSON file instead of InfluxDB
            # with open("dev_data/cromwell_fitbit_dev.json", "w") as f:
            #     json.dump(valid_records, f, indent=2, default=str)
            # logging.info(f"Wrote {len(valid_records)} records to dev_data/cromwell_fitbit_dev.json (development mode).")
            write_points_to_influxdb(valid_records, influx_client, influx_write_api)
        else:
            logging.warning("No valid records collected to write to InfluxDB.")

        logging.info(f"--- Script finished successfully. Total API requests made: {API_REQUEST_COUNT}, Records collected: {len(valid_records)} ---")

    except Exception as e:
        logging.error(f"Fatal error in main execution: {e}")
        sys.exit(1)
    finally:
        # Clean up
        if 'influx_client' in locals():
            try:
                influx_client.close()
            except:
                pass

if __name__ == "__main__":
    main()