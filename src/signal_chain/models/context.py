from __future__ import annotations

from collections.abc import Callable

from signal_chain.providers.base import Message


def _make_default_counter() -> Callable[[str], int]:
    """Lazy tiktoken loader; falls back to char/4 if tiktoken is not installed."""
    enc = None

    def count(text: str) -> int:
        nonlocal enc
        try:
            if enc is None:
                import tiktoken
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            return len(text) // 4

    return count


_default_counter = _make_default_counter()


class ContextWindowManager:
    PROVIDER_LIMITS: dict[str, int] = {
        "claude": 180_000,
        "ollama": 4_096,
    }

    def __init__(
        self,
        window_size: int = 20,
        token_limit: int = 4096,
        response_buffer: int = 1000,
        token_counter: Callable[[str], int] | None = None,
    ) -> None:
        self._window_size = window_size
        self._token_limit = token_limit
        self._response_buffer = response_buffer
        self._count = token_counter if token_counter is not None else _default_counter

    def prepare_messages(self, messages: list[Message]) -> list[Message]:
        # Step 1: take the last window_size messages
        window = list(messages[-self._window_size :])

        # Step 2: effective budget excludes the response reservation
        effective_budget = self._token_limit - self._response_buffer

        # Step 3: drop oldest until within budget; Step 4: always keep newest
        while len(window) > 1:
            if sum(self._count(m.content) for m in window) <= effective_budget:
                break
            window.pop(0)

        return window
