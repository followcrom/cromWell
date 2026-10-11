#!/usr/bin/env python3
"""
Compare two daily backup files record-by-record, per measurement.

Used to check a Google Health backup (health2s3.py) against the legacy Fitbit
backup (fitbit2s3.py) for the same date before cutting over.

Usage:
    python compare_backups.py legacy.json.gz new.json.gz
"""

import gzip
import json
import sys
from collections import defaultdict

import pandas as pd

# Sub-second precision and float noise differ between the two APIs.
TIME_ROUND = "1s"
VALUE_TOLERANCE = 0.05


def load(path):
    raw = open(path, "rb").read()
    try:
        records = json.loads(gzip.decompress(raw))
    except OSError:
        records = json.loads(raw)
    by_measurement = defaultdict(dict)
    for r in records:
        key = pd.Timestamp(r["time"]).round(TIME_ROUND)
        by_measurement[r["measurement"]][key] = r
    return by_measurement


def compare_fields(old, new):
    """Return a list of 'field: old -> new' strings for fields that differ."""
    diffs = []
    for field in sorted(set(old) | set(new)):
        a, b = old.get(field), new.get(field)
        if a is None or b is None:
            diffs.append(f"{field}: {a} -> {b}")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(a - b) > max(VALUE_TOLERANCE, 0.001 * abs(a)):
                diffs.append(f"{field}: {a:g} -> {b:g}")
        elif field == "endTime":
            if pd.Timestamp(a) != pd.Timestamp(b):
                diffs.append(f"{field}: {a} -> {b}")
        elif a != b:
            diffs.append(f"{field}: {a} -> {b}")
    return diffs


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    legacy, new = load(sys.argv[1]), load(sys.argv[2])

    print(f"{'measurement':30s} {'legacy':>7s} {'new':>7s} {'matched':>8s} {'differ':>7s}")
    details = []
    for measurement in sorted(set(legacy) | set(new)):
        a, b = legacy.get(measurement, {}), new.get(measurement, {})
        shared = set(a) & set(b)
        differing = 0
        for key in sorted(shared):
            diffs = compare_fields(a[key]["fields"], b[key]["fields"])
            diffs += compare_fields(a[key].get("tags", {}), b[key].get("tags", {}))
            if diffs:
                differing += 1
                if differing <= 3:
                    details.append(f"  {measurement} @ {key}: " + "; ".join(diffs))
        only = len(a) - len(shared), len(b) - len(shared)
        flag = "" if not differing and only == (0, 0) else "  <--"
        print(f"{measurement:30s} {len(a):7d} {len(b):7d} {len(shared):8d} {differing:7d}{flag}")
        if only != (0, 0):
            details.append(f"  {measurement}: {only[0]} only in legacy, {only[1]} only in new")

    if details:
        print("\nDifferences (first 3 per measurement):")
        print("\n".join(details))


if __name__ == "__main__":
    main()
