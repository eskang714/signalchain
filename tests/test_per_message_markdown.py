"""
Tests for per-message markdown rendering — ticket #122.

Each assistant message records the rendering mode (markdown ON/OFF) that was
active when it was generated. That flag must survive save/reload, and the view
must honour it when re-rendering.

None of this exists yet. All tests xfail via TypeError, AttributeError, or
ValueError triggered inside the test body before any assertion is reached.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-A  Wiring seam: ConversationViewModel gains an optional pedalboard=
          kwarg (following ADR-008).  At _on_complete time the VM reads
          self._pedalboard._by_id["markdown"].enabled, passes it as
          render_markdown= into conv.add_message(), and stamps it on the
          persisted message.  xfail trigger: TypeError today because
          ConversationViewModel.__init__ does not accept 'pedalboard'.
          Alternative: app.py reads self._main_window._pedalboard_vm at
          generation_complete time and passes render_markdown into add_message.
          Either seam must produce conv.messages[-1].render_markdown matching
          the pedal state — that is the only thing tests 4-5 assert.

  FLAG-B  show_conversation() signature: currently list[tuple[str, str]].
          Will need a third element — (role, content, render_markdown: bool).
          Alternative: a richer type (MessageDisplay namedtuple or dataclass).
          xfail trigger: ValueError (too many values to unpack) in
          _render_all_messages() when 3-tuples are passed today.

  FLAG-C  View HTML assertion reliability: Qt's QTextEdit.setHtml() normalises
          HTML on ingestion — <strong> may become <span style="font-weight:600">.
          Test 6 checks that "**hello**" is ABSENT (asterisks consumed by
          markdown) and "**world**" is PRESENT (literal text, not rendered).
          This is stable because '*' is not an HTML-special character and Qt
          preserves it verbatim in toHtml().  If assertion is still flaky,
          spy on setHtml() pre-normalisation instead.
"""
import json

import pytest

from signal_chain.modules.network_gateway import _PermitGateway
from signal_chain.providers.base import BaseProvider, GenerationConfig, Message


_xfail = pytest.mark.xfail(
    strict=True,
    reason="per-message render_markdown not yet implemented",
)


class _FakeProvider(BaseProvider):
    """Yields a fixed token sequence; satisfies the BaseProvider interface."""

    def __init__(self, tokens: tuple[str, ...] = ("hello",)) -> None:
        self._tokens = tokens

    def generate_stream(self, messages: list[Message], config: GenerationConfig):
        return iter(self._tokens)

    def list_models(self) -> list:
        return []

    def load_model(self, model_id: str) -> None:
        pass

    def validate_config(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# 1. Model layer — ConversationMessage.render_markdown field
# ---------------------------------------------------------------------------

class TestConversationMessageRenderMarkdownField:

    @_xfail
    def test_conversation_message_has_render_markdown_field(self):
        """ConversationMessage must accept render_markdown= and expose it as an attribute."""
        from signal_chain.models.conversation import ConversationMessage

        # TypeError today — dataclass has no 'render_markdown' field → xfail
        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="hi",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=False,
        )
        assert msg.render_markdown is False


# ---------------------------------------------------------------------------
# 2. Model layer — save/load round-trip
# ---------------------------------------------------------------------------

class TestRenderMarkdownRoundTrip:

    @_xfail
    def test_render_markdown_false_round_trips_through_save_and_load(self, tmp_path):
        """render_markdown=False must survive serialisation to JSON and back."""
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv = Conversation.create(provider="test", model_id="test")
        # TypeError today — add_message does not accept render_markdown → xfail
        conv.add_message(role="assistant", content="hello", render_markdown=False)

        path = ConversationLoader.save(conv, tmp_path)
        loaded = ConversationLoader.load(path)

        assert loaded.messages[-1].render_markdown is False

    @_xfail
    def test_render_markdown_defaults_to_true_when_field_absent_from_json(self, tmp_path):
        """Old conversation JSON without render_markdown must load with render_markdown=True.

        Backward-compat: existing saved conversations open without error and
        assistant messages render with markdown by default.
        """
        from signal_chain.models.conversation import ConversationLoader

        data = {
            "version": "1.0",
            "schema": "conversation.v1",
            "conversation_id": "conv_legacy_compat",
            "created": "2026-01-01T00:00:00+00:00",
            "model": {"provider": "test", "model_id": "test"},
            "messages": [
                {
                    "id": "msg_0000",
                    "role": "assistant",
                    "content": "legacy message",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    # render_markdown intentionally absent — simulates old format
                }
            ],
            "metadata": {"title": "", "tags": [], "module_usage": {}},
        }
        path = tmp_path / "conv_legacy_compat.json"
        path.write_text(json.dumps(data))

        loaded = ConversationLoader.load(path)

        # AttributeError today — ConversationMessage has no render_markdown → xfail
        assert loaded.messages[0].render_markdown is True


