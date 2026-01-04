# ============================================================================
# SLEEP ANALYSIS CONSTANTS & HELPER FUNCTIONS
# ============================================================================
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter, MinuteLocator, HourLocator
import pandas as pd

TIMEZONE = 'Europe/London'

def get_ordinal_suffix(day):
    """Get ordinal suffix for a day number (st, nd, rd, th)."""
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix

# Color scheme for sleep stages
SLEEP_COLORS = {
    'Deep': '#0f172a',      # Midnight Navy
    'Light': '#a5d8ff',     # Pastel Blue
    'REM': '#c084fc',       # Soft Lavender
    'Awake': '#fde047'      # Butter Yellow
}

# Map numeric levels to names
LEVEL_DECODE = {
    0: 'Deep',
    1: 'Light',
    2: 'REM',
    3: 'Awake'
}


def get_main_sleep_session(df_summary):
    """Extract the main sleep session from summary dataframe."""
    if df_summary.empty:
        return None
    
    summary = df_summary.copy()
    if 'isMainSleep' in summary.columns:
        main_sleep = summary[summary['isMainSleep'] == 'True']
        if not main_sleep.empty:
            summary = main_sleep
    
    return summary.iloc[0]


def prepare_sleep_data(df_levels, df_summary, start_time, end_time):
    """
    Prepare sleep level data for a time window.
    Adds Awake periods at the start, between sessions, and at the end.
    """
    levels = df_levels.copy()
    levels['time'] = levels['time'].dt.tz_convert(TIMEZONE)
    levels['end_time'] = levels['end_time'].dt.tz_convert(TIMEZONE)
    
    levels = levels[
        (levels['time'] >= start_time) & 
        (levels['time'] < end_time)
    ].copy()
    
    if levels.empty:
        return levels
    
    levels = levels.sort_values('time').reset_index(drop=True)
    
    summary = df_summary.copy()
    summary['time'] = summary['time'].dt.tz_convert(TIMEZONE)
    summary['end_time'] = summary['end_time'].dt.tz_convert(TIMEZONE)
    summary = summary.sort_values('time').reset_index(drop=True)
    
    gaps_to_add = []
    
    # Add Awake period from start_time to first sleep session
    if not summary.empty:
        first_session_start = summary['time'].min()
        if start_time < first_session_start:
            gap_seconds = (first_session_start - start_time).total_seconds()
            if gap_seconds > 60:
                gaps_to_add.append({
                    'time': start_time,
                    'end_time': first_session_start,
                    'level': 3.0,
                    'level_name': 'Awake',
                    'duration_seconds': gap_seconds,
                    'Device': levels['Device'].iloc[0] if 'Device' in levels.columns else 'PixelWatch3',
                })
    
    # Check if stages data ends before session end_time
    for idx, session in summary.iterrows():
        session_start = session['time']
        session_end = session['end_time']
        
        session_stages = levels[
            (levels['time'] >= session_start) & 
            (levels['time'] < session_end)
        ]
        
        if not session_stages.empty:
            last_stage_end = session_stages['end_time'].max()
            if last_stage_end < session_end:
                gap_seconds = (session_end - last_stage_end).total_seconds()
                if gap_seconds > 30:
                    gaps_to_add.append({
                        'time': last_stage_end,
                        'end_time': session_end,
                        'level': 3.0,
                        'level_name': 'Awake',
                        'duration_seconds': gap_seconds,
                        'Device': levels['Device'].iloc[0] if 'Device' in levels.columns else 'PixelWatch3',
                    })
    
    # Find gaps BETWEEN sessions
    for i in range(len(summary) - 1):
        current_session_end = summary.iloc[i]['end_time']
        next_session_start = summary.iloc[i + 1]['time']
        
        if current_session_end < next_session_start:
            gap_seconds = (next_session_start - current_session_end).total_seconds()
            if gap_seconds > 60:
                gaps_to_add.append({
                    'time': current_session_end,
                    'end_time': next_session_start,
                    'level': 3.0,
                    'level_name': 'Awake',
                    'duration_seconds': gap_seconds,
                    'Device': levels['Device'].iloc[0] if 'Device' in levels.columns else 'PixelWatch3',
                })
    
    # Add Awake period from last session to end_time
    if not summary.empty:
        last_session_end = summary['end_time'].max()
        if last_session_end < end_time:
            gap_seconds = (end_time - last_session_end).total_seconds()
            if gap_seconds > 60:
                gaps_to_add.append({
                    'time': last_session_end,
                    'end_time': end_time,
                    'level': 3.0,
                    'level_name': 'Awake',
                    'duration_seconds': gap_seconds,
                    'Device': levels['Device'].iloc[0] if 'Device' in levels.columns else 'PixelWatch3',
                })
    
    if gaps_to_add:
        levels = pd.concat([levels, pd.DataFrame(gaps_to_add)], ignore_index=True)
        levels = levels.sort_values('time').reset_index(drop=True)
    
    return levels


