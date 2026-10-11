import logging
from logging.handlers import RotatingFileHandler
import sys
import argparse
from pathlib import Path
from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox
from desktop_pet.config import RUNTIME, Settings
from desktop_pet.controller import PetController
from desktop_pet import __version__


def main():
    parser = argparse.ArgumentParser(description="DesktopPet PNG companion")
    parser.add_argument("--smoke-test-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(RUNTIME / "desktop-pet.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("DesktopPet")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("DesktopPet")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(RUNTIME / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "DesktopPet", "宠物已经在运行，可以从任务栏通知区域找到它。")
        return 0
    try:
        controller = PetController(app, Settings(), start_query=not args.offline)
        logging.info("DesktopPet %s started (%s)", __version__, "EXE" if getattr(sys, "frozen", False) else "Python")
        if args.smoke_test_report:
            from desktop_pet.diagnostics import start_smoke_test
            start_smoke_test(app, controller, args.smoke_test_report, args.offline)
        return app.exec()
    except Exception:
        logging.exception("Application failed")
        QMessageBox.critical(None, "DesktopPet", "启动失败，详情已写入项目 runtime 文件夹内的日志。")
        return 1
    finally:
        lock.unlock()
        logging.info("DesktopPet exited")


if __name__ == "__main__":
    sys.exit(main())
