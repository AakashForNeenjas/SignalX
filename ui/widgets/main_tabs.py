from PyQt6.QtWidgets import QTabWidget, QWidget


def create_main_tabs():
    tabs = QTabWidget()
    tab_map = {
        "config": QWidget(),
        "instrument": QWidget(),
        "data": QWidget(),
        "error": QWidget(),
        "tools": QWidget(),
        "diagnostics": QWidget(),
        "logconv": QWidget(),
        "signalplot": QWidget(),
        "canmatrix": QWidget(),
        "powerbank": QWidget(),
        "standards": QWidget(),
    }

    tabs.addTab(tab_map["config"], "Configuration")
    tabs.addTab(tab_map["instrument"], "Instrument")
    tabs.addTab(tab_map["data"], "Data")
    tabs.addTab(tab_map["error"], "Error and Warnings")
    tabs.addTab(tab_map["tools"], "System Log")
    tabs.addTab(tab_map["diagnostics"], "Diagnostics")
    tabs.addTab(tab_map["logconv"], "Log Converter")
    tabs.addTab(tab_map["signalplot"], "Signal Plot")
    tabs.addTab(tab_map["canmatrix"], "CAN Matrix")
    tabs.addTab(tab_map["powerbank"], "Power Bank Tester")
    tabs.addTab(tab_map["standards"], "Standards")

    tab_indices = {name: tabs.indexOf(widget) for name, widget in tab_map.items()}
    return tabs, tab_map, tab_indices
