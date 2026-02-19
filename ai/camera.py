"""
Kamera orqali real-vaqtda chiqindilarni aniqlash moduli.
Real-time waste detection via camera module.

Qo'llab-quvvatlanadigan kamera backendlari:
  1. picamera2  — RPi CSI kamera (picamera2 kutubxonasi kerak)
  2. libcamera  — RPi CSI kamera (hech qanday Python kutubxona kerak EMAS,
                   faqat libcamera-vid buyrug'i kerak — RPi OS da tayyor)
  3. opencv     — USB webcam yoki V4L2 orqali CSI kamera

Supports: Raspberry Pi CSI camera and USB webcams.
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
    RPI_CAMERA_ROTATION,
    RPI_CAMERA_HFLIP,
    RPI_CAMERA_VFLIP,
)

logger = logging.getLogger(__name__)

# ─── Backend mavjudligini tekshirish ───

_PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
    logger.info("picamera2 kutubxonasi topildi ✓")
except ImportError:
    pass

_LIBCAMERA_AVAILABLE = False
try:
    # libcamera-vid buyrug'i mavjudligini tekshirish
    result = subprocess.run(
        ["libcamera-vid", "--version"],
        capture_output=True, timeout=5
    )
    _LIBCAMERA_AVAILABLE = True
    logger.info("libcamera-vid topildi ✓")
except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
    pass


def _is_raspberry_pi() -> bool:
    """Raspberry Pi qurilmasida ishlayotganligini tekshirish."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
        return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
    except (FileNotFoundError, PermissionError):
        return False


def _check_v4l2_device() -> bool:
    """CSI kamera V4L2 qurilmasi sifatida mavjudligini tekshirish."""
    return os.path.exists("/dev/video0")


def _detect_camera_backend() -> str:
    """
    Kamera backendini avtomatik aniqlash.
    Sinash tartibi: picamera2 → libcamera → v4l2/opencv
    """
    if CAMERA_BACKEND != "auto":
        return CAMERA_BACKEND

    is_rpi = _is_raspberry_pi()

    if is_rpi:
        # 1-usul: picamera2
        if _PICAMERA2_AVAILABLE:
            logger.info("RPi: picamera2 backend ishlatiladi")
            return "picamera"

        # 2-usul: libcamera subprocess (hech qanday Python kutubxona kerak emas!)
        if _LIBCAMERA_AVAILABLE:
            logger.info("RPi: libcamera backend ishlatiladi (subprocess)")
            return "libcamera"

        # 3-usul: V4L2 orqali OpenCV
        if _check_v4l2_device():
            logger.info("RPi: /dev/video0 topildi — OpenCV V4L2 backend")
            return "opencv"

        logger.warning(
            "RPi kamera topilmadi! Quyidagi buyruqlardan birini sinang:\n"
            "  sudo modprobe bcm2835-v4l2\n"
            "  yoki: sudo raspi-config → Interface Options → Camera → Enable"
        )

    logger.info("OpenCV backend ishlatiladi")
    return "opencv"


