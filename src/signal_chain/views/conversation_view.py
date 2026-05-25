from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget

from signal_chain.viewmodels.conversation import ConversationViewModel


class ConversationView(QWidget):
    """Chat area: scrolling message display + input box.

    Zero business logic — connects to ConversationViewModel signals only.
    """

    message_submitted = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm: ConversationViewModel | None = None

        self._display = QTextEdit()
        self._display.setReadOnly(True)

        self._input = QTextEdit()
        self._input.setFixedHeight(80)
        self._input.setPlaceholderText(
            "Type a message… (Enter to send, Shift+Enter for newline)"
        )
        self._input.installEventFilter(self)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._send)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)

        layout = QVBoxLayout()
        layout.addWidget(self._display)
        layout.addLayout(input_row)
        self.setLayout(layout)

    def set_viewmodel(self, vm: ConversationViewModel) -> None:
        self._vm = vm
        vm.token_received.connect(self._on_token)
        vm.generation_started.connect(self._on_generation_started)
        vm.generation_complete.connect(self._on_generation_complete)
        vm.generation_error.connect(self._on_error)

    def clear_display(self) -> None:
        self._display.clear()

    def show_conversation(self, messages: list[tuple[str, str]]) -> None:
        """Display a loaded conversation. messages: [(role, content), ...]"""
        self._display.clear()
        for role, content in messages:
            prefix = "You" if role == "user" else "Assistant"
            self._display.append(f"{prefix}: {content}\n")

    def _send(self) -> None:
        if self._vm is None:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._display.append(f"You: {text}")
        self._input.clear()
        self.message_submitted.emit(text)
        self._vm.send_message(text)

    def _on_token(self, tok: str) -> None:
        cursor = self._display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._display.setTextCursor(cursor)
        self._display.insertPlainText(tok)
        self._display.ensureCursorVisible()

    def _on_generation_started(self) -> None:
        self._display.append("Assistant: ")
        self._send_btn.setEnabled(False)

    def _on_generation_complete(self) -> None:
        self._display.append("")
        self._send_btn.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self._display.append(f"[Error: {message}]")
        self._send_btn.setEnabled(True)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            if (
                key_event.key() == Qt.Key.Key_Return
                and not (key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            ):
                self._send()
                return True
        return super().eventFilter(obj, event)
