from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QFrame, QLabel, QGridLayout)
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

class InstrumentWidget(QWidget):
    def __init__(self, instrument_name, default_url="http://localhost"):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Header with Name and URL Input
        header_layout = QHBoxLayout()
        self.name_label = QLabel(instrument_name)
        self.name_label.setStyleSheet("font-weight: bold;")
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Instrument IP/URL")
        self.url_input.setText(default_url)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.load_url)
        
        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.url_input)
        header_layout.addWidget(self.btn_connect)
        
        self.layout.addLayout(header_layout)
        
        # Web View
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("about:blank"))
        self.web_view.setStyleSheet("background-color: white;") # Placeholder style
        
        # Frame for web view to give it a border
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self.web_view)
        
        self.layout.addWidget(frame)
        
    def load_url(self):
        url_text = self.url_input.text().strip()
        if not url_text.startswith("http://") and not url_text.startswith("https://"):
            url_text = "http://" + url_text
        
        self.web_view.setUrl(QUrl(url_text))

class InstrumentView(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        # User requested "horizontally one by one", implying vertical stacking of rows
        layout = QVBoxLayout(self)
        
        # Create 3 Instrument Widgets with specific names and IPs from config
        # Grid Emulator: 192.168.4.52
        self.inst_grid = InstrumentWidget("Grid Simulator", "http://192.168.4.52")
        
        # Bi-Directional Power Supply: 192.168.4.53
        self.inst_ps = InstrumentWidget("Bi-Directional PS", "http://192.168.4.53")
        
        # Oscilloscope: 192.168.4.51
        self.inst_scope = InstrumentWidget("Oscilloscope", "http://192.168.4.51")
        
        layout.addWidget(self.inst_grid)
        layout.addWidget(self.inst_ps)
        layout.addWidget(self.inst_scope)
