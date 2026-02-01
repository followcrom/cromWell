"""
Metric Card Components for Fitbit Dashboard

Helper functions for displaying summary statistics as metric cards.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple


def activity_metrics_line1(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display activity-related metric cards in a row.

    Args:
        dfs: Dictionary of dataframes from load_single_date
    """
    total_steps = dfs.get("Activity-steps")
    total_calories = dfs.get("Activity-calories")
    df_breathing = dfs.get("BreathingRate")
    resting_hr = dfs.get("RestingHR")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if total_steps is not None and not total_steps.empty:
            steps = int(total_steps.iloc[0]["value"])
            st.metric("Steps", f"{steps:,}", delta=None)
        else:
            st.metric("Steps", "N/A")

    with col2:
        if resting_hr is not None and not resting_hr.empty:
            hr = int(resting_hr.iloc[0]["value"])
            st.metric("Resting HR", f"{hr} bpm")
        else:
            st.metric("Resting HR", "N/A")

    with col3:
        if df_breathing is not None and not df_breathing.empty:
            br = df_breathing["value"].iloc[0]
            st.metric("Breathing Rate", f"{br:.1f} br/min")
        else:
            st.metric("Breathing Rate", "N/A")

    with col4:
        if total_calories is not None and not total_calories.empty:
            cals = int(total_calories.iloc[0]["value"])
            st.metric("Calories", f"{cals:,}")
        else:
            st.metric("Calories", "N/A")


