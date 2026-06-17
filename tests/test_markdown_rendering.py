"""
Tests for pedal-driven markdown rendering — ticket #127.

Supersedes tests/test_per_message_markdown.py (deleted).  The per-message
approach was abandoned on feat/per-message-markdown and never merged.
The markdown pedal is now the single source of truth: rendering is global,
not per-message.

CONTRACT:
  - ConversationView exposes a setter (set_markdown_enabled) that controls
    whether assistant messages are rendered as Markdown or plain text.
  - Calling set_markdown_enabled re-renders the currently loaded
    _display_messages in the new mode WITHOUT requiring another
    show_conversation() call.
  - MainWindow wires _pedalboard_vm.module_state_changed to the view's setter
    at construction time so that footswitch presses drive live re-rendering.
  - Conversation JSON files containing a render_markdown key (written by the
    abandoned per-message branch) load without error — the unknown key is
    silently ignored.

FLAGS (builder must confirm or amend):

  FLAG-A  View↔pedal wiring.
          Tests assume ConversationView.set_markdown_enabled(enabled: bool) —
          a setter that re-renders _display_messages in the requested mode.
          MainWindow must connect:
            _pedalboard_vm.module_state_changed → λ mid, en:
              conversation_view.set_markdown_enabled(en) if mid == "markdown"
          Alternative: the view holds a PedalboardViewModel reference and
          reads _by_id["markdown"].enabled directly in _render_all_messages.
          xfail trigger: AttributeError today — set_markdown_enabled does not
          exist on ConversationView.

  FLAG-B  _from_dict unknown-key tolerance.
          Option 1 (preferred): strip unknown keys before ConversationMessage(**m)
            known = {f.name for f in dataclasses.fields(ConversationMessage)}
            messages = [ConversationMessage(**{k: v for k, v in m.items() if k in known})
                        for m in data.get("messages", [])]
          Option 2: explicit version migration in a conversion layer.
          xfail trigger: TypeError today — ConversationMessage(**m) rejects
          render_markdown as an unexpected kwarg.

HTML assertions use asterisk presence/absence rather than tag names.
Qt's toHtml() normalises <strong> to font-weight spans, but it never
re-inserts the source asterisks — so "**bold**" absent ↔ markdown rendered.
"""
import json

import pytest

_xfail = pytest.mark.xfail(
    strict=True,
    reason="pedal-driven markdown rendering not yet implemented",
)


# ---------------------------------------------------------------------------
# View layer — set_markdown_enabled controls rendering direction
# ---------------------------------------------------------------------------

class TestViewMarkdownRendering:

    @_xfail
    def test_markdown_enabled_renders_markdown(self, qtbot):
        """set_markdown_enabled(True) must render assistant text as Markdown —
        asterisks consumed, not shown literally in the HTML output."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        view.show_conversation([("assistant", "**bold**")])

        # AttributeError today — ConversationView has no set_markdown_enabled → xfail
        view.set_markdown_enabled(True)

        html = view._display.toHtml()
        assert "**bold**" not in html, (
            "set_markdown_enabled(True): **bold** must be rendered as HTML bold; "
            "literal asterisks must not appear in toHtml() output (FLAG-A)"
        )

    @_xfail
    def test_markdown_disabled_renders_plain(self, qtbot):
        """set_markdown_enabled(False) must render assistant text as escaped plain
        text — asterisks preserved (* is not HTML-special)."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        view.show_conversation([("assistant", "**bold**")])

        # AttributeError today → xfail
        view.set_markdown_enabled(False)

        html = view._display.toHtml()
        assert "**bold**" in html, (
            "set_markdown_enabled(False): **bold** must appear as literal text; "
            "* is not HTML-special and must survive setHtml/toHtml (FLAG-A)"
        )

    @_xfail
    def test_pedal_toggle_rerenders_without_second_show_conversation(self, qtbot):
        """Calling set_markdown_enabled after show_conversation must re-render the
        currently loaded messages WITHOUT a second show_conversation() call."""
        from signal_chain.views.conversation_view import ConversationView

        view = ConversationView()
        qtbot.addWidget(view)
        view.show_conversation([("assistant", "**bold**")])

        # Establish a plain-text baseline.
        # AttributeError today → xfail
        view.set_markdown_enabled(False)
        html_plain = view._display.toHtml()
        assert "**bold**" in html_plain, "sanity: plain mode must preserve asterisks"

        # Flip to markdown — must re-render the already-loaded conversation in place.
        view.set_markdown_enabled(True)
        html_markdown = view._display.toHtml()

        assert "**bold**" not in html_markdown, (
            "set_markdown_enabled(True) must re-render existing _display_messages; "
            "asterisks must be consumed without a second show_conversation() call"
        )


