from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel
from ui.dialogs import LEDIndicator


class WarningLedPanel(QWidget):
    def __init__(self, errors=None, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        self.led_indicators = {}

        if errors is None:
            errors = [
                "OBC Input AC Over Voltage", "OBC Input AC Under Voltage", "OBC Input Over Current",
                "OBC Output Over Current", "OBC High Temperature", "OBC Low Temperature",
                "OBC Temp Sensor Fail", "OBC Current Sensing Fail", "OBC Contactor/Relay Fail",
                "OBC Output Open Circuit", "OBC Output Short Circuit", "OBC Output Over Voltage",
                "OBC Output Under Voltage", "DCDC Output Over Voltage", "DCDC Input Over Voltage",
                "DCDC Input Under Voltage", "DCDC Input Over Current", "DCDC Output Over Current",
                "DCDC High Temperature", "DCDC Low Temperature", "DCDC Temp Sensor Fail",
                "DCDC Current Sensing Fail", "DCDC Contactor/Relay Fail", "DCDC Output Open Circuit",
                "DCDC Output Short Circuit", "DCDC Output Under Voltage", "DCDC Input Over Voltage L2",
                "OBC Input AC Distorted", "OBC Input Short Circuit", "OBC Bus Over Voltage",
                "OBC Bus Short Out",
            ]

        for i, name in enumerate(errors):
            layout.addWidget(QLabel(name), i, 0)
            led = LEDIndicator()
            layout.addWidget(led, i, 1)
            self.led_indicators[name] = led
