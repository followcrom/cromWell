#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-off diagnostic: fetch the raw TCX for a single activity straight from the
Fitbit API and report exactly how many trackpoints / GPS positions it contains
and the route geometry. Compares the *source* TCX against what our pipeline
stores, to determine whether Fitbit serves a partial track or whether
get_tcx_data() in fitbit2s3.py is dropping points.

SAFE TO RUN ON THE VM: it refreshes the token and writes the rotated pair back
to TOKEN_FILE_PATH in the exact same format as fitbit2s3.py, so the nightly cron
stays consistent. Run it from the same directory as fitbit2s3.py / .env.

Usage:
    python diagnose_tcx.py                 # defaults to 2026-05-30, "Walk"
    python diagnose_tcx.py 2026-05-30 Walk
"""

import base64
import json
import math
import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE_PATH = os.getenv("TOKEN_FILE_PATH")

TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-05-30"
TARGET_NAME = sys.argv[2] if len(sys.argv) > 2 else "Walk"

TCX_NS = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}


def refresh_token():
    """Refresh the access token and write the rotated pair back (cron-safe)."""
    with open(TOKEN_FILE_PATH, "r") as f:
        tokens = json.load(f)
    refresh = tokens["refresh_token"]

    resp = requests.post(
        "https://api.fitbit.com/oauth2/token",
        headers={
            "Authorization": "Basic "
            + base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    # Persist immediately, identical format to fitbit2s3.py
    with open(TOKEN_FILE_PATH, "w") as f:
        json.dump(
            {"access_token": data["access_token"], "refresh_token": data["refresh_token"]},
            f,
        )
    print("[ok] token refreshed and written back to", TOKEN_FILE_PATH)
    return data["access_token"]


def haversine(a, b):
    R = 6371000.0
    p = math.pi / 180
    dlat = (b[0] - a[0]) * p
    dlon = (b[1] - a[1]) * p
    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(x))


def main():
    token = refresh_token()
    H = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # 1. Find the activity + its tcxLink
    before = (datetime.strptime(TARGET_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    url = (
        f"https://api.fitbit.com/1/user/-/activities/list.json"
        f"?beforeDate={before}&sort=desc&limit=20&offset=0"
    )
    r = requests.get(url, headers=H, timeout=30)
    print("[info] activities/list:", r.status_code)
    r.raise_for_status()
    acts = [a for a in r.json()["activities"] if a["startTime"][:10] == TARGET_DATE]
    print(f"[info] activities on {TARGET_DATE}:")
    for a in acts:
        print(
            f"   - {a['startTime']} {a['activityName']:14} "
            f"dist={a.get('distance')} dur(min)={a.get('duration', 0)/60000:.1f} "
            f"hasGps={a.get('hasGps')} tcx={'y' if a.get('tcxLink') else 'n'}"
        )
    act = next(
        (a for a in acts if a["activityName"] == TARGET_NAME and a.get("tcxLink")), None
    )
    if not act:
        print(f"[stop] no '{TARGET_NAME}' with tcxLink on {TARGET_DATE}")
        return

    # 2. Fetch raw TCX, save it
    tcx = requests.get(act["tcxLink"], headers={"Authorization": f"Bearer {token}"}, timeout=60)
    print("[info] tcxLink:", tcx.status_code, "| bytes:", len(tcx.content))
    tcx.raise_for_status()
    out = f"walk_{TARGET_DATE}_raw.tcx"
    with open(out, "wb") as f:
        f.write(tcx.content)
    print("[ok] raw TCX saved to", out)

    # 3. Parse + analyse
    root = ET.fromstring(tcx.text)
    laps = root.findall(".//ns:Lap", TCX_NS)
    tracks = root.findall(".//ns:Track", TCX_NS)
    tps = root.findall(".//ns:Trackpoint", TCX_NS)

    with_time = with_pos = 0
    coords = []  # (lat, lon) in document order, position-bearing only
    times = []
    for tp in tps:
        t = tp.find("ns:Time", TCX_NS)
        la = tp.find(".//ns:LatitudeDegrees", TCX_NS)
        lo = tp.find(".//ns:LongitudeDegrees", TCX_NS)
        if t is not None:
            with_time += 1
            times.append(t.text)
        if la is not None and lo is not None:
            with_pos += 1
            coords.append((float(la.text), float(lo.text)))

    print("\n===== RAW TCX (source of truth from Fitbit) =====")
    print(f"  <Lap> elements:        {len(laps)}")
    print(f"  <Track> elements:      {len(tracks)}")
    print(f"  <Trackpoint> total:    {len(tps)}")
    print(f"  with <Time>:           {with_time}  (unique={len(set(times))}, dupes={with_time-len(set(times))})")
    print(f"  with GPS position:     {with_pos}")
    print(f"  WITHOUT position:      {len(tps)-with_pos}  <-- our parser skips these")

    if coords:
        path = sum(haversine(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
        se = haversine(coords[0], coords[-1])
        dmax, imax = 0, 0
        for i, c in enumerate(coords):
            d = haversine(coords[0], c)
            if d > dmax:
                dmax, imax = d, i
        print("\n  --- geometry of position-bearing points (document order) ---")
        print(f"  path length:     {path/1000:.2f} km")
        print(f"  start -> end:    {se:.0f} m   (small => returns to start = full circuit)")
        print(f"  max from start:  {dmax:.0f} m @ index {imax}/{len(coords)}  "
              f"({'MIDDLE => out-and-back' if 0.25 < imax/len(coords) < 0.75 else 'END => one-way/partial'})")
        print("\n  idx : dist_from_start(m)")
        n = len(coords)
        for i in [int(k * (n - 1) / 12) for k in range(13)]:
            print(f"  {i:5} : {haversine(coords[0], coords[i]):7.0f}")

    print("\n  Our pipeline currently stores ~3201 points / 3.59 km for this walk.")
    print("  Compare the numbers above:")
    print("   * If raw path ~7.2 km and returns to start  -> Fitbit serves full; our parser drops half (fix get_tcx_data).")
    print("   * If raw path ~3.6 km / one-way (matches us) -> Fitbit's TCX itself is partial (API limitation, not our bug).")


if __name__ == "__main__":
    main()
