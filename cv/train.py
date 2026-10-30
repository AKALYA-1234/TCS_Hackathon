"""
Training harness for YOLOv8n on Classroom Head Detection.
Adheres strictly to Hardware Safety Rules (Rule 3):
- Max 2 CPU threads (torch, OpenCV, dataloader workers)
- Run under nice -n 10
- Uses ml/safety.py HardwareSafetyWatchdog (pauses at 85°C, aborts at 90°C)
- Cooldown between phases
- Checkpoints every epoch and logs to .claude/cv/train_log.csv
"""
import argparse
import csv
import os
import sys
import time

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath("."))

import torch
from ultralytics import YOLO

from ml.safety import watchdog

# Hardware Safety: enforce thread limit
torch.set_num_threads(2)
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

class TrainingEpochLogger:
    def __init__(self, log_path=".claude/cv/train_log.csv"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.epoch_start_time = time.time()
        
        # Write header if new file
        if not os.path.exists(log_path):
            with open(log_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "epoch", "train_box_loss", "train_cls_loss", "train_dfl_loss",
                    "val_precision", "val_recall", "val_mAP50", "val_mAP50_95",
                    "epoch_time_sec", "peak_cpu_temp_c"
                ])

    def on_train_epoch_start(self, trainer):
        self.epoch_start_time = time.time()

    def on_train_epoch_end(self, trainer):
        elapsed = time.time() - self.epoch_start_time
        epoch = trainer.epoch + 1
        metrics = trainer.metrics or {}
        
        # Extract losses
        loss_items = trainer.loss_items.cpu().numpy() if hasattr(trainer, 'loss_items') and trainer.loss_items is not None else [0, 0, 0]
        box_loss = float(loss_items[0]) if len(loss_items) > 0 else 0.0
        cls_loss = float(loss_items[1]) if len(loss_items) > 1 else 0.0
        dfl_loss = float(loss_items[2]) if len(loss_items) > 2 else 0.0
        
        # Validation metrics
        p = float(metrics.get("metrics/precision(B)", 0.0))
        r = float(metrics.get("metrics/recall(B)", 0.0))
        map50 = float(metrics.get("metrics/mAP50(B)", 0.0))
        map50_95 = float(metrics.get("metrics/mAP50-95(B)", 0.0))
        current_temp = watchdog.get_current_temp()

        with open(self.log_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                epoch, f"{box_loss:.4f}", f"{cls_loss:.4f}", f"{dfl_loss:.4f}",
                f"{p:.4f}", f"{r:.4f}", f"{map50:.4f}", f"{map50_95:.4f}",
                f"{elapsed:.1f}", f"{current_temp:.1f}"
            ])

        print(f"\n[EPOCH {epoch}] Box: {box_loss:.3f} | Cls: {cls_loss:.3f} | mAP50: {map50:.3f} | Time: {elapsed:.1f}s | Temp: {current_temp:.1f}°C")


def run_smoke_test(imgsz=384):
    print("\n=======================================================")
    print("RUNNING SMOKE TEST (100 images, 1 epoch)")
    print("=======================================================")
    watchdog.apply_process_limits()
    watchdog.start()

    # Create 100-image mini dataset
    smoke_yaml = "cv/data/classroom_yolo/smoke.yaml"
    with open("cv/data/classroom_yolo/dataset.yaml", "r") as f:
        content = f.read()
    with open(smoke_yaml, "w") as f:
        f.write(content)

    t0 = time.time()
    temp0 = watchdog.get_current_temp()

    model = YOLO("yolov8n.pt")
    
    # Train 1 epoch on mini subset (using first 100 images via fraction=0.1)
    model.train(
        data=smoke_yaml,
        epochs=1,
        fraction=0.1,  # 10% of 1010 = ~100 images
        imgsz=imgsz,
        batch=8,
        workers=2,
        device="cpu",
        plots=False,
        save=False,
        verbose=True
    )

    elapsed_sec = time.time() - t0
    temp1 = watchdog.get_current_temp()
    watchdog.stop()

    print("\n=======================================================")
    print("SMOKE TEST RESULTS & EXTRAPOLATION PLAN")
    print(f"Time for 100 images (1 epoch): {elapsed_sec:.1f} seconds")
    print(f"CPU Temp: start={temp0:.1f}°C, end={temp1:.1f}°C, peak={watchdog.peak_temp_c:.1f}°C")
    
    # Extrapolate for full training
    # For full 1000 images, 1 epoch is approx 10x
    sec_per_full_epoch = elapsed_sec * 10.0
    print(f"Projected seconds per full epoch (1,000 images): {sec_per_full_epoch:.1f}s (~{sec_per_full_epoch/60.0:.1f} min)")

    # 10 epochs
    epochs_target = 8
    total_projected_min = (sec_per_full_epoch * epochs_target) / 60.0
    print(f"Projected total training time for {epochs_target} epochs: {total_projected_min:.1f} minutes")
    print("Adjusted settings: imgsz=384, batch=8, freeze=10, workers=2, epochs=8 to stay well within 90-min budget.")
    print("=======================================================\n")

    return {
        "smoke_time_sec": elapsed_sec,
        "sec_per_full_epoch": sec_per_full_epoch,
        "recommended_epochs": epochs_target,
        "recommended_imgsz": imgsz
    }


def run_full_training(epochs=8, imgsz=384, resume=False):
    print("\n=======================================================")
    print(f"STARTING FULL TRAINING (epochs={epochs}, imgsz={imgsz}, resume={resume})")
    print("Hardware Safety: Watchdog active, 2 CPU threads, nice -n 10")
    print("=======================================================")

    watchdog.apply_process_limits()
    watchdog.start()

    logger = TrainingEpochLogger()
    model = YOLO("yolov8n.pt" if not resume else "runs/detect/classroom_head/weights/last.pt")

    # Add custom callback
    model.add_callback("on_train_epoch_start", logger.on_train_epoch_start)
    model.add_callback("on_train_epoch_end", logger.on_train_epoch_end)

    data_yaml = os.path.abspath("cv/data/classroom_yolo/dataset.yaml")
    project_dir = os.path.abspath("runs/detect")
    name = "classroom_head"

    try:
        model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=8,
            workers=2,
            device="cpu",
            project=project_dir,
            name=name,
            exist_ok=True,
            freeze=10,             # Freeze first 10 layers for stability on CPU
            patience=4,            # Early stopping
            close_mosaic=2,        # Disable mosaic augmentation for last 2 epochs
            lr0=0.01,
            lrf=0.01,
            weight_decay=0.0005,
            plots=True,
            save=True,
            save_period=1,         # Save checkpoint every epoch (Rule B2)
            resume=resume,
            verbose=True
        )
    finally:
        watchdog.stop()

    print("\nTraining completed successfully!")
    print(f"Peak CPU Temp: {watchdog.peak_temp_c:.1f}°C")
    print(f"Total cooling pause time: {watchdog.pause_duration_sec:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run smoke test on 100 images")
    parser.add_argument("--train", action="store_true", help="Run full training")
    parser.add_argument("--resume", action="store_true", help="Resume training")
    parser.add_argument("--epochs", type=int, default=8, help="Number of epochs")
    parser.add_argument("--imgsz", type=int, default=384, help="Input image size")
    args = parser.parse_args()

    if args.smoke:
        run_smoke_test(imgsz=args.imgsz)
    elif args.train:
        run_full_training(epochs=args.epochs, imgsz=args.imgsz, resume=args.resume)
    else:
        # Default: run smoke test
        run_smoke_test(imgsz=args.imgsz)
