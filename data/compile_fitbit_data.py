#!/usr/bin/env python3
"""
Compile daily Fitbit JSON.gz files into a single Parquet file for Pandas analysis.
Supports both full compilation and incremental updates.
"""

import gzip
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import argparse


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


def compile_all_files(data_dir='.', output_file='fitbit_compiled.parquet', state_file='compilation_state.json'):
    """Compile all JSON.gz files into a single Parquet file."""
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

    # Convert time to datetime (format='ISO8601' handles timestamps with/without microseconds)
    df['time'] = pd.to_datetime(df['time'], format='ISO8601')

    # Sort by time
    df = df.sort_values('time').reset_index(drop=True)

    # Save to Parquet
    output_path = data_path / output_file
    print(f"Saving to {output_path}...")
    df.to_parquet(output_path, index=False, compression='snappy')

    # Save state file
    state = {
        'last_updated': datetime.now().isoformat(),
        'total_records': len(all_records),
        'processed_dates': processed_dates,
        'latest_date': max(processed_dates) if processed_dates else None
    }
    state_path = data_path / state_file
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✓ Compilation complete!")
    print(f"  Total records: {len(all_records):,}")
    print(f"  Date range: {min(processed_dates)} to {max(processed_dates)}")
    print(f"  Output file: {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  State file: {state_path}")

    return df


def update_incremental(data_dir='.', output_file='fitbit_compiled.parquet', state_file='compilation_state.json'):
    """Update the compiled file with new daily files only."""
    data_path = Path(data_dir)
    output_path = data_path / output_file
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

    # Load existing DataFrame
    print(f"\nLoading existing Parquet file...")
    existing_df = pd.read_parquet(output_path)
    print(f"  Existing records: {len(existing_df):,}")

    # Create new DataFrame
    print(f"Creating DataFrame with {len(new_records):,} new records...")
    new_df = pd.DataFrame(new_records)
    new_df['time'] = pd.to_datetime(new_df['time'], format='ISO8601')

    # Combine and sort
    print("Combining and sorting...")
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df = combined_df.sort_values('time').reset_index(drop=True)

    # Save updated Parquet
    print(f"Saving updated file to {output_path}...")
    combined_df.to_parquet(output_path, index=False, compression='snappy')

    # Update state
    state['last_updated'] = datetime.now().isoformat()
    state['total_records'] = len(combined_df)
    state['processed_dates'].extend(new_dates)
    state['latest_date'] = max(state['processed_dates'])

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✓ Incremental update complete!")
    print(f"  New records added: {len(new_records):,}")
    print(f"  Total records: {len(combined_df):,}")
    print(f"  New date range: {min(new_dates)} to {max(new_dates)}")
    print(f"  Overall date range: {min(state['processed_dates'])} to {max(state['processed_dates'])}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    return combined_df


def main():
    parser = argparse.ArgumentParser(
        description='Compile Fitbit daily JSON.gz files into Parquet format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initial compilation of all files
  python compile_fitbit_data.py --compile

  # Incremental update (add only new files)
  python compile_fitbit_data.py --update

  # Custom output file
  python compile_fitbit_data.py --compile --output my_fitbit_data.parquet
        """
    )

    parser.add_argument(
        '--compile',
        action='store_true',
        help='Compile all JSON.gz files into a single Parquet file'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update existing Parquet file with new daily files only'
    )
    parser.add_argument(
        '--data-dir',
        default='.',
        help='Directory containing JSON.gz files (default: current directory)'
    )
    parser.add_argument(
        '--output',
        default='fitbit_compiled.parquet',
        help='Output Parquet filename (default: fitbit_compiled.parquet)'
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
            output_file=args.output,
            state_file=args.state_file
        )
    elif args.update:
        update_incremental(
            data_dir=args.data_dir,
            output_file=args.output,
            state_file=args.state_file
        )


if __name__ == '__main__':
    main()
