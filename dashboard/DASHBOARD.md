# CromBoard - Fitbit Dashboard

A Streamlit-based interactive dashboard for analyzing Fitbit data with Plotly visualizations.

## Overview

CromBoard is a multi-page Streamlit application that provides comprehensive analysis of Fitbit health and fitness data. The dashboard supports both single-day and multi-day date range analysis with interactive visualizations powered by Plotly.

## Project Structure

```
dashboard/
├── app.py                      # Main homepage with interactive calendar
├── DASHBOARD.md               # This file
├── pages/
│   ├── 1_Activity.py          # Activity analysis page
│   └── 2_Sleep.py             # Sleep analysis page
├── components/
│   ├── __init__.py           # Exports all component functions
│   ├── act_metrics.py        # Activity metrics display functions
│   ├── act_plots.py          # Activity visualization functions
│   ├── calendar.py           # Interactive calendar widget
│   ├── sleep_metrics.py      # Sleep metrics display functions
│   └── sleep_plots.py        # Sleep visualization functions
└── functions/
    ├── __init__.py           # Exports utility functions
    ├── load_data.py          # Data loading functions
    └── reused.py             # Shared utilities (session state, sidebar, formatting)
```

## Running the App

Start the venv:

```bash
source ../cw_venv/bin/activate
```

To start the Streamlit dashboard:

```bash
streamlit run app.py
```

The app will automatically open in your default web browser at `http://localhost:8501`

### Navigation

Once running, you can navigate between pages:
- **Home** ([app.py](app.py)): Overview with interactive calendar for date selection
- **Activity** ([pages/1_Activity.py](pages/1_Activity.py)): Activity metrics, heart rate analysis, and workout details
- **Sleep** ([pages/2_Sleep.py](pages/2_Sleep.py)): Sleep analysis, stage breakdowns, and vitals tracking

Navigation is available through:
- Sidebar links for switching between pages
- Homepage buttons ("🏃 Go to Activity Analysis →" and "😴 Go to Sleep Analysis →")
- Date selection can be adjusted in both the sidebar and on the homepage

## Technical Implementation

### Data Caching with Decorators

Both the Activity and Sleep pages use Streamlit's `@st.cache_data` decorator to optimize performance and reduce data loading times:

```python
@st.cache_data(ttl=300)
def load_data(date_str: str):
    """Load data for a single date with caching."""
    return load_single_date(date_str, str(DATA_PATH), TIMEZONE)

@st.cache_data(ttl=300)
def load_range_data(start_str: str, end_str: str):
    """Load data for a date range with caching."""
    return load_date_range(start_str, end_str, str(DATA_PATH), TIMEZONE)
```

**Purpose of the decorators:**
- **Performance Optimization**: Caches loaded data in memory to avoid repeated file I/O operations
- **TTL (Time-To-Live)**: Set to 300 seconds (5 minutes), after which cached data expires and is reloaded
- **User Experience**: Provides instant page loads when switching between pages with the same date/date range
- **Separate Caching**: Two functions ensure single-date and date-range data are cached independently

These decorators are critical for maintaining responsive performance, especially when working with large datasets or switching frequently between pages.

### Sleep Page Plot Generation Architecture

The Sleep page follows an efficient modular pattern where plotting functions receive raw dataframes and extract what they need internally.

**Data Flow:**
```
load_data() → cached (df_levels, df_summary)
    ↓
extract_and_preprocess_sleep_data() → add computed columns once
    ↓
Each plotting function receives both dataframes and filters as needed
```

**Key Design Decisions:**

1. **Dataframe Passing:** Functions receive `df_levels` and `df_summary` directly rather than pre-filtered data
   - Keeps functions self-contained and reusable
   - Filtering operations are cheap (0.1ms each) and create pandas views (zero-copy)
   - Total filtering overhead: <2% of render time

2. **Gap Filling:** The `_fill_sleep_gaps()` function is called with different time windows per visualization
   - Cannot be centralized (each plot needs different windows: 27-hour, per-nap, multi-day, etc.)
   - Accounts for 22-45% of processing time (true bottleneck)

3. **Column Naming Convention:**
   - **df_levels**: `end_time` computed as `time + duration_seconds`
   - **df_summary**: `end_time` is created from raw `endTime` column with timezone conversion, then `endTime` is dropped to avoid duplication

**Performance Profile:**
- Data loading: 50-500ms (cached)
- Preprocessing: 5-20ms (add computed columns)
- Filtering: <2% of total time
- Gap filling: 22-45% of processing time
- Plotly rendering: 54-63% of total time

