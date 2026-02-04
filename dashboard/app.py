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
            padding-top: 0.1rem;
        }
    </style>
""", unsafe_allow_html=True)




def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()

    # # Main content area
    # st.title("CromWell's Dashboard")
    st.image("https://followcrom.com/images/vinyl.png", caption="", width=200)
    # st.info("Welcome to the CromWell Dashboard! Use the sidebar to navigate through different sections and explore your Fitbit data.")

    # st.markdown("---")

    # Interactive Calendar
    st.markdown("### 📅 Select Date/s")

    # Date mode toggle
    st.session_state.date_mode = st.radio(
        "Label",
        ["Single Date", "Date Range"],
        index=0 if st.session_state.date_mode == "Single Date" else 1,
        horizontal=True,
        label_visibility="collapsed"
    )

    if st.session_state.date_mode == "Single Date":
        formatted = format_date(st.session_state.selected_date)
        st.markdown(f"### {formatted}")
    else:
        if st.session_state.start_date and st.session_state.end_date:
            start_formatted = format_date(st.session_state.start_date)
            end_formatted = format_date(st.session_state.end_date)
            st.markdown(f"### {start_formatted} to {end_formatted}")
        elif st.session_state.start_date:
            start_formatted = format_date(st.session_state.start_date)
            st.markdown(f"### {start_formatted} to ... (click another date to complete range)")
        else:
            st.markdown(f"### Select a date range")
             
    st.markdown("---")

    # Render calendar and handle date selection
    new_date, new_month, new_start, new_end = render_calendar(
        DATA_PATH,
        st.session_state.selected_date,
        st.session_state.calendar_month,
        date_mode=st.session_state.date_mode,
        start_date=st.session_state.start_date,
        end_date=st.session_state.end_date
    )

    # Update session state based on calendar interactions
    should_rerun = False

    if st.session_state.date_mode == "Single Date":
        if new_date != st.session_state.selected_date:
            st.session_state.selected_date = new_date
            should_rerun = True
    else:  # Date Range mode
        if new_start != st.session_state.start_date:
            st.session_state.start_date = new_start
            should_rerun = True
        if new_end != st.session_state.end_date:
            st.session_state.end_date = new_end
            should_rerun = True
        # Keep selected_date in sync for compatibility
        if new_start:
            st.session_state.selected_date = new_start

    if new_month != st.session_state.calendar_month:
        st.session_state.calendar_month = new_month
        should_rerun = True

    if should_rerun:
        st.rerun()

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🏃 Go to Activity Analysis →", key="activity_btn", width='stretch', type="secondary"):
            st.switch_page("pages/1_Activity.py")

    with col2:
        if st.button("😴 Go to Sleep Analysis →", key="sleep_btn", width='stretch', type="secondary"):
            st.switch_page("pages/2_Sleep.py")

if __name__ == "__main__":
    main()
