"""
Evaluates a YOLO model on the held-out classroom test set.
Computes:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- Share of images within +-1
- Share of images within +-10%
- Mean Signed Error (Bias)
- Breakdown by headcount bucket (1-10, 11-25, 26-50, 51+)
- Latency per frame (median and p95 ms) with 2 threads
Outputs Markdown table and summary metrics.
"""
import json
import os
import time

import numpy as np
import torch
from ultralytics import YOLO

# Enforce hardware safety thread limit (Hard Rule 3)
torch.set_num_threads(2)
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

def evaluate_model(model_path, is_coco=False, conf_thresh=0.25, iou_thresh=0.5, imgsz=384):
    print("\n=======================================================")
    print(f"Evaluating model: {model_path} (is_coco={is_coco})")
    print(f"Hardware config: CPU only, 2 threads, imgsz={imgsz}, conf={conf_thresh}")
    print("=======================================================")

    with open("cv/data/test_ground_truth.json", "r") as f:
        test_samples = json.load(f)

    print(f"Loaded {len(test_samples)} held-out classroom test images.")

    model = YOLO(model_path)

    results = []
    latencies_ms = []

    for idx, sample in enumerate(test_samples):
        img_path = os.path.join("cv/data/classroom_yolo/images/test", sample["image_file"])
        gt_count = sample["ground_truth_count"]

        t0 = time.perf_counter()
        # If COCO model, class 0 is 'person'. If fine-tuned head model, class 0 is 'head'.
        preds = model.predict(
            source=img_path,
            classes=[0],
            conf=conf_thresh,
            iou=iou_thresh,
            imgsz=imgsz,
            device="cpu",
            verbose=False
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

        det_boxes = preds[0].boxes
        det_count = len(det_boxes) if det_boxes is not None else 0

        # Cap count at 1.2x typical room max if needed (Rule B3)
        # Record item
        error = det_count - gt_count
        abs_error = abs(error)
        pct_error = abs_error / max(1, gt_count)

        # Bucket
        if gt_count <= 10:
            bucket = "1-10"
        elif gt_count <= 25:
            bucket = "11-25"
        elif gt_count <= 50:
            bucket = "26-50"
        else:
            bucket = "51+"

        results.append({
            "image": sample["image_file"],
            "gt": gt_count,
            "det": det_count,
            "err": error,
            "abs_err": abs_error,
            "pct_err": pct_error,
            "within_1": abs_error <= 1,
            "within_10pct": pct_error <= 0.10,
            "bucket": bucket
        })

    # Overall metrics
    all_abs_errors = [r["abs_err"] for r in results]
    all_sq_errors = [r["err"] ** 2 for r in results]
    all_signed_errors = [r["err"] for r in results]

    mae = float(np.mean(all_abs_errors))
    rmse = float(np.sqrt(np.mean(all_sq_errors)))
    bias = float(np.mean(all_signed_errors))
    share_within_1 = float(np.mean([r["within_1"] for r in results]) * 100.0)
    share_within_10pct = float(np.mean([r["within_10pct"] for r in results]) * 100.0)

    median_lat = float(np.median(latencies_ms))
    p95_lat = float(np.percentile(latencies_ms, 95))

    # Bucket metrics
    bucket_names = ["1-10", "11-25", "26-50", "51+"]
    bucket_stats = {}
    for b in bucket_names:
        b_res = [r for r in results if r["bucket"] == b]
        if b_res:
            b_mae = float(np.mean([r["abs_err"] for r in b_res]))
            b_rmse = float(np.sqrt(np.mean([r["err"]**2 for r in b_res])))
            b_bias = float(np.mean([r["err"] for r in b_res]))
            b_w1 = float(np.mean([r["within_1"] for r in b_res]) * 100.0)
            b_w10 = float(np.mean([r["within_10pct"] for r in b_res]) * 100.0)
            bucket_stats[b] = {
                "count": len(b_res),
                "mae": b_mae,
                "rmse": b_rmse,
                "bias": b_bias,
                "within_1": b_w1,
                "within_10pct": b_w10
            }

    print("\n--- Summary Evaluation Results ---")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"Bias (Mean Signed Error): {bias:+.2f}")
    print(f"Share within +-1 student: {share_within_1:.1f}%")
    print(f"Share within +-10%: {share_within_10pct:.1f}%")
    print(f"Latency per frame: Median {median_lat:.1f}ms, p95 {p95_lat:.1f}ms")

    return {
        "model_path": model_path,
        "is_coco": is_coco,
        "num_test_images": len(results),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "share_within_1": share_within_1,
        "share_within_10pct": share_within_10pct,
        "median_lat_ms": median_lat,
        "p95_lat_ms": p95_lat,
        "bucket_stats": bucket_stats
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("model_file", nargs="?", default="yolov8n.pt")
    parser.add_argument("out_file", nargs="?", default=None)
    parser.add_argument("--coco", action="store_true")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--imgsz", type=int, default=384)
    args = parser.parse_args()

    is_coco_flag = args.coco or args.model_file == "yolov8n.pt"
    eval_stats = evaluate_model(
        args.model_file,
        is_coco=is_coco_flag,
        conf_thresh=args.conf,
        iou_thresh=args.iou,
        imgsz=args.imgsz
    )

    if args.out_file:
        with open(args.out_file, "w") as f:
            json.dump(eval_stats, f, indent=2)

