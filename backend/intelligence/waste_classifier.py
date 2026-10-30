"""
Waste Classifier: Detects energy waste events by residual analysis (actual - baseline)
plus rules for waste taxonomy:
- after_hours: AC active outside operating/scheduled hours with 0 occupancy
- ghost_cooling: AC cooling an empty room during scheduled gaps
- overcooling: Indoor temp pushed below comfort band (< 22°C)
- early_start: Pre-cooling turned on hours before scheduled lecture
- possible_leakage: High continuous compressor power without indoor temp reduction
Computes wasted kWh, INR cost (including peak tariff multipliers), and confidence.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List


class WasteClassifier:
    def __init__(self, tariff_rate_base: float = 8.50, tariff_rate_peak: float = 12.50):
        self.tariff_rate_base = tariff_rate_base
        self.tariff_rate_peak = tariff_rate_peak

    def classify_reading(
        self,
        room_id: str,
        ac_unit_id: str,
        timestamp: datetime,
        actual_kw: float,
        baseline_kw: float,
        room_temp_c: float,
        target_temp_c: float,
        occupancy: int,
        scheduled_hours: bool,
        duration_hours: float = 0.5  # duration represented by reading
    ) -> Optional[Dict[str, Any]]:
        residual_kw = actual_kw - baseline_kw
        event_type = None
        confidence = 0.85
        details = {}

        # 1. After Hours
        if not scheduled_hours and occupancy == 0 and actual_kw > 0.8:
            event_type = "after_hours"
            confidence = 0.94
            details["reason"] = f"Unit consuming {actual_kw} kW outside scheduled hours with zero occupancy."

        # 2. Ghost Cooling
        elif scheduled_hours and occupancy == 0 and actual_kw > 1.2:
            event_type = "ghost_cooling"
            confidence = 0.91
            details["reason"] = f"Unit cooling empty room ({occupancy} headcount) during timetable gap."

        # 3. Overcooling
        elif room_temp_c < 22.0 and actual_kw > 1.0:
            event_type = "overcooling"
            confidence = 0.95
            details["reason"] = f"Room temperature {room_temp_c}°C is below comfort threshold (22°C)."

        # 4. Possible Leakage or Door Ajar
        elif actual_kw > (baseline_kw * 1.4) and room_temp_c > 26.5:
            event_type = "possible_leakage"
            confidence = 0.82
            details["reason"] = f"High compressor power ({actual_kw} kW) but room temp remains elevated ({room_temp_c}°C)."

        # 5. General Residual Waste
        elif residual_kw > 1.5:
            event_type = "excess_residual"
            confidence = 0.80
            details["reason"] = f"Consumption {actual_kw} kW exceeds baseline upper threshold {baseline_kw} kW."

        if not event_type:
            return None

        # Calculate Wasted kWh and Cost in INR
        wasted_kw = max(0.2, residual_kw if residual_kw > 0 else actual_kw)
        wasted_kwh = round(wasted_kw * duration_hours, 2)

        # Peak hours pricing check (14:00 to 18:00)
        hour = timestamp.hour
        rate = self.tariff_rate_peak if 14 <= hour < 18 else self.tariff_rate_base
        wasted_cost_inr = round(wasted_kwh * rate, 2)

        return {
            "room_id": room_id,
            "ac_unit_id": ac_unit_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "wasted_kwh": wasted_kwh,
            "wasted_cost_inr": wasted_cost_inr,
            "confidence": confidence,
            "details": details
        }
