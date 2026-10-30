"""
Model M2: Multiclass Waste Classifier & Model M3: Unsupervised Anomaly Detector.
M2: Classifies intervals into normal, after_hours, ghost_cooling, overcooling,
    early_start, possible_leakage, while ensuring decoys remain non-waste.
M3: Isolation Forest anomaly detector baseline trained on normal intervals.
"""
import json
import logging
import os
import time
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)

from ml.data import DataLoader
from ml.features import M2_CLASSIFIER_FEATURES, FeatureBuilder

logger = logging.getLogger("ml.classifier")

CLASSES = [
    "normal",
    "after_hours",
    "ghost_cooling",
    "overcooling",
    "early_start",
    "possible_leakage"
]


class WasteClassifierTrainer:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.model = None
        self.metadata: dict[str, Any] = {}

    def train(
        self,
        baseline_model_path: str = "ml/artifacts/m1_baseline.joblib",
        slice_days: int | None = None,
        resolution_mins: int = 15
    ) -> dict[str, Any]:
        """
        Trains multiclass LightGBM waste classifier.
        """
        logger.info(f"Loading telemetry for waste classification (slice_days={slice_days})...")
        loader = DataLoader()
        df_all = loader.load_telemetry_with_weather(slice_days=slice_days, resolution_mins=resolution_mins)
        df_gt = loader.load_ground_truth_labels()

        # Load baseline model to generate residuals
        if not os.path.exists(baseline_model_path):
            raise FileNotFoundError(f"Baseline model missing at {baseline_model_path}")
        m1_model = joblib.load(baseline_model_path)
        with open("ml/artifacts/m1_baseline_metadata.json") as f:
            m1_meta = json.load(f)
        band_q_hat = float(m1_meta.get("conformal_q_hat_kw", 0.50))

        # Predict baseline
        X_base = FeatureBuilder.build_baseline_features(df_all)
        base_pred_kw = m1_model.predict(X_base)

        # Label intervals with ground-truth events
        # Initialize with 'normal'
        df_all["target_class"] = "normal"
        df_all["is_decoy"] = False

        for _, ev in df_gt.iterrows():
            mask = (df_all["ac_unit_id"] == ev["ac_unit_id"]) & \
                   (df_all["dt"] >= ev["start_time"]) & \
                   (df_all["dt"] < ev["end_time"])
            if ev["is_legitimate_decoy"]:
                df_all.loc[mask, "is_decoy"] = True
                # Decoys must be classified as normal / non-waste
                df_all.loc[mask, "target_class"] = "normal"
            else:
                anom = ev["anomaly_type"]
                if anom in CLASSES:
                    df_all.loc[mask, "target_class"] = anom

        logger.info("Class distribution in full labeled dataset:")
        logger.info(df_all["target_class"].value_counts().to_dict())

        # Build classifier features
        X_clf = FeatureBuilder.build_classifier_features(df_all, base_pred_kw, band_q_hat)
        df_all_feat = pd.concat([df_all[["dt", "ac_unit_id", "room", "target_class", "is_decoy"]], X_clf], axis=1)

        # Time split
        df_train, _df_cal, df_test = loader.time_split(df_all_feat)

        class_to_idx = {c: i for i, c in enumerate(CLASSES)}
        y_train = df_train["target_class"].map(class_to_idx).values
        X_train = df_train[M2_CLASSIFIER_FEATURES]

        y_test = df_test["target_class"].map(class_to_idx).values
        X_test = df_test[M2_CLASSIFIER_FEATURES]

        # Handle class imbalance via class_weight='balanced'
        logger.info("Fitting multiclass LightGBM classifier (class_weight='balanced', n_jobs=3)...")
        params = {
            "objective": "multiclass",
            "num_class": len(CLASSES),
            "class_weight": "balanced",
            "n_estimators": 120,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "random_state": self.seed,
            "n_jobs": 2,
            "verbose": -1
        }
        self.model = lgb.LGBMClassifier(**params)
        self.model.fit(X_train, y_train)

        # Predict probabilities and classes
        probs_test = self.model.predict_proba(X_test)
        preds_test = np.argmax(probs_test, axis=1)

        # Metrics
        report = classification_report(
            y_test, preds_test, labels=list(range(len(CLASSES))), target_names=CLASSES, output_dict=True, zero_division=0
        )
        conf_mat = confusion_matrix(y_test, preds_test, labels=list(range(len(CLASSES)))).tolist()
        macro_f1 = float(f1_score(y_test, preds_test, average="macro", zero_division=0))

        # Check Decoy False-Positive Rate on test set
        decoy_mask = df_test["is_decoy"].values
        if decoy_mask.sum() > 0:
            decoy_preds = preds_test[decoy_mask]
            # Flagged as waste if pred != 0 ('normal')
            decoy_fp_count = int((decoy_preds != 0).sum())
            decoy_fp_rate = float(decoy_fp_count / len(decoy_preds))
        else:
            decoy_fp_rate = 0.0
            decoy_fp_count = 0

        # Check Server room False-Positive Rate (control room, must be 0)
        server_mask = (df_test["room"] == "eng-server").values
        if server_mask.sum() > 0:
            server_preds = preds_test[server_mask]
            server_fp_count = int((server_preds != 0).sum())
            server_fp_rate = float(server_fp_count / len(server_preds))
        else:
            server_fp_rate = 0.0
            server_fp_count = 0

        # Calibration: multiclass Brier score
        # Brier score = 1/N * sum((p_ij - y_ij)^2) across all classes
        num_classes = len(CLASSES)
        y_test_onehot = np.zeros((len(y_test), num_classes), dtype=np.float32)
        for i, val in enumerate(y_test):
            if val < num_classes:
                y_test_onehot[i, val] = 1.0
        
        # Expand probs_test to num_classes if fewer classes were in train
        if probs_test.shape[1] < num_classes:
            full_probs = np.zeros((len(y_test), num_classes), dtype=np.float32)
            for local_idx, c_idx in enumerate(self.model.classes_):
                full_probs[:, c_idx] = probs_test[:, local_idx]
            probs_test = full_probs

        brier_score = float(np.mean(np.sum((probs_test - y_test_onehot) ** 2, axis=1)))

        self.metadata = {
            "model_name": "waste_classifier_m2",
            "model_type": "LightGBM Multiclass Classifier (Balanced Weights)",
            "created_utc": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "seed": self.seed,
            "classes": CLASSES,
            "features": M2_CLASSIFIER_FEATURES,
            "decision_threshold": 0.50,
            "metrics": {
                "macro_f1": round(macro_f1, 3),
                "brier_score": round(brier_score, 4),
                "decoy_false_positive_rate": round(decoy_fp_rate * 100.0, 2),
                "decoy_total_intervals": int(decoy_mask.sum()),
                "server_room_fp_rate": round(server_fp_rate * 100.0, 2),
                "server_room_total_intervals": int(server_mask.sum()),
                "per_class_metrics": {c: {
                    "precision": round(report[c]["precision"], 3),
                    "recall": round(report[c]["recall"], 3),
                    "f1": round(report[c]["f1-score"], 3),
                    "support": int(report[c]["support"])
                } for c in CLASSES if c in report},
                "confusion_matrix": conf_mat
            },
            "assumptions": [
                "Decoys are treated as ground-truth normal/non-waste",
                "Target threshold of 0.50 used for multiclass decision argmax",
                "Server room control baseline contains zero legitimate anomalies",
                "Trained on synthetic data; validates pattern-recognition taxonomy"
            ]
        }

        os.makedirs("ml/artifacts", exist_ok=True)
        joblib.dump(self.model, "ml/artifacts/m2_classifier.joblib")
        with open("ml/artifacts/m2_classifier_metadata.json", "w") as f:
            json.dump(self.metadata, f, indent=2)

        return self.metadata


