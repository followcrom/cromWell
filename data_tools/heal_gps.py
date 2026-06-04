#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPS heal pass (Option B) -- RUNS ON THE VM, as its own cron job a little after
the main fitbit2s3 collection job.

Why: the phone uploads GPS to Fitbit lazily, so the 02:30 collection often stores
only a partial track. Fitbit completes it later. This job re-checks the last few
days of walks and, for any where Fitbit now serves a MORE COMPLETE track than we
stored, rewrites that day's S3 backup and records it in a manifest so the local
side can fold it into gps.parquet.

Safe & self-limiting:
  * Compares fresh-vs-stored GPS path length -- only writes when Fitbit has MORE
    than we hold (no churn once healthy; no reliance on distance units).
  * Only looks at a trailing window (WINDOW_DAYS); older walks are left alone.
  * Cron-safe token: refreshes and writes the rotated pair back to TOKEN_FILE_PATH
    in the same format fitbit2s3.py uses.

Usage (on the VM, from the repo dir):
    python data_tools/heal_gps.py            # default 5-day window
    python data_tools/heal_gps.py 7          # custom window
"""

import base64, io, gzip, json, math, os, sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import boto3
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE_PATH = os.getenv("TOKEN_FILE_PATH")

BUCKET = "followcrom"
PREFIX = "cromwell/fitbit/"
MANIFEST_KEY = f"{PREFIX}heal_manifest.json"
LOCAL_TZ = ZoneInfo("Europe/London")
NS = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

WINDOW_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
GROWTH = 1.05  # heal only if fresh path >= 5% longer than stored

# Uses default AWS creds/role on the VM (no named profile).
s3 = boto3.client("s3")


def log(m):
    print(f"{datetime.now(LOCAL_TZ).isoformat(timespec='seconds')}  {m}", flush=True)


def refresh_token():
    with open(TOKEN_FILE_PATH) as f:
        tokens = json.load(f)
    r = requests.post(
        "https://api.fitbit.com/oauth2/token",
        headers={"Authorization": "Basic " + base64.b64encode(
            f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        timeout=30)
    r.raise_for_status()
    d = r.json()
    with open(TOKEN_FILE_PATH, "w") as f:
        json.dump({"access_token": d["access_token"],
                   "refresh_token": d["refresh_token"]}, f)
    log("token refreshed (rotated pair written back)")
    return d["access_token"]


_TOKEN = None  # current access token; refreshed lazily only on 401


def api_get(url, accept_json=True, timeout=60):
    """GET using the existing access token; refresh-and-retry once on 401.
    Avoids an unconditional refresh so we don't rotate the token the main
    02:30 job is still relying on (its access token is valid for ~8h)."""
    global _TOKEN
    if _TOKEN is None:
        with open(TOKEN_FILE_PATH) as f:
            _TOKEN = json.load(f)["access_token"]
    hdr = {"Authorization": f"Bearer {_TOKEN}"}
    if accept_json:
        hdr["Accept"] = "application/json"
    r = requests.get(url, headers=hdr, timeout=timeout)
    if r.status_code == 401:
        log("access token expired -> refreshing")
        _TOKEN = refresh_token()
        hdr["Authorization"] = f"Bearer {_TOKEN}"
        r = requests.get(url, headers=hdr, timeout=timeout)
    r.raise_for_status()
    return r


def hav(a, b):
    R = 6371000.0; p = math.pi / 180
    x = (math.sin((b[0]-a[0])*p/2)**2 +
         math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin((b[1]-a[1])*p/2)**2)
    return 2*R*math.asin(math.sqrt(x))


def path_km(coords):
    return sum(hav(coords[i], coords[i+1]) for i in range(len(coords)-1))/1000 \
        if len(coords) > 1 else 0.0


def parse_tcx(text):
    """Trackpoints -> list of {time(UTC iso), fields}. TCX <Time> is LOCAL time."""
    root = ET.fromstring(text)
    out = []
    for tp in root.findall(".//ns:Trackpoint", NS):
        t = tp.find("ns:Time", NS)
        la = tp.find(".//ns:LatitudeDegrees", NS)
        lo = tp.find(".//ns:LongitudeDegrees", NS)
        if t is None or la is None or lo is None:
            continue
        s = t.text
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
        f = {"lat": float(la.text), "lon": float(lo.text)}
        for tag, key in (("ns:AltitudeMeters", "altitude"), ("ns:DistanceMeters", "distance")):
            e = tp.find(tag, NS)
            if e is not None:
                f[key] = float(e.text)
        hr = tp.find(".//ns:HeartRateBpm/ns:Value", NS)
        if hr is not None:
            f["heart_rate"] = float(hr.text)
        out.append({"time": dt.astimezone(timezone.utc).isoformat(), "fields": f})
    return out


def load_backup(date):
    key = f"{PREFIX}fitbit_backup_{date}.json.gz"
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
    except s3.exceptions.NoSuchKey:
        return None
    return json.loads(gzip.decompress(obj["Body"].read()).decode())


def stored_path_km(recs, aid):
    pts = sorted([r for r in recs if r["measurement"] == "GPS"
                  and r.get("tags", {}).get("ActivityID") == aid],
                 key=lambda r: r["time"])
    return path_km([(r["fields"]["lat"], r["fields"]["lon"]) for r in pts]), len(pts)


def main():
    today = datetime.now(LOCAL_TZ).date()
    tomorrow = (today + timedelta(days=1)).isoformat()
    cutoff = today - timedelta(days=WINDOW_DAYS)

    acts = api_get(
        f"https://api.fitbit.com/1/user/-/activities/list.json"
        f"?beforeDate={tomorrow}&sort=desc&limit=50&offset=0",
        timeout=30).json().get("activities", [])

    walks = [a for a in acts
             if a.get("activityName") == "Walk" and a.get("hasGps") and a.get("tcxLink")
             and datetime.strptime(a["startTime"][:10], "%Y-%m-%d").date() >= cutoff]
    log(f"window={WINDOW_DAYS}d  candidate walks: {len(walks)}")

    backups = {}      # date -> records (loaded once, mutated)
    dirty = set()     # dates needing re-upload
    healed = []       # manifest entries

    for w in walks:
        date = w["startTime"][:10]                      # local date == backup file name
        aid = f'{datetime.fromisoformat(w["startTime"]).astimezone(timezone.utc).isoformat()}-Walk'
        if date not in backups:
            backups[date] = load_backup(date)
        recs = backups[date]
        if recs is None:
            log(f"  {date} {aid}: no backup file, skipping")
            continue
        prev_km, prev_n = stored_path_km(recs, aid)
        fresh = parse_tcx(api_get(w["tcxLink"], accept_json=False, timeout=60).text)
        fresh_km = path_km([(p["fields"]["lat"], p["fields"]["lon"]) for p in fresh])

        if fresh_km >= max(prev_km * GROWTH, prev_km + 0.1) or prev_n == 0:
            kept = [r for r in recs if not (r["measurement"] == "GPS"
                    and r.get("tags", {}).get("ActivityID") == aid)]
            kept += [{"measurement": "GPS", "time": p["time"],
                      "tags": {"ActivityID": aid}, "fields": p["fields"]} for p in fresh]
            backups[date] = kept
            dirty.add(date)
            healed.append({"ts": datetime.now(timezone.utc).isoformat(),
                           "date": date, "aid": aid,
                           "prev_km": round(prev_km, 2), "fresh_km": round(fresh_km, 2),
                           "points": len(fresh)})
            log(f"  HEAL {date} {aid}: {prev_km:.2f}km/{prev_n}pts -> {fresh_km:.2f}km/{len(fresh)}pts")
        else:
            log(f"  ok   {date} {aid}: stored {prev_km:.2f}km already complete")

    for date in dirty:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="w") as f:
            f.write(json.dumps(backups[date], default=str).encode())
        buf.seek(0)
        s3.upload_fileobj(buf, BUCKET, f"{PREFIX}fitbit_backup_{date}.json.gz",
                          ExtraArgs={"ContentType": "application/json",
                                     "ContentEncoding": "gzip"})
        log(f"  uploaded healed backup {date}")

    if healed:
        try:
            existing = json.loads(gzip.decompress(
                s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)["Body"].read()).decode())
        except Exception:
            existing = []
        manifest = (existing + healed)[-500:]
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="w") as f:
            f.write(json.dumps(manifest).encode())
        buf.seek(0)
        s3.upload_fileobj(buf, BUCKET, MANIFEST_KEY,
                          ExtraArgs={"ContentType": "application/json",
                                     "ContentEncoding": "gzip"})
        log(f"manifest updated (+{len(healed)} entries)")
    log(f"done. healed {len(healed)} walk(s).")


if __name__ == "__main__":
    main()
