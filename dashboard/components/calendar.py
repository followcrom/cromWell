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


def render_calendar(
    data_path: str,
    selected_date: date,
    current_month: date = None,
    date_mode: str = "Single Date",
    start_date: date = None,
    end_date: date = None
) -> tuple:
    """
    Render an interactive calendar showing available data dates.

    Args:
        data_path: Path to the data directory
        selected_date: Currently selected date
        current_month: Date representing the month to display (defaults to selected_date's month)
        date_mode: "Single Date" or "Date Range" mode
        start_date: Start date for range selection
        end_date: End date for range selection

    Returns:
        Tuple of (selected_date, current_month, start_date, end_date) after user interaction
    """
    if current_month is None:
        current_month = selected_date

    # # Add CSS styling for visual enhancements
    # st.markdown("""
    #     <style>
    #     /* Calendar button styling */
    #     div[data-testid="column"] button {
    #         font-size: 24px;
    #     }
    #     </style>
    # """, unsafe_allow_html=True)

    # Get available dates
    available_dates = get_available_dates(data_path)

    # Month navigation - buttons half width
    col1, col2, col3, col4, col5 = st.columns([0.5, 0.5, 2, 0.5, 0.5])

    with col2:
        if st.button("◀ Prev", width='stretch'):
            # Go to previous month
            first_of_month = current_month.replace(day=1)
            current_month = (first_of_month - timedelta(days=1))

    with col3:
        st.markdown(f"<h2 style='text-align: center; margin: 0;'>{current_month.strftime('%B %Y')}</h2>",
                   unsafe_allow_html=True)

    with col4:
        if st.button("Next ▶", width='stretch'):
            # Go to next month
            first_of_month = current_month.replace(day=1)
            if first_of_month.month == 12:
                current_month = first_of_month.replace(year=first_of_month.year + 1, month=1)
            else:
                current_month = first_of_month.replace(month=first_of_month.month + 1)

    # Get calendar for the month
    cal = calendar.monthcalendar(current_month.year, current_month.month)

    # Calendar header
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = st.columns(7)
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>{day}</div>",
                       unsafe_allow_html=True)

    # Calendar grid
    new_selected_date = selected_date
    new_start_date = start_date
    new_end_date = end_date

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    # Empty cell for days from other months
                    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
                else:
                    # Create date object
                    dt = date(current_month.year, current_month.month, day)

                    # Determine styling
                    has_data = dt in available_dates
                    is_selected = dt == selected_date
                    is_future = dt > date.today()

                    # Range mode indicators
                    is_start_date = date_mode == "Date Range" and dt == start_date
                    is_end_date = date_mode == "Date Range" and dt == end_date

                    # Determine if button should be disabled
                    disabled = not has_data or is_future

                    # Create button with color indicators
                    if date_mode == "Single Date":
                        # Single date mode
                        if is_selected:
                            label = f"🔴 {day}"
                        elif has_data and not is_future:
                            label = f"🔵 {day}"
                        else:
                            label = f"{day}"
                    else:
                        # Date Range mode
                        if is_start_date:
                            label = f"🟢 {day}"
                        elif is_end_date:
                            label = f"🔴 {day}"
                        elif has_data and not is_future:
                            label = f"🔵 {day}"
                        else:
                            label = f"{day}"

                    button_type = "secondary"

                    if st.button(
                        label,
                        key=f"cal_{current_month.year}_{current_month.month}_{day}",
                        disabled=disabled,
                        type=button_type,
                        width='stretch'
                    ):
                        if date_mode == "Single Date":
                            new_selected_date = dt
                        else:
                            # Range selection
                            if not start_date or (start_date and end_date):
                                # First click or restart range
                                new_start_date = dt
                                new_end_date = None
                                new_selected_date = dt
                            else:
                                # Second click - complete the range
                                new_end_date = dt
                                # Auto-swap if needed
                                if new_end_date < new_start_date:
                                    new_start_date, new_end_date = new_end_date, new_start_date
                                new_selected_date = new_start_date

    return new_selected_date, current_month, new_start_date, new_end_date
