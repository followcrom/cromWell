# CromBoard - Fitbit Dashboard

A Streamlit-based interactive dashboard for analyzing Fitbit data with Plotly visualizations.

## Features

### Homepage
- **Interactive Calendar**: Browse available data by month with color-coded dates
  - 🟢 Green = Data available
  - 🔵 Blue = Today
  - 🔴 Red = Selected date
- Click any date to instantly view its data
- Month navigation with Prev/Next buttons

### Activity Analysis
- Heart rate timeline with zone tracking (range slider disabled by default)
- Hourly steps distribution
- Activity levels breakdown (horizontal bar chart)
- Logged workouts analysis
- GPS routes for walks
- Activity metrics: Steps, Resting HR, Distance, Calories
- Extended metrics: Breathing rate, Logged activities, Active time, Sedentary time

### Sleep Analysis
- Sleep timeline with stage visualization (27-hour window)
- Sleep stages breakdown (donut chart)
- Multi-day sleep trends
- Nap tracking with separate visualizations
- Sleep metrics and efficiency
- Sleep vitals: SpO2, Skin temperature, HRV

## Running the App

To start the Streamlit dashboard:

```bash
streamlit run app.py
```

The app will automatically open in your default web browser at `http://localhost:8501`

### Navigation

Once running, you can navigate between pages:
- **Home**: Overview and navigation page
- **Activity** (`/Activity`): Activity metrics and visualizations
- **Sleep** (`/Sleep`): Sleep analysis and patterns

Use the sidebar to switch between pages or adjust date selections.

## Project Structure

```
cromBoard/
├── app.py                    # Main application entry point
├── requirements.txt          # Python dependencies
├── components/
│   ├── __init__.py
│   ├── calendar.py          # Interactive calendar component
│   ├── metrics.py           # Reusable metric components
│   └── plots.py             # Plotly chart components
├── functions/
│   ├── __init__.py
│   ├── activity_helpers.py  # Activity data processing
│   └── load_data.py         # Data loading utilities
└── pages/
    ├── 1_Activity.py        # Activity analysis page
    └── 2_Sleep.py           # Sleep analysis page
```

## Data

The application expects Fitbit data to be located in a `data` directory at the parent level of this project:

```
projects/
├── cromWell/
│   └── data/                       # Fitbit data files
│       ├── heartrate_intraday/     # Heart rate data by date
│       │   ├── date=2025-10-03/
│       │   ├── date=2025-10-04/
│       │   └── ...
│       ├── steps_intraday/         # Steps data by date
│       ├── daily_summaries.parquet
│       ├── gps.parquet
│       └── sleep_levels.parquet
└── cromBoard/                      # This project
    └── app.py
```

**Note**: The interactive calendar scans the `heartrate_intraday` directory to determine which dates have available data. Dates without this directory will not appear as available in the calendar.

## Configuration

- **Timezone**: Set to `Europe/London` by default (configurable in `app.py`)
- **Layout**: Wide mode for better visualization
- **Date Selection**: Single date or date range mode available in sidebar

## Dependencies

- streamlit >= 1.28.0
- plotly >= 5.18.0
- pandas >= 2.0.0
- pyarrow >= 14.0.0

## Usage Tips

- Use the sidebar to toggle between single date and date range selection
- Navigate between pages using sidebar links or browser URLs
- All dates are capped at today's date to prevent future date selection
- Use the interactive calendar on the homepage to quickly jump to any date with data
- The selected date persists across all pages (Activity, Sleep, Home)

## Customization

### Enable Timeline Range Slider

The heart rate timeline has the range slider disabled by default for a cleaner view. To enable it:

1. Open `components/plots.py`
2. Find the `create_hr_timeline` function (around line 106)
3. Change `rangeslider=dict(visible=False)` to `rangeslider=dict(visible=True)`

```python
fig.update_layout(
    ...
    xaxis=dict(
        tickformat="%H:%M",
        rangeslider=dict(visible=True),  # Change False to True
    ),
    ...
)
```

### Change Data Path

To point to a different data directory:

1. Open `app.py`
2. Update the `DATA_PATH` constant (around line 31):

```python
DATA_PATH = "/your/custom/path/to/data"
```

### Change Timezone

To use a different timezone:

1. Open `app.py`, `pages/1_Activity.py`, and `pages/2_Sleep.py`
2. Update the `TIMEZONE` constant:

```python
TIMEZONE = "America/New_York"  # or your preferred timezone
```

### Customize Calendar Colors

The calendar uses emoji indicators by default (🟢, 🔵, 🔴). To modify:

1. Open `components/calendar.py`
2. Find the button label section (around line 127-138)
3. Update the emoji or text labels as desired

### Modify Heart Rate Zones

To adjust heart rate zone thresholds:

1. Open `components/plots.py`
2. Find the `HR_ZONES` dictionary (around line 15-20)
3. Update the ranges:

```python
HR_ZONES = {
    "Out of Range": {"range": (0, 97), "color": "#e0e0e0"},
    "Fat Burn": {"range": (98, 122), "color": "#fff4e0"},
    "Cardio": {"range": (123, 154), "color": "#ffe0b2"},
    "Peak": {"range": (155, 220), "color": "#ffcccc"},
}
```

### Sidebar Whitespace

The sidebar top padding is set to `0.1rem` for a compact layout. To adjust:

1. Open `app.py`, `pages/1_Activity.py`, and `pages/2_Sleep.py`
2. Find the CSS section (around line 18-28)
3. Change `padding-top: 0.1rem;` to your preferred value

## Recent Changes

### v1.1.0 (Latest)
- Added interactive calendar to homepage with month navigation
- Color-coded dates showing data availability (🟢 green), today (🔵 blue), and selected date (🔴 red)
- Disabled Plotly range slider on heart rate timeline for cleaner view
- Fixed Activity Levels chart orientation (now displays as horizontal bar chart)
- Improved metric calculations (Active Time now excludes sedentary minutes)
- Removed Streamlit's default navigation for cleaner UI
- Reduced sidebar whitespace for more compact layout
- Renamed metric functions for better clarity
  - `display_activity_metrics` → `activity_metrics_line1`
  - `display_extended_activity_metrics` → `activity_metrics_line2`
  - `display_activity_summary_table` → `activity_summary_table`
