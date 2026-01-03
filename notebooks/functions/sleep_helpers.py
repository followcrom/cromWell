# ============================================================================
# SLEEP ANALYSIS CONSTANTS & HELPER FUNCTIONS
# ============================================================================
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter, MinuteLocator, HourLocator
import pandas as pd

TIMEZONE = 'Europe/London'

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


print("✅ Sleep helper functions defined")