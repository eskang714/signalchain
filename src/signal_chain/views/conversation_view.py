from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from signal_chain.viewmodels.conversation import ConversationViewModel


class ConversationView(QWidget):
    """Chat area: scrolling message display + input box.

    Zero business logic — connects to ConversationViewModel signals only.
    """

    message_submitted = pyqtSignal(str)
    stop_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm: ConversationViewModel | None = None

        # Toolbar row
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self.export_requested)
        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(self._export_btn)
        toolbar_row.addStretch()

        # Message display
        self._display = QTextEdit()
        self._display.setReadOnly(True)

        # Warning label (module errors)
        self._warning_label = QLabel("")
        self._dismiss_btn = QPushButton("×")
        self._dismiss_btn.setFixedWidth(24)
        self._dismiss_btn.clicked.connect(self._dismiss_warning)
        warning_row = QHBoxLayout()
        warning_row.addWidget(self._warning_label)
        warning_row.addWidget(self._dismiss_btn)
        self._warning_widget = QWidget()
        self._warning_widget.setLayout(warning_row)
        self._warning_widget.setVisible(False)

        # Countdown label (rate-limit retry)
        self._countdown_label = QLabel("")
        self._countdown_label.setVisible(False)

        # Retry button
        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self._on_retry)

        # Input row
        self._input = QTextEdit()
        self._input.setFixedHeight(80)
        self._input.setPlaceholderText(
            "Type a message… (Enter to send, Shift+Enter for newline)"
        )
        self._input.installEventFilter(self)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._send)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self.stop_requested)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)
        input_row.addWidget(self._stop_btn)

        layout = QVBoxLayout()
        layout.addLayout(toolbar_row)
        layout.addWidget(self._display)
        layout.addWidget(self._warning_widget)
        layout.addWidget(self._countdown_label)
        layout.addWidget(self._retry_btn)
        layout.addLayout(input_row)
        self.setLayout(layout)

    def set_viewmodel(self, vm: ConversationViewModel) -> None:
        self._vm = vm
        vm.token_received.connect(self._on_token)
        vm.generation_started.connect(self._on_generation_started)
        vm.generation_complete.connect(self._on_generation_complete)
        vm.generation_error.connect(self._on_error)
        vm.retry_available.connect(self._on_retry_available)
        vm.module_error.connect(self._on_module_error)
        vm.countdown_tick.connect(self._on_countdown_tick)
        self.stop_requested.connect(vm.cancel_generation)

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

    def _on_retry(self) -> None:
        if self._vm is not None:
            self._vm.retry_last_message()
        self._retry_btn.setVisible(False)

    def _dismiss_warning(self) -> None:
        self._warning_widget.setVisible(False)

    def _on_token(self, tok: str) -> None:
        cursor = self._display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._display.setTextCursor(cursor)
        self._display.insertPlainText(tok)
        self._display.ensureCursorVisible()

    def _on_generation_started(self) -> None:
        self._display.append("Assistant: ")
        self._send_btn.setEnabled(False)
        self._stop_btn.setVisible(True)
        self._retry_btn.setVisible(False)
        self._countdown_label.setVisible(False)

    def _on_generation_complete(self) -> None:
        self._display.append("")
        self._send_btn.setEnabled(True)
        self._stop_btn.setVisible(False)

    def _on_error(self, message: str) -> None:
        self._display.append(f"[Error: {message}]")
        self._send_btn.setEnabled(True)
        self._stop_btn.setVisible(False)

    def _on_retry_available(self) -> None:
        self._retry_btn.setVisible(True)

    def _on_module_error(self, error: str) -> None:
        self._warning_label.setText(f"Module error: {error}")
        self._warning_widget.setVisible(True)

    def _on_countdown_tick(self, seconds: int) -> None:
        if seconds > 0:
            self._countdown_label.setText(f"Retrying in {seconds}s…")
            self._countdown_label.setVisible(True)
        else:
            self._countdown_label.setVisible(False)

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
