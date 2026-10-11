from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget
from .geometry import fit_position


class PetWindow(QWidget):
    behavior = Signal(str)
    hover_requested = Signal()
    hover_left = Signal()
    menu_requested = Signal(QPoint)
    position_changed = Signal(QPoint)
    visibility_changed = Signal(bool)

    def __init__(self, settings):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.settings = settings
        self.renderer = None
        self.setWindowTitle("DesktopPet")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.press_global = None
        self.press_origin = None
        self.dragging = False
        self.inside_pet = False
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(550)
        self.hover_timer.timeout.connect(self.hover_requested)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def attach_renderer(self, renderer):
        self.renderer = renderer
        renderer.setParent(self)
        self.set_pet_height(self.settings.get("height"))

    def set_pet_height(self, height):
        self.resize(round(height * self.renderer.aspect) + 16, height + 16)
        self.renderer.setGeometry(self.rect())

    def place_initially(self):
        saved = self.settings.get("position")
        screen = QGuiApplication.primaryScreen()
        pos = QPoint(*saved) if saved else None
        if pos is not None:
            screen = QGuiApplication.screenAt(pos + QPoint(self.width() // 2, self.height() // 2)) or screen
        area = screen.availableGeometry()
        if pos is None:
            pos = QPoint(area.right() - self.width() - 32, area.bottom() - self.height() - 16)
        self.move(fit_position(pos, self.width(), self.height(), area, False))

    def clamp_to_screen(self, snap=True):
        center = self.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or self.screen() or QGuiApplication.primaryScreen()
        pos = fit_position(self.pos(), self.width(), self.height(), screen.availableGeometry(), snap and self.settings.get("edge_snap"))
        self.move(pos)
        self.position_changed.emit(pos)

    def _hover(self, inside):
        if inside == self.inside_pet:
            return
        self.inside_pet = inside
        if inside and self.press_global is None:
            self.behavior.emit("hover")
            self.hover_timer.start()
        else:
            self.hover_timer.stop()
            self.hover_left.emit()

    def enterEvent(self, event):
        self._hover(self.renderer.hit_test(self.mapFromGlobal(QCursor.pos())))

    def leaveEvent(self, event):
        self._hover(False)

    def mousePressEvent(self, event):
        if not self.renderer.hit_test(event.position()):
            event.ignore()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.hover_timer.stop()
            self.menu_requested.emit(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_global = event.globalPosition().toPoint()
            self.press_origin = self.pos()
            self.hover_timer.stop()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.press_global is not None:
            delta = event.globalPosition().toPoint() - self.press_global
            if not self.dragging and delta.manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.behavior.emit("drag_start")
                self.hover_left.emit()
            if self.dragging:
                self.move(self.press_origin + delta)
        else:
            self._hover(self.renderer.hit_test(event.position()))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.press_global is None:
            return
        self.press_global = None
        if self.dragging:
            self.dragging = False
            self.clamp_to_screen()
            self.behavior.emit("drag_end")
        elif self.renderer.hit_test(event.position()):
            self.behavior.emit("click")
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def resizeEvent(self, event):
        if self.renderer:
            self.renderer.setGeometry(self.rect())

    def showEvent(self, event):
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        self.hover_timer.stop()
        self.press_global = None
        self.dragging = False
        self.inside_pet = False
        self.visibility_changed.emit(False)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
