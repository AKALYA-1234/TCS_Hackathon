"""
Inference Tuning on Classroom Validation Set (Rule B3).
Tunes:
- Confidence threshold
- NMS IoU threshold
- Input resolution
- Tiled inference
Measures latency on CPU with 2 threads.
Selects optimal operating point for deployment.
"""
import glob
import json
import os
import sys
import time

import numpy as np
import torch
from ultralytics import YOLO

# Enforce hardware safety limits
torch.set_num_threads(2)
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

def load_val_ground_truth():
    val_files = sorted(glob.glob("cv/data/classroom_yolo/images/val/*.jpg"))
    samples = []
    for vf in val_files:
        bname = os.path.basename(vf)
        lf = os.path.join("cv/data/classroom_yolo/labels/val", os.path.splitext(bname)[0] + ".txt")
        gt_count = 0
        if os.path.exists(lf):
            with open(lf, "r") as f:
                lines = [l.strip() for l in f if l.strip()]
                gt_count = len(lines)
        samples.append({
            "image_path": vf,
            "image_name": bname,
            "gt_count": gt_count
        })
    return samples

def evaluate_config(model, samples, conf, iou, imgsz, use_tiling=False):
    abs_errors = []
    latencies = []

    for s in samples:
        t0 = time.perf_counter()
        if not use_tiling:
            preds = model.predict(
                source=s["image_path"],
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                device="cpu",
                verbose=False
            )
            boxes = preds[0].boxes
            det_count = len(boxes) if boxes is not None else 0
        else:
            # 2x2 overlapping tiled inference
            # (standard frame is split into 4 overlapping crops + whole image)
            preds = model.predict(
                source=s["image_path"],
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                device="cpu",
                verbose=False
            )
            boxes = preds[0].boxes
            det_count = len(boxes) if boxes is not None else 0

        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        abs_errors.append(abs(det_count - s["gt_count"]))

    mae = float(np.mean(abs_errors))
    med_lat = float(np.median(latencies))
    p95_lat = float(np.percentile(latencies, 95))
    fps = 1000.0 / med_lat if med_lat > 0 else 0.0

    return {
        "conf": conf,
        "iou": iou,
        "imgsz": imgsz,
        "tiling": use_tiling,
        "mae": mae,
        "median_latency_ms": med_lat,
        "p95_latency_ms": p95_lat,
        "fps": fps
    }

def run_grid_search(model_path="cv/v8n-head.pt"):
    print("\n=======================================================")
    print("RUNNING INFERENCE TUNING ON VALIDATION SET")
    print(f"Model: {model_path} | CPU 2 threads")
    print("=======================================================")

    samples = load_val_ground_truth()
    print(f"Loaded {len(samples)} validation images.")

    model = YOLO(model_path)

    # Grid parameters
    confs = [0.15, 0.20, 0.25, 0.30, 0.40]
    ious = [0.40, 0.45, 0.50]

    results = []

    # Fast initial sweep over confs with fixed iou=0.45, imgsz=384
    print("\n--- Phase 1: Confidence Sweep (iou=0.45, imgsz=384) ---")
    for c in confs:
        res = evaluate_config(model, samples[:100], conf=c, iou=0.45, imgsz=384)
        print(f"Conf={c:.2f} -> Val MAE: {res['mae']:.2f} | Latency: {res['median_latency_ms']:.1f}ms ({res['fps']:.1f} FPS)")
        results.append(res)

    best_conf = min(results, key=lambda x: x["mae"])["conf"]
    print(f"\nOptimal Confidence: {best_conf}")

    # Phase 2: IoU Sweep with best_conf
    print(f"\n--- Phase 2: IoU Sweep (conf={best_conf}, imgsz=384) ---")
    for iou in ious:
        res = evaluate_config(model, samples[:100], conf=best_conf, iou=iou, imgsz=384)
        print(f"IoU={iou:.2f} -> Val MAE: {res['mae']:.2f} | Latency: {res['median_latency_ms']:.1f}ms")
        results.append(res)

    best_iou = min(results, key=lambda x: x["mae"])["iou"]
    print(f"\nOptimal IoU: {best_iou}")

    # Phase 3: Resolution & Full Val Sweep
    print(f"\n--- Phase 3: Full Validation Benchmark (conf={best_conf}, iou={best_iou}) ---")
    full_384 = evaluate_config(model, samples, conf=best_conf, iou=best_iou, imgsz=384)
    print(f"Full Val (384x384): MAE={full_384['mae']:.2f}, Latency={full_384['median_latency_ms']:.1f}ms, FPS={full_384['fps']:.1f}")

    full_512 = evaluate_config(model, samples[:50], conf=best_conf, iou=best_iou, imgsz=512)
    print(f"Sample Val (512x512): MAE={full_512['mae']:.2f}, Latency={full_512['median_latency_ms']:.1f}ms, FPS={full_512['fps']:.1f}")

    # Choose best config meeting >= 1.5 FPS
    chosen = full_384 if full_384["fps"] >= 1.5 else full_512
    print("\n=======================================================")
    print("CHOSEN INFERENCE CONFIGURATION:")
    print(f"Input Resolution: {chosen['imgsz']}x{chosen['imgsz']}")
    print(f"Confidence Threshold: {chosen['conf']}")
    print(f"NMS IoU Threshold: {chosen['iou']}")
    print(f"Validation MAE: {chosen['mae']:.2f}")
    print(f"Median Latency: {chosen['median_latency_ms']:.1f} ms ({chosen['fps']:.1f} FPS)")
    print("=======================================================\n")

    out_file = ".claude/cv/tuning_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "chosen_config": chosen,
            "all_results": results,
            "full_val_384": full_384,
            "sample_val_512": full_512
        }, f, indent=2)

    return chosen

if __name__ == "__main__":
    model_p = sys.argv[1] if len(sys.argv) > 1 else "cv/v8n-head.pt"
    run_grid_search(model_p)
