"""
Performance analysis functions for Fitbit workout data.

This module provides visualization and analysis tools for workout performance,
including heart rate zones, activity metrics, and full-day context views.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from typing import Dict, Optional, Tuple
import warnings


# ============================================================================
# Configuration
# ============================================================================

# Heart rate zones (user-specific - ideally calculated from age/max HR)
DEFAULT_HR_ZONES = {
    'Out of Range': {'range': (0, 97), 'color': '#808080'},      # Grey
    'Fat Burn': {'range': (98, 122), 'color': '#F5A623'},        # Yellow/Orange
    'Cardio': {'range': (123, 154), 'color': '#FF6B35'},         # Orange
    'Peak': {'range': (155, 220), 'color': '#D0021B'}            # Red
}

# Plotting configuration
PLOT_CONFIG = {
    'buffer_minutes': 15,        # Context window before/after workout
    'steps_bar_width': 0.0007,   # Bar width for minute-level step data
    'default_timezone': 'Europe/London',
    'time_format': '%H:%M',
    'detail_interval_minutes': 5,  # X-axis interval for detailed view
    'fullday_interval_hours': 2,   # X-axis interval for full day view
}


# ============================================================================
# Utility Functions
# ============================================================================

def calculate_hr_zones_from_age(age: int, resting_hr: int = 60) -> Dict:
    """
    Calculate personalized heart rate zones based on age and resting HR.

    Uses Karvonen formula: Target HR = ((Max HR - Resting HR) × %Intensity) + Resting HR
    Max HR = 220 - age

    Parameters:
    - age: User's age in years
    - resting_hr: Resting heart rate (default 60 bpm)

    Returns:
    - Dictionary of HR zones with ranges and colors
    """
    max_hr = 220 - age
    hr_reserve = max_hr - resting_hr

    zones = {
        'Out of Range': {
            'range': (0, int(resting_hr + hr_reserve * 0.50)),
            'color': '#e8f4f8'
        },
        'Fat Burn': {
            'range': (int(resting_hr + hr_reserve * 0.50), int(resting_hr + hr_reserve * 0.70)),
            'color': '#fff4e6'
        },
        'Cardio': {
            'range': (int(resting_hr + hr_reserve * 0.70), int(resting_hr + hr_reserve * 0.85)),
            'color': '#ffe8e8'
        },
        'Peak': {
            'range': (int(resting_hr + hr_reserve * 0.85), max_hr),
            'color': '#ffe0e0'
        }
    }

    return zones


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


def validate_dataframes(
    df_hr_intra: pd.DataFrame,
    df_steps_intra: pd.DataFrame,
    activity_record: pd.Series
) -> bool:
    """
    Validate that required data exists and has proper structure.

    Parameters:
    - df_hr_intra: Heart rate intraday DataFrame
    - df_steps_intra: Steps intraday DataFrame
    - activity_record: Activity record Series

    Returns:
    - True if valid, raises ValueError if invalid
    """
    # Check DataFrames are not empty
    if df_hr_intra.empty:
        raise ValueError("Heart rate DataFrame is empty")

    if df_steps_intra.empty:
        warnings.warn("Steps DataFrame is empty - steps plot will be skipped")

    # Check required columns
    required_hr_cols = ['time', 'value']
    required_steps_cols = ['time', 'value']
    required_activity_fields = ['time', 'duration', 'ActivityName']

    missing_hr = set(required_hr_cols) - set(df_hr_intra.columns)
    if missing_hr:
        raise ValueError(f"Heart rate DataFrame missing columns: {missing_hr}")

    if not df_steps_intra.empty:
        missing_steps = set(required_steps_cols) - set(df_steps_intra.columns)
        if missing_steps:
            raise ValueError(f"Steps DataFrame missing columns: {missing_steps}")

    missing_activity = set(required_activity_fields) - set(activity_record.index)
    if missing_activity:
        raise ValueError(f"Activity record missing fields: {missing_activity}")

    return True


def convert_timezone_safe(
    df: pd.DataFrame,
    time_col: str = 'time',
    target_tz: str = 'Europe/London'
) -> pd.DataFrame:
    """
    Safely convert DataFrame timezone, handling cases where tz is already set.

    Parameters:
    - df: DataFrame with time column
    - time_col: Name of the time column
    - target_tz: Target timezone

    Returns:
    - DataFrame with converted timezone
    """
    df = df.copy()

    if df[time_col].dt.tz is None:
        # No timezone - assume UTC
        df[time_col] = df[time_col].dt.tz_localize('UTC')

    # Convert to target timezone (str comparison handles all timezone types)
    current_tz = str(df[time_col].dt.tz)
    if current_tz != target_tz:
        df[time_col] = df[time_col].dt.tz_convert(target_tz)

    return df


# ============================================================================
# Plotting Functions
# ============================================================================

# def plot_performance_timeline(
#     df_hr_intra: pd.DataFrame,
#     df_steps_intra: pd.DataFrame,
#     activity_record: pd.Series,
#     hr_zones: Optional[Dict] = None,
#     config: Optional[Dict] = None,
#     timezone: str = 'Europe/London'
# ) -> plt.Figure:
#     """
#     Create a detailed performance timeline for a workout session.