def plot_sleep_bars(ax, levels):
    """Plot horizontal bars for sleep stages."""
    seen_labels = set()

    for idx, row in levels.iterrows():
        stage = row['level_name']
        color = SLEEP_COLORS.get(stage, '#cccccc')
        duration_hours = row['duration_seconds'] / 3600
        
        label = stage if stage not in seen_labels else None
        seen_labels.add(stage)

        ax.barh(
            y=0,
            width=duration_hours,
            left=row['time'],
            height=0.8,
            color=color,
            # edgecolor='white',
            # linewidth=0.5,
            alpha=0.9,
            label=label
        )


def format_timeline_axis(ax, start_time, end_time, title, interval_minutes=15):
    """Apply common formatting to timeline axis."""
    formatter = DateFormatter('%H:%M', tz=start_time.tz)
    ax.xaxis.set_major_formatter(formatter)
    
    time_span_hours = (end_time - start_time).total_seconds() / 3600
    
    if time_span_hours > 6:
        ax.xaxis.set_major_locator(HourLocator(interval=1, tz=start_time.tz))
    elif time_span_hours > 2:
        ax.xaxis.set_major_locator(MinuteLocator(byminute=range(0, 60, 30), tz=start_time.tz))
    else:
        ax.xaxis.set_major_locator(MinuteLocator(byminute=range(0, 60, interval_minutes), tz=start_time.tz))
    
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax.set_xlim(start_time, end_time)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    # ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    ax.grid(True, axis='x', alpha=0.3, linestyle='--')
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)


def add_sleep_legend(ax, location='upper right'):
    """Add standard sleep stage legend to axis."""
    legend_elements = [
        mpatches.Patch(facecolor=SLEEP_COLORS['Deep'], label='Deep', edgecolor='orange'),
        mpatches.Patch(facecolor=SLEEP_COLORS['Light'], label='Light', edgecolor='orange'),
        mpatches.Patch(facecolor=SLEEP_COLORS['REM'], label='REM', edgecolor='orange'),
        mpatches.Patch(facecolor=SLEEP_COLORS['Awake'], label='Awake', edgecolor='orange')
    ]
    ax.legend(handles=legend_elements, loc=location, ncol=4, fontsize=11, framealpha=0.9)


# ===== Plots =====

