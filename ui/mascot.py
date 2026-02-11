"""
EcoCoin Maskot — 3D Animatsiyali xarakter (v3).
Kosmik tabiat fonida yulduzlar, barglar, coinlar, 3D gradient maskot.
"""

import math
import random
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPainterPath, QFont
)
from PyQt6.QtWidgets import QWidget


# ─── Background elements ───

class BgStar:
    """Yulduzcha — miltillaydi."""
    def __init__(self, x, y, size, speed):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.phase = random.uniform(0, math.pi * 2)
        self.brightness = random.uniform(0.3, 1.0)


class BgLeaf:
    """Suzuvchi barg."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = random.uniform(18, 45)
        self.angle = random.uniform(-30, 30)
        self.sway_phase = random.uniform(0, math.pi * 2)
        self.sway_speed = random.uniform(0.01, 0.03)
        self.side = 1 if x > 0.5 else -1


class BgCoin:
    """Suzuvchi EcoCoin."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = random.uniform(28, 50)
        self.float_phase = random.uniform(0, math.pi * 2)
        self.float_speed = random.uniform(0.015, 0.03)
        self.glow_phase = random.uniform(0, math.pi * 2)


# ─── Particle system ───

class Particle:
    """Kichik yulduzcha / confetti particle."""
    def __init__(self, x, y, color, particle_type="star"):
        self.x = x
        self.y = y
        self.color = color
        self.type = particle_type
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-6, -1)
        self.life = 1.0
        self.decay = random.uniform(0.01, 0.025)
        self.size = random.uniform(4, 12)
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-5, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= self.decay
        self.rotation += self.rot_speed

    def is_alive(self):
        return self.life > 0


class FloatingCoin:
    """Yuqoriga uchib ketuvchi coin animatsiyasi."""
    def __init__(self, x, y, text="+5"):
        self.x = x
        self.y = y
        self.text = text
        self.life = 1.0
        self.decay = 0.012
        self.vy = -2.0
        self.scale = 0.5

    def update(self):
        self.y += self.vy
        self.life -= self.decay
        self.scale = min(1.5, self.scale + 0.03)

    def is_alive(self):
        return self.life > 0