def activity_metrics_line2(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display extended activity metrics (HRV, breathing rate, etc.)

    Args:
        dfs: Dictionary of dataframes
    """

    df_activity_records = dfs.get("ActivityRecords")
    total_distance = dfs.get("Activity-distance")
    activity_levels = {
    'Sedentary': dfs.get('Activity-minutesSedentary'),
    'Lightly Active': dfs.get('Activity-minutesLightlyActive'),
    'Fairly Active': dfs.get('Activity-minutesFairlyActive'),
    'Very Active': dfs.get('Activity-minutesVeryActive')
}

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if df_activity_records is not None and not df_activity_records.empty:
            count = len(df_activity_records)
            activity_names = df_activity_records["ActivityName"].unique()
            activity_str = ", ".join(activity_names[:3])
            if len(activity_names) > 3:
                activity_str += f" +{len(activity_names) - 3}"
            st.metric("Logged Activities", count, delta=activity_str)
        else:
            st.metric("Logged Activities", "0")

    with col2:
        if total_distance is not None and not total_distance.empty:
            dist_km = total_distance.iloc[0]["value"]
            st.metric("Total Distance", f"{dist_km:.2f} km")
        else:
            st.metric("Distance", "N/A")


    with col3:
        active_minutes_list = []
        for level_name, df in activity_levels.items():
            if level_name != 'Sedentary' and df is not None and not df.empty:
                active_minutes_list.append(df["value"].iloc[0])
        
        if active_minutes_list:
            active_hours = sum(active_minutes_list) / 60
            st.metric("Active Time", f"{active_hours:.1f} hrs")
        else:
            st.metric("Active Time", "N/A")

    with col4:
        sedentary_df = activity_levels.get('Sedentary')
        if sedentary_df is not None and not sedentary_df.empty:
            sedentary_minutes = sedentary_df["value"].iloc[0]
            sedentary_hours = sedentary_minutes / 60
            st.metric("Sedentary Time", f"{sedentary_hours:.1f} hrs")
        else:
            st.metric("Sedentary Time", "N/A")

def activity_metrics_avgs1(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display average activity metrics over a date range.

    Args:
        dfs: Dictionary of dataframes from load_date_range
    """
    total_steps = dfs.get("Activity-steps")
    total_calories = dfs.get("Activity-calories")
    df_breathing = dfs.get("BreathingRate")
    resting_hr = dfs.get("RestingHR")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if total_steps is not None and not total_steps.empty:
            avg_steps = int(total_steps["value"].mean())
            st.metric("Avg Steps", f"{avg_steps:,}")
        else:
            st.metric("Avg Steps", "N/A")

    with col2:
        if resting_hr is not None and not resting_hr.empty:
            avg_hr = int(resting_hr["value"].mean())
            st.metric("Avg Resting HR", f"{avg_hr} bpm")
        else:
            st.metric("Avg Resting HR", "N/A")

    with col3:
        if df_breathing is not None and not df_breathing.empty:
            avg_br = df_breathing["value"].mean()
            st.metric("Avg Breathing Rate", f"{avg_br:.1f} br/min")
        else:
            st.metric("Avg Breathing Rate", "N/A")


    with col4:
        if total_calories is not None and not total_calories.empty:
            avg_cals = int(total_calories["value"].mean())
            st.metric("Avg Calories", f"{avg_cals:,}")
        else:
            st.metric("Avg Calories", "N/A")


def activity_metrics_avgs2(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display average extended activity metrics over a date range.

    Args:
        dfs: Dictionary of dataframes from load_date_range
    """

    df_activity_records = dfs.get("ActivityRecords")
    total_distance = dfs.get("Activity-distance")
    activity_levels = {
        'Sedentary': dfs.get('Activity-minutesSedentary'),
        'Lightly Active': dfs.get('Activity-minutesLightlyActive'),
        'Fairly Active': dfs.get('Activity-minutesFairlyActive'),
        'Very Active': dfs.get('Activity-minutesVeryActive')
    }

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if df_activity_records is not None and not df_activity_records.empty:
            total_activities = len(df_activity_records)
            st.metric("Total Logged Activities", total_activities)
        else:
            st.metric("Total Logged Activities", "0")

    with col2:
        if total_distance is not None and not total_distance.empty:
            avg_dist_km = total_distance["value"].mean()
            st.metric("Avg Distance", f"{avg_dist_km:.2f} km")
        else:
            st.metric("Avg Distance", "N/A")

    with col3:
        # Calculate average active time (excluding sedentary)
        active_minutes_list = []
        for level_name, df in activity_levels.items():
            if level_name != 'Sedentary' and df is not None and not df.empty:
                active_minutes_list.append(df["value"])

        if active_minutes_list:
            # Sum all active minutes and calculate number of days from data
            all_active_values = pd.concat(active_minutes_list, ignore_index=True)
            # Count unique dates in one of the dataframes to get number of days
            sample_df = next(df for df in activity_levels.values() if df is not None and not df.empty)
            num_days = sample_df['date'].nunique() if 'date' in sample_df.columns else len(sample_df)
            avg_active_minutes = all_active_values.sum() / num_days
            avg_active_hours = avg_active_minutes / 60
            st.metric("Avg Active Time", f"{avg_active_hours:.1f} hrs")
        else:
            st.metric("Avg Active Time", "N/A")

    with col4:
        sedentary_df = activity_levels.get('Sedentary')
        if sedentary_df is not None and not sedentary_df.empty:
            avg_sedentary_minutes = sedentary_df["value"].mean()
            avg_sedentary_hours = avg_sedentary_minutes / 60
            st.metric("Avg Sedentary Time", f"{avg_sedentary_hours:.1f} hrs")
        else:
            st.metric("Avg Sedentary Time", "N/A")


def activity_summary_table(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display a summary table of logged activities.

    Args:
        dfs: Dictionary of dataframes
    """
    df_activities = dfs.get("ActivityRecords")

    if df_activities is None or df_activities.empty:
        st.info("No logged activities for this date")
        return

    # Create summary table
    records = []
    for _, row in df_activities.sort_values("time").iterrows():
        duration_min = row.get("duration", 0) / 1000 / 60
        records.append(
            {
            "Activity": row.get("ActivityName", "Unknown"),
            "Date": row["time"].strftime("%a %d %b"),
            "Start": row["time"].strftime("%H:%M"),
            "Duration": f"{int(duration_min)} min",
            "Distance (km)": (
            f"{row.get('distance', 0) * 1.60934:.2f}"
            if pd.notna(row.get("distance")) and row.get("distance", 0) > 0
            else "-"
            ),
            "Distance (mi)": (
            f"{row.get('distance', 0):.2f}"
            if pd.notna(row.get("distance")) and row.get("distance", 0) > 0
            else "-"
            ),
            "Calories": f"{int(row.get('calories', 0))} cal",
            "Avg HR": (
            f"{int(row.get('averageHeartRate', 0))} bpm"
            if pd.notna(row.get("averageHeartRate"))
            else "-"
            ),
            }
        )

    df_table = pd.DataFrame(records)
    st.dataframe(df_table, use_container_width=True, hide_index=True)



def calculate_activity_levels(dfs: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    Calculate activity level data from dataframes.

    Args:
        dfs: Dictionary of dataframes

    Returns:
        List of dicts with level data
    """
    levels = {
        "Sedentary": dfs.get("Activity-minutesSedentary"),
        "Lightly Active": dfs.get("Activity-minutesLightlyActive"),
        "Fairly Active": dfs.get("Activity-minutesFairlyActive"),
        "Very Active": dfs.get("Activity-minutesVeryActive"),
    }

    level_data = []
    total_minutes = 0

    for level_name, df in levels.items():
        if df is not None and not df.empty:
            minutes = df.iloc[0]["value"]
            total_minutes += minutes
            level_data.append(
                {
                    "level": level_name,
                    "minutes": minutes,
                    "hours": minutes / 60,
                }
            )

    # Calculate percentages
    for item in level_data:
        item["percentage"] = (
            (item["minutes"] / total_minutes) * 100 if total_minutes > 0 else 0
        )

    return level_data


def calculate_hr_zone_data(df_hr: pd.DataFrame) -> List[Dict]:
    """
    Calculate time spent in each HR zone.

    Args:
        df_hr: Heart rate intraday dataframe

    Returns:
        List of dicts with zone data
    """
    if df_hr is None or df_hr.empty:
        return []

    hr_zones = {
        "Out of Range": (0, 97),
        "Fat Burn": (98, 122),
        "Cardio": (123, 154),
        "Peak": (155, 220),
    }

    zone_data = []
    total_samples = len(df_hr)

    for zone_name, (low, high) in hr_zones.items():
        in_zone = df_hr[(df_hr["value"] >= low) & (df_hr["value"] < high)]
        minutes = len(in_zone) / 60  # Assuming 1 sample per second
        percentage = (len(in_zone) / total_samples) * 100 if total_samples > 0 else 0

        zone_data.append(
            {
                "zone": zone_name,
                "minutes": minutes,
                "hours": minutes / 60,
                "percentage": percentage,
            }
        )

    return zone_data


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
