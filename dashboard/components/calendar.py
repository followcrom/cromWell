"""
Calendar component for displaying and selecting dates with data availability.
"""

import streamlit as st
from pathlib import Path
from datetime import date, timedelta
import calendar


def get_available_dates(data_path: str) -> set:
    """
    Scan data directory to find dates with available data.

    Args:
        data_path: Path to the data directory

    Returns:
        Set of date objects representing dates with data
    """
    available_dates = set()
    data_dir = Path(data_path)

    # Check heartrate_intraday directory for available dates
    hr_dir = data_dir / "heartrate_intraday"
    if hr_dir.exists():
        for item in hr_dir.iterdir():
            if item.is_dir() and item.name.startswith("date="):
                date_str = item.name.replace("date=", "")
                try:
                    dt = date.fromisoformat(date_str)
                    available_dates.add(dt)
                except ValueError:
                    continue

    return available_dates


def _prev_month():
    first_of_month = st.session_state.calendar_month.replace(day=1)
    st.session_state.calendar_month = first_of_month - timedelta(days=1)


def _next_month():
    first_of_month = st.session_state.calendar_month.replace(day=1)
    if first_of_month.month == 12:
        st.session_state.calendar_month = first_of_month.replace(
            year=first_of_month.year + 1, month=1
        )
    else:
        st.session_state.calendar_month = first_of_month.replace(
            month=first_of_month.month + 1
        )


def _select_single_date(dt: date):
    st.session_state.selected_date = dt


def _select_range_date(dt: date):
    start = st.session_state.start_date
    end = st.session_state.end_date
    if not start or (start and end):
        # First click or restart range
        st.session_state.start_date = dt
        st.session_state.end_date = None
        st.session_state.selected_date = dt
    else:
        # Second click - complete the range; auto-swap if needed
        if dt < start:
            st.session_state.start_date = dt
            st.session_state.end_date = start
        else:
            st.session_state.end_date = dt
        st.session_state.selected_date = st.session_state.start_date


def render_calendar(data_path: str, date_mode: str = "Single Date") -> None:
    """Render an interactive calendar showing available data dates.

    All state mutations happen via on_click callbacks, which fire before the
    script body reruns. That order matters: the sidebar date_input widgets bind
    directly to selected_date / start_date / end_date via key=, and Streamlit
    forbids mutating those keys after the widgets are instantiated.
    """
    current_month = st.session_state.calendar_month
    selected_date = st.session_state.selected_date
    start_date = st.session_state.start_date
    end_date = st.session_state.end_date

    available_dates = get_available_dates(data_path)

    # Month navigation
    col1, col2, col3, col4, col5 = st.columns([0.5, 0.5, 2, 0.5, 0.5])

    with col2:
        st.button("◀ Prev", on_click=_prev_month, width='stretch', key="cal_prev")

    with col3:
        st.markdown(
            f"<h2 style='text-align: center; margin: 0;'>{current_month.strftime('%B %Y')}</h2>",
            unsafe_allow_html=True,
        )

    with col4:
        st.button("Next ▶", on_click=_next_month, width='stretch', key="cal_next")

    cal = calendar.monthcalendar(current_month.year, current_month.month)

    # Calendar header
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = st.columns(7)
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold;'>{day}</div>",
                unsafe_allow_html=True,
            )

    callback = _select_single_date if date_mode == "Single Date" else _select_range_date

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
                    continue

                dt = date(current_month.year, current_month.month, day)

                has_data = dt in available_dates
                is_selected = dt == selected_date
                is_future = dt > date.today()
                is_start_date = date_mode == "Date Range" and dt == start_date
                is_end_date = date_mode == "Date Range" and dt == end_date
                disabled = not has_data or is_future

                if date_mode == "Single Date":
                    if is_selected:
                        label = f"🔴 {day}"
                    elif has_data and not is_future:
                        label = f"🔵 {day}"
                    else:
                        label = f"{day}"
                else:
                    if is_start_date:
                        label = f"🟢 {day}"
                    elif is_end_date:
                        label = f"🔴 {day}"
                    elif has_data and not is_future:
                        label = f"🔵 {day}"
                    else:
                        label = f"{day}"

                st.button(
                    label,
                    key=f"cal_{current_month.year}_{current_month.month}_{day}",
                    disabled=disabled,
                    type="secondary",
                    width='stretch',
                    on_click=callback,
                    args=(dt,),
                )
