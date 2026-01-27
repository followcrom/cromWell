"""
Metric Card Components for Fitbit Dashboard

Helper functions for displaying summary statistics as metric cards.
"""

import streamlit as st
import pandas as pd
from typing import Dict

def display_sleep_metrics(dfs: Dict[str, pd.DataFrame]) -> None:
    """
    Display sleep-related metric cards.

    Args:
        dfs: Dictionary of dataframes
    """
    df_summary = dfs.get("SleepSummary")

    # Get main sleep session
    main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    summary = main_sleep.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mins_in_bed = summary.get("minutesInBed", 0)
        hours = int(mins_in_bed // 60)
        mins = int(mins_in_bed % 60)
        st.metric("Time in Bed", f"{hours}h {mins}m")

    with col2:
        mins_asleep = summary.get("minutesAsleep", 0)
        hours = int(mins_asleep // 60)
        mins = int(mins_asleep % 60)
        st.metric("Time on Task", f"{hours}h {mins}m")

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
        if df_hrv is not None and not df_hrv.empty:
            hrv = df_hrv["dailyRmssd"].iloc[0]
            st.metric("HRV (avg)", f"{hrv:.1f} ms")
        else:
            st.metric("HRV (avg)", "N/A")

    with col2:
        if df_spo2 is not None and not df_spo2.empty:
            avg = df_spo2["avg"].iloc[0]
            st.metric("Blood Oxygen Saturation (avg)", f"{avg:.1f}%")
        else:
            st.metric("Blood Oxygen Saturation (avg)", "N/A")

    with col3:
        if df_spo2 is not None and not df_spo2.empty:
            min_val = df_spo2["min"].iloc[0]
            max_val = df_spo2["max"].iloc[0]
            st.metric("SpO2 Range", f"{min_val:.1f}% - {max_val:.1f}%")
        else:
            st.metric("SpO2 Range", "N/A")

    with col4:
        if df_skin_temp is not None and not df_skin_temp.empty:
            temp = df_skin_temp["nightlyRelative"].iloc[0]
            sign = "+" if temp >= 0 else ""
            st.metric("Skin Temp (relative)", f"{sign}{temp:.1f}°")
        else:
            st.metric("Skin Temp", "N/A")


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
        mins_awake = row.get("minutesAwake", 0)

        end_time = row.get("end_time") or row.get("endTime")
        if end_time:
            end_str = pd.to_datetime(end_time).strftime("%H:%M")
        else:
            end_str = "-"

        start_str = row["time"].strftime("%H:%M")
        records.append(
            {
            "Date": f"{row['time'].strftime('%a %d')} - {row['endTime'].strftime('%a %d %b')}",
            "Type": "Main Sleep" if is_main else "Nap",
            "To Bed": start_str,
            "Up": end_str,
            "Time in Bed": f"{int(mins_in_bed // 60)}h {int(mins_in_bed % 60)}m",
            "Time Asleep": f"{int(mins_asleep // 60)}h {int(mins_asleep % 60)}m",
            "Time Awake": f"{int(mins_awake // 60)}h {int(mins_awake % 60)}m",
            "Efficiency": f"{row.get('efficiency', 0):.0f}%",
            }
        )

    df_table = pd.DataFrame(records)
    st.dataframe(df_table, use_container_width=True, hide_index=True)