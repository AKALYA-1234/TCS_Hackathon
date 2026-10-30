"""
Load Forecaster: Weekly and monthly load per room and unit with intervals.
Inputs: outdoor temperature forecast, headcount schedule, and peak tariff hours.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any


class Forecaster:
    def __init__(self, base_tariff: float = 8.50, peak_tariff: float = 12.50):
        self.base_tariff = base_tariff
        self.peak_tariff = peak_tariff

    def generate_weekly_forecast(self, room_id: str, rated_kw: float, capacity: int) -> List[Dict[str, Any]]:
        """Generates 7-day ahead load forecast in 24h day-blocks."""
        now = datetime.now(timezone.utc)
        results = []
        for d in range(7):
            forecast_date = (now + timedelta(days=d)).replace(hour=12, minute=0, second=0, microsecond=0)
            is_weekend = forecast_date.weekday() >= 5
            
            # Weekend consumption is light (~20% of weekday)
            day_hours = 8 if not is_weekend else 2
            load_factor = 0.55 if not is_weekend else 0.15
            
            day_kwh = round(rated_kw * day_hours * load_factor, 1)
            uncertainty = round(day_kwh * 0.15, 1)
            
            cost = round(day_kwh * self.base_tariff, 2)
            results.append({
                "room_id": room_id,
                "timestamp": forecast_date.isoformat(),
                "predicted_kwh": day_kwh,
                "lower_kwh": max(0.0, day_kwh - uncertainty),
                "upper_kwh": day_kwh + uncertainty,
                "predicted_cost_inr": cost,
                "is_placeholder": True
            })
        return results

    def generate_monthly_forecast(self, room_id: str, rated_kw: float, capacity: int) -> List[Dict[str, Any]]:
        """Generates 4-week load forecast."""
        now = datetime.now(timezone.utc)
        results = []
        for w in range(4):
            week_date = (now + timedelta(weeks=w)).replace(hour=12, minute=0, second=0, microsecond=0)
            # Approx 5 weekdays + 2 weekend days
            week_kwh = round(rated_kw * (5 * 8 * 0.55 + 2 * 2 * 0.15), 1)
            uncertainty = round(week_kwh * 0.18, 1)
            cost = round(week_kwh * self.base_tariff, 2)
            results.append({
                "room_id": room_id,
                "timestamp": week_date.isoformat(),
                "predicted_kwh": week_kwh,
                "lower_kwh": max(0.0, week_kwh - uncertainty),
                "upper_kwh": week_kwh + uncertainty,
                "predicted_cost_inr": cost,
                "is_placeholder": True
            })
        return results
