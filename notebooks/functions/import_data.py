import json
import gzip
import pandas as pd
from datetime import datetime
import boto3
from io import BytesIO

def get_fitbit_data_for_date(date_str):
    """
    Fetch Fitbit data for a specific date from S3.
    
    Args:
        date_str: Date in format 'YYYY-MM-DD'
    
    Returns:
        dict: Dictionary of DataFrames by measurement type
    """
    # Parse the date
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date must be in format 'YYYY-MM-DD'")
    
    # Build the file key with your actual naming convention
    file_key = f"cromwell/fitbit/fitbit_backup_{date.strftime('%Y-%m-%d')}.json.gz"
    
    print(f"📥 Fetching data for {date.strftime('%Y-%m-%d')} from S3...")
    print(f"   File: {file_key}")
    
    # Fetch from S3
    bucket_name = 'followcrom'
    session = boto3.Session(profile_name='surface')
    s3 = session.client('s3')
    
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        with gzip.GzipFile(fileobj=BytesIO(response['Body'].read())) as f:
            data = json.load(f)
        
        print(f"✅ Loaded {len(data)} records")
        
        # Parse all data
        dfs = parse_fitbit_data(data)
        
        print(f"📊 Found {len(dfs)} measurement types:")
        for measurement, df in dfs.items():
            print(f"   - {measurement}: {len(df)} records")
        
        return dfs
        
    except s3.exceptions.NoSuchKey:
        print(f"❌ No data found for {date.strftime('%Y-%m-%d')}")
        print(f"   File not found: {file_key}")
        return None
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None


def convert_activity_distances_to_km(df_activities):
    """
    Convert ActivityRecords distances from miles to kilometers.

    Fitbit API returns ALL activity distances in MILES (GPS, treadmill, swimming, etc.).
    This function converts them to kilometers and recalculates pace/speed.

    Args:
        df_activities: DataFrame with ActivityRecords (can be from Parquet or S3)

    Returns:
        DataFrame with distances converted to km
    """
    if df_activities.empty or 'distance' not in df_activities.columns:
        return df_activities

    # Conversion constant
    MILES_TO_KM = 1.609344

    # Work on a copy to avoid modifying the original
    df = df_activities.copy()

    # Only convert if distance exists and is > 0
    mask = (df['distance'].notna()) & (df['distance'] > 0)

    if mask.any():
        # Store original distance in miles
        df.loc[mask, 'distance_miles'] = df.loc[mask, 'distance']

        # Convert to kilometers
        df.loc[mask, 'distance'] = df.loc[mask, 'distance'] * MILES_TO_KM

        # Recalculate pace (seconds per km) with corrected distance
        if 'duration' in df.columns:
            duration_mask = mask & (df['duration'].notna())
            duration_seconds = df.loc[duration_mask, 'duration'] / 1000  # duration is in milliseconds
            df.loc[duration_mask, 'pace'] = duration_seconds / df.loc[duration_mask, 'distance']

        # Recalculate speed (km/h) with corrected distance
        if 'duration' in df.columns:
            duration_mask = mask & (df['duration'].notna())
            duration_hours = (df.loc[duration_mask, 'duration'] / 1000) / 3600
            df.loc[duration_mask, 'speed'] = df.loc[duration_mask, 'distance'] / duration_hours

    return df


def parse_fitbit_data(data):
    """Parse the list of measurements into separate DataFrames by measurement type"""

    # Conversion constant
    MILES_TO_KM = 1.609344

    # Group data by measurement type
    measurements_dict = {}
    for record in data:
        measurement = record['measurement']
        if measurement not in measurements_dict:
            measurements_dict[measurement] = []
        measurements_dict[measurement].append(record)

    # Convert each measurement type to a DataFrame
    dfs = {}

    for measurement, records in measurements_dict.items():
        parsed_records = []
        for record in records:
            flat_record = {
                'time': pd.to_datetime(record['time']),
            }

            # Add all tags
            if 'tags' in record:
                for tag_key, tag_value in record['tags'].items():
                    flat_record[tag_key] = tag_value

            # Add all fields
            if 'fields' in record:
                flat_record.update(record['fields'])

            # FIX: Convert distance from miles to km for ALL activities
            # Fitbit API returns distance in MILES for all activities (GPS, treadmill, swimming, etc.)
            if measurement == 'ActivityRecords' and 'distance' in flat_record and flat_record['distance'] is not None and flat_record['distance'] > 0:
                # Store original distance in miles
                flat_record['distance_miles'] = flat_record['distance']
                # Convert to kilometers
                flat_record['distance'] = flat_record['distance'] * MILES_TO_KM

                # Recalculate pace (seconds per km) with corrected distance
                if 'duration' in flat_record and flat_record['distance'] > 0:
                    duration_seconds = flat_record['duration'] / 1000  # duration is in milliseconds
                    flat_record['pace'] = duration_seconds / flat_record['distance']

                # Recalculate speed (km/h) with corrected distance
                if 'duration' in flat_record and flat_record['distance'] > 0:
                    duration_hours = (flat_record['duration'] / 1000) / 3600
                    flat_record['speed'] = flat_record['distance'] / duration_hours

            parsed_records.append(flat_record)

        # Create DataFrame
        df = pd.DataFrame(parsed_records)
        df = df.sort_values('time').reset_index(drop=True)

        dfs[measurement] = df

    return dfs