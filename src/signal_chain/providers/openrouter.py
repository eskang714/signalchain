from __future__ import annotations

import time
from collections.abc import Iterator

import keyring
import openai
from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.providers.base import GenerationConfig, Message, ModelInfo

_KEYRING_SERVICE = "signalchain"
_KEYRING_USER = "openrouter"
_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(QObject):
    countdown_tick = pyqtSignal(int)

    MAX_RETRIES = 3

    def __init__(self, model_id: str = "openrouter/free") -> None:
        super().__init__()
        self._model_id = model_id

    def _stream_tokens(self, messages: list[dict]) -> Iterator[str]:
        try:
            api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            api_key = None
        client = openai.OpenAI(
            base_url=_BASE_URL,
            api_key=api_key or "no-key",
        )
        for chunk in client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            stream=True,
            max_tokens=4096,
        ):
            yield chunk.choices[0].delta.content or ""

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id="openrouter/free",
                name="Auto-router (free)",
            ),
            ModelInfo(
                id="meta-llama/llama-3.3-70b-instruct:free",
                name="Llama 3.3 70B Instruct (free)",
            ),
            ModelInfo(
                id="mistralai/mistral-7b-instruct:free",
                name="Mistral 7B Instruct (free)",
            ),
            ModelInfo(
                id="deepseek/deepseek-chat-v3-0324:free",
                name="DeepSeek Chat V3 (free)",
            ),
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
        openai_msgs = [{"role": m.role, "content": m.content} for m in messages]
        for attempt in range(self.MAX_RETRIES):
            try:
                yield from self._stream_tokens(openai_msgs)
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
