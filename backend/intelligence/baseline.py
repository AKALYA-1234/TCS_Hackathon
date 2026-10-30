"""
Baseline Counterfactual Model Interface & Placeholder Implementation.
Counterfactual: What the room should have consumed given actual headcount, outdoor temperature, and timetable.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any


class BaselineModel(ABC):
    @abstractmethod
    def predict(self, room_id: str, timestamp: datetime, features: Dict[str, Any]) -> Dict[str, float]:
        """
        Returns:
            baseline_kw: float
            lower_bound_kw: float
            upper_bound_kw: float
        """
        pass


class SeasonalGradientBoostingBaseline(BaselineModel):
    """
    Placeholder baseline model mimicking a gradient boosting regressor.
    Inputs: outdoor_temp_c, occupancy, capacity, area_sqm, scheduled_hours, rated_kw.
    Reports expected counterfactual consumption with +/- 10% uncertainty interval.
    """
    def __init__(self, model_version: str = "counterfactual_gbr_v1"):
        self.model_version = model_version

    def predict(self, room_id: str, timestamp: datetime, features: Dict[str, Any]) -> Dict[str, float]:
        outdoor_temp_c = float(features.get("outdoor_temp_c", 32.0))
        occupancy = int(features.get("occupancy", 0))
        capacity = max(1, int(features.get("capacity", 40)))
        rated_kw = float(features.get("rated_kw", 5.0))
        scheduled_hours = bool(features.get("scheduled_hours", False))
        target_temp_c = float(features.get("target_temp_c", 24.0))

        # Counterfactual logic:
        # If room was scheduled or occupied, what SHOULD it consume?
        if not scheduled_hours and occupancy == 0:
            # Should be OFF during unreserved empty periods
            return {
                "baseline_kw": 0.05,
                "lower_bound_kw": 0.0,
                "upper_bound_kw": 0.10,
                "model_version": self.model_version,
                "is_placeholder": True
            }

        # Thermal demand regression formula
        delta_t = max(0.0, outdoor_temp_c - target_temp_c)
        envelope_component = (delta_t / 12.0) * 0.45
        internal_component = (occupancy / capacity) * 0.35
        base_demand_ratio = min(1.0, max(0.20, 0.30 + envelope_component + internal_component))

        baseline_kw = round(rated_kw * base_demand_ratio, 2)
        uncertainty = round(baseline_kw * 0.12, 2)  # 12% uncertainty interval

        return {
            "baseline_kw": baseline_kw,
            "lower_bound_kw": max(0.0, round(baseline_kw - uncertainty, 2)),
            "upper_bound_kw": round(baseline_kw + uncertainty, 2),
            "model_version": self.model_version,
            "is_placeholder": True
        }
