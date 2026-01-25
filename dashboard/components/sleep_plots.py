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


def _fill_sleep_gaps(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
) -> pd.DataFrame:
    """
    Fill gaps in sleep level data by adding Awake periods.

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
        start_time: Window start time (in Europe/London timezone)
        end_time: Window end time (in Europe/London timezone)

    Returns:
        DataFrame with Awake periods added to fill gaps
    """
    TIMEZONE = "Europe/London"

    levels = df_levels.copy()
    # Convert from UTC to Europe/London
    levels['time'] = levels['time'].dt.tz_convert(TIMEZONE)
    if 'end_time' in levels.columns:
        levels['end_time'] = levels['end_time'].dt.tz_convert(TIMEZONE)

    # Compute end_time if not present
    if 'end_time' not in levels.columns and 'duration_seconds' in levels.columns:
        levels['end_time'] = levels['time'] + pd.to_timedelta(levels['duration_seconds'], unit='s')

    print(f"\n{'='*80}")
    print(f"_fill_sleep_gaps() called for window: {start_time} to {end_time}")
    print(f"{'='*80}")
    print(f"Total levels in dataset: {len(levels)}")

    if not levels.empty:
        print(f"All levels time range: {levels['time'].min()} to {levels['time'].max()}")

    # Filter by OVERLAP (to catch levels that cross midnight)
    print(f"\nFiltering levels that OVERLAP with window [{start_time}, {end_time}):")
    levels = levels[(levels["end_time"] > start_time) & (levels["time"] < end_time)].copy()

    print(f"  Found {len(levels)} levels (before clipping)")

    # Clip levels to window boundaries
    levels.loc[levels["time"] < start_time, "time"] = start_time
    levels.loc[levels["end_time"] > end_time, "end_time"] = end_time
    levels["duration_seconds"] = (levels["end_time"] - levels["time"]).dt.total_seconds()

    if not levels.empty:
        print(f"  Time range after clipping: {levels['time'].min()} to {levels['end_time'].max()}")

    if levels.empty:
        print(f"WARNING: No levels found in window!")
        return levels

    levels = levels.sort_values("time").reset_index(drop=True)

    # Prepare summary data - FILTER to only sessions that overlap with current window
    summary = df_summary.copy()
    summary['time'] = summary['time'].dt.tz_convert(TIMEZONE)
    if 'end_time' in summary.columns:
        summary['end_time'] = summary['end_time'].dt.tz_convert(TIMEZONE)
    elif 'endTime' in summary.columns:
        summary['end_time'] = pd.to_datetime(summary['endTime']).dt.tz_convert(TIMEZONE)

    print(f"\nAll sessions in dataset:")
    for idx, sess in summary.iterrows():
        print(f"  {sess['time']} to {sess['end_time']}")

    # CRITICAL FIX: Only keep sessions that overlap with [start_time, end_time) window
    # A session overlaps if: session_end > start_time AND session_start < end_time
    print(f"\nFiltering sessions that overlap with window [{start_time}, {end_time}):")
    summary = summary[
        (summary['end_time'] > start_time) & (summary['time'] < end_time)
    ].copy()

    summary = summary.sort_values("time").reset_index(drop=True)

    print(f"Sessions after filtering: {len(summary)}")
    for idx, sess in summary.iterrows():
        print(f"  Session {idx}: {sess['time']} to {sess['end_time']}")

    gaps_to_add = []

    # ==========================================================================
    # STEP 1: Add Awake period from start_time to first sleep LEVEL
    # CRITICAL: Use actual levels (after clipping), not session start times!
    # If a session crossed midnight and was clipped, levels will start at window start
    # ==========================================================================
    if not levels.empty:
        first_level_time = levels["time"].min()
        print(f"\nSTEP 1 - Check gap at window start:")
        print(f"  Window start: {start_time}")
        print(f"  First level: {first_level_time}")
        # Only add gap if first level starts AFTER window start
        if start_time < first_level_time:
            gap_seconds = (first_level_time - start_time).total_seconds()
            if gap_seconds > 60:  # Only add if gap > 1 minute
                print(f"  Adding gap: {gap_seconds/60:.1f} minutes")
                gaps_to_add.append({
                    "time": start_time,
                    "end_time": first_level_time,
                    "level": 3.0,
                    "level_name": "Awake",
                    "duration_seconds": gap_seconds,
                })
            else:
                print(f"  Gap too small ({gap_seconds:.0f}s), skipping")
        else:
            print(f"  No gap at start (level starts at or before window start)")

    # ==========================================================================
    # STEP 2: Check if stages data ends before session end_time
    # CRITICAL: Clip session times to window boundaries to avoid gaps outside window
    # ==========================================================================
    print(f"\nSTEP 2 - Check for gaps within sessions:")
    for idx, session in summary.iterrows():
        session_start = session["time"]
        session_end = session.get("end_time") or session.get("endTime")
        if session_end is None:
            continue
        session_end = pd.Timestamp(session_end)

        # Clip session times to current window
        clipped_start = max(session_start, start_time)
        clipped_end = min(session_end, end_time)

        # Find stages within this session (and window)
        session_stages = levels[
            (levels["time"] >= clipped_start) & (levels["time"] < clipped_end)
        ]

        if not session_stages.empty:
            last_stage_end = session_stages["end_time"].max()
            # Only add gap if it's WITHIN the window
            if last_stage_end < clipped_end and last_stage_end >= start_time:
                gap_seconds = (clipped_end - last_stage_end).total_seconds()
                if gap_seconds > 30:
                    print(f"  Session gap: {last_stage_end} to {clipped_end} ({gap_seconds/60:.1f} min)")
                    gaps_to_add.append({
                        "time": last_stage_end,
                        "end_time": clipped_end,
                        "level": 3.0,
                        "level_name": "Awake",
                        "duration_seconds": gap_seconds,
                    })

    # ==========================================================================
    # STEP 3: Find gaps BETWEEN sleep sessions
    # CRITICAL: Clip gaps to window boundaries
    # ==========================================================================
    print(f"\nSTEP 3 - Check for gaps between sessions:")
    for i in range(len(summary) - 1):
        current_session_end = summary.iloc[i].get("end_time") or summary.iloc[i].get("endTime")
        next_session_start = summary.iloc[i + 1]["time"]

        if current_session_end is None:
            continue
        if not isinstance(current_session_end, pd.Timestamp):
            current_session_end = pd.Timestamp(current_session_end)

        # Clip gap to window boundaries
        gap_start = max(current_session_end, start_time)
        gap_end = min(next_session_start, end_time)

        if gap_start < gap_end:
            gap_seconds = (gap_end - gap_start).total_seconds()
            if gap_seconds > 60:
                print(f"  Between-session gap: {gap_start} to {gap_end} ({gap_seconds/60:.1f} min)")
                gaps_to_add.append({
                    "time": gap_start,
                    "end_time": gap_end,
                    "level": 3.0,
                    "level_name": "Awake",
                    "duration_seconds": gap_seconds,
                })

    # ==========================================================================
    # STEP 4: Add Awake period from last sleep LEVEL to end_time
    # CRITICAL: Use actual levels (after clipping), not session end times!
    # If a session crosses midnight and was clipped, levels will end at window end
    # ==========================================================================
    if not levels.empty:
        last_level_end = levels["end_time"].max()
        print(f"\nSTEP 4 - Check gap at window end:")
        print(f"  Last level end: {last_level_end}")
        print(f"  Window end: {end_time}")
        # Only add gap if last level ends BEFORE window end
        if last_level_end < end_time:
            gap_seconds = (end_time - last_level_end).total_seconds()
            if gap_seconds > 60:
                print(f"  Adding gap: {gap_seconds/60:.1f} minutes")
                gaps_to_add.append({
                    "time": last_level_end,
                    "end_time": end_time,
                    "level": 3.0,
                    "level_name": "Awake",
                    "duration_seconds": gap_seconds,
                })
            else:
                print(f"  Gap too small ({gap_seconds:.0f}s), skipping")
        else:
            print(f"  No gap at end (level ends at or after window end)")

    # ==========================================================================
    # STEP 5: Add all gap periods to the levels dataframe
    # ==========================================================================
    print(f"\nGaps to add: {len(gaps_to_add)}")
    for gap in gaps_to_add:
        print(f"  {gap['time']} to {gap['end_time']} ({gap['duration_seconds']/60:.1f} min) - {gap['level_name']}")

    if gaps_to_add:
        levels = pd.concat([levels, pd.DataFrame(gaps_to_add)], ignore_index=True)
        levels = levels.sort_values("time").reset_index(drop=True)

    print(f"\nFinal result: {len(levels)} levels total")
    print(f"{'='*80}\n")
    return levels


