"""
Acceptance tests – Providers
TC-20: Ollama Auto Discovery
TC-21: Ollama Not Running
TC-22: Local Model Addition via Wizard

Target classes (not yet implemented):
  signal_chain.providers.ollama.OllamaProvider
  signal_chain.providers.local_gguf.LocalGGUFProvider

FLAG TC-22 (design decision required):
  ModelInfo in base.py has only `id` and `name`.  TC-22 requires auto-detection
  of size, context_length, and quantization.  The builder must choose one of:
    A) Extend ModelInfo with optional fields (size_bytes, context_length, quantization)
    B) Define LocalModelInfo(ModelInfo) subclass in local_gguf.py with those fields
    C) Return a plain dataclass from add_model() that is NOT a ModelInfo subtype
  Tests below assume option A or B — they access .size_bytes, .context_length,
  .quantization on the returned object.  Awaiting builder decision.
"""
from unittest.mock import MagicMock, patch

import pytest

_xfail = pytest.mark.xfail(
    reason="Not yet implemented - TDD red phase",
    strict=True,
)

# Three models the mock_ollama fixture advertises (mirrors conftest.py values).
_KNOWN_MODELS = ["llama3:8b", "mistral:7b", "phi3:mini"]


# ---------------------------------------------------------------------------
# TC-20: Ollama Auto Discovery
# ---------------------------------------------------------------------------

class TestTC20OllamaAutoDiscovery:
    """list_models() returns every model from ollama.list(); no auth or manual config needed."""

    def test_all_ollama_models_appear_in_list(self, mock_ollama):
        from signal_chain.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        models = provider.list_models()

        assert len(models) == len(_KNOWN_MODELS), (
            f"list_models must return all {len(_KNOWN_MODELS)} models reported by "
            f"ollama.list(); got {len(models)}"
        )

    def test_model_ids_match_ollama_names(self, mock_ollama):
        from signal_chain.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        returned_ids = {m.id for m in provider.list_models()}

        for expected_id in _KNOWN_MODELS:
            assert expected_id in returned_ids, (
                f"Model '{expected_id}' reported by ollama.list() must appear in list_models()"
            )

    def test_list_models_returns_model_info_instances(self, mock_ollama):
        from signal_chain.providers.base import ModelInfo
        from signal_chain.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        models = provider.list_models()

        assert models, "list_models must return a non-empty list"
        assert all(isinstance(m, ModelInfo) for m in models), (
            "Every item returned by list_models must be a ModelInfo instance"
        )

    def test_discovery_requires_no_manual_configuration(self, mock_ollama):
        """Default constructor (no args) must work — Ollama needs no auth."""
        from signal_chain.providers.ollama import OllamaProvider

        # Must not raise; Ollama uses no API key or manual model registration.
        provider = OllamaProvider()
        models = provider.list_models()

        assert len(models) > 0, (
            "OllamaProvider() with no arguments must discover models automatically"
        )

    def test_validate_config_true_when_ollama_running(self, mock_ollama):
        from signal_chain.providers.ollama import OllamaProvider

        provider = OllamaProvider()

        assert provider.validate_config() is True, (
            "validate_config must return True when the Ollama service is reachable"
        )


# ---------------------------------------------------------------------------
# TC-21: Ollama Not Running
# ---------------------------------------------------------------------------

