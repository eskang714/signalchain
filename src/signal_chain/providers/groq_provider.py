from __future__ import annotations

import time
from collections.abc import Iterator

import keyring
from groq import Groq
from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.providers.base import GenerationConfig, Message, ModelInfo

_KEYRING_SERVICE = "signalchain"
_KEYRING_USER = "groq"


class GroqProvider(QObject):
    countdown_tick = pyqtSignal(int)

    MAX_RETRIES = 3

    def __init__(self, model_id: str = "llama-3.3-70b-versatile") -> None:
        super().__init__()
        self._model_id = model_id

    def _stream_tokens(self, messages: list[dict]) -> Iterator[str]:
        try:
            api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            api_key = None
        client = Groq(api_key=api_key or "no-key")
        for chunk in client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            max_tokens=4096,
            stream=True,
        ):
            yield chunk.choices[0].delta.content or ""

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="llama-3.3-70b-versatile", name="Llama 3.3 70B Versatile"),
            ModelInfo(id="llama3-8b-8192", name="Llama 3 8B (8192 ctx)"),
            ModelInfo(id="gemma2-9b-it", name="Gemma 2 9B IT"),
        ]

    def load_model(self, model_id: str) -> None:
        self._model_id = model_id

    def validate_config(self) -> bool:
        try:
            key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            key = None
        return bool(key)

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> Iterator[str]:
        groq_msgs = [{"role": m.role, "content": m.content} for m in messages]
        for attempt in range(self.MAX_RETRIES):
            try:
                yield from self._stream_tokens(groq_msgs)
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
