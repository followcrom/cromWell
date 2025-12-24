#!/usr/bin/env python3
"""
Memory-efficient incremental update for Parquet structure.
Processes new files one at a time to avoid OOM issues.

Updates:
- heartrate_intraday/ (appends new date partitions)
- steps_intraday/ (appends new date partitions)
- gps.parquet (appends to file)
- sleep_levels.parquet (appends to file)
- daily_summaries.parquet (appends to file)
"""

import gzip
import json
import pandas as pd
from pathlib import Path
from datetime import datetime


# Measurement categorization
HIGH_FREQUENCY_INTRADAY = {
    'HeartRate_Intraday': 'heartrate_intraday',
    'Steps_Intraday': 'steps_intraday'
}

MODERATE_FREQUENCY = {
    'GPS': 'gps.parquet',
    'SleepLevels': 'sleep_levels.parquet'
}


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


def append_to__data(df, data_path, timezone='Europe/London'):
    """
    Append new records to  structure.

    Args:
        df: DataFrame with new records
        data_path: Base directory
        timezone: Timezone for date extraction
    """
    # Ensure time is datetime with timezone
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'], format='ISO8601')

    if df['time'].dt.tz is None:
        df['time'] = df['time'].dt.tz_localize('UTC')

    # Add date column
    df['date'] = df['time'].dt.tz_convert(timezone).dt.date
    df['date'] = pd.to_datetime(df['date'])

    # Track what we've processed
    processed_measurements = set()

    # ========================================================================
    # 1. HIGH-FREQUENCY INTRADAY (date-)
    # ========================================================================
    for measurement, dir_name in HIGH_FREQUENCY_INTRADAY.items():
        if measurement not in df['measurement'].values:
            continue

        df_subset = df[df['measurement'] == measurement].copy()
        count = len(df_subset)

        if count == 0:
            continue

        output_dir = data_path / dir_name

        # Drop measurement column
        df_subset = df_subset.drop(columns=['measurement'])

        print(f"      → {measurement}: {count:,} records to {dir_name}/")

        # Append to existing partitions or create new ones
        df_subset.to_parquet(
            output_dir,
            partition_cols=['date'],
            index=False,
            compression='snappy',
            existing_data_behavior='overwrite_or_ignore'
        )

        processed_measurements.add(measurement)

    # ========================================================================
    # 2. MODERATE-FREQUENCY (single files, append mode)
    # ========================================================================
    for measurement, filename in MODERATE_FREQUENCY.items():
        if measurement not in df['measurement'].values:
            continue

        df_subset = df[df['measurement'] == measurement].copy()
        count = len(df_subset)

        if count == 0:
            continue

        output_file = data_path / filename

        # Drop measurement column
        df_subset = df_subset.drop(columns=['measurement'])

        print(f"      → {measurement}: {count:,} records to {filename}")

        # Append or create
        if output_file.exists():
            df_existing = pd.read_parquet(output_file)
            df_combined = pd.concat([df_existing, df_subset], ignore_index=True)
            # Remove duplicates based on time
            df_combined = df_combined.drop_duplicates(subset=['time'], keep='last')
            df_combined.to_parquet(output_file, index=False, compression='snappy')
        else:
            df_subset.to_parquet(output_file, index=False, compression='snappy')

        processed_measurements.add(measurement)

    # ========================================================================
    # 3. DAILY SUMMARIES (all remaining)
    # ========================================================================
    remaining_measurements = set(df['measurement'].unique()) - processed_measurements

    if remaining_measurements:
        df_daily = df[df['measurement'].isin(remaining_measurements)].copy()
        count = len(df_daily)

        output_file = data_path / 'daily_summaries.parquet'

        print(f"      → Daily summaries: {count:,} records to daily_summaries.parquet")

        # Keep measurement column
        if output_file.exists():
            df_existing = pd.read_parquet(output_file)
            df_combined = pd.concat([df_existing, df_daily], ignore_index=True)
            # Remove duplicates based on time and measurement
            df_combined = df_combined.drop_duplicates(
                subset=['time', 'measurement'],
                keep='last'
            )
            df_combined.to_parquet(output_file, index=False, compression='snappy')
        else:
            df_daily.to_parquet(output_file, index=False, compression='snappy')


def main():
    data_path = Path('.')
    state_file = 'compilation_state.json'
    state_path = data_path / state_file

    # Load existing state
    if not state_path.exists():
        print("No state file found. Run full compilation first:")
        print("  python compile_fitbit_data.py --compile")
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

    # Process new files ONE AT A TIME
    new_dates = []
    total_new_records = 0

    for i, file_path in enumerate(new_files, 1):
        file_date = get_date_from_filename(file_path.name)
        print(f"\nProcessing {i}/{len(new_files)}: {file_path.name} (date: {file_date})")

        try:
            # Load this file's records
            records = load_and_flatten_json_gz(file_path)
            print(f"   ✓ Loaded {len(records):,} records")

            # Convert to DataFrame
            new_df = pd.DataFrame(records)

            # Append to  structure
            print(f"   ✓ Appending to  structure...")
            append_to__data(new_df, data_path)

            new_dates.append(file_date)
            total_new_records += len(records)

            print(f"   ✓ Complete for {file_date}")

            # Free memory
            del new_df, records

        except Exception as e:
            print(f"   ✗ ERROR processing {file_path.name}: {e}")
            continue

    if total_new_records == 0:
        print("\nNo new records added")
        return

    # Update state
    state['last_updated'] = datetime.now().isoformat()
    state['total_records'] = state.get('total_records', 0) + total_new_records
    state['processed_dates'].extend(new_dates)
    state['latest_date'] = max(state['processed_dates'])

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✅ Incremental update complete!")
    print(f"  New records added: {total_new_records:,}")
    print(f"  Total records: {state['total_records']:,}")
    print(f"  New date range: {min(new_dates)} to {max(new_dates)}")
    print(f"  Overall date range: {min(state['processed_dates'])} to {max(state['processed_dates'])}")

    # Show structure size
    print(f"\n💾 Storage breakdown:")
    total_size = 0

    for dir_name in HIGH_FREQUENCY_INTRADAY.values():
        dir_path = data_path / dir_name
        if dir_path.exists():
            size = sum(f.stat().st_size for f in dir_path.rglob('*.parquet'))
            total_size += size
            print(f"   {dir_name + '/':30s} {size / 1024 / 1024:>8.1f} MB")

    for filename in MODERATE_FREQUENCY.values():
        file_path = data_path / filename
        if file_path.exists():
            size = file_path.stat().st_size
            total_size += size
            print(f"   {filename:30s} {size / 1024 / 1024:>8.1f} MB")

    daily_file = data_path / 'daily_summaries.parquet'
    if daily_file.exists():
        size = daily_file.stat().st_size
        total_size += size
        print(f"   {'daily_summaries.parquet':30s} {size / 1024 / 1024:>8.1f} MB")

    print(f"   {'-' * 30} {'-' * 10}")
    print(f"   {'TOTAL':30s} {total_size / 1024 / 1024:>8.1f} MB")


if __name__ == '__main__':
    main()