class TestTC21OllamaNotRunning:
    """When Ollama is unreachable: validate_config returns False, list_models raises
    a clear exception with an actionable message; no crash or silent failure."""

    def test_validate_config_returns_false_not_raises(self):
        from signal_chain.providers.ollama import OllamaProvider

        unreachable = MagicMock()
        unreachable.list.side_effect = ConnectionRefusedError("[Errno 111] Connection refused")

        with patch("ollama.Client", return_value=unreachable):
            provider = OllamaProvider()
            result = provider.validate_config()  # must return, not raise

        assert result is False, (
            "validate_config must return False (not raise) when Ollama is not running"
        )

    def test_list_models_raises_not_silent_when_not_running(self):
        from signal_chain.providers.ollama import OllamaProvider

        unreachable = MagicMock()
        unreachable.list.side_effect = ConnectionRefusedError("[Errno 111] Connection refused")

        with patch("ollama.Client", return_value=unreachable):
            provider = OllamaProvider()
            with pytest.raises(Exception):
                provider.list_models()
            # Reaching here means an exception was raised — no silent empty list.

    def test_error_message_names_ollama(self):
        """The raised exception must mention Ollama so the user knows what to fix."""
        from signal_chain.providers.ollama import OllamaProvider

        unreachable = MagicMock()
        unreachable.list.side_effect = ConnectionRefusedError("[Errno 111] Connection refused")

        with patch("ollama.Client", return_value=unreachable):
            provider = OllamaProvider()
            with pytest.raises(Exception) as exc_info:
                provider.list_models()

        message = str(exc_info.value)
        assert message, "Error message must not be empty"
        assert "ollama" in message.lower(), (
            f"Error message must mention 'Ollama' to be actionable, got: {message!r}"
        )

    def test_validate_config_handles_os_error_without_crashing(self):
        """OSError (e.g. service not installed) must not propagate unhandled."""
        from signal_chain.providers.ollama import OllamaProvider

        unreachable = MagicMock()
        unreachable.list.side_effect = OSError("No such file or directory: 'ollama'")

        with patch("ollama.Client", return_value=unreachable):
            provider = OllamaProvider()
            result = provider.validate_config()

        assert result is False, (
            "validate_config must return False for any connectivity failure, not crash"
        )


# ---------------------------------------------------------------------------
# TC-22: Local Model Addition via Wizard
# ---------------------------------------------------------------------------

class TestTC22LocalModelAdditionViaWizard:
    """add_model() on a .gguf file auto-detects metadata; model appears in list_models()."""

    # Stub GGUF file: 4-byte GGUF magic + padding.  Real detection is tested
    # in the builder's unit tests; here we verify the provider interface.
    _GGUF_MAGIC = b"GGUF" + b"\x00" * 64

    @_xfail
    def test_model_name_is_autodetected(self, tmp_path):
        from signal_chain.providers.local_gguf import LocalGGUFProvider

        gguf_file = tmp_path / "llama3-8b.Q4_K_M.gguf"
        gguf_file.write_bytes(self._GGUF_MAGIC)

        provider = LocalGGUFProvider()
        model_info = provider.add_model(gguf_file)

        assert model_info.name, "Model name must be auto-detected from the .gguf file"

    @_xfail
    def test_model_size_bytes_is_autodetected(self, tmp_path):
        from signal_chain.providers.local_gguf import LocalGGUFProvider

        gguf_file = tmp_path / "llama3-8b.Q4_K_M.gguf"
        gguf_file.write_bytes(self._GGUF_MAGIC)

        provider = LocalGGUFProvider()
        model_info = provider.add_model(gguf_file)

        assert model_info.size_bytes > 0, (
            "Model file size in bytes must be populated (see FLAG TC-22 at top of file)"
        )

    @_xfail
    def test_context_length_is_autodetected(self, tmp_path):
        from signal_chain.providers.local_gguf import LocalGGUFProvider

        gguf_file = tmp_path / "llama3-8b.Q4_K_M.gguf"
        gguf_file.write_bytes(self._GGUF_MAGIC)

        provider = LocalGGUFProvider()
        model_info = provider.add_model(gguf_file)

        assert model_info.context_length > 0, (
            "Context length must be auto-detected from the .gguf metadata"
        )

    @_xfail
    def test_quantization_is_autodetected(self, tmp_path):
        from signal_chain.providers.local_gguf import LocalGGUFProvider

        gguf_file = tmp_path / "llama3-8b.Q4_K_M.gguf"
        gguf_file.write_bytes(self._GGUF_MAGIC)

        provider = LocalGGUFProvider()
        model_info = provider.add_model(gguf_file)

        assert model_info.quantization, (
            "Quantization type must be auto-detected (e.g. 'Q4_K_M')"
        )

    @_xfail
    def test_added_model_appears_in_list_models(self, tmp_path):
        from signal_chain.providers.local_gguf import LocalGGUFProvider

        gguf_file = tmp_path / "llama3-8b.Q4_K_M.gguf"
        gguf_file.write_bytes(self._GGUF_MAGIC)

        provider = LocalGGUFProvider()
        added = provider.add_model(gguf_file)
        all_ids = [m.id for m in provider.list_models()]

        assert added.id in all_ids, (
            "A model added via add_model() must appear in the subsequent list_models() result"
        )


