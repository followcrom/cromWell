import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from matplotlib.patches import Rectangle
import matplotlib.patches as mpatches

# ============================================================================
# OPTION 3: Activity & Heart Rate Correlation (Enhanced)
# ============================================================================
def plot_activity_hr_correlation(df_hr_intra, df_steps_intra, 
                                  df_sedentary, df_light, df_fairly, df_very):
    """
    Detailed activity analysis with heart rate overlay and activity level shading
    """
    # Convert to London timezone
    df_hr = df_hr_intra.copy()
    df_hr['time'] = df_hr['time'].dt.tz_convert('Europe/London')
    
    df_steps = df_steps_intra.copy()
    df_steps['time'] = df_steps['time'].dt.tz_convert('Europe/London')
    
    # Extract activity minutes
    sedentary_min = df_sedentary['value'].iloc[0] if not df_sedentary.empty else 0
    light_min = df_light['value'].iloc[0] if not df_light.empty else 0
    fairly_min = df_fairly['value'].iloc[0] if not df_fairly.empty else 0
    very_min = df_very['value'].iloc[0] if not df_very.empty else 0
    
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3, height_ratios=[2, 1.5, 1])
    
    # ========================================================================
    # Panel 1: Heart Rate & Steps (spans both columns)
    # ========================================================================
    ax1 = fig.add_subplot(gs[0, :])
    
    # Plot HR
    color_hr = '#ff4444'
    ax1.plot(df_hr['time'], df_hr['value'], color=color_hr, 
            linewidth=1.5, label='Heart Rate', alpha=0.8)
    ax1.set_ylabel('Heart Rate (bpm)', fontsize=11, fontweight='bold', color=color_hr)
    ax1.tick_params(axis='y', labelcolor=color_hr)
    ax1.grid(True, alpha=0.3, linestyle='--')
    
    # Secondary axis for steps
    ax1_twin = ax1.twinx()
    color_steps = '#4a90e2'
    ax1_twin.bar(df_steps['time'], df_steps['value'], width=0.0007,
                 color=color_steps, alpha=0.5, label='Steps/min')
    ax1_twin.set_ylabel('Steps/min', fontsize=11, fontweight='bold', color=color_steps)
    ax1_twin.tick_params(axis='y', labelcolor=color_steps)
    
    ax1.set_title('Heart Rate & Activity Throughout Day', fontsize=13, fontweight='bold')
    
    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
    
    # ========================================================================
    # Panel 2: Activity Minutes Breakdown
    # ========================================================================
    ax2 = fig.add_subplot(gs[1, 0])
    
    activity_data = {
        'Sedentary': sedentary_min,
        'Light': light_min,
        'Fairly Active': fairly_min,
        'Very Active': very_min
    }
    
    colors_activity = ['#e0e0e0', '#ffeb99', '#ffb347', '#ff6b6b']
    bars = ax2.bar(activity_data.keys(), activity_data.values(), 
                   color=colors_activity, edgecolor='black', linewidth=1)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)} min', ha='center', va='bottom', fontsize=10)
    
    ax2.set_ylabel('Minutes', fontsize=11, fontweight='bold')
    ax2.set_title('Activity Level Distribution', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # ========================================================================
    # Panel 3: Activity Pie Chart
    # ========================================================================
    ax3 = fig.add_subplot(gs[1, 1])
    
    # Only include non-zero values
    pie_data = {k: v for k, v in activity_data.items() if v > 0}
    
    if pie_data:
        wedges, texts, autotexts = ax3.pie(pie_data.values(), 
                                            labels=pie_data.keys(),
                                            colors=colors_activity,
                                            autopct='%1.1f%%',
                                            startangle=90)
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)
    
    ax3.set_title('Activity Time Proportion', fontsize=12, fontweight='bold')
    
    # ========================================================================
    # Panel 4: HR Statistics by Activity Level (spans both columns)
    # ========================================================================
    ax4 = fig.add_subplot(gs[2, :])
    
    # Calculate HR stats for different step ranges
    df_hr_steps = df_hr.merge(df_steps, on='time', how='left', suffixes=('_hr', '_steps'))
    df_hr_steps['value_steps'] = df_hr_steps['value_steps'].fillna(0)
    
    # Define activity categories by steps/min
    df_hr_steps['activity_level'] = pd.cut(df_hr_steps['value_steps'],
                                           bins=[0, 1, 50, 100, 200],
                                           labels=['Resting', 'Light', 'Moderate', 'Vigorous'])
    
    # Calculate mean HR for each activity level
    hr_by_activity = df_hr_steps.groupby('activity_level', observed=True)['value_hr'].agg(['mean', 'std']).reset_index()
    
    bars = ax4.bar(range(len(hr_by_activity)), hr_by_activity['mean'],
                   yerr=hr_by_activity['std'], capsize=5,
                   color=['#e0e0e0', '#ffeb99', '#ffb347', '#ff6b6b'],
                   edgecolor='black', linewidth=1)
    
    ax4.set_xticks(range(len(hr_by_activity)))
    ax4.set_xticklabels(hr_by_activity['activity_level'])
    ax4.set_ylabel('Average Heart Rate (bpm)', fontsize=11, fontweight='bold')
    ax4.set_title('Heart Rate by Activity Level', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    # Add value labels
    for i, (bar, mean_val) in enumerate(zip(bars, hr_by_activity['mean'])):
        ax4.text(bar.get_x() + bar.get_width()/2., mean_val,
                f'{mean_val:.0f}', ha='center', va='bottom', fontsize=10)
    
    # Format x-axis for top panel
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz='Europe/London'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.suptitle('Activity & Heart Rate Analysis', fontsize=15, fontweight='bold', y=0.995)
    
    return fig


# ============================================================================
# OPTION 4: Sleep Analysis Dashboard
# ============================================================================
def plot_sleep_analysis(df_sleep_levels, df_sleep_summary, df_hrv, 
                        df_resting_hr, df_breathing_rate, df_skin_temp):
    """
    Comprehensive sleep analysis with stages, efficiency, and recovery metrics
    """
    # Extract sleep summary metrics
    if not df_sleep_summary.empty:
        efficiency = df_sleep_summary['efficiency'].iloc[0]
        mins_asleep = df_sleep_summary['minutesAsleep'].iloc[0]
        mins_awake = df_sleep_summary['minutesAwake'].iloc[0]
        mins_light = df_sleep_summary['minutesLight'].iloc[0]
        mins_rem = df_sleep_summary['minutesREM'].iloc[0]
        mins_deep = df_sleep_summary['minutesDeep'].iloc[0]
        sleep_start = pd.to_datetime(df_sleep_summary['time'].iloc[0])
        sleep_end = pd.to_datetime(df_sleep_summary['endTime'].iloc[0])
    else:
        return None
    
    # Convert to London timezone
    df_levels = df_sleep_levels.copy()
    df_levels['time'] = pd.to_datetime(df_levels['time']).dt.tz_convert('Europe/London')
    
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)  # Changed from 3 to 2 rows
    
    # Color mapping for sleep levels
    level_colors = {
        'wake': '#ff6b6b',
        'light': '#4ecdc4',
        'deep': '#1a535c',
        'rem': '#ffe66d',
        'awake': '#ff6b6b'
    }
    
    # level_positions = {
    #     'wake': 4,
    #     'awake': 4,
    #     'rem': 3,
    #     'light': 2,
    #     'deep': 1
    # }
    
    # ========================================================================
    # Panel 2: Sleep Stage Duration
    # ========================================================================
    ax2 = fig.add_subplot(gs[0, 0])  # Changed from [1, 0] to [0, 0]
    
    sleep_data = {
        'Deep': mins_deep,
        'Light': mins_light,
        'REM': mins_rem,
        'Awake': mins_awake
    }
    
    colors = [level_colors['deep'], level_colors['light'], 
              level_colors['rem'], level_colors['wake']]
    
    bars = ax2.bar(sleep_data.keys(), sleep_data.values(),
                   color=colors, edgecolor='black', linewidth=1)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)} min', ha='center', va='bottom', fontsize=10)
    
    ax2.set_ylabel('Minutes', fontsize=11, fontweight='bold')
    ax2.set_title('Sleep Stage Distribution', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    # ========================================================================
    # Panel 3: Sleep Pie Chart
    # ========================================================================
    ax3 = fig.add_subplot(gs[0, 1])
    
    wedges, texts, autotexts = ax3.pie(sleep_data.values(),
                                        labels=sleep_data.keys(),
                                        colors=colors,
                                        autopct='%1.1f%%',
                                        startangle=90)
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    ax3.set_title('Sleep Composition', fontsize=12, fontweight='bold')
    
    # ========================================================================
    # Panel 4: Recovery Metrics (spans both columns)
    # ========================================================================
    ax4 = fig.add_subplot(gs[1, :])  # Changed from [2, :] to [1, :]
    ax4.axis('off')
    
    # Gather recovery metrics
    metrics_text = f"Sleep Duration: {mins_asleep} min ({mins_asleep/60:.1f} hrs)\n"
    metrics_text += f"Sleep Efficiency: {efficiency}%\n"
    
    if not df_hrv.empty:
        metrics_text += f"Daily HRV (RMSSD): {df_hrv['dailyRmssd'].iloc[0]:.1f} ms\n"
        metrics_text += f"Deep Sleep HRV: {df_hrv['deepRmssd'].iloc[0]:.1f} ms\n"
    
    if not df_resting_hr.empty:
        metrics_text += f"Resting Heart Rate: {df_resting_hr['value'].iloc[0]:.0f} bpm\n"
    
    if not df_breathing_rate.empty:
        metrics_text += f"Breathing Rate: {df_breathing_rate['value'].iloc[0]:.1f} breaths/min\n"
    
    if not df_skin_temp.empty:
        metrics_text += f"Skin Temperature Variation: {df_skin_temp['nightlyRelative'].iloc[0]:+.2f}°C"
    
    ax4.text(0.5, 0.5, metrics_text,
            transform=ax4.transAxes,
            fontsize=12,
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=1',
                     facecolor='lightblue',
                     alpha=0.3,
                     edgecolor='steelblue',
                     linewidth=2),
            family='monospace')
    
    plt.suptitle('Sleep Analysis & Recovery Metrics', fontsize=15, fontweight='bold', y=0.995)
    
    return fig

