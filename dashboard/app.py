"""
Cromwell Dashboard - Main Application

A Streamlit dashboard for analyzing Fitbit data with interactive Plotly charts.
"""

import streamlit as st
# from datetime import date, timedelta
from components import render_calendar
from functions import (
    DATA_PATH,
    init_session_state,
    render_sidebar,
    format_date,
)

st.set_page_config(
    page_title="CromWell's Dashboard",
    page_icon="🕋",
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
            padding-top: 2.0rem;
        }
    </style>
""", unsafe_allow_html=True)




def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()

    # Main content area
    st.title("CromWell's Dashboard")
    st.info("Go, get out, make haste ye venal slaves. I will put an end to your prating. - Oliver Cromwell to the House of Commons, 1653")

    if st.session_state.date_mode == "Single Date":
        formatted = format_date(st.session_state.selected_date)
        st.markdown(f"### {formatted}")
    else:
        start_formatted = format_date(st.session_state.start_date)
        end_formatted = format_date(st.session_state.end_date)
        st.markdown(f"### {start_formatted} to {end_formatted}")

    st.markdown("---")
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

    # Interactive Calendar
    st.markdown("### 📅 Select a Date")
    st.markdown("Click on any date with a 🟢 to view data for that day.")

    # Render calendar and handle date selection
    new_date, new_month = render_calendar(
        DATA_PATH,
        st.session_state.selected_date,
        st.session_state.calendar_month
    )

    # Update session state if date or month changed
    if new_date != st.session_state.selected_date:
        st.session_state.selected_date = new_date
        st.session_state.date_mode = "Single Date"
        st.rerun()

    if new_month != st.session_state.calendar_month:
        st.session_state.calendar_month = new_month
        st.rerun()

if __name__ == "__main__":
    main()
