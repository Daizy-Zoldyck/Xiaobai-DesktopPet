from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QWidget
from ..events import PetEvent


class BasePetRenderer(QWidget):
    """Widget-backed renderer contract, also suitable for a future GPU surface."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def handle_event(self, event: PetEvent) -> None:
        raise NotImplementedError

    def set_active(self, active: bool) -> None:
        raise NotImplementedError

    def set_idle_motion(self, enabled: bool) -> None:
        raise NotImplementedError

    def hit_test(self, position: QPointF) -> bool:
        raise NotImplementedError

    def dispose(self) -> None:
        self.set_active(False)
