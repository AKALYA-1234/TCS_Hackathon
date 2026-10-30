"""
Person detector implementations for AC headcount computer-vision module.
Common interface: detect(frame) -> list[Box(x1, y1, x2, y2, conf)]
Strictly class 'person' (COCO class 0). Privacy-first: no identity, no biometrics.
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    label: str = "person"


class BaseDetector:
    def detect(self, frame: np.ndarray) -> list[Box]:
        raise NotImplementedError


class YOLOv8ONNXDetector(BaseDetector):
    """
    YOLOv8n detector executed via ONNXRuntime on CPU.
    License: AGPL-3.0 (Ultralytics weights converted to ONNX).
    Restricted to 2 CPU threads, input resolution 640x640.
    """

    def __init__(
        self,
        weights_path: str = "cv/weights/yolov8n.onnx",
        conf_threshold: float = 0.35,
        nms_iou: float = 0.50,
        imgsz: int = 640,
        num_threads: int = 2
    ):
        import onnxruntime as ort

        self.conf_threshold = conf_threshold
        self.nms_iou = nms_iou
        self.imgsz = imgsz
        self.weights_path = weights_path
        self.model_name = "YOLOv8n-ONNX"
        self.model_version = "8.4.193"
        self.license = "AGPL-3.0 (fine for internal prototype; legal review before commercialization)"

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = num_threads
        opts.inter_op_num_threads = num_threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            weights_path,
            sess_options=opts,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def preprocess(self, img: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Letterbox resize to imgszximgsz keeping aspect ratio."""
        h, w = img.shape[:2]
        r = min(self.imgsz / h, self.imgsz / w)
        new_unpad = (round(w * r), round(h * r))
        dw, dh = self.imgsz - new_unpad[0], self.imgsz - new_unpad[1]
        dw, dh = dw / 2, dh / 2

        if (w, h) != new_unpad:
            img_resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        else:
            img_resized = img

        top, bottom = round(dh - 0.1), round(dh + 0.1)
        left, right = round(dw - 0.1), round(dw + 0.1)
        img_padded = cv2.copyMakeBorder(
            img_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )

        # Convert HWC BGR to CHW RGB normalized [0, 1]
        blob = cv2.cvtColor(img_padded, cv2.COLOR_BGR2RGB)
        blob = blob.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return blob, r, (dw, dh)

    def detect(self, frame: np.ndarray) -> list[Box]:
        h_orig, w_orig = frame.shape[:2]
        blob, ratio, (pad_w, pad_h) = self.preprocess(frame)

        # Inference
        outputs = self.session.run([self.output_name], {self.input_name: blob})[0]
        # Output shape: [1, 84, 8400] -> transpose to [8400, 84]
        preds = outputs[0].transpose(1, 0)

        boxes_list = []
        confidences = []

        # YOLOv8 format: x_c, y_c, width, height, class0_prob, class1_prob...
        # Class 0 = person in COCO
        for i in range(preds.shape[0]):
            person_score = preds[i, 4]
            if person_score >= self.conf_threshold:
                xc, yc, bw, bh = preds[i, 0], preds[i, 1], preds[i, 2], preds[i, 3]
                # Adjust for padding and scale back to original image
                x1 = (xc - bw / 2.0 - pad_w) / ratio
                y1 = (yc - bh / 2.0 - pad_h) / ratio
                x2 = (xc + bw / 2.0 - pad_w) / ratio
                y2 = (yc + bh / 2.0 - pad_h) / ratio

                # Clip bounds
                x1 = max(0.0, min(float(w_orig), float(x1)))
                y1 = max(0.0, min(float(h_orig), float(y1)))
                x2 = max(0.0, min(float(w_orig), float(x2)))
                y2 = max(0.0, min(float(h_orig), float(y2)))

                if x2 > x1 and y2 > y1:
                    boxes_list.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])
                    confidences.append(float(person_score))

        if not boxes_list:
            return []

        # Non-Maximum Suppression
        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_list,
            scores=confidences,
            score_threshold=self.conf_threshold,
            nms_threshold=self.nms_iou
        )

        results: list[Box] = []
        if len(indices) > 0:
            for idx in indices.flatten():
                bx, by, bw, bh = boxes_list[idx]
                results.append(
                    Box(
                        x1=float(bx),
                        y1=float(by),
                        x2=float(bx + bw),
                        y2=float(by + bh),
                        conf=float(confidences[idx]),
                        label="person"
                    )
                )
        return results


class OpenCVHOGDetector(BaseDetector):
    """
    OpenCV standard Histogram of Oriented Gradients (HOG) people detector.
    Zero external weights (built into OpenCV). Permissive BSD license.
    Fallback detector if ONNX is unavailable.
    """

    def __init__(self, conf_threshold: float = 0.0):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.conf_threshold = conf_threshold
        self.model_name = "OpenCV-HOG"
        self.model_version = "OpenCV-" + cv2.__version__
        self.license = "Apache-2.0 / BSD (Permissive)"

    def detect(self, frame: np.ndarray) -> list[Box]:
        rects, weights = self.hog.detectMultiScale(
            frame,
            winStride=(4, 4),
            padding=(8, 8),
            scale=1.05
        )
        boxes = []
        for (x, y, w, h), score in zip(rects, weights):
            if score >= self.conf_threshold:
                boxes.append(
                    Box(
                        x1=float(x),
                        y1=float(y),
                        x2=float(x + w),
                        y2=float(y + h),
                        conf=float(min(1.0, max(0.1, (score + 1.0) / 2.0))),
                        label="person"
                    )
                )
        return boxes
