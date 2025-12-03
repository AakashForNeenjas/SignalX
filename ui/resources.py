from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont


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


def create_app_icon() -> QIcon:
    """Create a lightweight generated icon (no external assets)."""
    pix = _build_pixmap(128)
    icon = QIcon(pix)
    return icon


def create_splash_pixmap() -> QPixmap:
    """Splash artwork derived from the same generated icon."""
    return _build_pixmap(256)
