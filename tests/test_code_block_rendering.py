"""
Qt layout tests for code-block row pitch and trailing-block exit — ticket #149.

Pins two observable Qt layout properties that the #142 fix must satisfy:

  1. Row pitch flush — consecutive rows inside a code block are separated by at
     most the pre font's natural height (QFontMetricsF.height()) + a small epsilon.
     Current: line-height: 1.25 on pre/pre code inflates pitch to ~17.5px vs
     ~13.95px natural height — a ~3.5px dead band stacked between every row.

  2. Clean block exit — a message ending in a code block leaves no trailing empty
     paragraph in the QTextDocument.
     Current: <pre><code>…</code></pre><hr/> causes Qt to synthesize a phantom
     empty block (observed: bg alpha=255, h=16px, text='') after the last code line.

Measurement approach:
  Build ConversationView under qtbot (show() required — layout is degenerate without
  it), call show_conversation, then walk QTextDocument blocks via documentLayout().
  blockBoundingRect() to obtain (y, height) for each block.

Code-block identification:
  Blocks with monospace font families ('Menlo', 'Courier New', 'mono') in their
  first fragment's charFormat are code blocks. Blank lines inside a <pre> element
  have no fragments — identified by range (from first to last mono-font block).
  See _has_mono_font / _code_blocks helpers below.

  Phantom blocks from <hr/> have no fragments and a different background (alpha=255
  vs alpha≈30 for pre blocks), so _has_mono_font returns False for them — they fall
  outside the code range and are not counted as code.

Font sourcing (FLAG-font-source):
  QFontMetricsF height is sourced from the first non-empty code block's first
  fragment via block.begin().fragment().charFormat().font(). This matched the
  actual rendered block height in a verified probe (13.95px for Menlo 12px CSS
  font). If this probe fails on a different platform (font resolution differs),
  fall back to constructing QFont('Menlo', 12) directly.

Epsilon (FLAG-epsilon):
  1.5px — verified to separate the broken pitch (17.50px) from the fixed pitch
  (14.00px) with a clear margin on each side. Small enough to reject line-height
  values above ~1.1; large enough to absorb sub-pixel rounding (observed 0.05px
  rounding between fixed pitch and font height in verified probe).

FLAGS for the builder (do NOT decide by implementing):
  FLAG-font-source  — font from charFormat vs constructed from CSS constants
  FLAG-epsilon      — 1.5px epsilon value; flag if a different tolerance is needed
  FLAG-fix-mech     — builder owns the fix (line-height value, separator style);
                      tests assert layout properties only, not implementation details
"""

import pytest
from PyQt6.QtGui import QFontMetricsF

_xfail_code_spacing = pytest.mark.xfail(
    strict=True,
    reason="code-block row pitch and trailing empty paragraph fix (#149) not yet implemented",
)


# ---------------------------------------------------------------------------
# Document-block helpers (no imports of unimplemented code)
# ---------------------------------------------------------------------------


def _walk_blocks(view):
    """Walk all QTextDocument blocks; return list of (y, height, text, block) tuples."""
    doc = view._display.document()
    lay = doc.documentLayout()
    result = []
    b = doc.begin()
    while b.isValid():
        r = lay.blockBoundingRect(b)
        result.append((r.y(), r.height(), b.text(), b))
        b = b.next()
    return result


def _has_mono_font(block):
    """Return True if the block's first fragment uses a monospace font family."""
    it = block.begin()
    if it.atEnd():
        return False  # no fragments (blank line inside <pre>) — use range, not this
    font = it.fragment().charFormat().font()
    families = font.families() if hasattr(font, "families") else [font.family()]
    return any(
        any(m in f.lower() for m in ("menlo", "courier", "mono"))
        for f in families
    )


def _code_blocks(all_blocks):
    """Return the contiguous run of code blocks in document order.

    Finds the first and last block with a monospace font and returns the entire
    range, including blank lines inside the <pre> element (which have no fragments
    and are identified by their position between the bounding mono-font blocks).
    """
    first = last = None
    for i, (y, h, text, block) in enumerate(all_blocks):
        if _has_mono_font(block):
            if first is None:
                first = i
            last = i
    if first is None:
        return []
    return all_blocks[first : last + 1]


