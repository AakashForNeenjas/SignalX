from PyQt6.QtWidgets import QTabWidget, QWidget


def create_main_tabs():
    tabs = QTabWidget()
    tab_map = {
        "config": QWidget(),
        "error": QWidget(),
        "tools": QWidget(),
        "tracex": QWidget(),
        "canmatrix": QWidget(),
        "standards": QWidget(),
        "knowledge_base": QWidget(),
    }

    tabs.addTab(tab_map["config"], "Configuration")
    tabs.addTab(tab_map["error"], "CAN Tx Config")
    tabs.addTab(tab_map["tracex"], "TraceX")
    tabs.addTab(tab_map["canmatrix"], "CAN Matrix")
    tabs.addTab(tab_map["standards"], "Standards")
    tabs.addTab(tab_map["knowledge_base"], "Knowledge Base")
    tabs.addTab(tab_map["tools"], "App Log")

    tab_indices = {name: tabs.indexOf(widget) for name, widget in tab_map.items()}
    return tabs, tab_map, tab_indices
