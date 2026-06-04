#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time repair: re-fetch the now-complete TCX for the phone-delayed walks
(20 May - 2 Jun 2026) and replace their partial GPS in both the S3 daily
backups and the local gps.parquet.

READ-ONLY against Fitbit (GETs only; no token refresh). Requires a valid
access token in env var FITBIT_AT. Run from the repo root.

Backups taken first:
  - S3 originals -> s3://followcrom/cromwell/fitbit_pre_gpsfix_20260604/
  - gps.parquet  -> data/gps.parquet.bak_gpsfix_20260604
"""

import os, io, gzip, json, math
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import boto3
import pandas as pd

LOCAL_TZ = ZoneInfo("Europe/London")

AT = os.environ["FITBIT_AT"]
H = {"Authorization": f"Bearer {AT}"}
NS = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

BUCKET = "followcrom"
PREFIX = "cromwell/fitbit/"
BACKUP_PREFIX = "cromwell/fitbit_pre_gpsfix_20260604/"
AWS_PROFILE = "surface"
GPS_PARQUET = "data/gps.parquet"

# Activity dates that have partial walks (cron-fetch date == activity date)
TARGET_DATES = ["2026-05-20", "2026-05-22", "2026-05-24", "2026-05-25",
                "2026-05-27", "2026-05-30", "2026-06-01", "2026-06-02"]

session = boto3.Session(profile_name=AWS_PROFILE)
s3 = session.client("s3")


def get(url, **kw):
    r = requests.get(url, headers=H, timeout=60, **kw)
    r.raise_for_status()
    return r


def parse_tcx(text):
    """Return list of GPS field-dicts in document order (mirrors get_tcx_data)."""
    root = ET.fromstring(text)
    out = []
    for tp in root.findall(".//ns:Trackpoint", NS):
        t = tp.find("ns:Time", NS)
        la = tp.find(".//ns:LatitudeDegrees", NS)
        lo = tp.find(".//ns:LongitudeDegrees", NS)
        if t is None or la is None or lo is None:
            continue
        # Fitbit TCX <Time> is LOCAL time (BST offset / or naive), NOT UTC.
        # Mirror safe_datetime_parse: honour an explicit offset, else localise
        # to Europe/London, then convert to UTC. (A naive .replace(tzinfo=utc)
        # here would shift BST activities +1h.)
        s = t.text
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
        tt = dt.astimezone(timezone.utc).isoformat()
        fields = {"lat": float(la.text), "lon": float(lo.text)}
        alt = tp.find("ns:AltitudeMeters", NS)
        if alt is not None:
            fields["altitude"] = float(alt.text)
        dist = tp.find("ns:DistanceMeters", NS)
        if dist is not None:
            fields["distance"] = float(dist.text)
        hr = tp.find(".//ns:HeartRateBpm/ns:Value", NS)
        if hr is not None:
            fields["heart_rate"] = float(hr.text)
        out.append({"time": tt, "fields": fields})
    return out


def activity_id(start_time_local, name):
    """ActivityID = corrected-UTC-isoformat + '-' + name (matches existing data)."""
    dt = datetime.fromisoformat(start_time_local).astimezone(timezone.utc)
    return f"{dt.isoformat()}-{name}"


def hav(a, b):
    R = 6371000.0; p = math.pi / 180
    x = (math.sin((b[0]-a[0])*p/2)**2 +
         math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin((b[1]-a[1])*p/2)**2)
    return 2*R*math.asin(math.sqrt(x))


def path_km(pts):
    c = [(p["fields"]["lat"], p["fields"]["lon"]) for p in pts]
    return sum(hav(c[i], c[i+1]) for i in range(len(c)-1))/1000 if len(c) > 1 else 0


# ---------------------------------------------------------------- fetch TCX
print("=== Fetching complete TCX for each target walk ===")
repairs = {}  # date -> list of {aid, gps:[records]}
for d in TARGET_DATES:
    before = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    acts = get(f"https://api.fitbit.com/1/user/-/activities/list.json"
               f"?beforeDate={before}&sort=desc&limit=20&offset=0").json()["activities"]
    walks = [a for a in acts if a["startTime"][:10] == d
             and a["activityName"] == "Walk" and a.get("hasGps") and a.get("tcxLink")]
    repairs[d] = []
    for w in walks:
        aid = activity_id(w["startTime"], w["activityName"])
        pts = parse_tcx(get(w["tcxLink"]).text)
        repairs[d].append({"aid": aid, "pts": pts})
        rep_km = (w.get("distance") or 0) * 1.60934
        print(f"  {d} {aid}: {len(pts)} pts, {path_km(pts):.2f} km (reported {rep_km:.2f} km)")

# ---------------------------------------------------------------- backup + update S3
print("\n=== Updating S3 daily backups (originals copied to pre_gpsfix prefix) ===")
for d in TARGET_DATES:
    key = f"{PREFIX}fitbit_backup_{d}.json.gz"
    s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": key},
                   Key=f"{BACKUP_PREFIX}fitbit_backup_{d}.json.gz")
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    recs = json.loads(gzip.decompress(obj["Body"].read()).decode())
    aids = {r["aid"] for r in repairs[d]}
    # drop old GPS for these activity IDs, keep everything else
    kept = [r for r in recs if not (r["measurement"] == "GPS"
            and r.get("tags", {}).get("ActivityID") in aids)]
    new_gps = []
    for rep in repairs[d]:
        for p in rep["pts"]:
            new_gps.append({"measurement": "GPS", "time": p["time"],
                            "tags": {"ActivityID": rep["aid"]}, "fields": p["fields"]})
    final = kept + new_gps
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="w") as f:
        f.write(json.dumps(final, default=str).encode())
    buf.seek(0)
    s3.upload_fileobj(buf, BUCKET, key,
                      ExtraArgs={"ContentType": "application/json",
                                 "ContentEncoding": "gzip"})
    print(f"  {d}: replaced GPS -> {len(new_gps)} pts (file now {len(final)} recs)")

# ---------------------------------------------------------------- update parquet
print("\n=== Updating gps.parquet ===")
gps = pd.read_parquet(GPS_PARQUET)
gps.to_parquet("data/gps.parquet.bak_gpsfix_20260604", index=False, compression="snappy")
all_aids = {rep["aid"] for d in TARGET_DATES for rep in repairs[d]}
before_n = len(gps)
gps = gps[~gps["tag_ActivityID"].isin(all_aids)].copy()
rows = []
for d in TARGET_DATES:
    for rep in repairs[d]:
        for p in rep["pts"]:
            row = {"time": p["time"], "tag_ActivityID": rep["aid"]}
            for k, v in p["fields"].items():
                row[f"field_{k}"] = v
            rows.append(row)
new = pd.DataFrame(rows)
new["time"] = pd.to_datetime(new["time"], utc=True)
new["date"] = new["time"].dt.tz_convert("Europe/London").dt.date.astype(str)
# align columns with existing parquet
for c in gps.columns:
    if c not in new.columns:
        new[c] = pd.NA
new = new[gps.columns]
gps["time"] = pd.to_datetime(gps["time"], utc=True)
out = pd.concat([gps, new], ignore_index=True)
out.to_parquet(GPS_PARQUET, index=False, compression="snappy")
print(f"  parquet rows: {before_n} -> {len(out)}  (added {len(new)} repaired GPS rows)")
print("\nDONE.")
