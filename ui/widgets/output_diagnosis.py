from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit


class OutputDiagnosis(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Output Diagnosis"))

        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setMaximumHeight(100)
        layout.addWidget(self.output_log)
