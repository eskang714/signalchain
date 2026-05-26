from __future__ import annotations

import time
from collections.abc import Iterator

import keyring
from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.providers.base import GenerationConfig, Message, ModelInfo

_KEYRING_SERVICE = "signalchain"
_KEYRING_USER = "claude"


class ClaudeProvider(QObject):
    countdown_tick = pyqtSignal(int)

    MAX_RETRIES = 3

    def __init__(self, model_id: str = "claude-sonnet-4-6") -> None:
        super().__init__()
        self._model_id = model_id

    def _stream_tokens(self, messages: list[dict]) -> Iterator[str]:
        import anthropic
        api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        client = anthropic.Anthropic(api_key=api_key)
        for chunk in client.messages.stream(
            model=self._model_id,
            messages=messages,
            max_tokens=4096,
        ):
            if isinstance(chunk, str):
                yield chunk
            elif hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
                if chunk.delta.text:
                    yield chunk.delta.text

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="claude-opus-4-7", name="Claude Opus 4.7"),
            ModelInfo(id="claude-sonnet-4-6", name="Claude Sonnet 4.6"),
            ModelInfo(id="claude-haiku-4-5", name="Claude Haiku 4.5"),
        ]

    def load_model(self, model_id: str) -> None:
        self._model_id = model_id

    def validate_config(self) -> bool:
        key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        return bool(key)

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> Iterator[str]:
        anthropic_msgs = [{"role": m.role, "content": m.content} for m in messages]
        for attempt in range(self.MAX_RETRIES):
            try:
                yield from self._stream_tokens(anthropic_msgs)
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
