"""
Plotly Chart Components for Fitbit Dashboard

Reusable chart functions for activity and sleep visualization.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional, Dict, List, Any

# Heart rate zone configuration
HR_ZONES = {
    "Out of Range": {"range": (0, 97), "color": "rgba(135, 206, 235, 0.3)"},
    "Fat Burn": {"range": (98, 122), "color": "rgba(152, 251, 152, 0.3)"},
    "Cardio": {"range": (123, 154), "color": "rgba(255, 165, 0, 0.3)"},
    "Peak": {"range": (155, 220), "color": "rgba(220, 20, 60, 0.3)"},
}

# Sleep stage colors
SLEEP_COLORS = {
    "Deep": "#0f172a",
    "Light": "#a5d8ff",
    "REM": "#c084fc",
    "Awake": "#fde047",
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
    title: str = "Heart Rate Timeline",
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
        xaxis_title="Time",
        yaxis_title="Heart Rate (bpm)",
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
            f"rgba(76, 175, 80, {0.3 + 0.7 * (v / max_steps)})"
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
        title=title,
        xaxis_title="Hour",
        yaxis_title="Steps",
        height=400,
        xaxis_tickangle=-45,
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

    # Sort by hours descending
    level_data = sorted(level_data, key=lambda x: x["hours"], reverse=True)

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
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x:.1f} hours<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Hours",
        yaxis_title="",
        height=300,
        yaxis=dict(categoryorder="total ascending"),
    )

    return fig


def _prepare_sleep_data(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
) -> pd.DataFrame:
    """
    Prepare sleep level data by adding Awake periods to fill gaps.

    ============================================================================
    KEY FEATURE: FILLS GAPS WITH "AWAKE" PERIODS (shown in yellow)
    This ensures the timeline has no blank/white spaces - matching notebook
    ============================================================================

    Adds Awake periods in four scenarios:
    1. From window start to first sleep session
    2. Between sleep sessions (gaps)
    3. Within a session if stages end before session end_time
    4. From last sleep session to window end

    Args:
        df_levels: Sleep levels dataframe
        df_summary: Sleep summary dataframe
        start_time: Window start time
        end_time: Window end time

    Returns:
        DataFrame with Awake periods added to fill gaps
    """
    levels = df_levels.copy()

    # Filter to the time window
    levels = levels[(levels["time"] >= start_time) & (levels["time"] < end_time)].copy()

    if levels.empty:
        return levels

    levels = levels.sort_values("time").reset_index(drop=True)

    # Prepare summary data
    summary = df_summary.copy()
    summary = summary.sort_values("time").reset_index(drop=True)

    gaps_to_add = []

    # ==========================================================================
    # STEP 1: Add Awake period from start_time to first sleep session
    # ==========================================================================
    if not summary.empty:
        first_session_start = summary["time"].min()
        if start_time < first_session_start:
            gap_seconds = (first_session_start - start_time).total_seconds()
            if gap_seconds > 60:  # Only add if gap > 1 minute
                gaps_to_add.append({
                    "time": pd.Timestamp(start_time),
                    "end_time": pd.Timestamp(first_session_start),
                    "level": 3.0,
                    "level_name": "Awake",
                    "duration_seconds": gap_seconds,
                })

    # ==========================================================================
    # STEP 2: Check if stages data ends before session end_time
    # (Sometimes Fitbit doesn't record stages all the way to wake-up)
    # ==========================================================================
    for idx, session in summary.iterrows():
        session_start = session["time"]
        session_end = session.get("end_time") or session.get("endTime")
        if session_end is None:
            continue
        session_end = pd.Timestamp(session_end)

        # Find stages within this session
        session_stages = levels[
            (levels["time"] >= session_start) & (levels["time"] < session_end)
        ]

        if not session_stages.empty:
            last_stage_end = session_stages["end_time"].max()
            if last_stage_end < session_end:
                gap_seconds = (session_end - last_stage_end).total_seconds()
                if gap_seconds > 30:  # Only add if gap > 30 seconds
                    gaps_to_add.append({
                        "time": pd.Timestamp(last_stage_end),
                        "end_time": pd.Timestamp(session_end),
                        "level": 3.0,
                        "level_name": "Awake",
                        "duration_seconds": gap_seconds,
                    })

    # ==========================================================================
    # STEP 3: Find gaps BETWEEN sleep sessions
    # ==========================================================================
    for i in range(len(summary) - 1):
        current_session_end = summary.iloc[i].get("end_time") or summary.iloc[i].get("endTime")
        next_session_start = summary.iloc[i + 1]["time"]

        if current_session_end is None:
            continue
        current_session_end = pd.Timestamp(current_session_end)

        if current_session_end < next_session_start:
            gap_seconds = (next_session_start - current_session_end).total_seconds()
            if gap_seconds > 60:
                gaps_to_add.append({
                    "time": pd.Timestamp(current_session_end),
                    "end_time": pd.Timestamp(next_session_start),
                    "level": 3.0,
                    "level_name": "Awake",
                    "duration_seconds": gap_seconds,
                })

    # ==========================================================================
    # STEP 4: Add Awake period from last session to end_time
    # ==========================================================================
    if not summary.empty:
        last_session_end = summary["end_time"].max() if "end_time" in summary.columns else None
        if last_session_end is None and "endTime" in summary.columns:
            last_session_end = pd.Timestamp(summary["endTime"].max())

        if last_session_end is not None:
            last_session_end = pd.Timestamp(last_session_end)
            if last_session_end < end_time:
                gap_seconds = (end_time - last_session_end).total_seconds()
                if gap_seconds > 60:
                    gaps_to_add.append({
                        "time": pd.Timestamp(last_session_end),
                        "end_time": pd.Timestamp(end_time),
                        "level": 3.0,
                        "level_name": "Awake",
                        "duration_seconds": gap_seconds,
                    })

    # ==========================================================================
    # STEP 5: Add all gap periods to the levels dataframe
    # ==========================================================================
    if gaps_to_add:
        levels = pd.concat([levels, pd.DataFrame(gaps_to_add)], ignore_index=True)
        levels = levels.sort_values("time").reset_index(drop=True)

    return levels


def create_sleep_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    title: str = "Sleep Timeline",
    timezone: str = "Europe/London",
) -> go.Figure:
    """
    Create a Gantt-style timeline showing sleep stages for MAIN SLEEP.

    ============================================================================
    KEY FEATURE: 27-HOUR WINDOW (matching notebook behavior)
    - Window runs from 21:00 the day before to 00:00 the day after
    - This captures overnight sleep that spans midnight
    - Based on the wake-up time (end_time) of main sleep session
    ============================================================================

    Args:
        df_levels: Sleep levels dataframe
        df_summary: Sleep summary dataframe
        title: Chart title
        timezone: Timezone for display

    Returns:
        Plotly Figure object
    """
    if df_levels.empty:
        return _create_empty_chart("No sleep data available")

    # ==========================================================================
    # STEP 1: Get main sleep session to determine the 27-hour window
    # ==========================================================================
    main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    main_session = main_sleep.iloc[0]
    sleep_start = main_session["time"]
    sleep_end = main_session.get("end_time") or main_session.get("endTime")

    if sleep_end is not None:
        sleep_end = pd.to_datetime(sleep_end)
        if sleep_end.tz is None:
            sleep_end = sleep_end.tz_localize("UTC").tz_convert(timezone)
        # Use wake-up date as the reference date
        actual_date = sleep_end.date()
    else:
        actual_date = pd.to_datetime(sleep_start).date()

    # ==========================================================================
    # STEP 2: Calculate 27-hour window (21:00 previous day to 00:00 next day)
    # This matches the notebook's plot_sleep_timeline behavior
    # ==========================================================================
    window_start = pd.Timestamp(actual_date, tz=timezone) - pd.Timedelta(hours=3)  # 21:00 previous day
    window_end = window_start + pd.Timedelta(hours=27)  # 00:00 next day

    # ==========================================================================
    # STEP 3: Prepare sleep level data WITH AWAKE PERIODS FILLED IN
    # Uses _prepare_sleep_data() to add yellow "Awake" blocks
    # ==========================================================================
    level_decode = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}
    df = df_levels.copy()

    if "level_name" not in df.columns:
        df["level_name"] = df["level"].map(level_decode)

    if "end_time" not in df.columns and "duration_seconds" in df.columns:
        df["end_time"] = df["time"] + pd.to_timedelta(df["duration_seconds"], unit="s")

    # Use helper function to add Awake periods for gaps
    df = _prepare_sleep_data(df, df_summary, window_start, window_end)

    if df.empty:
        return _create_empty_chart("No sleep data in time window")

    # ==========================================================================
    # STEP 4: Build timeline data for px.timeline
    # ==========================================================================
    timeline_data = []
    for _, row in df.iterrows():
        stage = row["level_name"]
        start = row["time"]
        end = row["end_time"]
        duration_min = row.get("duration_seconds", 0) / 60

        timeline_data.append({
            "Task": "Sleep",
            "Start": start,
            "Finish": end,
            "Stage": stage,
            "Duration": f"{duration_min:.0f} min",
        })

    timeline_df = pd.DataFrame(timeline_data)

    # Remove timezone info for px.timeline compatibility
    # Convert tz-aware timestamps to tz-naive by removing timezone
    timeline_df["Start"] = timeline_df["Start"].apply(
        lambda x: x.tz_localize(None) if hasattr(x, 'tz_localize') and x.tz is not None else x
    )
    timeline_df["Finish"] = timeline_df["Finish"].apply(
        lambda x: x.tz_localize(None) if hasattr(x, 'tz_localize') and x.tz is not None else x
    )

    # Create timeline using px.timeline
    fig = px.timeline(
        timeline_df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Stage",
        color_discrete_map=SLEEP_COLORS,
        category_orders={"Stage": ["Deep", "Light", "REM", "Awake"]},
        hover_data={"Duration": True, "Task": False},
    )

    # ==========================================================================
    # STEP 5: Add "To Bed" and "Wake Up" markers
    # ==========================================================================
    if sleep_start is not None:
        fig.add_shape(
            type="line",
            x0=sleep_start,
            x1=sleep_start,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="black", width=2, dash="dash"),
        )
        fig.add_annotation(
            x=sleep_start,
            y=1.15,
            yref="paper",
            text="To Bed",
            showarrow=False,
            font=dict(size=11, color="black"),
        )

    if sleep_end is not None:
        fig.add_shape(
            type="line",
            x0=sleep_end,
            x1=sleep_end,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="black", width=2, dash="dash"),
        )
        fig.add_annotation(
            x=sleep_end,
            y=1.15,
            yref="paper",
            text="Wake Up",
            showarrow=False,
            font=dict(size=11, color="black"),
        )

    # ==========================================================================
    # STEP 6: Set x-axis range to the full 27-hour window
    # ==========================================================================
    fig.update_layout(
        title=title,
        height=400,
        xaxis=dict(
            tickformat="%H:%M",
            range=[window_start, window_end],  # Fixed 27-hour range
            dtick=3600000 * 2,  # Tick every 2 hours (in milliseconds)
        ),
        yaxis=dict(visible=False, title=""),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=80, b=40),
    )

    return fig


def create_nap_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    timezone: str = "Europe/London",
) -> Optional[go.Figure]:
    """
    Create individual timeline plots for each NAP (non-main sleep sessions).

    ============================================================================
    KEY FEATURE: SEPARATE NAP VISUALIZATION
    - Only shows naps (isMainSleep == 'False')
    - Each nap gets its own subplot with 30-min buffer before/after
    - Returns None if no naps found
    ============================================================================

    Args:
        df_levels: Sleep levels dataframe
        df_summary: Sleep summary dataframe
        timezone: Timezone for display

    Returns:
        Plotly Figure object or None if no naps
    """
    # ==========================================================================
    # STEP 1: Filter to only nap sessions
    # ==========================================================================
    naps = df_summary[df_summary.get("isMainSleep", "True") == "False"]

    if naps.empty:
        return None  # No naps to display

    naps = naps.sort_values("time").reset_index(drop=True)
    num_naps = len(naps)

    # ==========================================================================
    # STEP 2: Prepare level data
    # ==========================================================================
    level_decode = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}
    df = df_levels.copy()

    if "level_name" not in df.columns:
        df["level_name"] = df["level"].map(level_decode)

    if "end_time" not in df.columns and "duration_seconds" in df.columns:
        df["end_time"] = df["time"] + pd.to_timedelta(df["duration_seconds"], unit="s")

    # ==========================================================================
    # STEP 3: Create subplots - one row per nap
    # ==========================================================================
    subplot_titles = []
    for idx, (_, nap) in enumerate(naps.iterrows()):
        nap_start = nap["time"]
        nap_end = nap.get("end_time") or nap.get("endTime")
        duration = nap.get("minutesInBed", 0)
        asleep = nap.get("minutesAsleep", 0)

        title = f"Nap {idx + 1}: {nap_start.strftime('%H:%M')} | {int(duration)} min in bed, {int(asleep)} min asleep"
        subplot_titles.append(title)

    fig = make_subplots(
        rows=num_naps,
        cols=1,
        subplot_titles=subplot_titles,
        vertical_spacing=0.15,
    )

    # ==========================================================================
    # STEP 4: Add timeline bars for each nap
    # ==========================================================================
    for idx, (_, nap) in enumerate(naps.iterrows(), 1):
        nap_start = nap["time"]
        nap_end = nap.get("end_time") or nap.get("endTime")
        if nap_end is None:
            nap_end = nap_start + pd.Timedelta(minutes=nap.get("minutesInBed", 30))
        else:
            nap_end = pd.to_datetime(nap_end)

        # 30-minute buffer before and after nap
        window_start = nap_start - pd.Timedelta(minutes=30)
        window_end = nap_end + pd.Timedelta(minutes=30)

        # Filter levels for this nap's window AND add Awake periods for gaps
        nap_levels = _prepare_sleep_data(df, df_summary, window_start, window_end)

        for stage_name in ["Deep", "Light", "REM", "Awake"]:
            stage_data = nap_levels[nap_levels["level_name"] == stage_name]
            if stage_data.empty:
                continue

            # Use scatter with mode='lines' to create filled regions
            for _, row in stage_data.iterrows():
                fig.add_trace(
                    go.Bar(
                        x=[row["end_time"]],
                        y=["Nap"],
                        orientation="h",
                        base=row["time"],
                        width=0.8,
                        marker_color=SLEEP_COLORS.get(stage_name, "#cccccc"),
                        name=stage_name,
                        showlegend=(idx == 1),  # Only show legend for first nap
                        legendgroup=stage_name,
                        hovertemplate=f"<b>{stage_name}</b><br>{row.get('duration_seconds', 0) / 60:.0f} min<extra></extra>",
                    ),
                    row=idx,
                    col=1,
                )

        # Set x-axis range for this subplot
        fig.update_xaxes(
            tickformat="%H:%M",
            range=[window_start, window_end],
            row=idx,
            col=1,
        )
        fig.update_yaxes(visible=False, row=idx, col=1)

    fig.update_layout(
        height=200 * num_naps,
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=40),
    )

    return fig


def create_sleep_stages_donut(
    df_summary: pd.DataFrame,
    title: str = "Main Sleep Composition",
) -> go.Figure:
    """
    Create a donut chart showing sleep stage distribution.

    Args:
        df_summary: Sleep summary dataframe
        title: Chart title

    Returns:
        Plotly Figure object
    """
    if df_summary.empty:
        return _create_empty_chart("No sleep summary data available")

    # Get main sleep session
    main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    summary = main_sleep.iloc[0]

    stages = ["Deep", "Light", "REM", "Awake"]
    minutes = [
        summary.get("minutesDeep", 0),
        summary.get("minutesLight", 0),
        summary.get("minutesREM", 0),
        summary.get("minutesAwake", 0),
    ]
    colors = [SLEEP_COLORS[s] for s in stages]

    def mins_to_hm(m):
        return f"{int(m // 60)}h {int(m % 60)}m"

    labels = [f"{s}<br>{mins_to_hm(m)}" for s, m in zip(stages, minutes)]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=minutes,
            hole=0.4,
            marker_colors=colors,
            textinfo="percent",
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>%{value:.0f} minutes<br>%{percent}<extra></extra>",
        )
    )

    # Add center annotation
    total_asleep = sum(minutes) - minutes[3]  # Exclude awake
    fig.add_annotation(
        text=f"<b>Asleep</b><br>{mins_to_hm(total_asleep)}",
        x=0.5,
        y=0.5,
        font_size=14,
        showarrow=False,
    )

    fig.update_layout(
        title=title,
        height=600,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
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
    colors_solid = {
        "Out of Range": "#87CEEB",
        "Fat Burn": "#98FB98",
        "Cardio": "#FFA500",
        "Peak": "#DC143C",
    }
    colors = [colors_solid.get(z, "#cccccc") for z in zones]
    percentages = [d["percentage"] for d in zone_data]

    fig = go.Figure(
        go.Bar(
            y=zones,
            x=minutes,
            orientation="h",
            marker_color=colors,
            text=[f"{m:.1f} min ({p:.1f}%)" for m, p in zip(minutes, percentages)],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x:.1f} minutes<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Minutes",
        yaxis_title="",
        height=300,
    )

    return fig


def create_multi_day_sleep_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    dates: List[str],
    timezone: str = "Europe/London",
) -> go.Figure:
    """
    Create a multi-day sleep timeline with one row per day.

    Args:
        df_levels: Sleep levels dataframe
        df_summary: Sleep summary dataframe
        dates: List of date strings
        timezone: Timezone for display

    Returns:
        Plotly Figure object
    """
    if df_levels.empty or df_summary.empty:
        return _create_empty_chart("No sleep data available")

    level_decode = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}

    # Prepare data for all days
    timeline_data = []

    for date_str in dates:
        date_ts = pd.Timestamp(date_str, tz=timezone)
        start_time = date_ts
        end_time = date_ts + pd.Timedelta(days=1)

        # Filter data for this day
        day_levels = df_levels[
            (df_levels["time"] >= start_time) & (df_levels["time"] < end_time)
        ].copy()

        if day_levels.empty:
            continue

        if "level_name" not in day_levels.columns:
            day_levels["level_name"] = day_levels["level"].map(level_decode)

        if "end_time" not in day_levels.columns and "duration_seconds" in day_levels.columns:
            day_levels["end_time"] = day_levels["time"] + pd.to_timedelta(
                day_levels["duration_seconds"], unit="s"
            )

        day_label = pd.to_datetime(date_str).strftime("%a %b %d")

        for _, row in day_levels.iterrows():
            timeline_data.append({
                "Day": day_label,
                "Start": row["time"],
                "Finish": row["end_time"],
                "Stage": row["level_name"],
                "Duration": f"{row.get('duration_seconds', 0) / 60:.0f} min",
            })

    if not timeline_data:
        return _create_empty_chart("No sleep data available for selected dates")

    timeline_df = pd.DataFrame(timeline_data)

    # Create timeline using px.timeline with facet
    fig = px.timeline(
        timeline_df,
        x_start="Start",
        x_end="Finish",
        y="Day",
        color="Stage",
        color_discrete_map=SLEEP_COLORS,
        category_orders={"Stage": ["Deep", "Light", "REM", "Awake"]},
        hover_data={"Duration": True},
    )

    num_days = len(timeline_df["Day"].unique())

    fig.update_layout(
        height=150 * max(num_days, 2),
        xaxis=dict(tickformat="%H:%M"),
        yaxis=dict(title="", categoryorder="category descending"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=100, r=20, t=40, b=40),
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
