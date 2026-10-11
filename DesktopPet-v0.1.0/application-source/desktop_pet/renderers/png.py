import math
import time
from pathlib import Path
from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from .base import BasePetRenderer


class PngPetRenderer(BasePetRenderer):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image = QImage(str(image_path))
        if self.image.isNull():
            raise ValueError(f"无法读取宠物图片：{image_path}")
        self.pixmap = QPixmap.fromImage(self.image)
        self.aspect = self.image.width() / self.image.height()
        self.active = False
        self.idle_motion = False
        self.click_at = None
        self.started_at = time.monotonic()
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._tick)
        self.paint_count = 0

    def set_active(self, active):
        self.active = active
        if not active:
            self.click_at = None
        self._schedule()

    def set_idle_motion(self, enabled):
        self.idle_motion = bool(enabled)
        self._schedule()
        self.update()

    def handle_event(self, event):
        if event.name == "click" and self.active:
            self.click_at = time.monotonic()
            self._schedule()
        elif event.name == "drag_start":
            self.click_at = None
            self._schedule()
        # Usage events deliberately have no visual binding in this version.

    def _schedule(self):
        if not self.active or (self.click_at is None and not self.idle_motion):
            self.frame_timer.stop()
        else:
            self.frame_timer.start(34 if self.click_at is not None else 100)

    def _tick(self):
        if self.click_at is not None and time.monotonic() - self.click_at > 0.42:
            self.click_at = None
            self._schedule()
        self.update()

    def target_rect(self):
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        factor = min(rect.width() / self.image.width(), rect.height() / self.image.height())
        w, h = self.image.width() * factor, self.image.height() * factor
        y = rect.center().y() - h / 2
        now = time.monotonic()
        if self.idle_motion and self.active:
            y += math.sin((now - self.started_at) * 1.5) * 2
        if self.click_at is not None:
            t = min(1, (now - self.click_at) / 0.42)
            y -= math.sin(t * math.pi) * 7
        return QRectF(rect.center().x() - w / 2, y, w, h)

    def hit_test(self, position):
        rect = self.target_rect()
        if not rect.contains(position):
            return False
        x = min(self.image.width() - 1, int((position.x() - rect.x()) / rect.width() * self.image.width()))
        y = min(self.image.height() - 1, int((position.y() - rect.y()) / rect.height() * self.image.height()))
        return self.image.pixelColor(x, y).alpha() > 20

    def paintEvent(self, event):
        self.paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.target_rect(), self.pixmap, QRectF(self.pixmap.rect()))
