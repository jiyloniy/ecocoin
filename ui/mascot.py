"""
EcoCoin Maskot — Animatsiyali xarakter (v2).
Psixologik jalb qilish: ko'z kuzatuvi, qorin silash, xursandchilik, particle effektlar.
"""

import math
import random
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPainterPath, QFont
)
from PyQt6.QtWidgets import QWidget


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
        self.vy += 0.15  # gravity
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
    Animatsiyali EcoCoin maskoti v2.
    Holatlar: idle → eating → happy (qorin silash, "Mazza!") → thanking ("Katta rahmat!")
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
        self._state = "idle"  # idle | eating | happy | thanking
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

        # Maskot pozitsiyasi (chapga-o'ngga)
        self._mascot_x_offset = 0.0
        self._mascot_x_target = 0.0

        # Ranglar
        self._body_color = QColor(76, 175, 80)
        self._body_dark = QColor(56, 142, 60)
        self._body_light = QColor(129, 199, 132)
        self._eye_white = QColor(255, 255, 255)
        self._eye_pupil = QColor(33, 33, 33)
        self._eye_iris = QColor(76, 50, 30)
        self._cheek_color = QColor(255, 138, 128, 90)
        self._mouth_color = QColor(33, 33, 33)
        self._leaf_color = QColor(46, 125, 50)

        # Timers
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(25)  # 40 fps

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
        """Coin berilganda: yeydi → qorin silaydi → Mazza! → Katta rahmat!"""
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

        # Ko'z smooth lerp
        lerp = 0.08
        cx = self._eye_current.x() + (self._eye_target.x() - self._eye_current.x()) * lerp
        cy = self._eye_current.y() + (self._eye_target.y() - self._eye_current.y()) * lerp
        self._eye_current = QPointF(cx, cy)

        # Wave
        if self._is_waving:
            self._wave_phase += 0.15
            if self._wave_phase > math.pi * 4:
                self._is_waving = False
                self._wave_phase = 0.0

        # Blink
        if self._is_blinking:
            self._blink_timer += 1
            if self._blink_timer > 6:
                self._is_blinking = False
                self._blink_timer = 0

        # Bounce
        if self._state == "happy":
            self._bounce_offset = math.sin(self._state_timer * 0.3) * 15
        elif self._person_detected and self._state == "idle":
            self._bounce_offset = math.sin(self._breath_phase * 2) * 5
        else:
            self._bounce_offset *= 0.9

        # Squish
        self._squish *= 0.92

        # ─── STATE MACHINE ───
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

        # Override message timer
        if self._override_timer > 0:
            self._override_timer -= 1
            if self._override_timer <= 0:
                self._override_message = None

        # X pozitsiya smooth
        self._mascot_x_offset += (self._mascot_x_target - self._mascot_x_offset) * 0.05

        # Particles
        for pt in self._particles:
            pt.update()
        self._particles = [pt for pt in self._particles if pt.is_alive()]

        for fc in self._floating_coins:
            fc.update()
        self._floating_coins = [fc for fc in self._floating_coins if fc.is_alive()]

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

    # ─── Chizish ───

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mcx = w / 2 + self._mascot_x_offset
        mcy = h / 2 + self._bounce_offset

        scale = min(w, h) / 500.0
        p.translate(mcx, mcy)
        p.scale(scale, scale)

        breath = math.sin(self._breath_phase) * 3

        # Particles (orqa)
        self._draw_particles(p)

        # Glow
        glow_r = 180 + math.sin(self._glow_phase) * 20
        glow_alpha = 30 + int(math.sin(self._glow_phase) * 15)
        if self._state in ("happy", "thanking"):
            glow_alpha = 60 + int(math.sin(self._glow_phase * 2) * 30)
            glow_r = 230
        glow_grad = QRadialGradient(0, 0, glow_r)
        glow_grad.setColorAt(0, QColor(76, 175, 80, glow_alpha))
        glow_grad.setColorAt(1, QColor(76, 175, 80, 0))
        p.setBrush(QBrush(glow_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, 0), glow_r, glow_r)

        # Tana
        body_rx = 120 + breath + self._squish * 30
        body_ry = 130 + breath - self._squish * 20
        body_grad = QRadialGradient(QPointF(-30, -40), body_rx * 1.3)
        body_grad.setColorAt(0, self._body_light)
        body_grad.setColorAt(0.7, self._body_color)
        body_grad.setColorAt(1, self._body_dark)
        p.setBrush(QBrush(body_grad))
        p.setPen(QPen(self._body_dark, 3))
        p.drawEllipse(QPointF(0, 20), body_rx, body_ry)

        # Oyoqlar
        foot_y = 145 + breath
        for fx in [-45, 45]:
            foot_grad = QRadialGradient(QPointF(fx, foot_y), 30)
            foot_grad.setColorAt(0, self._body_color)
            foot_grad.setColorAt(1, self._body_dark)
            p.setBrush(QBrush(foot_grad))
            p.setPen(QPen(self._body_dark, 2))
            p.drawEllipse(QPointF(fx, foot_y), 28, 18)

        # Chap qo'l
        p.save()
        if self._is_rubbing_belly:
            bx = -50 + math.sin(self._belly_rub_phase) * 30
            by = 60 + math.cos(self._belly_rub_phase) * 10
            p.translate(bx, by)
            p.rotate(math.sin(self._belly_rub_phase) * 10)
        else:
            p.translate(-115, -10)
        p.setBrush(QBrush(self._body_color))
        p.setPen(QPen(self._body_dark, 2))
        p.drawEllipse(QPointF(0, 0), 25, 18)
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
            p.translate(115, -10)
            p.rotate(wave_angle)
        p.setBrush(QBrush(self._body_color))
        p.setPen(QPen(self._body_dark, 2))
        p.drawEllipse(QPointF(0, 0), 25, 18)
        if self._is_waving and not self._is_rubbing_belly:
            p.setBrush(QBrush(self._body_light))
            p.drawEllipse(QPointF(20, -15), 14, 14)
        p.restore()

        # Barg
        p.save()
        p.translate(0, -135 - breath)
        leaf_sway = math.sin(self._breath_phase * 1.5) * 8
        if self._state == "happy":
            leaf_sway = math.sin(self._state_timer * 0.4) * 20
        p.rotate(leaf_sway)
        p.setPen(QPen(QColor(27, 94, 32), 3))
        p.setBrush(QBrush(self._leaf_color))
        path = QPainterPath()
        path.moveTo(0, 0)
        path.cubicTo(-12, -25, -20, -40, 0, -55)
        path.cubicTo(20, -40, 12, -25, 0, 0)
        p.drawPath(path)
        p.setPen(QPen(QColor(27, 94, 32, 150), 1.5))
        p.drawLine(QPointF(0, -5), QPointF(0, -45))
        p.restore()

        # Ko'zlar
        eye_y = -25
        for ex in [-40, 40]:
            p.setBrush(QBrush(self._eye_white))
            p.setPen(QPen(QColor(200, 200, 200), 2))

            if self._is_blinking or (self._state == "happy" and self._is_rubbing_belly):
                # Baxtli yumilgan ko'z
                p.setPen(QPen(self._eye_pupil, 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                hp = QPainterPath()
                hp.moveTo(ex - 20, eye_y)
                hp.cubicTo(ex - 10, eye_y - 15, ex + 10, eye_y - 15, ex + 20, eye_y)
                p.drawPath(hp)
            else:
                p.drawEllipse(QPointF(ex, eye_y), 28, 30)
                pdx = (self._eye_current.x() - 0.5) * 16
                pdy = (self._eye_current.y() - 0.5) * 10
                iris_x = ex + pdx
                iris_y = eye_y + pdy

                iris_sz = 18 if self._state == "eating" else 14
                pupil_sz = 9 if self._state == "eating" else 7

                ig = QRadialGradient(QPointF(iris_x - 2, iris_y - 3), iris_sz + 2)
                ig.setColorAt(0, QColor(120, 80, 50))
                ig.setColorAt(0.7, self._eye_iris)
                ig.setColorAt(1, QColor(20, 15, 10))
                p.setBrush(QBrush(ig))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(iris_x, iris_y), iris_sz, iris_sz + 1)

                p.setBrush(QBrush(self._eye_pupil))
                p.drawEllipse(QPointF(iris_x, iris_y), pupil_sz, pupil_sz + 1)

                p.setBrush(QBrush(QColor(255, 255, 255, 220)))
                p.drawEllipse(QPointF(iris_x - 4, iris_y - 5), 4, 4)
                p.setBrush(QBrush(QColor(255, 255, 255, 120)))
                p.drawEllipse(QPointF(iris_x + 3, iris_y + 2), 2, 2)

        # Yonoqlar
        p.setPen(Qt.PenStyle.NoPen)
        ch_a = 160 if self._state in ("happy", "thanking") else 90
        p.setBrush(QBrush(QColor(255, 138, 128, ch_a)))
        p.drawEllipse(QPointF(-70, 15), 20, 14)
        p.drawEllipse(QPointF(70, 15), 20, 14)

        # Og'iz
        mouth_y = 30
        if self._state == "eating":
            p.setPen(QPen(self._mouth_color, 3))
            p.setBrush(QBrush(QColor(183, 28, 28, 200)))
            oa = abs(math.sin(self._state_timer * 0.3)) * 20
            p.drawEllipse(QPointF(0, mouth_y + 5), 20, 8 + oa)
        elif self._state == "happy":
            p.setPen(QPen(self._mouth_color, 3))
            p.setBrush(QBrush(QColor(239, 83, 80, 200)))
            mp = QPainterPath()
            mp.moveTo(-35, mouth_y - 5)
            mp.cubicTo(-18, mouth_y + 40, 18, mouth_y + 40, 35, mouth_y - 5)
            mp.cubicTo(18, mouth_y + 18, -18, mouth_y + 18, -35, mouth_y - 5)
            p.drawPath(mp)
        elif self._state == "thanking":
            p.setPen(QPen(self._mouth_color, 3))
            p.setBrush(QBrush(QColor(239, 83, 80, 150)))
            mp = QPainterPath()
            mp.moveTo(-28, mouth_y)
            mp.cubicTo(-14, mouth_y + 30, 14, mouth_y + 30, 28, mouth_y)
            mp.cubicTo(14, mouth_y + 12, -14, mouth_y + 12, -28, mouth_y)
            p.drawPath(mp)
        elif self._person_detected:
            p.setPen(QPen(self._mouth_color, 3))
            p.setBrush(QBrush(QColor(239, 83, 80, 180)))
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

        # Recycling belgisi
        if not self._is_rubbing_belly:
            p.save()
            p.translate(0, 70)
            p.scale(0.6, 0.6)
            rot_speed = self._breath_phase * 5
            if self._state in ("happy", "thanking"):
                rot_speed = self._state_timer * 3
            p.setPen(QPen(QColor(255, 255, 255, 150), 3))
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

        # Floating coins
        self._draw_floating_coins(p)

        # Yulduzchalar
        if self._state in ("happy", "eating"):
            self._draw_sparkles(p)

        p.resetTransform()

        # Xabar bubble
        self._draw_message_bubble(p, w, h)

        p.end()

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
                p.drawRect(QRectF(-s/2, -s/2, s, s))
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
            sz = int(20 * fc.scale)
            font = QFont("Segoe UI", sz, QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QColor(255, 215, 0, alpha))

            # Shadow
            p.save()
            p.setPen(QColor(0, 0, 0, alpha // 3))
            p.drawText(QPointF(fc.x - 38, fc.y + 2), fc.text)
            p.restore()

            p.setPen(QColor(255, 215, 0, alpha))
            p.drawText(QPointF(fc.x - 40, fc.y), fc.text)

    def _draw_sparkles(self, p: QPainter):
        t = self._state_timer * 0.1
        for i in range(8):
            angle = t + i * (math.pi / 4)
            dist = 150 + math.sin(t * 2 + i) * 20
            sx = math.cos(angle) * dist
            sy = math.sin(angle) * dist
            size = 4 + math.sin(t * 3 + i * 2) * 3
            alpha = 150 + int(math.sin(t * 4 + i) * 100)
            alpha = max(0, min(255, alpha))
            p.setPen(Qt.PenStyle.NoPen)
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
        p.setBrush(QColor(0, 0, 0, 30))
        sp = QPainterPath()
        sp.addRoundedRect(QRectF(bx + 3, by + 3, bubble_w, bubble_h), 22, 22)
        p.drawPath(sp)

        # Gradient background
        if self._state in ("happy", "eating"):
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0, QColor(255, 253, 231, 240))
            bg.setColorAt(1, QColor(255, 243, 224, 240))
        elif self._state == "thanking":
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0, QColor(232, 245, 233, 240))
            bg.setColorAt(1, QColor(200, 230, 201, 240))
        else:
            bg = QLinearGradient(bx, by, bx, by + bubble_h)
            bg.setColorAt(0, QColor(255, 255, 255, 230))
            bg.setColorAt(1, QColor(232, 245, 233, 230))
        p.setBrush(QBrush(bg))

        bp = QPainterPath()
        bp.addRoundedRect(QRectF(bx, by, bubble_w, bubble_h), 22, 22)
        p.drawPath(bp)

        # Border
        bc = QColor(255, 193, 7, 200) if self._state == "happy" else QColor(76, 175, 80, 150)
        p.setPen(QPen(bc, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bp)

        # Text
        p.setPen(QColor(33, 33, 33))
        font = QFont("Segoe UI", 18)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(bx, by, bubble_w, bubble_h), Qt.AlignmentFlag.AlignCenter, msg)
