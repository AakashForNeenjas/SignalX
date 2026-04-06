"""Unit tests for the bundled knowledge base."""

import pytest

from ui.knowledge_base import load_knowledge_base


@pytest.mark.unit
def test_load_knowledge_base_returns_bundled_entries():
    document = load_knowledge_base()

    assert document.source == "Bundled app data (DVP_Test_Procedures_Standard.xlsx)"
    assert len(document.entries) == 86


@pytest.mark.unit
def test_load_knowledge_base_contains_expected_first_entry():
    document = load_knowledge_base()
    first_entry = document.entries[0]

    assert first_entry.entry_id == "1"
    assert first_entry.test_name == "High temperature storage"
    assert first_entry.group == "Thermal"
    assert first_entry.section == "THERMAL"
    assert first_entry.summary_fields["Clause Title"] == "High temperature, non-operational dry heat storage"
    assert "Step 1:" in first_entry.detail_fields["Numbered Test Steps"]
    assert "solder joint weakening" in first_entry.search_text
