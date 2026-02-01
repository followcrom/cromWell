"""
Plotly Chart Components for Fitbit Dashboard

Reusable chart functions for activity and sleep visualization.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple

# Heart rate zone configuration (using Fitbit terminology)
# Note: These are approximate ranges for visualization.
# Actual Fitbit zones are personalized and stored in HR_Zones data.
# These colors are used for the semi-transparent horizontal background bands on the HR timeline chart. They create the colored horizontal zones behind your heart rate line
# HR_ZONES - Semi-transparent colors for timeline background bands
# HR_ZONE_COLORS - Solid hex colors for bar charts
HR_ZONES = {
    "Out of Range": {"range": (0, 97), "color": "rgba(135, 206, 235, 0.3)"},
    "Moderate": {"range": (98, 122), "color": "rgba(152, 251, 152, 0.3)"},
    "Vigorous": {"range": (123, 154), "color": "rgba(255, 165, 0, 0.3)"},
    "Peak": {"range": (155, 220), "color": "rgba(220, 20, 60, 0.3)"},
}

# Heart rate zone colors
HR_ZONE_COLORS = {
    "Out of Range": "#87CEEB",
    "Fat Burn": "#98FB98",
    "Moderate": "#98FB98",  # Fitbit terminology for Fat Burn
    "Cardio": "#FFA500",
    "Vigorous": "#FFA500",  # Fitbit terminology for Cardio
    "Peak": "#DC143C",
}

# Activity level colors
ACTIVITY_COLORS = {
    "Sedentary": "#87CEEB",
    "Lightly Active": "#98FB98",
    "Fairly Active": "#FFA500",
    "Very Active": "#DC143C",
}

def create_hr_timeline(
    df_hr: pd.DataFrame,
    df_activities: Optional[pd.DataFrame] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """
    Create an interactive heart rate timeline with zone bands.

    Args:
        df_hr: Heart rate dataframe with 'time' and 'value' columns
        df_activities: Optional activity records dataframe
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df_hr.empty:
        return _create_empty_chart("No heart rate data available")

    fig = go.Figure()

    # Add HR zone bands as shapes
    for zone_name, zone_info in HR_ZONES.items():
        fig.add_hrect(
            y0=zone_info["range"][0],
            y1=zone_info["range"][1],
            fillcolor=zone_info["color"],
            line_width=0,
            annotation_text=zone_name,
            annotation_position="left",
            annotation=dict(font_size=10, font_color="gray"),
        )

    # Plot heart rate line
    fig.add_trace(
        go.Scatter(
            x=df_hr["time"],
            y=df_hr["value"],
            mode="lines",
            name="Heart Rate",
            line=dict(color="#ff4444", width=1.5),
            hovertemplate="<b>%{x|%H:%M}</b><br>HR: %{y} bpm<extra></extra>",
        )
    )

    # Add activity regions if provided
    if df_activities is not None and not df_activities.empty:
        colors = px.colors.qualitative.Set2
        for idx, (_, activity) in enumerate(df_activities.iterrows()):
            activity_start = pd.to_datetime(activity["time"])
            if activity_start.tz is not None:
                activity_start = activity_start.tz_localize(None)

            duration_ms = activity.get("duration", 0)
            duration_min = duration_ms / 1000 / 60
            activity_end = activity_start + pd.Timedelta(minutes=duration_min)

            color = colors[idx % len(colors)]
            fig.add_vrect(
                x0=activity_start,
                x1=activity_end,
                fillcolor=color,
                opacity=0.3,
                line_width=0,
                annotation_text=activity.get("ActivityName", "Activity"),
                annotation_position="top right",
            )

    fig.update_layout(
        title=title,
        # xaxis_title="Time",
        # yaxis_title="Heart Rate (bpm)",
        hovermode="x unified",
        xaxis=dict(
            tickformat="%H:%M",
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(range=[40, 200]),
        height=550,
        showlegend=False,
    )

    return fig


def create_hourly_steps_chart(
    df_steps: pd.DataFrame,
    height: int = 500,
    title: str = "Hourly Steps",
) -> go.Figure:
    """
    Create a bar chart showing steps per hour.

    Args:
        df_steps: Steps dataframe with 'time' and 'value' columns
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df_steps.empty:
        return _create_empty_chart("No steps data available")

    df = df_steps.copy()
    df["hour"] = df["time"].dt.hour
    hourly = df.groupby("hour")["value"].sum().reset_index()

    # Ensure all 24 hours are present
    all_hours = pd.DataFrame({"hour": range(24)})
    hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)

    # Create color scale based on step count
    max_steps = hourly["value"].max()
    if max_steps > 0:
        colors = [
            f"rgba(169, 250, 75, {0.3 + 0.7 * (v / max_steps)})"
            for v in hourly["value"]
        ]
    else:
        colors = ["rgba(200, 200, 200, 0.5)"] * 24

    if height <= 400:
        margin_top = 5
        textposition = "auto"
    else:
        margin_top = 40
        textposition = "outside"

    fig = go.Figure(
        go.Bar(
            x=[f"{h:02d}:00" for h in hourly["hour"]],
            y=hourly["value"],
            marker=dict(
                color=hourly["value"],
                colorscale="Plasma",  # or Turbo, Viridis, RdYlGn
                showscale=False,
            ),
            # marker_color=colors,
            text=hourly["value"].astype(int),
            textposition=textposition,
            hovertemplate="<b>%{x}</b><br>Steps: %{y:,}<extra></extra>",
        )
    )

    # Add average line
    avg_steps = hourly["value"].mean()
    fig.add_hline(
        y=avg_steps,
        line_dash="dash",
        line_color="purple",
        annotation_text=f"Avg: {avg_steps:.0f}",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=28)),
        # xaxis_title="Hour",
        # yaxis_title="Steps",
        height=height,
        xaxis_tickangle=-45,
        margin=dict(t=margin_top),
    )

    return fig

def create_hr_zones_chart(
    dfs: Dict[str, pd.DataFrame],
    date_str: str,
    title: str = "Time in HR Zones",
) -> go.Figure:
    """
    Create a horizontal bar chart showing time in each HR zone for a single day.
    Uses Fitbit's stored HR_Zones data with Fitbit terminology.

    Args:
        dfs: Dictionary of dataframes
        date_str: Date string in YYYY-MM-DD format
        title: Chart title

    Returns:
        Plotly Figure object
    """
    df_zones = dfs.get("HR_Zones")

    if df_zones is None or df_zones.empty:
        return _create_empty_chart("No HR zone data available")

    # Filter for the specific date
    df_date = df_zones[df_zones['date'] == date_str]

    if df_date.empty:
        return _create_empty_chart("No HR zone data available for this date")

    # # HR zone names using Fitbit's terminology
    # zone_names = ["Out of Range", "Moderate", "Vigorous", "Peak"]

    # Map to field names in the data
    zone_field_map = {
        "Out of Range": "Out of Range",
        "Moderate": "Fat Burn",
        "Vigorous": "Cardio",
        "Peak": "Peak",
    }

    # Extract zone data for this date
    row = df_date.iloc[0]
    zone_data = []
    total_minutes = 0

    for zone_name, field_name in zone_field_map.items():
        value = row.get(field_name, 0)
        if pd.notna(value):
            minutes = value
        else:
            minutes = 0
        total_minutes += minutes
        zone_data.append({"zone": zone_name, "minutes": minutes})

    # Calculate percentages
    for item in zone_data:
        item["percentage"] = (item["minutes"] / total_minutes) * 100 if total_minutes > 0 else 0

    zones = [d["zone"] for d in zone_data]
    minutes_list = [d["minutes"] for d in zone_data]
    percentages = [d["percentage"] for d in zone_data]
    colors = [HR_ZONE_COLORS.get(z, "#cccccc") for z in zones]

    fig = go.Figure(
        go.Bar(
            y=zones,
            x=minutes_list,
            orientation="h",
            marker_color=colors,
            text=[f"{m:.0f} min ({p:.1f}%)" for m, p in zip(minutes_list, percentages)],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>%{x:.0f} minutes<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=28)),
        xaxis_title="Minutes",
        yaxis_title="",
        height=400,
    )

    return fig


def create_activity_levels_chart(
    level_data: List[Dict],
    title: str = "Activity Levels",
) -> go.Figure:
    """
    Create a horizontal bar chart showing time at each activity level.

    Args:
        level_data: List of dicts with 'level', 'hours', 'percentage' keys
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if not level_data:
        return _create_empty_chart("No activity level data available")

    # level_data = sorted(level_data, key=lambda x: x["hours"], reverse=True)
    level_data = sorted(level_data, key=lambda x: list(ACTIVITY_COLORS.keys()).index(x["level"]), reverse=True)

    levels = [d["level"] for d in level_data]
    hours = [d["hours"] for d in level_data]
    colors = [ACTIVITY_COLORS.get(d["level"], "#cccccc") for d in level_data]
    percentages = [d["percentage"] for d in level_data]

    fig = go.Figure(
        go.Bar(
            y=levels,
            x=hours,
            orientation="h",
            marker_color=colors,
            text=[f"{h:.1f}h ({p:.1f}%)" for h, p in zip(hours, percentages)],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>%{x:.1f} hours<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=28)),
        xaxis_title="Hours",
        yaxis_title="",
        height=400,
        # yaxis=dict(categoryorder="total ascending"),
    )

    return fig


