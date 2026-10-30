"""
Evaluation CLI and latency benchmark for trained ML models.
Measures single-unit and 28-unit batch inference latencies against < 200ms target.
"""
import glob
import json
import logging
import os
import time
from datetime import UTC, datetime

import pandas as pd

from ml.inference import BaselineInference
from ml.safety import watchdog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ml.eval")


def run_evaluation():
    watchdog.apply_process_limits()
    logger.info("=== Running Model Evaluation & Latency Benchmarks ===")

    # 1. Benchmark M1 Baseline Latency
    b_inf = BaselineInference()
    
    # Single-unit prediction benchmark (100 repetitions)
    now = datetime.now(UTC)
    feats = {
        "scheduled_hours": True,
        "outdoor_temp_c": 36.5,
        "set_temp_c": 24.0,
        "room_type": "lecture_hall",
        "capacity": 50,
        "area_sqm": 100.0,
        "rated_kw": 10.5
    }

    # Warmup
    for _ in range(5):
        b_inf.predict("eng-101", now, feats)

    t0 = time.perf_counter()
    n_single = 100
    for _ in range(n_single):
        b_inf.predict("eng-101", now, feats)
    single_ms = ((time.perf_counter() - t0) / n_single) * 1000.0

    # 28-unit batch benchmark
    batch_rows = []
    for i in range(28):
        batch_rows.append({
            "hour": now.hour,
            "minute_of_day": now.hour * 60 + now.minute,
            "weekday": now.weekday(),
            "is_weekend": int(now.weekday() >= 5),
            "is_holiday": 0,
            "scheduled_hours": 1,
            "outdoor_temp_c": 36.5,
            "temp_lag_1h": 35.0,
            "temp_lag_3h": 33.0,
            "temp_lag_6h": 30.0,
            "relative_humidity": 45.0,
            "set_temp_c": 24.0,
            "expected_headcount": 35.0,
            "room_type": "lecture_hall",
            "capacity": 50.0,
            "area_sqm": 100.0,
            "rated_kw": 10.5,
            "ac_unit_id": f"ac-unit-{i:02d}"
        })
    df_batch = pd.DataFrame(batch_rows)
    for c in ["room_type", "ac_unit_id"]:
        df_batch[c] = df_batch[c].astype("category")

    t0 = time.perf_counter()
    n_batch = 50
    for _ in range(n_batch):
        b_inf.predict_batch(df_batch)
    batch_ms = ((time.perf_counter() - t0) / n_batch) * 1000.0

    print("\n" + "=" * 60)
    print("INFERENCE LATENCY BENCHMARK (Target: < 200 ms)")
    print(f"Single Unit-Day Prediction: {single_ms:6.2f} ms")
    print(f"28-Unit Batch Prediction:   {batch_ms:6.2f} ms")
    print(f"Status:                     {'PASS' if batch_ms < 200.0 else 'FAIL'}")
    print("=" * 60 + "\n")

    # 2. Check metadata summaries
    meta_files = sorted(glob.glob("ml/artifacts/*_metadata.json"))
    print("TRAINED MODEL METADATA SUMMARY:")
    for mf in meta_files:
        with open(mf) as f:
            data = json.load(f)
            m_name = data.get("model_name", os.path.basename(mf))
            print(f"\n[{m_name}] - File: {mf}")
            print(f"  Type:    {data.get('model_type', 'N/A')}")
            print(f"  Metrics: {json.dumps(data.get('metrics', {}), indent=4)}")


if __name__ == "__main__":
    run_evaluation()
