"""
Tests for per-message (frozen-at-generation) markdown rendering — ticket #130.

Supersedes the global pedal-driven approach from #127. The per-message model:
  - Each assistant message is stamped with the markdown pedal's is_enabled state
    at the moment the generation completes.
  - The stamp is immutable — toggling the pedal after generation never re-renders
    existing messages.
  - The pedal's only live effect is on the NEXT message generated.

CONTRACT (all xfail until #129 builder tock lands):
  - ConversationMessage gains a render_markdown: bool field.
  - ConversationLoader saves and restores render_markdown; JSON without the field
    loads cleanly, defaulting to markdown-on (Elk's decision, ticket #130).
  - ConversationView renders each assistant message according to its own
    render_markdown flag, not a single global mode.
  - The generation pipeline stamps render_markdown = pedalboard.is_enabled("markdown")
    at completion time.

CONTRACT DECISIONS (decided — ticket #152):

  FLAG-A  Stamp location: DECIDED — ViewModel (Option 1).
          ConversationViewModel gains a pedalboard= constructor argument.
          The stamp is applied in _on_complete:
            render_markdown = pedalboard.is_enabled("markdown")
          No pedalboard wired / module absent → False (falsy default).
          Builder owns the mechanism (moving the message-append into
          _on_complete, the per-message setter shape, wiring the pedalboard
          arg into integration-test call sites) — but this decision is fixed.

  FLAG-B  Data shape: DECIDED — list[ConversationMessage] (Option b).
          show_conversation takes list[ConversationMessage];
          _display_messages stores the same. Tests below already assume
          this shape — no adjustment needed when the builder lands it.

  Stamp value: on → render_markdown=True; off → False; no pedalboard /
          module absent → False (falsy).

  Loader default: a stored message without render_markdown loads as True
          (historical fidelity — pre-stamp messages were generated in the
          all-markdown era; Elk's decision, ticket #130).

HTML assertions use asterisk presence/absence rather than tag names.
Qt's toHtml() normalises <strong> to font-weight spans but never
re-inserts source asterisks — "**bold**" absent ↔ markdown rendered.
"""
import json

import pytest

_xfail = pytest.mark.xfail(
    strict=True,
    reason="per-message frozen markdown rendering not yet implemented",
)


class _FakeProvider:
    """Minimal provider stub: yields '**bold**' without real network calls.

    Shared across TestMainWindowIntegration tests so asterisk presence/absence
    in toHtml() is a reliable rendering signal.
    """

    def list_models(self):
        return []

    def load_model(self, model_id):
        pass

    def generate_stream(self, messages, config):
        yield "**bold**"

    def validate_config(self):
        return True


# ---------------------------------------------------------------------------
# Model layer — ConversationMessage carries render_markdown
# ---------------------------------------------------------------------------

class TestConversationMessageModel:

    @_xfail
    def test_render_markdown_true_round_trips_through_json(self, tmp_path):
        """render_markdown=True must survive a save/load cycle."""
        from signal_chain.models.conversation import (
            Conversation,
            ConversationLoader,
            ConversationMessage,
        )

        # TypeError today: ConversationMessage has no render_markdown field → xfail
        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="**bold**",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=True,
        )
        conv = Conversation.create(provider="test", model_id="test-model")
        conv.messages.append(msg)

        path = ConversationLoader.save(conv, tmp_path)
        loaded = ConversationLoader.load(path)

        assert loaded.messages[0].render_markdown is True, (
            "render_markdown=True must survive JSON serialisation and load"
        )

    @_xfail
    def test_render_markdown_false_round_trips_through_json(self, tmp_path):
        """render_markdown=False must survive a save/load cycle."""
        from signal_chain.models.conversation import (
            Conversation,
            ConversationLoader,
            ConversationMessage,
        )

        # TypeError today → xfail
        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="**bold**",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=False,
        )
        conv = Conversation.create(provider="test", model_id="test-model")
        conv.messages.append(msg)

        path = ConversationLoader.save(conv, tmp_path)
        loaded = ConversationLoader.load(path)

        assert loaded.messages[0].render_markdown is False, (
            "render_markdown=False must survive JSON serialisation and load"
        )

    @_xfail
    def test_missing_render_markdown_defaults_to_markdown_on(self, tmp_path):
        """JSON without render_markdown must load with render_markdown=True (markdown-on default).

        Covers existing conversations and conversations saved by old code.
        Default is markdown-on per Elk's decision in ticket #130.
        """
        from signal_chain.models.conversation import ConversationLoader

        data = {
            "version": "1.0",
            "schema": "conversation.v1",
            "conversation_id": "conv_compat_130",
            "created": "2026-01-01T00:00:00+00:00",
            "model": {"provider": "test", "model_id": "test"},
            "messages": [
                {
                    "id": "msg_0000",
                    "role": "assistant",
                    "content": "**bold**",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    # render_markdown intentionally absent
                }
            ],
            "metadata": {"title": "", "tags": [], "module_usage": {}},
        }
        path = tmp_path / "conv_no_rm.json"
        path.write_text(json.dumps(data))

        conv = ConversationLoader.load(path)

        # AttributeError today: ConversationMessage has no render_markdown → xfail
        assert conv.messages[0].render_markdown is True, (
            "missing render_markdown must default to True (markdown-on) per Elk's decision"
        )


