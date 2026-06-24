from __future__ import annotations

from typing import Callable

_registry: dict[str, Callable[[str, str], str]] = {}
_MD_TAGS: frozenset[str] = frozenset({"md", "markdown"})


def register(tag: str, handler: Callable[[str, str], str]) -> None:
    """Register a handler for a fence tag.

    handler signature: (content: str, tag: str) -> str
    """
    _registry[tag] = handler


def clear_registry() -> None:
    """Remove all registered handlers. Use in test teardown for isolation."""
    _registry.clear()


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_fence(tag: str, content: str, *, markdown_on: bool) -> str:
    fallback = f"<pre><code>{_html_escape(content)}</code></pre>"
    if tag in _MD_TAGS:
        if markdown_on and tag in _registry:
            return _registry[tag](content, tag)
        return fallback
    if tag and tag in _registry:
        return _registry[tag](content, tag)
    return fallback


def _get_prose_md_handler() -> tuple[Callable[[str, str], str], str] | None:
    for tag in ("md", "markdown"):
        if tag in _registry:
            return _registry[tag], tag
    return None


def _render_prose(text: str) -> str:
    parts: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j != -1:
                parts.append(f"<code>{_html_escape(text[i + 1 : j])}</code>")
                i = j + 1
            else:
                parts.append("`")
                i += 1
        else:
            j = text.find("`", i)
            if j != -1:
                parts.append(text[i:j])
                i = j
            else:
                parts.append(text[i:])
                i = len(text)
    return "".join(parts)


def render_message(text: str, *, markdown_on: bool = False) -> str:
    """Render text with fence dispatch and inline monospace.

    Dispatch rules (ADR-010 Decision 4):
      - Untagged fence          → <pre><code> verbatim, never dispatched
      - Tagged fence, no handler → <pre><code> verbatim fallback
      - Tagged fence, handler   → handler(content, tag) output emitted
      - md/markdown tag gated by markdown_on: True→dispatch, False→verbatim
      - Inline backtick span    → <code> monospace, no dispatch
      - Unclosed trailing fence → partial content as <pre><code>, no exception
      - Prose                   → preserved, inline spans handled
    """
    lines = text.split("\n")
    parts: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            tag = line[3:].strip()
            fence_lines: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i] == "```":
                    i += 1
                    break
                fence_lines.append(lines[i])
                i += 1
            content = "\n".join(fence_lines)
            parts.append(_render_fence(tag, content, markdown_on=markdown_on))
        else:
            prose_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                prose_lines.append(lines[i])
                i += 1
            prose_text = "\n".join(prose_lines)
            if markdown_on:
                md_pair = _get_prose_md_handler()
            else:
                md_pair = None
            if md_pair is not None:
                handler_fn, handler_tag = md_pair
                parts.append(handler_fn(prose_text, handler_tag))
            else:
                parts.append(_render_prose(prose_text))

    return "".join(parts)
