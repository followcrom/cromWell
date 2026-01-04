#!/usr/bin/env python3
"""
Split monolithic fitbit_compiled.parquet into optimized  structure.

Creates:
- heartrate_intraday/     (date-, ~2.8M records)
- steps_intraday/         (date-, ~109K records)
- gps.parquet            (single file, ~21K records)
- sleep_levels.parquet   (single file, ~3.4K records)
- daily_summaries.parquet (single file, all low-frequency metrics)
"""

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

# Everything else goes to daily_summaries.parquet
# (HRV, BreathingRate, SkinTemperature, SPO2_Daily, Activity-*, HR_Zones,
#  RestingHR, SleepSummary, DeviceBatteryLevel, Weight, ActivityRecords)


def split_parquet(input_file='fitbit_compiled.parquet',
                  output_dir='.',
                  timezone='Europe/London'):
    """
    Split monolithic parquet into optimized structure.

    Args:
        input_file: Path to existing compiled parquet file
        output_dir: Directory to create new structure in
        timezone: Timezone for date extraction
    """
    input_path = Path(input_file)
    output_path = Path(output_dir)

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return

    print(f"📂 Reading {input_path.name}...")
    print(f"   File size: {input_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Load parquet file
    df = pd.read_parquet(input_path)
    print(f"   Total records: {len(df):,}")
    print(f"   Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")

    # Ensure time is datetime with timezone
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'])
    if df['time'].dt.tz is None:
        df['time'] = df['time'].dt.tz_localize('UTC')

    # Add date column in local timezone (as string for clean partition names)
    df['date'] = df['time'].dt.tz_convert(timezone).dt.date.astype(str)

    print(f"\n📊 Found {df['measurement'].nunique()} measurement types")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")

    # Get measurement counts
    measurement_counts = df['measurement'].value_counts()
    print(f"\n📈 Top measurements by record count:")
    for measurement, count in measurement_counts.head(10).items():
        pct = count / len(df) * 100
        print(f"   {measurement:40s} {count:>10,} ({pct:>5.1f}%)")

    print(f"\n🔄 Splitting into optimized structure...")
    print("=" * 70)

    # Track what we've processed
    processed_measurements = set()

    # ========================================================================
    # 1. Process HIGH-FREQUENCY INTRADAY data (date-)
    # ========================================================================
    print(f"\n📦 Creating date- datasets...")

    for measurement, dir_name in HIGH_FREQUENCY_INTRADAY.items():
        if measurement not in df['measurement'].values:
            print(f"   ⚠️  {measurement} not found in data")
            continue

        df_subset = df[df['measurement'] == measurement].copy()
        count = len(df_subset)

        if count == 0:
            print(f"   ⚠️  {measurement}: 0 records, skipping")
            continue

        output_subdir = output_path / dir_name
        output_subdir.mkdir(parents=True, exist_ok=True)

        # Drop the measurement column (redundant now)
        df_subset = df_subset.drop(columns=['measurement'])

        print(f"   📁 {measurement}")
        print(f"      Records: {count:,}")
        print(f"      Writing to: {dir_name}/")

        # Write with date partitioning
        df_subset.to_parquet(
            output_subdir,
            partition_cols=['date'],
            index=False,
            compression='snappy'
        )

        # Calculate size
        total_size = sum(f.stat().st_size for f in output_subdir.rglob('*.parquet'))
        print(f"      ✅ Saved: {total_size / 1024 / 1024:.1f} MB")

        processed_measurements.add(measurement)

    # ========================================================================
    # 2. Process MODERATE-FREQUENCY data (single files)
    # ========================================================================
    print(f"\n📄 Creating single-file datasets...")

    for measurement, filename in MODERATE_FREQUENCY.items():
        if measurement not in df['measurement'].values:
            print(f"   ⚠️  {measurement} not found in data")
            continue

        df_subset = df[df['measurement'] == measurement].copy()
        count = len(df_subset)

        if count == 0:
            print(f"   ⚠️  {measurement}: 0 records, skipping")
            continue

        output_file = output_path / filename

        # Drop the measurement column
        df_subset = df_subset.drop(columns=['measurement'])

        print(f"   📄 {measurement}")
        print(f"      Records: {count:,}")
        print(f"      Writing to: {filename}")

        df_subset.to_parquet(output_file, index=False, compression='snappy')

        file_size = output_file.stat().st_size / 1024 / 1024
        print(f"      ✅ Saved: {file_size:.1f} MB")

        processed_measurements.add(measurement)

    # ========================================================================
    # 3. Process ALL REMAINING (daily summaries)
    # ========================================================================
    print(f"\n📊 Creating daily summaries file...")

    # Get all measurements we haven't processed yet
    remaining_measurements = set(df['measurement'].unique()) - processed_measurements

    if remaining_measurements:
        df_daily = df[df['measurement'].isin(remaining_measurements)].copy()
        count = len(df_daily)

        output_file = output_path / 'daily_summaries.parquet'

        print(f"   📊 Daily Summaries ({len(remaining_measurements)} measurement types)")
        print(f"      Measurements: {', '.join(sorted(remaining_measurements))}")
        print(f"      Records: {count:,}")
        print(f"      Writing to: daily_summaries.parquet")

        # Keep measurement column for daily summaries
        df_daily.to_parquet(output_file, index=False, compression='snappy')

        file_size = output_file.stat().st_size / 1024 / 1024
        print(f"      ✅ Saved: {file_size:.1f} MB")
    else:
        print(f"   ⚠️  No remaining measurements for daily summaries")

    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n" + "=" * 70)
    print(f"✅ Split complete!")
    print(f"\n📁 New structure created in: {output_path}")
    print(f"\n💾 Storage breakdown:")

    total_new_size = 0

    for dir_name in HIGH_FREQUENCY_INTRADAY.values():
        dir_path = output_path / dir_name
        if dir_path.exists():
            size = sum(f.stat().st_size for f in dir_path.rglob('*.parquet'))
            total_new_size += size
            print(f"   {dir_name + '/':30s} {size / 1024 / 1024:>8.1f} MB")

    for filename in MODERATE_FREQUENCY.values():
        file_path = output_path / filename
        if file_path.exists():
            size = file_path.stat().st_size
            total_new_size += size
            print(f"   {filename:30s} {size / 1024 / 1024:>8.1f} MB")

    daily_file = output_path / 'daily_summaries.parquet'
    if daily_file.exists():
        size = daily_file.stat().st_size
        total_new_size += size
        print(f"   {'daily_summaries.parquet':30s} {size / 1024 / 1024:>8.1f} MB")

    print(f"   {'-' * 30} {'-' * 10}")
    print(f"   {'TOTAL':30s} {total_new_size / 1024 / 1024:>8.1f} MB")

    original_size = input_path.stat().st_size / 1024 / 1024
    print(f"\n📊 Comparison:")
    print(f"   Original file: {original_size:.1f} MB")
    print(f"   New structure: {total_new_size / 1024 / 1024:.1f} MB")

    print(f"\n💡 Next steps:")
    print(f"   1. Test loading data with the new structure")
    print(f"   2. Update notebooks to use new helper functions (import_data.py)")
    print(f"   3. Update compilation scripts for new structure")
    print(f"   4. Once verified, you can delete the old fitbit_compiled.parquet")


def main():
    split_parquet(
        input_file='fitbit_compiled.parquet',
        output_dir='.',
        timezone='Europe/London'
    )


if __name__ == '__main__':
    main()
