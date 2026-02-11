"""
EcoCoin — Kiosk UI (v2).
Katta animatsiyali oyna: kamera, maskot, coin berish, QR code chiqarish.
"""

import cv2
import io
import uuid
import random
import numpy as np
import logging
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QRadialGradient, QPen, QBrush, QPainterPath
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy, QGraphicsOpacityEffect
)

from ui.mascot import MascotWidget
from ui.sounds import play_detection_sound

logger = logging.getLogger(__name__)

# ─── Har bir chiqindi uchun 5 coin ───
COIN_REWARD = 5


class CameraWidget(QLabel):
    """Katta kamera oynasi — yuqorida markazda, chiroyli ramka bilan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(420, 310)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(45)
        shadow.setColor(QColor(76, 175, 80, 180))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
        self._placeholder = True
        self._frame_pixmap = None

    def update_frame(self, frame: np.ndarray):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(img).scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self._frame_pixmap = pixmap
        self._placeholder = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        border = 4
        radius = 22
        inner = self.rect().adjusted(border, border, -border, -border)

        # Rounded clip path — pixmap ramkadan chiqmasligi uchun
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(inner), radius - 2, radius - 2)
        p.setClipPath(clip_path)

        if self._placeholder:
            # Gradient background
            bg_grad = QLinearGradient(0, 0, 0, self.height())
            bg_grad.setColorAt(0, QColor(13, 17, 23))
            bg_grad.setColorAt(1, QColor(20, 30, 20))
            p.fillRect(self.rect(), QBrush(bg_grad))

            # Camera icon
            p.setPen(QColor(76, 175, 80, 120))
            icon_font = QFont("Segoe UI", 40)
            p.setFont(icon_font)
            p.drawText(QRectF(0, self.height() * 0.2, self.width(), 60),
                       Qt.AlignmentFlag.AlignCenter, "📷")

            # Text
            p.setPen(QColor(76, 175, 80, 200))
            p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            p.drawText(QRectF(0, self.height() * 0.55, self.width(), 35),
                       Qt.AlignmentFlag.AlignCenter, "Kamera yuklanmoqda...")
        else:
            # Kamera frameni clip ichida chizish
            pm = self._frame_pixmap
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            p.drawPixmap(x, y, pm)

        # Clip olib tashlash — ramkani ustidan chizish
        p.setClipping(False)

        # Gradient border
        border_grad = QLinearGradient(0, 0, self.width(), self.height())
        border_grad.setColorAt(0, QColor(102, 187, 106))
        border_grad.setColorAt(0.5, QColor(67, 160, 71))
        border_grad.setColorAt(1, QColor(46, 125, 50))
        p.setPen(QPen(QBrush(border_grad), border, Qt.PenStyle.SolidLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        frame_path = QPainterPath()
        frame_path.addRoundedRect(QRectF(self.rect()).adjusted(
            border / 2, border / 2, -border / 2, -border / 2), radius, radius)
        p.drawPath(frame_path)

        p.end()


class CoinDisplayWidget(QWidget):
    """Katta coin ko'rsatish — o'rtada paydo bo'lib yo'qoladi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._visible = False
        self._phase = 0.0
        self._coin_text = "+5 🪙"
        self._waste_text = ""
        self._opacity = 0.0
        self._scale = 0.3

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_hide)

        self._hiding = False

    def show_coin(self, waste_name: str, amount: int = 5):
        self._visible = True
        self._hiding = False
        self._coin_text = f"+{amount}"
        self._waste_text = waste_name
        self._opacity = 0.0
        self._scale = 0.3
        self._phase = 0.0
        self._hide_timer.start(2500)

    def _start_hide(self):
        self._hiding = True

    def _animate(self):
        if not self._visible:
            return

        self._phase += 0.08

        if self._hiding:
            self._opacity = max(0, self._opacity - 0.04)
            self._scale *= 0.98
            if self._opacity <= 0:
                self._visible = False
        else:
            self._opacity = min(1.0, self._opacity + 0.06)
            self._scale = min(1.0, self._scale + 0.04)

        self.update()

    def paintEvent(self, event):
        if not self._visible:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 3

        p.translate(cx, cy)
        p.scale(self._scale, self._scale)

        # Glow
        glow = QRadialGradient(0, 0, 120)
        glow.setColorAt(0, QColor(255, 215, 0, 80))
        glow.setColorAt(1, QColor(255, 215, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(0, 0), 120, 120)

        # Coin doira
        coin_grad = QRadialGradient(QPointF(-10, -15), 70)
        coin_grad.setColorAt(0, QColor(255, 241, 118))
        coin_grad.setColorAt(0.5, QColor(255, 215, 0))
        coin_grad.setColorAt(1, QColor(255, 160, 0))
        p.setBrush(QBrush(coin_grad))
        p.setPen(QPen(QColor(255, 160, 0), 4))
        p.drawEllipse(QPointF(0, 0), 60, 60)

        # Coin ichidagi matn
        p.setPen(QColor(120, 80, 0))
        font = QFont("Segoe UI", 34, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(-50, -25, 100, 50), Qt.AlignmentFlag.AlignCenter, self._coin_text)

        # Pastda EcoCoin yozuvi
        p.setPen(QColor(255, 215, 0))
        font2 = QFont("Segoe UI", 20, QFont.Weight.Bold)
        p.setFont(font2)
        p.drawText(QRectF(-100, 70, 200, 35), Qt.AlignmentFlag.AlignCenter, "EcoCoin")

        # Waste nomi
        p.setPen(QColor(255, 255, 255))
        font3 = QFont("Segoe UI", 16)
        p.setFont(font3)
        p.drawText(QRectF(-150, 110, 300, 30), Qt.AlignmentFlag.AlignCenter, self._waste_text)

        p.end()


class QRCodeWidget(QWidget):
    """O'ng tarafda paydo bo'ladigan QR code."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._qr_pixmap = None
        self._visible = False
        self._opacity = 0.0
        self._slide_x = 400  # o'ngdan kirib keladi
        self._code_text = ""
        self._glow_phase = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_hide)

        self._hiding = False

    def show_qr(self):
        """Random QR code yaratish va ko'rsatish."""
        import qrcode

        self._code_text = f"ECOCOIN-{uuid.uuid4().hex[:8].upper()}"

        qr = qrcode.QRCode(version=2, box_size=10, border=2)
        qr.add_data(self._code_text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1B5E20", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        qimg = QImage()
        qimg.loadFromData(buf.read())
        self._qr_pixmap = QPixmap.fromImage(qimg)

        self._visible = True
        self._hiding = False
        self._opacity = 0.0
        self._slide_x = 400
        self._glow_phase = 0.0

        self._hide_timer.start(8000)

    def _start_hide(self):
        self._hiding = True

    def _animate(self):
        if not self._visible:
            return

        self._glow_phase += 0.06

        if self._hiding:
            self._opacity = max(0, self._opacity - 0.03)
            self._slide_x += 10
            if self._opacity <= 0:
                self._visible = False
        else:
            self._opacity = min(1.0, self._opacity + 0.05)
            self._slide_x = max(0, self._slide_x - 18)

        self.update()

    def paintEvent(self, event):
        if not self._visible or not self._qr_pixmap:
            return

        import math

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)

        w, h = self.width(), self.height()
        ox = self._slide_x

        # Card o'lchamlari
        card_w = 350
        card_h = 480
        card_x = (w - card_w) // 2 + ox  # markazda
        card_y = (h - card_h) // 2 + 20  # biroz pastroq

        # Outer glow - pulsating
        glow_alpha = int(30 + 15 * math.sin(self._glow_phase))
        glow = QRadialGradient(card_x + card_w / 2, card_y + card_h / 2, card_w * 0.8)
        glow.setColorAt(0, QColor(76, 175, 80, glow_alpha))
        glow.setColorAt(1, QColor(76, 175, 80, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QRectF(card_x - 40, card_y - 30, card_w + 80, card_h + 60))

        # Shadow (deeper, offset)
        p.setBrush(QColor(0, 0, 0, 50))
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(QRectF(card_x + 6, card_y + 6, card_w, card_h), 24, 24)
        p.drawPath(shadow_path)

        # Card background — premium gradient
        card_grad = QLinearGradient(card_x, card_y, card_x + card_w, card_y + card_h)
        card_grad.setColorAt(0, QColor(255, 255, 255, 252))
        card_grad.setColorAt(0.3, QColor(245, 255, 245, 252))
        card_grad.setColorAt(0.7, QColor(232, 248, 233, 252))
        card_grad.setColorAt(1, QColor(200, 230, 201, 252))
        p.setBrush(QBrush(card_grad))

        # Animated border color
        border_g = int(155 + 20 * math.sin(self._glow_phase * 1.5))
        p.setPen(QPen(QColor(56, border_g, 60, 200), 3))
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(card_x, card_y, card_w, card_h), 24, 24)
        p.drawPath(card_path)

        # Dekorativ yuqori chiziq (gold accent)
        accent_grad = QLinearGradient(card_x + 30, card_y + 8, card_x + card_w - 30, card_y + 8)
        accent_grad.setColorAt(0, QColor(255, 215, 0, 0))
        accent_grad.setColorAt(0.3, QColor(255, 215, 0, 180))
        accent_grad.setColorAt(0.7, QColor(255, 193, 7, 180))
        accent_grad.setColorAt(1, QColor(255, 215, 0, 0))
        p.setPen(QPen(QBrush(accent_grad), 3))
        p.drawLine(int(card_x + 40), int(card_y + 8), int(card_x + card_w - 40), int(card_y + 8))

        # Title with icon
        p.setPen(QColor(27, 94, 32))
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(QRectF(card_x, card_y + 20, card_w, 38),
                   Qt.AlignmentFlag.AlignCenter, "🎁 EcoCoin Kupon")

        # Subtitle
        p.setPen(QColor(76, 175, 80))
        sub_font = QFont("Segoe UI", 11)
        p.setFont(sub_font)
        p.drawText(QRectF(card_x, card_y + 58, card_w, 22),
                   Qt.AlignmentFlag.AlignCenter, "Tabriklaymiz! Sovg'angiz tayyor ✨")

        # Separator line
        sep_grad = QLinearGradient(card_x + 20, 0, card_x + card_w - 20, 0)
        sep_grad.setColorAt(0, QColor(76, 175, 80, 0))
        sep_grad.setColorAt(0.5, QColor(76, 175, 80, 120))
        sep_grad.setColorAt(1, QColor(76, 175, 80, 0))
        p.setPen(QPen(QBrush(sep_grad), 1))
        p.drawLine(int(card_x + 20), int(card_y + 85), int(card_x + card_w - 20), int(card_y + 85))

        # QR Code — kattaroq
        qr_size = 240
        qr_x = card_x + (card_w - qr_size) // 2
        qr_y = card_y + 100

        # QR white background with subtle shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 15))
        p.drawRoundedRect(QRectF(qr_x - 10 + 3, qr_y - 10 + 3, qr_size + 20, qr_size + 20), 12, 12)

        p.setBrush(QColor(255, 255, 255))
        p.setPen(QPen(QColor(200, 230, 201), 2))
        p.drawRoundedRect(QRectF(qr_x - 10, qr_y - 10, qr_size + 20, qr_size + 20), 12, 12)

        # QR image
        scaled = self._qr_pixmap.scaled(qr_size, qr_size,
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(int(qr_x), int(qr_y), scaled)

        # Corner decorations (green dots at QR corners)
        dot_color = QColor(76, 175, 80, 180)
        p.setBrush(dot_color)
        p.setPen(Qt.PenStyle.NoPen)
        for dx, dy in [(-14, -14), (qr_size + 6, -14), (-14, qr_size + 6), (qr_size + 6, qr_size + 6)]:
            p.drawEllipse(QPointF(qr_x + dx, qr_y + dy), 4, 4)

        # Code text
        p.setPen(QColor(80, 80, 80))
        cf = QFont("Consolas", 12, QFont.Weight.Bold)
        p.setFont(cf)
        p.drawText(QRectF(card_x, qr_y + qr_size + 20, card_w, 24),
                   Qt.AlignmentFlag.AlignCenter, self._code_text)

        # "Skanerlang!" button-like shape
        btn_w, btn_h = 200, 40
        btn_x = card_x + (card_w - btn_w) // 2
        btn_y = qr_y + qr_size + 52

        btn_grad = QLinearGradient(btn_x, btn_y, btn_x, btn_y + btn_h)
        btn_grad.setColorAt(0, QColor(76, 175, 80))
        btn_grad.setColorAt(1, QColor(56, 142, 60))
        p.setBrush(QBrush(btn_grad))
        p.setPen(Qt.PenStyle.NoPen)
        btn_path = QPainterPath()
        btn_path.addRoundedRect(QRectF(btn_x, btn_y, btn_w, btn_h), 20, 20)
        p.drawPath(btn_path)

        p.setPen(QColor(255, 255, 255))
        sf = QFont("Segoe UI", 14, QFont.Weight.Bold)
        p.setFont(sf)
        p.drawText(QRectF(btn_x, btn_y, btn_w, btn_h),
                   Qt.AlignmentFlag.AlignCenter, "📱 Skanerlang!")

        # Pastda izoh
        p.setPen(QColor(120, 120, 120))
        nf = QFont("Segoe UI", 10)
        p.setFont(nf)
        p.drawText(QRectF(card_x + 10, card_y + card_h - 40, card_w - 20, 30),
                   Qt.AlignmentFlag.AlignCenter, "Bu kupon bilan sovg'a oling 🎉")

        p.end()


class KioskWindow(QMainWindow):
    """
    Kiosk oynasi v2:
    - Yuqori: status bar + kichik kamera
    - Pastda: maskot (chapga suriladi) + QR (o'ngdan chiqadi)
    - Chiqindi aniqlanganda: 5 coin → katta coin animatsiya → Mazza → Rahmat → QR
    - Coin ko'payib ketmasligi uchun cooldown
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EcoCoin ♻️")
        self.setMinimumSize(900, 650)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0a0e14, stop:0.4 #0d1117, stop:0.7 #111820, stop:1 #0a0e14);
            }
        """)

        # ─── Layout ───
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Camera (markazda yuqorida) + "Chiqindini cameraga ko'rsating" yozuvi
        cam_container = QWidget()
        cam_v_layout = QVBoxLayout(cam_container)
        cam_v_layout.setContentsMargins(0, 12, 0, 6)
        cam_v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_v_layout.setSpacing(8)

        # Tepada yozuv
        self.cam_label = QLabel("♻️  Chiqindini cameraga ko'rsating  ♻️")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setStyleSheet("""
            QLabel {
                color: #A5D6A7;
                font-size: 20px;
                font-weight: bold;
                font-family: 'Segoe UI';
                background: transparent;
                padding: 4px 18px;
                border: none;
            }
        """)
        cam_label_shadow = QGraphicsDropShadowEffect(self.cam_label)
        cam_label_shadow.setBlurRadius(18)
        cam_label_shadow.setColor(QColor(76, 175, 80, 100))
        cam_label_shadow.setOffset(0, 2)
        self.cam_label.setGraphicsEffect(cam_label_shadow)
        cam_v_layout.addWidget(self.cam_label)

        # Kamera widgeti
        self.camera_widget = CameraWidget()
        cam_v_layout.addWidget(self.camera_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(cam_container)

        # ─── Pastki qism: mascot (to'liq kenglikda) ───
        self.mascot = MascotWidget()
        self.mascot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.mascot, stretch=1)

        # QR widget — overlay sifatida (layout joy olmaydi)
        self.qr_widget = QRCodeWidget(central)
        self.qr_widget.setGeometry(0, 0, 0, 0)  # resizeEvent da joylashtiriladi

        # Coin display overlay (butun oyna ustida)
        self.coin_display = CoinDisplayWidget(central)

        # ─── AI / Camera state ───
        self.cap = None
        self.classifier = None
        self.total_ecocoins = 0
        self.frame_count = 0

        # Cooldown — bitta chiqindi uchun faqat 1 marta coin
        self._coin_cooldown = False
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setSingleShot(True)
        self._cooldown_timer.timeout.connect(self._reset_cooldown)

        # QR ko'rsatish — thanking tugagandan keyin
        self._qr_scheduled = False
        self._qr_delay = QTimer(self)
        self._qr_delay.setSingleShot(True)
        self._qr_delay.timeout.connect(self._show_qr_code)

        # Camera timer
        self._cam_timer = QTimer(self)
        self._cam_timer.timeout.connect(self._process_frame)

    def resizeEvent(self, event):
        """Coin display va QR widgetni oyna hajmiga moslashtirish."""
        super().resizeEvent(event)
        if hasattr(self, 'coin_display'):
            self.coin_display.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, 'qr_widget'):
            # QR widget — o'ng tomonda, avatar balandligida
            qr_w = 420
            qr_x = self.width() - qr_w - 30
            qr_y = 160
            qr_h = self.height() - qr_y
            self.qr_widget.setGeometry(qr_x, qr_y, qr_w, qr_h)
            self.qr_widget.raise_()

    def start(self, camera_index: int = 0):
        """Kamera va AI ishga tushirish."""
        try:
            from ai.classifier import WasteClassifier
            self.classifier = WasteClassifier()
            logger.info("AI model yuklandi")
        except Exception as e:
            logger.error(f"AI model yuklanmadi: {e}")
            logger.error(f"AI xato: {e}")

        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            logger.error("Kamera ochilmadi!")
            logger.error("Kamera topilmadi")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cam_timer.start(33)
        logger.info("Tayyor! Chiqindini ko'rsating")
        logger.info("Kiosk ishga tushdi")

    def _process_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            return

        self.frame_count += 1
        self.camera_widget.update_frame(frame)

        if self.frame_count % 4 == 0 and self.classifier:
            self._run_detection(frame)

    def _draw_detection_box(self, frame: np.ndarray, x1, y1, x2, y2, label: str, conf: float, color=(76, 175, 80)):
        """Kamera frameda detection box chizish."""
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        # Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        # Rounded corners
        r = 12
        for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            cv2.circle(frame, (cx, cy), r, color, 3)
        # Label background
        text = f"{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.rectangle(frame, (x1, y1 - th - 16), (x1 + tw + 14, y1), color, -1)
        cv2.putText(frame, text, (x1 + 7, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    def _run_detection(self, frame: np.ndarray):
        try:
            from ai.config import YOLO_TO_WASTE, WASTE_CATEGORIES
            from ai.classifier import DetectionResult

            results = self.classifier.model.predict(
                source=frame, conf=0.30, iou=0.45, verbose=False
            )

            waste_found = None

            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    class_name = self.classifier.model.names[class_id]

                    # Person — skip
                    if class_name == "person":
                        continue

                    # Waste detection
                    waste_cat = YOLO_TO_WASTE.get(class_name.lower())
                    if waste_cat and waste_cat in WASTE_CATEGORIES and waste_cat != "unknown":
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        name_uz = WASTE_CATEGORIES[waste_cat]["name_uz"]

                        # Detection box chizish
                        self._draw_detection_box(
                            frame, x1, y1, x2, y2,
                            name_uz, conf,
                            color=(76, 175, 80) if not self._coin_cooldown else (100, 180, 255)
                        )

                        if waste_found is None:
                            waste_found = {
                                "name": name_uz,
                                "category": waste_cat,
                                "confidence": conf,
                            }

            # Detection box chizilgan frameni kamerada yangilash
            self.camera_widget.update_frame(frame)

            # ─── Coin berish (cooldown bilan) ───
            if waste_found and not self._coin_cooldown:
                play_detection_sound()
                self._award_coins(waste_found["name"])

        except Exception as e:
            logger.error(f"Detection xato: {e}")

    def _award_coins(self, waste_name: str):
        """Coin berish — animatsiya ketma-ketligi."""
        self._coin_cooldown = True
        self._cooldown_timer.start(12000)  # 12 sekund cooldown

        # 1. Coin qo'shish
        self.total_ecocoins += COIN_REWARD

        # 2. Katta coin animatsiyasi
        self.coin_display.show_coin(waste_name, COIN_REWARD)

        # 3. Maskot: yeydi → Mazza → Rahmat
        self.mascot.award_coin(waste_name, COIN_REWARD)

        # 4. 3.5 sekunddan keyin QR code + maskot chapga
        self._qr_scheduled = True
        self._qr_delay.start(3500)

        logger.info(f"Coin berildi: {waste_name} → +{COIN_REWARD} (Jami: {self.total_ecocoins})")

    def _show_qr_code(self):
        """QR code ko'rsatish va maskotni chapga surish."""
        if not self._qr_scheduled:
            return
        self._qr_scheduled = False

        # Maskot chapga suriladi
        self.mascot.move_to_left()

        # QR code o'ngdan chiqadi
        self.qr_widget.show_qr()

        # 8 sekunddan keyin maskotni markazga qaytarish
        QTimer.singleShot(8500, self._restore_layout)

    def _restore_layout(self):
        self.mascot.move_to_center()

    def _reset_cooldown(self):
        self._coin_cooldown = False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
        elif event.key() in (Qt.Key.Key_F11, Qt.Key.Key_F):
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == Qt.Key.Key_Space:
            # Debug: qo'lda coin berish
            self._award_coins("Test shisha")

    def closeEvent(self, event):
        self._cam_timer.stop()
        if self.cap:
            self.cap.release()
        logger.info(f"Kiosk yopildi. Jami: {self.total_ecocoins} EcoCoin")
        event.accept()