#     Shows 3 panels:
#     1. Heart rate with zone coloring and averages
#     2. Steps/activity intensity
#     3. Workout metrics summary

#     Parameters:
#     - df_hr_intra: Intraday heart rate DataFrame
#     - df_steps_intra: Intraday steps DataFrame
#     - activity_record: Single activity record (Series or single-row DataFrame)
#     - hr_zones: Heart rate zones dict (default: DEFAULT_HR_ZONES)
#     - config: Plotting configuration (default: PLOT_CONFIG)
#     - timezone: Display timezone (default: 'Europe/London')

#     Returns:
#     - Matplotlib figure
#     """
#     # Handle defaults
#     if hr_zones is None:
#         hr_zones = DEFAULT_HR_ZONES
#     if config is None:
#         config = PLOT_CONFIG

#     # Extract activity record if DataFrame
#     if isinstance(activity_record, pd.DataFrame):
#         if len(activity_record) == 0:
#             raise ValueError("Activity record DataFrame is empty")
#         activity_record = activity_record.iloc[0]

#     # Validate inputs
#     validate_dataframes(df_hr_intra, df_steps_intra, activity_record)

#     # Convert data to target timezone
#     df_hr_intra = convert_timezone_safe(df_hr_intra, target_tz=timezone)
#     if not df_steps_intra.empty:
#         df_steps_intra = convert_timezone_safe(df_steps_intra, target_tz=timezone)

#     # Extract activity time window
#     activity_start, activity_end, activity_duration = extract_activity_time_window(
#         activity_record, timezone
#     )

#     # Add buffer time for context
#     buffer = pd.Timedelta(minutes=config['buffer_minutes'])
#     plot_start = activity_start - buffer
#     plot_end = activity_end + buffer

#     # Filter data to workout window + buffer
#     hr_window = df_hr_intra[
#         (df_hr_intra['time'] >= plot_start) &
#         (df_hr_intra['time'] <= plot_end)
#     ].copy()

#     steps_window = pd.DataFrame()
#     if not df_steps_intra.empty:
#         steps_window = df_steps_intra[
#             (df_steps_intra['time'] >= plot_start) &
#             (df_steps_intra['time'] <= plot_end)
#         ].copy()

#     if hr_window.empty:
#         raise ValueError(f"No heart rate data found in window {plot_start} to {plot_end}")

#     # Create figure with 3 subplots
#     fig, (ax1, ax2, ax3) = plt.subplots(
#         3, 1, figsize=(14, 10),
#         sharex=True,
#         gridspec_kw={'height_ratios': [2, 1.5, 1]}
#     )

#     # ========================================================================
#     # Panel 1: Heart Rate with Zones
#     # ========================================================================

#     # Plot zone bands
#     for zone_name, zone_info in hr_zones.items():
#         ax1.axhspan(
#             zone_info['range'][0], zone_info['range'][1],
#             alpha=0.2, color=zone_info['color'], label=zone_name
#         )

#     # Highlight workout period
#     ax1.axvspan(
#         activity_start, activity_end,
#         alpha=0.1, color='green', label='Workout Period', zorder=1
#     )

#     # Plot heart rate
#     ax1.plot(
#         hr_window['time'], hr_window['value'],
#         color='#ff4444', linewidth=2, label='Heart Rate', zorder=5
#     )

#     # Add average HR line for workout period
#     hr_workout = hr_window[
#         (hr_window['time'] >= activity_start) &
#         (hr_window['time'] <= activity_end)
#     ]

#     if not hr_workout.empty:
#         avg_hr = hr_workout['value'].mean()
#         ax1.axhline(
#             avg_hr, color='darkred', linestyle='--',
#             linewidth=2, alpha=0.7,
#             label=f'Avg HR: {avg_hr:.0f} bpm', zorder=4
#         )

