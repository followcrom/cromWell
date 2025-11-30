#!/usr/bin/env python3
"""
Memory-efficient incremental update for Parquet compilation.
Processes new files one at a time to avoid OOM issues.
"""

import gzip
import json
import pandas as pd
from pathlib import Path
from datetime import datetime


def load_and_flatten_json_gz(file_path):
    """Load a gzipped JSON file and flatten the nested structure."""
    with gzip.open(file_path, 'rt') as f:
        records = json.load(f)

    flattened_records = []
    for record in records:
        flat_record = {
            'measurement': record['measurement'],
            'time': record['time'],
        }
        # Flatten tags
        if 'tags' in record:
            for key, value in record['tags'].items():
                flat_record[f'tag_{key}'] = value

        # Flatten fields
        if 'fields' in record:
            for key, value in record['fields'].items():
                flat_record[f'field_{key}'] = value

        flattened_records.append(flat_record)

    return flattened_records


def get_date_from_filename(filename):
    """Extract date from fitbit_backup_YYYY-MM-DD.json.gz filename."""
    stem = Path(filename).stem  # Remove .gz
    stem = Path(stem).stem  # Remove .json
    date_str = stem.replace('fitbit_backup_', '')
    return date_str


def main():
    data_path = Path('.')
    output_file = 'fitbit_compiled.parquet'
    state_file = 'compilation_state.json'

    output_path = data_path / output_file
    state_path = data_path / state_file

    # Load existing state
    if not state_path.exists():
        print("No state file found. Run full compilation first with compile_fitbit_data.py --compile")
        return

    with open(state_path, 'r') as f:
        state = json.load(f)

    processed_dates_set = set(state['processed_dates'])
    print(f"Previously processed: {len(processed_dates_set)} dates (up to {state['latest_date']})")

    # Find new files
    all_json_files = sorted(data_path.glob('fitbit_backup_*.json.gz'))
    new_files = [
        f for f in all_json_files
        if get_date_from_filename(f.name) not in processed_dates_set
    ]

    if not new_files:
        print("No new files to process")
        return

    print(f"Found {len(new_files)} new file(s) to process")
    print(f"Processing files one at a time to minimize memory usage...\n")

    # Load existing parquet
    print("Loading existing Parquet file...")
    existing_df = pd.read_parquet(output_path)
    print(f"  Existing records: {len(existing_df):,}")

    # Process new files ONE AT A TIME
    new_dates = []
    total_new_records = 0

    for i, file_path in enumerate(new_files, 1):
        file_date = get_date_from_filename(file_path.name)
        print(f"\nProcessing {i}/{len(new_files)}: {file_path.name} (date: {file_date})")

        try:
            # Load this file's records
            records = load_and_flatten_json_gz(file_path)
            print(f"  Loaded {len(records):,} records")

            # Convert to DataFrame
            new_df = pd.DataFrame(records)
            new_df['time'] = pd.to_datetime(new_df['time'], format='ISO8601')

            # Append to existing
            print(f"  Appending to main DataFrame...")
            existing_df = pd.concat([existing_df, new_df], ignore_index=True)

            new_dates.append(file_date)
            total_new_records += len(records)

            print(f"  ✓ Total records now: {len(existing_df):,}")

            # Free memory
            del new_df, records

        except Exception as e:
            print(f"  ERROR processing {file_path.name}: {e}")
            continue

    if total_new_records == 0:
        print("\nNo new records added")
        return

    # Sort by time
    print(f"\nSorting {len(existing_df):,} total records by time...")
    existing_df = existing_df.sort_values('time').reset_index(drop=True)

    # Save updated Parquet
    print(f"Saving to {output_path}...")
    existing_df.to_parquet(output_path, index=False, compression='snappy')

    # Update state
    state['last_updated'] = datetime.now().isoformat()
    state['total_records'] = len(existing_df)
    state['processed_dates'].extend(new_dates)
    state['latest_date'] = max(state['processed_dates'])

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✓ Incremental update complete!")
    print(f"  New records added: {total_new_records:,}")
    print(f"  Total records: {len(existing_df):,}")
    print(f"  New date range: {min(new_dates)} to {max(new_dates)}")
    print(f"  Overall date range: {min(state['processed_dates'])} to {max(state['processed_dates'])}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == '__main__':
    main()
