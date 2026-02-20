"""
Chiqindilarni aniqlash va tasniflash moduli.
Waste detection and classification module.

Qo'llab-quvvatlanadigan backendlar:
  - ONNX Runtime (Raspberry Pi, ARM — torch kerak EMAS, "Illegal instruction" yo'q)
  - PyTorch/ultralytics (PC, kuchli qurilmalar)
"""

import os
import logging
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ai.config import (
    MODEL_NAME,
    MODEL_ONNX,
    MODEL_BACKEND,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    YOLO_TO_WASTE,
    WASTE_CATEGORIES,
    CIRCLE_DETECTION,
    CIRCLE_MIN_RADIUS,
    CIRCLE_MAX_RADIUS,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
)

logger = logging.getLogger(__name__)

# ─── Backend mavjudligini tekshirish ───
_ONNX_AVAILABLE = False
try:
    import onnxruntime as ort
    _ONNX_AVAILABLE = True
except ImportError:
    pass

_ULTRALYTICS_AVAILABLE = False
try:
    from ultralytics import YOLO
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    pass

# YOLOv8 COCO sinf nomlari (80 ta)
COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


@dataclass
class DetectionResult:
    """Bitta aniqlangan obyekt natijasi."""
    class_name: str
    waste_category: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    ecocoin_reward: int
    material: str
    name_uz: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def _detect_model_backend() -> str:
    """Qaysi backend ishlatishni avtomatik aniqlash."""
    if MODEL_BACKEND != "auto":
        return MODEL_BACKEND

    # ONNX model mavjud bo'lsa va onnxruntime o'rnatilgan bo'lsa — ONNX
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    onnx_path = os.path.join(base_dir, MODEL_ONNX)
    if _ONNX_AVAILABLE and os.path.exists(onnx_path):
        logger.info("ONNX model topildi — ONNX Runtime backend ishlatiladi")
        return "onnx"

    if _ULTRALYTICS_AVAILABLE:
        logger.info("ultralytics topildi — PyTorch backend ishlatiladi")
        return "pytorch"

    if _ONNX_AVAILABLE:
        logger.info("ONNX Runtime mavjud lekin .onnx model topilmadi")
        return "onnx"

    raise RuntimeError(
        "Hech qanday model backend topilmadi!\n"
        "RPi uchun: pip install onnxruntime\n"
        "PC uchun:  pip install ultralytics"
    )


