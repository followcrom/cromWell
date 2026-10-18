import streamlit as st
from datetime import date, timedelta


# Configuration
DATA_PATH = "/home/followcrom/projects/cromWell/data"
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
        st.session_state.selected_date = date.today() - timedelta(days=7)
        print(f"Initial date is: {st.session_state.selected_date}")
    if "start_date" not in st.session_state:
        st.session_state.start_date = date.today() - timedelta(days=7)
    if "end_date" not in st.session_state:
        st.session_state.end_date = date.today() - timedelta(days=1)
    if "calendar_month" not in st.session_state:
        st.session_state.calendar_month = date.today()


def _on_selected_date_change():
    st.session_state.selected_date = st.session_state._widget_selected_date


def _on_start_date_change():
    st.session_state.start_date = st.session_state._widget_start_date


def _on_end_date_change():
    st.session_state.end_date = st.session_state._widget_end_date


def render_sidebar():
    """Render the sidebar with date selection controls."""
    # Use separate widget keys (_widget_*) so the canonical persistent keys
    # (selected_date / start_date / end_date) aren't widget-scoped. In a
    # multi-page app, Streamlit resets widget-bound keys when navigating
    # between pages, so binding the canonical keys directly would lose the
    # user's selection on every page switch.
    #
    # Seed widget keys from canonical state BEFORE the widgets render. This
    # also propagates updates from the home-page custom calendar (which writes
    # to canonical keys via on_click callbacks) into the sidebar pickers.
    if st.session_state.get("_widget_selected_date") != st.session_state.selected_date:
        st.session_state._widget_selected_date = st.session_state.selected_date
    if st.session_state.get("_widget_start_date") != st.session_state.start_date:
        st.session_state._widget_start_date = st.session_state.start_date
    if st.session_state.get("_widget_end_date") != st.session_state.end_date:
        st.session_state._widget_end_date = st.session_state.end_date

    with st.sidebar:
        st.title("CromWell Dashboard")
        st.markdown("---")

        # Date mode toggle
        st.session_state.date_mode = st.radio(
            "Date Selection",
            ["Single Date", "Date Range"],
            index=0 if st.session_state.date_mode == "Single Date" else 1
        )

        st.markdown("---")

        if st.session_state.date_mode == "Single Date":
            st.date_input(
                "Select Date",
                key="_widget_selected_date",
                max_value=date.today(),
                on_change=_on_selected_date_change,
            )
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.date_input(
                    "Start Date",
                    key="_widget_start_date",
                    max_value=date.today(),
                    on_change=_on_start_date_change,
                )
            with col2:
                st.date_input(
                    "End Date",
                    key="_widget_end_date",
                    max_value=date.today(),
                    on_change=_on_end_date_change,
                )

            # Validate date range
            if st.session_state.start_date and st.session_state.end_date:
                if st.session_state.start_date > st.session_state.end_date:
                    st.error("Start date must be before end date")

        st.markdown("---")
        st.markdown("### Pages")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Activity.py", label="Activity", icon="🏃")
        st.page_link("pages/2_Sleep.py", label="Sleep", icon="😴")

        st.markdown("---")
        st.page_link("https://followcrom.com/", label="followCrom", icon="🌐")
        st.caption("followCrom © 2026")