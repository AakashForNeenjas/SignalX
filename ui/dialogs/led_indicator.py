from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QWidget


class LEDIndicator(QWidget):
    def __init__(self, color=Qt.GlobalColor.green):
        super().__init__()
        self.setFixedSize(20, 20)
        self.default_color = color
        self.color = color
        self.active = False

    def set_active(self, active):
        self.active = active
        self.update()

    def set_error(self, is_error):
        """Set LED to red if error (1), green if no error (0)."""
        if is_error:
            self.color = Qt.GlobalColor.red
            self.active = True
        else:
            self.color = Qt.GlobalColor.green
            self.active = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.active:
            brush = QBrush(self.color)
        else:
            brush = QBrush(QColor(50, 50, 50))

        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 20, 20)