The current architecture prioritizes code maintainability and reusability over micro-optimizations, which is appropriate for a Streamlit dashboard where Plotly rendering dominates performance.

### Activity Levels Classification

The Activity page displays activity levels that match Fitbit's official classifications exactly. The dashboard pulls data directly from Fitbit's export fields without recomputation.

**Activity Level Definitions (Based on MET - Metabolic Equivalent of Task):**

| Activity Level | MET Range | Additional Criteria |
|---|---|---|
| **Sedentary** | <1.5 METs | - |
| **Lightly Active** | 1.5–3.0 METs | - |
| **Fairly Active** | 3.0–6.0 METs | At least 10-minute bouts |
| **Very Active** | >6.0 METs | At least 10-minute bouts OR ≥145 steps/min |

**Data Sources:**
```python
"Sedentary": Activity-minutesSedentary
"Lightly Active": Activity-minutesLightlyActive
"Fairly Active": Activity-minutesFairlyActive
"Very Active": Activity-minutesVeryActive
```

These values come directly from Fitbit's native categorizations as defined in the Fitbit Web API Data Dictionary, ensuring consistency with the Fitbit app and web dashboard.

### Page Features

#### Home Page ([app.py](app.py))
- **Date Mode Toggle**: Radio buttons to switch between Single Date and Date Range modes (available both on homepage and in sidebar)
- **Interactive Calendar**: Visual calendar showing data availability with color-coded emoji indicators
- **Month Navigation**: Previous/Next buttons to browse different months
- **Date Display**: Shows currently selected date or date range in readable format
- **Quick Navigation**: Full-width buttons to jump directly to Activity or Sleep analysis pages
- **Range Selection Helper**: Informational message appears when selecting the first date of a range

#### Activity Page ([pages/1_Activity.py](pages/1_Activity.py))
- **Single Day Mode**: Displays heart rate timeline, hourly steps, activity levels, HR zones, and individual activity details
- **Multi-Day Mode**: Shows averaged metrics, daily comparisons, and aggregated patterns across the date range
- **Activity Details**: Expandable sections for each logged activity with GPS maps (for walks), HR analysis, and performance metrics

#### Sleep Page ([pages/2_Sleep.py](pages/2_Sleep.py))
- **Single Day Mode**: Sleep timeline (27-hour window), sleep stages breakdown, nap detection, and sleep vitals
- **Multi-Day Mode**: Consolidated sleep timelines, trends for HRV/SpO2/skin temperature, and sleep efficiency tracking
- **Sleep Stages**: Color-coded visualization of Deep, Light, REM, and Awake stages throughout the night

## Possible Colorscales

['aggrnyl', 'agsunset', 'algae', 'amp', 'armyrose', 'balance', 'blackbody', 'bluered', 'blues', 'blugrn', 'bluyl', 'brbg', 'brwnyl', 'bugn', 'bupu', 'burg', 'burgyl', 'cividis', 'curl', 'darkmint', 'deep', 'delta', 'dense', 'earth', 'edge', 'electric', 'emrld', 'fall', 'geyser', 'gnbu', 'gray', 'greens', 'greys', 'haline', 'hot', 'hsv', 'ice', 'icefire', 'inferno', 'jet', 'magenta', 'magma', 'matter', 'mint', 'mrybm', 'mygbm', 'oranges', 'orrd', 'oryel', 'oxy', 'peach', 'phase', 'picnic', 'pinkyl', 'piyg', 'plasma', 'plotly3', 'portland', 'prgn', 'pubu', 'pubugn', 'puor', 'purd', 'purp', 'purples', 'purpor', 'rainbow', 'rdbu', 'rdgy', 'rdpu', 'rdylbu', 'rdylgn', 'redor', 'reds', 'solar', 'spectral', 'speed', 'sunset', 'sunsetdark', 'teal', 'tealgrn', 'tealrose', 'tempo', 'temps', 'thermal', 'tropic', 'turbid', 'turbo', 'twilight', 'viridis', 'ylgn', 'ylgnbu', 'ylorbr', 'ylorrd']. Appending '_r' to a named colorscale reverses it.

## Data

The application expects Fitbit data to be located in a `data` directory at the parent level of this project. Data should be organized by date in subdirectories following the format `YYYY-MM-DD/`.

### Expected Data Files

