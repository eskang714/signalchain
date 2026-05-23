"""
Acceptance tests – Threading & Concurrency
TC-15: Multiple Simultaneous Conversations
TC-16: Background Generation Continuity
TC-17: Worker Thread Crash Isolation
TC-18: Concurrent Message Send
TC-19: Three Simultaneous Providers Under Load
"""
import time

import pytest

_xfail = pytest.mark.xfail(
    reason="Not yet implemented - TDD red phase",
    strict=True,
)


# ---------------------------------------------------------------------------
# Module-local mock providers
#
# These are defined here rather than in conftest because they depend on
# BaseProvider, which doesn't exist yet.  Once signal_chain.providers.base
# is implemented the mock classes will inherit from it; until then they raise
# ImportError at class definition time, which is the expected "red" state.
# ---------------------------------------------------------------------------

def _make_providers():
    """Import BaseProvider and return the three mock classes.  Raises ImportError if not ready."""
    from signal_chain.providers.base import (
        BaseProvider,
        GenerationConfig,
        Message,
        ModelInfo,
    )

    class SlowProvider(BaseProvider):
        """Streams tokens with a configurable per-token delay."""

        def __init__(self, tokens: list[str] | None = None, delay_per_token: float = 0.05):
            self._tokens = tokens if tokens is not None else [f"t{i}" for i in range(8)]
            self._delay = delay_per_token

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo(id="slow", name="Slow Mock")]

        def load_model(self, model_id: str) -> None:
            pass

        def validate_config(self) -> bool:
            return True

        def generate_stream(self, messages: list[Message], config: GenerationConfig):
            for token in self._tokens:
                time.sleep(self._delay)
                yield token

    class CrashingProvider(BaseProvider):
        """Yields a few tokens then raises RuntimeError to simulate a worker crash."""

        def __init__(self, tokens_before_crash: int = 2):
            self._tokens_before_crash = tokens_before_crash

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo(id="crash", name="Crashing Mock")]

        def load_model(self, model_id: str) -> None:
            pass

        def validate_config(self) -> bool:
            return True

        def generate_stream(self, messages: list[Message], config: GenerationConfig):
            for i in range(self._tokens_before_crash):
                time.sleep(0.02)
                yield f"pre_crash_{i}"
            raise RuntimeError("Simulated worker crash")

    class MidStreamErrorProvider(BaseProvider):
        """Yields a few tokens then raises ConnectionError to simulate a mid-stream API failure."""

        def __init__(self, tokens_before_error: int = 3):
            self._tokens_before_error = tokens_before_error

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo(id="midstream-error", name="Mid-Stream Error Mock")]

        def load_model(self, model_id: str) -> None:
            pass

        def validate_config(self) -> bool:
            return True

        def generate_stream(self, messages: list[Message], config: GenerationConfig):
            for i in range(self._tokens_before_error):
                time.sleep(0.02)
                yield f"partial_{i}"
            raise ConnectionError("Simulated mid-stream API failure")

    return SlowProvider, CrashingProvider, MidStreamErrorProvider


# ---------------------------------------------------------------------------
# TC-15: Multiple Simultaneous Conversations
# ---------------------------------------------------------------------------

