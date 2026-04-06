"""Window geometry helpers for stable, screen-adaptive main window behavior."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, QRect, QSettings
from PyQt6.QtGui import QGuiApplication

SETTINGS_ORG = "AtomX"
SETTINGS_APP = "AtomX"
KEY_NORMAL_RECT = "window/normal_rect"
KEY_MAXIMIZED = "window/maximized"


def _settings(settings: Optional[QSettings] = None) -> QSettings:
    return settings if settings is not None else QSettings(SETTINGS_ORG, SETTINGS_APP)


def _parse_rect(value) -> Optional[QRect]:
    if isinstance(value, QRect):
        return QRect(value)
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            x, y, w, h = [int(v) for v in value]
            if w > 0 and h > 0:
                return QRect(x, y, w, h)
        except Exception:
            return None
    return None


def load_window_settings(settings: Optional[QSettings] = None) -> dict:
    s = _settings(settings)
    rect_value = s.value(KEY_NORMAL_RECT, None)
    return {
        "normal_rect": _parse_rect(rect_value),
        "maximized": bool(s.value(KEY_MAXIMIZED, False, type=bool)),
    }


def save_window_settings(window, settings: Optional[QSettings] = None) -> None:
    s = _settings(settings)
    # On Windows, minimized windows can report off-screen/tiny geometry (e.g. -32000).
    # Persist normal geometry in both maximized and minimized states.
    rect = (
        window.normalGeometry()
        if window.isMaximized() or window.isMinimized()
        else window.geometry()
    )
    if not rect.isValid():
        rect = window.geometry()
    s.setValue(KEY_NORMAL_RECT, [rect.x(), rect.y(), rect.width(), rect.height()])
    s.setValue(KEY_MAXIMIZED, bool(window.isMaximized()))
    s.sync()


def is_suspicious_saved_rect(rect: Optional[QRect]) -> bool:
    """Detect window rectangles that likely come from minimized/off-screen artifacts."""
    if rect is None or not rect.isValid():
        return True
    if rect.x() <= -20000 or rect.y() <= -20000:
        return True
    if rect.width() < 400 or rect.height() < 250:
        return True
    return False


def compute_adaptive_rect(screen_available_rect: QRect) -> QRect:
    """Compute a centered first-run rect using a 1366x768 baseline."""
    screen = QRect(screen_available_rect)
    sw, sh = max(1, screen.width()), max(1, screen.height())
    baseline_w, baseline_h = 1366, 768

    # Keep 16:9-ish working ratio and scale to current screen with headroom.
    target_w = min(int(sw * 0.9), baseline_w if sw >= baseline_w else sw)
    target_h = int(target_w * baseline_h / baseline_w)
    if target_h > int(sh * 0.9):
        target_h = int(sh * 0.9)
        target_w = int(target_h * baseline_w / baseline_h)

    target_w = max(min(target_w, sw), min(900, sw))
    target_h = max(min(target_h, sh), min(600, sh))

    x = screen.left() + (sw - target_w) // 2
    y = screen.top() + (sh - target_h) // 2
    return QRect(x, y, target_w, target_h)


def clamp_rect_to_screen(rect: QRect, screen_rect: QRect) -> QRect:
    screen = QRect(screen_rect)
    r = QRect(rect)
    if not screen.isValid():
        return r

    w = min(max(1, r.width()), screen.width())
    h = min(max(1, r.height()), screen.height())
    max_x = screen.right() - w + 1
    max_y = screen.bottom() - h + 1

    x = min(max(r.x(), screen.left()), max_x)
    y = min(max(r.y(), screen.top()), max_y)
    return QRect(x, y, w, h)


def find_target_screen(window):
    screens = QGuiApplication.screens()
    if not screens:
        return None

    try:
        center = window.frameGeometry().center()
    except Exception:
        center = QPoint(0, 0)

    for screen in screens:
        if screen.availableGeometry().contains(center):
            return screen

    return QGuiApplication.primaryScreen() or screens[0]
