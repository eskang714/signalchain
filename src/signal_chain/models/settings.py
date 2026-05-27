from __future__ import annotations

from pathlib import Path

import keyring
import yaml

_KEYRING_SERVICE = "signalchain"
_DEFAULT_WINDOW_SIZE = 20
_MIN_WINDOW_SIZE = 10
_MAX_WINDOW_SIZE = 50
_DEFAULT_OLLAMA_URL = "http://localhost:11434"


class SettingsManager:
    def __init__(
        self,
        config_path: Path,
        context_window_size: int = _DEFAULT_WINDOW_SIZE,
        ollama_url: str = _DEFAULT_OLLAMA_URL,
    ) -> None:
        self._config_path = config_path
        self._context_window_size = context_window_size
        self._ollama_url = ollama_url

    @classmethod
    def load(cls, config_path: Path) -> SettingsManager:
        context_window_size = _DEFAULT_WINDOW_SIZE
        ollama_url = _DEFAULT_OLLAMA_URL
        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text()) or {}
                context_window_size = int(
                    data.get("context_window_size", _DEFAULT_WINDOW_SIZE)
                )
                ollama_url = str(data.get("ollama_url", _DEFAULT_OLLAMA_URL))
            except Exception:
                pass
        return cls(
            config_path=config_path,
            context_window_size=context_window_size,
            ollama_url=ollama_url,
        )

    def set_api_key(self, provider: str, key: str) -> None:
        keyring.set_password(_KEYRING_SERVICE, provider, key)
        # Detect null backend: if get_password returns something other than the key
        # that was just stored, the backend silently discarded the credential.
        if keyring.get_password(_KEYRING_SERVICE, provider) != key:
            raise RuntimeError(
                f"Keyring null backend detected for '{provider}': credential was "
                "silently discarded. Check your keyring backend configuration."
            )

    def get_api_key(self, provider: str) -> str | None:
        return keyring.get_password(_KEYRING_SERVICE, provider)

    def set_context_window_size(self, n: int) -> None:
        if n < _MIN_WINDOW_SIZE or n > _MAX_WINDOW_SIZE:
            raise ValueError(
                f"context_window_size must be between {_MIN_WINDOW_SIZE} and "
                f"{_MAX_WINDOW_SIZE}, got {n}"
            )
        self._context_window_size = n

    def get_context_window_size(self) -> int:
        return self._context_window_size

    def set_ollama_url(self, url: str) -> None:
        self._ollama_url = url

    def get_ollama_url(self) -> str:
        return self._ollama_url

    def save(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "context_window_size": self._context_window_size,
            "ollama_url": self._ollama_url,
        }
        self._config_path.write_text(yaml.dump(data, default_flow_style=False))
