#!/usr/bin/env python3
"""
Download new Fitbit data from S3 and update  Parquet structure.

This script:
1. Checks compilation_state_.json to see what we already have
2. Lists files in S3 bucket
3. Downloads ONLY new files (ones we haven't processed yet)
4. Updates the  structure incrementally

No sorting needed - data is already  by date!
"""

import boto3
import gzip
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import argparse


# AWS S3 Configuration
S3_BUCKET = 'followcrom'
S3_PREFIX = 'cromwell/fitbit/'
AWS_PROFILE = 'surface'  # From your notebooks

# Measurement categorization
HIGH_FREQUENCY_INTRADAY = {
    'HeartRate_Intraday': 'heartrate_intraday',
    'Steps_Intraday': 'steps_intraday'
}

MODERATE_FREQUENCY = {
    'GPS': 'gps.parquet',
    'SleepLevels': 'sleep_levels.parquet'
}

# Column filtering - only keep useful columns when writing to parquet
# This prevents bloat from empty columns being written in the first place
COLUMN_FILTER = {
    'GPS': [
        'time', 'date',
        'field_lat', 'field_lon', 'field_altitude',
        'field_heart_rate', 'field_distance',
        'field_speed', 'field_pace',
        'tag_ActivityID'
    ],
    'SleepLevels': [
        'time', 'date',
        'field_level', 'field_duration_seconds', 'field_endTime',
        'tag_isMainSleep', 'tag_Device'
    ],
    # For high-frequency data, keep all columns (they're already minimal)
    'HeartRate_Intraday': None,  # Keep all
    'Steps_Intraday': None,      # Keep all
}


def get_date_from_filename(filename):
    """Extract date from fitbit_backup_YYYY-MM-DD.json.gz filename."""
    # Handle both S3 keys and local filenames
    filename = Path(filename).name
    stem = filename.replace('.json.gz', '').replace('.json', '')
    date_str = stem.replace('fitbit_backup_', '')
    return date_str


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


def filter_columns(df, measurement):
    """
    Filter DataFrame to keep only useful columns for a measurement.
    This prevents writing bloated parquet files with empty columns.
    """
    if measurement not in COLUMN_FILTER or COLUMN_FILTER[measurement] is None:
        # No filter defined or explicitly set to None - keep all columns
        return df

    keep_cols = COLUMN_FILTER[measurement]

    # Only keep columns that exist in the dataframe
    existing_cols = [col for col in keep_cols if col in df.columns]

    # Warn if we're missing expected columns
    missing_cols = set(keep_cols) - set(df.columns)
    if missing_cols:
        print(f"         ⚠️  Some columns not found: {', '.join(missing_cols)}")

    return df[existing_cols].copy()


def append_to__data(df, data_path, timezone='Europe/London'):
    """
    Append new records to  structure.
    No sorting needed - data is already  by date!
    """
    # Ensure time is datetime with timezone
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'], format='ISO8601')

    if df['time'].dt.tz is None:
        df['time'] = df['time'].dt.tz_localize('UTC')

    # Add date column (as string for clean partition names)
    df['date'] = df['time'].dt.tz_convert(timezone).dt.date.astype(str)

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

        # Filter to keep only useful columns (prevent bloat)
        df_subset = filter_columns(df_subset, measurement)

        print(f"      → {measurement}: {count:,} records ({len(df_subset.columns)} cols) to {dir_name}/")

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

        # Filter to keep only useful columns (prevent bloat)
        df_subset = filter_columns(df_subset, measurement)

        print(f"      → {measurement}: {count:,} records ({len(df_subset.columns)} cols) to {filename}")

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


