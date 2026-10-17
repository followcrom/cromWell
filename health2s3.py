#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script fetches personal health data (e.g., heart rate, sleep, steps, activity)
via the Google Health API and backs it up to AWS S3 as gzipped JSON files. It replaces
fitbit2s3.py (legacy Fitbit Web API, switched off 2026-10-30) and writes the same
record format, so sync_from_s3.py and the dashboard are unaffected.

It's designed to be run once daily via a cron job, fetching the previous day.

Usage:
    python health2s3.py                      # yesterday -> S3
    python health2s3.py 2026-10-01           # a specific civil date -> S3
    python health2s3.py 2026-10-01 --dry-run # write ./health_backup_<date>.json.gz, no upload
"""
import argparse
import boto3
import gzip
import io
import json
import logging
import os
import sys
import time
import pytz
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Load variables from .env file
load_dotenv()

# =============================================================================
# ## ⚙️ Configuration Variables
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# --- Logging Configuration ---
HEALTH_LOG_FILE_PATH = os.environ.get("HEALTH_LOG_FILE_PATH")
# OVERWRITE_LOG_FILE: Set to True to clear the log file on each run / Set to False to append to the log file
OVERWRITE_LOG_FILE = True

# --- Google Health API Configuration ---
# The token file is created by the one-off consent flow (api-migration/probe.py) on a
# machine with a browser, then copied here. This script only ever refreshes it.
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", str(SCRIPT_DIR / "api-migration" / "token.json"))
BASE_URL = "https://health.googleapis.com/v4"
DEVICENAME = os.getenv("DEVICENAME", "PixelWatch3")

# --- Storage ---
S3_BUCKET = os.getenv("HEALTH_S3_BUCKET", "followcrom")
# Kept apart from the legacy cromwell/fitbit/ backups until the two have been compared.
S3_PREFIX = os.getenv("HEALTH_S3_PREFIX", "cromwell/google_health/fitbit_backup")

# --- Script Behavior ---
# Daily summaries are stamped at noon in this timezone, and "yesterday" is taken from it.
HOME_TIMEZONE = pytz.timezone(os.getenv("HOME_TIMEZONE", "Europe/London"))
MAX_RETRY = 5
TCX_FETCH_LIMIT = 10

# --- Unit conversions (the legacy backups are in en_US units) ---
MM_PER_MILE = 1_609_344
MM_PER_FOOT = 304.8

# --- Global Variables (do not change) ---
SESSION = None
collected_records = []
API_REQUEST_COUNT = 0

# =============================================================================
# ## 📝 Logging Setup
# =============================================================================

log_handlers = [logging.StreamHandler(sys.stdout)]
if HEALTH_LOG_FILE_PATH:
    if OVERWRITE_LOG_FILE:
        with open(HEALTH_LOG_FILE_PATH, "w"): pass
    log_handlers.append(logging.FileHandler(HEALTH_LOG_FILE_PATH, mode='a'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=log_handlers
)

# =============================================================================
# ## 🌐 API and Storage Functions
# =============================================================================

def get_authenticated_session():
    """Loads the cached Google token, refreshing it if expired, and returns a session."""
    if not os.path.exists(GOOGLE_TOKEN_FILE):
        raise RuntimeError(f"Token file not found at {GOOGLE_TOKEN_FILE}. Run the consent flow (api-migration/probe.py) first.")

    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE)
    if not creds.valid:
        if not creds.refresh_token:
            raise RuntimeError("Token has no refresh token. Re-run the consent flow (api-migration/probe.py).")
        creds.refresh(Request())
        with open(GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        logging.info("Refreshed Google access token.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {creds.token}", "Accept": "application/json"})
    return session


def request_data_from_health(method, url, **kwargs):
    """Makes a request to the Google Health API, retrying rate limits and server errors."""
    global API_REQUEST_COUNT
    for attempt in range(MAX_RETRY):
        API_REQUEST_COUNT += 1
        try:
            response = SESSION.request(method, url, timeout=60, **kwargs)
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Connection error on {url}: {e}. Retrying...")
            time.sleep(2 ** attempt)
            continue
        if response.status_code in (429, 500, 502, 503, 504):
            logging.warning(f"HTTP {response.status_code} on {url}. Retrying...")
            time.sleep(2 ** attempt)
            continue
        if response.status_code != 200:
            logging.error(f"HTTP {response.status_code} on {url}: {response.text[:300]}")
            return None
        return response
    logging.error(f"Giving up on {url} after {MAX_RETRY} attempts.")
    return None


def list_data_points(data_type, time_field, start, end):
    """
    Fetches every page of data points for one data type.

    time_field is the filter field after the type name (e.g. 'interval.civil_start_time');
    start/end are the already-formatted bounds of a closed-open range.
    """
    snake = data_type.replace("-", "_")
    params = {
        "filter": f'{snake}.{time_field} >= "{start}" AND {snake}.{time_field} < "{end}"',
        # exercise and sleep are capped at 25 per page by the API
        "pageSize": 25 if data_type in ("exercise", "sleep") else 10000,
    }
    points = []
    while True:
        response = request_data_from_health("GET", f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints", params=params)
        if response is None:
            logging.warning(f"Could not fetch {data_type}; continuing with {len(points)} points.")
            return points
        body = response.json()
        points.extend(body.get("dataPoints", []))
        if not body.get("nextPageToken"):
            return points
        params["pageToken"] = body["nextPageToken"]


def daily_rollup(data_type, day):
    """Fetches the civil-day total for one data type. Returns the rollup payload or {}."""
    civil = {"year": day.year, "month": day.month, "day": day.day}
    body = {
        "range": {
            "start": {"date": civil, "time": {"hours": 0, "minutes": 0, "seconds": 0, "nanos": 0}},
            "end": {"date": civil, "time": {"hours": 23, "minutes": 59, "seconds": 59, "nanos": 0}},
        },
        "windowSizeDays": 1,
    }
    response = request_data_from_health("POST", f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp", json=body)
    if response is None:
        return {}
    rollups = response.json().get("rollupDataPoints", [])
    return rollups[0] if rollups else {}

# =============================================================================
# ## 🧰 Helpers
# =============================================================================

def parse_time(time_string):
    """Parses an API timestamp (UTC 'Z' or explicit offset) into an aware UTC datetime."""
    return datetime.fromisoformat(time_string.replace("Z", "+00:00")).astimezone(timezone.utc)


def utc_iso(time_string):
    """API timestamp -> the UTC ISO string format used throughout the backups."""
    return parse_time(time_string).isoformat()


def offset_seconds(offset_string):
    """'3600s' -> 3600"""
    return int(float(str(offset_string).rstrip("s") or 0))


def daily_time(day):
    """Daily measurements are stamped at local noon to avoid timezone shifting issues."""
    return HOME_TIMEZONE.localize(datetime(day.year, day.month, day.day, 12)).astimezone(pytz.utc).isoformat()


def civil_bounds(day):
    return f"{day}T00:00:00", f"{day + timedelta(days=1)}T00:00:00"


def date_bounds(day):
    return str(day), str(day + timedelta(days=1))


def add_record(measurement, time_str, fields, tags=None):
    collected_records.append({
        "measurement": measurement,
        "time": time_str,
        "tags": tags if tags is not None else {"Device": DEVICENAME},
        "fields": fields
    })

# =============================================================================
# ## 📥 Data Fetching Functions
# =============================================================================

def get_intraday_heart_rate(day):
    """Fetches per-second heart rate samples for a civil day."""
    points = list_data_points("heart-rate", "sample_time.civil_time", *civil_bounds(day))
    for point in points:
        sample = point["heartRate"]
        add_record("HeartRate_Intraday", utc_iso(sample["sampleTime"]["physicalTime"]),
                   {"value": float(sample["beatsPerMinute"])})
    logging.info(f"Recorded {len(points)} points for HeartRate_Intraday on {day}")


def get_intraday_steps(day):
    """
    Fetches per-minute steps for a civil day.

    The API only returns minutes that have steps; the legacy backups held every
    minute of the day, so the zero minutes are filled back in.
    """
    points = list_data_points("steps", "interval.civil_start_time", *civil_bounds(day))
    steps_by_minute = {}
    for point in points:
        interval = point["steps"]["interval"]
        minute = parse_time(interval["startTime"])
        steps_by_minute[minute] = steps_by_minute.get(minute, 0.0) + float(point["steps"]["count"])

    # Civil midnight in UTC, using the offsets the watch actually recorded with
    # (so a day abroad, or one that changes timezone, still spans the right minutes).
    home_start = HOME_TIMEZONE.localize(datetime(day.year, day.month, day.day))
    home_end = HOME_TIMEZONE.localize(datetime(day.year, day.month, day.day) + timedelta(days=1))
    if points:
        ordered = sorted(points, key=lambda p: p["steps"]["interval"]["startTime"])
        first, last = ordered[0]["steps"]["interval"], ordered[-1]["steps"]["interval"]
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(seconds=offset_seconds(first["startUtcOffset"]))
        day_end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1) - timedelta(seconds=offset_seconds(last["startUtcOffset"]))
    else:
        day_start, day_end = home_start.astimezone(timezone.utc), home_end.astimezone(timezone.utc)

    minute = day_start
    count = 0
    while minute < day_end:
        add_record("Steps_Intraday", minute.isoformat(), {"value": steps_by_minute.get(minute, 0.0)})
        minute += timedelta(minutes=1)
        count += 1
    logging.info(f"Recorded {count} points for Steps_Intraday on {day} ({len(points)} with steps)")


def get_activity_summaries(day):
    """Fetches daily activity summaries (steps, distance, calories, active minutes, zones)."""
    time_str = daily_time(day)

    steps = daily_rollup("steps", day).get("steps", {}).get("countSum")
    if steps is not None:
        add_record("Activity-steps", time_str, {"value": float(steps)})

    distance_mm = daily_rollup("distance", day).get("distance", {}).get("millimetersSum")
    if distance_mm is not None:
        add_record("Activity-distance", time_str, {"value": float(distance_mm) / MM_PER_MILE})

    calories = daily_rollup("total-calories", day).get("totalCalories", {}).get("kcalSum")
    if calories is not None:
        add_record("Activity-calories", time_str, {"value": float(round(calories))})

    # Active minutes by level. Sedentary is whatever is left of the day.
    active = daily_rollup("active-minutes", day).get("activeMinutes", {})
    level_minutes = {"LIGHT": 0.0, "MODERATE": 0.0, "VIGOROUS": 0.0}
    for item in active.get("activeMinutesRollupByActivityLevel", []):
        level = "VIGOROUS" if item.get("activityLevel") == "PEAK" else item.get("activityLevel")
        level_minutes[level] = level_minutes.get(level, 0.0) + float(item.get("activeMinutesSum", 0))
    add_record("Activity-minutesLightlyActive", time_str, {"value": level_minutes["LIGHT"]})
    add_record("Activity-minutesFairlyActive", time_str, {"value": level_minutes["MODERATE"]})
    add_record("Activity-minutesVeryActive", time_str, {"value": level_minutes["VIGOROUS"]})
    add_record("Activity-minutesSedentary", time_str, {"value": 1440.0 - sum(level_minutes.values())})
    logging.info("Recorded Activity summaries.")

    # Heart rate zones: one data point per minute, named light/moderate/vigorous/peak.
    zone_points = list_data_points("time-in-heart-rate-zone", "interval.civil_start_time", *civil_bounds(day))
    if zone_points:
        zone_names = {"MODERATE": "Fat Burn", "VIGOROUS": "Cardio", "PEAK": "Peak"}
        zones = {"Fat Burn": 0.0, "Cardio": 0.0, "Peak": 0.0}
        for point in zone_points:
            name = zone_names.get(point["timeInHeartRateZone"].get("heartRateZoneType"))
            if name:
                zones[name] += 1.0
        zones["Out of Range"] = 1440.0 - sum(zones.values())
        add_record("HR_Zones", time_str, zones)

    for point in list_data_points("daily-resting-heart-rate", "date", *date_bounds(day)):
        add_record("RestingHR", time_str, {"value": float(point["dailyRestingHeartRate"]["beatsPerMinute"])})
    logging.info("Recorded Heart Rate Zone and Resting HR summaries.")


def get_daily_summaries(day):
    """Fetches various daily summaries (HRV, SpO2, Skin Temp, etc.)."""
    time_str = daily_time(day)

    for point in list_data_points("daily-heart-rate-variability", "date", *date_bounds(day)):
        hrv = point["dailyHeartRateVariability"]
        fields = {}
        if "averageHeartRateVariabilityMilliseconds" in hrv:
            fields["dailyRmssd"] = float(hrv["averageHeartRateVariabilityMilliseconds"])
        if "deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds" in hrv:
            fields["deepRmssd"] = float(hrv["deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds"])
        if fields:
            add_record("HRV", time_str, fields)
    logging.info("Recorded HRV summary.")

    for point in list_data_points("daily-respiratory-rate", "date", *date_bounds(day)):
        add_record("BreathingRate", time_str, {"value": float(point["dailyRespiratoryRate"]["breathsPerMinute"])})
    logging.info("Recorded Breathing Rate summary.")

    for point in list_data_points("daily-sleep-temperature-derivations", "date", *date_bounds(day)):
        temp = point["dailySleepTemperatureDerivations"]
        if "nightlyTemperatureCelsius" in temp and "baselineTemperatureCelsius" in temp:
            relative = float(temp["nightlyTemperatureCelsius"]) - float(temp["baselineTemperatureCelsius"])
            # Fitbit (en_US) reported this delta in °F; keep that unit so the history stays continuous.
            add_record("SkinTemperature", time_str, {"nightlyRelative": round(relative * 1.8, 1)})
    logging.info("Recorded Skin Temperature summary.")

    for point in list_data_points("daily-oxygen-saturation", "date", *date_bounds(day)):
        spo2 = point["dailyOxygenSaturation"]
        fields = {}
        for key, source in (("avg", "averagePercentage"), ("max", "upperBoundPercentage"), ("min", "lowerBoundPercentage")):
            if source in spo2:
                fields[key] = float(spo2[source])
        if fields:
            add_record("SPO2_Daily", time_str, fields)
    logging.info("Recorded Daily SpO2 summary.")

    for point in list_data_points("weight", "sample_time.civil_time", *civil_bounds(day)):
        weight = point["weight"]
        # NOTE: the legacy Fitbit backups stored pounds in this field (en_US units).
        add_record("Weight", utc_iso(weight["sampleTime"]["physicalTime"]),
                   {"weight_kg": round(float(weight["weightGrams"]) / 1000, 1)},
                   tags={"Source": point.get("dataSource", {}).get("platform", "Unknown")})
    logging.info("Recorded Weight summary.")


def get_sleep_data(day):
    """Fetches detailed sleep data, including stages and efficiency, for sleeps ending on the day."""
    sleep_level_map = {'AWAKE': 3, 'REM': 2, 'LIGHT': 1, 'DEEP': 0, 'ASLEEP': 1, 'RESTLESS': 2}
    points = list_data_points("sleep", "interval.civil_end_time", *civil_bounds(day))
    for point in points:
        sleep = point["sleep"]
        summary = sleep.get("summary", {})
        stage_minutes = {s.get("type"): float(s.get("minutes", 0)) for s in summary.get("stagesSummary", [])}
        is_main_sleep = str(sleep.get("metadata", {}).get("mainSleep", False))

        minutes_asleep = float(summary.get("minutesAsleep", 0))
        minutes_in_bed = float(summary.get("minutesInSleepPeriod", 0))

        add_record("SleepSummary", utc_iso(sleep["interval"]["startTime"]), {
            'efficiency': float(round(100 * minutes_asleep / minutes_in_bed)) if minutes_in_bed else 0.0,
            'minutesAsleep': minutes_asleep,
            'minutesInBed': minutes_in_bed,
            'minutesAwake': float(summary.get("minutesAwake", 0)),
            'minutesLight': stage_minutes.get("LIGHT", stage_minutes.get("ASLEEP", 0.0)),
            'minutesREM': stage_minutes.get("REM", stage_minutes.get("RESTLESS", 0.0)),
            'minutesDeep': stage_minutes.get("DEEP", 0.0),
            'endTime': utc_iso(sleep["interval"]["endTime"])
        }, tags={"Device": DEVICENAME, "isMainSleep": is_main_sleep})

        # Sleep stages detail
        for stage in sleep.get("stages", []):
            duration = (parse_time(stage["endTime"]) - parse_time(stage["startTime"])).total_seconds()
            add_record("SleepLevels", utc_iso(stage["startTime"]), {
                'level': float(sleep_level_map.get(stage.get("type"), -1)),
                'duration_seconds': duration
            }, tags={"Device": DEVICENAME, "isMainSleep": is_main_sleep})
    logging.info(f"Recorded {len(points)} sleep logs.")


def fetch_activities_for_date(day):
    """Fetches exercises that started on the day, plus the GPS track for those that have one."""
    points = list_data_points("exercise", "interval.civil_start_time", *civil_bounds(day))
    if not points:
        logging.info(f"No activities found for {day}.")
        return

    logging.info(f"Fetched {len(points)} activity logs for {day}.")
    tcx_fetched_count = 0

    for point in points:
        exercise = point["exercise"]
        metrics = exercise.get("metricsSummary", {})
        start = parse_time(exercise["interval"]["startTime"])
        end = parse_time(exercise["interval"]["endTime"])
        utc_time = start.isoformat()
        activity_name = exercise.get("displayName", "Activity")
        activity_id = f"{utc_time}-{activity_name}"
        has_gps = bool(exercise.get("exerciseMetadata", {}).get("hasGps"))

        duration_ms = (end - start).total_seconds() * 1000
        active_seconds = float(str(exercise.get("activeDuration", "0s")).rstrip("s") or 0)
        fields = {
            "duration": duration_ms,
            "originalDuration": duration_ms,
            "activeDuration": active_seconds * 1000,
            "inProgress": 0.0,
        }
        if "caloriesKcal" in metrics:
            fields["calories"] = float(metrics["caloriesKcal"])
        if "averageHeartRateBeatsPerMinute" in metrics:
            fields["averageHeartRate"] = float(metrics["averageHeartRateBeatsPerMinute"])
        if "steps" in metrics:
            fields["steps"] = float(metrics["steps"])
        if "elevationGainMillimeters" in metrics:
            fields["elevationGain"] = float(metrics["elevationGainMillimeters"]) / MM_PER_FOOT
        if "activeZoneMinutes" in metrics:
            fields["hasActiveZoneMinutes"] = 1.0
        if has_gps:
            fields["hasGps"] = 1.0
        if "distanceMillimeters" in metrics:
            miles = float(metrics["distanceMillimeters"]) / MM_PER_MILE
            fields["distance"] = miles
            if active_seconds:
                fields["speed"] = miles / (active_seconds / 3600)  # mph
        if "averagePaceSecondsPerMeter" in metrics:
            fields["pace"] = float(metrics["averagePaceSecondsPerMeter"]) * MM_PER_MILE / 1000  # seconds per mile

        add_record("ActivityRecords", utc_time, fields, tags={"ActivityName": activity_name})

        if has_gps and point.get("name") and tcx_fetched_count < TCX_FETCH_LIMIT:
            logging.info(f"Found GPS data for activity: {activity_name}. Attempting to fetch.")
            get_tcx_data(point["name"], activity_id)
            tcx_fetched_count += 1


def get_tcx_data(data_point_name, activity_id):
    """Exports an exercise as TCX and parses its GPS trackpoints."""
    response = request_data_from_health("GET", f"{BASE_URL}/{data_point_name}:exportExerciseTcx", params={"alt": "media"})
    if response is None:
        logging.error(f"Failed to fetch TCX data for {activity_id}")
        return

    try:
        root = ET.fromstring(response.text)
        namespace = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
        trackpoints = root.findall(".//ns:Trackpoint", namespace)

        points_added = 0
        for trkpt in trackpoints:
            time_elem = trkpt.find("ns:Time", namespace)
            lat_elem = trkpt.find(".//ns:LatitudeDegrees", namespace)
            lon_elem = trkpt.find(".//ns:LongitudeDegrees", namespace)

            if time_elem is not None and lat_elem is not None and lon_elem is not None:
                # TCX <Time> carries an explicit UTC offset; a naive value would be local time.
                point_time = datetime.fromisoformat(time_elem.text.replace("Z", "+00:00"))
                if point_time.tzinfo is None:
                    point_time = HOME_TIMEZONE.localize(point_time)

                fields = {"lat": float(lat_elem.text), "lon": float(lon_elem.text)}

                # Optional fields
                alt_elem = trkpt.find("ns:AltitudeMeters", namespace)
                if alt_elem is not None:
                    fields["altitude"] = float(alt_elem.text)

                dist_elem = trkpt.find("ns:DistanceMeters", namespace)
                if dist_elem is not None:
                    fields["distance"] = float(dist_elem.text)

                hr_elem = trkpt.find(".//ns:HeartRateBpm/ns:Value", namespace)
                if hr_elem is not None:
                    fields["heart_rate"] = float(hr_elem.text)

                add_record("GPS", point_time.astimezone(timezone.utc).isoformat(), fields, tags={"ActivityID": activity_id})
                points_added += 1

        logging.info(f"Recorded {points_added} GPS points for {activity_id}")
    except ET.ParseError as e:
        logging.error(f"Failed to parse TCX XML for {activity_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing TCX data for {activity_id}: {e}")

# =============================================================================
# ## ☁️ Backup
# =============================================================================

def compress_records(records):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='w') as f:
        f.write(json.dumps(records, default=str).encode("utf-8"))
    buf.seek(0)
    return buf


def backup_to_s3_daily(records, day):
    """Upload records to S3 as a gzipped JSON file named for the day they cover."""
    key = f"{S3_PREFIX}_{day}.json.gz"
    boto3.client("s3").upload_fileobj(
        compress_records(records),
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": "application/json", "ContentEncoding": "gzip"}
    )
    logging.info(f"✅ Uploaded {len(records)} records to s3://{S3_BUCKET}/{key}")

# =============================================================================
# ## 🚀 Main Execution
# =============================================================================

def main():
    """Main function to orchestrate the data fetching and writing process."""
    global SESSION

    parser = argparse.ArgumentParser(description="Back up one day of Google Health data to S3")
    parser.add_argument("date", nargs="?", help="Civil date to fetch (YYYY-MM-DD). Default: yesterday")
    parser.add_argument("--dry-run", action="store_true", help="Write a local json.gz instead of uploading to S3")
    args = parser.parse_args()

    logging.info("--- Starting Google Health data sync script ---")

    try:
        day = date.fromisoformat(args.date) if args.date else (datetime.now(HOME_TIMEZONE) - timedelta(days=1)).date()
        SESSION = get_authenticated_session()

        logging.info(f"Fetching data for date: {day}")

        logging.info("--- Fetching intraday data ---")
        get_intraday_heart_rate(day)
        get_intraday_steps(day)

        logging.info("--- Fetching daily and summary data ---")
        get_daily_summaries(day)
        get_activity_summaries(day)
        get_sleep_data(day)

        logging.info("--- Fetching activities for target date ---")
        fetch_activities_for_date(day)

        if not collected_records:
            logging.warning("No valid records collected.")
        elif args.dry_run:
            out_file = Path(f"health_backup_{day}.json.gz")
            out_file.write_bytes(compress_records(collected_records).getvalue())
            logging.info(f"✅ Dry run: wrote {len(collected_records)} records to {out_file}")
        else:
            backup_to_s3_daily(collected_records, day)

        logging.info(f"--- Script finished successfully for {day}. Total API requests made: {API_REQUEST_COUNT}, Records collected: {len(collected_records)} ---\n")

    except Exception as e:
        logging.error(f"Fatal error in main execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
