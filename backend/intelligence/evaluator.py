"""
Evaluator: Evaluates the WasteClassifier against injected ground truth labels.
Calculates Precision, Recall, and F1-Score per anomaly type:
- after_hours, ghost_cooling, overcooling, early_start, possible_leakage
"""
from typing import List, Dict, Any
from sqlalchemy import select
from common.database import AsyncSessionLocal
from domain.ac_models import GroundTruthLabelModel, WasteEventModel


class ModelEvaluator:
    async def evaluate_metrics(self) -> Dict[str, Any]:
        """
        Queries ground_truth_labels and waste_events to compute precision and recall.
        """
        async with AsyncSessionLocal() as session:
            gt_res = await session.execute(select(GroundTruthLabelModel))
            ground_truths = list(gt_res.scalars().all())

            ev_res = await session.execute(select(WasteEventModel))
            detected_events = list(ev_res.scalars().all())

        anomaly_types = ["after_hours", "ghost_cooling", "overcooling", "early_start", "possible_leakage"]
        metrics_by_type = {}

        total_tp = 0
        total_fp = 0
        total_fn = 0

        for atype in anomaly_types:
            gts = [g for g in ground_truths if g.anomaly_type == atype]
            dets = [d for d in detected_events if d.event_type == atype]

            # True Positives: Detected events that match a ground truth room and overlap temporally
            tp = 0
            for d in dets:
                matched = any(
                    g.room_id == d.room_id and (
                        (g.start_time <= d.start_time <= g.end_time) or
                        (d.end_time and g.start_time <= d.end_time <= g.end_time)
                    )
                    for g in gts
                )
                if matched:
                    tp += 1

            fp = max(0, len(dets) - tp)
            fn = max(0, len(gts) - tp)

            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 1.0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else (1.0 if len(gts) == 0 else 0.0)
            f1 = round(2 * (precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0

            metrics_by_type[atype] = {
                "ground_truth_count": len(gts),
                "detected_count": len(dets),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "f1_score": f1
            }

            total_tp += tp
            total_fp += fp
            total_fn += fn

        overall_precision = round(total_tp / (total_tp + total_fp), 3) if (total_tp + total_fp) > 0 else 1.0
        overall_recall = round(total_tp / (total_tp + total_fn), 3) if (total_tp + total_fn) > 0 else 1.0
        overall_f1 = round(2 * (overall_precision * overall_recall) / (overall_precision + overall_recall), 3) if (overall_precision + overall_recall) > 0 else 0.0

        return {
            "overall": {
                "precision": overall_precision,
                "recall": overall_recall,
                "f1_score": overall_f1,
                "total_ground_truth": len(ground_truths),
                "total_detected": len(detected_events)
            },
            "by_type": metrics_by_type
        }
