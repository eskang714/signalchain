"""
Tests for per-message markdown rendering — ticket #122.

When the markdown pedal is ON at generation time, the assistant response should
render with markdown.  When it is OFF, the response renders as plain text.  Each
message independently records the rendering mode active when it was generated.
The feature spans three layers: model, ViewModel, view.

None of this exists yet.  Changed classes are imported INSIDE each test body so
failures surface as XFAIL (AttributeError / TypeError / ValueError / ImportError),
never as collection errors.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-A  ViewModel contract for carrying render_markdown to the stored message.
          generation_complete currently carries NO args; changing its signature
          would break existing tests.  These tests assume instead that:
            - ConversationViewModel accepts a `pedalboard` reference
              (ConversationViewModel(provider=..., pedalboard=<PedalboardViewModel>))
            - on completion the VM stamps the assistant message it stores in
              self._conversation with render_markdown = (markdown pedal enabled).
          The assertion targets conv.messages[-1].render_markdown.  If the builder
          chooses a different seam (e.g. a new signal arg, or leaving message
          storage in app.py), update tests 4 and 5 — do NOT change the
          generation_complete signature silently.

  FLAG-B  show_conversation() signature.  Currently list[tuple[str, str]]
          (role, content).  Tests pass 3-tuples (role, content, render_markdown).
          If the builder prefers a richer type (dataclass / list of objects),
          update test 6 to match — the intent is per-message flag selection.

  FLAG-C  View HTML assertion is headless-reliable here because the test captures
          the HTML passed to QTextEdit.setHtml() (pre-normalization).  Reading
          back via toHtml() is NOT reliable — Qt rewrites <strong> to a
          font-weight span.  python-markdown renders **bold** as
          <strong>bold</strong>; the plain-text branch escapes & < > but leaves
          the literal **bold**, so the two modes are distinguishable in the
          captured HTML.
"""
import json

import pytest

from signal_chain.providers.base import BaseProvider, GenerationConfig, Message

_xfail = pytest.mark.xfail(
    strict=True,
    reason="per-message render_markdown not yet implemented",
)


class _FakeProvider(BaseProvider):
    """Yields a fixed token list so generation completes without a real backend."""

    def __init__(self, tokens: tuple[str, ...] = ("Hello",)) -> None:
        self._tokens = tokens

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ):
        for tok in self._tokens:
            yield tok

    def list_models(self) -> list:
        return []

    def load_model(self, model_id: str) -> None:
        pass

    def validate_config(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Model layer
# ---------------------------------------------------------------------------

class TestConversationMessageModel:

    @_xfail
    def test_conversation_message_has_render_markdown_field(self):
        """ConversationMessage must accept and store a render_markdown flag."""
        from signal_chain.models.conversation import ConversationMessage

        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="hi",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=False,
        )
        assert msg.render_markdown is False

    @_xfail
    def test_render_markdown_false_round_trips_through_save_and_load(self, tmp_path):
        """A message saved with render_markdown=False reloads with the flag intact."""
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv = Conversation.create(provider="test", model_id="m")
        conv.add_message(role="assistant", content="**bold**")
        conv.messages[0].render_markdown = False

        ConversationLoader.save(conv, tmp_path)
        reloaded = ConversationLoader.load(tmp_path / f"{conv.conversation_id}.json")

        assert reloaded.messages[0].render_markdown is False, (
            "render_markdown=False must survive save() and load()"
        )

    @_xfail
    def test_render_markdown_defaults_to_true_when_field_absent_from_json(self, tmp_path):
        """Old saved conversations (no render_markdown key) must load with True."""
        from signal_chain.models.conversation import ConversationLoader

        data = {
            "version": "1.0",
            "schema": "conversation.v1",
            "conversation_id": "conv_legacy",
            "created": "2026-01-01T00:00:00+00:00",
            "model": {"provider": "test", "model_id": "m"},
            "messages": [
                {
                    "id": "msg_0000",
                    "role": "assistant",
                    "content": "legacy message",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ],
            "metadata": {"title": "", "tags": [], "module_usage": {}},
        }
        path = tmp_path / "conv_legacy.json"
        path.write_text(json.dumps(data, indent=2))

        reloaded = ConversationLoader.load(path)

        assert reloaded.messages[0].render_markdown is True, (
            "messages from JSON without render_markdown must default to True "
            "(backward compatibility)"
        )


# ---------------------------------------------------------------------------
# ViewModel layer  (FLAG-A)
# ---------------------------------------------------------------------------

class TestConversationViewModelStampsFlag:

    @_xfail
    def test_message_has_render_markdown_true_when_markdown_pedal_on(self, qtbot):
        """Markdown pedal ON → stored assistant message gets render_markdown=True."""
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        pedalboard = PedalboardViewModel()
        pedalboard.toggle_module("markdown")  # OFF → ON

        provider = _FakeProvider(tokens=("**hi**",))
        vm = ConversationViewModel(provider=provider, pedalboard=pedalboard)  # FLAG-A
        conv = Conversation.create(provider="test", model_id="m")
        vm.set_conversation(conv)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("hi")

        assistant = [m for m in conv.messages if m.role == "assistant"]
        assert assistant, "VM must store the assistant message in the conversation"
        assert assistant[-1].render_markdown is True, (
            "assistant message must record render_markdown=True when the markdown "
            "pedal is enabled at generation time"
        )

    @_xfail
    def test_message_has_render_markdown_false_when_markdown_pedal_off(self, qtbot):
        """Markdown pedal OFF (default) → stored assistant message gets render_markdown=False."""
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        pedalboard = PedalboardViewModel()  # markdown starts OFF

        provider = _FakeProvider(tokens=("**hi**",))
        vm = ConversationViewModel(provider=provider, pedalboard=pedalboard)  # FLAG-A
        conv = Conversation.create(provider="test", model_id="m")
        vm.set_conversation(conv)

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("hi")

        assistant = [m for m in conv.messages if m.role == "assistant"]
        assert assistant, "VM must store the assistant message in the conversation"
        assert assistant[-1].render_markdown is False, (
            "assistant message must record render_markdown=False when the markdown "
            "pedal is disabled at generation time"
        )


# ---------------------------------------------------------------------------
# View layer  (FLAG-B, FLAG-C)
# ---------------------------------------------------------------------------

class TestConversationViewPerMessageRender:

    @_xfail
    def test_render_all_messages_uses_per_message_flag(self, qtbot):
        """show_conversation renders each message per its own render_markdown flag."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)

        # Capture the HTML passed to setHtml — pre-Qt-normalization (FLAG-C).
        captured: dict[str, str] = {}
        view._display.setHtml = lambda html: captured.update(html=html)

        # FLAG-B: 3-tuple (role, content, render_markdown).
        view.show_conversation(
            [
                ("assistant", "**bold**", True),   # render markdown → <strong>
                ("assistant", "**bold**", False),  # plain text → literal **bold**
            ]
        )

        html = captured.get("html", "")
        assert "<strong>bold</strong>" in html, (
            "the render_markdown=True message must be rendered as markdown"
        )
        assert html.count("<strong>") == 1, (
            "only the render_markdown=True message must be rendered as markdown"
        )
        assert "**bold**" in html, (
            "the render_markdown=False message must stay literal plain text"
        )
