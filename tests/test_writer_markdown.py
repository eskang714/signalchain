"""
Tests for writer.markdown handler and segmenter composition — ticket #146.

Pins the contract for:
  1. writer.markdown in isolation — renders markdown source to HTML.
  2. Segmenter + prose routing — prose rendered as markdown when markdown_on=True.
  3. Segmenter + md/markdown fence — fence contents rendered via writer.markdown.
  4. Code-fence clean exit (#142 fix) — no trailing empty paragraph alongside markdown.
  5. Isolation — code-fence content NEVER reaches the markdown library.
  6. Pedal gate — markdown_on=False keeps prose plain and code monospace.

Entry point asserted (FLAG-handler-name: see tester_log.md):
  signal_chain.modules.writer.markdown.handle(content: str, tag: str) -> str

  Registered with core as: register("md", handle)
  Also registered for prose when markdown_on=True (FLAG-prose-routing: see tester_log.md).

XPASS guard: every test imports writer.markdown inside the body. Since the module
does not exist yet, ImportError is the red trigger. Tests that assert conditions
already true in core.py (e.g. clean <pre><code> output) include a prose-routing
assertion as a second anchor so they cannot XPASS on a partial implementation.

Deferred (ADR-010 Q2):
  Nested same-length fences — marked @skip; see TestSegmenterComposition below.

All tests are xfail(strict=True) except the nested-fence skip.
"""

import pytest

# ---------------------------------------------------------------------------
# writer.markdown in isolation
# ---------------------------------------------------------------------------


class TestWriterMarkdown:
    """writer.markdown.handle renders markdown source to HTML — no segmenter."""

    def test_renders_heading_bold_and_list(self):
        """handle() must convert markdown headings, bold, and list items to HTML.

        Observable behavior:
          - A # heading produces an <h1> element.
          - **bold** text produces a <strong> element.
          - A - list item produces an <li> element.

        xfail trigger: ImportError — signal_chain.modules.writer.markdown does not exist.
        """
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        result = handle("# Heading\n\n**bold** text\n\n- list item", "md")

        assert "<h1>" in result, (
            "# Heading must produce an <h1> element (markdown library renders)"
        )
        assert "<strong>" in result, (
            "**bold** must produce a <strong> element"
        )
        assert "<li>" in result, (
            "- list item must produce an <li> element"
        )


# ---------------------------------------------------------------------------
# Segmenter composition — prose, md fence, code exit, isolation, gate
# ---------------------------------------------------------------------------