Each date directory should contain Fitbit export files including:
- **Heart Rate**: `heartrate_intraday/` - Intraday heart rate measurements
- **Steps**: `steps_intraday/` - Intraday step counts
- **Activity**: `activity_records/` - Logged activities and workouts
- **Sleep**: `sleep_levels/`, `sleep_summary/` - Sleep stage data and summaries
- **Vitals**: `hrv/`, `spo2/`, `skin_temperature/` - Health metrics
- **GPS**: `gps/` - GPS route data for outdoor activities

**Note**: The interactive calendar scans the `heartrate_intraday` directory to determine which dates have available data. Dates without this directory will not appear as available in the calendar.

## Configuration

### Global Settings
- **Timezone**: Set to `Europe/London` by default (configurable in [functions/reused.py](functions/reused.py))
- **Layout**: Wide mode for better visualization
- **Date Selection**: Single date or date range mode available in sidebar
- **Data Path**: Points to parent-level `data/` directory (configurable in [functions/reused.py](functions/reused.py))

### Session State Management
The app uses Streamlit session state to maintain:
- Selected date/date range across page navigation
- Date mode (single vs range)
- Calendar state and data availability

## Dependencies

Core dependencies:
- `streamlit >= 1.28.0` - Web app framework
- `plotly >= 5.18.0` - Interactive visualizations
- `pandas >= 2.0.0` - Data manipulation
- `pyarrow >= 14.0.0` - Fast data serialization for caching

## Usage Tips

- **Date Selection**: Toggle between single date and date range modes using radio buttons on the homepage or in the sidebar
- **Navigation**: Navigate between pages using sidebar links, homepage buttons, or browser URLs
- **Calendar**: Interactive calendar on homepage shows data availability with color-coded indicators
  - **Single Date Mode**: 🔴 = selected date, 🔵 = data available
  - **Date Range Mode**: 🟢 = start date, 🔴 = end date, 🔵 = data available
- **Date Range Selection**: Click start date (shows 🟢), then click end date (shows 🔴). Dates auto-swap if selected in reverse order
- **Helper Text**: When selecting a range, a message appears above the calendar showing your start date
- **Date Persistence**: The selected date/range persists across all pages (Activity, Sleep, Home)
- **Date Limit**: All dates are capped at today's date to prevent future date selection
- **Cache**: Data is cached for 5 minutes, so switching between pages is instant within that window

## Components Architecture

The dashboard follows a modular design with separate component files for different functionality:

### Activity Components
- **[components/act_metrics.py](components/act_metrics.py)**: Functions to display activity metrics (steps, distance, calories, HR)
  - `activity_metrics_line1()` - Primary metrics row
  - `activity_metrics_line2()` - Secondary metrics row
  - `activity_metrics_avgs1()` - Multi-day averages (first row)
  - `activity_metrics_avgs2()` - Multi-day averages (second row)
  - `activity_summary_table()` - Logged activities table

- **[components/act_plots.py](components/act_plots.py)**: Visualization functions for activity data
  - `create_hr_timeline()` - Heart rate timeline with zone coloring
  - `create_hourly_steps_chart()` - Bar chart of hourly step counts
  - `create_activity_levels_chart()` - Donut chart of activity levels
  - `create_hr_zones_chart()` - Heart rate zones donut chart
  - `create_gps_route_map()` - GPS route visualization for walks
  - `create_daily_*_comparison()` - Multi-day comparison charts

### Sleep Components
- **[components/sleep_metrics.py](components/sleep_metrics.py)**: Functions to display sleep metrics and vitals
  - `display_sleep_metrics()` - Sleep duration and efficiency metrics
  - `display_sleep_vitals()` - HRV, SpO2, and skin temperature
  - `display_sleep_sessions_table()` - Table of all sleep sessions

- **[components/sleep_plots.py](components/sleep_plots.py)**: Visualization functions for sleep data
  - `plot_sleep_timeline()` - Main sleep timeline with 27-hour window
  - `plot_nap_timeline()` - Individual nap visualizations
  - `create_sleep_stages_donut()` - Sleep stages breakdown (donut chart)
  - `create_sleep_stages_bar()` - Sleep stages breakdown (bar chart)
  - `create_multi_day_sleep_timeline()` - Multi-day sleep timeline
  - `create_consolidated_sleep_timeline()` - Overlaid sleep patterns
  - `create_*_trend_chart()` - Trend charts for vitals and efficiency

