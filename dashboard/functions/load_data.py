from pathlib import Path
import pandas as pd

# Measurement categorization
HIGH_FREQUENCY_INTRADAY = {
    'HeartRate_Intraday': 'heartrate_intraday',
    'Steps_Intraday': 'steps_intraday'
}

MODERATE_FREQUENCY = {
    'GPS': 'gps.parquet',
    'SleepLevels': 'sleep_levels.parquet'
}


def clean_column_names(df):
    """Remove field_ and tag_ prefixes from column names."""
    rename_dict = {}
    for col in df.columns:
        if col.startswith('field_'):
            rename_dict[col] = col.replace('field_', '')
        elif col.startswith('tag_'):
            rename_dict[col] = col.replace('tag_', '')

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df


def load_single_date(date_str, parquet_path='../data', timezone='Europe/London'):
    """
    Load Fitbit data for a single date from Parquet.

    For sleep data: Also checks previous day's sleep sessions that extend into target date.

    Args:
        date_str: Date in format 'YYYY-MM-DD'
        parquet_path: Path to data directory
        timezone: Timezone for date filtering and conversion

    Returns:
        dict: {'HeartRate_Intraday': df, 'SleepSummary': df, ...}
        All datetime columns are converted to the specified timezone.
    """
    data_dir = Path(parquet_path)
    dfs = {}
    target_date = pd.to_datetime(date_str).date()
    prev_date = (pd.to_datetime(date_str) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    # Load HIGH-FREQUENCY INTRADAY data (date-partitioned)
    for measurement, dir_name in HIGH_FREQUENCY_INTRADAY.items():
        dir_path = data_dir / dir_name
        if not dir_path.exists():
            continue

        try:
            df = pd.read_parquet(dir_path, filters=[('date', '=', date_str)])
            if not df.empty:
                df = clean_column_names(df)
                if pd.api.types.is_datetime64_any_dtype(df['time']):
                    if df['time'].dt.tz is None:
                        df['time'] = df['time'].dt.tz_localize('UTC')
                    df['time'] = df['time'].dt.tz_convert(timezone)
                dfs[measurement] = df
        except Exception as e:
            print(f"   ⚠️  Error loading {measurement}: {e}")

    # Load MODERATE-FREQUENCY data
    for measurement, filename in MODERATE_FREQUENCY.items():
        file_path = data_dir / filename
        if not file_path.exists():
            continue

        try:
            df = pd.read_parquet(file_path)
            if 'date' in df.columns:
                df = df[df['date'] == date_str]
            elif 'time' in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df['time']):
                    if df['time'].dt.tz is None:
                        df['time'] = df['time'].dt.tz_localize('UTC')
                    start_datetime = pd.Timestamp(target_date).tz_localize(timezone)
                    end_datetime = start_datetime + pd.Timedelta(days=1)
                    start_utc = start_datetime.tz_convert('UTC')
                    end_utc = end_datetime.tz_convert('UTC')
                    df = df[(df['time'] >= start_utc) & (df['time'] < end_utc)]
                    df['time'] = df['time'].dt.tz_convert(timezone)

            if not df.empty:
                df = clean_column_names(df)
                dfs[measurement] = df
        except Exception as e:
            print(f"   ⚠️  Error loading {measurement}: {e}")

    # Load DAILY SUMMARIES (special handling for sleep)
    daily_file = data_dir / 'daily_summaries.parquet'
    if daily_file.exists():
        try:
            df_daily = pd.read_parquet(daily_file)
            
            # For sleep data, also check previous day for overnight sleep
            if 'date' in df_daily.columns:
                # Get data for target date and previous date
                df_daily_filtered = df_daily[
                    (df_daily['date'] == date_str) | 
                    (df_daily['date'] == prev_date)
                ].copy()
                
                # For SleepSummary measurements, filter by endTime extending into target date
                if not df_daily_filtered.empty and 'measurement' in df_daily_filtered.columns:
                    df_daily_filtered = clean_column_names(df_daily_filtered)
                    
                    for measurement in df_daily_filtered['measurement'].unique():
                        df_meas = df_daily_filtered[df_daily_filtered['measurement'] == measurement].copy()
                        
                        # Special handling for SleepSummary: check if sleep extends into target date
                        if measurement == 'SleepSummary' and 'endTime' in df_meas.columns:
                            # Parse endTime and filter
                            df_meas['endTime_parsed'] = pd.to_datetime(df_meas['endTime'])
                            target_start = pd.Timestamp(target_date).tz_localize('UTC')
                            target_end = target_start + pd.Timedelta(days=1)

                            # Keep sleep sessions that:
                            # 1. Start on target date, OR
                            # 2. End on or after target date (overnight sleep from previous day)
                            df_meas = df_meas[
                                (df_meas['date'] == date_str) |
                                (df_meas['endTime_parsed'] >= target_start)
                            ]

                            # Drop the helper column
                            if 'endTime_parsed' in df_meas.columns:
                                df_meas = df_meas.drop(columns=['endTime_parsed'])

                            # Convert timezone for SleepSummary datetime columns
                            if 'time' in df_meas.columns:
                                df_meas['time'] = pd.to_datetime(df_meas['time'])
                                if df_meas['time'].dt.tz is None:
                                    df_meas['time'] = df_meas['time'].dt.tz_localize('UTC')
                                df_meas['time'] = df_meas['time'].dt.tz_convert(timezone)

                            if 'endTime' in df_meas.columns:
                                df_meas['endTime'] = pd.to_datetime(df_meas['endTime'])
                                if df_meas['endTime'].dt.tz is None:
                                    df_meas['endTime'] = df_meas['endTime'].dt.tz_localize('UTC')
                                df_meas['endTime'] = df_meas['endTime'].dt.tz_convert(timezone)
                        else:
                            # For non-sleep measurements, only keep target date
                            df_meas = df_meas[df_meas['date'] == date_str]

                            # Convert timezone for datetime columns in other measurements
                            if 'time' in df_meas.columns:
                                if pd.api.types.is_datetime64_any_dtype(df_meas['time']):
                                    if df_meas['time'].dt.tz is None:
                                        df_meas['time'] = df_meas['time'].dt.tz_localize('UTC')
                                    df_meas['time'] = df_meas['time'].dt.tz_convert(timezone)

                        if not df_meas.empty:
                            df_meas = df_meas.drop(columns=['measurement'])
                            dfs[measurement] = df_meas
                            
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
                    df_daily['time'] = df_daily['time'].dt.tz_convert(timezone)

                if not df_daily.empty and 'measurement' in df_daily.columns:
                    df_daily = clean_column_names(df_daily)
                    for measurement in df_daily['measurement'].unique():
                        df_meas = df_daily[df_daily['measurement'] == measurement].copy()
                        df_meas = df_meas.drop(columns=['measurement'])
                        dfs[measurement] = df_meas
        except Exception as e:
            print(f"   ⚠️  Error loading daily summaries: {e}")

    return dfs


