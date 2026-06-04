#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply GPS heals into the local gps.parquet -- RUNS LOCALLY (wired into cromwell.sh).

Reads the heal manifest that heal_gps.py writes to S3, and for any heals not yet
applied locally, replaces that activity's GPS rows in data/gps.parquet from the
(now healed) S3 backup. Idempotent: tracks the last-applied timestamp in
data/heal_applied.json, so re-runs with nothing new do nothing.
"""

import gzip, json
from pathlib import Path
import boto3
import pandas as pd

S3_PROFILE = "surface"          # same profile sync_from_s3.py uses
BUCKET = "followcrom"
PREFIX = "cromwell/fitbit/"
MANIFEST_KEY = f"{PREFIX}heal_manifest.json"
TZ = "Europe/London"

REPO = Path(__file__).resolve().parent.parent
GPS_PARQUET = REPO / "data" / "gps.parquet"
APPLIED_STATE = REPO / "data" / "heal_applied.json"


def main():
    s3 = boto3.Session(profile_name=S3_PROFILE).client("s3")

    try:
        manifest = json.loads(gzip.decompress(
            s3.get_object(Bucket=BUCKET, Key=MANIFEST_KEY)["Body"].read()).decode())
    except Exception:
        print("apply_heal: no heal manifest yet -- nothing to do.")
        return

    applied_ts = ""
    if APPLIED_STATE.exists():
        applied_ts = json.loads(APPLIED_STATE.read_text()).get("applied_ts", "")

    pending = [e for e in manifest if e["ts"] > applied_ts]
    if not pending:
        print("apply_heal: up to date -- nothing to apply.")
        return

    # latest heal per (date, aid)
    latest = {}
    for e in pending:
        latest[(e["date"], e["aid"])] = e
    print(f"apply_heal: {len(latest)} healed walk(s) to apply.")

    if not GPS_PARQUET.exists():
        print("apply_heal: gps.parquet missing -- skipping (will apply after first sync).")
        return

    gps = pd.read_parquet(GPS_PARQUET)
    gps["time"] = pd.to_datetime(gps["time"], utc=True)

    # cache backups per date
    backups = {}
    new_rows = []
    aids_to_replace = set()
    for (date, aid) in latest:
        if date not in backups:
            obj = s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}fitbit_backup_{date}.json.gz")
            backups[date] = json.loads(gzip.decompress(obj["Body"].read()).decode())
        gps_recs = [r for r in backups[date] if r["measurement"] == "GPS"
                    and r.get("tags", {}).get("ActivityID") == aid]
        if not gps_recs:
            continue
        aids_to_replace.add(aid)
        for r in gps_recs:
            row = {"time": r["time"], "tag_ActivityID": aid}
            for k, v in r["fields"].items():
                row[f"field_{k}"] = v
            new_rows.append(row)
        print(f"  {date} {aid}: {len(gps_recs)} pts")

    if not new_rows:
        print("apply_heal: nothing to replace.")
    else:
        before = len(gps)
        gps = gps[~gps["tag_ActivityID"].isin(aids_to_replace)].copy()
        new = pd.DataFrame(new_rows)
        new["time"] = pd.to_datetime(new["time"], utc=True)
        new["date"] = new["time"].dt.tz_convert(TZ).dt.date.astype(str)
        for c in gps.columns:
            if c not in new.columns:
                new[c] = pd.NA
        new = new[gps.columns]
        out = pd.concat([gps, new], ignore_index=True)
        out.to_parquet(GPS_PARQUET, index=False, compression="snappy")
        print(f"  gps.parquet rows: {before} -> {len(out)} "
              f"({len(aids_to_replace)} activities replaced)")

    APPLIED_STATE.write_text(json.dumps(
        {"applied_ts": max(e["ts"] for e in manifest)}, indent=2))
    print("apply_heal: done.")


if __name__ == "__main__":
    main()