def plot_sleep_timeline(df_levels, df_summary, formatted_date=None):
    """Plot horizontal timeline showing sleep stages for a single day (28-hour window: 20:00 previous day to midnight next day)."""
    if df_levels.empty or df_summary.empty:
        print(f"❌ No sleep data found")
        return None

    main_sleep = df_summary[df_summary.get('isMainSleep', 'True') == 'True']
    if main_sleep.empty:
        main_sleep = df_summary.iloc[[0]]

    main_sleep_start = main_sleep.iloc[0]['time']

    main_sleep_end = (
        main_sleep.iloc[0].get("endTime") or
        main_sleep.iloc[0].get("end_time") or
        None
    )
    if main_sleep_end is not None:
        main_sleep_end = pd.to_datetime(main_sleep_end)
        # Use the wake-up date for the window (more intuitive - "Nov 18's sleep" = woke up on Nov 18)
        actual_date = main_sleep_end.date()
    else:
        actual_date = main_sleep_start.date()

    # Use 28-hour window: 20:00 previous day to 00:00 next day
    start_time = pd.Timestamp(actual_date, tz=TIMEZONE) - pd.Timedelta(hours=3)
    end_time = start_time + pd.Timedelta(hours=27)

    # Format date if not provided
    if formatted_date is None:
        day = actual_date.day
        suffix = get_ordinal_suffix(day)
        formatted_date = actual_date.strftime(f'%A {day}{suffix} %B %Y')

    print(f"   📅 Date: {formatted_date}")
    print(f"   🌙 To Bed: {main_sleep_start.strftime('%H:%M on %A %dth %B')}")
    if main_sleep_end is not None:
        print(f"   ☀️ Woke Up: {main_sleep_end.strftime('%H:%M on %A %dth %B')}\n")

    levels = prepare_sleep_data(df_levels, df_summary, start_time, end_time)
    if levels.empty:
        print(f"❌ No sleep level data found")
        return None

    fig, ax = plt.subplots(figsize=(18, 4))
    plot_sleep_bars(ax, levels)

    ax.axvline(main_sleep_start, linestyle="--", linewidth=1.2)
    ax.text(main_sleep_start, 1.05, "To Bed", ha="center", va="bottom",
            fontsize=10, transform=ax.get_xaxis_transform())

    if main_sleep_end is not None:
        ax.axvline(main_sleep_end, linestyle="--", linewidth=1.2)
        ax.text(main_sleep_end, 1.05, "Up", ha="center", va="bottom",
                fontsize=10, transform=ax.get_xaxis_transform())

    title = f'{formatted_date}\n'

    format_timeline_axis(ax, start_time, end_time, title, interval_minutes=60)
    add_sleep_legend(ax, location='upper right')

    plt.tight_layout()
    return fig



def plot_steps_hour(df_steps_intra):
    """
    Show hourly activity levels as a heatmap-style bar chart.
    
    Args:
        df_steps_intra: Intraday steps DataFrame
        tz: Timezone for display
    
    Returns:
        matplotlib.figure.Figure: The generated figure
    """
    if df_steps_intra.empty:
        print("⚠️  No steps data available")
        return None
    
    df_steps = df_steps_intra.copy()
    
    # Extract date and hour
    date_str = df_steps['time'].iloc[0].strftime('%A, %dth %B')
    df_steps['hour'] = df_steps['time'].dt.hour
    
    # Calculate steps per hour
    hourly_steps = df_steps.groupby('hour', as_index=False)['value'].sum()
    hourly_steps.columns = ['hour', 'steps']
    
    # Ensure all 24 hours are present
    all_hours = pd.DataFrame({'hour': range(24)})
    hourly_steps = all_hours.merge(hourly_steps, on='hour', how='left').fillna(0)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(18, 4))
    
    # Create color map based on activity level
    max_steps = hourly_steps['steps'].max()
    if max_steps > 0:
        colors = plt.cm.YlOrRd(hourly_steps['steps'] / max_steps)
    else:
        colors = ['lightgray'] * 24
    
    # Plot bars
    bars = ax.bar(hourly_steps['hour'], hourly_steps['steps'], 
                  color=colors, edgecolor='black', linewidth=0.5)
    
    # Add value labels on top of bars
    for bar, steps in zip(bars, hourly_steps['steps']):
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(steps)}', ha='center', va='bottom', fontsize=9)
    
    ax.set_ylabel('Total Steps', fontsize=12, fontweight='bold')
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(24)], rotation=45, ha='right')
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    plt.tight_layout()
    return fig