# ---------------------------------------------------------------------------
# Integration — MainWindow pedalboard drives the conversation view
# ---------------------------------------------------------------------------

class TestMainWindowIntegration:

    @_xfail
    def test_mainwindow_pedalboard_toggle_rerenders_conversation_view(self, qtbot):
        """Toggling the markdown pedal via the real MainWindow pedalboard must
        change the rendered HTML — proves conversation_view is bound to the
        shared _pedalboard_vm that the physical footswitch drives.

        xfail today: no signal wiring exists between _pedalboard_vm and
        conversation_view; toggling the module has no effect on the rendered HTML.
        """
        from signal_chain.views.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.conversation_view.show_conversation([("assistant", "**bold**")])

        html_before = window.conversation_view._display.toHtml()

        # Toggle the markdown pedal via the shared pedalboard VM.
        window._pedalboard_vm.toggle_module("markdown")

        html_after = window.conversation_view._display.toHtml()

        # HTML must change — proves the view re-rendered in response to the toggle.
        # Fails today because there is no wiring between _pedalboard_vm and the view.
        assert html_before != html_after, (
            "toggling _pedalboard_vm.toggle_module('markdown') must trigger a "
            "live re-render of conversation_view — proves the view is bound to "
            "the same pedalboard VM the footswitch drives (FLAG-A)"
        )


# ---------------------------------------------------------------------------
# Model layer — backward-compat with abandoned per-message JSON
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    @_xfail
    def test_json_with_render_markdown_field_loads_without_error(self, tmp_path):
        """A conversation JSON file containing render_markdown in a message must
        load without raising TypeError — the unknown key must be silently ignored.

        Context: the per-message branch wrote render_markdown into saved JSON.
        That branch was abandoned, but users may have such files on disk.
        FLAG-B: builder chooses between key-filtering and version migration.
        """
        from signal_chain.models.conversation import ConversationLoader

        data = {
            "version": "1.0",
            "schema": "conversation.v1",
            "conversation_id": "conv_compat_127",
            "created": "2026-01-01T00:00:00+00:00",
            "model": {"provider": "test", "model_id": "test"},
            "messages": [
                {
                    "id": "msg_0000",
                    "role": "assistant",
                    "content": "hello from the past",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "render_markdown": True,  # unknown key — from abandoned branch
                }
            ],
            "metadata": {"title": "", "tags": [], "module_usage": {}},
        }
        path = tmp_path / "conv_compat_127.json"
        path.write_text(json.dumps(data))

        # TypeError today: ConversationMessage(**m) rejects unknown kwarg → xfail
        conv = ConversationLoader.load(path)

        assert len(conv.messages) == 1, "all messages must load, none dropped"
        assert conv.messages[0].content == "hello from the past"


# ---------------------------------------------------------------------------
# Regression guard — already-implemented behavior; must not regress
# ---------------------------------------------------------------------------

class TestRegressionGuard:

    def test_markdown_footswitch_flips_enabled_state(self):
        """toggle_module('markdown') must flip and restore the enabled flag.

        Already implemented in PedalboardViewModel. This test guards against
        regression — it passes today and must continue to pass after #127.
        """
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        initial = vm._by_id["markdown"].enabled  # do not assert specific default
        vm.toggle_module("markdown")
        assert vm._by_id["markdown"].enabled is not initial, (
            "first toggle must flip enabled away from its initial state"
        )
        vm.toggle_module("markdown")
        assert vm._by_id["markdown"].enabled is initial, (
            "second toggle must restore enabled to its initial state"
        )
