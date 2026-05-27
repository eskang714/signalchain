"""
UI integration tests — Ticket #32

Views are tested in isolation with a FakeConversationViewModel.
The Application class is NOT instantiated in any test.

FLAG: Application not testable without real Ollama
Problem: app.py creates OllamaProvider() directly inside _on_main_ready() with no
  injection point. Bootstrapping Application in CI would require a live Ollama process.
Options:
  A) Add Application(provider=None) with default fallback to OllamaProvider
  B) Test views in isolation without the Application class (current approach)
Recommendation: Option B for immediate tests. Builder should add an injection point
  in the next cycle so end-to-end Application tests can run in CI without Ollama.
Waiting for human decision.
"""
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog


# ---------------------------------------------------------------------------
# Test double — stands in for ConversationViewModel with no provider/threads
# ---------------------------------------------------------------------------

class FakeConversationViewModel(QObject):
    token_received = pyqtSignal(str)
    generation_started = pyqtSignal()
    generation_complete = pyqtSignal()
    generation_error = pyqtSignal(str)
    retry_available = pyqtSignal()
    module_error = pyqtSignal(str)
    countdown_tick = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.is_generating = False
        self.send_message_calls: list[str] = []

    def send_message(self, text: str) -> str:
        self.send_message_calls.append(text)
        return "sent"

    def cancel_generation(self) -> None:
        pass

    def retry_last_message(self) -> str:
        return "queued"


# ---------------------------------------------------------------------------
# ConversationView
# ---------------------------------------------------------------------------

