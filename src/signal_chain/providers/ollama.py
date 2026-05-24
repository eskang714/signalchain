from __future__ import annotations

from collections.abc import Iterator

import ollama

from signal_chain.providers.base import BaseProvider, GenerationConfig, Message, ModelInfo


class OllamaProvider(BaseProvider):
    def __init__(self) -> None:
        self._client = ollama.Client()
        self._model_id: str = ""

    def list_models(self) -> list[ModelInfo]:
        try:
            response = self._client.list()
        except Exception as exc:
            raise RuntimeError(
                f"Ollama is not running or not reachable: {exc}"
            ) from exc

        if hasattr(response, "models"):
            raw_models = response.models
        else:
            raw_models = response.get("models", [])

        result = []
        for m in raw_models:
            if isinstance(m, dict):
                name = m.get("name", "")
            else:
                name = getattr(m, "model", "") or getattr(m, "name", "")
            result.append(ModelInfo(id=name, name=name))
        return result

    def load_model(self, model_id: str) -> None:
        self._model_id = model_id

    def validate_config(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> Iterator[str]:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        for chunk in self._client.chat(
            model=self._model_id,
            messages=ollama_messages,
            stream=True,
        ):
            if isinstance(chunk, dict):
                content = chunk.get("message", {}).get("content", "")
            else:
                msg = getattr(chunk, "message", None)
                content = getattr(msg, "content", "") if msg is not None else ""
            if content:
                yield content
