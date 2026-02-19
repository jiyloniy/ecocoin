"""
Kamera orqali real-vaqtda chiqindilarni aniqlash moduli.
Real-time waste detection via camera module.

Raspberry Pi CSI kamera va USB webcam ni qo'llab-quvvatlaydi.
Supports both Raspberry Pi CSI camera (via picamera2) and USB webcams (via OpenCV).
"""

import cv2
import logging
import platform
import numpy as np
from typing import Optional, Callable
from datetime import datetime

from ai.classifier import WasteClassifier, DetectionResult
from ai.config import (
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    FPS,
    WINDOW_NAME,
    FONT_SCALE,
    FONT_THICKNESS,
    COLORS,
    WASTE_CATEGORIES,
    CAMERA_BACKEND,
    RPI_CAMERA_ROTATION,
    RPI_CAMERA_HFLIP,
    RPI_CAMERA_VFLIP,
)

logger = logging.getLogger(__name__)

# Raspberry Pi kamerani tekshirish
_PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
    logger.info("picamera2 kutubxonasi topildi ✓")
except ImportError:
    logger.info("picamera2 topilmadi — OpenCV backend ishlatiladi")


def _is_raspberry_pi() -> bool:
    """Raspberry Pi qurilmasida ishlayotganligini tekshirish."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
        return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
    except (FileNotFoundError, PermissionError):
        return False


def _detect_camera_backend() -> str:
    """
    Kamera backendini avtomatik aniqlash.
    Returns: 'picamera' yoki 'opencv'
    """
    if CAMERA_BACKEND != "auto":
        return CAMERA_BACKEND

    if _PICAMERA2_AVAILABLE and _is_raspberry_pi():
        logger.info("Raspberry Pi aniqlandi — picamera2 backend ishlatiladi")
        return "picamera"
    else:
        logger.info("OpenCV backend ishlatiladi")
        return "opencv"


class CameraDetector:
    """
    Kamera orqali real-vaqtda chiqindilarni aniqlash.
    Real-time waste detection using camera feed.
    """

    def __init__(
        self,
        camera_index: int = CAMERA_INDEX,
        classifier: Optional[WasteClassifier] = None,
        on_detection: Optional[Callable] = None,
        camera_backend: Optional[str] = None,
    ):
        """
        Args:
            camera_index: Kamera indeksi (0 = default, faqat OpenCV uchun).
            classifier: WasteClassifier obyekti.
            on_detection: Aniqlanganda chaqiriladigan callback funksiya.
            camera_backend: 'picamera', 'opencv', yoki None (auto).
        """
        self.camera_index = camera_index
        self.classifier = classifier or WasteClassifier()
        self.on_detection = on_detection
        self.cap = None
        self.picam = None
        self.is_running = False
        self.total_ecocoins = 0
        self.detection_history = []
        self.frame_count = 0
        self.detect_every_n_frames = 3  # Har 3-frameda detect qilish (tezlik uchun)
        self.backend = camera_backend or _detect_camera_backend()
        logger.info(f"Kamera backend: {self.backend}")

    def _open_camera(self) -> bool:
        """Kamerani ochish — RPi CSI yoki USB webcam."""
        if self.backend == "picamera":
            return self._open_picamera()
        else:
            return self._open_opencv_camera()

    def _open_picamera(self) -> bool:
        """Raspberry Pi CSI kamerani picamera2 orqali ochish."""
        try:
            self.picam = Picamera2()

            # Kamera konfiguratsiyasi
            config = self.picam.create_preview_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            )
            self.picam.configure(config)

            # Rotation va flip sozlamalari
            transform = {}
            if RPI_CAMERA_HFLIP:
                transform["hflip"] = True
            if RPI_CAMERA_VFLIP:
                transform["vflip"] = True
            if transform:
                from libcamera import Transform
                t = Transform(**transform)
                self.picam.set_controls({"Transform": t})

            self.picam.start()
            logger.info(
                f"RPi kamera ochildi (picamera2): {CAMERA_WIDTH}x{CAMERA_HEIGHT}"
            )
            return True
        except Exception as e:
            logger.error(f"RPi kamerani ochib bo'lmadi: {e}")
            logger.info("OpenCV ga qaytish...")
            # Fallback to OpenCV
            self.backend = "opencv"
            return self._open_opencv_camera()

    def _open_opencv_camera(self) -> bool:
        """OpenCV orqali USB webcamni ochish."""
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            logger.error(f"Kamerani ochib bo'lmadi (index: {self.camera_index})")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)

        logger.info(f"OpenCV kamera ochildi: {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {FPS}fps")
        return True

    def _read_frame(self):
        """
        Kameradan kadr o'qish — backend ga qarab.
        Returns: (success: bool, frame: np.ndarray)
        """
        if self.backend == "picamera" and self.picam is not None:
            try:
                frame = self.picam.capture_array()
                # picamera2 RGB qaytaradi, OpenCV BGR kutadi
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            except Exception as e:
                logger.warning(f"RPi kameradan kadr o'qishda xato: {e}")
                return False, None
        else:
            if self.cap is None:
                return False, None
            return self.cap.read()

    def _draw_detections(
        self, frame: np.ndarray, detections: list
    ) -> np.ndarray:
        """
        Rasmga aniqlash natijalarini chizish.

        Args:
            frame: OpenCV rasm.
            detections: Aniqlangan obyektlar.

        Returns:
            Chizilgan rasm.
        """
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cat_info = WASTE_CATEGORIES.get(
                det.waste_category, WASTE_CATEGORIES["unknown"]
            )
            color = COLORS.get(cat_info["bin_color"], COLORS["kulrang"])

            # Bounding box chizish
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Matn tayyorlash
            label = f"{cat_info['icon']} {det.name_uz} ({det.confidence:.0%})"
            reward_text = f"+{det.ecocoin_reward} EcoCoin"

            # Matn fonini chizish
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, FONT_THICKNESS
            )
            cv2.rectangle(
                frame, (x1, y1 - th - 20), (x1 + tw + 10, y1), color, -1
            )

            # Matnni yozish
            cv2.putText(
                frame,
                label,
                (x1 + 5, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                FONT_SCALE,
                COLORS["qora"],
                FONT_THICKNESS,
            )

            # EcoCoin mukofotini ko'rsatish
            cv2.putText(
                frame,
                reward_text,
                (x1 + 5, y2 + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                FONT_SCALE * 0.8,
                COLORS["oq"],
                FONT_THICKNESS,
            )

        return frame

    def _draw_dashboard(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """
        Ekranning yuqori qismiga ma'lumot panelini chizish.

        Args:
            frame: OpenCV rasm.
            detections: Joriy aniqlashlar.

        Returns:
            Yangilangan rasm.
        """
        h, w = frame.shape[:2]

        # Yuqori panel foni
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 70), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        # Sarlavha
        cv2.putText(
            frame,
            WINDOW_NAME,
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            COLORS["oq"],
            1,
        )

        # EcoCoin hisobi
        coin_text = f"EcoCoin: {self.total_ecocoins}"
        cv2.putText(
            frame,
            coin_text,
            (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )

        # Aniqlangan obyektlar soni
        count_text = f"Aniqlandi: {len(detections)}"
        cv2.putText(
            frame,
            count_text,
            (w - 200, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            COLORS["oq"],
            1,
        )

        # Pastgi panel - ko'rsatma
        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (0, h - 40), (w, h), (30, 30, 30), -1)
        cv2.addWeighted(overlay2, 0.8, frame, 0.2, 0, frame)

        help_text = "[Q] Chiqish | [S] Screenshot | [SPACE] Saqlash"
        cv2.putText(
            frame,
            help_text,
            (10, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 180, 180),
            1,
        )

        return frame

    def _save_screenshot(self, frame: np.ndarray) -> str:
        """Screenshot saqlash."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        logger.info(f"Screenshot saqlandi: {filename}")
        return filename

    def run(self) -> None:
        """
        Kamerani ishga tushirish va real-vaqtda aniqlashni boshlash.
        'q' tugmasi bilan to'xtatish.
        """
        if not self._open_camera():
            print("XATO: Kamerani ochib bo'lmadi!")
            print("Iltimos, kamerangiz ulanganligini tekshiring.")
            return

        self.is_running = True
        last_detections = []

        print("=" * 50)
        print(f"  {WINDOW_NAME}")
        print("=" * 50)
        print("  Kamera tayyor! Chiqindilarni kamera oldiga qo'ying.")
        print("  Q - Chiqish | S - Screenshot | SPACE - Saqlash")
        print("=" * 50)

        try:
            while self.is_running:
                ret, frame = self._read_frame()
                if not ret:
                    logger.warning("Kadrni o'qib bo'lmadi")
                    continue

                self.frame_count += 1

                # Tezlik uchun har N-frameda detect qilish
                if self.frame_count % self.detect_every_n_frames == 0:
                    last_detections = self.classifier.detect(frame)

                    # Callback chaqirish
                    if last_detections and self.on_detection:
                        self.on_detection(last_detections)

                # Natijalarni chizish
                frame = self._draw_detections(frame, last_detections)
                frame = self._draw_dashboard(frame, last_detections)

                # Ko'rsatish
                cv2.imshow(WINDOW_NAME, frame)

                # Klaviatura buyruqlari
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == ord("Q"):
                    print("\nDastur to'xtatilmoqda...")
                    break
                elif key == ord("s") or key == ord("S"):
                    self._save_screenshot(frame)
                elif key == ord(" "):
                    # SPACE - joriy aniqlashni saqlash va EcoCoin hisoblash
                    if last_detections:
                        summary = self.classifier.get_summary(last_detections)
                        self.total_ecocoins += summary["total_ecocoins"]
                        self.detection_history.extend(last_detections)

                        print(f"\n  ✅ {summary['message_uz']}")
                        print(f"  💰 Jami EcoCoin: {self.total_ecocoins}")
                        for cat, info in summary["categories"].items():
                            cat_info = WASTE_CATEGORIES[cat]
                            print(
                                f"     {cat_info['icon']} {info['name_uz']}: "
                                f"{info['count']} ta = {info['ecocoins']} EcoCoin"
                            )
                    else:
                        print("\n  ⚠️  Hech narsa aniqlanmadi. Chiqindini kamera oldiga qo'ying.")

        except KeyboardInterrupt:
            print("\nDastur to'xtatildi.")

        finally:
            self.stop()

    def stop(self) -> None:
        """Kamerani to'xtatish va resurslarni ozod qilish."""
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
        if self.picam is not None:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception:
                pass
        cv2.destroyAllWindows()

        print("\n" + "=" * 50)
        print("  Yakuniy natija:")
        print(f"  💰 Jami EcoCoin: {self.total_ecocoins}")
        print(f"  📊 Jami aniqlangan: {len(self.detection_history)} ta")
        print("=" * 50)

        logger.info(
            f"Kamera to'xtatildi. "
            f"Jami: {self.total_ecocoins} EcoCoin, "
            f"{len(self.detection_history)} ta aniqlash."
        )

    def detect_from_image(self, image_path: str) -> list:
        """
        Bitta rasmdan aniqlash (kamerasiz).

        Args:
            image_path: Rasm fayli yo'li.

        Returns:
            Aniqlangan obyektlar ro'yxati.
        """
        detections = self.classifier.detect_single_image(image_path)
        if detections:
            summary = self.classifier.get_summary(detections)
            print(f"\n  📸 Rasm tahlili: {image_path}")
            print(f"  {summary['message_uz']}")
            for cat, info in summary["categories"].items():
                cat_info = WASTE_CATEGORIES[cat]
                print(
                    f"     {cat_info['icon']} {info['name_uz']}: "
                    f"{info['count']} ta = {info['ecocoins']} EcoCoin"
                )
        else:
            print("  ⚠️  Rasmda chiqindi aniqlanmadi.")

        return detections
