
def get_styles():
    return """
    QPushButton {
        border-radius: 4px;
        padding: 6px;
        font-weight: bold;
    }
    QPushButton[text="Force Stop"] {
        background-color: #d32f2f;
        color: white;
        border: 1px solid #b71c1c;
    }
    QPushButton[text="Force Stop"]:hover {
        background-color: #ef5350;
    }
    QPushButton[text="E-Stop"] {
        background-color: #d32f2f;
        color: white;
        border: 1px solid #b71c1c;
    }
    QPushButton[text="E-Stop"]:hover {
        background-color: #ef5350;
    }
    QTableWidget {
        gridline-color: #444;
    }
    QHeaderView::section {
        background-color: #333;
        padding: 4px;
        border: 1px solid #444;
    }
    QLabel {
        font-size: 12px;
    }
    """