# ---------------------------------------------------------------------------
# View layer — per-message render_markdown flag drives rendering
# ---------------------------------------------------------------------------

class TestViewPerMessageRendering:

    @_xfail
    def test_message_with_render_markdown_true_consumes_asterisks(self, qtbot):
        """A message with render_markdown=True must be rendered as HTML — asterisks consumed."""
        from signal_chain.models.conversation import ConversationMessage
        from signal_chain.views.conversation_view import ConversationView

        # TypeError today: render_markdown not a field → xfail
        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="**bold**",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=True,
        )
        view = ConversationView()
        qtbot.addWidget(view)
        # FLAG-B: show_conversation shape; view tests assume ConversationMessage objects
        view.show_conversation([msg])

        html = view._display.toHtml()
        assert "**bold**" not in html, (
            "render_markdown=True: asterisks must be consumed by markdown rendering; "
            "**bold** must not appear literally in toHtml() output (FLAG-B)"
        )

    @_xfail
    def test_message_with_render_markdown_false_preserves_asterisks(self, qtbot):
        """A message with render_markdown=False must display as plain text — asterisks present."""
        from signal_chain.models.conversation import ConversationMessage
        from signal_chain.views.conversation_view import ConversationView

        # TypeError today → xfail
        msg = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="**bold**",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=False,
        )
        view = ConversationView()
        qtbot.addWidget(view)
        view.show_conversation([msg])

        html = view._display.toHtml()
        assert "**bold**" in html, (
            "render_markdown=False: **bold** must appear as literal text; "
            "* is not HTML-special and must survive setHtml/toHtml (FLAG-B)"
        )

    @_xfail
    def test_mixed_render_markdown_flags_render_per_message(self, qtbot):
        """A conversation with mixed flags must render each message in its own mode,
        not one global mode for the whole conversation."""
        from signal_chain.models.conversation import ConversationMessage
        from signal_chain.views.conversation_view import ConversationView

        # TypeError today → xfail
        msg_on = ConversationMessage(
            id="msg_0000",
            role="assistant",
            content="**markdown on**",
            timestamp="2026-01-01T00:00:00+00:00",
            render_markdown=True,
        )
        msg_off = ConversationMessage(
            id="msg_0001",
            role="assistant",
            content="**markdown off**",
            timestamp="2026-01-01T00:00:01+00:00",
            render_markdown=False,
        )
        view = ConversationView()
        qtbot.addWidget(view)
        view.show_conversation([msg_on, msg_off])

        html = view._display.toHtml()
        assert "**markdown on**" not in html, (
            "render_markdown=True message: asterisks must be consumed (FLAG-B)"
        )
        assert "**markdown off**" in html, (
            "render_markdown=False message: asterisks must be preserved (FLAG-B)"
        )


# ---------------------------------------------------------------------------
# Integration — MainWindow: pedal stamps at generation, toggle freezes
# ---------------------------------------------------------------------------