def create_gps_route_map(
    df_gps: pd.DataFrame,
    title: str = "Route Map",
) -> go.Figure:
    """
    Create a map showing GPS route using OpenStreetMap tiles.

    Args:
        df_gps: GPS dataframe with lat/lon columns
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df_gps.empty:
        return _create_empty_chart("No GPS data available")

    # Find lat/lon columns
    lat_col = None
    lon_col = None

    for col in df_gps.columns:
        if col.lower() in ["lat", "latitude"]:
            lat_col = col
        elif col.lower() in ["lon", "lng", "longitude"]:
            lon_col = col

    if not lat_col or not lon_col:
        return _create_empty_chart("GPS data missing lat/lon columns")

    fig = go.Figure()

    # Add route line
    fig.add_trace(
        go.Scattermapbox(
            lat=df_gps[lat_col],
            lon=df_gps[lon_col],
            mode="lines",
            line=dict(width=3, color="blue"),
            name="Route",
            hoverinfo="skip",
        )
    )

    # Add start marker
    fig.add_trace(
        go.Scattermapbox(
            lat=[df_gps[lat_col].iloc[0]],
            lon=[df_gps[lon_col].iloc[0]],
            mode="markers",
            marker=dict(size=15, color="green"),
            name="Start",
            hovertemplate="Start<extra></extra>",
        )
    )

    # Add end marker
    fig.add_trace(
        go.Scattermapbox(
            lat=[df_gps[lat_col].iloc[-1]],
            lon=[df_gps[lon_col].iloc[-1]],
            mode="markers",
            marker=dict(size=15, color="red", symbol="square"),
            name="End",
            hovertemplate="End<extra></extra>",
        )
    )

    # Calculate center and zoom
    center_lat = df_gps[lat_col].mean()
    center_lon = df_gps[lon_col].mean()

    fig.update_layout(
        title=title,
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=14,
        ),
        height=500,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig


def create_daily_steps_comparison(
    dfs: Dict[str, pd.DataFrame],
    title: str = "Steps by Date",
) -> go.Figure:
    """
    Create a bar chart showing total steps for each date.

    Args:
        dfs: Dictionary of dataframes with steps data
        title: Chart title

    Returns:
        Plotly Figure object with bars for each date
    """
    df_steps = dfs.get("Activity-steps")

    if df_steps is None or df_steps.empty or 'date' not in df_steps.columns:
        return _create_empty_chart("No steps data available")

    # Group by date
    daily_steps = df_steps.groupby('date')['value'].sum().reset_index()
    daily_steps = daily_steps.sort_values('date')

    # Create bar chart
    fig = go.Figure(
        go.Bar(
            x=[pd.to_datetime(d).strftime('%a %d %b') for d in daily_steps['date']],
            y=daily_steps['value'],
            marker=dict(
                color=daily_steps['value'],
                colorscale='speed',
                showscale=False,
            ),
            text=daily_steps['value'].astype(int),
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Steps: %{y:,.0f}<extra></extra>',
        )
    )

    # Add average line
    avg_steps = daily_steps['value'].mean()
    fig.add_hline(
        y=avg_steps,
        line_dash="dash",
        line_color="black",
        annotation_text=f"Avg: {avg_steps:,.0f}",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=22)),
        # xaxis_title="Date",
        yaxis_title="Steps",
        height=450,
        xaxis_tickangle=-45,
    )

    return fig

def create_daily_calories_comparison(
    dfs: Dict[str, pd.DataFrame],
    title: str = "Calories by Date",
) -> go.Figure:
    """
    Create a bar chart showing total calories for each date.

    Args:
        dfs: Dictionary of dataframes with calorie data
        title: Chart title

    Returns:
        Plotly Figure object with bars for each date
    """
    df_calories = dfs.get("Activity-calories")

    if df_calories is None or df_calories.empty or 'date' not in df_calories.columns:
        return _create_empty_chart("No calorie data available")

    # Group by date
    daily_calories = df_calories.groupby('date')['value'].sum().reset_index()
    daily_calories = daily_calories.sort_values('date')

    # Create bar chart
    fig = go.Figure(
        go.Bar(
            x=[pd.to_datetime(d).strftime('%a %d %b') for d in daily_calories['date']],
            y=daily_calories['value'],
            marker=dict(
                color=daily_calories['value'],
                colorscale='portland',
                showscale=False,
            ),
            text=daily_calories['value'].astype(int),
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Calories: %{y:,.0f}<extra></extra>',
        )
    )

    # Add average line
    avg_calories = daily_calories['value'].mean()
    fig.add_hline(
        y=avg_calories,
        line_dash="dash",
        line_color="black",
        annotation_text=f"Avg: {avg_calories:,.0f}",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=22)),
        yaxis_title="Calories",
        height=450,
        xaxis_tickangle=-45,
    )

    return fig

def create_daily_activity_levels_comparison(
    dfs: Dict[str, pd.DataFrame],
    title: str = "Activity Levels by Date",
) -> go.Figure:
    """
    Create a stacked bar chart showing activity levels across multiple dates.

    Args:
        dfs: Dictionary of dataframes with activity level data
        title: Chart title

    Returns:
        Plotly Figure object with stacked bars for each date
    """
    # Activity level measurements
    level_keys = {
        'Very Active': 'Activity-minutesVeryActive',
        'Fairly Active': 'Activity-minutesFairlyActive',
        'Lightly Active': 'Activity-minutesLightlyActive',
        # 'Sedentary': 'Activity-minutesSedentary'
    }

    # Collect data by date
    dates_data = {}

    for level_name, key in level_keys.items():
        df = dfs.get(key)
        if df is not None and not df.empty and 'date' in df.columns:
            for _, row in df.iterrows():
                date = row['date']
                minutes = row['value']

                if date not in dates_data:
                    dates_data[date] = {}
                dates_data[date][level_name] = minutes / 60  # Convert to hours

    if not dates_data:
        return _create_empty_chart("No activity level data available")

    # Sort dates
    sorted_dates = sorted(dates_data.keys())

    # Create stacked bar chart
    fig = go.Figure()

    # Add traces for each activity level (reverse order for stacking)
    for level_name in level_keys.keys():
        values = [dates_data[date].get(level_name, 0) for date in sorted_dates]
        fig.add_trace(go.Bar(
            name=level_name,
            x=[pd.to_datetime(d).strftime('%a %d %b') for d in sorted_dates],
            y=values,
            marker_color=ACTIVITY_COLORS.get(level_name, '#cccccc'),
            hovertemplate='%{fullData.name}: %{y:.1f} hrs<extra></extra>',
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=22)),
        barmode='stack',
        yaxis_title="Hours",
        height=450,
        xaxis_tickangle=-45,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
    )

    return fig

def create_daily_hr_zones_comparison(
    dfs: Dict[str, pd.DataFrame],
    title: str = "HR Zones Distribution by Date",
) -> go.Figure:
    """
    Create a stacked bar chart showing HR zone time in minutes by date.
    Uses Fitbit's stored HR_Zones data for personalized zone calculations.

    Args:
        dfs: Dictionary of dataframes with HR_Zones data
        title: Chart title

    Returns:
        Plotly Figure object with stacked bars showing minutes per zone
    """
    df_zones = dfs.get("HR_Zones")

    if df_zones is None or df_zones.empty:
        return _create_empty_chart("No heart rate zone data available")

    # HR zone names in order (using Fitbit's terminology)
    zone_names = ["Peak", "Vigorous", "Moderate"]

    # Map display names to field names in the data
    zone_field_map = {
        "Peak": "Peak",
        "Vigorous": "Cardio",
        "Moderate": "Fat Burn",
        # "Out of Range": "Out of Range"
    }

    # Collect zone data by date
    dates_data = {}

    for _, row in df_zones.iterrows():
        date = row['date']
        if date not in dates_data:
            dates_data[date] = {}

        for zone_name, field_name in zone_field_map.items():
            value = row.get(field_name, 0)
            if pd.notna(value):
                dates_data[date][zone_name] = value
            else:
                dates_data[date][zone_name] = 0

    if not dates_data:
        return _create_empty_chart("No heart rate zone data available")

    # Sort dates
    sorted_dates = sorted(dates_data.keys())

    # Create stacked bar chart
    fig = go.Figure()

    # Add traces for each zone
    for zone_name in zone_names:
        values = [dates_data[date].get(zone_name, 0) for date in sorted_dates]
        fig.add_trace(go.Bar(
            name=zone_name,
            x=[pd.to_datetime(d).strftime('%a %d %b') for d in sorted_dates],
            y=values,
            marker_color=HR_ZONE_COLORS.get(zone_name, '#cccccc'),
            text=[f'{v:.0f} mins' if v > 10 else '' for v in values],  # Show values > 10 mins
            textposition='inside',
            textfont=dict(color='blue', size=10),
            hovertemplate='%{fullData.name}: %{y:.0f} mins<extra></extra>',
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=22)),
        barmode='stack',
        yaxis_title="Minutes",
        yaxis2=dict(
            title="Resting HR (bpm)",
            overlaying='y',
            side='right',
            showgrid=False,
        ),
        height=450,
        xaxis_tickangle=-45,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
    )

    return fig


def _create_empty_chart(message: str) -> go.Figure:
    """Create an empty chart with a message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16, color="gray"),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=300,
    )
    return fig