class LibcameraCapture:
    """
    libcamera-vid subprocess orqali RPi CSI kameradan kadr olish.
    Hech qanday qo'shimcha Python kutubxona kerak EMAS.
    Faqat Raspberry Pi OS da ishlaydi.
    """

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None
        self.frame_size = width * height * 3  # RGB888

    def start(self) -> bool:
        """libcamera-vid ni raw RGB chiqish bilan boshlash."""
        try:
            cmd = [
                "libcamera-vid",
                "--width", str(self.width),
                "--height", str(self.height),
                "--framerate", str(self.fps),
                "--codec", "yuv420",
                "--timeout", "0",             # Cheksiz davom etsin
                "--nopreview",                # Preview oynasiz
                "-o", "-",                    # stdout ga yozish
            ]

            # Flip sozlamalari
            if RPI_CAMERA_HFLIP:
                cmd.append("--hflip")
            if RPI_CAMERA_VFLIP:
                cmd.append("--vflip")
            if RPI_CAMERA_ROTATION:
                cmd.extend(["--rotation", str(RPI_CAMERA_ROTATION)])

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=self.width * self.height * 3,
            )

            # Kamera ishga tushishi uchun biroz kutish
            time.sleep(1.0)

            if self.process.poll() is not None:
                logger.error("libcamera-vid ishga tushmadi")
                return False

            logger.info(
                f"libcamera-vid ishga tushdi: {self.width}x{self.height}@{self.fps}fps"
            )
            return True

        except Exception as e:
            logger.error(f"libcamera-vid xatosi: {e}")
            return False

    def read_frame(self) -> tuple:
        """
        YUV420 kadrni o'qib, BGR ga aylantirish.
        Returns: (success: bool, frame: np.ndarray | None)
        """
        if self.process is None or self.process.poll() is not None:
            return False, None

        try:
            # YUV420 = width * height * 1.5 bayt
            yuv_size = self.width * self.height * 3 // 2
            raw = self.process.stdout.read(yuv_size)

            if len(raw) < yuv_size:
                return False, None

            # YUV420 → BGR
            yuv = np.frombuffer(raw, dtype=np.uint8).reshape(
                (self.height * 3 // 2, self.width)
            )
            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            return True, bgr

        except Exception as e:
            logger.warning(f"libcamera kadr o'qishda xato: {e}")
            return False, None

    def stop(self):
        """Processni to'xtatish."""
        if self.process is not None:
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
            camera_backend: 'picamera', 'libcamera', 'opencv', yoki None (auto).
        """
        self.camera_index = camera_index
        self.classifier = classifier or WasteClassifier()
        self.on_detection = on_detection
        self.cap = None          # OpenCV VideoCapture
        self.picam = None        # Picamera2
        self.libcam = None       # LibcameraCapture (subprocess)
        self.is_running = False
        self.total_ecocoins = 0
        self.detection_history = []
        self.frame_count = 0
        self.detect_every_n_frames = 3
        self.backend = camera_backend or _detect_camera_backend()
        logger.info(f"Kamera backend: {self.backend}")

    def _open_camera(self) -> bool:
        """
        Kamerani ochish — tanlangan backend bo'yicha.
        Agar muvaffaqiyatsiz bo'lsa, keyingi backendga o'tadi.
        """
        if self.backend == "picamera":
            if self._open_picamera():
                return True
            logger.info("picamera2 ishlamadi, libcamera ga o'tilmoqda...")
            self.backend = "libcamera"

        if self.backend == "libcamera":
            if self._open_libcamera():
                return True
            logger.info("libcamera ishlamadi, OpenCV ga o'tilmoqda...")
            self.backend = "opencv"

        return self._open_opencv_camera()

    def _open_picamera(self) -> bool:
        """Raspberry Pi CSI kamerani picamera2 orqali ochish."""
        if not _PICAMERA2_AVAILABLE:
            logger.warning("picamera2 kutubxonasi o'rnatilmagan")
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
                    logger.warning("libcamera Transform import qilib bo'lmadi")

            self.picam.start()
            logger.info(f"RPi kamera ochildi (picamera2): {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
            return True
        except Exception as e:
            logger.error(f"picamera2 xatosi: {e}")
            self.picam = None
            return False

    def _open_libcamera(self) -> bool:
        """
        libcamera-vid subprocess orqali CSI kamerani ochish.
        Hech qanday Python kutubxona kerak EMAS — faqat RPi OS.
        """
        if not _LIBCAMERA_AVAILABLE:
            logger.warning("libcamera-vid buyrug'i topilmadi")
            return False
        try:
            self.libcam = LibcameraCapture(
                width=CAMERA_WIDTH, height=CAMERA_HEIGHT, fps=FPS
            )
            success = self.libcam.start()
            if success:
                logger.info(f"RPi kamera ochildi (libcamera-vid): {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
            return success
        except Exception as e:
            logger.error(f"libcamera-vid xatosi: {e}")
            self.libcam = None
            return False

    def _open_opencv_camera(self) -> bool:
        """
        OpenCV orqali kamerani ochish.
        V4L2 driver yuklangan bo'lsa, CSI kamera ham ishlaydi.
        """
        # RPi da V4L2 orqali CSI kamerani sinash
        if _is_raspberry_pi() and _check_v4l2_device():
            # V4L2 backend bilan ochish
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_FPS, FPS)
                logger.info(f"OpenCV V4L2 kamera ochildi: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
                return True
            self.cap = None

        # Oddiy OpenCV
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
        Returns: (success: bool, frame: np.ndarray | None)
        """
        if self.backend == "picamera" and self.picam is not None:
            try:
                frame = self.picam.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            except Exception as e:
                logger.warning(f"picamera2 kadr xatosi: {e}")
                return False, None

        elif self.backend == "libcamera" and self.libcam is not None:
            return self.libcam.read_frame()

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
        if self.libcam is not None:
            self.libcam.stop()
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
