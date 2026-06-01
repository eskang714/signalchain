"""
Tests for gateway wiring into the generation path — ticket #104.

Verifies that _GenerationThread.run() calls gateway.authorize("net:provider")
BEFORE invoking generate_stream, and handles NetworkBlockedError gracefully.

CONTRACT (source of truth for this file):
  - gateway.authorize("net:provider") is called at the start of run(), before
    any token is streamed.
  - If authorize raises NetworkBlockedError → generate_stream is NOT called;
    the error is emitted via generation_error; the thread does not crash.
  - If authorize passes → generate_stream runs and tokens stream normally.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-A  Injection point: ConversationViewModel(provider, gateway=None).
          The gateway is optional (None = no auth check, keeps existing call
          sites working).  _start_generation() passes it to _GenerationThread.
          Alternative: gateway injected separately via vm.set_gateway(gw).

  FLAG-B  Thread receives it: _GenerationThread(provider, messages, config,
          gateway=None).  At the top of run(), before the for-loop:
            if self._gateway is not None:
                self._gateway.authorize("net:provider")
          Alternative: gateway called in _start_generation() before the thread
          starts — synchronous, avoids threading complexity.

  FLAG-C  Blocked path surfaces via the existing generation_error signal.
          NetworkBlockedError is caught by the existing except-Exception block
          in run(), so no new signal or state is required.
          Alternative: a dedicated access_denied signal for distinguishing
          "blocked" from "network error".

XFAIL TRIGGER: ConversationViewModel(provider=..., gateway=...) raises
  TypeError today because __init__ does not accept a 'gateway' keyword.
  The import of NetworkBlockedError (which lives in an unbuilt module)
  provides a second, independent xfail trigger for the denied-path tests.
"""
from signal_chain.providers.base import BaseProvider, GenerationConfig, Message


class _FakeProvider(BaseProvider):
    """Yields a fixed token list; records whether generate_stream was called."""

    def __init__(self, tokens: tuple[str, ...] = ("hello",)) -> None:
        self._tokens = tokens
        self.generate_called: bool = False

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ):
        self.generate_called = True
        return iter(self._tokens)

    def list_models(self) -> list:
        return []

    def load_model(self, model_id: str) -> None:
        pass

    def validate_config(self) -> bool:
        return True


class _PermitGateway:
    """Test stub: permits every scope; records calls in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def authorize(self, scope: str) -> None:
        self.calls.append(scope)


class _DenyGateway:
    """Test stub: always raises NetworkBlockedError."""

    def authorize(self, scope: str) -> None:
        from signal_chain.modules.network_gateway import NetworkBlockedError

        raise NetworkBlockedError("blocked by test stub")


# ---------------------------------------------------------------------------
# Normal path — gateway permits, generation proceeds
# ---------------------------------------------------------------------------

class TestGatewayWiringNormalPath:

    def test_authorize_called_with_net_provider_before_generate_stream(self, qtbot):
        """gateway.authorize('net:provider') must precede generate_stream()."""
        from signal_chain.viewmodels.conversation import ConversationViewModel

        gateway = _PermitGateway()
        provider = _FakeProvider()
        # TypeError today (no 'gateway' kwarg) → xfail
        vm = ConversationViewModel(provider=provider, gateway=gateway)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("ping")

        assert "net:provider" in gateway.calls, (
            "gateway.authorize('net:provider') must be called during generation"
        )
        assert gateway.calls[0] == "net:provider", (
            "authorize must be the first gateway call — before generate_stream"
        )
        assert provider.generate_called, (
            "generate_stream must run when the gateway permits"
        )

    def test_tokens_stream_normally_when_gateway_permits(self, qtbot):
        """With a permitting gateway, token_received fires for each token."""
        from signal_chain.viewmodels.conversation import ConversationViewModel

        gateway = _PermitGateway()
        provider = _FakeProvider(tokens=("Hi", " there"))
        vm = ConversationViewModel(provider=provider, gateway=gateway)

        received: list[str] = []
        vm.token_received.connect(received.append)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("ping")

        assert received == ["Hi", " there"], (
            "token_received must fire for each token when the gateway permits"
        )


# ---------------------------------------------------------------------------
# Blocked path — NetworkBlockedError, generate_stream never runs
# ---------------------------------------------------------------------------

class TestGatewayWiringBlockedPath:

    def test_generate_stream_not_called_when_gateway_blocks(self, qtbot):
        """generate_stream must not be invoked when NetworkBlockedError is raised."""
        from signal_chain.modules.network_gateway import NetworkBlockedError  # noqa: F401
        from signal_chain.viewmodels.conversation import ConversationViewModel

        gateway = _DenyGateway()
        provider = _FakeProvider()
        vm = ConversationViewModel(provider=provider, gateway=gateway)

        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("ping")

        assert not provider.generate_called, (
            "generate_stream must not be invoked when the gateway raises "
            "NetworkBlockedError — the call must be aborted before reaching the provider"
        )

    def test_generation_error_emitted_when_gateway_blocks(self, qtbot):
        """generation_error must fire (not crash) when NetworkBlockedError is raised."""
        from signal_chain.modules.network_gateway import NetworkBlockedError  # noqa: F401
        from signal_chain.viewmodels.conversation import ConversationViewModel

        gateway = _DenyGateway()
        provider = _FakeProvider()
        vm = ConversationViewModel(provider=provider, gateway=gateway)

        errors: list[str] = []
        vm.generation_error.connect(errors.append)

        with qtbot.waitSignal(vm.generation_error, timeout=5000):
            vm.send_message("ping")

        assert len(errors) == 1, (
            "generation_error must fire exactly once when the gateway blocks"
        )
        assert errors[0], "error message must be non-empty"
