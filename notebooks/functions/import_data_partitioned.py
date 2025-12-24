#!/usr/bin/env python3
"""
Helper functions for loading Fitbit data from partitioned Parquet structure.

This is a drop-in replacement for import_data.py that uses the optimized
partitioned structure for massive memory savings and faster loading.

Memory improvement:
- Old: Load 1.7 GB (3M records) → filter to 40K records
- New: Load only 2 MB (40K records) directly
"""

import pandas as pd
from pathlib import Path
from typing import Dict


# Measurement categorization (matches compilation scripts)
HIGH_FREQUENCY_INTRADAY = {
    'HeartRate_Intraday': 'heartrate_intraday',
    'Steps_Intraday': 'steps_intraday'
}

MODERATE_FREQUENCY = {
    'GPS': 'gps.parquet',
    'SleepLevels': 'sleep_levels.parquet'
}


def convert_activity_distances_to_km(df_activities):
    """
    Convert ActivityRecords distances from miles to kilometers.
    Fitbit API returns ALL activity distances in MILES.

    Args:
        df_activities: DataFrame with activity records

    Returns:
        DataFrame with distances converted to km
    """
    if df_activities.empty or 'distance' not in df_activities.columns:
        return df_activities

    MILES_TO_KM = 1.609344
    df = df_activities.copy()
    mask = (df['distance'].notna()) & (df['distance'] > 0)

    if mask.any():
        # Store original distance in miles
        df.loc[mask, 'distance_miles'] = df.loc[mask, 'distance']
        # Convert to kilometers
        df.loc[mask, 'distance'] = df.loc[mask, 'distance'] * MILES_TO_KM

        # Recalculate pace (seconds per km)
        if 'duration' in df.columns:
            duration_mask = mask & (df['duration'].notna())
            duration_seconds = df.loc[duration_mask, 'duration'] / 1000
            df.loc[duration_mask, 'pace'] = duration_seconds / df.loc[duration_mask, 'distance']

        # Recalculate speed (km/h)
        if 'duration' in df.columns:
            duration_mask = mask & (df['duration'].notna())
            duration_hours = (df.loc[duration_mask, 'duration'] / 1000) / 3600
            df.loc[duration_mask, 'speed'] = df.loc[duration_mask, 'distance'] / duration_hours

    return df


def clean_column_names(df):
    """
    Remove field_ and tag_ prefixes from column names.

    Args:
        df: DataFrame with prefixed columns

    Returns:
        DataFrame with clean column names
    """
    rename_dict = {}
    for col in df.columns:
        if col.startswith('field_'):
            rename_dict[col] = col.replace('field_', '')
        elif col.startswith('tag_'):
            rename_dict[col] = col.replace('tag_', '')

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df