class TestConversationView:

    def test_renders_without_error(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        view.show()
        assert view.isVisible()

    def test_send_button_emits_message_submitted(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)
        view._input.setPlainText("Hello world")

        with qtbot.waitSignal(view.message_submitted, timeout=1000) as blocker:
            qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert blocker.args == ["Hello world"]

    def test_message_submitted_emitted_exactly_once(self, qtbot):
        """Send click must emit message_submitted exactly once — not zero, not twice."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        signal_calls: list[str] = []
        view.message_submitted.connect(signal_calls.append)
        view._input.setPlainText("Test message")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(signal_calls) == 1, (
            f"message_submitted must fire exactly once per Send click, fired {len(signal_calls)} times"
        )

    def test_vm_send_message_called_exactly_once(self, qtbot):
        """Send click must call vm.send_message exactly once — not twice via signal+direct."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)
        view._input.setPlainText("Test message")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(vm.send_message_calls) == 1, (
            f"vm.send_message must be called exactly once per Send click, "
            f"called {len(vm.send_message_calls)} times — "
            "check for double-call via signal connection + direct call"
        )

    def test_enter_key_sends_message(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)
        view._input.setPlainText("Enter message")

        with qtbot.waitSignal(view.message_submitted, timeout=1000) as blocker:
            qtbot.keyPress(view._input, Qt.Key.Key_Return)

        assert blocker.args == ["Enter message"]

    def test_shift_enter_inserts_newline_not_send(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)
        view._input.setPlainText("Line one")

        submitted: list[str] = []
        view.message_submitted.connect(submitted.append)
        qtbot.keyPress(view._input, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)

        assert len(submitted) == 0, "Shift+Enter must not submit the message"
        assert "\n" in view._input.toPlainText(), "Shift+Enter must insert a newline into the input"

    def test_token_received_appends_to_display(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        vm.generation_started.emit()
        vm.token_received.emit("Hello")
        vm.token_received.emit(" world")

        assert "Hello world" in view._display.toPlainText()

    def test_send_button_disabled_during_generation(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        assert view._send_btn.isEnabled(), "Send button must be enabled before generation starts"
        vm.generation_started.emit()
        assert not view._send_btn.isEnabled(), "Send button must be disabled while generation is in progress"

    def test_send_button_re_enabled_after_generation(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        vm.generation_started.emit()
        vm.generation_complete.emit()
        assert view._send_btn.isEnabled(), "Send button must be re-enabled after generation completes"

    def test_send_button_re_enabled_after_error(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        vm.generation_started.emit()
        vm.generation_error.emit("Network timeout")
        assert view._send_btn.isEnabled(), "Send button must be re-enabled after a generation error"

    def test_empty_input_does_not_submit(self, qtbot):
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        vm = FakeConversationViewModel()
        view.set_viewmodel(vm)

        submitted: list[str] = []
        view.message_submitted.connect(submitted.append)
        view._input.setPlainText("   ")
        qtbot.mouseClick(view._send_btn, Qt.MouseButton.LeftButton)

        assert len(submitted) == 0, "Whitespace-only input must not submit"
        assert len(vm.send_message_calls) == 0, "vm.send_message must not be called for empty input"


# ---------------------------------------------------------------------------
# ConversationListView
# ---------------------------------------------------------------------------

class TestConversationListView:

    def test_renders_without_error(self, qtbot):
        from signal_chain.views.conversation_list_view import ConversationListView

        view = ConversationListView()
        qtbot.addWidget(view)
        view.show()
        assert view.isVisible()

    def test_new_chat_button_emits_signal(self, qtbot):
        from signal_chain.views.conversation_list_view import ConversationListView

        view = ConversationListView()
        qtbot.addWidget(view)

        with qtbot.waitSignal(view.new_chat_requested, timeout=1000):
            qtbot.mouseClick(view._new_btn, Qt.MouseButton.LeftButton)

    def test_load_conversations_populates_list(self, qtbot):
        from signal_chain.views.conversation_list_view import ConversationListView

        view = ConversationListView()
        qtbot.addWidget(view)
        view.load_conversations([("conv-001", "First Chat"), ("conv-002", "Second Chat")])

        assert view._list.count() == 2
        assert view._list.item(0).text() == "First Chat"
        assert view._list.item(1).text() == "Second Chat"

    def test_clicking_item_emits_conversation_selected(self, qtbot):
        from signal_chain.views.conversation_list_view import ConversationListView

        view = ConversationListView()
        qtbot.addWidget(view)
        view.show()
        view.load_conversations([("conv-abc", "My Chat")])

        item_rect = view._list.visualItemRect(view._list.item(0))
        with qtbot.waitSignal(view.conversation_selected, timeout=1000) as blocker:
            qtbot.mouseClick(
                view._list.viewport(),
                Qt.MouseButton.LeftButton,
                pos=item_rect.center(),
            )

        assert blocker.args == ["conv-abc"]

    def test_load_conversations_replaces_previous_items(self, qtbot):
        from signal_chain.views.conversation_list_view import ConversationListView

        view = ConversationListView()
        qtbot.addWidget(view)
        view.load_conversations([("conv-001", "Old Chat")])
        view.load_conversations([("conv-002", "New Chat A"), ("conv-003", "New Chat B")])

        assert view._list.count() == 2
        assert view._list.item(0).text() == "New Chat A"


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class TestMainWindow:

    def test_renders_without_error(self, qtbot):
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()

    def test_all_three_panels_present(self, qtbot):
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window.conversation_list is not None, "Left panel (conversation list) must exist"
        assert window.conversation_view is not None, "Center panel (conversation view) must exist"

    def test_set_status_updates_status_bar(self, qtbot):
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.set_status("Generating…")

        assert window._status_bar.currentMessage() == "Generating…"

    def test_default_status_is_ready(self, qtbot):
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window._status_bar.currentMessage() == "Ready"


# ---------------------------------------------------------------------------
# StartupWizard
# ---------------------------------------------------------------------------

class TestStartupWizard:

    def test_renders_without_error(self, qtbot):
        from signal_chain.views.startup_wizard import StartupWizard

        wizard = StartupWizard()
        qtbot.addWidget(wizard)
        wizard.show()
        assert wizard.isVisible()

    def test_cancel_closes_dialog(self, qtbot):
        from signal_chain.views.startup_wizard import StartupWizard

        wizard = StartupWizard()
        qtbot.addWidget(wizard)
        wizard.show()
        wizard.reject()
        assert not wizard.isVisible()

    def test_cancel_result_is_rejected(self, qtbot):
        from signal_chain.views.startup_wizard import StartupWizard

        wizard = StartupWizard()
        qtbot.addWidget(wizard)
        wizard.reject()

        assert wizard.result() == QDialog.DialogCode.Rejected

    def test_ok_with_path_accepts_dialog(self, qtbot, tmp_path):
        from signal_chain.views.startup_wizard import StartupWizard

        wizard = StartupWizard()
        qtbot.addWidget(wizard)
        wizard._path_input.setText(str(tmp_path))
        wizard._on_ok()

        assert wizard.result() == QDialog.DialogCode.Accepted
        assert wizard.conversation_dir == tmp_path
        assert wizard.output_dir == tmp_path / "output"

    def test_ok_without_path_uses_placeholder(self, qtbot, tmp_path):
        from signal_chain.views.startup_wizard import StartupWizard

        wizard = StartupWizard()
        qtbot.addWidget(wizard)
        wizard._path_input.setPlaceholderText(str(tmp_path))
        wizard._path_input.setText("")
        wizard._on_ok()

        assert wizard.result() == QDialog.DialogCode.Accepted
        assert wizard.conversation_dir == tmp_path