def _code_font(code_blocks):
    """Return the QFont from the first non-empty code block's first fragment.

    FLAG-font-source: sourced from charFormat().font() on the block's first fragment.
    Verified to match the actual rendered metrics (13.95px for Menlo 12px CSS).
    If unavailable, falls back to QFont('Menlo', 12) (point size).
    """
    from PyQt6.QtGui import QFont  # noqa: PLC0415

    for _, _, _, block in code_blocks:
        it = block.begin()
        if not it.atEnd():
            return it.fragment().charFormat().font()
    return QFont("Menlo", 12)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCodeBlockLayout:
    """Qt QTextDocument layout assertions for code-block rendering — ticket #149."""

    @_xfail_code_spacing
    def test_code_block_row_pitch_is_flush(self, qtbot):
        """Every row-to-row pitch inside a code block must be ≤ font height + epsilon.

        Uses a 4-line code block (PEP 8 layout, includes one blank line) so that:
          (a) pitch can be measured across at least 3 consecutive row pairs, and
          (b) a fix that deletes blank lines fails the row-count assertion.

        Current (broken):
          line-height: 1.25 on pre/pre code → pitch ≈ 17.50px for Menlo 12px.
          font_height ≈ 13.95px → threshold = 15.45px → 17.50 > 15.45 → RED.

        Fixed:
          line-height: 1.0 → pitch ≈ 14.00px ≤ 15.45px → GREEN.

        FLAG-epsilon: epsilon = 1.5px (see module docstring).
        FLAG-font-source: font sourced from first code block's charFormat (see _code_font).
        FLAG-fix-mech: builder owns the line-height value; test asserts property only.

        Requires view.show() — blockBoundingRect() returns zero-height blocks without it.
        qtbot.wait(50) flushes QTimer.singleShot(0, ...) from _render_all_messages to
        prevent cross-test teardown RuntimeError on the scrollbar callback.
        """
        from signal_chain.views.conversation_view import ConversationView  # noqa: PLC0415

        # PEP 8 layout: two non-empty lines, a blank line, a third non-empty line.
        MSG = "```python\ndef foo():\n    x = 1\n\n    y = 2\n```"
        SOURCE_LINE_COUNT = 4  # "def foo():", "    x = 1", "", "    y = 2"

        view = ConversationView()
        view.resize(800, 600)
        qtbot.addWidget(view)
        view.show()
        view.show_conversation([("assistant", MSG)])
        qtbot.wait(50)

        all_blocks = _walk_blocks(view)
        code = _code_blocks(all_blocks)

        assert len(code) == SOURCE_LINE_COUNT, (
            f"rendered row count {len(code)} must equal source line count {SOURCE_LINE_COUNT}; "
            "a fix that deletes blank lines from the code block must not pass this test"
        )

        font = _code_font(code)
        font_height = QFontMetricsF(font).height()
        EPSILON = 1.5  # px — see FLAG-epsilon in module docstring

        for i in range(len(code) - 1):
            y_curr = code[i][0]
            y_next = code[i + 1][0]
            pitch = y_next - y_curr
            assert pitch <= font_height + EPSILON, (
                f"dead band detected at row {i}→{i + 1}: "
                f"pitch {pitch:.2f}px > font height {font_height:.2f}px + epsilon {EPSILON}px; "
                "line-height on pre/pre code must not exceed 1.0 "
                "(current: line-height: 1.25 inflates pitch by ~3.5px per row)"
            )

    @_xfail_code_spacing
    def test_code_block_leaves_no_trailing_empty_paragraph(self, qtbot):
        """A message ending in a code block must leave no trailing empty paragraph.

        After the last code line, the document must contain no empty blocks.
        Current (broken): <pre><code>…</code></pre><hr/> causes Qt to synthesize
        a phantom empty paragraph block (observed: y=61.5, h=16.0, text='') after
        the last code line. trailing_count = 1 → assertion fails → RED.

        Fixed (any separator that does not create a phantom): trailing_count = 0 → GREEN.

        FLAG-fix-mech: builder may use a <div class="msg"> with border-bottom,
        margin-bottom, or any other approach that produces zero trailing empty blocks.
        Test asserts only the observable property (trailing_count == 0), not the mechanism.

        Requires view.show() and qtbot.wait(50) — see test_code_block_row_pitch_is_flush.
        """
        from signal_chain.views.conversation_view import ConversationView  # noqa: PLC0415

        MSG = "```python\nsome_code()\n```"

        view = ConversationView()
        view.resize(800, 600)
        qtbot.addWidget(view)
        view.show()
        view.show_conversation([("assistant", MSG)])
        qtbot.wait(50)

        all_blocks = _walk_blocks(view)
        texts = [text for _, _, text, _ in all_blocks]

        try:
            last_nonempty_idx = max(i for i, t in enumerate(texts) if t.strip())
        except ValueError:
            pytest.fail("no non-empty block found in document after show_conversation")

        trailing_count = len(texts) - last_nonempty_idx - 1
        assert trailing_count == 0, (
            f"phantom empty paragraph detected: {trailing_count} empty block(s) after "
            f"the last code line ('{texts[last_nonempty_idx]}'). "
            "Current cause: <pre><code>…</code></pre><hr/> causes Qt to synthesize "
            "a phantom empty block. Fix: replace <hr/> with a non-phantom separator."
        )
