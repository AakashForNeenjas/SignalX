"""Unit tests for main tab creation/order."""

import pytest

from ui.widgets.main_tabs import create_main_tabs


@pytest.mark.unit
def test_main_tabs_labels_and_order(qt_app):
    """Tabs must match the expected end-user order and names."""
    tabs, tab_map, _ = create_main_tabs()

    expected_labels = [
        "Configuration",
        "CAN Tx Config",
        "TraceX",
        "CAN Matrix",
        "Standards",
        "Knowledge Base",
        "App Log",
    ]
    actual_labels = [tabs.tabText(i) for i in range(tabs.count())]

    assert actual_labels == expected_labels
    assert "data" not in tab_map


@pytest.mark.unit
def test_main_tabs_internal_keys_preserved(qt_app):
    """Internal keys should stay stable for existing wiring."""
    _, tab_map, _ = create_main_tabs()

    assert "error" in tab_map
    assert "tools" in tab_map
    assert "knowledge_base" in tab_map
