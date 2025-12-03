from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, 
                             QScrollArea, QFrame, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QComboBox, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient
import json
import math

class RoundGaugeWidget(QWidget):
    """Professional round gauge with needle for voltage and current - automotive grade"""
    
    def __init__(self, title="Signal", min_val=0, max_val=100, unit="", dbc_signal="", parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.dbc_signal = dbc_signal
        self.current_value = min_val
        self.setMinimumSize(180, 220)
        self.setStyleSheet("background-color: transparent;")
        
    def set_value(self, value):
        """Update gauge value"""
        self.current_value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # No background - transparent
        
        # Title
        title_font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#00d4ff"))
        painter.drawText(5, 5, w-10, 20, Qt.AlignmentFlag.AlignCenter, self.title)
        
        # Circle center and radius
        circle_x = w // 2
        circle_y = h // 2 + 5
        radius = 65
        
        # Draw outer circle (gauge background)
        painter.setPen(QPen(QColor("#00d4ff"), 2))
        painter.setBrush(QBrush(QColor("#0a1428")))
        painter.drawEllipse(circle_x - radius, circle_y - radius, radius * 2, radius * 2)
        
        # Draw gauge scale (tick marks and numbers)
        num_ticks = 10
        for i in range(num_ticks + 1):
            angle = 225 - (i * 270 / num_ticks)  # 225° to -45° (270° arc)
            angle_rad = math.radians(angle)
            
            # Tick mark
            tick_start_r = radius - 12
            tick_end_r = radius - 4
            
            tick_start_x = circle_x + tick_start_r * math.cos(angle_rad)
            tick_start_y = circle_y - tick_start_r * math.sin(angle_rad)
            tick_end_x = circle_x + tick_end_r * math.cos(angle_rad)
            tick_end_y = circle_y - tick_end_r * math.sin(angle_rad)
            
            painter.setPen(QPen(QColor("#00d4ff"), 1.5))
            painter.drawLine(int(tick_start_x), int(tick_start_y), int(tick_end_x), int(tick_end_y))
            
            # Scale label (only every other one to avoid clutter)
            if i % 2 == 0:
                scale_value = self.min_val + (i * (self.max_val - self.min_val) / num_ticks)
                label_r = radius - 28
                label_x = circle_x + label_r * math.cos(angle_rad)
                label_y = circle_y - label_r * math.sin(angle_rad)
                
                label_font = QFont("Arial", 6)
                painter.setFont(label_font)
                painter.setPen(QColor("#888888"))
                painter.drawText(int(label_x - 12), int(label_y - 8), 24, 16, 
                               Qt.AlignmentFlag.AlignCenter, f"{scale_value:.0f}")
        
        # Draw colored arc (green -> yellow -> red)
        painter.setPen(QPen(QColor("#00ff00"), 3))
        painter.drawArc(circle_x - radius + 8, circle_y - radius + 8, (radius - 8) * 2, (radius - 8) * 2,
                       int(225 * 16), int(162 * 16))  # Green 60% of arc
        
        painter.setPen(QPen(QColor("#ffff00"), 3))
        painter.drawArc(circle_x - radius + 8, circle_y - radius + 8, (radius - 8) * 2, (radius - 8) * 2,
                       int(63 * 16), int(54 * 16))  # Yellow 20% of arc
        
        painter.setPen(QPen(QColor("#ff3333"), 3))
        painter.drawArc(circle_x - radius + 8, circle_y - radius + 8, (radius - 8) * 2, (radius - 8) * 2,
                       int(9 * 16), int(54 * 16))  # Red 20% of arc
        
        # Draw needle
        value_ratio = (self.current_value - self.min_val) / (self.max_val - self.min_val)
        value_ratio = max(0, min(1, value_ratio))  # Clamp to 0-1
        angle = 225 - (value_ratio * 270)  # Angle for current value
        angle_rad = math.radians(angle)
        
        needle_length = radius - 15
        needle_x = circle_x + needle_length * math.cos(angle_rad)
        needle_y = circle_y - needle_length * math.sin(angle_rad)
        
        # Draw needle with gradient effect
        painter.setPen(QPen(QColor("#00ff88"), 3))
        painter.drawLine(int(circle_x), int(circle_y), int(needle_x), int(needle_y))
        
        # Center hub
        painter.setBrush(QBrush(QColor("#00ff88")))
        painter.setPen(QPen(QColor("#00d4ff"), 1.5))
        painter.drawEllipse(int(circle_x - 6), int(circle_y - 6), 12, 12)
        
        # Value display below gauge
        value_font = QFont("Arial", 12, QFont.Weight.Bold)
        painter.setFont(value_font)
        painter.setPen(QColor("#00ff88"))
        value_text = f"{self.current_value:.1f}"
        painter.drawText(5, h - 32, w - 10, 20, Qt.AlignmentFlag.AlignCenter, value_text)
        
        # Unit display
        unit_font = QFont("Arial", 8)
        painter.setFont(unit_font)
        painter.setPen(QColor("#888888"))
        painter.drawText(5, h - 14, w - 10, 15, Qt.AlignmentFlag.AlignCenter, self.unit)


class StatusLED(QWidget):
    """CAN Connection Status LED - Green when connected, Red when disconnected"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False
        self.setMinimumSize(50, 50)
        self.setMaximumSize(50, 50)
        
    def set_connected(self, connected):
        self.is_connected = connected
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Choose color based on connection status
        if self.is_connected:
            led_color = QColor("#00ff00")  # Green
        else:
            led_color = QColor("#ff0000")  # Red
        
        # Draw outer circle
        painter.setBrush(QBrush(led_color))
        painter.setPen(QPen(led_color, 2))
        painter.drawEllipse(5, 5, 40, 40)
        
        # Draw inner glow
        painter.setBrush(QBrush(QColor(led_color.red(), led_color.green(), led_color.blue(), 100)))
        painter.setPen(QPen(QColor(led_color.red(), led_color.green(), led_color.blue(), 50), 1))
class DataDashboard(QWidget):
    """Focused Data Dashboard with automotive-grade gauges and test monitoring"""
    
    # Signal configuration: (DBC_Signal_Name, Display_Name, Widget_Type, Min, Max, Unit)
    SIGNALS = [
        ("GridVol", "Grid Voltage", "gauge", 0, 300, "V"),
        ("GridCur", "Grid Current", "gauge", -50, 50, "A"),
        ("BusVol", "Bus Voltage", "gauge", 0, 500, "V"),
        ("BmsVol", "BMS Voltage", "gauge", 0, 300, "V"),
        ("HvVol", "HV Voltage", "gauge", 0, 300, "V"),
        ("HvCur", "HV Current", "gauge", -50, 50, "A"),
        ("LvVol", "LV Voltage", "gauge", 0, 30, "V"),
        ("LvCur", "LV Current", "gauge", -50, 50, "A"),
        ("OBC_temp", "OBC Temperature", "gauge", -40, 150, "C"),
        ("OBC_FET_Temp", "OBC FET Temp", "gauge", -40, 150, "C"),
        ("HP_DCDC_Temp", "HP DCDC Temp", "gauge", -40, 150, "C"),
        ("Transformer_temp", "Transformer Temp", "gauge", -40, 150, "C"),
    ]
    
    def __init__(self, signal_manager=None, can_mgr=None, parent=None):
        super().__init__(parent)
        self.signal_manager = signal_manager
        self.can_mgr = can_mgr
        self.gauges = {}
        self.displays = {}
        self.current_test_name = None
        
        self.init_ui()
        
        # Setup timer for 1 second updates
        if self.can_mgr:
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_from_signal_cache)
            self.update_timer.start(1000)  # Update every 1 second
    
    def set_test_name(self, test_name):
        """Set the running test name - called when test starts"""
        self.current_test_name = test_name
        if test_name:
            self.test_heading.setText(test_name)
            self.test_heading.setVisible(True)
        else:
            self.test_heading.setVisible(False)
        self.update()
    
    def init_ui(self):
        """Initialize the dashboard UI with automotive-grade design"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(12)
        
        # ===== TOP HEADER BAR (Test Name + CAN Status) =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        # Test Name Heading (left side)
        self.test_heading = QLabel("")
        test_heading_font = QFont("Arial", 18, QFont.Weight.Bold)
        self.test_heading.setFont(test_heading_font)
        self.test_heading.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                background-color: transparent;
            }
        """)
        self.test_heading.setVisible(False)  # Hidden until test starts
        header_layout.addWidget(self.test_heading)
        
        # Spacer
        header_layout.addStretch()
        
        # CAN Status LED (right side)
        self.status_led = StatusLED()
        self.status_led.set_connected(False)
        led_container = QVBoxLayout()
        led_container.setSpacing(5)
        led_container.addWidget(self.status_led, alignment=Qt.AlignmentFlag.AlignCenter)
        led_label = QLabel("CAN")
        led_label_font = QFont("Arial", 9, QFont.Weight.Bold)
        led_label.setFont(led_label_font)
        led_label.setStyleSheet("color: #888888;")
        led_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        led_container.addWidget(led_label)
        header_layout.addLayout(led_container)
        
        main_layout.addLayout(header_layout)
        
        # ===== SEPARATOR LINE =====
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #1a3a52; background-color: #1a3a52;")
        main_layout.addWidget(separator)
        
        # ===== SCROLLABLE GAUGE AREA =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #0f3460;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #00d4ff;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00ff88;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QGridLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create signal widgets - 4 columns layout (automotive grade)
        row, col = 0, 0
        for dbc_signal, display_name, widget_type, min_val, max_val, unit in self.SIGNALS:
            widget = RoundGaugeWidget(display_name, min_val, max_val, unit, dbc_signal)
            self.gauges[dbc_signal] = widget
            
            content_layout.addWidget(widget, row, col)
            col += 1
            if col >= 4:  # 4 columns per row
                col = 0
                row += 1
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Set overall stylesheet with enhanced aesthetics
        self.setStyleSheet("""
            QWidget {
                background-color: #0a0e27;
            }
        """)

    def update_from_signal_cache(self):
        """Update dashboard from CANManager's signal_cache every 1 second"""
        if not self.can_mgr:
            return
        
        try:
            # Update CAN status LED
            diag = self.can_mgr.get_diagnostics()
            is_connected = diag.get('connection_status') == 'Connected'
            self.status_led.set_connected(is_connected)
            
            # Get all signals
            all_signals = self.can_mgr.get_all_signals_from_cache()
            
            # Update gauges
            for dbc_signal, gauge in self.gauges.items():
                if dbc_signal in all_signals:
                    value = all_signals[dbc_signal].get('value')
                    if value is not None:
                        gauge.set_value(value)
            
        except Exception as e:
            print(f"[Dashboard] Error: {e}")




