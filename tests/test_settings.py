"""
Acceptance tests – Settings & Persistence
TC-38: Provider Config Persists
TC-39: Context Window Setting Applied

Target module (not yet implemented):
  signal_chain.models.settings.SettingsManager

Behavior contract (from Signal_Chain_Project_Brief.md):
  - Config stored as YAML in ~/.signal_chain/config/ (paths, context settings, etc.)
  - Credentials stored in OS keychain via keyring library — NEVER in config YAML
  - Context window default: window_size=20, token_limit=4096, response_buffer=1000
  - Context window configurable 10–50 recent messages
  - Settings persist across application restarts (save → new instance → read)
  - Invalid values rejected with a clear error

Keyring in tests:
  keyring.set_password / keyring.get_password are always mocked via monkeypatch.
  No real OS keychain is accessed in any test.
"""
import pytest

_KEYRING_SERVICE = "signalchain"


# ---------------------------------------------------------------------------
# TC-38: Provider Config Persists
# ---------------------------------------------------------------------------

class TestTC38ProviderConfigPersists:
    """API keys go to keyring, not to config.yaml; they survive a restart cycle."""

    def test_api_key_stored_via_keyring_set_password(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            "keyring.set_password",
            lambda svc, user, pwd: recorded.append((svc, user, pwd)),
        )
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        settings = SettingsManager.load(tmp_path / "config.yaml")
        settings.set_api_key("claude", "sk-test-key-123")

        assert len(recorded) == 1, (
            "set_api_key must call keyring.set_password exactly once"
        )
        assert recorded[0][0] == _KEYRING_SERVICE, (
            "keyring.set_password must use the application's keyring service name"
        )
        assert "sk-test-key-123" in recorded[0], (
            "The API key value must be passed to keyring.set_password"
        )

    def test_api_key_retrieved_via_keyring_get_password(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr(
            "keyring.get_password",
            lambda svc, user: "sk-test-key-456" if user == "claude" else None,
        )

        settings = SettingsManager.load(tmp_path / "config.yaml")
        key = settings.get_api_key("claude")

        assert key == "sk-test-key-456", (
            "get_api_key must retrieve the key via keyring.get_password"
        )

    def test_api_key_absent_from_config_yaml_after_save(self, tmp_path, monkeypatch):
        from signal_chain.models.settings import SettingsManager

        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        config_path = tmp_path / "config.yaml"
        settings = SettingsManager.load(config_path)
        settings.set_api_key("claude", "sk-secret-key-do-not-store")
        settings.save()

        raw = config_path.read_text()
        assert "sk-secret-key-do-not-store" not in raw, (
            "API key must NEVER appear in the YAML config file — keychain only"
        )
        assert "sk-secret" not in raw, (
            "No fragment of the API key may appear in the config file"
        )

    def test_api_key_survives_save_and_reload_cycle(self, tmp_path, monkeypatch):
        keychain: dict[tuple[str, str], str] = {}

        def fake_set(svc: str, user: str, pwd: str) -> None:
            keychain[(svc, user)] = pwd

        def fake_get(svc: str, user: str) -> str | None:
            return keychain.get((svc, user))

        monkeypatch.setattr("keyring.set_password", fake_set)
        monkeypatch.setattr("keyring.get_password", fake_get)

        from signal_chain.models.settings import SettingsManager

        config_path = tmp_path / "config.yaml"

        settings = SettingsManager.load(config_path)
        settings.set_api_key("claude", "sk-persistent-key")
        settings.save()

        reloaded = SettingsManager.load(config_path)
        retrieved = reloaded.get_api_key("claude")

        assert retrieved == "sk-persistent-key", (
            "API key must be retrievable from a freshly loaded SettingsManager — "
            "simulates application restart"
        )

    def test_missing_api_key_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        settings = SettingsManager.load(tmp_path / "config.yaml")
        key = settings.get_api_key("claude")

        assert key is None, (
            "get_api_key must return None (not raise) when no key has been stored"
        )


# ---------------------------------------------------------------------------
# TC-39: Context Window Setting Applied
# ---------------------------------------------------------------------------

class TestTC39ContextWindowSettingApplied:
    """Changing window_size in settings affects how many messages are sent to the model."""

    def test_default_context_window_size_is_20(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        settings = SettingsManager.load(tmp_path / "config.yaml")
        assert settings.get_context_window_size() == 20, (
            "Default context window size must be 20 per the project brief"
        )

    def test_context_window_size_changeable(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        settings = SettingsManager.load(tmp_path / "config.yaml")
        settings.set_context_window_size(10)

        assert settings.get_context_window_size() == 10, (
            "set_context_window_size(10) must be immediately reflected by get_context_window_size()"
        )

    def test_context_window_size_persists_across_reload(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        config_path = tmp_path / "config.yaml"
        settings = SettingsManager.load(config_path)
        settings.set_context_window_size(15)
        settings.save()

        reloaded = SettingsManager.load(config_path)
        assert reloaded.get_context_window_size() == 15, (
            "context_window_size must survive a save → reload cycle (simulates restart)"
        )

    def test_context_window_size_below_minimum_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        settings = SettingsManager.load(tmp_path / "config.yaml")
        with pytest.raises((ValueError, TypeError)):
            settings.set_context_window_size(9), (
                "window_size below the minimum of 10 must be rejected with ValueError"
            )

    def test_context_window_size_above_maximum_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.settings import SettingsManager

        settings = SettingsManager.load(tmp_path / "config.yaml")
        with pytest.raises((ValueError, TypeError)):
            settings.set_context_window_size(51), (
                "window_size above the maximum of 50 must be rejected with ValueError"
            )

    def test_context_window_size_from_settings_applied_to_context_manager(
        self, tmp_path, monkeypatch
    ):
        """TC-39 end-to-end: changed setting limits messages forwarded to model."""
        monkeypatch.setattr("keyring.set_password", lambda svc, user, pwd: None)
        monkeypatch.setattr("keyring.get_password", lambda svc, user: None)

        from signal_chain.models.context import ContextWindowManager
        from signal_chain.models.settings import SettingsManager
        from signal_chain.providers.base import Message

        config_path = tmp_path / "config.yaml"
        settings = SettingsManager.load(config_path)
        settings.set_context_window_size(10)
        settings.save()

        reloaded = SettingsManager.load(config_path)
        mgr = ContextWindowManager(
            window_size=reloaded.get_context_window_size(),
            token_limit=999_999,
        )

        msgs = [
            Message(role="user" if i % 2 == 0 else "assistant", content=f"msg {i}")
            for i in range(50)
        ]
        result = mgr.prepare_messages(msgs)

        assert len(result) == 10, (
            "After changing the setting to 10 and reloading, only the 10 most "
            "recent messages must be included — simulates the user changing Settings → "
            "Context → Recent messages from 20 to 10"
        )
