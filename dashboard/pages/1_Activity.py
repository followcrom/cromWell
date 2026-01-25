"""
Activity Analysis Page

Displays activity metrics, heart rate analysis, and workout details.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import sys

# Add dashboard root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import (
    create_hr_timeline,
    create_hourly_steps_chart,
    create_activity_levels_chart,
    create_gps_route_map,
    create_hr_zones_chart,
    display_activity_metrics,
    display_extended_activity_metrics,
    display_activity_summary_table,
    calculate_activity_levels,
    calculate_hr_zone_data,
)

from functions import load_single_date, load_date_range, extract_activity_time_window

# Configuration
DATA_PATH = Path(__file__).parent.parent.parent / "data"
TIMEZONE = "Europe/London"

st.set_page_config(
    page_title="Activity - Fitbit Dashboard",
    page_icon="🏃",
    layout="wide",
)


def get_ordinal_suffix(day: int) -> str:
    """Get ordinal suffix for a day number."""
    if 10 <= day % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_date(d: date) -> str:
    """Format date with ordinal suffix."""
    day = d.day
    suffix = get_ordinal_suffix(day)
    return d.strftime(f"%A {day}{suffix} %B %Y")


def init_session_state():
    """Initialize session state."""
    if "date_mode" not in st.session_state:
        st.session_state.date_mode = "Single Date"
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today() - timedelta(days=1)
    if "start_date" not in st.session_state:
        st.session_state.start_date = date.today() - timedelta(days=7)
    if "end_date" not in st.session_state:
        st.session_state.end_date = date.today() - timedelta(days=1)


def render_sidebar():
    """Render sidebar with date controls."""
    with st.sidebar:
        st.title("Fitbit Dashboard")
        st.markdown("---")

        st.session_state.date_mode = st.radio(
            "Date Selection",
            ["Single Date", "Date Range"],
            index=0 if st.session_state.date_mode == "Single Date" else 1,
        )

        st.markdown("---")

        if st.session_state.date_mode == "Single Date":
            st.session_state.selected_date = st.date_input(
                "Select Date",
                value=st.session_state.selected_date,
                max_value=date.today(),
            )
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.start_date = st.date_input(
                    "Start Date",
                    value=st.session_state.start_date,
                    max_value=date.today(),
                )
            with col2:
                st.session_state.end_date = st.date_input(
                    "End Date",
                    value=st.session_state.end_date,
                    max_value=date.today(),
                )

        st.markdown("---")
        st.markdown("### Navigation")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Activity.py", label="Activity", icon="🏃")
        st.page_link("pages/2_Sleep.py", label="Sleep", icon="😴")


@st.cache_data(ttl=300)
def load_data(date_str: str):
    """Load data for a single date with caching."""
    return load_single_date(date_str, str(DATA_PATH), TIMEZONE)


@st.cache_data(ttl=300)
def load_range_data(start_str: str, end_str: str):
    """Load data for a date range with caching."""
    return load_date_range(start_str, end_str, str(DATA_PATH), TIMEZONE)


def render_single_day_activity(dfs: dict, selected_date: date):
    """Render activity analysis for a single day."""
    formatted = format_date(selected_date)
    st.title(f"Activity Analysis")
    st.markdown(f"### {formatted}")

    # Metrics row
    st.markdown("---")
    display_activity_metrics(dfs)
    display_extended_activity_metrics(dfs)

    # Heart Rate Timeline
    st.markdown("---")
    st.subheader("Heart Rate Timeline")

    df_hr = dfs.get("HeartRate_Intraday")
    df_activities = dfs.get("ActivityRecords")

    if df_hr is not None and not df_hr.empty:
        fig = create_hr_timeline(
            df_hr,
            df_activities,
            title=f"Heart Rate - {formatted}",
        )
        st.plotly_chart(fig, width='stretch')

        # HR Zones
        zone_data = calculate_hr_zone_data(df_hr)
        if zone_data:
            st.subheader("Time in Heart Rate Zones")
            fig_zones = create_hr_zones_chart(zone_data)
            st.plotly_chart(fig_zones, width='stretch')
    else:
        st.info("No heart rate data available for this date")

    # Hourly Steps and Activity Levels side by side
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Hourly Steps")
        df_steps = dfs.get("Steps_Intraday")
        if df_steps is not None and not df_steps.empty:
            fig_steps = create_hourly_steps_chart(df_steps)
            st.plotly_chart(fig_steps, width='stretch')
        else:
            st.info("No steps data available")

    with col2:
        st.subheader("Activity Levels")
        level_data = calculate_activity_levels(dfs)
        if level_data:
            fig_levels = create_activity_levels_chart(level_data)
            st.plotly_chart(fig_levels, width='stretch')
        else:
            st.info("No activity level data available")

    # Logged Activities
    st.markdown("---")
    st.subheader("Logged Activities")
    display_activity_summary_table(dfs)

    # Per-activity analysis
    if df_activities is not None and not df_activities.empty:
        st.markdown("---")
        st.subheader("Activity Details")

        for idx, (_, activity) in enumerate(df_activities.sort_values("time").iterrows()):
            activity_name = activity.get("ActivityName", "Unknown")
            with st.expander(f"{activity_name} - {activity['time'].strftime('%H:%M')}"):
                render_activity_details(activity, df_hr, dfs.get("GPS"))


def render_activity_details(activity: pd.Series, df_hr: pd.DataFrame, df_gps: pd.DataFrame):
    """Render detailed analysis for a single activity."""
    # Basic info
    col1, col2, col3, col4 = st.columns(4)

    duration_min = activity.get("duration", 0) / 1000 / 60

    with col1:
        st.metric("Duration", f"{int(duration_min)} min")

    with col2:
        calories = activity.get("calories", 0)
        st.metric("Calories", f"{int(calories)}")

    with col3:
        avg_hr = activity.get("averageHeartRate")
        if pd.notna(avg_hr):
            st.metric("Avg HR", f"{int(avg_hr)} bpm")
        else:
            st.metric("Avg HR", "N/A")

    with col4:
        distance = activity.get("distance")
        if pd.notna(distance) and distance > 0:
            st.metric("Distance", f"{distance:.2f} mi")
        else:
            st.metric("Distance", "N/A")

    # Activity-specific HR analysis
    if df_hr is not None and not df_hr.empty:
        try:
            activity_start, activity_end, _ = extract_activity_time_window(
                activity, TIMEZONE
            )

            # Filter HR data for this activity window
            activity_hr = df_hr[
                (df_hr["time"] >= activity_start) & (df_hr["time"] <= activity_end)
            ]

            if not activity_hr.empty:
                st.markdown("**Heart Rate During Activity**")
                fig = create_hr_timeline(
                    activity_hr,
                    title=f"HR during {activity.get('ActivityName', 'Activity')}",
                )
                st.plotly_chart(fig, width='stretch')

                # HR stats
                vals = activity_hr["value"]
                st.markdown(
                    f"**HR Stats:** Min: {vals.min():.0f} | Avg: {vals.mean():.0f} | Max: {vals.max():.0f} bpm"
                )
        except Exception as e:
            st.warning(f"Could not analyze activity HR: {e}")

    # GPS map for walks
    activity_name = activity.get("ActivityName", "").lower()
    if "walk" in activity_name and df_gps is not None and not df_gps.empty:
        try:
            activity_start, activity_end, _ = extract_activity_time_window(
                activity, TIMEZONE
            )

            # Filter GPS data for this activity
            walk_gps = df_gps[
                (df_gps["time"] >= activity_start) & (df_gps["time"] <= activity_end)
            ]

            if not walk_gps.empty:
                st.markdown("**Route Map**")
                fig_map = create_gps_route_map(walk_gps)
                st.plotly_chart(fig_map, width='stretch')
        except Exception:
            pass  # GPS may not be available


def render_multi_day_activity(dfs: dict, start_date: date, end_date: date):
    """Render activity analysis for multiple days."""
    st.title("Activity Analysis")
    st.markdown(f"### {format_date(start_date)} to {format_date(end_date)}")

    st.info("Multi-day activity analysis shows aggregated data across the date range.")

    # Show metrics (will be averaged/totaled as appropriate)
    st.markdown("---")
    display_activity_metrics(dfs)

    # HR timeline for the entire range
    st.markdown("---")
    st.subheader("Heart Rate Overview")

    df_hr = dfs.get("HeartRate_Intraday")
    if df_hr is not None and not df_hr.empty:
        fig = create_hr_timeline(df_hr, title="Heart Rate - Date Range")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No heart rate data available")

    # Activity levels aggregate
    st.markdown("---")
    st.subheader("Activity Levels")
    level_data = calculate_activity_levels(dfs)
    if level_data:
        fig_levels = create_activity_levels_chart(level_data)
        st.plotly_chart(fig_levels, width='stretch')

    # All logged activities
    st.markdown("---")
    st.subheader("All Logged Activities")
    display_activity_summary_table(dfs)


def main():
    """Main entry point for Activity page."""
    init_session_state()
    render_sidebar()

    # Load data based on mode
    if st.session_state.date_mode == "Single Date":
        date_str = st.session_state.selected_date.strftime("%Y-%m-%d")

        with st.spinner("Loading data..."):
            dfs = load_data(date_str)

        if not dfs:
            st.warning(f"No data available for {date_str}")
            return

        render_single_day_activity(dfs, st.session_state.selected_date)

    else:
        # Date range mode
        if st.session_state.start_date > st.session_state.end_date:
            st.error("Start date must be before end date")
            return

        start_str = st.session_state.start_date.strftime("%Y-%m-%d")
        end_str = st.session_state.end_date.strftime("%Y-%m-%d")

        with st.spinner("Loading data..."):
            dfs = load_range_data(start_str, end_str)

        if not dfs:
            st.warning(f"No data available for {start_str} to {end_str}")
            return

        render_multi_day_activity(
            dfs, st.session_state.start_date, st.session_state.end_date
        )


if __name__ == "__main__":
    main()
