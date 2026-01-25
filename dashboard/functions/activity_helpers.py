import pandas as pd
from typing import Tuple


def extract_activity_time_window(
    activity_record: pd.Series,
    timezone: str = 'Europe/London'
) -> Tuple[pd.Timestamp, pd.Timestamp, float]:
    """
    Extract and properly handle activity start/end times.

    NOTE: Fitbit API returns timestamps in local time but marked as UTC.
    We need to strip the UTC timezone and re-localize to the actual timezone.

    Parameters:
    - activity_record: Single activity record (Series)
    - timezone: Target timezone for display

    Returns:
    - (activity_start, activity_end, duration_minutes)
    """
    # Get activity start time
    activity_start = pd.to_datetime(activity_record['time'])

    # Fitbit quirk: timestamps are in local time but marked as UTC
    # Solution: Remove timezone and re-localize to actual timezone
    if activity_start.tz is not None:
        # Strip timezone (convert to naive) then localize to actual timezone
        activity_start = activity_start.tz_localize(None).tz_localize(timezone)
    else:
        # If no timezone, localize to target timezone
        activity_start = activity_start.tz_localize(timezone)

    # Calculate duration and end time
    duration_ms = activity_record.get('duration', 0)
    duration_minutes = duration_ms / 1000 / 60
    activity_end = activity_start + pd.Timedelta(minutes=duration_minutes)

    return activity_start, activity_end, duration_minutes

