from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_USER_ROLE = Qt.ItemDataRole.UserRole


class ConversationListView(QWidget):
    """Left-panel list of saved conversations with search and context menu.

    Emits signals only — no model imports.
    """

    conversation_selected = pyqtSignal(str)
    new_chat_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    rename_requested = pyqtSignal(str, str)  # conv_id, new_title
    delete_requested = pyqtSignal(str)       # conv_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._renaming_conv_id: str | None = None
        self._original_title: str = ""

        self._new_btn = QPushButton("+ New Chat")
        self._new_btn.clicked.connect(self.new_chat_requested)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations…")
        self._search.textChanged.connect(self._on_search_changed)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemChanged.connect(self._on_item_changed)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._new_btn)
        layout.addWidget(self._search)
        layout.addWidget(self._list)
        self.setLayout(layout)

    def load_conversations(self, items: list[tuple]) -> None:
        """Populate the list.

        Accepts (conv_id, title) or (conv_id, title, date_str) tuples.
        When dates are present conversations are grouped by Today/Yesterday/Older.
        """
        normalized: list[tuple[str, str, str]] = []
        for item in items:
            if len(item) >= 3:
                normalized.append((item[0], item[1], item[2]))
            else:
                normalized.append((item[0], item[1], ""))
        self._populate_list(normalized)

    def _populate_list(self, items: list[tuple[str, str, str]]) -> None:
        self._list.clear()
        if not items:
            return

        has_dates = any(date for _, _, date in items)
        if not has_dates:
            for conv_id, title, _ in items:
                litem = QListWidgetItem(title or conv_id)
                litem.setData(_USER_ROLE, conv_id)
                self._list.addItem(litem)
            return

        today, yesterday, older = self._group_by_date(items)
        for label, group in [("Today", today), ("Yesterday", yesterday), ("Older", older)]:
            if not group:
                continue
            header = QListWidgetItem(label)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(header)
            for conv_id, title, _ in group:
                litem = QListWidgetItem(f"  {title or conv_id}")
                litem.setData(_USER_ROLE, conv_id)
                self._list.addItem(litem)

    def _group_by_date(
        self, items: list[tuple[str, str, str]]
    ) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]], list[tuple[str, str, str]]]:
        now = datetime.now(timezone.utc)
        today_date = now.date()
        yesterday_date = (now - timedelta(days=1)).date()
        today: list[tuple[str, str, str]] = []
        yesterday: list[tuple[str, str, str]] = []
        older: list[tuple[str, str, str]] = []
        for item in items:
            _, _, date_str = item
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                d = dt.date()
                if d == today_date:
                    today.append(item)
                elif d == yesterday_date:
                    yesterday.append(item)
                else:
                    older.append(item)
            except Exception:
                older.append(item)
        return today, yesterday, older

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        conv_id = item.data(_USER_ROLE)
        if conv_id:
            self.conversation_selected.emit(conv_id)

    def _on_search_changed(self, query: str) -> None:
        self.search_requested.emit(query)

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None or not item.data(_USER_ROLE):
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename(item)
        elif action == delete_action:
            self._confirm_delete(item)

    def _start_rename(self, item: QListWidgetItem) -> None:
        original_title = item.text().strip()
        # setText and setFlags both fire itemChanged. Keep _renaming_conv_id=None
        # until both are done so the guard in _on_item_changed ignores them.
        item.setText(original_title)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._renaming_conv_id = item.data(_USER_ROLE)
        self._original_title = original_title
        self._list.editItem(item)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        conv_id = item.data(_USER_ROLE)
        if not conv_id or conv_id != self._renaming_conv_id:
            return
        self._renaming_conv_id = None
        original = self._original_title
        self._original_title = ""
        # Remove editable flag BEFORE emitting rename_requested — the signal may
        # trigger load_conversations() which deletes this item from the list.
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        new_title = item.text().strip()
        if new_title and new_title != original:
            self.rename_requested.emit(conv_id, new_title)
        elif not new_title:
            item.setText(original)  # item still valid; rename_requested not emitted

    def _confirm_delete(self, item: QListWidgetItem) -> None:
        conv_id = item.data(_USER_ROLE)
        title = item.text().strip()
        result = QMessageBox.question(
            self,
            "Delete Conversation",
            f"Delete '{title}'?\n\nThis cannot be undone.",
        )
        if result == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(conv_id)
