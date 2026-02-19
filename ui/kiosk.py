"""
EcoCoin — Kiosk UI (v2).
Katta animatsiyali oyna: kamera, maskot, coin berish, QR code chiqarish.
"""

import cv2
import io
import uuid
import random
import math as _math
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

# Raspberry Pi CSI kamera uchun
_PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    pass

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


class _FlyingCoin:
    """Uchib ketuvchi kichik coin."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-7, -2)
        self.size = random.uniform(18, 35)
        self.life = 1.0
        self.decay = random.uniform(0.008, 0.018)
        self.rot = random.uniform(0, 360)
        self.rot_speed = random.uniform(-4, 4)
        self.glow_phase = random.uniform(0, _math.pi * 2)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.12
        self.life -= self.decay
        self.rot += self.rot_speed
        self.glow_phase += 0.1

    def is_alive(self):
        return self.life > 0


class CoinDisplayWidget(QWidget):
    """Coin berish animatsiyasi — pastda yashil gradient bar + uchuvchi coinlar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._visible = False
        self._phase = 0.0
        self._amount = 5
        self._waste_text = ""
        self._opacity = 0.0
        self._scale = 0.3
        self._flying_coins = []
        self._golden_glow_phase = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(25)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_hide)

        self._hiding = False

    def show_coin(self, waste_name: str, amount: int = 5):
        self._visible = True
        self._hiding = False
        self._amount = amount
        self._waste_text = waste_name
        self._opacity = 0.0
        self._scale = 0.3
        self._phase = 0.0
        self._golden_glow_phase = 0.0

        # Uchuvchi coinlar yaratish
        self._flying_coins = []
        for _ in range(12):
            fx = random.uniform(-60, 60)
            fy = random.uniform(-40, 20)
            self._flying_coins.append(_FlyingCoin(fx, fy))

        self._hide_timer.start(3500)

    def _start_hide(self):
        self._hiding = True

    def _animate(self):
        if not self._visible:
            return

        self._phase += 0.06
        self._golden_glow_phase += 0.08

        if self._hiding:
            self._opacity = max(0, self._opacity - 0.035)
            self._scale = max(0.8, self._scale - 0.01)
            if self._opacity <= 0:
                self._visible = False
        else:
            self._opacity = min(1.0, self._opacity + 0.05)
            self._scale = min(1.0, self._scale + 0.03)

        for fc in self._flying_coins:
            fc.update()
        self._flying_coins = [c for c in self._flying_coins if c.is_alive()]

        self.update()

    def _draw_coin(self, p: QPainter, cx: float, cy: float, sz: float, alpha: int):
        """3D coin chizish."""
        # Glow
        glow_g = QRadialGradient(QPointF(cx, cy), sz * 2.2)
        glow_g.setColorAt(0, QColor(255, 215, 0, alpha // 3))
        glow_g.setColorAt(1, QColor(255, 215, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow_g))
        p.drawEllipse(QPointF(cx, cy), sz * 2.2, sz * 2.2)

        # Coin body
        cg = QRadialGradient(QPointF(cx - sz * 0.15, cy - sz * 0.2), sz * 1.3)
        cg.setColorAt(0, QColor(255, 245, 140, alpha))
        cg.setColorAt(0.4, QColor(255, 215, 0, alpha))
        cg.setColorAt(0.8, QColor(220, 170, 0, alpha))
        cg.setColorAt(1, QColor(180, 130, 0, alpha))
        p.setBrush(QBrush(cg))
        p.setPen(QPen(QColor(180, 130, 0, alpha), 2))
        p.drawEllipse(QPointF(cx, cy), sz, sz)

        # Inner ring
        p.setPen(QPen(QColor(200, 160, 0, alpha // 2), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), sz * 0.72, sz * 0.72)

        # Recycling icon
        p.setPen(QPen(QColor(140, 100, 0, alpha), 2))
        icon_sz = sz * 0.3
        for i in range(3):
            a1 = _math.radians(i * 120 - 90 + self._golden_glow_phase * 15)
            a2 = _math.radians(i * 120 + 30 + self._golden_glow_phase * 15)
            p.drawLine(
                QPointF(cx + _math.cos(a1) * icon_sz, cy + _math.sin(a1) * icon_sz),
                QPointF(cx + _math.cos(a2) * icon_sz, cy + _math.sin(a2) * icon_sz)
            )

        # Highlight
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, alpha // 3)))
        p.drawEllipse(QPointF(cx - sz * 0.2, cy - sz * 0.25), sz * 0.35, sz * 0.25)

    def paintEvent(self, event):
        if not self._visible:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)

        w, h = self.width(), self.height()

        # ── Uchuvchi coinlar — ekran markazida ──
        mcx = w / 2
        mcy = h * 0.42
        for fc in self._flying_coins:
            alpha = int(fc.life * 255)
            self._draw_coin(p, mcx + fc.x, mcy + fc.y, fc.size, alpha)

        # ── Oltin glow — maskot ostida ──
        glow_a = int(50 + 30 * _math.sin(self._golden_glow_phase))
        ground_glow = QRadialGradient(QPointF(mcx, mcy + 100), 200)
        ground_glow.setColorAt(0, QColor(255, 200, 0, glow_a))
        ground_glow.setColorAt(0.5, QColor(255, 180, 0, glow_a // 2))
        ground_glow.setColorAt(1, QColor(255, 150, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(ground_glow))
        p.drawEllipse(QPointF(mcx, mcy + 100), 220, 80)

        # ── Pastdagi bar — "+X EcoCoin berildi!" ──
        bar_h = 80
        bar_w = min(w - 60, 580)
        bar_x = (w - bar_w) / 2
        bar_y = h - bar_h - 20

        p.save()
        bar_scale = 0.5 + self._scale * 0.5
        p.translate(w / 2, bar_y + bar_h / 2)
        p.scale(bar_scale, bar_scale)
        p.translate(-w / 2, -(bar_y + bar_h / 2))

        # Shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 50, 0, 50))
        sh_path = QPainterPath()
        sh_path.addRoundedRect(QRectF(bar_x + 4, bar_y + 5, bar_w, bar_h), 28, 28)
        p.drawPath(sh_path)

        # Outer glow
        glow_rect = QRectF(bar_x - 15, bar_y - 10, bar_w + 30, bar_h + 20)
        outer_glow = QRadialGradient(glow_rect.center(), bar_w * 0.55)
        outer_glow.setColorAt(0, QColor(76, 200, 80, 40))
        outer_glow.setColorAt(1, QColor(76, 175, 80, 0))
        p.setBrush(QBrush(outer_glow))
        p.drawRoundedRect(glow_rect, 35, 35)

        # Bar background — yashil gradient
        bar_grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h)
        bar_grad.setColorAt(0.0, QColor(85, 195, 90, 240))
        bar_grad.setColorAt(0.3, QColor(66, 175, 72, 245))
        bar_grad.setColorAt(0.7, QColor(50, 155, 55, 245))
        bar_grad.setColorAt(1.0, QColor(38, 130, 43, 240))
        p.setBrush(QBrush(bar_grad))
        p.setPen(Qt.PenStyle.NoPen)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 28, 28)
        p.drawPath(bar_path)

        # Highlight — yuqori chiziq
        hl_grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h * 0.4)
        hl_grad.setColorAt(0, QColor(255, 255, 255, 50))
        hl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl_grad))
        hl_path = QPainterPath()
        hl_path.addRoundedRect(QRectF(bar_x + 3, bar_y + 2, bar_w - 6, bar_h * 0.4), 25, 25)
        p.drawPath(hl_path)

        # Border — nozik
        p.setPen(QPen(QColor(100, 220, 110, 120), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bar_path)

        # ── Coin icon chap tomonda ──
        coin_cx = bar_x + 55
        coin_cy = bar_y + bar_h / 2
        coin_sz = 26

        # Mini coin
        mcg = QRadialGradient(QPointF(coin_cx - 3, coin_cy - 4), coin_sz * 1.3)
        mcg.setColorAt(0, QColor(255, 245, 140))
        mcg.setColorAt(0.5, QColor(255, 215, 0))
        mcg.setColorAt(1, QColor(200, 150, 0))
        p.setBrush(QBrush(mcg))
        p.setPen(QPen(QColor(180, 130, 0), 2))
        p.drawEllipse(QPointF(coin_cx, coin_cy), coin_sz, coin_sz)

        # Coin ichidagi +X
        p.setPen(QColor(120, 80, 0))
        cf = QFont("Segoe UI", 16, QFont.Weight.ExtraBold)
        p.setFont(cf)
        p.drawText(QRectF(coin_cx - coin_sz, coin_cy - coin_sz, coin_sz * 2, coin_sz * 2),
                   Qt.AlignmentFlag.AlignCenter, f"+{self._amount}")

        # Coin highlight
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 80)))
        p.drawEllipse(QPointF(coin_cx - 5, coin_cy - 8), 10, 7)

        # ── Matn — "EcoCoin berildi!" ──
        text_x = coin_cx + coin_sz + 15
        text_w = bar_w - (text_x - bar_x) - 20

        # Shadow text
        p.setPen(QColor(0, 60, 0, 100))
        main_font = QFont("Segoe UI", 24, QFont.Weight.ExtraBold)
        p.setFont(main_font)
        p.drawText(QRectF(text_x + 2, bar_y + 2, text_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   "EcoCoin berildi!")

        # Main text
        p.setPen(QColor(255, 255, 255))
        p.setFont(main_font)
        p.drawText(QRectF(text_x, bar_y, text_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   "EcoCoin berildi!")

        p.restore()
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
                background: #060e1e;
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
        self.cap = None          # OpenCV VideoCapture
        self.picam = None        # picamera2 Picamera2
        self._camera_backend = None  # 'picamera' yoki 'opencv'
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
            # QR widget — o'ng tomonda, biroz o'rtaroqda
            qr_w = 420
            qr_x = self.width() - qr_w - 120
            qr_y = 160
            qr_h = self.height() - qr_y
            self.qr_widget.setGeometry(qr_x, qr_y, qr_w, qr_h)
            self.qr_widget.raise_()

    def _is_raspberry_pi(self) -> bool:
        """Raspberry Pi qurilmasida ishlayotganligini tekshirish."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
            return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
        except (FileNotFoundError, PermissionError):
            return False

    def _open_picamera(self) -> bool:
        """Raspberry Pi CSI kamerani picamera2 orqali ochish."""
        try:
            from ai.config import CAMERA_WIDTH, CAMERA_HEIGHT, RPI_CAMERA_HFLIP, RPI_CAMERA_VFLIP
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
            self._camera_backend = "picamera"
            logger.info("RPi CSI kamera ochildi (picamera2)")
            return True
        except Exception as e:
            logger.error(f"RPi kamerani ochib bo'lmadi: {e}")
            return False

    def _read_frame(self):
        """Kameradan kadr o'qish — backend ga qarab."""
        if self._camera_backend == "picamera" and self.picam is not None:
            try:
                frame = self.picam.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            except Exception as e:
                logger.warning(f"RPi kameradan kadr o'qishda xato: {e}")
                return False, None
        else:
            if self.cap is None or not self.cap.isOpened():
                return False, None
            return self.cap.read()

    def start(self, camera_index: int = 0):
        """Kamera va AI ishga tushirish."""
        try:
            from ai.classifier import WasteClassifier
            self.classifier = WasteClassifier()
            logger.info("AI model yuklandi")
        except Exception as e:
            logger.error(f"AI model yuklanmadi: {e}")
            logger.error(f"AI xato: {e}")

        # Avval RPi CSI kamerani sinash, keyin OpenCV ga qaytish
        camera_opened = False
        from ai.config import CAMERA_BACKEND
        use_picamera = (
            CAMERA_BACKEND == "picamera"
            or (CAMERA_BACKEND == "auto" and _PICAMERA2_AVAILABLE and self._is_raspberry_pi())
        )

        if use_picamera:
            camera_opened = self._open_picamera()

        if not camera_opened:
            # OpenCV fallback
            self.cap = cv2.VideoCapture(camera_index)
            if not self.cap.isOpened():
                logger.error("Kamera ochilmadi!")
                logger.error("Kamera topilmadi")
                return
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._camera_backend = "opencv"
            logger.info("OpenCV kamera ochildi")

        self._cam_timer.start(33)
        logger.info(f"Tayyor! Kamera backend: {self._camera_backend}")
        logger.info("Kiosk ishga tushdi")

    def _process_frame(self):
        ret, frame = self._read_frame()
        if not ret or frame is None:
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
        if self.picam:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception:
                pass
        logger.info(f"Kiosk yopildi. Jami: {self.total_ecocoins} EcoCoin")
        event.accept()
