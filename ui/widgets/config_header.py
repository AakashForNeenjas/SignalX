from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox


class ConfigHeader(QWidget):
    def __init__(self, profiles, active_profile, on_profile_change=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.set_profiles(profiles, active_profile)
        if on_profile_change:
            self.profile_combo.currentTextChanged.connect(on_profile_change)
        layout.addWidget(self.profile_combo)
        layout.addStretch()

    def set_profiles(self, profiles, active_profile):
        self.profile_combo.clear()
        for name in profiles.keys():
            self.profile_combo.addItem(name)
        self.profile_combo.setCurrentText(active_profile)
