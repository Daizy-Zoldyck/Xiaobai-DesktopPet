from datetime import datetime
import time
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QComboBox, QFrame


def reset_text(timestamp):
    if timestamp is None:
        return "重置时间暂不可用"
    if timestamp <= time.time():
        return "已到重置时间，等待更新"
    try:
        return "重置于 " + datetime.fromtimestamp(timestamp).strftime("%m月%d日 %H:%M")
    except (ValueError, OSError, OverflowError):
        return "重置时间暂不可用"


class QuotaRow(QWidget):
    def __init__(self, title):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(7)
        heading = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("rowTitle")
        self.value = QLabel("—")
        self.value.setObjectName("percentage")
        heading.addWidget(label)
        heading.addStretch()
        heading.addWidget(self.value)
        layout.addLayout(heading)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(7)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.reset = QLabel("等待额度数据")
        self.reset.setObjectName("muted")
        layout.addWidget(self.reset)

    def update_window(self, window, stale):
        remaining = window.remaining if window else None
        expired = bool(window and window.resets_at and window.resets_at <= time.time())
        if remaining is None or expired:
            self.value.setText("待更新" if expired else "暂不可用")
            self.bar.setValue(0)
            self.bar.setEnabled(False)
        else:
            number = f"{remaining:.0f}" if remaining.is_integer() else f"{remaining:.1f}"
            self.value.setText(f"剩余 {number}%" + (" · 旧" if stale else ""))
            self.bar.setValue(round(remaining * 10))
            self.bar.setEnabled(not stale)
        self.reset.setText(reset_text(window.resets_at) if window else "服务未提供此窗口")


class UsageCard(QWidget):
    refresh_requested = Signal()
    bucket_changed = Signal(str)
    entered = Signal()
    left = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("DesktopPet · Codex 额度")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(320)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)
        frame = QFrame()
        frame.setObjectName("card")
        outer.addWidget(frame)
        body = QVBoxLayout(frame)
        body.setContentsMargins(20, 18, 20, 17)
        body.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Codex 额度")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        badge = QLabel("桌面伙伴")
        badge.setObjectName("badge")
        header.addWidget(badge)
        body.addLayout(header)
        self.bucket = QComboBox()
        self.bucket.setMinimumHeight(28)
        self.bucket.currentIndexChanged.connect(self._bucket_changed)
        body.addWidget(self.bucket)
        self.five_hour = QuotaRow("5 小时额度")
        self.weekly = QuotaRow("周额度")
        body.addWidget(self.five_hour)
        body.addWidget(self.weekly)
        self.status = QLabel("正在读取额度…")
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        body.addWidget(self.status)
        footer = QHBoxLayout()
        help_text = QLabel("拖动移动 · 右键设置")
        help_text.setObjectName("muted")
        footer.addWidget(help_text)
        footer.addStretch()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh_requested)
        footer.addWidget(self.refresh_button)
        body.addLayout(footer)
        self.setStyleSheet("""
            QWidget { font-family: 'Microsoft YaHei UI'; font-size: 11px; color: #56463e; }
            QFrame#card { background: #fffaf2; border: 1px solid #d9cbbb; border-radius: 17px; }
            QLabel { background: transparent; border: none; }
            QLabel#title { font-size: 18px; font-weight: 700; color: #49372f; }
            QLabel#badge { background: #e9f1e7; color: #537363; border-radius: 7px; padding: 4px 7px; font-size: 10px; }
            QLabel#rowTitle { font-size: 12px; font-weight: 600; }
            QLabel#percentage { font-size: 13px; font-weight: 700; color: #527968; }
            QLabel#muted { color: #908176; font-size: 10px; }
            QProgressBar { border: none; background: #eee6dc; border-radius: 3px; }
            QProgressBar::chunk { background: #91b69e; border-radius: 3px; }
            QProgressBar:disabled::chunk { background: #bdb5aa; }
            QPushButton { background: #eee5d8; border: none; border-radius: 8px; padding: 6px 13px; }
            QPushButton:hover { background: #e4d6c4; }
            QPushButton:disabled { color: #b3a79a; }
            QComboBox { border: 1px solid #e3d8c9; border-radius: 6px; padding: 3px 6px; background: #fffdf8; }
            QComboBox QAbstractItemView { background: #fffaf2; selection-background-color: #e9f1e7; }
        """)

    def _bucket_changed(self):
        value = self.bucket.currentData()
        if value:
            self.bucket_changed.emit(value)

    def present(self, snapshot, selected, error, busy, refresh_seconds):
        buckets = snapshot.buckets if snapshot else ()
        current_items = [self.bucket.itemData(i) for i in range(self.bucket.count())]
        if current_items != [b.id for b in buckets]:
            self.bucket.blockSignals(True)
            self.bucket.clear()
            for b in buckets:
                self.bucket.addItem(b.name, b.id)
            self.bucket.blockSignals(False)
        if buckets:
            index = self.bucket.findData(selected)
            self.bucket.blockSignals(True)
            self.bucket.setCurrentIndex(max(index, 0))
            self.bucket.blockSignals(False)
        self.bucket.setVisible(len(buckets) > 1)
        chosen = next((b for b in buckets if b.id == selected), buckets[0] if buckets else None)
        stale = bool(snapshot and (error or time.time() - snapshot.fetched_at > refresh_seconds + 60))
        self.five_hour.update_window(chosen.window(300) if chosen else None, stale)
        self.weekly.update_window(chosen.window(10080) if chosen else None, stale)
        lines = []
        if snapshot:
            stamp = datetime.fromtimestamp(snapshot.fetched_at).strftime("%m-%d %H:%M:%S")
            lines.append(("上次成功更新 " if stale else "更新于 ") + stamp)
        if busy:
            lines.append("正在后台刷新…")
        elif error:
            lines.append(error)
        elif snapshot:
            lines.append(f"每 {refresh_seconds // 60} 分钟自动刷新 · 账户共享额度")
        else:
            lines.append("尚未取得额度数据")
        self.status.setText("\n".join(lines))
        self.refresh_button.setEnabled(not busy)
        self.adjustSize()

    def enterEvent(self, event):
        self.entered.emit()

    def leaveEvent(self, event):
        self.left.emit()
