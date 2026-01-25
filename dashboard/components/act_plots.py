"""
Plotly Chart Components for Fitbit Dashboard

Reusable chart functions for activity and sleep visualization.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple

# Heart rate zone configuration
HR_ZONES = {
    "Out of Range": {"range": (0, 97), "color": "rgba(135, 206, 235, 0.3)"},
    "Fat Burn": {"range": (98, 122), "color": "rgba(152, 251, 152, 0.3)"},
    "Cardio": {"range": (123, 154), "color": "rgba(255, 165, 0, 0.3)"},
    "Peak": {"range": (155, 220), "color": "rgba(220, 20, 60, 0.3)"},
}

# Heart rate zone colors
HR_ZONE_COLORS = {
    "Out of Range": "#87CEEB",
    "Fat Burn": "#98FB98",
    "Cardio": "#FFA500",
    "Peak": "#DC143C",
}

# Activity level colors
ACTIVITY_COLORS = {
    "Sedentary": "#87CEEB",
    "Lightly Active": "#98FB98",
    "Fairly Active": "#FFA500",
    "Very Active": "#DC143C",
}


def extract_activity_time_window(
    activity_record: pd.Series,
    timezone: str = 'Europe/London'
) -> Tuple[pd.Timestamp, pd.Timestamp, float]:
    """
    Extract and properly handle activity start/end times.

    NOTE: Fitbit API returns timestamps in local time but marked as UTC.
    We need to strip the UTC timezone and re-localize to the actual timezone.

    Parameters:
    - activity_record: Single activity record (Series)
    - timezone: Target timezone for display

    Returns:
    - (activity_start, activity_end, duration_minutes)
    """
    # Get activity start time
    activity_start = pd.to_datetime(activity_record['time'])

    # Fitbit quirk: timestamps are in local time but marked as UTC
    # Solution: Remove timezone and re-localize to actual timezone
    if activity_start.tz is not None:
        # Strip timezone (convert to naive) then localize to actual timezone
        activity_start = activity_start.tz_localize(None).tz_localize(timezone)
    else:
        # If no timezone, localize to target timezone
        activity_start = activity_start.tz_localize(timezone)

    # Calculate duration and end time
    duration_ms = activity_record.get('duration', 0)
    duration_minutes = duration_ms / 1000 / 60
    activity_end = activity_start + pd.Timedelta(minutes=duration_minutes)

    return activity_start, activity_end, duration_minutes


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
                annotation_position="top left",
            )

    fig.update_layout(
        title=title,
        # xaxis_title="Time",
        # yaxis_title="Heart Rate (bpm)",
        hovermode="x unified",
        xaxis=dict(
            tickformat="%H:%M",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(range=[40, 200]),
        height=500,
        showlegend=False,
    )

    return fig


def create_hourly_steps_chart(
    df_steps: pd.DataFrame,
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
            f"rgba(69, 50, 175, {0.3 + 0.7 * (v / max_steps)})"
            for v in hourly["value"]
        ]
    else:
        colors = ["rgba(200, 200, 200, 0.5)"] * 24

    fig = go.Figure(
        go.Bar(
            x=[f"{h:02d}:00" for h in hourly["hour"]],
            y=hourly["value"],
            marker_color=colors,
            text=hourly["value"].astype(int),
            textposition="outside",
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
        height=500,
        xaxis_tickangle=-45,
    )

    return fig

def create_hr_zones_chart(
    zone_data: List[Dict],
    title: str = "Time in HR Zones",
) -> go.Figure:
    """
    Create a horizontal bar chart showing time in each HR zone.

    Args:
        zone_data: List of dicts with zone info
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if not zone_data:
        return _create_empty_chart("No HR zone data available")

    zones = [d["zone"] for d in zone_data]
    minutes = [d["minutes"] for d in zone_data]

    colors_solid = HR_ZONE_COLORS
    colors = [colors_solid.get(z, "#cccccc") for z in zones]
    percentages = [d["percentage"] for d in zone_data]

    fig = go.Figure(
        go.Bar(
            y=zones,
            x=minutes,
            orientation="h",
            marker_color=colors,
            text=[f"{m:.1f} min / {p:.1f}%" for m, p in zip(minutes, percentages)],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>%{x:.1f} minutes<extra></extra>",
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
