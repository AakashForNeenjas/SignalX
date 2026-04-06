from __future__ import annotations

import html
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.knowledge_base import KnowledgeBaseDocument, KnowledgeBaseEntry, load_knowledge_base


SUMMARY_COLUMNS = ("No.", "Test Name", "Type", "Group", "Section")


class KnowledgeBaseTab(QWidget):
    def __init__(self, logger: logging.Logger | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.logger = logger
        self.document: KnowledgeBaseDocument | None = None
        self.filtered_entries: list[KnowledgeBaseEntry] = []
        self._building_table = False
        self._build_ui()
        self.load_embedded_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("DVP Knowledge Base")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff88;")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.source_label = QLabel("Source: bundled app data")
        self.source_label.setWordWrap(True)
        controls.addWidget(self.source_label, 1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by test name, standard, criteria, failure mode...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.apply_filters)
        controls.addWidget(self.search_edit, 1)
        layout.addLayout(controls)

        self.info_label = QLabel("Loading knowledge base...")
        layout.addWidget(self.info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, len(SUMMARY_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(SUMMARY_COLUMNS))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.table)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        splitter.addWidget(self.detail_view)
        splitter.setSizes([420, 780])
        layout.addWidget(splitter, 1)

    def load_embedded_data(self) -> None:
        try:
            self.document = load_knowledge_base()
            self.source_label.setText(f"Source: {self.document.source}")
            self.apply_filters()
        except Exception as exc:
            self.document = None
            self._log(logging.ERROR, f"Knowledge base load failed: {exc}")
            self.source_label.setText("Source: bundled app data")
            self._show_placeholder(f"Failed to load bundled knowledge base:\n{exc}")

    def apply_filters(self) -> None:
        if not self.document:
            self.filtered_entries = []
            self.table.setRowCount(0)
            return

        needle = self.search_edit.text().strip().lower()
        if needle:
            self.filtered_entries = [
                entry for entry in self.document.entries if needle in entry.search_text
            ]
        else:
            self.filtered_entries = list(self.document.entries)

        self._populate_table()
        self.info_label.setText(
            f"Showing {len(self.filtered_entries)} of {len(self.document.entries)} bundled tests"
        )

    def _populate_table(self) -> None:
        self._building_table = True
        self.table.setRowCount(len(self.filtered_entries))
        for row_index, entry in enumerate(self.filtered_entries):
            row_values = (
                entry.entry_id,
                entry.test_name,
                entry.test_type,
                entry.group,
                entry.section,
            )
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row_index)
                self.table.setItem(row_index, column_index, item)

        self._building_table = False
        if self.filtered_entries:
            self.table.selectRow(0)
            self._render_entry(self.filtered_entries[0])
        else:
            self.detail_view.setPlainText("No matching entries.")

        self.table.resizeColumnsToContents()

    def _on_selection_changed(self) -> None:
        if self._building_table:
            return
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        row_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(row_index, int) and 0 <= row_index < len(self.filtered_entries):
            self._render_entry(self.filtered_entries[row_index])

    def _render_entry(self, entry: KnowledgeBaseEntry) -> None:
        self.detail_view.setHtml(self._build_entry_html(entry))

    def _show_placeholder(self, message: str) -> None:
        self.table.setRowCount(0)
        self.info_label.setText(message.replace("\n", " "))
        self.detail_view.setPlainText(message)

    def _build_entry_html(self, entry: KnowledgeBaseEntry) -> str:
        title = html.escape(f"{entry.entry_id} - {entry.test_name}".strip(" -"))
        badges = []
        if entry.test_type:
            badges.append(f"<b>Type:</b> {html.escape(entry.test_type)}")
        if entry.group:
            badges.append(f"<b>Group:</b> {html.escape(entry.group)}")
        if entry.section:
            badges.append(f"<b>Section:</b> {html.escape(entry.section)}")

        sections = [
            "<html><body style='font-family: Segoe UI; color: #d8f9ff;'>",
            f"<h2 style='color:#00ff88;'>{title}</h2>",
        ]
        if badges:
            sections.append(f"<p>{' | '.join(badges)}</p>")
        sections.append(self._build_field_block("Master Index", entry.summary_fields))
        sections.append(self._build_field_block("Detailed Procedure", entry.detail_fields))
        sections.append("</body></html>")
        return "".join(sections)

    def _build_field_block(self, heading: str, fields: dict[str, str]) -> str:
        if not fields:
            return f"<h3>{html.escape(heading)}</h3><p>No data available.</p>"
        parts = [f"<h3 style='color:#00d4ff;'>{html.escape(heading)}</h3>"]
        for key, value in fields.items():
            safe_key = html.escape(key)
            safe_value = html.escape(value).replace("\n", "<br>")
            parts.append(
                "<div style='margin-bottom:10px;'>"
                f"<div style='font-weight:bold; color:#9fe7ff;'>{safe_key}</div>"
                f"<div style='white-space:pre-wrap; line-height:1.4;'>{safe_value}</div>"
                "</div>"
            )
        return "".join(parts)

    def _log(self, level: int, message: str) -> None:
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass
