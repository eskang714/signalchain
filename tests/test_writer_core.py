"""
Tests for writer core — ticket #138.

Pins the contract for fence/inline parsing, fence-tag dispatch with monospace
as the default and fallback, the markdown_on gate on md/markdown tags, and
unclosed/streaming handling.

Entry points (in signal_chain.modules.writer.core):
  render_message(text: str, *, markdown_on: bool = False) -> str
  register(tag: str, handler: Callable[[str, str], str]) -> None

  handler signature: (content: str, tag: str) -> str

Dispatch rules (ADR-010 Decision 4):
  - Untagged fence          → monospace verbatim, never dispatched
  - Tagged fence, no handler → monospace verbatim fallback
  - Tagged fence, handler registered → handler called, its output emitted
  - md/markdown tag gated by markdown_on:
      True  → handler dispatched
      False → monospace verbatim (handler NOT called)
  - Inline backtick span    → monospace, dispatch skipped
  - Unclosed trailing fence → partial content as monospace, no exception
  - Prose outside code regions → preserved unchanged

FLAG-A (deferred): same-length nested fence extraction is out of scope for
this ticket. See ADR-010 Open Questions ("Nested fences").

Note on handler registry isolation: register() likely writes to module-level
state. Tests use distinct tag names for neutral handlers and keep both sides
of the md-gate test in the same method. The builder must expose a teardown
or scoped-registry mechanism to prevent cross-test contamination in future
suites.

All tests are xfail(strict=True): signal_chain.modules.writer.core does
not exist; ImportError is the expected trigger until the builder's tock lands.
"""

# ---------------------------------------------------------------------------
# Fence dispatch — ADR-010 Decision 4
# ---------------------------------------------------------------------------


class TestFenceDispatch:
    """Fence parsing and tag-based dispatch rules."""

    def test_untagged_fence_renders_as_monospace_and_is_not_dispatched(self):
        """An untagged fence must produce monospace-formatted output and must
        never invoke any registered handler.

        Observable behavior:
          - Fence content appears verbatim in the output.
          - Raw backtick delimiters (```) do not appear literally.
          - Output contains code-block HTML (<pre> or <code>).
          - A registered handler is NOT called (no tag → no dispatch).
        """
        from signal_chain.modules.writer.core import register, render_message

        handler_calls = []

        def spy(content: str, tag: str) -> str:
            handler_calls.append((content, tag))
            return f"<spy>{content}</spy>"

        register("untagged_spy", spy)  # neutral tag; untagged fence carries no tag

        text = "before\n```\nsome untagged code\n```\nafter"
        result = render_message(text, markdown_on=False)

        assert "some untagged code" in result, (
            "untagged fence content must appear in output"
        )
        assert "```" not in result, (
            "raw backtick delimiters must be consumed by fence parsing"
        )
        assert any(t in result for t in ("<pre>", "<code>")), (
            "untagged fence must render as monospace (<pre> or <code>)"
        )
        assert not handler_calls, (
            "untagged fence must not invoke any registered handler"
        )

    def test_tagged_fence_with_no_registered_handler_falls_back_to_monospace(self):
        """A fence tagged with a language that has no registered handler must
        fall back to monospace verbatim output, not an error or rendered markdown.

        Observable behavior:
          - Content appears verbatim in output.
          - Output contains code-block HTML (<pre> or <code>).
          - No exception is raised.
        """
        from signal_chain.modules.writer.core import render_message

        # "python" has no registered handler in this test; fallback expected
        text = "```python\nprint('hello')\n```"
        result = render_message(text, markdown_on=True)

        assert "print('hello')" in result, (
            "tagged fence content must appear verbatim when no handler is registered"
        )
        assert "```" not in result, (
            "raw backtick delimiters must be consumed"
        )
        assert any(t in result for t in ("<pre>", "<code>")), (
            "tagged fence with no handler must fall back to monospace (<pre> or <code>)"
        )

    def test_tagged_fence_with_registered_handler_routes_to_handler(self):
        """A fence tagged with a neutral tag that has a registered handler must
        route the fence's inner content to that handler and emit its return value.

        Dispatch is markdown_on-agnostic for non-md tags: routing happens
        regardless of the markdown_on flag.
        """
        from signal_chain.modules.writer.core import register, render_message

        handler_calls = []

        def fake_handler(content: str, tag: str) -> str:
            handler_calls.append({"content": content, "tag": tag})
            return "<dispatch-output>rendered by handler</dispatch-output>"

        register("demo_dispatch", fake_handler)

        text = "```demo_dispatch\nhello world\n```"
        result = render_message(text, markdown_on=False)

        assert handler_calls, (
            "registered handler must be called for its tag"
        )
        assert "hello world" in handler_calls[0]["content"], (
            "handler must receive the inner fence content (without backtick delimiters)"
        )
        assert handler_calls[0]["tag"] == "demo_dispatch", (
            "handler must receive the fence tag string"
        )
        assert "<dispatch-output>rendered by handler</dispatch-output>" in result, (
            "handler's return value must appear in render_message output"
        )

    def test_md_tag_gated_by_markdown_on(self):
        """A fence tagged 'md' or 'markdown' is gated by the markdown_on argument.

        markdown_on=True  → registered handler is invoked; its output emitted.
        markdown_on=False → handler is NOT invoked; content rendered as monospace.

        ADR-010 Decision 4: "a fence whose language tag is markdown/md has its
        contents rendered as markdown" — gated on markdown_on.

        Note: both assertions are in the same test to avoid cross-test registry
        contamination from the 'md' handler registration.
        """
        from signal_chain.modules.writer.core import register, render_message

        md_calls = []

        def fake_md_handler(content: str, tag: str) -> str:
            md_calls.append(content)
            return "<md-handler-output>handled</md-handler-output>"

        register("md", fake_md_handler)
        text = "```md\n**bold**\n```"

        # markdown_on=True: handler must be called
        result_on = render_message(text, markdown_on=True)
        assert md_calls, (
            "md-tagged fence: markdown_on=True must route to the registered md handler"
        )
        assert "**bold**" in md_calls[0], (
            "md handler must receive the inner fence content"
        )
        assert "<md-handler-output>handled</md-handler-output>" in result_on, (
            "md handler's return value must appear in output when markdown_on=True"
        )

        # markdown_on=False: handler must NOT be called; content verbatim monospace
        md_calls.clear()
        result_off = render_message(text, markdown_on=False)
        assert not md_calls, (
            "md-tagged fence: markdown_on=False must NOT invoke the md handler"
        )
        assert "**bold**" in result_off, (
            "md-tagged fence with markdown_on=False must render verbatim (asterisks preserved)"
        )
        assert any(t in result_off for t in ("<pre>", "<code>")), (
            "md-tagged fence with markdown_on=False must fall back to monospace"
        )


