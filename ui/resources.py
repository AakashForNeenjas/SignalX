from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt


def _icon_file_path(prefer_ico: bool = True) -> Path | None:
    """Return icon asset path from the ui package directory, if present."""
    ico_path = Path(__file__).with_name("app_logo.ico")
    png_path = Path(__file__).with_name("app logo.png")
    if prefer_ico and ico_path.exists():
        return ico_path
    if png_path.exists():
        return png_path
    if ico_path.exists():
        return ico_path
    return None


def _build_pixmap(size: int = 128) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("#0a0e27"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Outer circle
    painter.setBrush(QColor("#0f3460"))
    painter.setPen(QColor("#00d4ff"))
    painter.drawEllipse(8, 8, size - 16, size - 16)
    # Inner glow
    painter.setBrush(QColor("#00d4ff"))
    painter.setPen(QColor("#00ff88"))
    painter.drawEllipse(size // 4, size // 4, size // 2, size // 2)
    # Text
    painter.setPen(QColor("#0a0e27"))
    painter.setFont(QFont("Arial", int(size * 0.22), QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), 0x84, "AtomX")  # Centered
    painter.end()
    return pixmap


def _load_logo_pixmap(size: int = 256) -> QPixmap:
    """
    Try to load the saved app logo from the ui folder; fall back to generated art.
    """
    logo_path = Path(__file__).with_name("app logo.png")
    if logo_path.exists():
        pix = QPixmap(str(logo_path))
        if not pix.isNull():
            return pix.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return _build_pixmap(size)


def create_app_icon() -> QIcon:
    """Create app icon; prefer ICO on Windows/taskbar and fallback to PNG-derived sizes."""
    icon_path = _icon_file_path(prefer_ico=True)
    if icon_path is not None and icon_path.suffix.lower() == ".ico":
        ico_icon = QIcon(str(icon_path))
        if not ico_icon.isNull():
            return ico_icon

    base = _load_logo_pixmap(512)
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(
            base.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    return icon


def create_splash_pixmap() -> QPixmap:
    """Splash artwork derived from the same saved logo (or fallback artwork)."""
    return _load_logo_pixmap(512)


def get_app_ico_path() -> str | None:
    """Return ICO file path for Windows native icon APIs, if available."""
    icon_path = _icon_file_path(prefer_ico=True)
    if icon_path is not None and icon_path.suffix.lower() == ".ico":
        return str(icon_path)
    return None
