"""Dashboard components package."""

from .act_plots import (
    create_hr_timeline,
    create_hourly_steps_chart,
    create_activity_levels_chart,
    create_gps_route_map,
    create_hr_zones_chart,
    create_daily_activity_levels_comparison,
    create_daily_calories_comparison,
    create_daily_hr_zones_comparison,
    create_daily_steps_comparison,
)

from .sleep_plots import (
    plot_sleep_timeline,
    plot_nap_timeline,
    create_sleep_stages_donut,
    create_sleep_stages_bar,
    create_multi_day_sleep_timeline,
    create_consolidated_sleep_timeline,
    create_spo2_trend_chart,
    create_hrv_trend_chart,
    create_skin_temp_trend_chart,
    create_sleep_efficiency_trend_chart,
    create_sleep_stages_stacked_histogram,
)

from .act_metrics import (
    activity_metrics_line1,
    activity_metrics_line2,
    activity_metrics_avgs1,
    activity_metrics_avgs2,
    activity_summary_table,
    calculate_activity_levels,
    calculate_hr_zone_data,
    extract_activity_time_window,
)

from .sleep_metrics import (
    display_sleep_metrics,
    display_sleep_vitals,
    display_sleep_sessions_table,
)

from .calendar import (
    render_calendar,
    get_available_dates,
)

__all__ = [
    "extract_activity_time_window",
    "create_hr_timeline",
    "create_hourly_steps_chart",
    "create_activity_levels_chart",
    "plot_sleep_timeline",
    "plot_nap_timeline",
    "create_sleep_stages_donut",
    "create_sleep_stages_bar",
    "create_gps_route_map",
    "create_hr_zones_chart",
    "create_multi_day_sleep_timeline",
    "create_consolidated_sleep_timeline",
    "create_spo2_trend_chart",
    "create_hrv_trend_chart",
    "create_skin_temp_trend_chart",
    "create_sleep_efficiency_trend_chart",
    "create_sleep_stages_stacked_histogram",
    "create_daily_activity_levels_comparison",
    "create_daily_hr_zones_comparison",
    "create_daily_calories_comparison",
    "create_daily_steps_comparison",
    "activity_metrics_line1",
    "activity_metrics_line2",
    "activity_metrics_avgs1",
    "activity_metrics_avgs2",
    "display_sleep_metrics",
    "display_sleep_vitals",
    "activity_summary_table",
    "display_sleep_sessions_table",
    "calculate_activity_levels",
    "calculate_hr_zone_data",
    "render_calendar",
    "get_available_dates",
]