# ============================================================================
# OPTION 5: Daily Activity Summary Wheel
# ============================================================================
def plot_activity_summary_wheel(df_sedentary, df_light, df_fairly, df_very,
                                 df_steps, df_calories, df_distance):
    """
    Create a comprehensive daily activity summary with donut chart
    """
    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    
    # Extract values
    sedentary = df_sedentary['value'].iloc[0] if not df_sedentary.empty else 0
    light = df_light['value'].iloc[0] if not df_light.empty else 0
    fairly = df_fairly['value'].iloc[0] if not df_fairly.empty else 0
    very = df_very['value'].iloc[0] if not df_very.empty else 0
    
    total_steps = df_steps['value'].iloc[0] if not df_steps.empty else 0
    total_calories = df_calories['value'].iloc[0] if not df_calories.empty else 0
    total_distance = df_distance['value'].iloc[0] if not df_distance.empty else 0
    
    # ========================================================================
    # Panel 1: Activity Minutes Donut Chart
    # ========================================================================
    ax1 = fig.add_subplot(gs[0, 0])
    
    activity_data = [sedentary, light, fairly, very]
    activity_labels = ['Sedentary', 'Lightly Active', 'Fairly Active', 'Very Active']
    colors = ['#e0e0e0', '#ffeb99', '#ffb347', '#ff6b6b']
    
    wedges, texts, autotexts = ax1.pie(activity_data,
                                        labels=activity_labels,
                                        colors=colors,
                                        autopct='%1.1f%%',
                                        startangle=90,
                                        pctdistance=0.85,
                                        wedgeprops=dict(width=0.5, edgecolor='white'))
    
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)
    
    # Add center circle for donut effect
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    ax1.add_artist(centre_circle)
    
    # Add total time in center
    total_mins = sum(activity_data)
    ax1.text(0, 0, f'{int(total_mins)} min\n({total_mins/60:.1f} hrs)',
            ha='center', va='center', fontsize=14, fontweight='bold')
    
    ax1.set_title('Activity Level Distribution', fontsize=12, fontweight='bold', pad=20)
    
    # ========================================================================
    # Panel 2: Key Metrics
    # ========================================================================
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.axis('off')
    
    metrics = [
        ('Steps', f'{int(total_steps):,}', '⚡'),
        ('Calories', f'{int(total_calories):,} kcal', '⚡'),
        ('Distance', f'{total_distance:.2f} km', '⚡'),
        ('Active Time', f'{int(light + fairly + very)} min', '⚡')
    ]
    
    y_pos = 0.9
    for label, value, emoji in metrics:
        ax2.text(0.1, y_pos, f'{emoji} {label}:', fontsize=12, fontweight='bold')
        ax2.text(0.9, y_pos, value, fontsize=12, ha='right')
        y_pos -= 0.2
    
    # Add box around metrics
    rect = mpatches.FancyBboxPatch((0.05, 0.1), 0.9, 0.85,
                                   boxstyle="round,pad=0.05",
                                   edgecolor='steelblue',
                                   facecolor='lightblue',
                                   alpha=0.2,
                                   linewidth=2,
                                   transform=ax2.transAxes)
    ax2.add_patch(rect)
    
    ax2.set_title('Daily Summary', fontsize=12, fontweight='bold', pad=20)
    
    # ========================================================================
    # Panel 3: Activity Minutes Bar Chart
    # ========================================================================
    ax3 = fig.add_subplot(gs[1, :])
    
    bars = ax3.barh(activity_labels, activity_data, color=colors,
                    edgecolor='black', linewidth=1)
    
    # Add value labels
    for bar, minutes in zip(bars, activity_data):
        width = bar.get_width()
        ax3.text(width, bar.get_y() + bar.get_height()/2.,
                f' {int(minutes)} min',
                ha='left', va='center', fontsize=11, fontweight='bold')
    
    ax3.set_xlabel('Minutes', fontsize=11, fontweight='bold')
    ax3.set_title('Time in Each Activity Level', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='x', linestyle='--')
    
    plt.suptitle('Daily Activity Summary', fontsize=14, fontweight='bold', y=0.98)
    
    return fig

