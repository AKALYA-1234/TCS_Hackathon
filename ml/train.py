"""
CLI entrypoints for training, evaluating, and validating ML models.
Commands:
  python -m ml.train --model {baseline,classifier,anomaly,forecast,vision,all} --days {1,7,full}
  python -m ml.evaluate
"""
import argparse
import logging
import time

from ml.baseline import BaselineTrainer
from ml.classifier import AnomalyDetectorTrainer, WasteClassifierTrainer
from ml.forecaster import LoadForecasterTrainer
from ml.safety import watchdog
from ml.vision import CVHeadcountVerifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ml.cli")


def run_training():
    parser = argparse.ArgumentParser(description="AC Optimization ML Training CLI")
    parser.add_argument("--model", choices=["baseline", "classifier", "anomaly", "forecast", "vision", "all"], default="all")
    parser.add_argument("--days", choices=["1", "7", "full"], default="full")
    parser.add_argument("--allow-battery", action="store_true", help="Allow battery power for dry run")
    args = parser.parse_args()

    slice_days = 1 if args.days == "1" else (7 if args.days == "7" else None)
    
    # Enforce hardware safety guards
    watchdog.apply_process_limits()
    if slice_days is None:
        watchdog.check_battery_status(allow_battery=args.allow_battery)
    watchdog.start()

    logger.info(f"=== Starting Training Session (model={args.model}, days={args.days}) ===")
    logger.info(f"Initial CPU Temp: {watchdog.get_current_temp():.1f}°C, Available RAM: {watchdog.get_available_ram_gb():.1f} GB")

    start_total = time.time()
    timings = {}

    try:
        # 1. Baseline Model (M1)
        if args.model in ["baseline", "all"]:
            t0 = time.time()
            bt = BaselineTrainer(seed=42)
            meta_m1 = bt.train_synthetic(slice_days=slice_days)
            timings["m1_baseline_synthetic"] = time.time() - t0
            logger.info(f"M1 Synthetic training complete ({timings['m1_baseline_synthetic']:.1f}s). CV-RMSE: {meta_m1['metrics']['cv_rmse_pct']}%, NMBE: {meta_m1['metrics']['nmbe_pct']}%")

            # Train ASHRAE credibility baseline
            t_ashrae = time.time()
            bt.train_ashrae()
            timings["m1_baseline_ashrae"] = time.time() - t_ashrae
            logger.info(f"M1 ASHRAE training complete ({timings['m1_baseline_ashrae']:.1f}s).")
            watchdog.cooldown(seconds=20.0 if slice_days else 45.0, label="Cooldown after M1")

        # 2. Classifier Model (M2)
        if args.model in ["classifier", "all"]:
            t0 = time.time()
            ct = WasteClassifierTrainer(seed=42)
            meta_m2 = ct.train(slice_days=slice_days)
            timings["m2_classifier"] = time.time() - t0
            logger.info(f"M2 Classifier training complete ({timings['m2_classifier']:.1f}s). Macro-F1: {meta_m2['metrics']['macro_f1']}, Decoy FPR: {meta_m2['metrics']['decoy_false_positive_rate']}%")
            watchdog.cooldown(seconds=20.0 if slice_days else 45.0, label="Cooldown after M2")

        # 3. Anomaly Detector (M3)
        if args.model in ["anomaly", "all"]:
            t0 = time.time()
            adt = AnomalyDetectorTrainer(seed=42)
            meta_m3 = adt.train(slice_days=slice_days)
            timings["m3_anomaly"] = time.time() - t0
            logger.info(f"M3 Anomaly training complete ({timings['m3_anomaly']:.1f}s). Waste detection rate: {meta_m3['metrics']['detection_rate_on_waste_pct']}%")
            watchdog.cooldown(seconds=20.0 if slice_days else 45.0, label="Cooldown after M3")

        # 4. Load Forecaster (M4)
        if args.model in ["forecast", "all"]:
            t0 = time.time()
            ft = LoadForecasterTrainer(seed=42)
            ft.train(slice_days=slice_days)
            timings["m4_forecaster"] = time.time() - t0
            logger.info(f"M4 Forecaster training complete ({timings['m4_forecaster']:.1f}s).")
            watchdog.cooldown(seconds=20.0 if slice_days else 45.0, label="Cooldown after M4")

        # 5. Vision Verifier (M5)
        if args.model in ["vision", "all"]:
            t0 = time.time()
            vt = CVHeadcountVerifier()
            vt.verify()
            timings["m5_vision"] = time.time() - t0
            logger.info(f"M5 Vision verification complete ({timings['m5_vision']:.1f}s).")

        total_elapsed = time.time() - start_total
        print("\n" + "=" * 60)
        print("TRAINING RUN COMPLETE")
        print(f"Total Session Time: {total_elapsed:.1f}s")
        print(f"Peak CPU Temp:      {watchdog.peak_temp_c:.1f}°C")
        print(f"Peak Process RSS:   {watchdog.peak_rss_mb:.1f} MB")
        print(f"Thermal Pauses:     {watchdog.pause_duration_sec:.1f}s")
        print("Model Timings:")
        for m, t in timings.items():
            print(f"  - {m:25s}: {t:6.1f}s")
        print("=" * 60 + "\n")

    finally:
        watchdog.stop()


if __name__ == "__main__":
    run_training()
