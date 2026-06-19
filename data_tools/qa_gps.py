#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA check for GPS tracks in data/gps.parquet -- RUNS LOCALLY.

Flags GPS tracks that look incompletely fetched (the slow-phone-upload problem):
a healthy Fitbit track has a point every few seconds, so the longest gap between
consecutive points is the reliable tell. A multi-minute gap means a dropped or
delayed segment, regardless of how many points the track has overall.

Usage:
    python qa_gps.py            # show recent tracks + flag suspects
    python qa_gps.py --all      # show every track
    python qa_gps.py --days 30  # only tracks from the last N days
"""

import argparse
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
GPS_PARQUET = REPO / "data" / "gps.parquet"

# A clean track gaps a few seconds between points. Flag anything past this.
MAX_GAP_WARN_S = 60


def build_report(gps: pd.DataFrame) -> pd.DataFrame:
    gps = gps.copy()
    gps["time"] = pd.to_datetime(gps["time"], utc=True)
    gps = gps.sort_values("time")

    rows = []
    for aid, d in gps.groupby("tag_ActivityID"):
        t = d["time"]
        span_s = (t.max() - t.min()).total_seconds()
        gaps = t.diff().dt.total_seconds().dropna()
        rows.append({
            "date": d["date"].iloc[0],
            "activity": str(aid)[:25],
            "pts": len(d),
            "span_min": round(span_s / 60, 1),
            "median_gap_s": round(gaps.median(), 1) if len(gaps) else 0,
            "max_gap_s": round(gaps.max()) if len(gaps) else 0,
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="show every track")
    ap.add_argument("--days", type=int, default=0, help="only the last N days")
    args = ap.parse_args()

    if not GPS_PARQUET.exists():
        print(f"qa_gps: {GPS_PARQUET} not found.")
        return

    report = build_report(pd.read_parquet(GPS_PARQUET))

    if args.days:
        cutoff = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=args.days)).date()
        report = report[pd.to_datetime(report["date"]).dt.date >= cutoff]

    pd.set_option("display.max_rows", None, "display.width", 200)

    shown = report if args.all else report.tail(20)
    print(shown.to_string(index=False))
    print()

    suspects = report[report["max_gap_s"] > MAX_GAP_WARN_S]
    if suspects.empty:
        print(f"OK: no tracks with a gap over {MAX_GAP_WARN_S}s.")
    else:
        print(f"SUSPECT tracks (gap over {MAX_GAP_WARN_S}s -- likely truncated/delayed):")
        print(suspects.to_string(index=False))


if __name__ == "__main__":
    main()