class MascotWidget(QWidget):
    """
    3D Animatsiyali EcoCoin maskoti v3.
    Kosmik tabiat fonida, 3D shading, yulduzlar, barglar, coinlar.
    """

    IDLE_MESSAGES = [
        "Salom! Chiqindini menga olib kel! ♻️",
        "Plastik shishani tashlang — EcoCoin oling! 🪙",
        "Tabiatni asraylik! 🌿",
        "Har bir shisha muhim! 🍶",
        "Keling, birga saralaylik! 💚",
        "EcoCoin yig'ib, sovg'a oling! 🎁",
        "Men chiqindini yaxshi ko'raman! 😋",
        "Menga shisha bering! 🧴",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)

        # Ko'z kuzatuvi
        self._eye_target = QPointF(0.5, 0.5)
        self._eye_current = QPointF(0.5, 0.5)
        self._person_detected = False

        # Animatsiya holatlari
        self._breath_phase = 0.0
        self._wave_phase = 0.0
        self._is_waving = False
        self._blink_timer = 0
        self._is_blinking = False
        self._bounce_offset = 0.0
        self._glow_phase = 0.0

        # Coin holatlari
        self._state = "idle"
        self._state_timer = 0
        self._belly_rub_phase = 0.0
        self._is_rubbing_belly = False
        self._squish = 0.0

        # Particle system
        self._particles = []
        self._floating_coins = []

        # Xabar
        self._message_index = 0
        self._current_message = self.IDLE_MESSAGES[0]
        self._override_message = None
        self._override_timer = 0

        # Maskot pozitsiyasi
        self._mascot_x_offset = 0.0
        self._mascot_x_target = 0.0

        # 3D Ranglar
        self._body_color = QColor(76, 175, 80)
        self._body_dark = QColor(40, 110, 45)
        self._body_light = QColor(160, 220, 160)
        self._eye_white = QColor(255, 255, 255)
        self._eye_pupil = QColor(50, 30, 15)
        self._eye_iris = QColor(90, 60, 35)
        self._mouth_color = QColor(33, 33, 33)
        self._leaf_color = QColor(46, 125, 50)

        # Background elementlar
        self._bg_stars = []
        self._bg_leaves = []
        self._bg_coins = []
        self._bg_initialized = False
        self._bg_phase = 0.0

        # Timers
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(25)

        self._blink_trigger = QTimer(self)
        self._blink_trigger.timeout.connect(self._start_blink)
        self._blink_trigger.start(2500)

        self._wave_trigger = QTimer(self)
        self._wave_trigger.timeout.connect(self._start_wave)
        self._wave_trigger.start(6000)

        self._message_timer = QTimer(self)
        self._message_timer.timeout.connect(self._next_message)
        self._message_timer.start(4000)

    # ─── Public API ───

    def set_person_position(self, x_norm: float, y_norm: float):
        self._eye_target = QPointF(x_norm, y_norm)
        self._person_detected = True
        if not self._is_waving and self._state == "idle":
            self._start_wave()

    def set_no_person(self):
        self._eye_target = QPointF(0.5, 0.5)
        self._person_detected = False

    def award_coin(self, waste_name: str = "Chiqindi", amount: int = 5):
        self._state = "eating"
        self._state_timer = 0
        self._squish = 0.35
        self._override_message = f"😋 Yam-yam! {waste_name} yedim!"
        self._override_timer = 120
        self._spawn_confetti(0, 0, 35)
        self._floating_coins.append(FloatingCoin(
            random.uniform(-30, 30), -100, f"+{amount} 🪙"
        ))

    def move_to_right(self):
        self._mascot_x_target = 180

    def move_to_center(self):
        self._mascot_x_target = 0

    def move_to_left(self):
        self._mascot_x_target = -180

    # ─── Background init ───

    def _init_bg(self):
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return
        self._bg_initialized = True

        self._bg_stars = []
        for _ in range(120):
            self._bg_stars.append(BgStar(
                random.uniform(0, 1), random.uniform(0, 1),
                random.uniform(1, 4), random.uniform(0.02, 0.06)
            ))

        self._bg_leaves = []
        for _ in range(12):
            side = random.choice([0, 1])
            lx = random.uniform(0, 0.15) if side == 0 else random.uniform(0.85, 1.0)
            ly = random.uniform(0.05, 0.85)
            self._bg_leaves.append(BgLeaf(lx, ly))

        self._bg_coins = []
        positions = [
            (0.12, 0.45), (0.88, 0.45),
            (0.08, 0.65), (0.92, 0.65),
            (0.18, 0.30), (0.82, 0.30),
        ]
        for cx, cy in positions:
            self._bg_coins.append(BgCoin(cx, cy))

    # ─── Particle ───

    def _spawn_confetti(self, cx, cy, count=20):
        colors = [
            QColor(255, 215, 0), QColor(76, 175, 80), QColor(33, 150, 243),
            QColor(255, 87, 34), QColor(156, 39, 176), QColor(255, 235, 59),
            QColor(244, 67, 54), QColor(0, 188, 212),
        ]
        for _ in range(count):
            c = random.choice(colors)
            t = random.choice(["star", "circle", "square"])
            self._particles.append(Particle(
                cx + random.uniform(-50, 50),
                cy + random.uniform(-30, 30), c, t
            ))

    # ─── Animatsiya ───

    def _animate(self):
        self._breath_phase += 0.04
        if self._breath_phase > 2 * math.pi:
            self._breath_phase -= 2 * math.pi

        self._glow_phase += 0.03
        if self._glow_phase > 2 * math.pi:
            self._glow_phase -= 2 * math.pi

        self._bg_phase += 0.02

        lerp = 0.08
        cx = self._eye_current.x() + (self._eye_target.x() - self._eye_current.x()) * lerp
        cy = self._eye_current.y() + (self._eye_target.y() - self._eye_current.y()) * lerp
        self._eye_current = QPointF(cx, cy)

        if self._is_waving:
            self._wave_phase += 0.15
            if self._wave_phase > math.pi * 4:
                self._is_waving = False
                self._wave_phase = 0.0

        if self._is_blinking:
            self._blink_timer += 1
            if self._blink_timer > 6:
                self._is_blinking = False
                self._blink_timer = 0

        if self._state == "happy":
            self._bounce_offset = math.sin(self._state_timer * 0.3) * 15
        elif self._person_detected and self._state == "idle":
            self._bounce_offset = math.sin(self._breath_phase * 2) * 5
        else:
            self._bounce_offset *= 0.9

        self._squish *= 0.92

        # STATE MACHINE
        if self._state == "eating":
            self._state_timer += 1
            if self._state_timer > 45:
                self._state = "happy"
                self._state_timer = 0
                self._is_rubbing_belly = True
                self._belly_rub_phase = 0.0
                self._override_message = "😊 Mazza! Qornim to'ydi!"
                self._override_timer = 90
                self._spawn_confetti(0, 50, 20)

        elif self._state == "happy":
            self._state_timer += 1
            self._belly_rub_phase += 0.12
            if self._state_timer > 90:
                self._state = "thanking"
                self._state_timer = 0
                self._is_rubbing_belly = False
                self._override_message = "🙏 Katta rahmat! Tabiat sizga minnatdor!"
                self._override_timer = 110
                self._start_wave()

        elif self._state == "thanking":
            self._state_timer += 1
            if self._state_timer > 110:
                self._state = "idle"
                self._state_timer = 0
                self._override_message = None

        if self._override_timer > 0:
            self._override_timer -= 1
            if self._override_timer <= 0:
                self._override_message = None

        self._mascot_x_offset += (self._mascot_x_target - self._mascot_x_offset) * 0.05

        for pt in self._particles:
            pt.update()
        self._particles = [pt for pt in self._particles if pt.is_alive()]

        for fc in self._floating_coins:
            fc.update()
        self._floating_coins = [fc for fc in self._floating_coins if fc.is_alive()]

        for lf in self._bg_leaves:
            lf.sway_phase += lf.sway_speed
            lf.angle = math.sin(lf.sway_phase) * 15

        self.update()

    def _start_blink(self):
        self._is_blinking = True
        self._blink_timer = 0

    def _start_wave(self):
        self._is_waving = True
        self._wave_phase = 0.0

    def _next_message(self):
        if self._override_message is None:
            self._message_index = (self._message_index + 1) % len(self.IDLE_MESSAGES)
            self._current_message = self.IDLE_MESSAGES[self._message_index]

    # ═══════════════════════════════════════
    # MAIN PAINT
    # ═══════════════════════════════════════

    def paintEvent(self, event):
        if not self._bg_initialized:
            self._init_bg()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. BACKGROUND
        self._draw_background(p, w, h)

        # 2. MASCOT
        mcx = w / 2 + self._mascot_x_offset
        mcy = h / 2 + self._bounce_offset

        scale = min(w, h) / 500.0
        p.translate(mcx, mcy)
        p.scale(scale, scale)

        breath = math.sin(self._breath_phase) * 3

        self._draw_particles(p)
        self._draw_ground_shadow(p, breath)
        self._draw_3d_glow(p)
        self._draw_3d_body(p, breath)
        self._draw_3d_feet(p, breath)
        self._draw_3d_arms(p)
        self._draw_3d_leaf(p, breath)
        self._draw_3d_eyes(p)
        self._draw_cheeks(p)
        self._draw_mouth(p)
        self._draw_recycling_symbol(p)
        self._draw_floating_coins(p)

        if self._state in ("happy", "eating"):
            self._draw_sparkles(p)

        p.resetTransform()
        self._draw_message_bubble(p, w, h)
        p.end()

    # ═══════════════════════════════════════
    # BACKGROUND
    # ═══════════════════════════════════════

    def _draw_background(self, p: QPainter, w: int, h: int):
        # Kosmik gradient fon
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(6, 14, 30))
        bg.setColorAt(0.3, QColor(8, 22, 48))
        bg.setColorAt(0.55, QColor(10, 35, 60))
        bg.setColorAt(0.75, QColor(12, 50, 45))
        bg.setColorAt(1.0, QColor(8, 30, 25))
        p.fillRect(0, 0, w, h, QBrush(bg))

        # Yulduzlar
        for star in self._bg_stars:
            star.phase += star.speed
            alpha = int((0.4 + 0.6 * abs(math.sin(star.phase))) * star.brightness * 255)
            alpha = max(0, min(255, alpha))
            sx = star.x * w
            sy = star.y * h
            sz = star.size

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(200, 230, 255, alpha // 3)))
            p.drawEllipse(QPointF(sx, sy), sz * 3, sz * 3)

            p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            p.drawEllipse(QPointF(sx, sy), sz, sz)

            if star.size > 2.5 and star.brightness > 0.7:
                cross_alpha = alpha // 2
                p.setPen(QPen(QColor(200, 230, 255, cross_alpha), 0.8))
                ext = sz * 4
                p.drawLine(QPointF(sx - ext, sy), QPointF(sx + ext, sy))
                p.drawLine(QPointF(sx, sy - ext), QPointF(sx, sy + ext))
                p.setPen(Qt.PenStyle.NoPen)

        # Ufq glow
        horizon_y = h * 0.68
        horizon_glow = QLinearGradient(0, horizon_y - 80, 0, horizon_y + 40)
        horizon_glow.setColorAt(0, QColor(0, 200, 150, 0))
        horizon_glow.setColorAt(0.4, QColor(0, 180, 120, 30))
        horizon_glow.setColorAt(0.7, QColor(0, 150, 100, 50))
        horizon_glow.setColorAt(1, QColor(0, 100, 70, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(horizon_glow))
        glow_path = QPainterPath()
        glow_path.moveTo(-w * 0.1, horizon_y + 60)
        glow_path.quadTo(w * 0.5, horizon_y - 100, w * 1.1, horizon_y + 60)
        glow_path.lineTo(w * 1.1, horizon_y + 120)
        glow_path.lineTo(-w * 0.1, horizon_y + 120)
        glow_path.closeSubpath()
        p.drawPath(glow_path)

        # Ufq liniyasi
        p.setPen(QPen(QColor(0, 200, 150, 80), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc_line = QPainterPath()
        arc_line.moveTo(-w * 0.1, horizon_y + 20)
        arc_line.quadTo(w * 0.5, horizon_y - 50, w * 1.1, horizon_y + 20)
        p.drawPath(arc_line)

        # Barglar
        for lf in self._bg_leaves:
            self._draw_bg_leaf(p, lf, w, h)

        # Coinlar
        for coin in self._bg_coins:
            self._draw_bg_coin(p, coin, w, h)

    def _draw_bg_leaf(self, p: QPainter, lf: BgLeaf, w: int, h: int):
        lx = lf.x * w
        ly = lf.y * h
        sz = lf.size

        p.save()
        p.translate(lx, ly)
        p.rotate(lf.angle)

        leaf_grad = QLinearGradient(0, -sz, 0, sz)
        leaf_grad.setColorAt(0, QColor(60, 160, 60, 200))
        leaf_grad.setColorAt(0.5, QColor(40, 130, 50, 220))
        leaf_grad.setColorAt(1, QColor(30, 100, 40, 180))

        p.setBrush(QBrush(leaf_grad))
        p.setPen(QPen(QColor(25, 90, 35, 150), 1))

        path = QPainterPath()
        path.moveTo(0, -sz)
        path.cubicTo(-sz * 0.6, -sz * 0.3, -sz * 0.5, sz * 0.3, 0, sz)
        path.cubicTo(sz * 0.5, sz * 0.3, sz * 0.6, -sz * 0.3, 0, -sz)
        p.drawPath(path)

        # Tomirlar
        p.setPen(QPen(QColor(25, 80, 30, 100), 1))
        p.drawLine(QPointF(0, -sz * 0.8), QPointF(0, sz * 0.8))
        for vy in [-0.4, 0, 0.4]:
            p.drawLine(QPointF(0, sz * vy), QPointF(-sz * 0.25, sz * (vy - 0.15)))
            p.drawLine(QPointF(0, sz * vy), QPointF(sz * 0.25, sz * (vy - 0.15)))

        p.restore()

    def _draw_bg_coin(self, p: QPainter, coin: BgCoin, w: int, h: int):
        coin.float_phase += coin.float_speed
        coin.glow_phase += 0.04

        cx = coin.x * w
        cy = coin.y * h + math.sin(coin.float_phase) * 12
        sz = coin.size

        p.save()
        p.translate(cx, cy)

        # Glow
        glow_alpha = int(40 + 25 * math.sin(coin.glow_phase))
        glow = QRadialGradient(0, 0, sz * 2)
        glow.setColorAt(0, QColor(255, 215, 0, glow_alpha))
        glow.setColorAt(1, QColor(255, 215, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(0, 0), sz * 2, sz * 2)

        # Body
        coin_grad = QRadialGradient(QPointF(-sz * 0.2, -sz * 0.3), sz * 1.3)
        coin_grad.setColorAt(0, QColor(255, 245, 140))
        coin_grad.setColorAt(0.4, QColor(255, 215, 0))
        coin_grad.setColorAt(0.8, QColor(220, 170, 0))
        coin_grad.setColorAt(1, QColor(180, 130, 0))
        p.setBrush(QBrush(coin_grad))
        p.setPen(QPen(QColor(180, 130, 0, 180), 2))
        p.drawEllipse(QPointF(0, 0), sz, sz)

        # Inner ring
        p.setPen(QPen(QColor(200, 160, 0, 120), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), sz * 0.75, sz * 0.75)

        # Recycling icon
        p.setPen(QPen(QColor(120, 90, 0, 180), 2))
        icon_sz = sz * 0.35
        for i in range(3):
            a = math.radians(i * 120 - 90 + self._bg_phase * 20)
            ax = math.cos(a) * icon_sz
            ay = math.sin(a) * icon_sz
            a2 = math.radians(i * 120 + 30 + self._bg_phase * 20)
            ax2 = math.cos(a2) * icon_sz
            ay2 = math.sin(a2) * icon_sz
            p.drawLine(QPointF(ax, ay), QPointF(ax2, ay2))

        # Highlight
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 80)))
        p.drawEllipse(QPointF(-sz * 0.2, -sz * 0.3), sz * 0.35, sz * 0.25)

        p.restore()

    # ═══════════════════════════════════════
    # 3D MASCOT
    # ═══════════════════════════════════════

    def _draw_ground_shadow(self, p: QPainter, breath):
        p.setPen(Qt.PenStyle.NoPen)

        # Oltin glow — coin holatlari uchun
        if self._state in ("eating", "happy", "thanking"):
            glow_a = int(60 + 30 * math.sin(self._glow_phase * 2))
            golden = QRadialGradient(QPointF(0, 155 + breath), 180)
            golden.setColorAt(0, QColor(255, 200, 0, glow_a))
            golden.setColorAt(0.4, QColor(255, 180, 0, glow_a // 2))
            golden.setColorAt(0.7, QColor(200, 150, 0, glow_a // 4))
            golden.setColorAt(1, QColor(150, 120, 0, 0))
            p.setBrush(QBrush(golden))
            p.drawEllipse(QPointF(0, 155 + breath), 180, 60)

        # Oddiy soya
        sh_grad = QRadialGradient(QPointF(0, 165 + breath), 130)
        sh_grad.setColorAt(0, QColor(0, 0, 0, 60))
        sh_grad.setColorAt(0.7, QColor(0, 0, 0, 20))
        sh_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(sh_grad))
        p.drawEllipse(QPointF(0, 165 + breath), 140, 30)

    def _draw_3d_glow(self, p: QPainter):
        glow_r = 200 + math.sin(self._glow_phase) * 25
        glow_alpha = 35 + int(math.sin(self._glow_phase) * 20)
        if self._state in ("happy", "thanking"):
            glow_alpha = 70 + int(math.sin(self._glow_phase * 2) * 35)
            glow_r = 260
        glow_grad = QRadialGradient(0, 10, glow_r)
        glow_grad.setColorAt(0, QColor(100, 220, 110, glow_alpha))
        glow_grad.setColorAt(0.5, QColor(60, 180, 80, glow_alpha // 2))
        glow_grad.setColorAt(1, QColor(40, 150, 60, 0))
        p.setBrush(QBrush(glow_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, 10), glow_r, glow_r)

    def _draw_3d_body(self, p: QPainter, breath):
        body_rx = 120 + breath + self._squish * 30
        body_ry = 130 + breath - self._squish * 20

        # Asosiy tana — ko'p qatlamli gradient
        body_grad = QRadialGradient(QPointF(-25, -30), body_rx * 1.5)
        body_grad.setColorAt(0.0, QColor(170, 235, 170))
        body_grad.setColorAt(0.25, QColor(130, 210, 135))
        body_grad.setColorAt(0.5, QColor(76, 175, 80))
        body_grad.setColorAt(0.75, QColor(56, 142, 60))
        body_grad.setColorAt(1.0, QColor(35, 100, 40))
        p.setBrush(QBrush(body_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, 20), body_rx, body_ry)

        # Kontur
        p.setPen(QPen(QColor(30, 90, 35, 120), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 20), body_rx, body_ry)

        # Highlight — yuqori chap
        hl_grad = QRadialGradient(QPointF(-35, -25), body_rx * 0.7)
        hl_grad.setColorAt(0, QColor(220, 255, 220, 120))
        hl_grad.setColorAt(0.3, QColor(180, 240, 180, 60))
        hl_grad.setColorAt(1, QColor(130, 210, 130, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hl_grad))
        p.drawEllipse(QPointF(-30, -10), body_rx * 0.65, body_ry * 0.55)

        # Rim light — pastki o'ng
        rim_grad = QRadialGradient(QPointF(50, 80), body_rx * 0.8)
        rim_grad.setColorAt(0, QColor(100, 230, 120, 0))
        rim_grad.setColorAt(0.6, QColor(100, 230, 120, 0))
        rim_grad.setColorAt(0.85, QColor(100, 230, 120, 50))
        rim_grad.setColorAt(1, QColor(100, 230, 120, 0))
        p.setBrush(QBrush(rim_grad))
        p.drawEllipse(QPointF(0, 20), body_rx + 3, body_ry + 3)

        # Qorin gradient
        belly_grad = QRadialGradient(QPointF(0, 55), 70)
        belly_grad.setColorAt(0, QColor(100, 195, 105, 60))
        belly_grad.setColorAt(1, QColor(60, 160, 70, 0))
        p.setBrush(QBrush(belly_grad))
        p.drawEllipse(QPointF(0, 55), 65, 55)

    def _draw_3d_feet(self, p: QPainter, breath):
        foot_y = 145 + breath
        for fx in [-50, 50]:
            # Soya
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, 25)))
            p.drawEllipse(QPointF(fx, foot_y + 6), 32, 12)

            foot_grad = QRadialGradient(QPointF(fx - 5, foot_y - 5), 38)
            foot_grad.setColorAt(0, QColor(120, 200, 125))
            foot_grad.setColorAt(0.5, QColor(76, 175, 80))
            foot_grad.setColorAt(1, QColor(40, 110, 45))
            p.setBrush(QBrush(foot_grad))
            p.setPen(QPen(QColor(35, 100, 40, 100), 1.5))
            p.drawEllipse(QPointF(fx, foot_y), 30, 20)

            # Highlight
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(200, 255, 200, 60)))
            p.drawEllipse(QPointF(fx - 5, foot_y - 6), 14, 8)

    def _draw_3d_arms(self, p: QPainter):
        # Chap qo'l
        p.save()
        if self._is_rubbing_belly:
            bx = -50 + math.sin(self._belly_rub_phase) * 30
            by = 60 + math.cos(self._belly_rub_phase) * 10
            p.translate(bx, by)
            p.rotate(math.sin(self._belly_rub_phase) * 10)
        else:
            p.translate(-118, -10)

        arm_grad = QRadialGradient(QPointF(-5, -5), 30)
        arm_grad.setColorAt(0, QColor(130, 210, 135))
        arm_grad.setColorAt(0.6, QColor(76, 175, 80))
        arm_grad.setColorAt(1, QColor(45, 120, 50))
        p.setBrush(QBrush(arm_grad))
        p.setPen(QPen(QColor(35, 100, 40, 80), 1.5))
        p.drawEllipse(QPointF(0, 0), 27, 20)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(200, 255, 200, 70)))
        p.drawEllipse(QPointF(-5, -6), 12, 8)
        p.restore()

        # O'ng qo'l
        p.save()
        if self._is_rubbing_belly:
            bx2 = 50 + math.sin(self._belly_rub_phase + 1) * 25
            by2 = 55 + math.cos(self._belly_rub_phase + 1) * 10
            p.translate(bx2, by2)
            p.rotate(math.sin(self._belly_rub_phase + 1) * -10)
        else:
            wave_angle = math.sin(self._wave_phase) * 35 if self._is_waving else 0
            p.translate(118, -10)
            p.rotate(wave_angle)

        arm_grad2 = QRadialGradient(QPointF(5, -5), 30)
        arm_grad2.setColorAt(0, QColor(130, 210, 135))
        arm_grad2.setColorAt(0.6, QColor(76, 175, 80))
        arm_grad2.setColorAt(1, QColor(45, 120, 50))
        p.setBrush(QBrush(arm_grad2))
        p.setPen(QPen(QColor(35, 100, 40, 80), 1.5))
        p.drawEllipse(QPointF(0, 0), 27, 20)

        if self._is_waving and not self._is_rubbing_belly:
            kaft_grad = QRadialGradient(QPointF(20, -15), 18)
            kaft_grad.setColorAt(0, QColor(160, 230, 165))
            kaft_grad.setColorAt(1, QColor(76, 175, 80))
            p.setBrush(QBrush(kaft_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(22, -16), 15, 15)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(200, 255, 200, 70)))
        p.drawEllipse(QPointF(5, -6), 12, 8)
        p.restore()

    def _draw_3d_leaf(self, p: QPainter, breath):
        p.save()
        p.translate(0, -135 - breath)

        leaf_sway = math.sin(self._breath_phase * 1.5) * 8
        if self._state == "happy":
            leaf_sway = math.sin(self._state_timer * 0.4) * 20
        p.rotate(leaf_sway)

        # Soya
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(20, 60, 20, 60)))
        sp = QPainterPath()
        sp.moveTo(2, 3)
        sp.cubicTo(-10, -22, -18, -37, 2, -52)
        sp.cubicTo(22, -37, 14, -22, 2, 3)
        p.drawPath(sp)

        # Barg gradient
        leaf_grad = QLinearGradient(QPointF(-15, 0), QPointF(15, -55))
        leaf_grad.setColorAt(0, QColor(56, 142, 60))
        leaf_grad.setColorAt(0.3, QColor(46, 125, 50))
        leaf_grad.setColorAt(0.6, QColor(76, 175, 80))
        leaf_grad.setColorAt(1, QColor(100, 200, 100))
        p.setBrush(QBrush(leaf_grad))
        p.setPen(QPen(QColor(27, 94, 32), 2))

        path = QPainterPath()
        path.moveTo(0, 0)
        path.cubicTo(-14, -25, -22, -42, 0, -58)
        path.cubicTo(22, -42, 14, -25, 0, 0)
        p.drawPath(path)

        # Highlight
        p.setPen(Qt.PenStyle.NoPen)
        hl = QRadialGradient(QPointF(5, -30), 20)
        hl.setColorAt(0, QColor(150, 230, 150, 80))
        hl.setColorAt(1, QColor(100, 200, 100, 0))
        p.setBrush(QBrush(hl))
        p.drawEllipse(QPointF(5, -30), 12, 18)

        # Tomirlar
        p.setPen(QPen(QColor(27, 94, 32, 120), 1.2))
        p.drawLine(QPointF(0, -5), QPointF(0, -48))
        p.drawLine(QPointF(0, -20), QPointF(-8, -14))
        p.drawLine(QPointF(0, -20), QPointF(8, -14))
        p.drawLine(QPointF(0, -35), QPointF(-7, -28))
        p.drawLine(QPointF(0, -35), QPointF(7, -28))

        # Poya
        p.setPen(QPen(QColor(60, 110, 45), 3))
        p.drawLine(QPointF(0, 0), QPointF(0, 12))

        p.restore()

    def _draw_3d_eyes(self, p: QPainter):
        eye_y = -25
        for ex in [-40, 40]:
            if self._is_blinking or (self._state == "happy" and self._is_rubbing_belly):
                p.setPen(QPen(self._eye_pupil, 3.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                hp = QPainterPath()
                hp.moveTo(ex - 22, eye_y)
                hp.cubicTo(ex - 12, eye_y - 18, ex + 12, eye_y - 18, ex + 22, eye_y)
                p.drawPath(hp)
            else:
                # Ko'z oqi — gradient
                eye_bg = QRadialGradient(QPointF(ex - 3, eye_y - 5), 35)
                eye_bg.setColorAt(0, QColor(255, 255, 255))
                eye_bg.setColorAt(0.8, QColor(240, 240, 245))
                eye_bg.setColorAt(1, QColor(210, 215, 220))
                p.setBrush(QBrush(eye_bg))
                p.setPen(QPen(QColor(180, 185, 190), 2))
                p.drawEllipse(QPointF(ex, eye_y), 28, 30)

                pdx = (self._eye_current.x() - 0.5) * 16
                pdy = (self._eye_current.y() - 0.5) * 10
                iris_x = ex + pdx
                iris_y = eye_y + pdy

                iris_sz = 18 if self._state == "eating" else 14
                pupil_sz = 9 if self._state == "eating" else 7

                # Iris
                ig = QRadialGradient(QPointF(iris_x - 2, iris_y - 3), iris_sz + 4)
                ig.setColorAt(0.0, QColor(140, 95, 60))
                ig.setColorAt(0.3, QColor(110, 70, 40))
                ig.setColorAt(0.7, self._eye_iris)
                ig.setColorAt(0.9, QColor(40, 25, 15))
                ig.setColorAt(1.0, QColor(20, 12, 8))
                p.setBrush(QBrush(ig))
                p.setPen(QPen(QColor(30, 20, 10, 120), 1))
                p.drawEllipse(QPointF(iris_x, iris_y), iris_sz, iris_sz + 1)

                # Pupil
                pg = QRadialGradient(QPointF(iris_x - 1, iris_y - 1), pupil_sz + 2)
                pg.setColorAt(0, QColor(10, 5, 0))
                pg.setColorAt(0.8, self._eye_pupil)
                pg.setColorAt(1, QColor(30, 20, 10))
                p.setBrush(QBrush(pg))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(iris_x, iris_y), pupil_sz, pupil_sz + 1)

                # Yaltiroqlar
                p.setBrush(QBrush(QColor(255, 255, 255, 230)))
                p.drawEllipse(QPointF(iris_x - 4, iris_y - 5), 5, 5)
                p.setBrush(QBrush(QColor(255, 255, 255, 140)))
                p.drawEllipse(QPointF(iris_x + 3, iris_y + 3), 2.5, 2.5)

                # Qaboq soyasi
                shadow_grad = QLinearGradient(QPointF(ex, eye_y - 30), QPointF(ex, eye_y - 10))
                shadow_grad.setColorAt(0, QColor(40, 100, 45, 40))
                shadow_grad.setColorAt(1, QColor(40, 100, 45, 0))
                p.setBrush(QBrush(shadow_grad))
                p.drawEllipse(QPointF(ex, eye_y - 15), 26, 15)

    def _draw_cheeks(self, p: QPainter):
        p.setPen(Qt.PenStyle.NoPen)
        ch_a = 180 if self._state in ("happy", "thanking") else 100
        for cx_pos in [-70, 70]:
            cg = QRadialGradient(QPointF(cx_pos, 15), 22)
            cg.setColorAt(0, QColor(255, 130, 120, ch_a))
            cg.setColorAt(1, QColor(255, 130, 120, 0))
            p.setBrush(QBrush(cg))
            p.drawEllipse(QPointF(cx_pos, 15), 22, 16)

    def _draw_mouth(self, p: QPainter):
        mouth_y = 30
        if self._state == "eating":
            p.setPen(QPen(QColor(40, 20, 10), 2.5))
            mg = QRadialGradient(QPointF(0, mouth_y + 5), 25)
            mg.setColorAt(0, QColor(170, 20, 20, 220))
            mg.setColorAt(1, QColor(120, 15, 15, 200))
            p.setBrush(QBrush(mg))
            oa = abs(math.sin(self._state_timer * 0.3)) * 20
            p.drawEllipse(QPointF(0, mouth_y + 5), 22, 10 + oa)
        elif self._state == "happy":
            p.setPen(QPen(self._mouth_color, 2.5))
            mg = QLinearGradient(QPointF(0, mouth_y), QPointF(0, mouth_y + 35))
            mg.setColorAt(0, QColor(239, 83, 80, 220))
            mg.setColorAt(1, QColor(200, 50, 50, 180))
            p.setBrush(QBrush(mg))
            mp = QPainterPath()
            mp.moveTo(-35, mouth_y - 5)
            mp.cubicTo(-18, mouth_y + 40, 18, mouth_y + 40, 35, mouth_y - 5)
            mp.cubicTo(18, mouth_y + 18, -18, mouth_y + 18, -35, mouth_y - 5)
            p.drawPath(mp)
        elif self._state == "thanking":
            p.setPen(QPen(self._mouth_color, 2.5))
            p.setBrush(QBrush(QColor(239, 83, 80, 160)))
            mp = QPainterPath()
            mp.moveTo(-28, mouth_y)
            mp.cubicTo(-14, mouth_y + 30, 14, mouth_y + 30, 28, mouth_y)
            mp.cubicTo(14, mouth_y + 12, -14, mouth_y + 12, -28, mouth_y)
            p.drawPath(mp)
        elif self._person_detected:
            p.setPen(QPen(self._mouth_color, 2.5))
            p.setBrush(QBrush(QColor(239, 83, 80, 190)))
            mp = QPainterPath()
            mp.moveTo(-30, mouth_y)
            mp.cubicTo(-15, mouth_y + 35, 15, mouth_y + 35, 30, mouth_y)
            mp.cubicTo(15, mouth_y + 15, -15, mouth_y + 15, -30, mouth_y)
            p.drawPath(mp)
        else:
            p.setPen(QPen(self._mouth_color, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            mp = QPainterPath()
            mp.moveTo(-22, mouth_y)
            mp.cubicTo(-10, mouth_y + 20, 10, mouth_y + 20, 22, mouth_y)
            p.drawPath(mp)

    def _draw_recycling_symbol(self, p: QPainter):
        if self._is_rubbing_belly:
            return
        p.save()
        p.translate(0, 70)
        p.scale(0.65, 0.65)
        rot_speed = self._breath_phase * 5
        if self._state in ("happy", "thanking"):
            rot_speed = self._state_timer * 3
        p.setPen(QPen(QColor(255, 255, 255, 170), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            p.save()
            p.rotate(i * 120 + rot_speed)
            arrow = QPainterPath()
            arrow.moveTo(0, -22)
            arrow.lineTo(10, -10)
            arrow.lineTo(5, -10)
            arrow.lineTo(5, 5)
            arrow.lineTo(-5, 5)
            arrow.lineTo(-5, -10)
            arrow.lineTo(-10, -10)
            arrow.closeSubpath()
            p.drawPath(arrow)
            p.restore()
        p.restore()

    # ═══════════════════════════════════════
    # EFFECTS
    # ═══════════════════════════════════════

    def _draw_particles(self, p: QPainter):
        for pt in self._particles:
            alpha = int(pt.life * 255)
            color = QColor(pt.color.red(), pt.color.green(), pt.color.blue(), alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.save()
            p.translate(pt.x, pt.y)
            p.rotate(pt.rotation)
            s = pt.size * pt.life
            if pt.type == "circle":
                p.drawEllipse(QPointF(0, 0), s, s)
            elif pt.type == "square":
                p.drawRect(QRectF(-s / 2, -s / 2, s, s))
            else:
                path = QPainterPath()
                for i in range(5):
                    a = math.radians(i * 72 - 90)
                    ia = math.radians(i * 72 - 90 + 36)
                    ox, oy = math.cos(a) * s, math.sin(a) * s
                    ix, iy = math.cos(ia) * s * 0.4, math.sin(ia) * s * 0.4
                    if i == 0:
                        path.moveTo(ox, oy)
                    else:
                        path.lineTo(ox, oy)
                    path.lineTo(ix, iy)
                path.closeSubpath()
                p.drawPath(path)
            p.restore()

    def _draw_floating_coins(self, p: QPainter):
        for fc in self._floating_coins:
            alpha = int(fc.life * 255)
            sz = int(22 * fc.scale)
            font = QFont("Segoe UI", sz, QFont.Weight.Bold)
            p.setFont(font)

            p.save()
            p.setPen(QColor(0, 0, 0, alpha // 3))
            p.drawText(QPointF(fc.x - 38, fc.y + 2), fc.text)
            p.restore()

            p.setPen(QColor(255, 215, 0, alpha))
            p.drawText(QPointF(fc.x - 40, fc.y), fc.text)

    def _draw_sparkles(self, p: QPainter):
        t = self._state_timer * 0.1
        for i in range(10):
            angle = t + i * (math.pi / 5)
            dist = 150 + math.sin(t * 2 + i) * 25
            sx = math.cos(angle) * dist
            sy = math.sin(angle) * dist
            size = 5 + math.sin(t * 3 + i * 2) * 3
            alpha = 160 + int(math.sin(t * 4 + i) * 95)
            alpha = max(0, min(255, alpha))

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 235, 59, alpha // 3)))
            p.drawEllipse(QPointF(sx, sy), size * 2.5, size * 2.5)

            p.setBrush(QBrush(QColor(255, 235, 59, alpha)))
            p.drawEllipse(QPointF(sx, sy), size, size)
            p.setBrush(QBrush(QColor(255, 255, 255, alpha // 2)))
            p.drawEllipse(QPointF(sx, sy), size * 0.5, size * 0.5)

    def _draw_message_bubble(self, p: QPainter, w: int, h: int):
        msg = self._override_message or self._current_message
        bubble_h = 75
        bubble_w = min(w - 40, 620)
        bx = (w - bubble_w) / 2
        by = h - bubble_h - 15

        # Shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        sp = QPainterPath()
        sp.addRoundedRect(QRectF(bx + 5, by + 5, bubble_w, bubble_h), 28, 28)
        p.drawPath(sp)

        # Background
        if self._state in ("happy", "eating"):
            # Oltin-yashil gradient — coin holati uchun
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0.0, QColor(85, 195, 90, 240))
            bg.setColorAt(0.3, QColor(66, 175, 72, 245))
            bg.setColorAt(0.7, QColor(50, 155, 55, 245))
            bg.setColorAt(1.0, QColor(38, 130, 43, 240))
        elif self._state == "thanking":
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0.0, QColor(75, 190, 85, 240))
            bg.setColorAt(0.5, QColor(56, 160, 65, 245))
            bg.setColorAt(1.0, QColor(40, 135, 48, 240))
        else:
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0, QColor(255, 255, 255, 230))
            bg.setColorAt(1, QColor(232, 245, 233, 230))
        p.setBrush(QBrush(bg))

        bp = QPainterPath()
        bp.addRoundedRect(QRectF(bx, by, bubble_w, bubble_h), 28, 28)
        p.drawPath(bp)

        # Highlight — yuqori qism
        if self._state in ("happy", "eating", "thanking"):
            hl = QLinearGradient(bx, by, bx, by + bubble_h * 0.4)
            hl.setColorAt(0, QColor(255, 255, 255, 45))
            hl.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(hl))
            hl_p = QPainterPath()
            hl_p.addRoundedRect(QRectF(bx + 3, by + 2, bubble_w - 6, bubble_h * 0.4), 25, 25)
            p.drawPath(hl_p)

        # Border
        if self._state in ("happy", "eating", "thanking"):
            bc = QColor(100, 220, 110, 120)
        else:
            bc = QColor(76, 175, 80, 150)
        p.setPen(QPen(bc, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bp)

        # Text
        if self._state in ("happy", "eating", "thanking"):
            # Oq matn — yashil fonda
            # Shadow
            p.setPen(QColor(0, 60, 0, 90))
            font = QFont("Segoe UI", 18)
            font.setBold(True)
            p.setFont(font)
            p.drawText(QRectF(bx + 2, by + 2, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, msg)
            # Main
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(bx, by, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, msg)
        else:
            p.setPen(QColor(33, 33, 33))
            font = QFont("Segoe UI", 18)
            font.setBold(True)
            p.setFont(font)
            p.drawText(QRectF(bx, by, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, msg)
