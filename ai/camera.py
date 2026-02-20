"""
Kamera orqali real-vaqtda chiqindilarni aniqlash moduli.
Real-time waste detection via camera module.

Qo'llab-quvvatlanadigan kamera backendlari:
  1. picamera2  — RPi CSI kamera (picamera2 kutubxonasi kerak)
  2. libcamera  — RPi CSI kamera (Python kutubxona kerak EMAS, faqat RPi OS)
  3. opencv     — USB webcam yoki V4L2 orqali CSI kamera
"""

import cv2
import logging
import os
import subprocess
import time
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
    RPI_CAMERA_HFLIP,
    RPI_CAMERA_VFLIP,
    RPI_CAMERA_ROTATION,
)

logger = logging.getLogger(__name__)

# ─── Backend mavjudligini tekshirish ───
_PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    pass

_LIBCAMERA_AVAILABLE = False
try:
    subprocess.run(["libcamera-vid", "--version"], capture_output=True, timeout=5)
    _LIBCAMERA_AVAILABLE = True
except Exception:
    pass


def _is_raspberry_pi() -> bool:
    """Raspberry Pi qurilmasida ishlayotganligini tekshirish."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "BCM" in f.read()
    except Exception:
        return False


def _detect_camera_backend() -> str:
    """Kamera backendini avtomatik aniqlash."""
    if CAMERA_BACKEND != "auto":
        return CAMERA_BACKEND

    if _is_raspberry_pi():
        if _PICAMERA2_AVAILABLE:
            return "picamera"
        if _LIBCAMERA_AVAILABLE:
            return "libcamera"
        if os.path.exists("/dev/video0"):
            return "opencv"
        logger.warning(
            "RPi kamera topilmadi! Sinab ko'ring:\n"
            "  sudo modprobe bcm2835-v4l2\n"
            "  yoki: sudo raspi-config → Interface Options → Camera → Enable"
        )
    return "opencv"


class LibcameraCapture:
    """
    libcamera-vid subprocess orqali RPi CSI kameradan kadr olish.
    Hech qanday Python kutubxona kerak EMAS.
    """

    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None

    def start(self) -> bool:
        try:
            cmd = [
                "libcamera-vid",
                "--width", str(self.width),
                "--height", str(self.height),
                "--framerate", str(self.fps),
                "--codec", "yuv420",
                "--timeout", "0",
                "--nopreview",
                "-o", "-",
            ]
            if RPI_CAMERA_HFLIP:
                cmd.append("--hflip")
            if RPI_CAMERA_VFLIP:
                cmd.append("--vflip")
            if RPI_CAMERA_ROTATION:
                cmd.extend(["--rotation", str(RPI_CAMERA_ROTATION)])

            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=self.width * self.height * 3,
            )
            time.sleep(1.0)
            if self.process.poll() is not None:
                return False
            logger.info(f"libcamera-vid: {self.width}x{self.height}@{self.fps}fps")
            return True
        except Exception as e:
            logger.error(f"libcamera-vid xatosi: {e}")
            return False

    def read_frame(self):
        if self.process is None or self.process.poll() is not None:
            return False, None
        try:
            yuv_size = self.width * self.height * 3 // 2
            raw = self.process.stdout.read(yuv_size)
            if len(raw) < yuv_size:
                return False, None
            yuv = np.frombuffer(raw, dtype=np.uint8).reshape(
                (self.height * 3 // 2, self.width)
            )
            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            return True, bgr
        except Exception:
            return False, None

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


class CameraDetector:
    """
    Kamera orqali real-vaqtda chiqindilarni aniqlash.
    Supports: picamera2, libcamera subprocess, OpenCV (V4L2 / USB).
    """

    def __init__(
        self,
        camera_index: int = CAMERA_INDEX,
        classifier: Optional[WasteClassifier] = None,
        on_detection: Optional[Callable] = None,
        camera_backend: Optional[str] = None,
    ):
        self.camera_index = camera_index
        self.classifier = classifier or WasteClassifier()
        self.on_detection = on_detection
        self.cap = None
        self.picam = None
        self.libcam = None
        self.is_running = False
        self.total_ecocoins = 0
        self.detection_history = []
        self.frame_count = 0
        self.detect_every_n_frames = 3
        self.backend = camera_backend or _detect_camera_backend()
        logger.info(f"Kamera backend: {self.backend}")

    def _open_camera(self) -> bool:
        """Kamerani ochish — fallback bilan."""
        if self.backend == "picamera":
            if self._open_picamera():
                return True
            self.backend = "libcamera"

        if self.backend == "libcamera":
            if self._open_libcamera():
                return True
            self.backend = "opencv"

        return self._open_opencv()

    def _open_picamera(self) -> bool:
        if not _PICAMERA2_AVAILABLE:
            return False
        try:
            self.picam = Picamera2()
            config = self.picam.create_preview_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            )
            self.picam.configure(config)

            if RPI_CAMERA_HFLIP or RPI_CAMERA_VFLIP:
                try:
                    from libcamera import Transform
                    t = Transform(hflip=RPI_CAMERA_HFLIP, vflip=RPI_CAMERA_VFLIP)
                    self.picam.set_controls({"Transform": t})
                except ImportError:
                    pass

            self.picam.start()
            logger.info(f"picamera2 ochildi: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
            return True
        except Exception as e:
            logger.error(f"picamera2 xatosi: {e}")
            self.picam = None
            return False

    def _open_libcamera(self) -> bool:
        if not _LIBCAMERA_AVAILABLE:
            return False
        try:
            self.libcam = LibcameraCapture(CAMERA_WIDTH, CAMERA_HEIGHT, FPS)
            if self.libcam.start():
                return True
            self.libcam = None
            return False
        except Exception as e:
            logger.error(f"libcamera xatosi: {e}")
            self.libcam = None
            return False

    def _open_opencv(self) -> bool:
        if _is_raspberry_pi() and os.path.exists("/dev/video0"):
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_FPS, FPS)
                logger.info(f"OpenCV V4L2: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
                return True
            self.cap = None

        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            logger.error(f"Kamerani ochib bo'lmadi (index: {self.camera_index})")
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)
        logger.info(f"OpenCV kamera: {CAMERA_WIDTH}x{CAMERA_HEIGHT}@{FPS}fps")
        return True

    def _read_frame(self):
        if self.backend == "picamera" and self.picam:
            try:
                frame = self.picam.capture_array()
                return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception:
                return False, None
        elif self.backend == "libcamera" and self.libcam:
            return self.libcam.read_frame()
        else:
            if self.cap is None:
                return False, None
            return self.cap.read()

    def _draw_detections(self, frame, detections):
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cat_info = WASTE_CATEGORIES.get(det.waste_category, WASTE_CATEGORIES["unknown"])
            color = COLORS.get(cat_info["bin_color"], COLORS["kulrang"])

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f"{cat_info['icon']} {det.name_uz} ({det.confidence:.0%})"
            reward_text = f"+{det.ecocoin_reward} EcoCoin"

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, FONT_THICKNESS)
            cv2.rectangle(frame, (x1, y1 - th - 20), (x1 + tw + 10, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLORS["qora"], FONT_THICKNESS)
            cv2.putText(frame, reward_text, (x1 + 5, y2 + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE * 0.8, COLORS["oq"], FONT_THICKNESS)
        return frame

    def _draw_dashboard(self, frame, detections):
        h, w = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 70), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        cv2.putText(frame, WINDOW_NAME, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["oq"], 1)
        cv2.putText(frame, f"EcoCoin: {self.total_ecocoins}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"Aniqlandi: {len(detections)}", (w - 200, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["oq"], 1)

        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (0, h - 40), (w, h), (30, 30, 30), -1)
        cv2.addWeighted(overlay2, 0.8, frame, 0.2, 0, frame)
        cv2.putText(frame, "[Q] Chiqish | [S] Screenshot | [SPACE] Saqlash",
                    (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        return frame

    def _save_screenshot(self, frame):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"screenshot_{ts}.jpg"
        cv2.imwrite(fn, frame)
        logger.info(f"Screenshot: {fn}")
        return fn

    def run(self):
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
                    continue

                self.frame_count += 1

                if self.frame_count % self.detect_every_n_frames == 0:
                    last_detections = self.classifier.detect(frame)
                    if last_detections and self.on_detection:
                        self.on_detection(last_detections)

                frame = self._draw_detections(frame, last_detections)
                frame = self._draw_dashboard(frame, last_detections)
                cv2.imshow(WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                elif key in (ord("s"), ord("S")):
                    self._save_screenshot(frame)
                elif key == ord(" "):
                    if last_detections:
                        summary = self.classifier.get_summary(last_detections)
                        self.total_ecocoins += summary["total_ecocoins"]
                        self.detection_history.extend(last_detections)
                        print(f"\n  +{summary['total_ecocoins']} EcoCoin! Jami: {self.total_ecocoins}")
                    else:
                        print("\n  Hech narsa aniqlanmadi.")

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.picam:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception:
                pass
        if self.libcam:
            self.libcam.stop()
        cv2.destroyAllWindows()

        print(f"\n  Jami: {self.total_ecocoins} EcoCoin, {len(self.detection_history)} ta aniqlash.")

    def detect_from_image(self, image_path):
        detections = self.classifier.detect_single_image(image_path)
        if detections:
            summary = self.classifier.get_summary(detections)
            print(f"\n  {summary['message_uz']}")
        else:
            print("  Rasmda chiqindi aniqlanmadi.")
        return detections
