#!/usr/bin/env python3
"""
Compile daily Fitbit JSON.gz files into optimized  Parquet structure.
Supports both full compilation and incremental updates.

Creates:
- heartrate_intraday/ (date-)
- steps_intraday/ (date-)
- gps.parquet
- sleep_levels.parquet
- daily_summaries.parquet
"""

import gzip
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import argparse


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


def save__data(df, data_dir, timezone='Europe/London'):
    """
    Save DataFrame in optimized  structure.

    Args:
        df: DataFrame with all records
        data_dir: Base directory for output
        timezone: Timezone for date extraction
    """
    data_path = Path(data_dir)

    # Ensure time is datetime with timezone
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'], format='ISO8601')

    if df['time'].dt.tz is None:
        df['time'] = df['time'].dt.tz_localize('UTC')

    # Add date column
    df['date'] = df['time'].dt.tz_convert(timezone).dt.date
    df['date'] = pd.to_datetime(df['date'])

    print(f"\n💾 Saving data in  structure...")

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

        print(f"   📁 {measurement}: {count:,} records → {dir_name}/")

        # Append to existing partitions
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

        print(f"   📄 {measurement}: {count:,} records → {filename}")

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

        print(f"   📊 Daily summaries: {count:,} records → daily_summaries.parquet")

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


def compile_all_files(data_dir='.', state_file='compilation_state.json'):
    """Compile all JSON.gz files into  Parquet structure."""
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob('fitbit_backup_*.json.gz'))

    if not json_files:
        print("No fitbit_backup_*.json.gz files found in directory")
        return

    print(f"Found {len(json_files)} JSON.gz files")

    all_records = []
    processed_dates = []

    for i, file_path in enumerate(json_files, 1):
        file_date = get_date_from_filename(file_path.name)
        print(f"Processing {i}/{len(json_files)}: {file_path.name} (date: {file_date})")

        try:
            records = load_and_flatten_json_gz(file_path)
            all_records.extend(records)
            processed_dates.append(file_date)
        except Exception as e:
            print(f"  ERROR processing {file_path.name}: {e}")
            continue

    if not all_records:
        print("No records found to compile")
        return

    # Convert to DataFrame
    print(f"\nCreating DataFrame with {len(all_records):,} records...")
    df = pd.DataFrame(all_records)

    # Save in  structure
    save__data(df, data_dir)

    # Save state file
    state = {
        'last_updated': datetime.now().isoformat(),
        'total_records': len(all_records),
        'processed_dates': processed_dates,
        'latest_date': max(processed_dates) if processed_dates else None,
        'structure_version': '_v1'
    }
    state_path = data_path / state_file
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✅ Compilation complete!")
    print(f"  Total records: {len(all_records):,}")
    print(f"  Date range: {min(processed_dates)} to {max(processed_dates)}")
    print(f"  State file: {state_path}")

    return df


def update_incremental(data_dir='.', state_file='compilation_state.json'):
    """Update the  files with new daily files only."""
    data_path = Path(data_dir)
    state_path = data_path / state_file

    # Load existing state
    if not state_path.exists():
        print("No state file found. Run full compilation first with --compile")
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

    # Process new files
    new_records = []
    new_dates = []

    for i, file_path in enumerate(new_files, 1):
        file_date = get_date_from_filename(file_path.name)
        print(f"Processing {i}/{len(new_files)}: {file_path.name} (date: {file_date})")

        try:
            records = load_and_flatten_json_gz(file_path)
            new_records.extend(records)
            new_dates.append(file_date)
        except Exception as e:
            print(f"  ERROR processing {file_path.name}: {e}")
            continue

    if not new_records:
        print("No new records found")
        return

    # Create DataFrame from new records
    print(f"\nCreating DataFrame with {len(new_records):,} new records...")
    new_df = pd.DataFrame(new_records)

    # Save in  structure
    save__data(new_df, data_dir)

    # Update state
    state['last_updated'] = datetime.now().isoformat()
    state['total_records'] = state['total_records'] + len(new_records)
    state['processed_dates'].extend(new_dates)
    state['latest_date'] = max(state['processed_dates'])

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✅ Incremental update complete!")
    print(f"  New records added: {len(new_records):,}")
    print(f"  Total records: {state['total_records']:,}")
    print(f"  New date range: {min(new_dates)} to {max(new_dates)}")
    print(f"  Overall date range: {min(state['processed_dates'])} to {max(state['processed_dates'])}")

    return new_df


def main():
    parser = argparse.ArgumentParser(
        description='Compile Fitbit daily JSON.gz files into  Parquet format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initial compilation of all files
  python compile_fitbit_data.py --compile

  # Incremental update (add only new files)
  python compile_fitbit_data.py --update

  # Custom data directory
  python compile_fitbit_data.py --compile --data-dir /path/to/data
        """
    )

    parser.add_argument(
        '--compile',
        action='store_true',
        help='Compile all JSON.gz files into  Parquet structure'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update existing  structure with new daily files only'
    )
    parser.add_argument(
        '--data-dir',
        default='.',
        help='Directory containing JSON.gz files (default: current directory)'
    )
    parser.add_argument(
        '--state-file',
        default='compilation_state.json',
        help='State file to track processed dates (default: compilation_state.json)'
    )

    args = parser.parse_args()

    if not args.compile and not args.update:
        parser.error('Please specify either --compile or --update')

    if args.compile and args.update:
        parser.error('Please specify only one of --compile or --update')

    if args.compile:
        compile_all_files(
            data_dir=args.data_dir,
            state_file=args.state_file
        )
    elif args.update:
        update_incremental(
            data_dir=args.data_dir,
            state_file=args.state_file
        )


if __name__ == '__main__':
    main()
