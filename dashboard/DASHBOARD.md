# CromBoard - Fitbit Dashboard

A Streamlit-based interactive dashboard for analyzing Fitbit data with Plotly visualizations.

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
- **Home**: Overview and navigation page
- **Activity** (`/Activity`): Activity metrics and visualizations
- **Sleep** (`/Sleep`): Sleep analysis and patterns

Use the sidebar to switch between pages or adjust date selections.

## Project Structure



## Data

The application expects Fitbit data to be located in a `data` directory at the parent level of this project:



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

## Modify Sleep Stages Colors

To change the colors used in sleep stage visualizations:

## Modify Activity Levels Colors

## Modify HR Zones Colors



### Sidebar Whitespace

The sidebar top padding is set to `0.1rem` for a compact layout. To adjust:

1. Open `app.py`, `pages/1_Activity.py`, and `pages/2_Sleep.py`
2. Find the CSS section (around line 18-28)
3. Change `padding-top: 0.1rem;` to your preferred value

### GitHub Badges

