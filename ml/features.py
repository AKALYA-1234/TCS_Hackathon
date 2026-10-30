"""
Feature engineering pipelines for ML models (shared by training and inference).
Enforces zero-leakage guards (no forbidden label or future target columns).
"""
import numpy as np
import pandas as pd

# Explicit baseline feature list
M1_BASELINE_FEATURES = [
    "hour",
    "minute_of_day",
    "weekday",
    "is_weekend",
    "is_holiday",
    "scheduled_hours",
    "outdoor_temp_c",
    "temp_lag_1h",
    "temp_lag_3h",
    "temp_lag_6h",
    "relative_humidity",
    "set_temp_c",
    "expected_headcount",
    "room_type",
    "capacity",
    "area_sqm",
    "rated_kw",
    "ac_unit_id"
]

# Explicit waste classifier window features
M2_CLASSIFIER_FEATURES = [
    "baseline_residual_kw",
    "residual_z_score",
    "occupancy_vs_timetable",
    "occupancy",
    "expected_headcount",
    "scheduled_hours",
    "setpoint_minus_room_temp",
    "runtime_fraction",
    "outdoor_temp_c",
    "hour",
    "weekday",
    "is_weekend"
]


def check_forbidden_leakage(feature_cols: list[str]) -> None:
    forbidden = [
        "anomaly_type",
        "wasted_energy_kwh",
        "wasted_power_kw",
        "wasted_cost_inr",
        "is_anomaly",
        "is_legitimate_decoy",
        "severity",
        "counterfactual_power_kw"
    ]
    for c in feature_cols:
        c_low = c.lower()
        for f in forbidden:
            if f in c_low:
                raise ValueError(f"LEAKAGE DETECTED: Column '{c}' contains forbidden pattern '{f}' in feature set!")


class FeatureBuilder:
    @staticmethod
    def build_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineers baseline counterfactual features (M1).
        All features are known or observable without relying on anomalous behavior.
        """
        feats = pd.DataFrame(index=df.index)
        
        # Calendar & time features
        feats["hour"] = df["dt"].dt.hour.astype(np.int32)
        feats["minute_of_day"] = (df["dt"].dt.hour * 60 + df["dt"].dt.minute).astype(np.int32)
        feats["weekday"] = df["dt"].dt.dayofweek.astype(np.int32)
        feats["is_weekend"] = (feats["weekday"] >= 5).astype(np.int32)
        feats["is_holiday"] = 0  # Summer term simulation has standard academic calendar

        # Schedule context
        feats["scheduled_hours"] = df["scheduled_hours"].astype(np.int32)
        feats["set_temp_c"] = df["set_temp_c"].astype(np.float32)
        feats["expected_headcount"] = df["expected_headcount"].astype(np.float32)

        # Weather and lags (calculated per unit time sequence)
        feats["outdoor_temp_c"] = df["outdoor_temp_c"].astype(np.float32)
        feats["relative_humidity"] = df["relative_humidity"].astype(np.float32)

        # Weather lags (1h, 3h, 6h) - outdoor weather is exogenous and safe from target leakage
        # Assuming sorted by (ac_unit_id, dt)
        feats["temp_lag_1h"] = df.groupby("ac_unit_id")["outdoor_temp_c"].shift(4).bfill().astype(np.float32)
        feats["temp_lag_3h"] = df.groupby("ac_unit_id")["outdoor_temp_c"].shift(12).bfill().astype(np.float32)
        feats["temp_lag_6h"] = df.groupby("ac_unit_id")["outdoor_temp_c"].shift(24).bfill().astype(np.float32)

        # Room & unit metadata
        feats["room_type"] = df["room_type"].astype("category")
        feats["capacity"] = df["capacity"].astype(np.float32)
        feats["area_sqm"] = df["area_sqm"].astype(np.float32)
        feats["rated_kw"] = (df["rated_sensible_cooling_w"] / 1000.0).astype(np.float32)
        feats["ac_unit_id"] = df["ac_unit_id"].astype("category")

        # Verify against explicit list and check leakage
        check_forbidden_leakage(list(feats.columns))
        return feats[M1_BASELINE_FEATURES]

    @staticmethod
    def build_classifier_features(
        df: pd.DataFrame,
        baseline_pred_kw: np.ndarray,
        band_q_hat: float = 0.50
    ) -> pd.DataFrame:
        """
        Engineers features for multiclass waste classifier (M2) from observable signals.
        """
        feats = pd.DataFrame(index=df.index)
        
        residual = df["power_kw"].values - baseline_pred_kw
        feats["baseline_residual_kw"] = residual.astype(np.float32)
        feats["residual_z_score"] = (residual / max(0.1, band_q_hat)).astype(np.float32)
        
        # Observed occupancy vs expected
        feats["occupancy"] = df["occupancy"].astype(np.float32)
        feats["expected_headcount"] = df["expected_headcount"].astype(np.float32)
        feats["occupancy_vs_timetable"] = (feats["occupancy"] - feats["expected_headcount"]).astype(np.float32)

        # Room states
        feats["scheduled_hours"] = df["scheduled_hours"].astype(np.int32)
        feats["setpoint_minus_room_temp"] = (df["set_temp_c"] - df["room_temp_c"]).astype(np.float32)
        feats["runtime_fraction"] = df["runtime_fraction"].astype(np.float32)
        feats["outdoor_temp_c"] = df["outdoor_temp_c"].astype(np.float32)

        # Time context
        feats["hour"] = df["dt"].dt.hour.astype(np.int32)
        feats["weekday"] = df["dt"].dt.dayofweek.astype(np.int32)
        feats["is_weekend"] = (feats["weekday"] >= 5).astype(np.int32)

        check_forbidden_leakage(list(feats.columns))
        return feats[M2_CLASSIFIER_FEATURES]