def sync_from_s3(data_dir='../data',
                 state_file='compilation_state.json',
                 download_only=False,
                 dry_run=False):
    """
    Download new files from S3 and update  structure.

    Args:
        data_dir: Local directory for data files
        state_file: JSON file tracking processed dates
        download_only: If True, only download files without processing
        dry_run: If True, show what would be downloaded without actually doing it
    """
    data_path = Path(data_dir)
    state_path = data_path / state_file

    # Initialize boto3 session
    print(f"🔗 Connecting to S3 bucket: s3://{S3_BUCKET}/{S3_PREFIX}")
    try:
        session = boto3.Session(profile_name=AWS_PROFILE)
        s3 = session.client('s3')
    except Exception as e:
        print(f"❌ Error connecting to S3: {e}")
        print(f"   Make sure AWS profile '{AWS_PROFILE}' is configured")
        return

    # Load existing state or create new
    if state_path.exists():
        with open(state_path, 'r') as f:
            state = json.load(f)
        processed_dates = set(state['processed_dates'])
        print(f"📋 Previously processed: {len(processed_dates)} dates")
        print(f"   Latest date: {state.get('latest_date', 'N/A')}")
    else:
        print(f"📋 No state file found - will process all files from S3")
        processed_dates = set()
        state = {
            'processed_dates': [],
            'total_records': 0,
            'structure_version': '_v1'
        }

    # List files in S3
    print(f"\n🔍 Listing files in S3...")
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)

        if 'Contents' not in response:
            print(f"❌ No files found in s3://{S3_BUCKET}/{S3_PREFIX}")
            return

        all_s3_files = [
            obj['Key'] for obj in response['Contents']
            if obj['Key'].endswith('.json.gz') and 'fitbit_backup_' in obj['Key']
        ]

        print(f"   Found {len(all_s3_files)} total backup files in S3")

    except Exception as e:
        print(f"❌ Error listing S3 files: {e}")
        return

    # Filter for new files only
    new_files = []
    for s3_key in all_s3_files:
        file_date = get_date_from_filename(s3_key)
        if file_date not in processed_dates:
            new_files.append((s3_key, file_date))

    if not new_files:
        print(f"\n✅ No new files to download - already up to date!")
        return

    # Sort by date
    new_files.sort(key=lambda x: x[1])

    print(f"\n📥 Found {len(new_files)} new file(s) to download:")
    for s3_key, file_date in new_files:
        size_mb = next(
            obj['Size'] for obj in response['Contents'] if obj['Key'] == s3_key
        ) / 1024 / 1024
        print(f"   • {file_date} ({size_mb:.2f} MB)")

    if dry_run:
        print(f"\n🔍 DRY RUN - No files downloaded")
        return

    # Download and process files
    print(f"\n{'📥 Downloading files...' if download_only else '📥 Downloading and processing files...'}")
    print("=" * 70)

    new_dates = []
    total_new_records = 0
    downloaded_files = []

    for i, (s3_key, file_date) in enumerate(new_files, 1):
        local_filename = Path(s3_key).name
        local_path = data_path / local_filename

        print(f"\n[{i}/{len(new_files)}] {file_date}")
        print(f"   ↓ Downloading from S3...")

        try:
            # Download file
            s3.download_file(S3_BUCKET, s3_key, str(local_path))
            file_size = local_path.stat().st_size / 1024 / 1024
            print(f"   ✅ Downloaded: {file_size:.2f} MB")

            downloaded_files.append(local_path)

            if not download_only:
                # Process file
                print(f"   ⚙️  Processing...")
                records = load_and_flatten_json_gz(local_path)
                print(f"   ✅ Loaded {len(records):,} records")

                # Convert to DataFrame
                new_df = pd.DataFrame(records)

                # Append to  structure
                append_to__data(new_df, data_path)

                new_dates.append(file_date)
                total_new_records += len(records)

                # Free memory
                del new_df, records

                print(f"   ✅ Complete")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            continue

    if download_only:
        print(f"\n✅ Download complete!")
        print(f"   Downloaded {len(downloaded_files)} file(s)")
        print(f"\n💡 To process these files, run:")
        print(f"   python update_parquet_lowmem.py")
        return

    if total_new_records == 0:
        print(f"\n⚠️  No records processed")
        return

    # Update state
    state['last_updated'] = datetime.now().isoformat()
    state['total_records'] = state.get('total_records', 0) + total_new_records
    state['processed_dates'].extend(new_dates)
    state['latest_date'] = max(state['processed_dates'])

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n" + "=" * 70)
    print(f"✅ Sync complete!")
    print(f"   New records added: {total_new_records:,}")
    print(f"   Total records: {state['total_records']:,}")
    print(f"   New date range: {min(new_dates)} to {max(new_dates)}")
    print(f"   Overall date range: {min(state['processed_dates'])} to {max(state['processed_dates'])}")

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


def main():
    parser = argparse.ArgumentParser(
        description='Download new Fitbit data from S3 and update  Parquet structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and process new files
  python sync_from_s3.py

  # See what would be downloaded without downloading
  python sync_from_s3.py --dry-run

  # Download only (don't process yet)
  python sync_from_s3.py --download-only

  # Custom data directory
  python sync_from_s3.py --data-dir /path/to/data
        """
    )

    parser.add_argument(
        '--data-dir',
        default='../data',
        help='Directory for data files (default: ../data)'
    )
    parser.add_argument(
        '--state-file',
        default='compilation_state.json',
        help='State file to track processed dates (default: compilation_state.json)'
    )
    parser.add_argument(
        '--download-only',
        action='store_true',
        help='Only download files without processing them'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be downloaded without actually downloading'
    )

    args = parser.parse_args()

    sync_from_s3(
        data_dir=args.data_dir,
        state_file=args.state_file,
        download_only=args.download_only,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
