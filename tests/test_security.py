"""
Acceptance tests – Security & Data Integrity
TC-35: API Key Never Exposed
TC-36: Cross-Platform Keychain
TC-37: Connected Accounts Scope Enforcement

Existing state:
  SettingsManager (signal_chain.models.settings) — implemented; stores API keys
    via keyring.set_password, never writes them to the config YAML.
  ClaudeProvider — implemented; reads credentials via anthropic.Anthropic()
    (picks up env var by default). Provider-to-keyring wiring not yet enforced.
  connected_accounts global module — NOT yet implemented.

xfail policy:
  - TC-35 "key not in YAML" and "key not in log output": PASS —
    SettingsManager already guarantees these properties.
  - TC-35 "API key masked in str/repr": XFAIL — no SecretStr/masking wrapper exists.
  - TC-36 "keyring called", "error propagates", "no plaintext fallback file": PASS —
    SettingsManager already has the correct behavior.
  - TC-36 "null keyring backend detected": XFAIL — no backend-detection guard exists.
  - TC-37: all XFAIL — connected_accounts module is not yet implemented.

FLAG TC-35 (partial): "any UI element" — rendering of API key fields in the
  Settings view is not testable in a headless pytest run.
  Options:
    A) Accept that config-file and log assertions cover the intent.
    B) Add a widget test for the Settings view once it masks key input.
  Recommendation: Option A. Waiting for human decision.
"""
import logging

import pytest

_KEYRING_SERVICE = "signalchain"


# ---------------------------------------------------------------------------
# TC-35: API Key Never Exposed
# ---------------------------------------------------------------------------

class TestTC35ApiKeyNeverExposed:
    """API keys must not appear in config files, logs, or provider attributes."""

    def test_api_key_not_in_config_yaml_after_save(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        keychain: dict[tuple[str, str], str] = {}
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: keychain.__setitem__((svc, user), pwd))
        monkeypatch.setattr("keyring.get_password", lambda svc, user: keychain.get((svc, user)))

        config_path = tmp_path / "config.yaml"
        settings = SettingsManager.load(config_path)
        settings.set_api_key("claude", "sk-plaintext-exposure-test")
        settings.save()

        raw = config_path.read_text()
        assert "sk-plaintext-exposure-test" not in raw, (
            "API key must not appear anywhere in the saved YAML config"
        )

    def test_api_key_not_in_log_output_when_stored(self, tmp_path, monkeypatch, caplog):
        from signal_chain.models.settings import SettingsManager

        keychain: dict[tuple[str, str], str] = {}
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: keychain.__setitem__((svc, user), pwd))
        monkeypatch.setattr("keyring.get_password", lambda svc, user: keychain.get((svc, user)))

        settings = SettingsManager.load(tmp_path / "config.yaml")
        with caplog.at_level(logging.DEBUG):
            settings.set_api_key("claude", "sk-log-exposure-test")

        assert "sk-log-exposure-test" not in caplog.text, (
            "API key must not appear in any log output when stored"
        )

    def test_api_key_not_in_log_output_when_retrieved(self, tmp_path, monkeypatch, caplog):
        from signal_chain.models.settings import SettingsManager

        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr(
            "keyring.get_password",
            lambda svc, user: "sk-log-retrieval-test",
        )

        settings = SettingsManager.load(tmp_path / "config.yaml")
        with caplog.at_level(logging.DEBUG):
            settings.get_api_key("claude")

        assert "sk-log-retrieval-test" not in caplog.text, (
            "API key must not appear in any log output when retrieved"
        )

    def test_api_key_not_stored_as_attribute_on_settings_manager(
        self, tmp_path, monkeypatch
    ):
        """API key must not be held as a plain attribute — only keyring holds it."""
        from signal_chain.models.settings import SettingsManager

        keychain: dict[tuple[str, str], str] = {}
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: keychain.__setitem__((svc, user), pwd))
        monkeypatch.setattr("keyring.get_password", lambda svc, user: keychain.get((svc, user)))

        settings = SettingsManager.load(tmp_path / "config.yaml")
        settings.set_api_key("claude", "sk-attr-check-test")

        as_str = repr(settings) + str(settings)
        assert "sk-attr-check-test" not in as_str, (
            "SettingsManager must not store the API key as a plain instance attribute "
            "(which would appear in repr/str and risk leaking in logs)"
        )
        for attr_value in vars(settings).values():
            assert attr_value != "sk-attr-check-test", (
                "The API key must not appear as the value of any SettingsManager attribute"
            )


# ---------------------------------------------------------------------------
# TC-36: Cross-Platform Keychain
# ---------------------------------------------------------------------------

