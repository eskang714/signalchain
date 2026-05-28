from __future__ import annotations

import time
from collections.abc import Iterator

import keyring
from google import genai
from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.providers.base import GenerationConfig, Message, ModelInfo

_KEYRING_SERVICE = "signalchain"
_KEYRING_USER = "gemini"


class GeminiProvider(QObject):
    countdown_tick = pyqtSignal(int)

    MAX_RETRIES = 3

    def __init__(self, model_id: str = "gemini-2.5-flash") -> None:
        super().__init__()
        self._model_id = model_id

    def _stream_tokens(self, messages: list[dict]) -> Iterator[str]:
        try:
            api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            api_key = None
        client = genai.Client(api_key=api_key or "no-key")
        gemini_messages = [
            {
                "role": "model" if m["role"] == "assistant" else m["role"],
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        for chunk in client.models.generate_content_stream(
            model=self._model_id,
            contents=gemini_messages,
            config={"max_output_tokens": 4096},
        ):
            if chunk.text:
                yield chunk.text

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gemini-2.5-flash", name="Gemini 2.5 Flash"),
            ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash"),
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
        gemini_msgs = [{"role": m.role, "content": m.content} for m in messages]
        for attempt in range(self.MAX_RETRIES):
            try:
                yield from self._stream_tokens(gemini_msgs)
                return
            except Exception as exc:
                if type(exc).__name__ == "ResourceExhausted":
                    if attempt == self.MAX_RETRIES - 1:
                        raise
                    self._countdown_sleep(60)
                else:
                    raise

    def _countdown_sleep(self, seconds: int) -> None:
        time.sleep(seconds)