class TestSegmenterComposition:
    """render_message + writer.markdown wired — segmenter routing contracts."""

    def test_prose_rendered_as_markdown_when_markdown_on(self):
        """Prose text is rendered as markdown when markdown_on=True.

        Observable behavior:
          - A markdown heading in prose produces <h1> in the output.
          - **bold** in prose produces <strong>.

        FLAG-prose-routing: the mechanism that routes prose through writer.markdown
        (special registration key, default handler, or direct call in core) is the
        builder's design choice. This test asserts the observable result only.
        See tester_log.md FLAG-prose-routing.

        xfail trigger: ImportError — writer.markdown does not exist.
        """
        from signal_chain.modules.writer.core import clear_registry, register, render_message
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        register("md", handle)
        try:
            result = render_message("# Title\n\nsome **bold** text", markdown_on=True)
        finally:
            clear_registry()

        assert "<h1>" in result, (
            "prose heading must produce <h1> when markdown_on=True (requires prose routing)"
        )
        assert "<strong>" in result, (
            "prose **bold** must produce <strong> when markdown_on=True"
        )

    def test_md_fence_routed_through_markdown_handler_when_markdown_on(self):
        """A ```md fence is rendered via writer.markdown when markdown_on=True.

        Observable behavior:
          - **bold** inside the fence is consumed (not present literally).
          - <strong> appears in the output.

        xfail trigger: ImportError — writer.markdown does not exist.
        """
        from signal_chain.modules.writer.core import clear_registry, register, render_message
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        register("md", handle)
        try:
            text = "before\n```md\n**bold**\n```\nafter"
            result = render_message(text, markdown_on=True)
        finally:
            clear_registry()

        assert "**bold**" not in result, (
            "md fence **bold** must be consumed by markdown rendering"
        )
        assert "<strong>" in result, (
            "md fence **bold** must produce <strong> via writer.markdown"
        )

    def test_code_fence_clean_exit_no_trailing_empty_paragraph(self):
        """Code fences adjacent to markdown prose produce no trailing <p></p>.

        This is the #142 structural fix: when the markdown library renders prose
        above a code block, it must not emit a trailing empty paragraph after the
        <pre><code> block.

        Tests both python-tagged and untagged fences.

        XPASS guard: also asserts <h1> from prose (requires prose routing). Without
        that anchor, the code-clean assertion would pass today in core.py alone,
        causing an XPASS when writer.markdown first exists but prose is not yet wired.

        xfail trigger: ImportError — writer.markdown does not exist.
        """
        from signal_chain.modules.writer.core import clear_registry, register, render_message
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        register("md", handle)
        try:
            for text in (
                "# Heading\n\n```python\nsome_code()\n```",
                "# Heading\n\n```\nsome_code()\n```",
            ):
                result = render_message(text, markdown_on=True)

                assert "<h1>" in result, (
                    "prose heading must produce <h1> (prose-routing anchor; "
                    "prevents XPASS on partial implementation)"
                )
                assert "<pre><code>" in result, (
                    "code fence must render as <pre><code>"
                )
                assert "some_code()" in result, (
                    "code content must appear inside the <pre><code> block"
                )
                assert "<p></p>" not in result, (
                    "no trailing empty paragraph must follow the code block"
                )
        finally:
            clear_registry()

    def test_code_fence_content_never_routed_to_markdown_handler(self):
        """Code-fence content must NEVER be passed to the markdown handler.

        A spy is registered for "md" fences. The rendered text contains both an
        md fence and a python fence. The spy must be called for the md fence
        content but NOT for the python fence content.

        Observable behavior:
          - Spy call log contains md fence content.
          - Spy call log does NOT contain python fence content.
          - Code never enters the markdown library (ADR-010 Decision 2).

        xfail trigger: ImportError — writer.markdown does not exist.
        """
        from signal_chain.modules.writer.core import clear_registry, register, render_message
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        spy_calls: list[str] = []

        def spy(content: str, tag: str) -> str:
            spy_calls.append(content)
            return handle(content, tag)

        register("md", spy)
        try:
            text = (
                "some prose\n"
                "```md\n**markdown content**\n```\n"
                "```python\nsome_code()\n```"
            )
            render_message(text, markdown_on=True)
        finally:
            clear_registry()

        assert any("**markdown content**" in c for c in spy_calls), (
            "spy must be called with md fence content"
        )
        assert not any("some_code()" in c for c in spy_calls), (
            "python fence content must NEVER be passed to the markdown handler; "
            "code must not enter the markdown library (ADR-010 Decision 2)"
        )

    def test_pedal_gate_markdown_off_leaves_prose_plain_and_code_monospace(self):
        """markdown_on=False: prose stays plain (raw markdown syntax visible),
        code fence renders as <pre><code> (monospace, unchanged behavior).

        Observable behavior:
          - <h1> is NOT in the output (heading not rendered).
          - The raw # Heading text appears literally in the output.
          - <pre><code> is in the output (code fence rendered as monospace).

        xfail trigger: ImportError — writer.markdown does not exist.
        """
        from signal_chain.modules.writer.core import clear_registry, register, render_message
        from signal_chain.modules.writer.markdown import handle  # noqa: PLC0415

        register("md", handle)
        try:
            text = "# Heading\n\n```python\nsome_code()\n```"
            result = render_message(text, markdown_on=False)
        finally:
            clear_registry()

        assert "<h1>" not in result, (
            "prose heading must NOT be rendered as <h1> when markdown_on=False"
        )
        assert "# Heading" in result, (
            "raw markdown heading syntax must appear literally when markdown_on=False"
        )
        assert "<pre><code>" in result, (
            "code fence must still render as <pre><code> when markdown_on=False"
        )
        assert "some_code()" in result, (
            "code content must appear in the monospace block"
        )

    @pytest.mark.skip(
        reason=(
            "Nested same-length fences deferred — ADR-010 Open Questions Q2 (decision B). "
            "A ```markdown block wrapping a ```python block requires nesting-aware extraction; "
            "out of scope for writer.markdown Cycle 1."
        )
    )
    def test_nested_same_length_fences_unwrap_inner_code_as_monospace(self):
        pass
