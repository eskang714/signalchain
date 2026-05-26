"""
Acceptance tests – Features
TC-40: File Output via Markdown Module
TC-41: Input Behavior
TC-42: Empty Message Rejected

Existing state:
  ConversationView — implemented; Enter sends, Shift+Enter inserts newline,
    empty/whitespace input is rejected.
  markdown_output module — NOT yet implemented.

xfail policy:
  - TC-40: all XFAIL — signal_chain.modules.markdown_output does not exist;
    ImportError triggers xfail.
  - TC-41 Enter/Shift+Enter: PASS — ConversationView already handles these.
  - TC-42: PASS — ConversationView already rejects empty/whitespace input.

FLAG TC-40 (partial): "file appears as clickable card in the chat message" and
  "clicking the card opens or previews the file" are View rendering/interaction
  assertions not testable in a headless pytest run.
  Options:
    A) Accept that file-on-disk and result-contains-file-path cover the intent.
    B) Add widget tests once ConversationView renders file cards.
  Recommendation: Option A. Waiting for human decision.

FLAG TC-41 (partial): "textarea expands to show new line" is a visual layout assertion.
  Options:
    A) Accept that Shift+Enter inserts a newline into the text content (already tested).
    B) Assert QPlainTextEdit height changes — brittle in headless environments.
  Recommendation: Option A. Waiting for human decision.
"""
from PyQt6.QtCore import QObject, Qt, pyqtSignal

# Minimal test double for ConversationViewModel — used by TC-41 and TC-42 tests.
class _FakeVM(QObject):
    token_received = pyqtSignal(str)
    generation_started = pyqtSignal()
    generation_complete = pyqtSignal()
    generation_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.is_generating = False
        self.send_message_calls: list[str] = []

    def send_message(self, text: str) -> str:
        self.send_message_calls.append(text)
        return "sent"


# ---------------------------------------------------------------------------
# TC-40: File Output via Markdown Module
# ---------------------------------------------------------------------------

class TestTC40FileOutputViaMarkdownModule:
    """markdown_output writes files to output_dir and returns the path in its result."""

    def test_markdown_module_writes_file_to_output_dir(self, tmp_path):
        from signal_chain.modules.markdown_output import MarkdownOutputModule

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        module = MarkdownOutputModule(output_dir=output_dir)
        module.initialize()
        module.execute("write_file", {
            "filename": "report.md",
            "content": "# Report\n\nGenerated content.",
        })

        assert (output_dir / "report.md").exists(), (
            "markdown_output.execute('write_file') must create the file at output_dir/filename"
        )

    def test_markdown_module_result_contains_file_path(self, tmp_path):
        from signal_chain.modules.markdown_output import MarkdownOutputModule

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        module = MarkdownOutputModule(output_dir=output_dir)
        module.initialize()
        result = module.execute("write_file", {
            "filename": "notes.md",
            "content": "# Notes\n\nSome notes.",
        })

        assert isinstance(result, dict), "execute must return a dict"
        assert "file_path" in result, (
            "result must contain 'file_path' so the chat view can render a clickable card"
        )
        assert result["file_path"], "file_path must be a non-empty string"

    def test_markdown_module_created_file_has_correct_content(self, tmp_path):
        from signal_chain.modules.markdown_output import MarkdownOutputModule

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        content = "# Generated Report\n\n## Summary\n\nAI-generated content here."
        module = MarkdownOutputModule(output_dir=output_dir)
        module.initialize()
        module.execute("write_file", {"filename": "report.md", "content": content})

        written = (output_dir / "report.md").read_text()
        assert written == content, (
            "File written to disk must exactly match the content passed to write_file"
        )


# ---------------------------------------------------------------------------
# TC-41: Input Behavior
# ---------------------------------------------------------------------------

class TestTC41InputBehavior:
    """Enter submits the message; Shift+Enter inserts a newline without submitting."""

    def test_enter_key_sends_message(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)
        view._input.setPlainText("Hello from Enter")

        with qtbot.waitSignal(view.message_submitted, timeout=1000) as blocker:
            qtbot.keyPress(view._input, Qt.Key.Key_Return)

        assert blocker.args == ["Hello from Enter"], (
            "Pressing Enter must emit message_submitted with the current input text"
        )

    def test_shift_enter_inserts_newline_not_send(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)
        view._input.setPlainText("Line one")

        submitted: list[str] = []
        view.message_submitted.connect(submitted.append)
        qtbot.keyPress(view._input, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)

        assert len(submitted) == 0, "Shift+Enter must not submit the message"
        assert "\n" in view._input.toPlainText(), (
            "Shift+Enter must insert a newline into the input field"
        )


# ---------------------------------------------------------------------------
# TC-42: Empty Message Rejected
# ---------------------------------------------------------------------------

class TestTC42EmptyMessageRejected:
    """Empty or whitespace-only input is not submitted and triggers no generation."""

    def test_empty_input_message_submitted_not_emitted(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)

        submitted: list[str] = []
        view.message_submitted.connect(submitted.append)
        view._input.setPlainText("")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(submitted) == 0, (
            "message_submitted must not fire when input is empty"
        )

    def test_whitespace_only_input_message_submitted_not_emitted(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)

        submitted: list[str] = []
        view.message_submitted.connect(submitted.append)
        view._input.setPlainText("   \t   ")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(submitted) == 0, (
            "message_submitted must not fire for whitespace-only input"
        )

    def test_empty_input_generation_not_triggered(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)

        view._input.setPlainText("   ")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(vm.send_message_calls) == 0, (
            "vm.send_message must not be called for empty or whitespace-only input"
        )

    def test_send_button_stays_enabled_after_empty_input_attempt(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = _FakeVM()
        view.set_viewmodel(vm)

        view._input.setPlainText("")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert view._send_btn.isEnabled(), (
            "Send button must remain enabled after rejecting empty input — "
            "generation was not started so the disabled state must not apply"
        )