### Shared Components
- **[components/calendar.py](components/calendar.py)**: Interactive calendar widget with data availability indicators
  - **Single Date Mode**: Displays 🔴 for selected date, 🔵 for dates with data
  - **Date Range Mode**: Displays 🟢 for start date, 🔴 for end date, 🔵 for dates with data
  - Helper text appears above calendar when selecting range start
  - Uses Streamlit's default secondary button styling for clean appearance
- **[functions/load_data.py](functions/load_data.py)**: Data loading functions for single dates and date ranges
- **[functions/reused.py](functions/reused.py)**: Shared utilities
  - `init_session_state()` - Initialize Streamlit session state
  - `render_sidebar()` - Render date selection sidebar
  - `format_date()` - Consistent date formatting

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

### Customize Calendar Indicators

The calendar uses emoji indicators for visual clarity:
- 🔴 Red circle: Selected date (single mode) or end date (range mode)
- 🟢 Green circle: Start date (range mode only)
- 🔵 Blue circle: Dates with available data

To modify these indicators:

1. Open `components/calendar.py`
2. Find the button label section (around lines 158-175)
3. Update the emoji or text labels:

```python
# Single Date Mode
if is_selected:
    label = f"🔴 {day}"  # Selected date
elif has_data and not is_future:
    label = f"🔵 {day}"  # Data available

# Date Range Mode
if is_start_date:
    label = f"🟢 {day}"  # Range start
elif is_end_date:
    label = f"🔴 {day}"  # Range end
elif has_data and not is_future:
    label = f"🔵 {day}"  # Data available
```

The calendar uses Streamlit's default secondary button styling (no custom CSS) for a clean, consistent appearance.

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

### Modify Sleep Stages Colors

To change the colors used in sleep stage visualizations:

1. Open [components/sleep_plots.py](components/sleep_plots.py)
2. Find the `SLEEP_STAGE_COLORS` dictionary
3. Update the hex color codes for each stage (Deep, Light, REM, Awake)

```python
SLEEP_STAGE_COLORS = {
    "Deep": "#1f77b4",    # Blue
    "Light": "#aec7e8",   # Light blue
    "REM": "#ff7f0e",     # Orange
    "Awake": "#d62728"    # Red
}
```

### Modify Activity Levels Colors

To change the colors for activity level visualization:

1. Open [components/act_plots.py](components/act_plots.py)
2. Find the `ACTIVITY_COLORS` dictionary
3. Update colors for Sedentary, Lightly Active, Fairly Active, and Very Active levels

### Modify HR Zones Colors

To adjust heart rate zone colors:

1. Open [components/act_plots.py](components/act_plots.py)
2. Find the `HR_ZONES` dictionary (around line 15-20)
3. Update the color values for each zone:

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

### GitHub Badges

Badges can be added to the README by customizing the markdown in [app.py](app.py).

## Development Best Practices

### Adding New Visualizations
1. Create visualization functions in the appropriate component file (`act_plots.py` or `sleep_plots.py`)
2. Import the function in the page file (`1_Activity.py` or `2_Sleep.py`)
3. Call the function within the rendering logic
4. Ensure all Plotly figures use `use_container_width=True` or `width='stretch'` for responsive design

### Modifying Data Loading
- Data loading logic is centralized in [functions/load_data.py](functions/load_data.py)
- Any changes to data loading should be made there to ensure consistency across pages
- Remember to update the cache TTL if data refresh frequency needs adjustment

### Adding New Pages
1. Create a new file in `pages/` following the naming convention `N_PageName.py`
2. Import required components and functions
3. Implement the same caching decorators for data loading
4. Use `init_session_state()` and `render_sidebar()` for consistency
5. Hide default navigation with the CSS snippet used in other pages

## Troubleshooting

### Calendar Shows No Available Dates
- Ensure `heartrate_intraday/` directory exists for dates with data
- Check that data directory path is correctly configured
- Verify date format is `YYYY-MM-DD/`

### Data Not Loading
- Check that the data path in [functions/reused.py](functions/reused.py) points to the correct location
- Verify file permissions allow reading from the data directory
- Clear Streamlit cache by refreshing the page with Ctrl+Shift+R

### Plots Not Displaying
- Check browser console for JavaScript errors
- Ensure Plotly version is up to date
- Verify data is not empty before creating visualizations

### Performance Issues
- Consider increasing cache TTL for less frequently changing data
- Reduce date range for multi-day analysis
- Check if data files are excessively large

## Contributing

When making changes to the dashboard:
1. Test both single-date and date-range modes
2. Verify all pages work with the updated code
3. Ensure caching still works correctly
4. Update this documentation if adding new features or changing configuration