# ---------------------------------------------------------------------------
# Inline code — monospace, dispatch skipped
# ---------------------------------------------------------------------------


class TestInlineCode:
    """Single-backtick inline spans are monospace; dispatch is never invoked."""

    def test_inline_backtick_span_renders_as_monospace_without_dispatch(self):
        """A single-backtick inline code span must produce monospace output and
        must NOT invoke any registered handler.

        Observable behavior:
          - Span content appears in the output.
          - Raw backtick delimiters do not appear literally.
          - Output contains inline code HTML (<code>).
          - No registered handler is called (inline spans are never dispatched).
        """
        from signal_chain.modules.writer.core import register, render_message

        spy_calls = []

        def inline_spy(content: str, tag: str) -> str:
            spy_calls.append(content)
            return f"<spy>{content}</spy>"

        register("inline_spy_tag", inline_spy)  # must never fire for inline spans

        text = "some `inline code` text"
        result = render_message(text, markdown_on=True)

        assert "inline code" in result, (
            "inline span content must appear in output"
        )
        assert "`" not in result, (
            "raw backtick delimiter must be consumed from inline spans"
        )
        assert "<code>" in result, (
            "inline backtick span must render as <code> (monospace)"
        )
        assert not spy_calls, (
            "inline backtick span must not invoke any registered handler"
        )


# ---------------------------------------------------------------------------
# Streaming resilience — unclosed fences
# ---------------------------------------------------------------------------


class TestStreamingResilience:
    """Unclosed/streaming fences: partial content as monospace, no exception."""

    def test_unclosed_fence_yields_partial_content_as_monospace_without_error(self):
        """An unclosed fence (mid-generation snapshot, no closing ```) must be
        handled gracefully: content rendered as monospace, no exception raised.

        Observable behavior:
          - Partial content inside the opened fence appears in the output.
          - Output contains code-block HTML (<pre> or <code>).
          - No exception is raised.
        """
        from signal_chain.modules.writer.core import render_message

        text = "```python\nprint('partial')\n"  # no closing ```

        result = render_message(text, markdown_on=False)  # must not raise

        assert "print('partial')" in result, (
            "partial content of an unclosed fence must appear in output"
        )
        assert any(t in result for t in ("<pre>", "<code>")), (
            "unclosed fence content must render as monospace (<pre> or <code>)"
        )


# ---------------------------------------------------------------------------
# Prose preservation
# ---------------------------------------------------------------------------


class TestProsePreservation:
    """Prose outside code regions passes through unchanged."""

    def test_prose_outside_code_regions_is_preserved(self):
        """Text before, between, and after fences must not be consumed or altered
        by fence parsing.

        Observable behavior:
          - Prose text appears in the output unchanged.
          - Fence content also appears.
          - Both prose regions are present simultaneously with the code output.
        """
        from signal_chain.modules.writer.core import render_message

        text = "before fence\n```\nsome code\n```\nafter fence"
        result = render_message(text, markdown_on=False)

        assert "before fence" in result, (
            "prose before a fence must be preserved in the output"
        )
        assert "after fence" in result, (
            "prose after a fence must be preserved in the output"
        )
        assert "some code" in result, (
            "fence content must also appear in the output"
        )


# ---------------------------------------------------------------------------
# Facade — writer/__init__.py re-exports the public API from writer.core
# ---------------------------------------------------------------------------


class TestFacade:
    """writer/__init__.py is a thin re-export facade (no logic).

    This test forces the builder to wire __init__.py. Without it, writer.core
    could ship in isolation and leave the package-level import path empty.
    """

    def test_package_re_exports_render_message_and_register(self):
        """from signal_chain.modules.writer import render_message, register must succeed.

        The architecture decision specifies writer/__init__.py as a thin facade
        re-exporting the public API from writer.core. This test fails until the
        builder creates both writer/core.py and wires the __init__.py re-export.
        """
        from signal_chain.modules.writer import register, render_message  # noqa: F401

        assert callable(render_message), "render_message must be callable via the facade"
        assert callable(register), "register must be callable via the facade"
