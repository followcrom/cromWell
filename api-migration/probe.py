#!/usr/bin/env python3
"""
Probe the Google Health API for one day of every data type CromWell needs.

Saves each raw response under probe_out/<date>/ and prints a one-line summary
per data type, so the Fitbit -> Google Health field mapping can be settled from
real payloads before the collector is written.

Usage (run from api-migration/):
    python probe.py                 # yesterday
    python probe.py 2026-10-09      # a specific civil date
"""

import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPE_PREFIX = "https://www.googleapis.com/auth/googlehealth."
SCOPES = [SCOPE_PREFIX + s for s in (
    "activity_and_fitness.readonly",
    "health_metrics_and_measurements.readonly",
    "sleep.readonly",
    "location.readonly",
    "profile.readonly",
)]

CLIENT_SECRETS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
BASE_URL = "https://health.googleapis.com/v4"
OUT_DIR = Path("probe_out")

# data type -> candidate filter fields, tried in order until one is accepted.
# {t} is the snake_case type name used inside filter expressions.
INTERVAL = ["{t}.interval.civil_start_time"]
SAMPLE = ["{t}.sample_time.civil_time", "{t}.sample_time.physical_time"]
DAILY = ["{t}.date", "{t}.civil_date", "{t}.day"]
SESSION = ["{t}.interval.civil_start_time", "{t}.interval.civil_end_time"]

DATA_TYPES = {
    # activity_and_fitness
    "steps": INTERVAL,
    "distance": INTERVAL,
    "active-minutes": INTERVAL,
    "active-zone-minutes": INTERVAL,
    "activity-level": INTERVAL,
    "sedentary-period": INTERVAL,
    "time-in-heart-rate-zone": INTERVAL,
    "exercise": SESSION,
    # health_metrics_and_measurements
    "heart-rate": SAMPLE,
    "heart-rate-variability": SAMPLE,
    "oxygen-saturation": SAMPLE,
    "respiratory-rate-sleep-summary": SAMPLE,
    "weight": SAMPLE,
    "daily-resting-heart-rate": DAILY,
    "daily-heart-rate-zones": DAILY,
    "daily-heart-rate-variability": DAILY,
    "daily-respiratory-rate": DAILY,
    "daily-oxygen-saturation": DAILY,
    "daily-sleep-temperature-derivations": DAILY,
    # sleep
    "sleep": SESSION,
}

# Daily totals that replace Fitbit's activities/tracker/* summaries.
DAILY_ROLLUPS = ["steps", "distance", "total-calories", "active-minutes"]


def get_authenticated_session() -> requests.Session:
    """Load the cached token (with whatever scopes it was granted) or run the consent flow."""
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    granted = set(creds.scopes or [])
    missing = [s.replace(SCOPE_PREFIX, "") for s in SCOPES if s not in granted]
    if missing:
        print(f"⚠️  Token is missing scopes: {', '.join(missing)}")
        print(f"   Delete {TOKEN_FILE} and re-run to consent to all five.\n")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {creds.token}", "Accept": "application/json"})
    return session


def request_with_backoff(session, method, url, **kwargs):
    """Send a request, retrying 429/504 with exponential backoff."""
    for attempt in range(5):
        response = session.request(method, url, timeout=60, **kwargs)
        if response.status_code not in (429, 504):
            return response
        time.sleep(2 ** attempt)
    return response


def list_data_points(session, data_type, filter_expr, page_size=10000):
    """
    Fetch every page of a dataPoints list call.

    Returns (data_points, error_response). error_response is None on success.
    """
    url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints"
    # exercise and sleep are capped at 25 per page by the API
    if data_type in ("exercise", "sleep"):
        page_size = 25
    params = {"filter": filter_expr, "pageSize": page_size}
    points = []
    while True:
        response = request_with_backoff(session, "GET", url, params=params)
        if response.status_code != 200:
            return points, response
        body = response.json()
        points.extend(body.get("dataPoints", []))
        token = body.get("nextPageToken")
        if not token:
            return points, None
        params["pageToken"] = token


