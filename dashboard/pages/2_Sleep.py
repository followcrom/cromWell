"""
Sleep Analysis Page

Displays sleep metrics, stage analysis, and multi-day trends.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import sys

# Add dashboard root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import (
    plot_sleep_timeline,
    plot_nap_timeline,
    create_sleep_stages_donut,
    create_sleep_stages_bar,
    create_hourly_steps_chart,
    create_multi_day_sleep_timeline,
    create_consolidated_sleep_timeline,
    create_spo2_trend_chart,
    create_hrv_trend_chart,
    create_skin_temp_trend_chart,
    create_sleep_efficiency_trend_chart,
    create_sleep_stages_stacked_histogram,
    display_sleep_metrics,
    display_sleep_vitals,
    display_sleep_sessions_table,
)

from functions import (
    DATA_PATH,
    TIMEZONE,
    load_single_date,
    load_date_range,
    init_session_state,
    render_sidebar,
    format_date,
)


# Sleep stage mapping
LEVEL_DECODE = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}

st.set_page_config(
    page_title="CromWell's Dashboard - Sleep",
    page_icon="😴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit's default page navigation and reduce top whitespace
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        section[data-testid="stSidebar"] > div {
            padding-top: 0.1rem;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data(date_str: str):
    """Load data for a single date with caching."""
    return load_single_date(date_str, str(DATA_PATH), TIMEZONE)


@st.cache_data(ttl=300)
def load_range_data(start_str: str, end_str: str):
    """Load data for a date range with caching."""
    return load_date_range(start_str, end_str, str(DATA_PATH), TIMEZONE)


def extract_and_preprocess_sleep_data(dfs: dict) -> tuple:
    """
    Extract and preprocess sleep data by adding computed columns.

    Returns:
        Tuple of (df_levels, df_summary) with computed columns
    """
    df_levels = dfs.get("SleepLevels")
    df_summary = dfs.get("SleepSummary")

    if df_levels is not None and not df_levels.empty:
        df_levels = df_levels.copy()
        if "duration_seconds" in df_levels.columns:
            df_levels["end_time"] = df_levels["time"] + pd.to_timedelta(
                df_levels["duration_seconds"], unit="s"
            )
        if "level_name" not in df_levels.columns:
            df_levels["level_name"] = df_levels["level"].map(LEVEL_DECODE)

    if df_summary is not None and not df_summary.empty:
        df_summary = df_summary.copy()
        if "endTime" in df_summary.columns and "end_time" not in df_summary.columns:
            df_summary["end_time"] = pd.to_datetime(df_summary["endTime"])
            if df_summary["end_time"].dt.tz is None:
                df_summary["end_time"] = df_summary["end_time"].dt.tz_localize("UTC")
            df_summary["end_time"] = df_summary["end_time"].dt.tz_convert(TIMEZONE)
            df_summary = df_summary.drop(columns=["endTime"]) # we can drop endTime because we have end_time now, which is tz-aware

    return df_levels, df_summary


def render_single_day_sleep(dfs: dict, selected_date: date):
    """Render sleep analysis for a single day."""
    formatted = format_date(selected_date)
    st.title("Single-Day Sleep Analysis")
    st.markdown(f"## {formatted}")

    df_levels, df_summary = extract_and_preprocess_sleep_data(dfs)

    if df_summary is None or df_summary.empty:
        st.warning("No sleep data available for this date")
        return

    # Metrics row
    st.markdown("---")
    st.subheader("Main Sleep Summary")
    display_sleep_metrics(dfs)
    display_sleep_vitals(dfs)

    # Sleep Sessions Table
    st.markdown("---")
    st.subheader("Sleep Sessions")
    display_sleep_sessions_table(dfs)

    # ==========================================================================
    # MAIN SLEEP TIMELINE: 27-hour window from 21:00 to 00:00 next day
    # Window is based on wake-up time (end_time) of main sleep session
    # ==========================================================================
    st.markdown("---")
    st.subheader(f"Sleep Timeline for {formatted}")

    if df_levels is not None and not df_levels.empty:
        # Get main sleep for window calculation
        main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
        if main_sleep.empty:
            main_sleep = df_summary.iloc[[0]]

        main_session = main_sleep.iloc[0]
        sleep_start = main_session["time"]
        sleep_end = main_session.get("end_time") or main_session.get("endTime")

        # Display sleep times
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"To Bed: {sleep_start.strftime('%H:%M on %a %d %b')}")
        with col2:
            if sleep_end:   
                end_ts = pd.to_datetime(sleep_end)
                st.info(f"Get Up: {end_ts.strftime('%H:%M on %a %d %b')}")

        fig = plot_sleep_timeline(
            df_levels,
            df_summary,
            title=f"Sleep Stages - {formatted}",
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No detailed sleep stage data available")

    # Hourly Steps
    df_steps = dfs.get("Steps_Intraday")
    if df_steps is not None and not df_steps.empty:
        fig_steps = create_hourly_steps_chart(df_steps, 340, title="")
        st.plotly_chart(fig_steps, width='stretch')
    else:
        st.info("No steps data available")

    # ==========================================================================
    # NAPS SECTION: Separate timeline visualization for each nap
    # Uses create_nap_timeline() which shows each nap with 30-min buffer
    # ==========================================================================
    naps = df_summary[df_summary.get("isMainSleep", "True") == "False"]
    if not naps.empty:
        st.markdown("---")
        st.subheader(f"Nap Tracking: {len(naps)} x naps found for {formatted}")

        # Create nap timeline visualizations (one figure per nap)
        nap_figures = plot_nap_timeline(df_levels, df_summary)
        if nap_figures is not None:
            for fig in nap_figures:
                st.plotly_chart(fig, width='content')
    

    # Sleep Stages Donut and Bar Chart side by side
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        fig_donut = create_sleep_stages_donut(df_summary)
        st.plotly_chart(fig_donut, width='stretch')

    with col2:
        fig_bar = create_sleep_stages_bar(df_summary)
        st.plotly_chart(fig_bar, width='stretch')


def render_multi_day_sleep(dfs: dict, start_date: date, end_date: date):
    """Render sleep analysis for multiple days."""
    st.title("Multi-Day Sleep Analysis")
    st.markdown(f"## {format_date(start_date)} - {format_date(end_date)}")

    df_levels, df_summary = extract_and_preprocess_sleep_data(dfs)

    if df_summary is None or df_summary.empty:
        st.warning("No sleep data available for this date range")
        return

    # Summary metrics (averaged)
    st.markdown("---")
    # st.subheader("Main Sleeps Summary")

    main_sleeps = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if not main_sleeps.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            avg_mins_in_bed = main_sleeps["minutesInBed"].mean()
            hours = int(avg_mins_in_bed // 60)
            mins = int(avg_mins_in_bed % 60)
            st.metric("Avg Time in Bed", f"{hours}h {mins}m")


        with col2:
            avg_asleep = main_sleeps["minutesAsleep"].mean()
            hours = int(avg_asleep // 60)
            mins = int(avg_asleep % 60)
            st.metric("Avg Time Asleep", f"{hours}h {mins}m")

        with col3:
            avg_deep = main_sleeps.get("minutesDeep", pd.Series([0])).mean()
            avg_deep_pct = (avg_deep / avg_asleep * 100) if avg_asleep > 0 else 0
            st.metric("Avg Deep Sleep", f"{int(avg_deep)}m ({avg_deep_pct:.0f}%)")

        with col4:
            avg_rem = main_sleeps.get("minutesREM", pd.Series([0])).mean()
            avg_rem_pct = (avg_rem / avg_asleep * 100) if avg_asleep > 0 else 0
            st.metric("Avg REM Sleep", f"{int(avg_rem)}m ({avg_rem_pct:.0f}%)")

        # Second row of metrics for vitals and times
        st.markdown("")  # Add some spacing
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            hrv_data = dfs.get("HRV")
            avg_hrv = hrv_data["dailyRmssd"].mean()
            st.metric("Avg HRV", f"{avg_hrv:.1f} ms")

        with col2:
            spo2_data = dfs.get("SPO2_Daily")
            avg_spo2 = spo2_data["avg"].mean()
            st.metric("Avg Blood Oxygen Saturation", f"{avg_spo2:.1f}%")

        with col3:
            temp_data = dfs.get("SkinTemperature")
            avg_temp = temp_data["nightlyRelative"].mean()
            st.metric("Avg Skin Temp", f"{avg_temp:.2f}°C")

        with col4:
            efficiency_data = main_sleeps.get("efficiency")
            avg_efficiency = efficiency_data.mean()
            st.metric("Avg Sleep Efficiency", f"{avg_efficiency:.1f}%")

    # All sleep sessions table
    st.markdown("---")
    # st.subheader("Sleep Sessions by Day")
    display_sleep_sessions_table(dfs)

    # Multi-day timeline
    st.markdown("---")
    st.subheader("Sleep Timeline by Day")

    if df_levels is not None and not df_levels.empty:
        # Generate date list
        dates = pd.date_range(start=start_date, end=end_date, freq="D")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        fig = create_multi_day_sleep_timeline(
            df_levels, df_summary, date_strs, TIMEZONE
        )
        st.plotly_chart(fig, width='stretch')

        # Consolidated timeline
        # st.markdown("---")
        st.subheader("Consolidated Sleep Timeline")
        fig_consolidated = create_consolidated_sleep_timeline(
            df_levels, df_summary, date_strs, TIMEZONE
        )
        st.plotly_chart(fig_consolidated, width='stretch')
    else:
        st.info("No detailed sleep stage data available for timeline")

    # Sleep vitals and efficiency trends
    st.markdown("---")
    st.subheader("Sleep Trends by Day")

    fig_stacked = create_sleep_stages_stacked_histogram(dfs)
    st.plotly_chart(fig_stacked, width='stretch')


    col1, col2 = st.columns(2)

    with col1:
        fig_spo2 = create_spo2_trend_chart(dfs)
        st.plotly_chart(fig_spo2, width='stretch')

    with col2:
        fig_temp = create_skin_temp_trend_chart(dfs)
        st.plotly_chart(fig_temp, width='stretch')


    col1, col2 = st.columns(2)

    with col1:
        fig_efficiency = create_sleep_efficiency_trend_chart(dfs)
        st.plotly_chart(fig_efficiency, width='stretch')
    
    with col2:
        fig_hrv = create_hrv_trend_chart(dfs)
        st.plotly_chart(fig_hrv, width='stretch')


def main():
    """Main entry point for Sleep page."""
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

        render_single_day_sleep(dfs, st.session_state.selected_date)

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

        render_multi_day_sleep(
            dfs, st.session_state.start_date, st.session_state.end_date
        )


if __name__ == "__main__":
    main()