class TestMainWindowIntegration:

    @_xfail
    def test_pedal_stamps_at_generation_and_toggle_is_frozen(self, qtbot):
        """Full integration: pedal state at generation drives the stamp; toggling
        afterwards does NOT re-render already-displayed messages.

        Setup:  pedal OFF (default) → generation of "**bold**"
        Assert: rendered HTML shows asterisks (plain text — pedal was off)
        Toggle: pedal ON
        Assert: HTML unchanged — the completed message is frozen at its stamp

        xfail today:
          - _render_all_messages() renders unconditionally as markdown regardless
            of pedal state, so asterisks are consumed → first assertion fails.
          - No wiring exists between _pedalboard_vm and rendering at all.

        This test covers the footswitch-seam gap that #127's global re-render design
        missed. FLAG-A applies: stamp location determines how the pedalboard state
        reaches the completed message.
        """
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.views.main_window import MainWindow

        class _FakeProvider:
            def list_models(self):
                return []
            def load_model(self, model_id):
                pass
            def generate_stream(self, messages, config):
                yield "**bold**"
            def validate_config(self):
                return True

        window = MainWindow()
        qtbot.addWidget(window)

        vm = ConversationViewModel(provider=_FakeProvider())
        conv = Conversation.create(provider="test", model_id="test-model")
        vm.set_conversation(conv)
        window.conversation_view.set_viewmodel(vm)

        # Pedal starts OFF (PedalboardViewModel default) — stamp will be render_markdown=False
        assert not window._pedalboard_vm._by_id["markdown"].enabled, (
            "precondition: markdown pedal must start disabled"
        )

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("hello")

        # Flush QTimer.singleShot(0, ...) from _render_all_messages so the scrollbar
        # callback fires while the widget is alive, not during the next test's teardown.
        qtbot.wait(50)

        # Pedal was OFF → message must be stamped render_markdown=False → plain text.
        # Today: _render_all_messages() renders unconditionally as markdown → asterisks
        # consumed → "**bold**" NOT in HTML → this assertion fails → xfail.
        html_after_gen = window.conversation_view._display.toHtml()
        assert "**bold**" in html_after_gen, (
            "pedal OFF at generation time → message must render as plain text; "
            "asterisks must be present in toHtml() output (FLAG-A: stamp location)"
        )

        # Toggle pedal ON — must NOT re-render the already-stamped message.
        # The frozen stamp (render_markdown=False) must hold.
        window._pedalboard_vm.toggle_module("markdown")
        html_after_toggle = window.conversation_view._display.toHtml()

        assert html_after_gen == html_after_toggle, (
            "toggling pedal after generation must not re-render already-displayed messages; "
            "per-message stamp is frozen at generation time (footswitch-seam guard)"
        )

    def test_pedal_on_at_generation_renders_markdown(self, qtbot):
        """Pedal ON at generation → message renders as markdown, asterisks consumed.

        Characterization: today's unconditional rendering already passes this; must
        stay green once the builder wires the stamp-and-render path through the writer.
        Not xfail — let it report honestly.
        """
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        vm = ConversationViewModel(provider=_FakeProvider())
        conv = Conversation.create(provider="test", model_id="test-model")
        vm.set_conversation(conv)
        window.conversation_view.set_viewmodel(vm)

        if not window._pedalboard_vm._by_id["markdown"].enabled:
            window._pedalboard_vm.toggle_module("markdown")
        assert window._pedalboard_vm._by_id["markdown"].enabled, (
            "precondition: markdown pedal must be on"
        )

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("hello")

        qtbot.wait(50)  # flush QTimer.singleShot(0, ...) before widget teardown

        html = window.conversation_view._display.toHtml()
        assert "**bold**" not in html, (
            "pedal ON at generation → markdown rendered → asterisks must be consumed"
        )

    @_xfail
    def test_pedal_off_at_generation_renders_plain(self, qtbot):
        """Pedal OFF at generation → message renders as plain text, asterisks preserved.

        xfail under the per-message-frozen marker: unconditional rendering ignores pedal
        state today (same root cause as test_pedal_stamps_at_generation_and_toggle_is_frozen).
        The gap is the missing pedal→render_markdown stamp, closed in the stamping cycle,
        not the writer.markdown relocation.
        """
        from signal_chain.models.conversation import Conversation
        from signal_chain.viewmodels.conversation import ConversationViewModel
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        vm = ConversationViewModel(provider=_FakeProvider())
        conv = Conversation.create(provider="test", model_id="test-model")
        vm.set_conversation(conv)
        window.conversation_view.set_viewmodel(vm)

        assert not window._pedalboard_vm._by_id["markdown"].enabled, (
            "precondition: markdown pedal must be off (PedalboardViewModel default)"
        )

        with qtbot.waitSignal(vm.generation_complete, timeout=5000):
            vm.send_message("hello")

        qtbot.wait(50)  # flush QTimer.singleShot(0, ...) before widget teardown

        html = window.conversation_view._display.toHtml()
        assert "**bold**" in html, (
            "pedal OFF at generation → plain text → asterisks must be preserved in toHtml()"
        )


# ---------------------------------------------------------------------------
# Regression guard — already-implemented behavior; must not regress
# ---------------------------------------------------------------------------

class TestRegressionGuard:

    def test_markdown_footswitch_flips_enabled_state(self):
        """toggle_module('markdown') must flip and restore the enabled flag.

        Already implemented in PedalboardViewModel. Guards against regression.
        """
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        initial = vm._by_id["markdown"].enabled
        vm.toggle_module("markdown")
        assert vm._by_id["markdown"].enabled is not initial, (
            "first toggle must flip enabled away from its initial state"
        )
        vm.toggle_module("markdown")
        assert vm._by_id["markdown"].enabled is initial, (
            "second toggle must restore enabled to its initial state"
        )


# ---------------------------------------------------------------------------
# Humble View — conversation_view must not render markdown itself
# ---------------------------------------------------------------------------


class TestHumbleViewDelegation:

    def test_conversation_view_delegates_rendering_to_writer(self):
        """conversation_view.py must not import the markdown library.

        Asserts the post-relocation invariant (ADR-001 Humble View / ADR-010):
        rendering belongs in writer.markdown; conversation_view must not import
        the markdown library directly. The relocation landed in #148/#151.

        Source read via importlib so the path is correct regardless of install layout.
        This test passes — it is a regression guard, not a red contract.
        """
        import importlib.util
        import re
        from pathlib import Path

        spec = importlib.util.find_spec("signal_chain.views.conversation_view")
        assert spec is not None and spec.origin is not None, (
            "signal_chain.views.conversation_view must be importable"
        )
        source = Path(spec.origin).read_text()

        # Matches any import form that brings in the markdown package as a top-level name:
        #   import markdown
        #   import markdown as md_lib
        has_markdown_import = bool(re.search(r"\bimport\s+markdown\b", source))

        assert not has_markdown_import, (
            "conversation_view must not import the markdown library; "
            "rendering belongs in writer.markdown (Humble View, ADR-001/ADR-010)"
        )