def plot_sleep_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    title: str = "Sleep Timeline",
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

    Returns:
        Plotly Figure object
    """
    if df_levels.empty or df_summary.empty:
        print(f"❌ No sleep data found")
        return None

    main_sleep = df_summary[df_summary.get("isMainSleep", "True") == "True"]
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    main_sleep_end = (
        main_sleep.iloc[0].get("endTime") or
        main_sleep.iloc[0].get("end_time") or
        None
    )
    TIMEZONE = "Europe/London"

    main_start = main_sleep.iloc[0]["time"]
    if not isinstance(main_start, pd.Timestamp):
        main_start = pd.to_datetime(main_start)
    # Convert to Europe/London
    main_start = main_start.tz_convert(TIMEZONE)

    if main_sleep_end is not None:
        main_sleep_end = pd.to_datetime(main_sleep_end)
        main_sleep_end = main_sleep_end.tz_convert(TIMEZONE)
        # Use the wake-up date for the window (more intuitive - "Nov 18's sleep" = woke up on Nov 18)
        actual_date = main_sleep_end.date()
    else:
        actual_date = main_start.date()

    # Calculate 27-hour window: 21:00 previous day → 00:00 next day (in Europe/London)
    start_time = pd.Timestamp(actual_date, tz=TIMEZONE) - pd.Timedelta(hours=3)
    end_time = start_time + pd.Timedelta(hours=27)

    # Use existing _fill_sleep_gaps() helper for gap-filling
    levels = _fill_sleep_gaps(df_levels, df_summary, start_time, end_time)

    if levels.empty:
        return _create_empty_chart("No sleep level data found")

    # Ensure end_time column exists
    if "end_time" not in levels.columns and "duration_seconds" in levels.columns:
        levels["end_time"] = levels["time"] + pd.to_timedelta(
            levels["duration_seconds"], unit="s"
        )

    # Filter out any rows with invalid datetime values
    levels = levels.dropna(subset=["time", "end_time"])

    if levels.empty:
        return _create_empty_chart("No valid sleep level data found")

    # Convert to timeline format for px.timeline()
    # Use a constant y value to create a single horizontal bar
    timeline_data = []
    for _, row in levels.iterrows():
        timeline_data.append({
            "Task": "Sleep",  # Constant value for single horizontal bar
            "Stage": row["level_name"],
            "Start": row["time"],  # Already a pandas Timestamp with timezone
            "Finish": row["end_time"],  # Already a pandas Timestamp with timezone
            "Duration": f"{row['duration_seconds'] / 60:.0f} min",
        })

    timeline_df = pd.DataFrame(timeline_data)

    # Create Plotly timeline (single horizontal bar with colored segments)
    fig = px.timeline(
        timeline_df,
        x_start="Start",
        x_end="Finish",
        y="Task",  # Single row
        color="Stage",  # Color segments by stage
        color_discrete_map=SLEEP_COLORS,
        category_orders={"Stage": ["Deep", "Light", "REM", "Awake"]},
        hover_data={"Duration": True},
    )

    # Add vertical markers for bed time and wake time using shapes
    fig.add_shape(
        type="line",
        x0=main_start, x1=main_start,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="green", dash="dash", width=1),
    )
    fig.add_annotation(
        x=main_start,
        y=1.1,
        yref="paper",
        text="To Bed",
        showarrow=False,
        font=dict(color="green"),
    )

    if main_sleep_end:
        fig.add_shape(
            type="line",
            x0=main_sleep_end, x1=main_sleep_end,
            y0=0, y1=1,
            yref="paper",
            line=dict(color="green", dash="dash", width=1),
        )
        fig.add_annotation(
            x=main_sleep_end,
            y=1.1,
            yref="paper",
            text="Up",
            showarrow=False,
            font=dict(color="green"),
        )

    # Configure layout
    fig.update_layout(
        title=title,
        xaxis=dict(
            tickformat="%H:%M",
            dtick=60 * 60 * 1000,  # every hour
            range=[start_time, end_time],
            rangeslider=dict(visible=True),
            tickangle=-45,
            showgrid=True,
            gridcolor="rgba(128, 128, 128, 0.3)",
            griddash="dash",
        ),
        yaxis=dict(
            showticklabels=False,
            title="",
        ),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    return fig


def plot_nap_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
) -> Optional[list]:
    """
    Create individual timeline plots for each NAP (non-main sleep sessions).

    ============================================================================
    KEY FEATURE: SEPARATE NAP VISUALIZATION
    - Only shows naps (isMainSleep == 'False')
    - Each nap gets its own separate figure with 30-min buffer before/after
    - Returns list of figures, one per nap, or None if no naps found
    ============================================================================

    Args:
        df_levels: Sleep levels dataframe
        df_summary: Sleep summary dataframe

    Returns:
        List of Plotly Figure objects (one per nap) or None if no naps
    """

    naps = df_summary[df_summary['isMainSleep'] == 'False'].copy()

    if naps.empty:
        print(f"😴 No naps found")
        return None

    # Sort naps by time (earliest first)
    naps = naps.sort_values('time').reset_index(drop=True)

    print(f"💤 Found {len(naps)} nap(s)\n")

    TIMEZONE = "Europe/London"
    figures = []

    for idx, (_, nap) in enumerate(naps.iterrows()):
        # Convert nap times to Europe/London
        nap_time = nap['time'].tz_convert(TIMEZONE)
        nap_end = nap.get('end_time') or nap.get('endTime')
        if nap_end is None and 'minutesAsleep' in nap:
            nap_end = nap_time + pd.Timedelta(minutes=nap['minutesAsleep'])
        else:
            nap_end = pd.to_datetime(nap_end).tz_convert(TIMEZONE) if nap_end is not None else None

        if nap_end is None:
            nap_end = nap_time + pd.Timedelta(hours=1)  # Default 1-hour nap

        nap_label = f"Nap {idx+1}"

        # Calculate display window with 30-min buffer for x-axis range
        display_start = nap_time - pd.Timedelta(minutes=30)
        display_end = nap_end + pd.Timedelta(minutes=30)

        # Get levels for the display period (includes 30-min buffer on each side)
        # This will show Awake (yellow) for the buffer periods
        levels = _fill_sleep_gaps(df_levels, df_summary, display_start, display_end)

        # Ensure end_time column exists
        if not levels.empty and "end_time" not in levels.columns and "duration_seconds" in levels.columns:
            levels["end_time"] = levels["time"] + pd.to_timedelta(
                levels["duration_seconds"], unit="s"
            )

        # Filter out any rows with invalid datetime values
        levels = levels.dropna(subset=["time", "end_time"])

        if levels.empty:
            continue

        # Build timeline data for this nap only
        timeline_data = []
        for _, row in levels.iterrows():
            timeline_data.append({
                "Task": "Nap",  # Constant value for single horizontal bar
                "Stage": row["level_name"],
                "Start": row["time"],
                "Finish": row["end_time"],
                "Duration": f"{row['duration_seconds'] / 60:.0f} min",
            })

        timeline_df = pd.DataFrame(timeline_data)

        # Create single timeline figure for this nap
        fig = px.timeline(
            timeline_df,
            x_start="Start",
            x_end="Finish",
            y="Task",  # Single horizontal bar
            color="Stage",
            color_discrete_map=SLEEP_COLORS,
            category_orders={"Stage": ["Deep", "Light", "REM", "Awake"]},
            hover_data={"Duration": True},
        )

        # Add start time marker
        fig.add_shape(
            type="line",
            x0=nap_time, x1=nap_time,
            y0=0, y1=1,
            yref="paper",
            line=dict(color="green", dash="dash", width=1),
        )
        fig.add_annotation(
            x=nap_time,
            y=1.02,
            yref="paper",
            text=f"Start {nap_time.strftime('%H:%M')}",
            showarrow=False,
            font=dict(color="green", size=10),
        )

        # Add end time marker
        fig.add_shape(
            type="line",
            x0=nap_end, x1=nap_end,
            y0=0, y1=1,
            yref="paper",
            line=dict(color="green", dash="dash", width=1),
        )
        fig.add_annotation(
            x=nap_end,
            y=1.02,
            yref="paper",
            text=f"End {nap_end.strftime('%H:%M')}",
            showarrow=False,
            font=dict(color="green", size=10),
        )

        fig.update_layout(
            height=250,  # Increased height
            xaxis=dict(
                tickformat="%H:%M",
                dtick=15 * 60 * 1000,  # Every 15 minutes
                range=[display_start, display_end],  # 30-min buffer on each side
                tickangle=-45,
                showgrid=True,
                gridcolor="rgba(128, 128, 128, 0.3)",
                griddash="dash",
            ),
            yaxis=dict(
                showticklabels=False,  # Hide the "Nap" label
                title="",
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            title=nap_label,
        )

        figures.append(fig)

    return figures if figures else None


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
    total_in_bed = sum(minutes)
    total_asleep = sum(minutes) - minutes[3]  # Exclude awake
    fig.add_annotation(
        text=f"<b>Asleep</b>: {mins_to_hm(total_asleep)}<br><b>In Bed:</b> <br>{mins_to_hm(total_in_bed)}",
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

def create_sleep_bar_chart():
    pass  # Placeholder for additional functions if needed
        
        

def create_multi_day_sleep_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    dates: List[str],
    timezone: str = "Europe/London",
) -> go.Figure:
    """
    Create a multi-day sleep timeline with one row per day.
    """
    if df_levels.empty or df_summary.empty:
        return _create_empty_chart("No sleep data available")

    reference_date = pd.Timestamp(dates[0], tz=timezone)
    timeline_data = []
    session_markers = []

    for date_str in dates:
        date_ts = pd.Timestamp(date_str, tz=timezone)
        start_time = date_ts
        end_time = date_ts + pd.Timedelta(days=1)

        # Get sessions for this day (for annotations)
        summary_for_day = df_summary.copy()
        summary_for_day['time'] = pd.to_datetime(summary_for_day['time']).dt.tz_convert(timezone)
        if 'end_time' in summary_for_day.columns:
            summary_for_day['end_time'] = pd.to_datetime(summary_for_day['end_time']).dt.tz_convert(timezone)
        elif 'endTime' in summary_for_day.columns:
            summary_for_day['end_time'] = pd.to_datetime(summary_for_day['endTime']).dt.tz_convert(timezone)

        sessions = summary_for_day[
            (summary_for_day['end_time'] > start_time) & (summary_for_day['time'] < end_time)
        ]

        day_levels = _fill_sleep_gaps(df_levels, df_summary, start_time, end_time)

        if day_levels.empty:
            continue

        if "end_time" not in day_levels.columns and "duration_seconds" in day_levels.columns:
            day_levels["end_time"] = day_levels["time"] + pd.to_timedelta(
                day_levels["duration_seconds"], unit="s"
            )

        day_levels = day_levels.dropna(subset=["time", "end_time"])
        if day_levels.empty:
            continue

        day_label = pd.to_datetime(date_str).strftime("%a %b %d")

        # Store session markers for annotations
        for _, session in sessions.iterrows():
            session_start = session['time']
            session_end = session['end_time']

            display_start = max(session_start, start_time)
            display_end = min(session_end, end_time)

            start_mapped = reference_date.replace(
                hour=display_start.hour,
                minute=display_start.minute,
                second=display_start.second
            )
            end_mapped = reference_date.replace(
                hour=display_end.hour,
                minute=display_end.minute,
                second=display_end.second
            )

            if end_mapped <= start_mapped:
                end_mapped += pd.Timedelta(days=1)

            session_markers.append({
                'day': day_label,
                'start': start_mapped,
                'end': end_mapped,
            })

        for _, row in day_levels.iterrows():
            mapped_start = reference_date.replace(
                hour=row["time"].hour,
                minute=row["time"].minute,
                second=row["time"].second
            )
            mapped_end = reference_date.replace(
                hour=row["end_time"].hour,
                minute=row["end_time"].minute,
                second=row["end_time"].second
            )

            if mapped_end <= mapped_start:
                mapped_end += pd.Timedelta(days=1)

            timeline_data.append({
                "Day": day_label,
                "Start": mapped_start,
                "Finish": mapped_end,
                "Stage": row["level_name"],
                "Duration": f"{row.get('duration_seconds', 0) / 60:.0f} min",
            })

    if not timeline_data:
        return _create_empty_chart("No sleep data available for selected dates")

    timeline_df = pd.DataFrame(timeline_data)
    day_order = [pd.to_datetime(d).strftime("%a %b %d") for d in dates]

    fig = px.timeline(
        timeline_df,
        x_start="Start",
        x_end="Finish",
        y="Day",
        color="Stage",
        color_discrete_map=SLEEP_COLORS,
        category_orders={
            "Day": day_order,
            "Stage": ["Deep", "Light", "REM", "Awake"],
        },
        hover_data={"Duration": True},
    )

    # Add "To Bed" and "Up" annotations
    for marker in session_markers:
        fig.add_annotation(
            x=marker['start'],
            y=marker['day'],
            text=f"To Bed<br>{marker['start'].strftime('%H:%M')}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor="green",
            ax=0,
            ay=-40,
            font=dict(color="green", size=12),
            bgcolor="rgba(255, 255, 255, 0.8)",
        )

        fig.add_annotation(
            x=marker['end'],
            y=marker['day'],
            text=f"Up<br>{marker['end'].strftime('%H:%M')}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor="orange",
            ax=0,
            ay=-40,
            font=dict(color="orange", size=12),
            bgcolor="rgba(255, 255, 255, 0.8)",
        )

    num_days = len(timeline_df["Day"].unique())

    fig.update_layout(
        height=150 * max(num_days, 2),
        xaxis=dict(
            tickformat="%H:%M",
            dtick=60 * 120 * 1000,
            tickangle=-45,
            rangeslider=dict(visible=True),
            showgrid=True,
            gridcolor="rgba(128, 128, 128, 0.3)",
            griddash="dash",
        ),
        yaxis=dict(title=""),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=""),
        margin=dict(l=100, r=20, t=40, b=40),
    )

    return fig

def create_consolidated_sleep_timeline(
    df_levels: pd.DataFrame,
    df_summary: pd.DataFrame,
    dates: List[str],
    timezone: str = "Europe/London",
) -> go.Figure:
    """
    Create a consolidated sleep timeline showing all days on a single horizontal bar.

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

    # level_decode = {0: "Deep", 1: "Light", 2: "REM", 3: "Awake"}

    # Prepare data for all days in chronological order
    timeline_data = []

    for date_str in dates:
        date_ts = pd.Timestamp(date_str, tz=timezone)
        start_time = date_ts
        end_time = date_ts + pd.Timedelta(days=1)

        # Use _fill_sleep_gaps to prepare data with Awake periods filled
        day_levels = _fill_sleep_gaps(df_levels, df_summary, start_time, end_time)

        if day_levels.empty:
            continue

        # Ensure end_time column exists
        if "end_time" not in day_levels.columns and "duration_seconds" in day_levels.columns:
            day_levels["end_time"] = day_levels["time"] + pd.to_timedelta(
                day_levels["duration_seconds"], unit="s"
            )

        # Filter out invalid datetime values
        day_levels = day_levels.dropna(subset=["time", "end_time"])

        if day_levels.empty:
            continue

        # Add all sleep stages for this day to the timeline (using actual timestamps)
        for _, row in day_levels.iterrows():
            timeline_data.append({
                "Task": "Sleep",  # Single row for all days
                "Stage": row["level_name"],
                "Start": row["time"],
                "Finish": row["end_time"],
                "Duration": f"{row.get('duration_seconds', 0) / 60:.0f} min",
            })

    if not timeline_data:
        return _create_empty_chart("No sleep data available for selected dates")

    timeline_df = pd.DataFrame(timeline_data)

    # Create Plotly timeline (single horizontal bar with colored segments)
    fig = px.timeline(
        timeline_df,
        x_start="Start",
        x_end="Finish",
        y="Task",  # Single row
        color="Stage",  # Color segments by stage
        color_discrete_map=SLEEP_COLORS,
        category_orders={"Stage": ["Deep", "Light", "REM", "Awake"]},
        hover_data={"Duration": True},
    )


    # Configure layout
    fig.update_layout(
        # title="Consolidated Sleep Timeline - All Days",
        xaxis=dict(
            tickformat="%a %b %d<br>%H:%M",
            tickangle=-45,
            showgrid=True,
            gridcolor="rgba(128, 128, 128, 0.3)",
            griddash="dash",
        ),
        yaxis=dict(
            showticklabels=False,
            title="",
        ),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title="Script",
        ),
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