def load_date_range(start_date, end_date, parquet_path='../data', timezone='Europe/London'):
    """
    Load Fitbit data for a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        parquet_path: Path to data directory
        timezone: Timezone for date filtering
    
    Returns:
        dict: {'HeartRate_Intraday': df, 'SleepSummary': df, ...} with multi-day data
    """
    print(f"📥 Loading data for {start_date} to {end_date}...")
    
    # Generate date range
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    date_strs = [d.strftime('%Y-%m-%d') for d in dates]
    
    all_dfs = {}
    
    for date_str in date_strs:
        day_dfs = load_single_date(date_str, parquet_path, timezone)
        
        # Combine with existing data
        for measurement, df in day_dfs.items():
            if measurement not in all_dfs:
                all_dfs[measurement] = []
            all_dfs[measurement].append(df)
    
    # Concatenate all dataframes
    combined_dfs = {}
    for measurement, df_list in all_dfs.items():
        if df_list:
            combined_df = pd.concat(df_list, ignore_index=True)
            # Remove duplicates (e.g., same sleep session appearing in multiple days)
            if 'time' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['time'], keep='first')
            combined_dfs[measurement] = combined_df
    
    total_memory_mb = sum(df.memory_usage(deep=True).sum() for df in combined_dfs.values()) / 1024 / 1024
    print(f"   ✅ Loaded {len(combined_dfs)} measurement types")
    print(f"   💾 Memory used: {total_memory_mb:.1f} MB")
    
    return combined_dfs


def get_ordinal_suffix(day):
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix