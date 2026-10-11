import json
import logging
import threading
import time
from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction, QActionGroup, QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
from .card import UsageCard
from .config import ROOT, RUNTIME, atomic_json
from .events import PetEvent, usage_state
from .renderers import create_renderer
from .usage import read_usage, snapshot_from_cache, UsageError
from .window import PetWindow
from . import startup


class UsageWorker(QThread):
    received = Signal(object)
    failed = Signal(str)

    def __init__(self, executable, parent=None):
        super().__init__(parent)
        self.executable = executable
        self.cancel = threading.Event()

    def run(self):
        try:
            self.received.emit(read_usage(self.executable, cancel=self.cancel))
        except UsageError as exc:
            self.failed.emit(str(exc))
        except Exception:
            logging.exception("Quota worker failed")
            self.failed.emit("额度暂不可用；稍后会自动重试")


class PetController(QObject):
    def __init__(self, app, settings, start_query=True):
        super().__init__()
        self.app = app
        self.settings = settings
        self.snapshot = None
        self.error = ""
        self.worker = None
        self.quitting = False
        self.last_query_at = -100.0
        self.states = {}
        self.window = PetWindow(settings)
        self.renderer = create_renderer(settings.get("renderer"), ROOT / settings.get("image"), self.window)
        self.window.attach_renderer(self.renderer)
        self.renderer.set_idle_motion(settings.get("idle_motion"))
        self.card = UsageCard()
        self.card.hide()
        self.close_card_timer = QTimer(self)
        self.close_card_timer.setSingleShot(True)
        self.close_card_timer.setInterval(450)
        self.close_card_timer.timeout.connect(self._maybe_close_card)
        self.window.behavior.connect(self.dispatch)
        self.window.hover_requested.connect(self.show_card)
        self.window.hover_left.connect(self.close_card_timer.start)
        self.window.menu_requested.connect(self.show_menu)
        self.window.position_changed.connect(lambda p: settings.set("position", [p.x(), p.y()]))
        self.window.visibility_changed.connect(self._visibility)
        self.card.entered.connect(self.close_card_timer.stop)
        self.card.left.connect(self.close_card_timer.start)
        self.card.refresh_requested.connect(self.refresh)
        self.card.bucket_changed.connect(self._select_bucket)
        self._make_tray()
        try:
            self.snapshot = snapshot_from_cache(json.loads((RUNTIME / "usage-cache.json").read_text(encoding="utf-8")))
            self.error = "这是上次保存的数据，正在重新查询"
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(settings.get("refresh_seconds") * 1000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.card_timer = QTimer(self)
        self.card_timer.setInterval(30000)
        self.card_timer.timeout.connect(self._update_visible_card)
        self.card_timer.start()
        self.window.place_initially()
        self.window.show()
        self.renderer.handle_event(PetEvent("idle"))
        self.app.aboutToQuit.connect(self.shutdown)
        self.app.screenAdded.connect(self._screen_added)
        self.app.screenRemoved.connect(lambda _: QTimer.singleShot(0, self.window.clamp_to_screen))
        for screen in self.app.screens():
            self._screen_added(screen)
        if start_query:
            self.refresh_timer.start()
            QTimer.singleShot(500, self.refresh)

    def _screen_added(self, screen):
        screen.availableGeometryChanged.connect(lambda _: self.window.clamp_to_screen(False))

    def _make_tray(self):
        icon = QIcon(str(ROOT / "assets" / "desktop-pet-icon.ico"))
        if icon.isNull():
            icon = QIcon(str(ROOT / "assets" / "pet.png"))
        self.app.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("DesktopPet · 悬停查看 Codex 额度")
        self.menu = QMenu()
        self.toggle_action = self.menu.addAction("隐藏宠物", self.toggle_visible)
        self.menu.addAction("查看额度", self.show_card)
        self.menu.addAction("刷新额度", self.refresh)
        self.menu.addSeparator()
        sizes = self.menu.addMenu("宠物大小")
        group = QActionGroup(self)
        for title, height in (("小 · 220", 220), ("中 · 300", 300), ("大 · 400", 400)):
            action = QAction(title, group)
            action.setCheckable(True)
            action.setChecked(height == self.settings.get("height"))
            action.triggered.connect(lambda checked, h=height: self.resize_pet(h))
            sizes.addAction(action)
        snap = self.menu.addAction("屏幕边缘吸附")
        snap.setCheckable(True)
        snap.setChecked(self.settings.get("edge_snap"))
        snap.toggled.connect(lambda value: self.settings.set("edge_snap", value))
        motion = self.menu.addAction("轻微浮动")
        motion.setCheckable(True)
        motion.setChecked(self.settings.get("idle_motion"))
        motion.toggled.connect(self._idle_motion)
        self.autostart = self.menu.addAction("开机启动")
        self.autostart.setCheckable(True)
        self.autostart.setChecked(startup.is_enabled())
        self.autostart.toggled.connect(self._autostart)
        self.menu.addAction("恢复到屏幕右下角", self.reset_position)
        self.menu.addSeparator()
        self.menu.addAction("退出", self.app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def dispatch(self, name):
        self.renderer.handle_event(PetEvent(name))
        if name == "drag_start":
            self.card.hide()

    def _visibility(self, visible):
        self.renderer.set_active(visible)
        if not visible:
            self.card.hide()
        if hasattr(self, "toggle_action"):
            self.toggle_action.setText("隐藏宠物" if visible else "显示宠物")

    def toggle_visible(self):
        self.window.setVisible(not self.window.isVisible())

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def show_menu(self, point):
        self.card.hide()
        self.menu.popup(point)

    def _idle_motion(self, value):
        self.settings.set("idle_motion", value)
        self.renderer.set_idle_motion(value)

    def _autostart(self, value):
        try:
            startup.set_enabled(value, ROOT)
        except OSError:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(startup.is_enabled())
            self.autostart.blockSignals(False)
            QMessageBox.warning(self.window, "开机启动", "无法修改开机启动设置，请检查 Windows 权限。")

    def resize_pet(self, height):
        self.settings.set("height", height)
        self.card.hide()
        self.window.set_pet_height(height)
        self.window.clamp_to_screen(False)

    def reset_position(self):
        self.settings.set("position", None)
        self.window.place_initially()
        self.window.show()

    def _select_bucket(self, bucket):
        self.settings.set("bucket_id", bucket)
        self.update_card()

    def _maybe_close_card(self):
        cursor = QCursor.pos()
        if self.card.isVisible() and self.card.frameGeometry().contains(cursor):
            return
        if self.window.isVisible() and self.renderer.hit_test(self.window.mapFromGlobal(cursor)):
            return
        if QApplication.activePopupWidget():
            self.close_card_timer.start()
            return
        self.card.hide()

    def show_card(self):
        if self.window.dragging:
            return
        if not self.window.isVisible():
            self.window.show()
        self.close_card_timer.stop()
        self.update_card()
        area = self.window.screen().availableGeometry()
        x = self.window.x() - self.card.width() - 10
        if x < area.left():
            x = self.window.x() + self.window.width() + 10
        x = max(area.left(), min(x, area.x() + area.width() - self.card.width()))
        y = max(area.top(), min(self.window.y(), area.y() + area.height() - self.card.height()))
        self.card.move(x, y)
        self.card.show()
        self.card.raise_()

    def update_card(self):
        self.card.present(self.snapshot, self.settings.get("bucket_id"), self.error,
                          self.worker is not None, self.settings.get("refresh_seconds"))

    def _update_visible_card(self):
        if self.card.isVisible():
            self.update_card()

    def refresh(self):
        if self.quitting or self.worker is not None or time.monotonic() - self.last_query_at < 10:
            return
        self.last_query_at = time.monotonic()
        self.worker = UsageWorker(self.settings.get("codex_executable"), self)
        self.worker.received.connect(self._received)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()
        self.update_card()

    def _received(self, snapshot):
        self.snapshot = snapshot
        self.error = ""
        try:
            atomic_json(RUNTIME / "usage-cache.json", snapshot.to_dict())
        except OSError:
            logging.warning("Could not save quota cache")
        for bucket in snapshot.buckets:
            for window in bucket.windows:
                if window.remaining is None or window.duration not in (300, 10080):
                    continue
                if window.resets_at and window.resets_at <= time.time():
                    continue
                key = (bucket.id, window.duration)
                state = usage_state(window.remaining)
                if self.states.get(key) != state:
                    self.states[key] = state
                    self.renderer.handle_event(PetEvent(state, {
                        "bucket_id": bucket.id, "window_minutes": window.duration, "remaining": window.remaining}))

    def _failed(self, message):
        self.error = message

    def _worker_finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        self.update_card()

    def shutdown(self):
        self.quitting = True
        self.refresh_timer.stop()
        self.card_timer.stop()
        self.close_card_timer.stop()
        self.renderer.dispose()
        self.card.hide()
        self.tray.hide()
        if self.worker is not None:
            self.worker.cancel.set()
            self.worker.wait(6000)
        self.settings.set("position", [self.window.x(), self.window.y()])