# ---------------------------------------------------------------------------
# 3. Wiring layer — persisted message reflects markdown pedal state
# ---------------------------------------------------------------------------

class TestPersistedMessageRenderMarkdown:

    @_xfail
    def test_persisted_message_render_markdown_true_when_markdown_pedal_on(self, qtbot):
        """Persisted assistant message carries render_markdown=True when the markdown
        pedal was ON at generation time.

        FLAG-A: assumes ConversationViewModel gains a pedalboard= kwarg and stamps
        render_markdown into conv.add_message() at _on_complete time.
        TypeError today → xfail.
        """
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        pedalboard_vm = PedalboardViewModel()
        pedalboard_vm.toggle_module("markdown")  # OFF → ON

        provider = _FakeProvider(tokens=("hello",))
        gateway = _PermitGateway()

        # TypeError today — ConversationViewModel does not accept 'pedalboard' → xfail
        vm = ConversationViewModel(
            provider=provider, gateway=gateway, pedalboard=pedalboard_vm
        )

        conv = Conversation.create(provider="test", model_id="test")
        vm.set_conversation(conv)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("ping")

        assert conv.messages[-1].render_markdown is True

    @_xfail
    def test_persisted_message_render_markdown_false_when_markdown_pedal_off(self, qtbot):
        """Persisted assistant message carries render_markdown=False when the markdown
        pedal was OFF (default) at generation time.

        FLAG-A: see test above.
        """
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        pedalboard_vm = PedalboardViewModel()
        # markdown pedal starts disabled (PedalboardViewModel default: enabled=False)

        provider = _FakeProvider(tokens=("hello",))
        gateway = _PermitGateway()

        # TypeError today — ConversationViewModel does not accept 'pedalboard' → xfail
        vm = ConversationViewModel(
            provider=provider, gateway=gateway, pedalboard=pedalboard_vm
        )

        conv = Conversation.create(provider="test", model_id="test")
        vm.set_conversation(conv)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("ping")

        assert conv.messages[-1].render_markdown is False


# ---------------------------------------------------------------------------
# 4. View layer — per-message flag controls markdown rendering
# ---------------------------------------------------------------------------

class TestViewRenderMarkdownPerMessage:

    @_xfail
    def test_render_all_messages_uses_per_message_flag(self, qtbot):
        """show_conversation() must honour the per-message render_markdown flag.

        render_markdown=True  → content rendered as Markdown HTML (asterisks consumed)
        render_markdown=False → content rendered as escaped plain text (asterisks preserved)

        FLAG-B: show_conversation() currently accepts list[tuple[str, str]].
        Passing 3-tuples triggers ValueError: too many values to unpack in
        _render_all_messages() today → xfail.

        FLAG-C: Qt normalises HTML on setHtml(); <strong> may become a font-weight
        span in toHtml() output.  The assertion avoids checking tag names: it checks
        that literal "**hello**" is absent (markdown consumed the asterisks) and
        "**world**" is present (plain text preserved them).
        """
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)

        # ValueError: too many values to unpack in _render_all_messages() today → xfail
        view.show_conversation([
            ("assistant", "**hello**", True),   # markdown ON → asterisks consumed
            ("assistant", "**world**", False),  # markdown OFF → asterisks preserved
        ])

        html = view._display.toHtml()

        assert "**hello**" not in html, (
            "message with render_markdown=True must render **hello** as HTML bold "
            "(asterisks consumed by the markdown library, not present in toHtml output)"
        )
        assert "**world**" in html, (
            "message with render_markdown=False must appear as literal text "
            "(asterisks not consumed — * is not HTML-special and survives toHtml)"
        )
