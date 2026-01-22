from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt


class SequenceEditorRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self.combo_step = QComboBox()
        self.btn_add_step = QPushButton("+ Add Step")
        self.running_test_label = QLabel("")
        self.running_test_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        self.run_status_label = QLabel("Idle")
        self.run_status_label.setStyleSheet("color: #9db4d4;")
        self.run_timer_label = QLabel("00:00")
        self.run_timer_label.setStyleSheet("color: #9db4d4;")
        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet(
            "background: #444; color: #fff; padding: 6px 10px; border-radius: 6px;"
        )
        self.toast_label.setVisible(False)

        layout.addWidget(QLabel("Test Step"))
        layout.addWidget(self.combo_step)
        layout.addWidget(self.btn_add_step)
        layout.addWidget(self.running_test_label)
        layout.addWidget(self.run_status_label)
        layout.addWidget(self.run_timer_label)
        layout.addWidget(self.toast_label)
        layout.addStretch()

    def populate_actions(self, instrument_actions, can_actions, utility_actions):
        self.combo_step.clear()

        def _add_header(text: str):
            idx = self.combo_step.count()
            self.combo_step.addItem(text)
            item = self.combo_step.model().item(idx)
            item.setEnabled(False)
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
            item.setForeground(QBrush(QColor("#888888")))
            item.setData(Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)

        grouped = {"GS": [], "PS": [], "OS": [], "LOAD": [], "INSTR": [], "RAMP": []}
        for act in instrument_actions:
            grouped.setdefault(act.group, []).append(act)
        for group_name in ["GS", "PS", "OS", "LOAD", "INSTR", "RAMP"]:
            acts = grouped.get(group_name, [])
            if not acts:
                continue
            _add_header(f"--- {group_name} ---")
            for act in acts:
                self.combo_step.addItem(act.name)
                if act.description:
                    self.combo_step.setItemData(
                        self.combo_step.count() - 1,
                        f"{act.group}: {act.description}",
                        Qt.ItemDataRole.ToolTipRole,
                    )
                else:
                    self.combo_step.setItemData(
                        self.combo_step.count() - 1,
                        act.group,
                        Qt.ItemDataRole.ToolTipRole,
                    )

        _add_header("--- CAN ---")
        for act in can_actions:
            self.combo_step.addItem(act)

        _add_header("--- Utility ---")
        for act in utility_actions:
            self.combo_step.addItem(act)

        for idx in range(self.combo_step.count()):
            if self.combo_step.model().item(idx).isEnabled():
                self.combo_step.setCurrentIndex(idx)
                break
