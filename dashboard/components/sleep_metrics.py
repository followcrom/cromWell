"""
Metric Card Components for Fitbit Dashboard

Helper functions for displaying summary statistics as metric cards.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List

def display_sleep_metrics(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display sleep-related metric cards.

    Args:
        dfs: Dictionary of dataframes
    """
    df_summary = dfs.get("SleepSummary")

    if df_summary is None or df_summary.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Time Asleep", "N/A")
        with col2:
            st.metric("Efficiency", "N/A")
        with col3:
            st.metric("Deep Sleep", "N/A")
        with col4:
            st.metric("REM Sleep", "N/A")
        return

    # Get main sleep session
    main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    summary = main_sleep.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mins_asleep = summary.get("minutesAsleep", 0)
        hours = int(mins_asleep // 60)
        mins = int(mins_asleep % 60)
        st.metric("Time Asleep", f"{hours}h {mins}m")

    with col2:
        efficiency = summary.get("efficiency", 0)
        st.metric("Efficiency", f"{efficiency:.0f}%")

    with col3:
        deep = summary.get("minutesDeep", 0)
        deep_pct = (deep / mins_asleep * 100) if mins_asleep > 0 else 0
        st.metric("Deep Sleep", f"{int(deep)}m ({deep_pct:.0f}%)")

    with col4:
        rem = summary.get("minutesREM", 0)
        rem_pct = (rem / mins_asleep * 100) if mins_asleep > 0 else 0
        st.metric("REM Sleep", f"{int(rem)}m ({rem_pct:.0f}%)")


def display_sleep_vitals(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display sleep-related vitals (SpO2, skin temp).

    Args:
        dfs: Dictionary of dataframes
    """
    df_spo2 = dfs.get("SPO2_Daily")
    df_skin_temp = dfs.get("SkinTemperature")
    df_hrv = dfs.get('HRV')

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if df_spo2 is not None and not df_spo2.empty:
            avg = df_spo2["avg"].iloc[0]
            st.metric("SpO2 (avg)", f"{avg:.1f}%")
        else:
            st.metric("SpO2 (avg)", "N/A")

    with col2:
        if df_spo2 is not None and not df_spo2.empty:
            min_val = df_spo2["min"].iloc[0]
            max_val = df_spo2["max"].iloc[0]
            st.metric("SpO2 Range", f"{min_val:.1f}% - {max_val:.1f}%")
        else:
            st.metric("SpO2 Range", "N/A")

    with col3:
        if df_skin_temp is not None and not df_skin_temp.empty:
            temp = df_skin_temp["nightlyRelative"].iloc[0]
            sign = "+" if temp >= 0 else ""
            st.metric("Skin Temp (relative)", f"{sign}{temp:.1f}°")
        else:
            st.metric("Skin Temp", "N/A")

    with col4:
        if df_hrv is not None and not df_hrv.empty:
            hrv = df_hrv["dailyRmssd"].iloc[0]
            st.metric("HRV (avg)", f"{hrv:.1f} ms")
        else:
            st.metric("HRV (avg)", "N/A")

# def activity_summary_table(dfs: Dict[str, pd.DataFrame]) -> None:
#     """
#     Display a summary table of logged activities.

#     Args:
#         dfs: Dictionary of dataframes
#     """
#     df_activities = dfs.get("ActivityRecords")

#     if df_activities is None or df_activities.empty:
#         st.info("No logged activities for this date")
#         return

#     # Create summary table
#     records = []
#     for _, row in df_activities.sort_values("time").iterrows():
#         duration_min = row.get("duration", 0) / 1000 / 60
#         records.append(
#             {
#             "Activity": row.get("ActivityName", "Unknown"),
#             "Start": row["time"].strftime("%H:%M"),
#             "Distance (mi)": (
#                 f"{row.get('distance', 0):.2f}"
#                 if pd.notna(row.get("distance")) and row.get("distance", 0) > 0
#                 else "-"
#             ),
#             "Distance (km)": (
#                 f"{row.get('distance', 0) * 1.60934:.2f}"
#                 if pd.notna(row.get("distance")) and row.get("distance", 0) > 0
#                 else "-"
#             ),
#             "Duration": f"{int(duration_min)} min",
#             "Calories": int(row.get("calories", 0)),
#             "Avg HR": (
#                 f"{int(row.get('averageHeartRate', 0))} bpm"
#                 if pd.notna(row.get("averageHeartRate"))
#                 else "-"
#             ),
#             }
#         )

#     df_table = pd.DataFrame(records)
#     st.dataframe(df_table, use_container_width=True, hide_index=True)


def display_sleep_sessions_table(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display a table of sleep sessions.

    Args:
        dfs: Dictionary of dataframes
    """
    df_summary = dfs.get("SleepSummary")

    if df_summary is None or df_summary.empty:
        st.info("No sleep data for this date")
        return

    records = []
    for _, row in df_summary.sort_values("time").iterrows():
        is_main = row.get("isMainSleep", "True") == "True"
        mins_in_bed = row.get("minutesInBed", 0)
        mins_asleep = row.get("minutesAsleep", 0)

        end_time = row.get("end_time") or row.get("endTime")
        if end_time:
            end_str = pd.to_datetime(end_time).strftime("%H:%M")
        else:
            end_str = "-"

        records.append(
            {
                "Date": row["time"].strftime("%a %d %b"),
                "Type": "Main Sleep" if is_main else "Nap",
                "To Bed": row["time"].strftime("%H:%M"),
                "Wake Up": end_str,
                "In Bed": f"{int(mins_in_bed // 60)}h {int(mins_in_bed % 60)}m",
                "Asleep": f"{int(mins_asleep // 60)}h {int(mins_asleep % 60)}m",
                # "Efficiency": f"{row.get('efficiency', 0):.0f}%",
            }
        )

    df_table = pd.DataFrame(records)
    st.dataframe(df_table, use_container_width=True, hide_index=True)


# def calculate_activity_levels(dfs: Dict[str, pd.DataFrame]) -> List[Dict]:
#     """
#     Calculate activity level data from dataframes.

#     Args:
#         dfs: Dictionary of dataframes

#     Returns:
#         List of dicts with level data
#     """
#     levels = {
#         "Sedentary": dfs.get("Activity-minutesSedentary"),
#         "Lightly Active": dfs.get("Activity-minutesLightlyActive"),
#         "Fairly Active": dfs.get("Activity-minutesFairlyActive"),
#         "Very Active": dfs.get("Activity-minutesVeryActive"),
#     }

#     level_data = []
#     total_minutes = 0

#     for level_name, df in levels.items():
#         if df is not None and not df.empty:
#             minutes = df.iloc[0]["value"]
#             total_minutes += minutes
#             level_data.append(
#                 {
#                     "level": level_name,
#                     "minutes": minutes,
#                     "hours": minutes / 60,
#                 }
#             )

#     # Calculate percentages
#     for item in level_data:
#         item["percentage"] = (
#             (item["minutes"] / total_minutes) * 100 if total_minutes > 0 else 0
#         )

#     return level_data


# def calculate_hr_zone_data(df_hr: pd.DataFrame) -> List[Dict]:
#     """
#     Calculate time spent in each HR zone.

#     Args:
#         df_hr: Heart rate intraday dataframe

#     Returns:
#         List of dicts with zone data
#     """
#     if df_hr is None or df_hr.empty:
#         return []

#     hr_zones = {
#         "Out of Range": (0, 97),
#         "Fat Burn": (98, 122),
#         "Cardio": (123, 154),
#         "Peak": (155, 220),
#     }

#     zone_data = []
#     total_samples = len(df_hr)

#     for zone_name, (low, high) in hr_zones.items():
#         in_zone = df_hr[(df_hr["value"] >= low) & (df_hr["value"] < high)]
#         minutes = len(in_zone) / 60  # Assuming 1 sample per second
#         percentage = (len(in_zone) / total_samples) * 100 if total_samples > 0 else 0

#         zone_data.append(
#             {
#                 "zone": zone_name,
#                 "minutes": minutes,
#                 "hours": minutes / 60,
#                 "percentage": percentage,
#             }
#         )

#     return zone_data
