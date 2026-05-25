from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

_USER_ROLE = Qt.ItemDataRole.UserRole


class ConversationListView(QWidget):
    """Left-panel list of saved conversations + New Chat button.

    Emits signals only — no model imports.
    """

    conversation_selected = pyqtSignal(str)  # conversation_id
    new_chat_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._new_btn = QPushButton("+ New Chat")
        self._new_btn.clicked.connect(self.new_chat_requested)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._new_btn)
        layout.addWidget(self._list)
        self.setLayout(layout)

    def load_conversations(self, items: list[tuple[str, str]]) -> None:
        """Populate the list. items: [(conversation_id, display_title), ...]"""
        self._list.clear()
        for conv_id, title in items:
            item = QListWidgetItem(title or conv_id)
            item.setData(_USER_ROLE, conv_id)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        conv_id = item.data(_USER_ROLE)
        if conv_id:
            self.conversation_selected.emit(conv_id)
