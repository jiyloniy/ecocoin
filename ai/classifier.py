"""
Chiqindilarni aniqlash va tasniflash moduli.
Waste detection and classification module using YOLOv8.
"""

import os
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError(
        "ultralytics kutubxonasi o'rnatilmagan. "
        "O'rnatish: pip install ultralytics"
    )

from ai.config import (
    MODEL_NAME,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    YOLO_TO_WASTE,
    WASTE_CATEGORIES,
    CIRCLE_DETECTION,
    CIRCLE_MIN_RADIUS,
    CIRCLE_MAX_RADIUS,
)

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Bitta aniqlangan obyekt natijasi."""
    class_name: str               # YOLO klass nomi
    waste_category: str           # Bizning kategoriyamiz
    confidence: float             # Ishonch darajasi (0-1)
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    ecocoin_reward: int           # EcoCoin mukofoti
    material: str                 # Material turi
    name_uz: str                  # O'zbekcha nomi
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class WasteClassifier:
    """
    YOLOv8 asosida chiqindilarni aniqlash va tasniflash.
    Uses pre-trained YOLOv8 model for waste detection.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Classifierni ishga tushirish.

        Args:
            model_path: Model fayl yo'li. None bo'lsa, default model yuklanadi.
        """
        self.model_path = model_path or MODEL_NAME
        self.model = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self) -> None:
        """YOLOv8 modelini yuklash."""
        try:
            logger.info(f"Model yuklanmoqda: {self.model_path}")
            self.model = YOLO(self.model_path)
            self.is_loaded = True
            logger.info("Model muvaffaqiyatli yuklandi ✓")
        except Exception as e:
            logger.error(f"Modelni yuklashda xato: {e}")
            raise RuntimeError(f"Modelni yuklash imkoni bo'lmadi: {e}")

    def _map_to_waste_category(self, class_name: str) -> str:
        """
        YOLO klass nomini chiqindi kategoriyasiga moslashtirish.

        Args:
            class_name: YOLO tomonidan aniqlangan klass nomi.

        Returns:
            Chiqindi kategoriyasi nomi.
        """
        return YOLO_TO_WASTE.get(class_name.lower(), "unknown")

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """
        Rasmda chiqindilarni aniqlash.

        Args:
            frame: OpenCV formatidagi rasm (BGR).

        Returns:
            Aniqlangan obyektlar ro'yxati.
        """
        if not self.is_loaded:
            logger.warning("Model yuklanmagan!")
            return []

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

                # Faqat bottle, cup, glass kategoriyalarigagina
                waste_category = self._map_to_waste_category(class_name)
                if waste_category not in WASTE_CATEGORIES:
                    continue

                # Bounding box koordinatalari
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # Kategoriya ma'lumotlari
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

        # YOLO tanimagan bo'lsa, dumaloq shakl orqali bottle aniqlash
        if not detections and CIRCLE_DETECTION:
            circle_detections = self._detect_circles(frame)
            detections.extend(circle_detections)

        # Ishonch darajasi bo'yicha tartiblash
        detections.sort(key=lambda d: d.confidence, reverse=True)

        if detections:
            logger.info(
                f"{len(detections)} ta obyekt aniqlandi: "
                + ", ".join(f"{d.name_uz} ({d.confidence:.0%})" for d in detections)
            )

        return detections

    def _detect_circles(self, frame: np.ndarray) -> List[DetectionResult]:
        """
        Dumaloq shakllarni aniqlash (shisha qopqog'i yuqoridan).
        Hough Circle Transform orqali ishlaydi.

        Args:
            frame: OpenCV rasm (BGR).

        Returns:
            Aniqlangan dumaloq obyektlar (bottle sifatida).
        """
        import cv2

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

            if detections:
                logger.info(
                    f"Dumaloq shakl orqali {len(detections)} ta shisha aniqlandi"
                )

        return detections

    def detect_single_image(self, image_path: str) -> List[DetectionResult]:
        """
        Bitta rasm faylida chiqindilarni aniqlash.

        Args:
            image_path: Rasm fayli yo'li.

        Returns:
            Aniqlangan obyektlar ro'yxati.
        """
        import cv2

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Rasm topilmadi: {image_path}")

        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Rasmni o'qib bo'lmadi: {image_path}")

        return self.detect(frame)

    def get_summary(self, detections: List[DetectionResult]) -> Dict:
        """
        Aniqlash natijalarining qisqacha xulosasi.

        Args:
            detections: Aniqlangan obyektlar ro'yxati.

        Returns:
            Xulosa lug'ati.
        """
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
