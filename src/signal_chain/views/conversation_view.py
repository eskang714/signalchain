from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence, QShortcut, QTextDocument
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from signal_chain.modules.writer import render_message as _render_message
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
        self._display_messages: list[tuple[str, str]] = []  # (role, content)
        self._current_response: str = ""

        # Toolbar row
        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self.export_requested)
        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(self._export_btn)
        toolbar_row.addStretch()

        # Message display
        self._display = QTextEdit()
        self._display.setReadOnly(True)

        # Find bar (Ctrl+F)
        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find in chat…")
        self._find_input.textChanged.connect(self._on_find_text_changed)
        self._find_input.installEventFilter(self)
        self._find_prev_btn = QPushButton("▲")
        self._find_prev_btn.setFixedWidth(28)
        self._find_prev_btn.setToolTip("Previous match")
        self._find_prev_btn.clicked.connect(self._find_prev)
        self._find_next_btn = QPushButton("▼")
        self._find_next_btn.setFixedWidth(28)
        self._find_next_btn.setToolTip("Next match")
        self._find_next_btn.clicked.connect(self._find_next)
        self._find_close_btn = QPushButton("✕")
        self._find_close_btn.setFixedWidth(28)
        self._find_close_btn.clicked.connect(self._hide_find_bar)
        find_bar_layout = QHBoxLayout()
        find_bar_layout.setContentsMargins(4, 2, 4, 2)
        find_bar_layout.addWidget(QLabel("Find:"))
        find_bar_layout.addWidget(self._find_input)
        find_bar_layout.addWidget(self._find_prev_btn)
        find_bar_layout.addWidget(self._find_next_btn)
        find_bar_layout.addWidget(self._find_close_btn)
        self._find_bar = QWidget()
        self._find_bar.setLayout(find_bar_layout)
        self._find_bar.setVisible(False)

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._show_find_bar)

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
        layout.addWidget(self._find_bar)
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
        self._display_messages = []
        self._current_response = ""
        self._display.clear()

    def show_conversation(self, messages: list[tuple[str, str]]) -> None:
        """Display a loaded conversation with Markdown rendering for assistant messages."""
        self._display_messages = list(messages)
        self._current_response = ""
        self._render_all_messages()

    _CSS = """
<style>
body {
  font-family: -apple-system, sans-serif;
  font-size: 13px;
  line-height: 1.6;
  margin: 6px;
  padding: 0;
}
h1 { font-size: 1.4em; margin: 12px 0 4px; }
h2 { font-size: 1.2em; margin: 10px 0 4px; }
h3 { font-size: 1.05em; margin: 8px 0 4px; }
code {
  font-family: 'Menlo', 'Courier New', monospace;
  font-size: 12px;
  background: rgba(128,128,128,0.15);
  padding: 1px 4px;
  border-radius: 3px;
}
pre {
  background: rgba(128,128,128,0.12);
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 6px 0;
  line-height: 1.25;
}
pre code { background: none; padding: 0; line-height: 1.25; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
th, td {
  border: 1px solid rgba(128,128,128,0.4);
  padding: 5px 10px;
  text-align: left;
}
th { font-weight: bold; }
blockquote {
  border-left: 3px solid rgba(128,128,128,0.5);
  margin: 6px 0;
  padding-left: 12px;
  opacity: 0.8;
}
hr { border: none; border-top: 1px solid rgba(128,128,128,0.3); }
</style>
"""

    def _render_all_messages(self) -> None:
        """Rebuild the display: user messages as escaped text, assistant via writer."""
        parts: list[str] = []
        for role, content in self._display_messages:
            if role == "assistant":
                body = _render_message(content, markdown_on=True)
                parts.append(f"<p><b>Assistant:</b></p>{body}<hr/>")
            else:
                escaped = (
                    content.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                parts.append(f"<p><b>You:</b> {escaped}</p>")
        full_html = (
            f"<html><head>{self._CSS}</head>"
            f"<body>{''.join(parts)}</body></html>"
        )
        self._display.setHtml(full_html)
        QTimer.singleShot(0, lambda: self._display.verticalScrollBar().setValue(
            self._display.verticalScrollBar().maximum()
        ))

    def _send(self) -> None:
        if self._vm is None:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._display_messages.append(("user", text))
        self._display.append(f"You: {text}")
        self._input.clear()
        self.message_submitted.emit(text)
        self._vm.send_message(text)

    def _on_retry(self) -> None:
        if self._vm is not None:
            self._vm.retry_last_message()
        self._retry_btn.setVisible(False)

    def _show_find_bar(self) -> None:
        self._find_bar.setVisible(True)
        self._find_input.setFocus()
        self._find_input.selectAll()

    def _hide_find_bar(self) -> None:
        self._find_bar.setVisible(False)
        self._find_input.clear()
        self._display.find("")  # clear highlight

    def _on_find_text_changed(self, term: str) -> None:
        if term:
            self._run_find(term, backward=False)
        else:
            self._display.find("")
            self._find_input.setStyleSheet("")

    def _find_next(self) -> None:
        self._run_find(self._find_input.text(), backward=False)

    def _find_prev(self) -> None:
        self._run_find(self._find_input.text(), backward=True)

    def _run_find(self, term: str, *, backward: bool) -> None:
        if not term:
            return
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags = QTextDocument.FindFlag.FindBackward
        found = self._display.find(term, flags)
        if not found:
            self._find_input.setStyleSheet("background-color: #ffcccc;")
            QTimer.singleShot(500, lambda: self._find_input.setStyleSheet(""))
        else:
            self._find_input.setStyleSheet("")

    def _dismiss_warning(self) -> None:
        self._warning_widget.setVisible(False)

    def _on_token(self, tok: str) -> None:
        self._current_response += tok
        cursor = self._display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._display.setTextCursor(cursor)
        self._display.insertPlainText(tok)
        self._display.ensureCursorVisible()

    def _on_generation_started(self) -> None:
        self._current_response = ""
        self._display.append("Assistant: ")
        self._send_btn.setEnabled(False)
        self._stop_btn.setVisible(True)
        self._retry_btn.setVisible(False)
        self._countdown_label.setVisible(False)

    def _on_generation_complete(self) -> None:
        if self._current_response:
            self._display_messages.append(("assistant", self._current_response))
        self._current_response = ""
        self._render_all_messages()
        self._send_btn.setEnabled(True)
        self._stop_btn.setVisible(False)

    def _on_error(self, message: str) -> None:
        self._current_response = ""
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
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            if obj is self._input:
                if (
                    key_event.key() == Qt.Key.Key_Return
                    and not (key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                ):
                    self._send()
                    return True
            elif obj is self._find_input:
                if key_event.key() == Qt.Key.Key_Escape:
                    self._hide_find_bar()
                    return True
                if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._find_next()
                    return True
        return super().eventFilter(obj, event)
