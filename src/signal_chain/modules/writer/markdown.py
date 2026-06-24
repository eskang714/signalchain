from __future__ import annotations

import markdown as _md_lib


def handle(content: str, tag: str) -> str:
    """Render markdown source to HTML. Handler signature: (content, tag) -> str."""
    try:
        return _md_lib.markdown(
            content,
            extensions=["fenced_code", "tables", "codehilite", "nl2br", "sane_lists"],
        )
    except Exception:
        escaped = (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f"<pre>{escaped}</pre>"
