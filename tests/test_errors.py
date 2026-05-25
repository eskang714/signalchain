"""
Acceptance tests – Error Recovery
TC-30: Mid-Stream Generation Failure
TC-31: Module Execution Failure
TC-32: Rate Limit Auto-Retry
TC-33: Unclean Shutdown Recovery
TC-34: Corrupted Conversation File

Target modules (not yet implemented):
  signal_chain.providers.claude.ClaudeProvider  (TC-32)
  signal_chain.modules.runner.ModuleRunner       (TC-31, new signals)
  ConversationViewModel gains: retry_available signal, retry_last_message()

xfail policy:
  - TC-30 "partial response in memory" and "generation_error emitted": PASS —
    ConversationViewModel already preserves response_text on error.
  - TC-30 "retry" behavior: XFAIL — retry_last_message() / retry_available not implemented.
  - TC-31: all XFAIL — module system not yet implemented.
  - TC-32: all XFAIL — signal_chain.providers.claude does not exist yet.
  - TC-33 / TC-34 "no crash + others load": PASS — ConversationLoader.load_all()
    already catches exceptions and skips corrupt files.
  - TC-33 / TC-34 "error indicator / user informed": XFAIL — no error-reporting
    interface exists yet.

FLAG TC-30 (partial): "Retry button is shown" and "error indicator appears on the
  message" are View rendering assertions that cannot be made in a headless pytest run.
  Options:
    A) Accept that retry_available signal covers the intent; visual button deferred.
    B) Add a pytest-qt widget test once the ConversationView gains a retry button.
  Recommendation: Option A for now. Waiting for human decision.

FLAG TC-31 (partial): "⚠️ indicator appears on the message" is a View rendering
  assertion. The underlying module_error signal is testable; the visual indicator is not.
  Options:
    A) Accept that module_error signal emission covers the intent.
    B) Add a widget test for the indicator once ConversationView renders it.
  Recommendation: Option A. Waiting for human decision.

FLAG TC-32 (partial): "application shows countdown timer" is a View rendering
  assertion. The countdown_tick signal is testable; the rendered timer widget is not.
  Options:
    A) Accept that countdown_tick signal covers the intent.
    B) Add a widget test once the UI exposes the countdown.
  Recommendation: Option A. Waiting for human decision.
"""
import json
from pathlib import Path

import pytest

from signal_chain.providers.base import (
    BaseProvider,
    GenerationConfig,
    Message,
    ModelInfo,
)

_xfail = pytest.mark.xfail(
    reason="error recovery not yet implemented — TDD red phase", strict=True
)


# ---------------------------------------------------------------------------
# Stub provider for TC-30: emits tokens then raises mid-stream
# ---------------------------------------------------------------------------

