"""Explicit packaging smoke-test mode; never enabled during ordinary startup."""
import sys
import time
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from .config import ROOT, RUNTIME, atomic_json
from .events import PetEvent
from .startup import startup_command


def start_smoke_test(app, controller, report: Path, offline=False):
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    timer = QTimer(controller)
    state = {"ticks": 0}

    def finish():
        timer.stop()
        try:
            window, renderer = controller.window, controller.renderer
            renderer.set_idle_motion(True)
            window.hide()
            paused = not renderer.frame_timer.isActive()
            window.show()
            resumed = renderer.frame_timer.isActive()
            renderer.set_idle_motion(False)
            if offline:
                controller.error = "离线测试：额度不可用时仍可使用桌宠"
            controller.show_card()
            app.processEvents()
            renderer.grab().save(str(report.with_suffix(".pet.png")))
            controller.card.grab().save(str(report.with_suffix(".card.png")))
            result = {
                "frozen": bool(getattr(sys, "frozen", False)),
                "executable": sys.executable,
                "resource_root": str(ROOT),
                "data_directory": str(RUNTIME),
                "image_loaded": not renderer.image.isNull(),
                "image_has_alpha": renderer.image.hasAlphaChannel(),
                "icon_loaded": not app.windowIcon().isNull(),
                "icon_sizes": [[s.width(), s.height()] for s in app.windowIcon().availableSizes()],
                "transparent_window": window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground),
                "always_on_top": bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                "hide_pauses": paused,
                "show_resumes": resumed,
                "idle_timer_stopped": not renderer.frame_timer.isActive(),
                "quota_received": controller.snapshot is not None,
                "quota_windows": [w.duration for b in controller.snapshot.buckets for w in b.windows] if controller.snapshot else [],
                "quota_error": controller.error,
                "ui_ticks": state["ticks"],
                "startup_command": startup_command(ROOT),
                "offline": offline,
            }
            required = ("image_loaded", "image_has_alpha", "icon_loaded", "transparent_window", "always_on_top", "hide_pauses", "show_resumes", "idle_timer_stopped")
            result["passed"] = all(result[k] for k in required) and (offline or (result["quota_received"] and not result["quota_error"]))
            atomic_json(report, result)
            app.exit(0 if result["passed"] else 2)
        except Exception as exc:
            atomic_json(report, {"passed": False, "error": type(exc).__name__ + ": " + str(exc)})
            app.exit(2)

    def tick():
        state["ticks"] += 1
        elapsed = time.monotonic() - start
        if elapsed >= 2 and (offline or (controller.worker is None and controller.last_query_at > 0)):
            finish()
        elif elapsed > 35:
            finish()

    timer.timeout.connect(tick)
    timer.start(100)
