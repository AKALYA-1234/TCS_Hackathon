"""
Savings Engine: Computes verified savings post-action vs baseline counterfactual.
Always reports as an uncertainty range (min, max, est), never a misleading single point.
"""
from datetime import datetime
from typing import Dict, Any


class SavingsEngine:
    def __init__(self, base_tariff: float = 8.50, peak_tariff: float = 12.50):
        self.base_tariff = base_tariff
        self.peak_tariff = peak_tariff

    def calculate_verified_savings(
        self,
        room_id: str,
        measured_start: datetime,
        measured_end: datetime,
        actual_kwh: float,
        baseline_kwh: float,
        model_uncertainty_pct: float = 0.12,
        peak_fraction: float = 0.35
    ) -> Dict[str, Any]:
        """
        Reports measured savings range:
        Savings = Baseline (Counterfactual) - Actual Post-Action
        """
        raw_savings = max(0.0, baseline_kwh - actual_kwh)
        
        # Uncertainty band around baseline counterfactual
        kwh_min = max(0.0, round(raw_savings * (1.0 - model_uncertainty_pct), 2))
        kwh_est = round(raw_savings, 2)
        kwh_max = round(raw_savings * (1.0 + model_uncertainty_pct), 2)

        # Blended tariff rate calculation
        blended_rate = (self.base_tariff * (1.0 - peak_fraction)) + (self.peak_tariff * peak_fraction)
        
        inr_min = round(kwh_min * blended_rate, 2)
        inr_est = round(kwh_est * blended_rate, 2)
        inr_max = round(kwh_max * blended_rate, 2)

        return {
            "room_id": room_id,
            "measured_start": measured_start,
            "measured_end": measured_end,
            "actual_kwh": actual_kwh,
            "baseline_kwh": baseline_kwh,
            "savings_kwh": {
                "min": kwh_min,
                "est": kwh_est,
                "max": kwh_max
            },
            "savings_inr": {
                "min": inr_min,
                "est": inr_est,
                "max": inr_max
            },
            "confidence": round(1.0 - model_uncertainty_pct, 2),
            "tariff_blended_inr": round(blended_rate, 2)
        }
