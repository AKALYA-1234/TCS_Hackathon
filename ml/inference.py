"""
Inference interfaces for AC optimization models.
Exposes drop-in classes matching backend service interfaces:
- BaselineInference: predict(room, dt, features) -> {baseline_kw, lower_bound_kw, upper_bound_kw}
- ClassifierInference: classify(features) -> {class, probability, confidence}
- ForecasterInference: forecast_weekly(room_id), forecast_monthly(room_id)
"""
import json
import os
from datetime import datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.features import M1_BASELINE_FEATURES, M2_CLASSIFIER_FEATURES


class BaselineInference:
    def __init__(self, artifact_dir: str = "ml/artifacts"):
        self.artifact_dir = artifact_dir
        model_path = os.path.join(artifact_dir, "m1_baseline.joblib")
        meta_path = os.path.join(artifact_dir, "m1_baseline_metadata.json")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model artifact not found at {model_path}")
            
        self.model = joblib.load(model_path)
        with open(meta_path, "r") as f:
            self.metadata = json.load(f)
        self.q_hat = float(self.metadata.get("conformal_q_hat_kw", 0.50))

    def predict(self, room_id: str, timestamp: datetime, features: dict[str, Any]) -> dict[str, float]:
        """
        Drop-in replacement for backend/intelligence/baseline.py
        Returns:
            baseline_kw: float
            lower_bound_kw: float
            upper_bound_kw: float
        """
        # Format single-row dataframe matching feature builder
        hour = timestamp.hour
        minute_of_day = timestamp.hour * 60 + timestamp.minute
        weekday = timestamp.weekday()
        is_weekend = int(weekday >= 5)

        row_dict = {
            "hour": [hour],
            "minute_of_day": [minute_of_day],
            "weekday": [weekday],
            "is_weekend": [is_weekend],
            "is_holiday": [0],
            "scheduled_hours": [int(features.get("scheduled_hours", False))],
            "outdoor_temp_c": [float(features.get("outdoor_temp_c", 32.0))],
            "temp_lag_1h": [float(features.get("temp_lag_1h", features.get("outdoor_temp_c", 32.0)))],
            "temp_lag_3h": [float(features.get("temp_lag_3h", features.get("outdoor_temp_c", 32.0)))],
            "temp_lag_6h": [float(features.get("temp_lag_6h", features.get("outdoor_temp_c", 32.0)))],
            "relative_humidity": [float(features.get("relative_humidity", 50.0))],
            "set_temp_c": [float(features.get("set_temp_c", 24.0))],
            "expected_headcount": [float(features.get("expected_headcount", features.get("capacity", 40) * 0.75))],
            "room_type": [features.get("room_type", "lecture_hall")],
            "capacity": [float(features.get("capacity", 40))],
            "area_sqm": [float(features.get("area_sqm", 80.0))],
            "rated_kw": [float(features.get("rated_kw", 7.0))],
            "ac_unit_id": [features.get("ac_unit_id", f"ac-{room_id}-1")]
        }

        df_row = pd.DataFrame(row_dict)
        for cat_col in ["room_type", "ac_unit_id"]:
            df_row[cat_col] = df_row[cat_col].astype("category")

        pred_kw = float(self.model.predict(df_row[M1_BASELINE_FEATURES])[0])
        pred_kw = max(0.05, round(pred_kw, 2))

        return {
            "baseline_kw": pred_kw,
            "lower_bound_kw": max(0.0, round(pred_kw - self.q_hat, 2)),
            "upper_bound_kw": round(pred_kw + self.q_hat, 2),
            "model_version": self.metadata.get("model_name", "counterfactual_baseline_v1"),
            "is_placeholder": False
        }

    def predict_batch(self, df_features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Batch prediction returning (pred, lower, upper)."""
        preds = self.model.predict(df_features[M1_BASELINE_FEATURES])
        lower = np.maximum(0.0, preds - self.q_hat)
        upper = preds + self.q_hat
        return preds, lower, upper


class ClassifierInference:
    def __init__(self, artifact_dir: str = "ml/artifacts"):
        self.artifact_dir = artifact_dir
        model_path = os.path.join(artifact_dir, "m2_classifier.joblib")
        meta_path = os.path.join(artifact_dir, "m2_classifier_metadata.json")
        
        self.model = joblib.load(model_path)
        with open(meta_path, "r") as f:
            self.metadata = json.load(f)
        self.classes = self.metadata.get("classes", [])

    def classify(self, feature_dict: dict[str, Any]) -> dict[str, Any]:
        df_row = pd.DataFrame([feature_dict])
        probs = self.model.predict_proba(df_row[M2_CLASSIFIER_FEATURES])[0]
        idx = int(np.argmax(probs))
        pred_class = self.classes[idx]
        confidence = float(probs[idx])

        return {
            "predicted_class": pred_class,
            "confidence": round(confidence, 3),
            "probabilities": {c: round(float(p), 3) for c, p in zip(self.classes, probs)}
        }
