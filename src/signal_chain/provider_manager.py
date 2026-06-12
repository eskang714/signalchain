from __future__ import annotations

from signal_chain.models.settings import SettingsManager
from signal_chain.providers.claude import ClaudeProvider
from signal_chain.providers.gemini_provider import GeminiProvider
from signal_chain.providers.groq_provider import GroqProvider
from signal_chain.providers.ollama import OllamaProvider
from signal_chain.providers.openrouter import OpenRouterProvider


class ProviderManager:
    """Encapsulates provider discovery, selection, and active state.

    Application creates one instance after SettingsManager is loaded and
    delegates all provider lifecycle calls here, keeping Application as a
    thin coordinator.
    """

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings
        self._available: list[tuple[str, str, object]] = []
        self._active_provider: object | None = None
        self._active_name: str = ""
        self._active_model_id: str = ""

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> list[tuple[str, str, object]]:
        return self._available

    @property
    def active_provider(self) -> object | None:
        return self._active_provider

    @property
    def active_name(self) -> str:
        return self._active_name

    @property
    def active_model_id(self) -> str:
        return self._active_model_id

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> None:
        """Instantiate all providers; keep those that pass validate_config()."""
        result: list[tuple[str, str, object]] = []
        or_p = OpenRouterProvider()
        if or_p.validate_config():
            result.append(("openrouter", "OpenRouter", or_p))
        claude_p = ClaudeProvider()
        if claude_p.validate_config():
            result.append(("claude", "Claude", claude_p))
        groq_p = GroqProvider()
        if groq_p.validate_config():
            result.append(("groq", "Groq", groq_p))
        gemini_p = GeminiProvider()
        if gemini_p.validate_config():
            result.append(("gemini", "Gemini", gemini_p))
        ollama_p = OllamaProvider(base_url=self._settings.get_ollama_url())
        if ollama_p.validate_config():
            result.append(("ollama", "Ollama", ollama_p))
        self._available = result

    # ------------------------------------------------------------------
    # Initial selection
    # ------------------------------------------------------------------

    def select_initial(self) -> tuple[object | None, str]:
        """Pick provider and model from saved prefs or first available.

        Updates internal active state. Returns (provider, model_id).
        """
        if not self._available:
            return None, ""
        saved_name = self._settings.get_active_provider()
        provider = next(
            (p for n, _, p in self._available if n == saved_name),
            self._available[0][2],
        )
        self._active_name = next(
            (n for n, _, p in self._available if p is provider), ""
        )
        self._active_provider = provider
        model_id = ""
        try:
            models = provider.list_models()  # type: ignore[union-attr]
            if models:
                saved_model = self._settings.get_active_model()
                model_id = (
                    saved_model
                    if any(m.id == saved_model for m in models)
                    else models[0].id
                )
                provider.load_model(model_id)  # type: ignore[union-attr]
        except Exception:
            pass
        self._active_model_id = model_id
        return provider, model_id

    # ------------------------------------------------------------------
    # Provider change
    # ------------------------------------------------------------------

    def select_provider(self, name: str) -> tuple[str, list[tuple[str, str]]]:
        """Select a named provider, load its best model, persist to settings.

        Returns (model_id, [(id, display_name), ...]) for the caller to
        update UI dropdowns with.
        """
        provider = next((p for n, _, p in self._available if n == name), None)
        if provider is None:
            return "", []
        self._active_provider = provider
        self._active_name = name
        model_id = ""
        model_items: list[tuple[str, str]] = []
        try:
            models = provider.list_models()  # type: ignore[union-attr]
            if models:
                saved = self._settings.get_active_model()
                model_id = (
                    saved if any(m.id == saved for m in models) else models[0].id
                )
                provider.load_model(model_id)  # type: ignore[union-attr]
                model_items = [(m.id, m.name) for m in models]
        except Exception:
            pass
        self._active_model_id = model_id
        try:
            self._settings.set_active_provider(name)
            self._settings.set_active_model(model_id)
            self._settings.save()
        except Exception:
            pass
        return model_id, model_items

    # ------------------------------------------------------------------
    # Model change
    # ------------------------------------------------------------------

    def select_model(self, model_id: str) -> None:
        """Load model_id on the active provider and persist to settings."""
        if self._active_provider is not None and model_id:
            try:
                self._active_provider.load_model(model_id)  # type: ignore[union-attr]
            except Exception:
                pass
        if model_id:
            self._active_model_id = model_id
        try:
            self._settings.set_active_model(model_id)
            self._settings.save()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Refresh (e.g. after settings dialog save)
    # ------------------------------------------------------------------

    def refresh(self) -> tuple[str, str]:
        """Re-discover providers and re-select based on current preferences.

        Returns (active_name, model_id) for the caller to repopulate UI.
        """
        self.discover()
        _, model_id = self.select_initial()
        return self._active_name, model_id