#     # Add activity average HR from record (if available)
#     if pd.notna(activity_record.get('averageHeartRate')):
#         recorded_avg = activity_record['averageHeartRate']
#         ax1.axhline(
#             recorded_avg, color='purple', linestyle=':',
#             linewidth=2, alpha=0.7,
#             label=f'Recorded Avg: {recorded_avg:.0f} bpm', zorder=4
#         )

#     ax1.set_ylabel('Heart Rate (bpm)', fontsize=11, fontweight='bold')
#     ax1.set_title(
#         f'Workout Performance Analysis - {activity_record["ActivityName"]}',
#         fontsize=14, fontweight='bold'
#     )
#     ax1.grid(True, alpha=0.3, linestyle='--')
#     ax1.legend(loc='upper left', fontsize=9, ncol=2)

#     # ========================================================================
#     # Panel 2: Steps/Activity Intensity
#     # ========================================================================

#     # Plot steps as bar chart
#     if not steps_window.empty:
#         ax2.bar(
#             steps_window['time'], steps_window['value'],
#             width=config['steps_bar_width'],
#             color='#4a90e2', alpha=0.7, label='Steps per Minute'
#         )
#         ax2.legend(loc='upper left', fontsize=9)
#     else:
#         ax2.text(
#             0.5, 0.5, 'No step data available',
#             transform=ax2.transAxes, ha='center', va='center',
#             fontsize=12, color='gray'
#         )

#     ax2.set_ylabel('Steps/min', fontsize=11, fontweight='bold')
#     ax2.grid(True, alpha=0.3, linestyle='--', axis='y')

#     # ========================================================================
#     # Panel 3: Workout Metrics Summary
#     # ========================================================================

#     # Hide axes for metric display
#     ax3.axis('off')

#     # Create metrics display
#     metrics = []
#     metrics.append(f"Activity: {activity_record['ActivityName']}")
#     metrics.append(f"Duration: {activity_duration:.1f} min")

#     if pd.notna(activity_record.get('calories')):
#         metrics.append(f"Calories: {activity_record['calories']:.0f} kcal")

#     if pd.notna(activity_record.get('distance')):
#         metrics.append(f"Distance: {activity_record['distance']:.2f} km")

#     if pd.notna(activity_record.get('steps')):
#         metrics.append(f"Steps: {activity_record['steps']:.0f}")

#     if pd.notna(activity_record.get('pace')):
#         # Convert pace from ms to min/km
#         pace_min_km = activity_record['pace'] / 60000
#         metrics.append(f"Pace: {pace_min_km:.2f} min/km")

#     if pd.notna(activity_record.get('speed')):
#         metrics.append(f"Speed: {activity_record['speed']:.2f} km/h")

#     if pd.notna(activity_record.get('elevationGain')):
#         metrics.append(f"Elevation: {activity_record['elevationGain']:.0f} m")

#     # Display metrics in a grid
#     metrics_text = "  |  ".join(metrics)
#     ax3.text(
#         0.5, 0.5, metrics_text,
#         transform=ax3.transAxes,
#         fontsize=11,
#         ha='center', va='center',
#         bbox=dict(
#             boxstyle='round,pad=1',
#             facecolor='lightblue',
#             alpha=0.3,
#             edgecolor='steelblue',
#             linewidth=2
#         )
#     )

#     # ========================================================================
#     # Formatting
#     # ========================================================================

#     # Format x-axis with time labels - FIXED BUG
#     for ax in [ax1, ax2]:
#         ax.xaxis.set_major_formatter(
#             mdates.DateFormatter(config['time_format'], tz=timezone)
#         )
#         ax.xaxis.set_major_locator(
#             mdates.MinuteLocator(interval=config['detail_interval_minutes'])
#         )
#         ax.tick_params(axis='x', which='both', bottom=True, top=False, labelbottom=True)

#     ax2.set_xlabel('Time', fontsize=11, fontweight='bold')
#     plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

#     plt.tight_layout()
#     return fig