# ---------------------------------------------------------------------------
# ClaudeProvider: owned adapter interface (Humble Object pattern)
# ---------------------------------------------------------------------------

class TestClaudeProvider:
    """Contract tests for the owned adapter layer above the anthropic.Anthropic boundary.

    CRITICAL: anthropic.Anthropic() and messages.stream() are NOT mocked here —
    they are the Humble Object boundary (thin wrappers, untestable in isolation).
    All mocking targets OWNED types: ClaudeProvider._stream_tokens() and keyring.
    """

    def test_generate_stream_delegates_to_stream_tokens_adapter(self, monkeypatch):
        """generate_stream() must call self._stream_tokens() rather than the raw API directly."""
        from signal_chain.providers.base import GenerationConfig, Message
        from signal_chain.providers.claude import ClaudeProvider

        provider = ClaudeProvider()
        monkeypatch.setattr(
            provider,
            "_stream_tokens",
            lambda messages: iter(["Hello", " ", "world"]),
            raising=False,
        )
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        messages = [Message(role="user", content="hi")]
        tokens = list(provider.generate_stream(messages, GenerationConfig()))

        assert tokens == ["Hello", " ", "world"], (
            "generate_stream must delegate to _stream_tokens() and yield its tokens verbatim"
        )

    def test_validate_config_reads_api_key_from_keyring(self, monkeypatch):
        """validate_config must read the API key from keyring, not hardcode a result."""
        keyring_calls: list[tuple[str, str]] = []

        monkeypatch.setattr(
            "keyring.get_password",
            lambda svc, user: keyring_calls.append((svc, user)) or "sk-test-key",
        )

        from signal_chain.providers.claude import ClaudeProvider

        provider = ClaudeProvider()
        result = provider.validate_config()

        assert result is True, "validate_config must return True when API key is present"
        assert len(keyring_calls) == 1, (
            "validate_config must call keyring.get_password exactly once "
            "to retrieve the API key rather than hardcoding True"
        )

    def test_validate_config_returns_false_when_api_key_absent(self, monkeypatch):
        """validate_config must return False (not raise) when no key is stored."""
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.providers.claude import ClaudeProvider

        provider = ClaudeProvider()
        result = provider.validate_config()

        assert result is False, (
            "validate_config must return False when keyring.get_password returns None "
            "(no API key stored for the 'claude' provider)"
        )

    def test_list_models_returns_known_claude_model_ids(self):
        """list_models must return at least the supported Claude model family."""
        from signal_chain.providers.base import ModelInfo
        from signal_chain.providers.claude import ClaudeProvider

        provider = ClaudeProvider()
        models = provider.list_models()

        assert len(models) > 0, "list_models must return a non-empty list of Claude models"
        assert all(isinstance(m, ModelInfo) for m in models), (
            "Every item in list_models must be a ModelInfo instance"
        )
        model_ids = {m.id for m in models}
        known = {"claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"}
        assert model_ids & known, (
            f"list_models must include at least one known model ID from {known}; "
            f"got {model_ids}"
        )
