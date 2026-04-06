from __future__ import annotations

from dataclasses import dataclass

from ui.knowledge_base_data import KNOWLEDGE_BASE_ENTRIES, KNOWLEDGE_BASE_SOURCE


@dataclass(frozen=True)
class KnowledgeBaseEntry:
    entry_id: str
    test_name: str
    test_type: str
    group: str
    section: str
    summary_fields: dict[str, str]
    detail_fields: dict[str, str]
    search_text: str


@dataclass(frozen=True)
class KnowledgeBaseDocument:
    source: str
    entries: tuple[KnowledgeBaseEntry, ...]


def load_knowledge_base() -> KnowledgeBaseDocument:
    entries = tuple(_build_entry(raw_entry) for raw_entry in KNOWLEDGE_BASE_ENTRIES)
    return KnowledgeBaseDocument(
        source=f"Bundled app data ({KNOWLEDGE_BASE_SOURCE})",
        entries=entries,
    )


def _build_entry(raw_entry: dict[str, object]) -> KnowledgeBaseEntry:
    return KnowledgeBaseEntry(
        entry_id=str(raw_entry["entry_id"]),
        test_name=str(raw_entry["test_name"]),
        test_type=str(raw_entry["test_type"]),
        group=str(raw_entry["group"]),
        section=str(raw_entry["section"]),
        summary_fields=_string_dict(raw_entry["summary_fields"]),
        detail_fields=_string_dict(raw_entry["detail_fields"]),
        search_text=str(raw_entry["search_text"]),
    )


def _string_dict(value: object) -> dict[str, str]:
    raw_dict = value if isinstance(value, dict) else {}
    return {str(key): str(item) for key, item in raw_dict.items()}