class AnomalyDetectorTrainer:
    def __init__(self, contamination: float = 0.05, seed: int = 42):
        self.contamination = contamination
        self.seed = seed
        self.model = None
        self.metadata: dict[str, Any] = {}

    def train(
        self,
        baseline_model_path: str = "ml/artifacts/m1_baseline.joblib",
        slice_days: int | None = None,
        resolution_mins: int = 15
    ) -> dict[str, Any]:
        """
        Trains M3: Isolation Forest unsupervised fallback anomaly detector.
        Trained strictly on normal intervals.
        """
        logger.info("Training M3: Isolation Forest Anomaly Detector...")
        loader = DataLoader()
        df_all = loader.load_telemetry_with_weather(slice_days=slice_days, resolution_mins=resolution_mins)
        df_gt = loader.load_ground_truth_labels()

        m1_model = joblib.load(baseline_model_path)
        with open("ml/artifacts/m1_baseline_metadata.json") as f:
            m1_meta = json.load(f)
        band_q_hat = float(m1_meta.get("conformal_q_hat_kw", 0.50))

        X_base = FeatureBuilder.build_baseline_features(df_all)
        base_pred_kw = m1_model.predict(X_base)

        # Mark anomaly intervals
        is_anom = np.zeros(len(df_all), dtype=bool)
        for _, row in df_gt.iterrows():
            if not row["is_legitimate_decoy"]:
                mask = (df_all["ac_unit_id"] == row["ac_unit_id"]) & \
                       (df_all["dt"] >= row["start_time"]) & \
                       (df_all["dt"] < row["end_time"])
                is_anom |= mask.values

        df_all["is_anomaly"] = is_anom
        X_feats = FeatureBuilder.build_classifier_features(df_all, base_pred_kw, band_q_hat)

        df_train, _df_cal, df_test = loader.time_split(pd.concat([df_all[["dt", "is_anomaly"]], X_feats], axis=1))

        # Train on clean normal intervals
        train_clean = df_train[~df_train["is_anomaly"]]
        X_train = train_clean[M2_CLASSIFIER_FEATURES]

        # Thin laptop thermal protection: cap n_estimators to 60 and max_samples to 1000
        self.model = IsolationForest(
            n_estimators=60,
            max_samples=min(1000, len(X_train)),
            contamination=self.contamination,
            random_state=self.seed,
            n_jobs=2
        )
        self.model.fit(X_train)

        # Evaluate on test set (detection rate on waste vs FPR on normal)
        X_test = df_test[M2_CLASSIFIER_FEATURES]
        y_test_is_anom = df_test["is_anomaly"].values

        # Isolation forest: -1 is anomaly, 1 is normal
        raw_preds = self.model.predict(X_test)
        pred_is_anom = (raw_preds == -1)

        # Detection rate (recall on waste)
        waste_total = y_test_is_anom.sum()
        detection_rate = float((pred_is_anom & y_test_is_anom).sum() / max(1, waste_total))

        # False positive rate on normal intervals
        normal_total = (~y_test_is_anom).sum()
        fpr = float((pred_is_anom & (~y_test_is_anom)).sum() / max(1, normal_total))

        self.metadata = {
            "model_name": "anomaly_detector_m3",
            "model_type": "Isolation Forest (Unsupervised Fallback)",
            "contamination": self.contamination,
            "seed": self.seed,
            "metrics": {
                "detection_rate_on_waste_pct": round(detection_rate * 100.0, 2),
                "false_positive_rate_pct": round(fpr * 100.0, 2),
                "waste_intervals_in_test": int(waste_total),
                "normal_intervals_in_test": int(normal_total)
            },
            "comparison_with_m2": (
                "M2 (Supervised LightGBM) is the primary detector because it classifies the specific "
                "waste taxonomy and distinguishes legitimate authorized decoys from waste. M3 serves as an "
                "unsupervised fallback for unmodeled fault modes."
            )
        }

        joblib.dump(self.model, "ml/artifacts/m3_anomaly_detector.joblib")
        with open("ml/artifacts/m3_anomaly_metadata.json", "w") as f:
            json.dump(self.metadata, f, indent=2)

        return self.metadata