def plot_naps_timeline(df_levels, df_summary, formatted_date=None):
    """Plot individual timelines for all naps."""
    naps = df_summary[df_summary['isMainSleep'] == 'False'].copy()

    if naps.empty:
        print(f"😴 No naps found")
        return None

    # Sort naps by time (earliest first)
    naps = naps.sort_values('time').reset_index(drop=True)

    print(f"💤 Found {len(naps)} nap(s)\n")

    # Format date if not provided
    if formatted_date is None:
        nap_date = naps.iloc[0]['time'].date()
        day = nap_date.day
        suffix = get_ordinal_suffix(day)
        formatted_date = nap_date.strftime(f'%A {day}{suffix} %B %Y')

    fig, axes = plt.subplots(len(naps), 1, figsize=(16, 3 * len(naps)))
    if len(naps) == 1:
        axes = [axes]

    for idx, (nap_idx, nap) in enumerate(naps.iterrows()):
        ax = axes[idx]

        start_time = nap['time'] - pd.Timedelta(minutes=30)
        end_time = nap['end_time'] + pd.Timedelta(minutes=30)

        levels = prepare_sleep_data(df_levels, df_summary, start_time, end_time)

        if levels.empty:
            ax.text(0.5, 0.5, 'No detailed stage data available',
                   ha='center', va='center', transform=ax.transAxes, fontsize=14)
            ax.set_title(f'Nap {idx+1} - No Data', fontweight='bold')
            continue

        plot_sleep_bars(ax, levels)

        nap_duration = nap['minutesInBed']
        nap_asleep = nap['minutesAsleep']

        # Main title for the figure
        fig.suptitle(formatted_date, fontsize=16, fontweight='bold', y=1)

        # Each subplot title:
        title = (f'Nap {idx+1} - {nap["time"].strftime("%H:%M")} to {nap["end_time"].strftime("%H:%M")} | '
                 f'Duration: {nap_duration:.0f} min | Asleep: {nap_asleep:.0f} min')

        format_timeline_axis(ax, start_time, end_time, title, interval_minutes=15)

        if idx == 0:
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=4, frameon=False)

    plt.tight_layout()
    return fig


def plot_sleep_stages_pie(df_levels, df_summary, formatted_date=None):
    """Plot pie chart showing sleep stage distribution."""
    summary = get_main_sleep_session(df_summary)
    if summary is None:
        print(f"❌ No sleep summary found")
        return None

    # Use wake-up date (end_time) for consistency with midnight-to-midnight approach
    end_time = summary.get('end_time') or summary.get('endTime')
    if end_time is not None:
        if isinstance(end_time, str):
            end_time = pd.to_datetime(end_time)
        sleep_date = end_time.date()
    else:
        # Fallback to start time if end_time not available
        start_time = summary['time']
        sleep_date = start_time.date()

    # Format date if not provided
    if formatted_date is None:
        day = sleep_date.day
        suffix = get_ordinal_suffix(day)
        formatted_date = sleep_date.strftime(f'%A {day}{suffix} %B %Y')

    stage_minutes = {
        'Deep': summary.get('minutesDeep', 0),
        'Light': summary.get('minutesLight', 0),
        'REM': summary.get('minutesREM', 0),
        'Awake': summary.get('minutesAwake', 0)
    }

    stage_minutes = pd.Series(stage_minutes)
    non_awake = stage_minutes.sum() - stage_minutes.get('Awake', 0)

    # Convert to hours and minutes
    def mins_to_hm(total_mins):
        hours = int(total_mins // 60)
        mins = int(total_mins % 60)
        return f'{hours}h {mins}m'

    time_in_bed = summary['minutesInBed']
    time_asleep = non_awake

    fig, ax = plt.subplots(figsize=(8, 8))
    colors_ordered = [SLEEP_COLORS[stage] for stage in stage_minutes.index]

    wedges, texts, autotexts = ax.pie(
        stage_minutes,
        labels=[f'{stage}\n{mins_to_hm(mins)}' for stage, mins in stage_minutes.items()],
        autopct='%1.1f%%',
        colors=colors_ordered,
        startangle=90,
        textprops={'fontsize': 12, 'fontweight': 'normal'},
        explode=[0.05] * len(stage_minutes)
    )

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(14)

    ax.set_title(
        f'{formatted_date}\n\n'
        f'Time in Bed: {mins_to_hm(time_in_bed)}\n'
        f'Time Asleep: {mins_to_hm(time_asleep)}',
        fontsize=12,
        fontweight='bold',
        pad=10
    )

    plt.tight_layout()
    return fig

print("✅ Sleep helper functions defined")