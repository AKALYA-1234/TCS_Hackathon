"""
Evaluation script for Phase 2: Real COCO Evaluation.
Measures:
- Per bucket (1-2, 3-5, 6-10, 11+) and overall:
  - MAE of headcount
  - RMSE of headcount
  - Share within +-1 of ground truth
  - Mean signed error (bias)
  - Precision and Recall of detection boxes at IoU 0.5
  - Latency (median and p95 ms) and FPS
- Saves 6 annotated sample images to .claude/cv/samples/ with privacy blur
- Adheres to hardware safety rules: nice 10, max 2 threads, 30s cooldown
"""
import json
import os
import time

import cv2
import numpy as np

from cv.detector import YOLOv8ONNXDetector
from ml.safety import HardwareSafetyWatchdog


def compute_iou(box1, box2):
    """
    box1: [x1, y1, x2, y2]
    box2: [x1, y1, x2, y2]
    """
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    boxBArea = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    denom = boxAArea + boxBArea - interArea
    if denom <= 0:
        return 0.0
    return interArea / denom


def evaluate():
    os.nice(10)
    watchdog = HardwareSafetyWatchdog()

    print("Initializing YOLOv8n ONNX Detector (conf=0.35, nms_iou=0.5, threads=2)...")
    detector = YOLOv8ONNXDetector(conf_threshold=0.35, nms_iou=0.50, num_threads=2)

    with open("cv/eval_data/sampled_eval_manifest.json") as f:
        manifest = json.load(f)

    img_dir = "cv/eval_data/images"
    os.makedirs(".claude/cv/samples", exist_ok=True)

    bucket_stats = {
        "1-2": {"gt": [], "pred": [], "latencies": [], "tp": 0, "fp": 0, "fn": 0},
        "3-5": {"gt": [], "pred": [], "latencies": [], "tp": 0, "fp": 0, "fn": 0},
        "6-10": {"gt": [], "pred": [], "latencies": [], "tp": 0, "fp": 0, "fn": 0},
        "11+": {"gt": [], "pred": [], "latencies": [], "tp": 0, "fp": 0, "fn": 0},
    }

    saved_samples_count = 0

    print(f"Starting evaluation across {len(manifest)} images...")
    for idx, item in enumerate(manifest):
        # Thermal check
        curr_temp = watchdog.get_current_temp()
        if curr_temp >= 85.0:
            print(f"Warning: Thermal watchdog triggered at {curr_temp}°C! Cooling...")
            time.sleep(15)

        img_path = os.path.join(img_dir, item["file_name"])
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        h, w = frame.shape[:2]
        t0 = time.perf_counter()
        preds = detector.detect(frame)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        pred_count = len(preds)
        gt_count = item["ground_truth_count"]
        b_name = item["bucket"]

        bucket_stats[b_name]["gt"].append(gt_count)
        bucket_stats[b_name]["pred"].append(pred_count)
        bucket_stats[b_name]["latencies"].append(elapsed_ms)

        # Box matching at IoU 0.5
        # COCO bbox: [x, y, width, height] -> convert to [x1, y1, x2, y2]
        gt_boxes = []
        for b in item["ground_truth_boxes"]:
            gt_boxes.append([b[0], b[1], b[0] + b[2], b[1] + b[3]])

        pred_boxes = [[p.x1, p.y1, p.x2, p.y2] for p in preds]

        matched_gt = set()
        matched_pred = set()

        for p_idx, p_box in enumerate(pred_boxes):
            best_iou = 0.0
            best_gt = -1
            for g_idx, g_box in enumerate(gt_boxes):
                if g_idx in matched_gt:
                    continue
                iou = compute_iou(p_box, g_box)
                if iou > best_iou:
                    best_iou = iou
                    best_gt = g_idx
            if best_iou >= 0.5 and best_gt >= 0:
                matched_gt.add(best_gt)
                matched_pred.add(p_idx)

        tp = len(matched_pred)
        fp = len(pred_boxes) - tp
        fn = len(gt_boxes) - len(matched_gt)

        bucket_stats[b_name]["tp"] += tp
        bucket_stats[b_name]["fp"] += fp
        bucket_stats[b_name]["fn"] += fn

        # Save up to 6 annotated samples with privacy blur
        if saved_samples_count < 6:
            vis_frame = frame.copy()
            for p in preds:
                # Privacy blur on head/upper box region
                bx1, by1 = max(0, int(p.x1)), max(0, int(p.y1))
                bx2, by2 = min(w, int(p.x2)), min(h, int(p.y2))
                head_h = max(5, int((by2 - by1) * 0.35))
                head_roi = vis_frame[by1:min(h, by1 + head_h), bx1:bx2]
                if head_roi.shape[0] > 2 and head_roi.shape[1] > 2:
                    ksize = (max(15, (head_roi.shape[1] // 5) * 2 + 1), max(15, (head_roi.shape[0] // 5) * 2 + 1))
                    vis_frame[by1:min(h, by1 + head_h), bx1:bx2] = cv2.GaussianBlur(head_roi, ksize, 30)

                # Anonymous box
                cv2.rectangle(vis_frame, (bx1, by1), (bx2, by2), (0, 255, 120), 2)
                cv2.putText(
                    vis_frame,
                    f"person {p.conf:.2f}",
                    (bx1, max(15, by1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 120),
                    1,
                    cv2.LINE_AA
                )

            # Watermark
            cv2.putText(
                vis_frame,
                f"SIMULATED EVAL - PRED: {pred_count} | GT: {gt_count} | PRIVACY BLUR ACTIVE",
                (15, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 200, 255),
                2,
                cv2.LINE_AA
            )
            out_sample_path = f".claude/cv/samples/eval_sample_{saved_samples_count + 1}.jpg"
            cv2.imwrite(out_sample_path, vis_frame)
            saved_samples_count += 1

        if (idx + 1) % 25 == 0:
            print(f"Evaluated {idx + 1}/{len(manifest)} images...")

    # Aggregation & metrics computation
    all_gt = []
    all_pred = []
    all_latencies = []
    total_tp, total_fp, total_fn = 0, 0, 0

    results = {}
    for b_name, data in bucket_stats.items():
        gts = np.array(data["gt"])
        preds = np.array(data["pred"])
        lats = np.array(data["latencies"])

        all_gt.extend(data["gt"])
        all_pred.extend(data["pred"])
        all_latencies.extend(data["latencies"])
        total_tp += data["tp"]
        total_fp += data["fp"]
        total_fn += data["fn"]

        errors = preds - gts
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        within_1 = float(np.mean(np.abs(errors) <= 1) * 100.0)
        bias = float(np.mean(errors))
        prec = float(data["tp"] / (data["tp"] + data["fp"])) if (data["tp"] + data["fp"]) > 0 else 0.0
        rec = float(data["tp"] / (data["tp"] + data["fn"])) if (data["tp"] + data["fn"]) > 0 else 0.0

        results[b_name] = {
            "count": len(gts),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "within_1_pct": round(within_1, 1),
            "bias": round(bias, 2),
            "precision": round(prec * 100, 1),
            "recall": round(rec * 100, 1),
            "median_ms": round(float(np.median(lats)), 1),
            "p95_ms": round(float(np.percentile(lats, 95)), 1),
        }

    all_errors = np.array(all_pred) - np.array(all_gt)
    all_lats = np.array(all_latencies)
    results["Overall"] = {
        "count": len(all_gt),
        "mae": round(float(np.mean(np.abs(all_errors))), 2),
        "rmse": round(float(np.sqrt(np.mean(all_errors ** 2))), 2),
        "within_1_pct": round(float(np.mean(np.abs(all_errors) <= 1) * 100.0), 1),
        "bias": round(float(np.mean(all_errors)), 2),
        "precision": round(float(total_tp / (total_tp + total_fp) * 100), 1) if (total_tp + total_fp) > 0 else 0.0,
        "recall": round(float(total_tp / (total_tp + total_fn) * 100), 1) if (total_tp + total_fn) > 0 else 0.0,
        "median_ms": round(float(np.median(all_lats)), 1),
        "p95_ms": round(float(np.percentile(all_lats, 95)), 1),
        "fps": round(1000.0 / float(np.median(all_lats)), 1),
    }

    with open(".claude/cv/coco_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n--- COCO EVALUATION SUMMARY ---")
    print(json.dumps(results, indent=2))
    print("\nSaved 6 samples to .claude/cv/samples/")

    # 30s cooldown as specified in hardware safety
    print("Executing 30s hardware safety cooldown...")
    time.sleep(30)
    print("Evaluation complete.")


if __name__ == "__main__":
    evaluate()