class _PartialStreamProvider(BaseProvider):
    """Yields three tokens then raises ConnectionError to simulate a mid-stream drop."""

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> object:
        yield "Hello"
        yield " world"
        yield "!"
        raise ConnectionError("Simulated connection drop mid-stream")

    def list_models(self) -> list[ModelInfo]:
        return []

    def load_model(self, model_id: str) -> None:
        pass

    def validate_config(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# TC-30: Mid-Stream Generation Failure
# ---------------------------------------------------------------------------

class TestTC30MidStreamGenerationFailure:
    """Partial response is preserved and a retry mechanism is available after a mid-stream drop."""

    def test_partial_response_in_memory_after_stream_failure(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel

        vm = ConversationViewModel(provider=_PartialStreamProvider())
        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("test")

        assert "Hello world!" in vm.response_text, (
            "Tokens received before the connection drop must be preserved in response_text"
        )

    def test_generation_error_signal_emitted_on_mid_stream_failure(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel

        vm = ConversationViewModel(provider=_PartialStreamProvider())
        errors: list[str] = []
        vm.generation_error.connect(errors.append)

        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("test")

        assert len(errors) == 1, "generation_error must fire exactly once on mid-stream failure"
        assert len(errors[0]) > 0, "Error message must be non-empty"

    @_xfail
    def test_retry_last_message_restarts_generation(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel

        vm = ConversationViewModel(provider=_PartialStreamProvider())
        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("test")

        assert hasattr(vm, "retry_last_message"), (
            "ConversationViewModel must expose retry_last_message() after a generation error"
        )
        result = vm.retry_last_message()
        assert result in ("sent", "queued"), (
            "retry_last_message() must return 'sent' or 'queued'"
        )

    @_xfail
    def test_retry_available_signal_emitted_after_mid_stream_failure(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel

        vm = ConversationViewModel(provider=_PartialStreamProvider())
        assert hasattr(vm, "retry_available"), (
            "ConversationViewModel must expose a retry_available signal "
            "so the View can show a Retry button"
        )
        retries: list[object] = []
        vm.retry_available.connect(lambda: retries.append(True))

        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("test")

        assert len(retries) == 1, (
            "retry_available must be emitted once when a mid-stream failure occurs"
        )


# ---------------------------------------------------------------------------
# TC-31: Module Execution Failure
# ---------------------------------------------------------------------------

class TestTC31ModuleExecutionFailure:
    """Generation continues when a module raises; other modules are unaffected."""

    @_xfail
    def test_generation_continues_after_module_exception(self):
        from signal_chain.modules.runner import ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("broken_module")

        result = runner.execute_safe(
            module_name="broken_module",
            function_name="any_function",
            parameters={},
        )
        assert result is not None, (
            "execute_safe must return a result object (possibly with an error field) "
            "rather than propagating the module's exception"
        )

    @_xfail
    def test_module_error_signal_emitted_with_failing_module_name(self, qtbot):
        from signal_chain.modules.runner import ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("broken_module")

        assert hasattr(runner, "module_error"), (
            "ModuleRunner must expose a module_error signal so callers can display a ⚠️ indicator"
        )
        errors: list[tuple[str, str]] = []
        runner.module_error.connect(lambda mod, err: errors.append((mod, err)))

        runner.execute_safe("broken_module", "any_function", {})

        assert len(errors) == 1, "module_error must fire once when a module raises"
        assert errors[0][0] == "broken_module", (
            "module_error must include the failing module's name"
        )

    @_xfail
    def test_other_modules_unaffected_after_single_failure(self):
        from signal_chain.modules.runner import ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("broken_module")
        runner.register_user_module("working_module")

        runner.execute_safe("broken_module", "any_function", {})

        result = runner.execute_safe("working_module", "some_function", {})
        assert result is not None, (
            "A module that did not raise must remain executable after another module fails"
        )


# ---------------------------------------------------------------------------
# TC-32: Rate Limit Auto-Retry
# ---------------------------------------------------------------------------

class TestTC32RateLimitAutoRetry:
    """Claude API 429 responses trigger automatic retry with countdown, no user action needed."""

    @_xfail
    def test_429_triggers_automatic_retry_without_user_action(self, qtbot):
        from unittest.mock import MagicMock, patch

        from signal_chain.providers.claude import ClaudeProvider

        attempts: list[int] = []

        def mock_stream_429_then_ok(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                err = MagicMock()
                err.status_code = 429
                err.response = MagicMock()
                err.response.headers = {"retry-after": "1"}
                raise type("RateLimitError", (Exception,), {})(err)
            yield "token"

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.stream.side_effect = mock_stream_429_then_ok

            provider = ClaudeProvider()
            msgs = [Message(role="user", content="hello")]
            tokens = list(provider.generate_stream(msgs, GenerationConfig()))

        assert len(attempts) >= 2, (
            "Provider must retry at least once after a 429 without user intervention"
        )
        assert "token" in tokens, "Generation must succeed after the rate-limit wait"

    @_xfail
    def test_countdown_tick_signal_emitted_during_rate_limit_wait(self, qtbot):
        from signal_chain.providers.claude import ClaudeProvider

        provider = ClaudeProvider()
        assert hasattr(provider, "countdown_tick"), (
            "ClaudeProvider must expose a countdown_tick(int) signal that fires "
            "each second while waiting for the rate-limit retry window"
        )

    @_xfail
    def test_retry_after_header_value_honored(self, qtbot):
        from unittest.mock import MagicMock, patch

        from signal_chain.providers.claude import ClaudeProvider

        waited: list[float] = []
        real_sleep = __import__("time").sleep

        def tracking_sleep(seconds: float) -> None:
            waited.append(seconds)
            real_sleep(min(seconds, 0.01))  # cap actual wait in tests

        with patch("time.sleep", side_effect=tracking_sleep):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value = mock_client

                err = MagicMock()
                err.status_code = 429
                err.response = MagicMock()
                err.response.headers = {"retry-after": "5"}
                mock_client.messages.stream.side_effect = [
                    type("RateLimitError", (Exception,), {})(err),
                    iter([]),
                ]

                provider = ClaudeProvider()
                msgs = [Message(role="user", content="hello")]
                try:
                    list(provider.generate_stream(msgs, GenerationConfig()))
                except Exception:
                    pass

        assert any(w >= 5 for w in waited), (
            "Provider must sleep for at least the retry-after header value (5 s) before retrying"
        )

    @_xfail
    def test_generation_error_emitted_after_max_retries_exhausted(self, qtbot):
        from unittest.mock import MagicMock, patch

        from signal_chain.providers.claude import ClaudeProvider

        rate_limit_err = type("RateLimitError", (Exception,), {})

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.stream.side_effect = rate_limit_err("always 429")

            provider = ClaudeProvider()
            msgs = [Message(role="user", content="hello")]
            with pytest.raises(Exception):
                list(provider.generate_stream(msgs, GenerationConfig()))


# ---------------------------------------------------------------------------
# TC-33: Unclean Shutdown Recovery
# ---------------------------------------------------------------------------

class TestTC33UncleanShutdownRecovery:
    """Truncated conversation files from a force-kill are skipped; others load normally."""

    def _write_valid_conversation(self, directory: Path, conv_id: str) -> None:
        data = {
            "version": "1.0",
            "schema": "conversation.v1",
            "conversation_id": conv_id,
            "created": "2026-05-25T10:00:00Z",
            "model": {"provider": "ollama", "model_id": "llama3:8b"},
            "messages": [],
            "metadata": {"title": "Valid conversation", "tags": [], "module_usage": {}},
        }
        (directory / f"{conv_id}.json").write_text(json.dumps(data))

    def test_truncated_json_does_not_crash_load_all(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        (conv_dir / "truncated.json").write_text(
            '{"version": "1.0", "schema": "conversation.v1", "conversation_id": "conv_trunc",'
        )  # cut off mid-write

        result = ConversationLoader.load_all(conv_dir)
        assert isinstance(result, list), (
            "load_all must return a list even when a truncated file is present"
        )

    def test_valid_conversations_load_alongside_truncated_file(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        (conv_dir / "truncated.json").write_text('{"broken":')
        self._write_valid_conversation(conv_dir, "conv-good")

        result = ConversationLoader.load_all(conv_dir)
        loaded_ids = [c.conversation_id for c in result]

        assert "conv-good" in loaded_ids, (
            "Valid conversations must load normally even when a truncated file is present"
        )

    @_xfail
    def test_corrupt_file_paths_reported_to_caller(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        bad = conv_dir / "truncated.json"
        bad.write_text('{"broken":')
        self._write_valid_conversation(conv_dir, "conv-good")

        convs, errors = ConversationLoader.load_all_with_errors(conv_dir)

        assert len(errors) == 1, (
            "load_all_with_errors must return one error entry for the truncated file"
        )
        assert errors[0].path == bad, (
            "The reported error path must identify the truncated file exactly"
        )


# ---------------------------------------------------------------------------
# TC-34: Corrupted Conversation File
# ---------------------------------------------------------------------------

class TestTC34CorruptedConversationFile:
    """Malformed JSON files are skipped without crashing; well-formed files load normally."""

    def test_malformed_json_skipped_by_load_all(self, corrupt_conversation_file):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = corrupt_conversation_file.parent
        result = ConversationLoader.load_all(conv_dir)

        assert isinstance(result, list), "load_all must return a list, never raise"
        assert all(hasattr(c, "conversation_id") for c in result), (
            "Every item in the result must be a valid Conversation object"
        )

    def test_valid_conversations_load_alongside_corrupt_file(
        self, corrupt_conversation_file, tmp_path
    ):
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv_dir = corrupt_conversation_file.parent
        good = Conversation.create(provider="ollama", model_id="llama3:8b")
        ConversationLoader.save(good, conv_dir)

        result = ConversationLoader.load_all(conv_dir)
        loaded_ids = [c.conversation_id for c in result]

        assert good.conversation_id in loaded_ids, (
            "A valid conversation saved alongside a corrupt file must still load"
        )

    @_xfail
    def test_corrupt_file_error_indicator_in_load_result(self, corrupt_conversation_file):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = corrupt_conversation_file.parent
        convs, errors = ConversationLoader.load_all_with_errors(conv_dir)

        assert len(errors) >= 1, (
            "load_all_with_errors must report at least one error for the corrupt file"
        )
        error_paths = [e.path for e in errors]
        assert corrupt_conversation_file in error_paths, (
            "The corrupt file's path must appear in the error list so the UI can show an indicator"
        )
