from __future__ import annotations

import time
from collections.abc import Iterator

from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.providers.base import GenerationConfig, Message, ModelInfo


class ClaudeProvider(QObject):
    countdown_tick = pyqtSignal(int)

    MAX_RETRIES = 3

    def __init__(self) -> None:
        super().__init__()
        self._client: object | None = None

    def _get_client(self) -> object:
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def list_models(self) -> list[ModelInfo]:
        return []

    def load_model(self, model_id: str) -> None:
        pass

    def validate_config(self) -> bool:
        return True

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> Iterator[str]:
        client = self._get_client()
        anthropic_msgs = [{"role": m.role, "content": m.content} for m in messages]

        for attempt in range(self.MAX_RETRIES):
            try:
                for chunk in client.messages.stream(  # type: ignore[union-attr]
                    model="claude-opus-4-7",
                    max_tokens=config.max_tokens,
                    messages=anthropic_msgs,
                ):
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
                        text = chunk.delta.text
                        if text:
                            yield text
                return
            except Exception as exc:
                if type(exc).__name__ == "RateLimitError":
                    if attempt == self.MAX_RETRIES - 1:
                        raise
                    seconds = self._get_retry_after(exc)
                    self._countdown_sleep(seconds)
                else:
                    raise

    def _get_retry_after(self, exc: Exception) -> int:
        try:
            return int(exc.args[0].response.headers.get("retry-after", 0))
        except Exception:
            return 0

    def _countdown_sleep(self, seconds: int) -> None:
        time.sleep(seconds)