def error_summary(response):
    try:
        err = response.json().get("error", {})
        return f"{response.status_code} {err.get('status', '')}: {err.get('message', '')[:300]}"
    except ValueError:
        return f"{response.status_code}: {response.text[:300]}"


def save(day_dir, name, payload):
    with open(day_dir / f"{name}.json", "w") as f:
        json.dump(payload, f, indent=2)


def probe_data_type(session, data_type, candidates, day, day_dir):
    """Try each candidate filter field for one data type and save the first that works."""
    snake = data_type.replace("-", "_")
    next_day = day + timedelta(days=1)
    last_error = None
    for field in candidates:
        field = field.format(t=snake)
        if field.endswith("physical_time"):
            lo, hi = f"{day}T00:00:00Z", f"{next_day}T00:00:00Z"
        elif field.endswith(("civil_time", "civil_start_time", "civil_end_time")):
            lo, hi = f"{day}T00:00:00", f"{next_day}T00:00:00"
        else:
            lo, hi = str(day), str(next_day)
        filter_expr = f'{field} >= "{lo}" AND {field} < "{hi}"'
        points, error = list_data_points(session, data_type, filter_expr)
        if error is None:
            save(day_dir, data_type, {"filter": filter_expr, "dataPoints": points})
            payload_keys = sorted(points[0].get(snake_to_camel(snake), points[0]).keys()) if points else []
            print(f"✅ {data_type:38s} {len(points):6d} points  filter={field}  keys={payload_keys}")
            return points
        last_error = error_summary(error)
        if error.status_code in (401, 403):
            break  # scope problem - other filter fields won't help
    print(f"❌ {data_type:38s} {last_error}")
    save(day_dir, f"{data_type}.error", {"error": last_error})
    return []


def snake_to_camel(name):
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def probe_daily_rollup(session, data_type, day, day_dir):
    """Fetch the civil-day total for one data type."""
    url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
    civil = {"year": day.year, "month": day.month, "day": day.day}
    body = {
        "range": {
            "start": {"date": civil, "time": {"hours": 0, "minutes": 0, "seconds": 0, "nanos": 0}},
            "end": {"date": civil, "time": {"hours": 23, "minutes": 59, "seconds": 59, "nanos": 0}},
        },
        "windowSizeDays": 1,
    }
    response = request_with_backoff(session, "POST", url, json=body)
    if response.status_code != 200:
        print(f"❌ {data_type + ' (dailyRollUp)':38s} {error_summary(response)}")
        return
    payload = response.json()
    save(day_dir, f"{data_type}.dailyRollUp", payload)
    print(f"✅ {data_type + ' (dailyRollUp)':38s} {json.dumps(payload)[:160]}")


def probe_tcx(session, exercises, day_dir):
    """Export the TCX for the first exercise that has GPS."""
    for point in exercises:
        if not point.get("exercise", {}).get("exerciseMetadata", {}).get("hasGps"):
            continue
        name = point.get("name") or point.get("dataPointName")
        response = request_with_backoff(
            session, "GET", f"{BASE_URL}/{name}:exportExerciseTcx", params={"alt": "media"}
        )
        if response.status_code != 200:
            print(f"❌ {'exercise TCX export':38s} {error_summary(response)}")
            return
        (day_dir / "exercise.tcx").write_text(response.text)
        print(f"✅ {'exercise TCX export':38s} {response.text.count('<Trackpoint>')} trackpoints")
        return
    print(f"➖ {'exercise TCX export':38s} no exercise with GPS on this date")


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=1)
    day_dir = OUT_DIR / str(day)
    day_dir.mkdir(parents=True, exist_ok=True)

    session = get_authenticated_session()
    print(f"Probing Google Health API for {day} at {datetime.now():%H:%M:%S}\n")

    results = {}
    for data_type, candidates in DATA_TYPES.items():
        results[data_type] = probe_data_type(session, data_type, candidates, day, day_dir)

    print()
    for data_type in DAILY_ROLLUPS:
        probe_daily_rollup(session, data_type, day, day_dir)

    print()
    probe_tcx(session, results.get("exercise", []), day_dir)
    print(f"\nRaw responses saved to {day_dir}/")


if __name__ == "__main__":
    main()
