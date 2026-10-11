from PySide6.QtCore import QPoint, QRect


def fit_position(pos: QPoint, width: int, height: int, available: QRect, snap=True, threshold=24):
    left, top = available.x(), available.y()
    right = max(left, available.x() + available.width() - width)
    bottom = max(top, available.y() + available.height() - height)
    x = max(left, min(pos.x(), right))
    y = max(top, min(pos.y(), bottom))
    if snap:
        if x - left <= threshold:
            x = left
        elif right - x <= threshold:
            x = right
        if y - top <= threshold:
            y = top
        elif bottom - y <= threshold:
            y = bottom
    return QPoint(x, y)