# ============================================================================
# OPTION 7: Recovery & Readiness Score
# ============================================================================
def plot_recovery_readiness(df_hrv, df_resting_hr, df_sleep_summary,
                            df_breathing_rate, df_skin_temp):
    """
    Calculate and visualize a recovery/readiness score based on multiple metrics
    """
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    fig.suptitle('Recovery & Readiness Assessment', fontsize=15, fontweight='bold')
    
    # Initialize readiness components
    readiness_scores = {}
    
    # ========================================================================
    # Metric 1: HRV Score (Daily RMSSD)
    # ========================================================================
    ax1 = axes[0, 0]
    if not df_hrv.empty:
        hrv_value = df_hrv['dailyRmssd'].iloc[0]
        # Rough scoring: >50 excellent, 30-50 good, <30 needs recovery
        hrv_score = min(100, (hrv_value / 50) * 100)
        readiness_scores['HRV'] = hrv_score
        
        color = '#50c878' if hrv_score > 70 else '#ffb347' if hrv_score > 50 else '#ff6b6b'
        ax1.bar(['HRV'], [hrv_value], color=color, edgecolor='black', linewidth=2)
        ax1.axhline(50, color='green', linestyle='--', alpha=0.5, label='Excellent')
        ax1.axhline(30, color='orange', linestyle='--', alpha=0.5, label='Good')
        ax1.text(0, hrv_value, f'{hrv_value:.1f} ms', ha='center', va='bottom', 
                fontsize=11, fontweight='bold')
        ax1.set_ylabel('RMSSD (ms)', fontweight='bold')
        ax1.set_title('Heart Rate Variability', fontweight='bold')
        ax1.legend(fontsize=8)
    else:
        ax1.text(0.5, 0.5, 'No HRV data', ha='center', va='center',
                transform=ax1.transAxes)
    
    # ========================================================================
    # Metric 2: Resting Heart Rate
    # ========================================================================
    ax2 = axes[0, 1]
    if not df_resting_hr.empty:
        rhr_value = df_resting_hr['value'].iloc[0]
        # Lower is better: <60 excellent, 60-70 good, >70 needs attention
        rhr_score = max(0, 100 - (rhr_value - 50) * 2)
        readiness_scores['RHR'] = rhr_score
        
        color = '#50c878' if rhr_value < 60 else '#ffb347' if rhr_value < 70 else '#ff6b6b'
        ax2.bar(['RHR'], [rhr_value], color=color, edgecolor='black', linewidth=2)
        ax2.axhline(60, color='green', linestyle='--', alpha=0.5, label='Excellent')
        ax2.axhline(70, color='orange', linestyle='--', alpha=0.5, label='Good')
        ax2.text(0, rhr_value, f'{int(rhr_value)} bpm', ha='center', va='bottom',
                fontsize=11, fontweight='bold')
        ax2.set_ylabel('BPM', fontweight='bold')
        ax2.set_title('Resting Heart Rate', fontweight='bold')
        ax2.legend(fontsize=8)
    else:
        ax2.text(0.5, 0.5, 'No RHR data', ha='center', va='center',
                transform=ax2.transAxes)
    
    # ========================================================================
    # Metric 3: Sleep Efficiency
    # ========================================================================
    ax3 = axes[0, 2]
    if not df_sleep_summary.empty:
        efficiency = df_sleep_summary['efficiency'].iloc[0]
        readiness_scores['Sleep'] = efficiency
        
        color = '#50c878' if efficiency > 85 else '#ffb347' if efficiency > 75 else '#ff6b6b'
        ax3.bar(['Sleep'], [efficiency], color=color, edgecolor='black', linewidth=2)
        ax3.axhline(85, color='green', linestyle='--', alpha=0.5, label='Excellent')
        ax3.axhline(75, color='orange', linestyle='--', alpha=0.5, label='Good')
        ax3.text(0, efficiency, f'{efficiency}%', ha='center', va='bottom',
                fontsize=11, fontweight='bold')
        ax3.set_ylabel('Efficiency (%)', fontweight='bold')
        ax3.set_title('Sleep Quality', fontweight='bold')
        ax3.set_ylim([0, 100])
        ax3.legend(fontsize=8)
    else:
        ax3.text(0.5, 0.5, 'No sleep data', ha='center', va='center',
                transform=ax3.transAxes)
    
    # ========================================================================
    # Metric 4: Breathing Rate
    # ========================================================================
    ax4 = axes[1, 0]
    if not df_breathing_rate.empty:
        br_value = df_breathing_rate['value'].iloc[0]
        # Normal range 12-20, optimal 12-16
        br_score = max(0, 100 - abs(br_value - 14) * 5)
        readiness_scores['Breathing'] = br_score
        
        color = '#50c878' if 12 <= br_value <= 16 else '#ffb347'
        ax4.bar(['BR'], [br_value], color=color, edgecolor='black', linewidth=2)
        ax4.axhspan(12, 16, alpha=0.2, color='green', label='Optimal')
        ax4.text(0, br_value, f'{br_value:.1f}', ha='center', va='bottom',
                fontsize=11, fontweight='bold')
        ax4.set_ylabel('Breaths/min', fontweight='bold')
        ax4.set_title('Breathing Rate', fontweight='bold')
        ax4.legend(fontsize=8)
    else:
        ax4.text(0.5, 0.5, 'No breathing data', ha='center', va='center',
                transform=ax4.transAxes)
    
    # ========================================================================
    # Metric 5: Skin Temperature Variation
    # ========================================================================
    ax5 = axes[1, 1]
    if not df_skin_temp.empty:
        temp_var = df_skin_temp['nightlyRelative'].iloc[0]
        # Closer to 0 is better
        temp_score = max(0, 100 - abs(temp_var) * 50)
        readiness_scores['Temp'] = temp_score
        
        color = '#50c878' if abs(temp_var) < 0.5 else '#ffb347' if abs(temp_var) < 1 else '#ff6b6b'
        ax5.bar(['Temp'], [temp_var], color=color, edgecolor='black', linewidth=2)
        ax5.axhline(0, color='green', linestyle='--', alpha=0.5, label='Baseline')
        ax5.text(0, temp_var, f'{temp_var:+.2f}°C', ha='center', 
                va='bottom' if temp_var > 0 else 'top',
                fontsize=11, fontweight='bold')
        ax5.set_ylabel('Temperature Variation (°C)', fontweight='bold')
        ax5.set_title('Skin Temperature', fontweight='bold')
        ax5.legend(fontsize=8)
    else:
        ax5.text(0.5, 0.5, 'No temp data', ha='center', va='center',
                transform=ax5.transAxes)
    
    # ========================================================================
    # Overall Readiness Score
    # ========================================================================
    ax6 = axes[1, 2]
    ax6.axis('off')
    
    if readiness_scores:
        overall_score = np.mean(list(readiness_scores.values()))
        
        # Determine readiness level
        if overall_score >= 80:
            level = 'EXCELLENT'
            level_color = '#50c878'
            emoji = '💪'
        elif overall_score >= 65:
            level = 'GOOD'
            level_color = '#ffb347'
            emoji = '👍'
        else:
            level = 'RECOVERY NEEDED'
            level_color = '#ff6b6b'
            emoji = '😴'
        
        # Draw circular score
        circle = plt.Circle((0.5, 0.6), 0.25, color=level_color, alpha=0.3,
                           transform=ax6.transAxes)
        ax6.add_patch(circle)
        
        ax6.text(0.5, 0.15, 'Readiness Score',
                ha='center', va='center',
                fontsize=12,
                transform=ax6.transAxes)
        
        ax6.set_title('Overall Assessment', fontweight='bold', pad=20)
    else:
        ax6.text(0.5, 0.5, 'Insufficient data\nfor score',
                ha='center', va='center',
                fontsize=12,
                transform=ax6.transAxes)
    
    plt.tight_layout()
    return fig