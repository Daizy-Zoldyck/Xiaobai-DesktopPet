import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from desktop_pet.card import UsageCard
from desktop_pet.config import Settings, ROOT
from desktop_pet.controller import PetController, UsageWorker
from desktop_pet.events import PetEvent
from desktop_pet.geometry import fit_position
from desktop_pet.renderers import create_renderer
from desktop_pet.usage import parse_limits
from desktop_pet.window import PetWindow

app = QApplication.instance() or QApplication([])


class UiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name) / "config.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_screen_clamp_and_snap_negative_monitor(self):
        area = QRect(-1920, -100, 1920, 1040)
        self.assertEqual(fit_position(QPoint(-1910, -90), 300, 400, area), QPoint(-1920, -100))
        self.assertEqual(fit_position(QPoint(-50, 9999), 300, 400, area), QPoint(-300, 540))
        self.assertEqual(fit_position(QPoint(-1900, 0), 300, 400, area, False), QPoint(-1900, 0))

    def test_idle_and_hidden_rendering_stop(self):
        renderer = create_renderer("png", ROOT / "assets/pet.png")
        renderer.resize(280, 320)
        renderer.set_active(True)
        self.assertFalse(renderer.frame_timer.isActive())
        renderer.handle_event(PetEvent("usage_critical"))
        self.assertFalse(renderer.frame_timer.isActive())
        renderer.handle_event(PetEvent("click"))
        self.assertTrue(renderer.frame_timer.isActive())
        QTest.qWait(500)
        self.assertFalse(renderer.frame_timer.isActive())
        renderer.set_idle_motion(True)
        self.assertTrue(renderer.frame_timer.isActive())
        renderer.set_active(False)
        self.assertFalse(renderer.frame_timer.isActive())
        renderer.deleteLater()

    def test_click_drag_are_mutually_exclusive(self):
        window = PetWindow(self.settings)
        renderer = create_renderer("png", ROOT / "assets/pet.png", window)
        window.attach_renderer(renderer)
        window.show()
        events = []
        window.behavior.connect(events.append)
        point = QPoint(window.width() // 2, window.height() // 3)
        self.assertTrue(renderer.hit_test(point))
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(events.count("click"), 1)
        events.clear()
        start = window.mapToGlobal(point)
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=point)
        move = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(point + QPoint(60, 20)),
            QPointF(start + QPoint(60, 20)), Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window, move)
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(events, ["drag_start", "drag_end"])
        window.hide()
        renderer.dispose()
        window.deleteLater()

    def test_card_expired_window_and_offline_data(self):
        snap = parse_limits({"rateLimits": {"primary": {
            "usedPercent": 34, "windowDurationMins": 300, "resetsAt": int(time.time()) - 1}}})
        card = UsageCard()
        card.present(snap, "codex", "离线", False, 300)
        self.assertEqual(card.five_hour.value.text(), "待更新")
        self.assertIn("离线", card.status.text())
        self.assertEqual(card.weekly.value.text(), "暂不可用")
        card.deleteLater()

    def test_slow_usage_query_does_not_block_ui(self):
        ticks = []
        timer = QTimer()
        timer.setInterval(20)
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        def slow(*args, **kwargs):
            time.sleep(0.3)
            return parse_limits({"rateLimits": {"primary": {"usedPercent": 1, "windowDurationMins": 300}}})
        with patch("desktop_pet.controller.read_usage", slow):
            worker = UsageWorker("")
            timer.start()
            worker.start()
            QTest.qWait(450)
            worker.wait()
            timer.stop()
        self.assertGreaterEqual(len(ticks), 8)

    def test_quota_events_only_on_transitions_and_hide_pauses(self):
        with patch("desktop_pet.controller.RUNTIME", Path(self.temp.name)):
            controller = PetController(app, self.settings, start_query=False)
            events = []
            controller.renderer.handle_event = events.append
            data = {"rateLimits": {"primary": {"usedPercent": 34, "windowDurationMins": 300},
                                   "secondary": {"usedPercent": 82, "windowDurationMins": 10080}}}
            snapshot = parse_limits(data)
            controller._received(snapshot)
            controller._received(snapshot)
            self.assertEqual([e.name for e in events], ["usage_normal", "usage_critical"])
            self.assertEqual(events[1].payload["window_minutes"], 10080)
            controller._failed("离线")
            self.assertEqual(len(events), 2)
            controller.renderer.set_idle_motion(True)
            controller.window.hide()
            self.assertFalse(controller.renderer.frame_timer.isActive())
            controller.shutdown()
            app.aboutToQuit.disconnect(controller.shutdown)
            controller.window.deleteLater()
            controller.card.deleteLater()
            controller.deleteLater()


if __name__ == "__main__":
    unittest.main()
