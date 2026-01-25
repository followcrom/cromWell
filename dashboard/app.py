"""
Fitbit Dashboard - Main Application

A Streamlit dashboard for analyzing Fitbit data with interactive Plotly charts.
"""

import streamlit as st
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="Fitbit Dashboard",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
DATA_PATH = Path(__file__).parent.parent / "data"
TIMEZONE = "Europe/London"


def get_ordinal_suffix(day: int) -> str:
    """Get ordinal suffix for a day number (st, nd, rd, th)."""
    if 10 <= day % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_date(d: date) -> str:
    """Format date with ordinal suffix."""
    day = d.day
    suffix = get_ordinal_suffix(day)
    return d.strftime(f"%A {day}{suffix} %B %Y")


def init_session_state():
    """Initialize session state variables."""
    if "date_mode" not in st.session_state:
        st.session_state.date_mode = "Single Date"
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today() - timedelta(days=9)
        print(f"Initialized selected_date to {st.session_state.selected_date}")
    if "start_date" not in st.session_state:
        st.session_state.start_date = date.today() - timedelta(days=7)
    if "end_date" not in st.session_state:
        st.session_state.end_date = date.today() - timedelta(days=1)


def render_sidebar():
    """Render the sidebar with date selection controls."""
    with st.sidebar:
        st.title("Fitbit Dashboard")
        st.markdown("---")

        # Date mode toggle
        st.session_state.date_mode = st.radio(
            "Date Selection",
            ["Single Date", "Date Range"],
            index=0 if st.session_state.date_mode == "Single Date" else 1
        )

        st.markdown("---")

        if st.session_state.date_mode == "Single Date":
            st.session_state.selected_date = st.date_input(
                "Select Date",
                value=st.session_state.selected_date,
                max_value=date.today()
            )
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.start_date = st.date_input(
                    "Start Date",
                    value=st.session_state.start_date,
                    max_value=date.today()
                )
            with col2:
                st.session_state.end_date = st.date_input(
                    "End Date",
                    value=st.session_state.end_date,
                    max_value=date.today()
                )

            # Validate date range
            if st.session_state.start_date > st.session_state.end_date:
                st.error("Start date must be before end date")

        st.markdown("---")
        st.markdown("### Pages")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Activity.py", label="Activity", icon="🏃")
        st.page_link("pages/2_Sleep.py", label="Sleep", icon="😴")

        st.markdown("---")
        st.caption("Use sidebar links or browser URLs:")
        st.caption("/Activity, /Sleep")

        st.markdown("---")
        st.caption(f"Data path: {DATA_PATH}")


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()

    # Main content area
    st.title("CromWell Dashboard")

    if st.session_state.date_mode == "Single Date":
        formatted = format_date(st.session_state.selected_date)
        st.markdown(f"### {formatted}")
    else:
        start_formatted = format_date(st.session_state.start_date)
        end_formatted = format_date(st.session_state.end_date)
        st.markdown(f"### {start_formatted} to {end_formatted}")

    st.markdown("---")

    # Welcome content
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### Activity Analysis

        View your daily activity metrics including:
        - Heart rate timeline with zone tracking
        - Hourly steps distribution
        - Activity levels breakdown
        - Logged workouts analysis
        - GPS routes for walks
        """)
        st.page_link("pages/1_Activity.py", label="Go to Activity →", icon="🏃")

    with col2:
        st.markdown("""
        ### Sleep Analysis

        Explore your sleep patterns:
        - Sleep timeline with stage visualization
        - Sleep stages breakdown (donut chart)
        - Multi-day sleep trends
        - Nap tracking
        - Sleep metrics and efficiency
        - Add HRV, right?
        """)
        st.page_link("pages/2_Sleep.py", label="Go to Sleep →", icon="😴")

    st.markdown("---")
    st.info("Select a page from the sidebar or click the links above to begin your analysis.")


if __name__ == "__main__":
    main()