def load_single_date_from_partitioned(date_str: str,
                                      data_dir: str = '../data',
                                      timezone: str = 'Europe/London') -> Dict[str, pd.DataFrame]:
    """
    Load Fitbit data for a single date from partitioned Parquet structure.

    This function is MUCH more memory efficient than loading the monolithic file:
    - Old approach: Load 1.7 GB → filter to 40K records
    - New approach: Load only 40K records directly (~2 MB)

    Args:
        date_str: Date in format 'YYYY-MM-DD'
        data_dir: Path to data directory containing partitioned structure
        timezone: Timezone for date filtering (default: 'Europe/London')

    Returns:
        dict: {'HeartRate_Intraday': df, 'SleepSummary': df, ...}

    Example:
        >>> dfs = load_single_date_from_partitioned('2025-12-02')
        >>> df_hr = dfs['HeartRate_Intraday']
        >>> print(f"Loaded {len(df_hr):,} heart rate records")
    """
    data_path = Path(data_dir)
    print(f"📥 Loading data for {date_str} from partitioned structure...")

    dfs = {}
    target_date = pd.to_datetime(date_str).date()

    # ========================================================================
    # 1. Load HIGH-FREQUENCY INTRADAY data (date-partitioned)
    # ========================================================================
    for measurement, dir_name in HIGH_FREQUENCY_INTRADAY.items():
        dir_path = data_path / dir_name

        if not dir_path.exists():
            print(f"   ⚠️  {dir_name}/ not found, skipping")
            continue

        try:
            # Use partition filtering for efficient loading
            df = pd.read_parquet(
                dir_path,
                filters=[('date', '=', date_str)]
            )

            if not df.empty:
                # Clean column names
                df = clean_column_names(df)

                # Convert timezone if needed
                if pd.api.types.is_datetime64_any_dtype(df['time']):
                    if df['time'].dt.tz is None:
                        df['time'] = df['time'].dt.tz_localize('UTC')
                    # Note: Keep as UTC, notebooks will convert as needed

                dfs[measurement] = df
                print(f"   ✅ {measurement}: {len(df):,} records")
            else:
                print(f"   ⚠️  {measurement}: No data for {date_str}")

        except Exception as e:
            print(f"   ✗ Error loading {measurement}: {e}")

    # ========================================================================
    # 2. Load MODERATE-FREQUENCY data (single files, then filter)
    # ========================================================================
    for measurement, filename in MODERATE_FREQUENCY.items():
        file_path = data_path / filename

        if not file_path.exists():
            print(f"   ⚠️  {filename} not found, skipping")
            continue

        try:
            # Load entire file (small enough)
            df = pd.read_parquet(file_path)

            # Filter for target date
            if 'date' in df.columns:
                df = df[df['date'] == pd.to_datetime(date_str)]
            elif 'time' in df.columns:
                # Fallback: filter by time
                if pd.api.types.is_datetime64_any_dtype(df['time']):
                    if df['time'].dt.tz is None:
                        df['time'] = df['time'].dt.tz_localize('UTC')

                    start_datetime = pd.Timestamp(target_date).tz_localize(timezone)
                    end_datetime = start_datetime + pd.Timedelta(days=1)
                    start_utc = start_datetime.tz_convert('UTC')
                    end_utc = end_datetime.tz_convert('UTC')

                    df = df[(df['time'] >= start_utc) & (df['time'] < end_utc)]

            if not df.empty:
                df = clean_column_names(df)
                dfs[measurement] = df
                print(f"   ✅ {measurement}: {len(df):,} records")
            else:
                print(f"   ⚠️  {measurement}: No data for {date_str}")

        except Exception as e:
            print(f"   ✗ Error loading {measurement}: {e}")

    # ========================================================================
    # 3. Load DAILY SUMMARIES (all low-frequency metrics)
    # ========================================================================
    daily_file = data_path / 'daily_summaries.parquet'

    if daily_file.exists():
        try:
            df_daily = pd.read_parquet(daily_file)

            # Filter for target date
            if 'date' in df_daily.columns:
                df_daily = df_daily[df_daily['date'] == pd.to_datetime(date_str)]
            elif 'time' in df_daily.columns:
                # Fallback: filter by time
                if pd.api.types.is_datetime64_any_dtype(df_daily['time']):
                    if df_daily['time'].dt.tz is None:
                        df_daily['time'] = df_daily['time'].dt.tz_localize('UTC')

                    start_datetime = pd.Timestamp(target_date).tz_localize(timezone)
                    end_datetime = start_datetime + pd.Timedelta(days=1)
                    start_utc = start_datetime.tz_convert('UTC')
                    end_utc = end_datetime.tz_convert('UTC')

                    df_daily = df_daily[(df_daily['time'] >= start_utc) & (df_daily['time'] < end_utc)]

            # Split by measurement type
            if not df_daily.empty and 'measurement' in df_daily.columns:
                df_daily = clean_column_names(df_daily)

                for measurement in df_daily['measurement'].unique():
                    df_meas = df_daily[df_daily['measurement'] == measurement].copy()
                    df_meas = df_meas.drop(columns=['measurement'])
                    dfs[measurement] = df_meas

                measurement_count = len(df_daily['measurement'].unique())
                print(f"   ✅ Daily summaries: {len(df_daily):,} records ({measurement_count} types)")
            else:
                print(f"   ⚠️  Daily summaries: No data for {date_str}")

        except Exception as e:
            print(f"   ✗ Error loading daily summaries: {e}")

    # ========================================================================
    # Apply distance conversion for ActivityRecords
    # ========================================================================
    if 'ActivityRecords' in dfs:
        dfs['ActivityRecords'] = convert_activity_distances_to_km(dfs['ActivityRecords'])
        print(f"   ✅ Applied distance conversion to ActivityRecords")

    print(f"   ✅ Found {len(dfs)} measurement types")
    return dfs


def get_available_dates(data_dir: str = '../data') -> list:
    """
    Get list of available dates from the partitioned structure.

    Args:
        data_dir: Path to data directory

    Returns:
        List of date strings in YYYY-MM-DD format
    """
    data_path = Path(data_dir)

    # Check heartrate_intraday partitions (most reliable)
    hr_dir = data_path / 'heartrate_intraday'

    if not hr_dir.exists():
        print(f"⚠️  {hr_dir} not found")
        return []

    # Extract dates from partition directories
    dates = []
    for partition_dir in sorted(hr_dir.iterdir()):
        if partition_dir.is_dir() and partition_dir.name.startswith('date='):
            # Extract date from directory name (format: date=YYYY-MM-DD%20...)
            date_str = partition_dir.name.replace('date=', '').split('%20')[0].split()[0]
            try:
                # Validate it's a proper date
                pd.to_datetime(date_str)
                dates.append(date_str)
            except:
                continue

    return sorted(dates)


# Backwards compatibility alias
def load_single_date_from_parquet(date_str: str,
                                  parquet_path: str = '../data',
                                  timezone: str = 'Europe/London') -> Dict[str, pd.DataFrame]:
    """
    Backwards compatible wrapper for load_single_date_from_partitioned.

    This allows existing notebooks to work without changes by just
    importing from import_data_partitioned instead of import_data.
    """
    # If parquet_path ends with .parquet, extract directory
    if parquet_path.endswith('.parquet'):
        data_dir = str(Path(parquet_path).parent)
    else:
        data_dir = parquet_path

    return load_single_date_from_partitioned(date_str, data_dir, timezone)