class TestTC36CrossPlatformKeychain:
    """keyring is always used; no plaintext fallback occurs on any platform."""

    def test_keyring_set_password_called_on_store(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        calls: list[tuple[str, str, str]] = []
        keychain: dict[tuple[str, str], str] = {}

        def _mock_set(svc: str, user: str, pwd: str) -> None:
            calls.append((svc, user, pwd))
            keychain[(svc, user)] = pwd

        monkeypatch.setattr("keyring.set_password", _mock_set)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: keychain.get((svc, user)))

        settings = SettingsManager.load(tmp_path / "config.yaml")
        settings.set_api_key("claude", "sk-keyring-call-test")

        assert len(calls) == 1, "set_api_key must delegate to keyring.set_password"
        assert calls[0][2] == "sk-keyring-call-test", (
            "The exact key value must be passed to keyring.set_password"
        )

    def test_keyring_failure_propagates_not_swallowed(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        def raise_keyring_error(svc: str, user: str, pwd: str) -> None:
            raise RuntimeError("Keyring backend unavailable")

        monkeypatch.setattr("keyring.set_password", raise_keyring_error)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        settings = SettingsManager.load(tmp_path / "config.yaml")
        with pytest.raises(Exception):
            settings.set_api_key("claude", "sk-error-test")

    def test_no_plaintext_fallback_file_created_on_keyring_failure(
        self, tmp_path, monkeypatch
    ):
        from signal_chain.models.settings import SettingsManager

        def raise_keyring_error(svc: str, user: str, pwd: str) -> None:
            raise RuntimeError("Keyring backend unavailable")

        monkeypatch.setattr("keyring.set_password", raise_keyring_error)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        settings = SettingsManager.load(tmp_path / "config.yaml")
        try:
            settings.set_api_key("claude", "sk-fallback-test")
        except Exception:
            pass

        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert "sk-fallback-test" not in path.read_text(), (
                    f"API key must not appear in any file after keyring failure — "
                    f"found in {path.name}"
                )

    def test_null_keyring_backend_detected_not_silently_discarded(
        self, tmp_path, monkeypatch
    ):
        """If keyring silently discards credentials (null backend), an error must be raised."""
        from signal_chain.models.settings import SettingsManager

        def null_set(svc: str, user: str, pwd: str) -> None:
            pass  # null backend: silently discards

        def null_get(svc: str, user: str) -> str | None:
            return None  # null backend: always returns None

        monkeypatch.setattr("keyring.set_password", null_set)
        monkeypatch.setattr("keyring.get_password", null_get)

        settings = SettingsManager.load(tmp_path / "config.yaml")

        with pytest.raises(Exception):
            settings.set_api_key("claude", "sk-null-backend-test"), (
                "set_api_key must detect when keyring silently discarded the credential "
                "(i.e., get_password returns None immediately after set_password) "
                "and raise rather than silently pretend the key was stored"
            )


# ---------------------------------------------------------------------------
# TC-37: Connected Accounts Scope Enforcement
# ---------------------------------------------------------------------------

class TestTC37ConnectedAccountsScopeEnforcement:
    """connected_accounts provides tokens only — it never calls external APIs itself."""

    def test_get_token_returns_token_for_connected_service(self):
        from signal_chain.modules.pedal_connectedAccounts import pedal_connectedAccounts

        module = pedal_connectedAccounts()
        module.initialize()
        result = module.execute("get_token", {"service": "google"})

        assert isinstance(result, dict), "get_token must return a dict"
        assert "token" in result, "get_token must return a dict with a 'token' key"
        assert result["token"] is not None, "token must be non-None for a connected service"

    def test_connected_accounts_makes_no_external_network_calls(self, monkeypatch):
        """connected_accounts is a pure passthrough — no outbound HTTP during get_token."""
        from signal_chain.modules.pedal_connectedAccounts import pedal_connectedAccounts

        network_calls: list[str] = []

        def intercept(*args: object, **kwargs: object) -> None:
            network_calls.append(str(args))
            raise RuntimeError("Network access blocked in tests")

        monkeypatch.setattr("urllib.request.urlopen", intercept)

        module = pedal_connectedAccounts()
        module.initialize()
        module.execute("get_token", {"service": "google"})

        assert len(network_calls) == 0, (
            "connected_accounts.get_token must not make outbound network calls — "
            "it only retrieves stored tokens, never calls external APIs itself"
        )

    def test_get_token_result_contains_credential_not_api_data(self):
        """The returned dict contains credential fields only, not API response payloads."""
        from signal_chain.modules.pedal_connectedAccounts import pedal_connectedAccounts

        module = pedal_connectedAccounts()
        module.initialize()
        result = module.execute("get_token", {"service": "google"})

        assert result, "get_token must return a non-empty result"
        allowed_keys = {"token", "token_type", "expires_at", "service", "error"}
        unexpected = set(result.keys()) - allowed_keys
        assert not unexpected, (
            f"get_token must only return credential fields, not API response data. "
            f"Unexpected keys: {unexpected}"
        )

    def test_connected_accounts_has_no_data_processing_functions(self):
        """connected_accounts exposes only auth functions, not data-fetching calls."""
        from signal_chain.modules.pedal_connectedAccounts import pedal_connectedAccounts

        module = pedal_connectedAccounts()
        function_names = [f.name for f in module.get_functions()]

        data_processing_keywords = ("fetch", "query", "send", "post", "get_data", "call")
        data_processing = [
            name for name in function_names
            if any(kw in name.lower() for kw in data_processing_keywords)
        ]
        assert not data_processing, (
            f"connected_accounts must not expose data-fetching functions — "
            f"scope is auth (tokens) only. Found: {data_processing}"
        )
