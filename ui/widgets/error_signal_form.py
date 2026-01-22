from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFormLayout


class ErrorSignalForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.err_scroll = QScrollArea()
        self.err_scroll.setWidgetResizable(True)
        self.err_form_container = QWidget()
        self.err_form_layout = QFormLayout(self.err_form_container)
        self.err_scroll.setWidget(self.err_form_container)
        layout.addWidget(self.err_scroll)