class TestTC15MultipleSimultaneousConversations:
    """Two chats generate concurrently; UI stays responsive; no tokens from chat 1 are lost."""

    @_xfail
    def test_two_conversations_generating_at_the_same_time(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm1 = ConversationViewModel(provider=SlowProvider(delay_per_token=0.1))
        vm2 = ConversationViewModel(provider=SlowProvider(delay_per_token=0.1))

        vm1.send_message("Hello from chat 1")
        vm2.send_message("Hello from chat 2")

        assert vm1.is_generating, "Chat 1 must still be generating"
        assert vm2.is_generating, "Chat 2 must also be generating simultaneously"

    @_xfail
    def test_ui_thread_not_blocked_during_dual_generation(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm1 = ConversationViewModel(provider=SlowProvider(delay_per_token=0.1))
        vm2 = ConversationViewModel(provider=SlowProvider(delay_per_token=0.1))

        vm1.send_message("Chat 1")
        vm2.send_message("Chat 2")

        start = time.monotonic()
        qtbot.wait(100)
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, (
            f"UI thread was blocked ({elapsed:.2f}s elapsed); "
            "generation workers must run on separate QThreads"
        )

    @_xfail
    def test_all_chat1_tokens_received_while_chat2_runs(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        tokens = ["alpha", "bravo", "charlie", "delta"]
        vm1 = ConversationViewModel(
            provider=SlowProvider(tokens=tokens, delay_per_token=0.02)
        )
        vm2 = ConversationViewModel(
            provider=SlowProvider(tokens=["x", "y"], delay_per_token=0.02)
        )

        received: list[str] = []
        vm1.token_received.connect(lambda t: received.append(t))

        vm1.send_message("Chat 1 message")
        vm2.send_message("Chat 2 message")

        with qtbot.waitSignals(
            [vm1.generation_complete, vm2.generation_complete], timeout=5000
        ):
            pass

        assert received == tokens, (
            f"All Chat 1 tokens must arrive while Chat 2 runs concurrently; "
            f"expected {tokens}, got {received}"
        )


# ---------------------------------------------------------------------------
# TC-16: Background Generation Continuity
# ---------------------------------------------------------------------------

class TestTC16BackgroundGenerationContinuity:
    """Chat 1 completes fully in the background while the user views Chat 2."""

    @_xfail
    def test_background_generation_receives_all_tokens(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        tokens = ["the", " ", "answer", " ", "is", " ", "42"]
        vm1 = ConversationViewModel(
            provider=SlowProvider(tokens=tokens, delay_per_token=0.04)
        )
        vm2 = ConversationViewModel(
            provider=SlowProvider(tokens=["fg"], delay_per_token=0.02)
        )

        received: list[str] = []
        vm1.token_received.connect(lambda t: received.append(t))

        vm1.send_message("Background question")
        vm2.send_message("Foreground question")

        with qtbot.waitSignal(vm1.generation_complete, timeout=5000):
            pass

        assert received == tokens, (
            f"Background generation must complete with all tokens: "
            f"expected {tokens}, got {received}"
        )

    @_xfail
    def test_switching_back_shows_completed_response(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm1 = ConversationViewModel(
            provider=SlowProvider(tokens=["done"], delay_per_token=0.04)
        )
        vm2 = ConversationViewModel(
            provider=SlowProvider(tokens=["ok"], delay_per_token=0.02)
        )

        vm1.send_message("Background question")
        vm2.send_message("Foreground question")

        with qtbot.waitSignal(vm1.generation_complete, timeout=5000):
            pass

        assert vm1.response_text, (
            "response_text must be non-empty when the user switches back to Chat 1"
        )
        assert not vm1.is_generating


# ---------------------------------------------------------------------------
# TC-17: Worker Thread Crash Isolation
# ---------------------------------------------------------------------------

class TestTC17WorkerThreadCrashIsolation:
    """A crash in Chat 1's worker thread must not affect the UI, Chat 2, or Chat 3."""

    @_xfail
    def test_ui_thread_remains_responsive_after_crash(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, CrashingProvider, _ = _make_providers()

        vm1 = ConversationViewModel(provider=CrashingProvider())
        vm1.send_message("trigger crash")

        with qtbot.waitSignal(vm1.generation_error, timeout=3000):
            pass

        start = time.monotonic()
        qtbot.wait(100)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, (
            f"UI thread appears frozen after worker crash ({elapsed:.2f}s for 100 ms wait)"
        )

    @_xfail
    def test_other_conversations_unaffected_by_crash(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, CrashingProvider, _ = _make_providers()

        vm1 = ConversationViewModel(provider=CrashingProvider(tokens_before_crash=1))
        vm2 = ConversationViewModel(provider=SlowProvider(tokens=["chat2_done"]))
        vm3 = ConversationViewModel(provider=SlowProvider(tokens=["chat3_done"]))

        vm1.send_message("crash this")
        vm2.send_message("keep going")
        vm3.send_message("keep going")

        with qtbot.waitSignals(
            [vm2.generation_complete, vm3.generation_complete], timeout=5000
        ):
            pass

        assert vm2.response_text, "Chat 2 must complete normally after Chat 1 crashes"
        assert vm3.response_text, "Chat 3 must complete normally after Chat 1 crashes"

    @_xfail
    def test_crashed_conversation_shows_recoverable_error_state(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        _, CrashingProvider, __ = _make_providers()

        vm1 = ConversationViewModel(provider=CrashingProvider())
        vm1.send_message("crash trigger")

        with qtbot.waitSignal(vm1.generation_error, timeout=3000):
            pass

        assert vm1.error_state, (
            "Crashed conversation must expose a non-empty error_state; "
            "the UI must show a recoverable error, not a blank or frozen widget"
        )


# ---------------------------------------------------------------------------
# TC-18: Concurrent Message Send
# ---------------------------------------------------------------------------

class TestTC18ConcurrentMessageSend:
    """Sending a second message before the first completes: defined behavior, no dual generation."""

    @_xfail
    def test_first_send_returns_sent(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm = ConversationViewModel(provider=SlowProvider(delay_per_token=0.2))
        result = vm.send_message("First message")
        assert result == "sent"

    @_xfail
    def test_second_send_during_generation_returns_defined_result(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm = ConversationViewModel(provider=SlowProvider(delay_per_token=0.2))
        vm.send_message("First message")
        assert vm.is_generating

        result = vm.send_message("Second message while generating")

        assert result in ("queued", "cancelled_and_replaced"), (
            f"send_message during active generation must return 'queued' or "
            f"'cancelled_and_replaced', got {result!r}"
        )

    @_xfail
    def test_at_most_one_generation_active_at_a_time(self, qtbot):
        """generation_started and generation_complete must stay balanced at <= 1 active."""
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, __ = _make_providers()

        vm = ConversationViewModel(provider=SlowProvider(delay_per_token=0.2))
        active = [0]
        peak = [0]

        def on_start() -> None:
            active[0] += 1
            if active[0] > peak[0]:
                peak[0] = active[0]

        def on_done() -> None:
            active[0] = max(0, active[0] - 1)

        vm.generation_started.connect(on_start)
        vm.generation_complete.connect(on_done)
        vm.generation_error.connect(lambda _: on_done())

        vm.send_message("First message")
        vm.send_message("Second message while generating")

        qtbot.wait(200)

        assert peak[0] <= 1, (
            f"Peak concurrent generations was {peak[0]}; "
            "ConversationViewModel must never run two generations simultaneously"
        )


# ---------------------------------------------------------------------------
# TC-19: Three Simultaneous Providers Under Load
# ---------------------------------------------------------------------------

class TestTC19ThreeProvidersUnderLoad:
    """Claude API mid-stream failure: Ollama and local GGUF chats continue unaffected."""

    @_xfail
    def test_other_chats_complete_when_claude_api_fails(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, MidStreamErrorProvider = _make_providers()

        vm_ollama = ConversationViewModel(provider=SlowProvider(tokens=["ollama_ok"]))
        vm_claude = ConversationViewModel(
            provider=MidStreamErrorProvider(tokens_before_error=2)
        )
        vm_local = ConversationViewModel(provider=SlowProvider(tokens=["local_ok"]))

        vm_ollama.send_message("Ollama question")
        vm_claude.send_message("Claude question")
        vm_local.send_message("Local question")

        with qtbot.waitSignal(vm_claude.generation_error, timeout=3000):
            pass

        with qtbot.waitSignals(
            [vm_ollama.generation_complete, vm_local.generation_complete], timeout=5000
        ):
            pass

        assert vm_ollama.response_text, "Ollama chat must complete despite Claude API error"
        assert vm_local.response_text, "Local GGUF chat must complete despite Claude API error"

    @_xfail
    def test_partial_response_preserved_on_mid_stream_failure(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        _, __, MidStreamErrorProvider = _make_providers()

        vm_claude = ConversationViewModel(
            provider=MidStreamErrorProvider(tokens_before_error=3)
        )

        received: list[str] = []
        vm_claude.token_received.connect(lambda t: received.append(t))
        vm_claude.send_message("Claude question")

        with qtbot.waitSignal(vm_claude.generation_error, timeout=3000):
            pass

        assert vm_claude.error_state, (
            "error_state must be set after a mid-stream failure"
        )
        if received:
            assert vm_claude.response_text, (
                "Partial tokens received before the mid-stream error must be saved to response_text"
            )

    @_xfail
    def test_ui_responsive_during_three_provider_load(self, qtbot):
        from signal_chain.viewmodels.conversation import ConversationViewModel
        SlowProvider, _, MidStreamErrorProvider = _make_providers()

        vm_ollama = ConversationViewModel(provider=SlowProvider(delay_per_token=0.02))
        vm_claude = ConversationViewModel(
            provider=MidStreamErrorProvider(tokens_before_error=2)
        )
        vm_local = ConversationViewModel(provider=SlowProvider(delay_per_token=0.02))

        vm_ollama.send_message("Ollama")
        vm_claude.send_message("Claude")
        vm_local.send_message("Local")

        start = time.monotonic()
        qtbot.wait(100)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, (
            f"UI thread must remain responsive with three active providers "
            f"({elapsed:.2f}s for a 100 ms wait)"
        )
