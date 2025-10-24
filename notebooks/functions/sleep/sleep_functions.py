"""
Sleep analysis functions for Fitbit data visualization.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.dates import DateFormatter, MinuteLocator, HourLocator
from datetime import timedelta
import pandas as pd

# Color scheme for sleep stages
SLEEP_COLORS = {
    'Deep': '#1e3a8a',      # Dark blue
    'Light': '#60a5fa',     # Light blue
    'REM': '#a78bfa',       # Purple
    'Awake': '#fbbf24'      # Yellow/amber
}

TIMEZONE = 'Europe/London'

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_main_sleep_session(df_summary):
    """Extract the main sleep session from summary dataframe."""
    if df_summary.empty:
        return None
    
    summary = df_summary.copy()
    if 'isMainSleep' in summary.columns:
        main_sleep = summary[summary['isMainSleep'] == 'True']
        if not main_sleep.empty:
            summary = main_sleep
    
    return summary.iloc[0]


def _prepare_sleep_data(df_levels, df_summary, start_time, end_time):
    """
    Prepare sleep level data for a 24-hour window.
    Adds Awake periods between sleep sessions and at the end.
    """
    # Convert all level times to local timezone
    levels = df_levels.copy()
    levels['time'] = levels['time'].dt.tz_convert(TIMEZONE)
    levels['end_time'] = levels['end_time'].dt.tz_convert(TIMEZONE)
    
    # Filter levels for this time window
    levels = levels[
        (levels['time'] >= start_time) & 
        (levels['time'] < end_time)
    ].copy()
    
    if levels.empty:
        return levels
    
    # Sort by time
    levels = levels.sort_values('time').reset_index(drop=True)
    
    # Get all sleep sessions from summary (converted to local timezone)
    summary = df_summary.copy()
    summary['time'] = summary['time'].dt.tz_convert(TIMEZONE)
    summary['end_time'] = summary['end_time'].dt.tz_convert(TIMEZONE)
    
    # Sort sessions by start time
    summary = summary.sort_values('time').reset_index(drop=True)
    
    gaps_to_add = []
    
    # For each sleep session, check if stages data ends before session end_time
    for idx, session in summary.iterrows():
        session_start = session['time']
        session_end = session['end_time']
        
        # Get stages for this session
        session_stages = levels[
            (levels['time'] >= session_start) & 
            (levels['time'] < session_end)
        ]
        
        if not session_stages.empty:
            last_stage_end = session_stages['end_time'].max()
            
            # If stages end before session end, add Awake period
            if last_stage_end < session_end:
                gap_seconds = (session_end - last_stage_end).total_seconds()
                
                if gap_seconds > 30:  # More than 30 seconds
                    print(f"   ⚠️  Adding Awake at end of session: {gap_seconds/60:.1f} min ({last_stage_end.strftime('%H:%M')} to {session_end.strftime('%H:%M')})")
                    
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
            
            if gap_seconds > 60:  # More than 1 minute
                print(f"   ⚠️  Adding Awake between sessions: {gap_seconds/60:.1f} min ({current_session_end.strftime('%H:%M')} to {next_session_start.strftime('%H:%M')})")
                
                gaps_to_add.append({
                    'time': current_session_end,
                    'end_time': next_session_start,
                    'level': 3.0,
                    'level_name': 'Awake',
                    'duration_seconds': gap_seconds,
                    'Device': levels['Device'].iloc[0] if 'Device' in levels.columns else 'PixelWatch3',
                })
    
    # Add all gaps
    if gaps_to_add:
        levels = pd.concat([levels, pd.DataFrame(gaps_to_add)], ignore_index=True)
        levels = levels.sort_values('time').reset_index(drop=True)
    
    return levels


def _plot_sleep_bars(ax, levels):
    """Plot horizontal bars for sleep stages on given axis."""
    for idx, row in levels.iterrows():
        stage = row['level_name']
        color = SLEEP_COLORS.get(stage, '#cccccc')
        duration_hours = row['duration_seconds'] / 3600
        
        ax.barh(
            y=0,
            width=duration_hours,
            left=row['time'],
            height=0.8,
            color=color,
            edgecolor='white',
            linewidth=0.5,
            alpha=0.9
        )


def _format_timeline_axis(ax, start_time, end_time, title, interval_minutes=15):
    """Apply common formatting to timeline axis."""
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(MinuteLocator(interval=interval_minutes))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax.set_xlim(start_time, end_time)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    ax.grid(True, axis='x', alpha=0.3, linestyle='--')
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)


def _add_sleep_legend(ax, location='upper right'):
    """Add standard sleep stage legend to axis."""
    legend_elements = [
        mpatches.Patch(facecolor=SLEEP_COLORS['Deep'], label='Deep', edgecolor='white'),
        mpatches.Patch(facecolor=SLEEP_COLORS['Light'], label='Light', edgecolor='white'),
        mpatches.Patch(facecolor=SLEEP_COLORS['REM'], label='REM', edgecolor='white'),
        mpatches.Patch(facecolor=SLEEP_COLORS['Awake'], label='Awake', edgecolor='white')
    ]
    ax.legend(handles=legend_elements, loc=location, ncol=4, fontsize=11, framealpha=0.9)


# =============================================================================
# MAIN PLOTTING FUNCTIONS
# =============================================================================

def plot_sleep_timeline(df_levels, df_summary):
    """Plot a horizontal timeline showing sleep stages throughout the night."""
    summary = _get_main_sleep_session(df_summary)
    if summary is None:
        print(f"❌ No sleep summary found in this file")
        return None
    
    start_time = summary['time'].tz_convert(TIMEZONE)
    end_time = summary['end_time'].tz_convert(TIMEZONE)
    
    print(f"🌙 Sleep session: {start_time} to {end_time}")
    print(f"   Duration: {summary['minutesAsleep']:.0f} minutes ({summary['minutesAsleep']/60:.1f} hours)")
    
    # Pass the isMainSleep flag to filter correctly
    is_main = summary.get('isMainSleep', 'True')
    levels = _prepare_sleep_data(df_levels, df_summary, start_time, end_time, is_main_sleep=is_main)
    
    if levels.empty:
        print(f"❌ No sleep level data found for this session")
        return None
    
    print(f"✅ Found {len(levels)} sleep stage records")
    
    # Create plot
    fig, ax = plt.subplots(figsize=(16, 4))
    _plot_sleep_bars(ax, levels)
    
    title = f'Sleep Stages Timeline for {start_time.strftime("%Y-%m-%d")}\n\n{start_time.strftime("%H:%M")} to {end_time.strftime("%H:%M")}'
    _format_timeline_axis(ax, start_time, end_time, title, interval_minutes=15)
    _add_sleep_legend(ax)
    
    plt.tight_layout()
    plt.show()
    
    return fig


# def plot_naps_timeline(df_levels, df_summary):
#     """Plot timeline for naps (isMainSleep = False)."""
#     if df_summary.empty:
#         print(f"❌ No sleep summary found in this file")
#         return None
    
#     if 'isMainSleep' not in df_summary.columns:
#         print(f"❌ No isMainSleep column found")
#         return None
    
#     naps = df_summary[df_summary['isMainSleep'] == 'False']
    
#     if naps.empty:
#         print(f"😴 No naps found in this file")
#         return None
    
#     print(f"Found {len(naps)} nap(s)")
    
#     # Create a subplot for each nap
#     fig, axes = plt.subplots(len(naps), 1, figsize=(16, 4 * len(naps)))
#     if len(naps) == 1:
#         axes = [axes]
    
#     for idx, (nap_idx, nap) in enumerate(naps.iterrows()):
#         ax = axes[idx]
        
#         start_time = nap['time'].tz_convert(TIMEZONE)
#         end_time = nap['end_time'].tz_convert(TIMEZONE)

#         levels = _prepare_sleep_data(df_levels, df_summary, start_time, end_time)
        
#         if levels.empty:
#             ax.text(0.5, 0.5, 'No detailed stage data', 
#                    ha='center', va='center', transform=ax.transAxes)
#             continue
        
#         _plot_sleep_bars(ax, levels)
        
#         title = f'Nap {idx+1} - {start_time.strftime("%Y-%m-%d %H:%M")} to {end_time.strftime("%H:%M")} ({nap["minutesAsleep"]:.0f} min)'
#         _format_timeline_axis(ax, start_time, end_time, title, interval_minutes=15)
        
#         if idx == 0:
#             _add_sleep_legend(ax)
    
#     plt.tight_layout()
#     plt.show()
    
#     return fig


def plot_sleep_stages_pie(df_levels, df_summary):
    """Plot a pie chart showing the distribution of sleep stages in minutes."""
    summary = _get_main_sleep_session(df_summary)
    if summary is None:
        print(f"❌ No sleep summary found in this file")
        return None
    
    start_time = summary['time'].tz_convert(TIMEZONE)
    end_time = summary['end_time'].tz_convert(TIMEZONE)
    
    levels = _prepare_sleep_data(df_levels, df_summary, start_time, end_time)
    
    if levels.empty:
        print(f"❌ No sleep level data found")
        return None
    
    # Calculate minutes per stage
    stage_minutes = levels.groupby('level_name')['duration_seconds'].sum() / 60
    non_awake = stage_minutes.sum() - stage_minutes.get('Awake', 0)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors_ordered = [SLEEP_COLORS[stage] for stage in stage_minutes.index]
    
    wedges, texts, autotexts = ax.pie(
        stage_minutes,
        labels=[f'{stage}\n{mins:.0f} min' for stage, mins in stage_minutes.items()],
        autopct='%1.1f%%',
        colors=colors_ordered,
        startangle=90,
        textprops={'fontsize': 12, 'fontweight': 'bold'},
        explode=[0.05] * len(stage_minutes)
    )
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(14)
    
    ax.set_title(
        f'Sleep Stage Distribution for {start_time.strftime("%Y-%m-%d")}\n\nTotal Sleep: {non_awake:.0f} min (excluding Awake)',
        fontsize=14,
        fontweight='bold',
        pad=12
    )
    
    plt.tight_layout()
    plt.show()
    
    return fig


def display_sleep_efficiency(df_summary):
    """Display sleep efficiency as a simple large text with context."""
    summary = _get_main_sleep_session(df_summary)
    if summary is None:
        print(f"❌ No sleep summary found in this file")
        return None
    
    efficiency = summary['efficiency']
    minutes_asleep = summary['minutesAsleep']
    minutes_in_bed = summary['minutesInBed']
    
    # Determine color and rating based on efficiency
    if efficiency >= 85:
        color, rating = '#10b981', 'Excellent'
    elif efficiency >= 75:
        color, rating = '#3b82f6', 'Good'
    elif efficiency >= 65:
        color, rating = '#f59e0b', 'Fair'
    else:
        color, rating = '#ef4444', 'Needs Improvement'
    
    # Create figure
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('off')
    
    ax.text(0.5, 0.6, f'{efficiency:.0f}%', 
            ha='center', va='center', fontsize=80, fontweight='bold', color=color)
    ax.text(0.5, 0.4, f'Sleep Efficiency - {rating}', 
            ha='center', va='center', fontsize=18, fontweight='bold')
    ax.text(
        0.5, 0.3,
        f'{minutes_asleep:.0f} min asleep / {minutes_in_bed:.0f} min in bed\n\n'
        f'{minutes_asleep/60:.1f} h asleep / {minutes_in_bed/60:.1f} h in bed',
        ha='center', va='center', fontsize=14, style='italic', color=color
    )
    
    plt.tight_layout()
    plt.show()
    
    return fig


# def plot_sleep_stages_bar(df_levels, df_summary):
#     """Plot a single vertical stacked bar showing hours of each sleep stage."""
#     summary = _get_main_sleep_session(df_summary)
#     if summary is None:
#         print(f"❌ No sleep summary found in this file")
#         return None
    
#     start_time = summary['time'].tz_convert(TIMEZONE)
#     end_time = summary['end_time'].tz_convert(TIMEZONE)
    
#     levels = _prepare_sleep_data(df_levels, df_summary, start_time, end_time)
    
#     if levels.empty:
#         print(f"❌ No sleep level data found")
#         return None
    
#     # Calculate hours per stage
#     stage_hours = levels.groupby('level_name')['duration_seconds'].sum() / 3600
    
#     # Ensure all stages are present and ordered
#     stage_order = ['Deep', 'Light', 'REM', 'Awake']
#     for stage in stage_order:
#         if stage not in stage_hours:
#             stage_hours[stage] = 0
#     stage_hours = stage_hours.reindex(stage_order, fill_value=0)
    
#     # Calculate actual sleep time (exclude Awake)
#     time_asleep = stage_hours[['Deep', 'Light', 'REM']].sum()
#     time_in_bed = stage_hours.sum()
    
#     # Create plot
#     fig, ax = plt.subplots(figsize=(6, 10))
    
#     bottom = 0
#     for stage in stage_order:
#         hours = stage_hours[stage]
#         color = SLEEP_COLORS[stage]
        
#         ax.bar(0, hours, bottom=bottom, color=color, edgecolor='white',
#                linewidth=2, width=0.5, label=f'{stage}: {hours:.1f}h')
        
#         if hours > 0.1:
#             ax.text(0, bottom + hours/2, f'{hours:.1f}h',
#                    ha='center', va='center', fontweight='bold', 
#                    fontsize=14, color='white')
        
#         bottom += hours
    
#     ax.set_ylabel('Hours', fontsize=14, fontweight='bold')
#     ax.set_title(f'Sleep Composition for {start_time.strftime("%Y-%m-%d")}',
#                 fontsize=16, fontweight='bold', pad=20)
#     ax.set_xlim(-0.5, 0.5)
#     ax.set_xticks([])
#     ax.legend(loc='upper right', fontsize=11, framealpha=0.9)
#     ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    
#     # Set y-axis limit to add space for labels above bar
#     ax.set_ylim(0, time_in_bed * 1.15)  # Add 15% space at top
    
#     # Add labels above the bar
#     ax.text(0, time_in_bed + 0.5, f'Time in Bed: {time_in_bed:.1f}h',
#            ha='center', fontweight='bold', fontsize=12, color='orange')
#     ax.text(0, time_in_bed + 0.25, f'Time Asleep: {time_asleep:.1f}h',
#            ha='center', fontweight='bold', fontsize=12)
    
#     plt.tight_layout()
#     plt.show()
    
#     return fig