class WasteClassifier:
    """
    Chiqindilarni aniqlash — ONNX Runtime yoki PyTorch/ultralytics.
    RPi da ONNX ishlatiladi (torch/ultralytics kerak emas → "Illegal instruction" yo'q).
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None          # ultralytics YOLO (PyTorch)
        self.onnx_session = None   # onnxruntime session (ONNX)
        self.is_loaded = False
        self.backend = _detect_model_backend()
        self.model_path = model_path

        if self.backend == "onnx":
            self._load_onnx()
        else:
            self._load_pytorch()

    # ─── PyTorch/ultralytics backend ───

    def _load_pytorch(self) -> None:
        """ultralytics YOLO modelini yuklash (PC uchun)."""
        if not _ULTRALYTICS_AVAILABLE:
            raise RuntimeError(
                "ultralytics kutubxonasi o'rnatilmagan.\n"
                "O'rnatish: pip install ultralytics\n"
                "RPi uchun ONNX ishlatishni ko'ring."
            )
        path = self.model_path or MODEL_NAME
        try:
            logger.info(f"PyTorch model yuklanmoqda: {path}")
            self.model = YOLO(path).to("cpu")
            self.is_loaded = True
            logger.info("PyTorch model yuklandi ✓")
        except Exception as e:
            logger.error(f"PyTorch model xatosi: {e}")
            raise

    # ─── ONNX Runtime backend ───

    def _load_onnx(self) -> None:
        """ONNX modelini yuklash (RPi uchun — torch kerak EMAS)."""
        if not _ONNX_AVAILABLE:
            raise RuntimeError(
                "onnxruntime o'rnatilmagan.\n"
                "O'rnatish: pip install onnxruntime"
            )

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = self.model_path or os.path.join(base_dir, MODEL_ONNX)

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"ONNX model topilmadi: {path}\n"
                "Eksport qilish uchun PC da quyidagini bajaring:\n"
                "  python export_onnx.py\n"
                "Keyin yolov8n.onnx faylini Raspberry Pi ga nusxalang."
            )

        try:
            logger.info(f"ONNX model yuklanmoqda: {path}")
            self.onnx_session = ort.InferenceSession(
                path, providers=["CPUExecutionProvider"]
            )
            self.is_loaded = True
            logger.info("ONNX model yuklandi ✓ (torch kerak emas!)")
        except Exception as e:
            logger.error(f"ONNX model xatosi: {e}")
            raise

    # ─── ONNX preprocessing / postprocessing ───

    def _preprocess_onnx(self, frame: np.ndarray) -> Tuple[np.ndarray, float, int, int]:
        """
        YOLOv8 ONNX uchun rasmni tayyorlash (letterbox resize + normalize).
        Returns: (input_tensor, ratio, pad_x, pad_y)
        """
        input_shape = self.onnx_session.get_inputs()[0].shape  # [1, 3, H, W]
        input_h, input_w = input_shape[2], input_shape[3]

        h, w = frame.shape[:2]
        ratio = min(input_w / w, input_h / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        pad_x = (input_w - new_w) // 2
        pad_y = (input_h - new_h) // 2

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((input_h, input_w, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # BGR → RGB, HWC → CHW, normalize 0-1
        blob = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)

        return blob, ratio, pad_x, pad_y

    def _postprocess_onnx(
        self, output: np.ndarray, ratio: float, pad_x: int, pad_y: int
    ) -> List[DetectionResult]:
        """
        ONNX chiqishini qayta ishlash — NMS + filtrlash.
        YOLOv8 output: [1, 84, 8400] → transpose → [8400, 84]
        """
        predictions = output[0].T  # [8400, 84]

        boxes = predictions[:, :4]       # cx, cy, w, h
        scores = predictions[:, 4:]      # 80 class scores

        max_scores = scores.max(axis=1)
        class_ids = scores.argmax(axis=1)

        mask = max_scores >= CONFIDENCE_THRESHOLD
        boxes = boxes[mask]
        max_scores = max_scores[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return []

        # cx,cy,w,h → x1,y1,x2,y2
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        # Letterbox padding olib tashlash
        x1 = (x1 - pad_x) / ratio
        y1 = (y1 - pad_y) / ratio
        x2 = (x2 - pad_x) / ratio
        y2 = (y2 - pad_y) / ratio

        # NMS
        boxes_for_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        indices = cv2.dnn.NMSBoxes(
            boxes_for_nms,
            max_scores.tolist(),
            CONFIDENCE_THRESHOLD,
            IOU_THRESHOLD,
        )

        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                class_id = int(class_ids[i])
                if class_id >= len(COCO_NAMES):
                    continue
                class_name = COCO_NAMES[class_id]
                waste_category = self._map_to_waste_category(class_name)

                if waste_category not in WASTE_CATEGORIES:
                    continue

                cat_info = WASTE_CATEGORIES[waste_category]
                detection = DetectionResult(
                    class_name=class_name,
                    waste_category=waste_category,
                    confidence=float(max_scores[i]),
                    bbox=(int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])),
                    ecocoin_reward=cat_info["ecocoin_reward"],
                    material=cat_info["material"],
                    name_uz=cat_info["name_uz"],
                )
                detections.append(detection)

        return detections

    # ─── Umumiy metodlar ───

    def _map_to_waste_category(self, class_name: str) -> str:
        """YOLO klass nomini chiqindi kategoriyasiga moslashtirish."""
        return YOLO_TO_WASTE.get(class_name.lower(), "unknown")

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """Rasmda chiqindilarni aniqlash — backend ga qarab."""
        if not self.is_loaded:
            logger.warning("Model yuklanmagan!")
            return []

        if self.backend == "onnx":
            detections = self._detect_onnx(frame)
        else:
            detections = self._detect_pytorch(frame)

        # Dumaloq shakl orqali qo'shimcha aniqlash
        if not detections and CIRCLE_DETECTION:
            detections.extend(self._detect_circles(frame))

        detections.sort(key=lambda d: d.confidence, reverse=True)

        if detections:
            logger.info(
                f"{len(detections)} ta obyekt aniqlandi: "
                + ", ".join(f"{d.name_uz} ({d.confidence:.0%})" for d in detections)
            )

        return detections

    def _detect_onnx(self, frame: np.ndarray) -> List[DetectionResult]:
        """ONNX Runtime orqali aniqlash."""
        blob, ratio, pad_x, pad_y = self._preprocess_onnx(frame)
        input_name = self.onnx_session.get_inputs()[0].name
        output = self.onnx_session.run(None, {input_name: blob})
        return self._postprocess_onnx(output[0], ratio, pad_x, pad_y)

    def _detect_pytorch(self, frame: np.ndarray) -> List[DetectionResult]:
        """PyTorch/ultralytics orqali aniqlash."""
        results = self.model.predict(
            source=frame,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                confidence = float(box.conf[0])

                waste_category = self._map_to_waste_category(class_name)
                if waste_category not in WASTE_CATEGORIES:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cat_info = WASTE_CATEGORIES[waste_category]

                detection = DetectionResult(
                    class_name=class_name,
                    waste_category=waste_category,
                    confidence=confidence,
                    bbox=(x1, y1, x2, y2),
                    ecocoin_reward=cat_info["ecocoin_reward"],
                    material=cat_info["material"],
                    name_uz=cat_info["name_uz"],
                )
                detections.append(detection)

        return detections

    def _detect_circles(self, frame: np.ndarray) -> List[DetectionResult]:
        """Dumaloq shakllarni aniqlash (shisha qopqog'i yuqoridan)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=50,
            param1=100,
            param2=40,
            minRadius=CIRCLE_MIN_RADIUS,
            maxRadius=CIRCLE_MAX_RADIUS,
        )

        detections = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            cat_info = WASTE_CATEGORIES.get("bottle", None)
            if cat_info is None:
                return []

            for circle in circles[0]:
                cx, cy, r = int(circle[0]), int(circle[1]), int(circle[2])
                x1 = max(0, cx - r)
                y1 = max(0, cy - r)
                x2 = min(frame.shape[1], cx + r)
                y2 = min(frame.shape[0], cy + r)

                detection = DetectionResult(
                    class_name="circle_bottle",
                    waste_category="bottle",
                    confidence=0.55,
                    bbox=(x1, y1, x2, y2),
                    ecocoin_reward=cat_info["ecocoin_reward"],
                    material=cat_info["material"],
                    name_uz=cat_info["name_uz"] + " (yuqoridan)",
                )
                detections.append(detection)

        return detections

    def detect_single_image(self, image_path: str) -> List[DetectionResult]:
        """Bitta rasm faylida chiqindilarni aniqlash."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Rasm topilmadi: {image_path}")
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Rasmni o'qib bo'lmadi: {image_path}")
        return self.detect(frame)

    def get_summary(self, detections: List[DetectionResult]) -> Dict:
        """Aniqlash natijalarining qisqacha xulosasi."""
        if not detections:
            return {
                "total_items": 0,
                "total_ecocoins": 0,
                "categories": {},
                "message_uz": "Hech narsa aniqlanmadi",
            }

        categories = {}
        total_ecocoins = 0

        for det in detections:
            cat = det.waste_category
            if cat not in categories:
                categories[cat] = {
                    "count": 0,
                    "name_uz": det.name_uz,
                    "ecocoins": 0,
                }
            categories[cat]["count"] += 1
            categories[cat]["ecocoins"] += det.ecocoin_reward
            total_ecocoins += det.ecocoin_reward

        return {
            "total_items": len(detections),
            "total_ecocoins": total_ecocoins,
            "categories": categories,
            "message_uz": (
                f"{len(detections)} ta chiqindi aniqlandi. "
                f"Jami {total_ecocoins} EcoCoin topildi!"
            ),
        }
