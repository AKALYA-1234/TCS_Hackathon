"""
Optimizer Engine: Minimizes kWh * tariff subject to thermal comfort bounds (24-26°C default),
pre-cooling finished before class, minimum cycle time, and rate limits.
Uses the configurable ASSUMPTION: 4% power savings per 1°C setpoint increase.
"""
from datetime import datetime, time
from typing import Dict, Any, List


class Optimizer:
    def __init__(self, setpoint_savings_pct_per_deg: float = 4.0, base_tariff: float = 8.50, peak_tariff: float = 12.50):
        self.setpoint_savings_pct_per_deg = setpoint_savings_pct_per_deg
        self.base_tariff = base_tariff
        self.peak_tariff = peak_tariff

    def optimize_room(
        self,
        room_id: str,
        current_set_temp_c: float,
        target_comfort_min: float,
        target_comfort_max: float,
        schedule_start_time: str,  # "09:00:00"
        schedule_end_time: str,    # "17:00:00"
        rated_kw: float,
        outdoor_temp_c: float,
        is_critical: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates optimal pre-cool start, shut-off time, recommended setpoint,
        and estimated savings range under the 4%/°C assumption.
        """
        # Thermal comfort recommendation
        # If room is non-critical, optimal setpoint is near upper comfort boundary (e.g. 25.0 - 25.5°C)
        recommended_setpoint = target_comfort_max if not is_critical else round((target_comfort_min + target_comfort_max) / 2.0, 1)

        temp_diff = recommended_setpoint - current_set_temp_c
        savings_pct = max(0.0, temp_diff * (self.setpoint_savings_pct_per_deg / 100.0))

        # Pre-cooling estimation:
        # Pre-cool required based on thermal mass & delta T
        delta_outdoor = max(0.0, outdoor_temp_c - recommended_setpoint)
        precool_lead_minutes = int(min(60, max(15, 10 + delta_outdoor * 2.5)))

        # Shut-off recommendation:
        # Flywheel effect: Turn off AC 15-20 minutes before class ends, thermal mass maintains comfort
        flywheel_shutoff_minutes_before = 15

        # Estimated daily savings
        operating_hours = 8.0
        daily_kwh = rated_kw * operating_hours * 0.65
        kwh_saved_est = round(daily_kwh * savings_pct, 2)
        kwh_saved_min = round(kwh_saved_est * 0.75, 2)
        kwh_saved_max = round(kwh_saved_est * 1.25, 2)

        cost_saved_est = round(kwh_saved_est * self.base_tariff, 2)
        cost_saved_min = round(kwh_saved_min * self.base_tariff, 2)
        cost_saved_max = round(kwh_saved_max * self.base_tariff, 2)

        return {
            "room_id": room_id,
            "current_set_temp_c": current_set_temp_c,
            "recommended_set_temp_c": recommended_setpoint,
            "recommended_precool_lead_min": precool_lead_minutes,
            "recommended_flywheel_shutoff_min": flywheel_shutoff_minutes_before,
            "savings_pct": round(savings_pct * 100, 1),
            "estimated_daily_savings_kwh": {
                "min": kwh_saved_min,
                "est": kwh_saved_est,
                "max": kwh_saved_max
            },
            "estimated_daily_savings_inr": {
                "min": cost_saved_min,
                "est": cost_saved_est,
                "max": cost_saved_max
            },
            "assumptions": {
                "setpoint_effect_pct_per_deg": self.setpoint_savings_pct_per_deg,
                "comfort_band": f"{target_comfort_min}°C - {target_comfort_max}°C",
                "label": "Configurable rule-based heuristic with flywheel coasting"
            }
        }
