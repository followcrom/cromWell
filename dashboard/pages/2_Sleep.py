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
    create_sleep_timeline,
    create_nap_timeline,  # Separate nap visualization
    create_sleep_stages_donut,
    create_hourly_steps_chart,
    create_multi_day_sleep_timeline,
    display_sleep_metrics,
    display_sleep_vitals,
    display_sleep_sessions_table,
)

from functions import load_single_date, load_date_range

# Configuration
DATA_PATH = Path(__file__).parent.parent.parent / "data"
TIMEZONE = "Europe/London"

# Sleep stage mapping
LEVEL_DECODE = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}

st.set_page_config(
    page_title="Sleep - Fitbit Dashboard",
    page_icon="😴",
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


def prepare_sleep_data(dfs: dict) -> tuple:
    """
    Prepare sleep data by adding computed columns.

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

    return df_levels, df_summary


def render_single_day_sleep(dfs: dict, selected_date: date):
    """Render sleep analysis for a single day."""
    formatted = format_date(selected_date)
    st.title("Sleep Well Crom?")
    st.markdown(f"### {formatted}")

    df_levels, df_summary = prepare_sleep_data(dfs)

    if df_summary is None or df_summary.empty:
        st.warning("No sleep data available for this date")
        return

    # Metrics row
    st.markdown("---")
    display_sleep_metrics(dfs)
    display_sleep_vitals(dfs)

    # Sleep Sessions Table
    st.markdown("---")
    st.subheader("Sleep Sessions")
    display_sleep_sessions_table(dfs)

    # ==========================================================================
    # MAIN SLEEP TIMELINE: 27-hour window from 21:00 to 00:00 next day
    # This matches the notebook's plot_sleep_timeline behavior
    # Window is based on wake-up time (end_time) of main sleep session
    # ==========================================================================
    st.markdown("---")
    st.subheader("Sleep Timeline")

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
            st.info(f"To Bed: {sleep_start.strftime('%H:%M on %A')}")
        with col2:
            if sleep_end:
                end_ts = pd.to_datetime(sleep_end)
                st.info(f"Wake Up: {end_ts.strftime('%H:%M on %A')}")

        fig = create_sleep_timeline(
            df_levels,
            df_summary,
            title=f"Sleep Stages - {formatted}",
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No detailed sleep stage data available")

    # Sleep Stages Donut and Hourly Steps side by side
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sleep Composition")
        fig_donut = create_sleep_stages_donut(df_summary, title="Sleep Stages")
        st.plotly_chart(fig_donut, width='stretch')

    with col2:
        st.subheader("Daily Activity Context")
        df_steps = dfs.get("Steps_Intraday")
        if df_steps is not None and not df_steps.empty:
            fig_steps = create_hourly_steps_chart(df_steps, title="Hourly Steps")
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
        st.subheader(f"Naps ({len(naps)} found)")

        # Create nap timeline visualization
        fig_naps = create_nap_timeline(df_levels, df_summary, TIMEZONE)
        if fig_naps is not None:
            st.plotly_chart(fig_naps, width='stretch')


def render_multi_day_sleep(dfs: dict, start_date: date, end_date: date):
    """Render sleep analysis for multiple days."""
    st.title("Multi-Day Sleep Analysis")
    st.markdown(f"### {format_date(start_date)} to {format_date(end_date)}")

    df_levels, df_summary = prepare_sleep_data(dfs)

    if df_summary is None or df_summary.empty:
        st.warning("No sleep data available for this date range")
        return

    # Summary metrics (averaged)
    st.markdown("---")
    st.subheader("Sleep Summary")

    main_sleeps = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if not main_sleeps.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            avg_asleep = main_sleeps["minutesAsleep"].mean()
            hours = int(avg_asleep // 60)
            mins = int(avg_asleep % 60)
            st.metric("Avg Time Asleep", f"{hours}h {mins}m")

        with col2:
            avg_efficiency = main_sleeps["efficiency"].mean()
            st.metric("Avg Efficiency", f"{avg_efficiency:.0f}%")

        with col3:
            avg_deep = main_sleeps.get("minutesDeep", pd.Series([0])).mean()
            st.metric("Avg Deep Sleep", f"{int(avg_deep)} min")

        with col4:
            avg_rem = main_sleeps.get("minutesREM", pd.Series([0])).mean()
            st.metric("Avg REM Sleep", f"{int(avg_rem)} min")

    # All sleep sessions table
    st.markdown("---")
    st.subheader("Sleep Sessions by Day")
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
    else:
        st.info("No detailed sleep stage data available for timeline")

    # # Sleep trends
    # st.markdown("---")
    # st.subheader("Sleep Trends")

    # if not main_sleeps.empty:
    #     # Create trend data
    #     main_sleeps_sorted = main_sleeps.sort_values("time")

    #     col1, col2 = st.columns(2)

    #     with col1:
    #         # Time asleep trend
    #         import plotly.express as px

    #         trend_data = main_sleeps_sorted.copy()
    #         trend_data["date"] = trend_data["time"].dt.date
    #         trend_data["hours_asleep"] = trend_data["minutesAsleep"] / 60

    #         fig_trend = px.line(
    #             trend_data,
    #             x="date",
    #             y="hours_asleep",
    #             markers=True,
    #             title="Time Asleep Trend",
    #             labels={"hours_asleep": "Hours", "date": "Date"},
    #         )
    #         fig_trend.add_hline(
    #             y=7, line_dash="dash", line_color="green", annotation_text="7h target"
    #         )
    #         st.plotly_chart(fig_trend, width='stretch')

    #     with col2:
    #         # Efficiency trend
    #         fig_eff = px.line(
    #             trend_data,
    #             x="date",
    #             y="efficiency",
    #             markers=True,
    #             title="Sleep Efficiency Trend",
    #             labels={"efficiency": "Efficiency %", "date": "Date"},
    #         )
    #         fig_eff.add_hline(
    #             y=85, line_dash="dash", line_color="green", annotation_text="85% target"
    #         )
    #         st.plotly_chart(fig_eff, width='stretch')


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
