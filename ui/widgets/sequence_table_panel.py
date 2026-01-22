from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QPushButton, QHeaderView


class SequenceTablePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self.sequence_table = QTableWidget(0, 4)
        self.sequence_table.setHorizontalHeaderLabels(
            ["Step", "Action", "Parameters", "Status"]
        )
        self.sequence_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.sequence_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sequence_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        button_layout = QVBoxLayout()
        self.btn_del_step = QPushButton("Delete Step")
        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_down = QPushButton("Move Down")
        self.btn_edit_step = QPushButton("Edit Step")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_force_stop = QPushButton("E-Stop")
        self.btn_force_stop.setStyleSheet(
            "background-color: red; color: white; font-weight: bold;"
        )

        button_layout.addWidget(self.btn_del_step)
        button_layout.addWidget(self.btn_move_up)
        button_layout.addWidget(self.btn_move_down)
        button_layout.addWidget(self.btn_edit_step)
        button_layout.addWidget(self.btn_duplicate)
        button_layout.addWidget(self.btn_force_stop)
        button_layout.addStretch()

        layout.addWidget(self.sequence_table)
        layout.addLayout(button_layout)