def plot_full_day_with_workout_highlight(
    df_hr_intra: pd.DataFrame,
    df_steps_intra: pd.DataFrame,
    activity_record: pd.Series,
    config: Optional[Dict] = None,
    timezone: str = 'Europe/London'
) -> plt.Figure:
    """
    Show full day context with workout highlighted.

    Shows 2 panels:
    1. Full day heart rate with workout highlighted
    2. Full day steps with workout highlighted

    Parameters:
    - df_hr_intra: Intraday heart rate DataFrame
    - df_steps_intra: Intraday steps DataFrame
    - activity_record: Single activity record (Series or single-row DataFrame)
    - config: Plotting configuration (default: PLOT_CONFIG)
    - timezone: Display timezone (default: 'Europe/London')

    Returns:
    - Matplotlib figure
    """
    # Handle defaults
    if config is None:
        config = PLOT_CONFIG

    # Extract activity record if DataFrame
    if isinstance(activity_record, pd.DataFrame):
        if len(activity_record) == 0:
            raise ValueError("Activity record DataFrame is empty")
        activity_record = activity_record.iloc[0]

    # Validate inputs
    validate_dataframes(df_hr_intra, df_steps_intra, activity_record)

    # Convert data to target timezone
    df_hr_intra = convert_timezone_safe(df_hr_intra, target_tz=timezone)
    if not df_steps_intra.empty:
        df_steps_intra = convert_timezone_safe(df_steps_intra, target_tz=timezone)

    # Extract activity time window
    activity_start, activity_end, activity_duration = extract_activity_time_window(
        activity_record, timezone
    )

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # ========================================================================
    # Panel 1: Full day heart rate
    # ========================================================================

    ax1.plot(
        df_hr_intra['time'], df_hr_intra['value'],
        color='#ff4444', linewidth=1, alpha=0.7
    )
    ax1.axvspan(
        activity_start, activity_end,
        alpha=0.3, color='green',
        label=f'{activity_record["ActivityName"]} ({activity_duration:.0f} min)'
    )
    ax1.set_ylabel('Heart Rate (bpm)', fontweight='bold')
    ax1.set_title('Full Day Context', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend()

    # ========================================================================
    # Panel 2: Full day steps
    # ========================================================================

    if not df_steps_intra.empty:
        ax2.bar(
            df_steps_intra['time'], df_steps_intra['value'],
            width=config['steps_bar_width'], color='#4a90e2', alpha=0.5
        )
        ax2.axvspan(
            activity_start, activity_end,
            alpha=0.3, color='green'
        )
    else:
        ax2.text(
            0.5, 0.5, 'No step data available',
            transform=ax2.transAxes, ha='center', va='center',
            fontsize=12, color='gray'
        )

    ax2.set_ylabel('Steps/min', fontweight='bold')
    ax2.set_xlabel('Time', fontweight='bold')
    ax2.grid(True, alpha=0.3, linestyle='--', axis='y')

    # ========================================================================
    # Formatting
    # ========================================================================

    ax2.xaxis.set_major_formatter(
        mdates.DateFormatter(config['time_format'], tz=timezone)
    )
    ax2.xaxis.set_major_locator(
        mdates.HourLocator(interval=config['fullday_interval_hours'])
    )
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    return fig


def plot_multiple_workouts_comparison(
    df_hr_intra: pd.DataFrame,
    df_steps_intra: pd.DataFrame,
    activity_records: pd.DataFrame,
    hr_zones: Optional[Dict] = None,
    timezone: str = 'Europe/London'
) -> plt.Figure:
    """
    Compare multiple workouts from the same day.

    Parameters:
    - df_hr_intra: Intraday heart rate DataFrame
    - df_steps_intra: Intraday steps DataFrame
    - activity_records: Multiple activity records DataFrame
    - hr_zones: Heart rate zones dict (default: DEFAULT_HR_ZONES)
    - timezone: Display timezone (default: 'Europe/London')

    Returns:
    - Matplotlib figure
    """
    if hr_zones is None:
        hr_zones = DEFAULT_HR_ZONES

    if len(activity_records) == 0:
        raise ValueError("No activity records provided")

    # Convert data to target timezone
    df_hr_intra = convert_timezone_safe(df_hr_intra, target_tz=timezone)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot heart rate
    ax.plot(
        df_hr_intra['time'], df_hr_intra['value'],
        color='#ff4444', linewidth=1, alpha=0.7, label='Heart Rate'
    )

    # Plot zone bands
    for zone_name, zone_info in hr_zones.items():
        ax.axhspan(
            zone_info['range'][0], zone_info['range'][1],
            alpha=0.15, color=zone_info['color']
        )

    # Highlight each workout
    colors = plt.cm.Set3(np.linspace(0, 1, len(activity_records)))

    for idx, (_, activity) in enumerate(activity_records.iterrows()):
        activity_start, activity_end, duration = extract_activity_time_window(
            activity, timezone
        )

        ax.axvspan(
            activity_start, activity_end,
            alpha=0.3, color=colors[idx],
            label=f'{activity["ActivityName"]} ({duration:.0f} min)'
        )

    ax.set_xlabel('Time', fontweight='bold')
    ax.set_ylabel('Heart Rate (bpm)', fontweight='bold')
    ax.set_title('Multiple Workouts Comparison', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=timezone))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    return fig
