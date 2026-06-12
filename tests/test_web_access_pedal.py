"""
Tests for pedal_webAccess — ticket #118.

The module does not exist yet. Every test imports from
signal_chain.modules.pedal_webAccess inside its body so that
ImportError surfaces as xfail, not a collection error.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-A  Gateway injection: pedal_webAccess(gateway=None).
          Follows ADR-008 — gateway kwarg matches the ConversationViewModel
          pattern (_PermitGateway() as the default null-object).
          Alternative: gateway passed per execute() call rather than at
          construction. Do NOT decide here — flag it if the per-call form
          fits the module interface better.

  FLAG-B  execute("fetch") return shape: {"content": str, "url": str}.
          "content" is the page body as a string; "url" echoes the requested
          URL.  If pedal_connectedAccounts or BaseModule convention implies a
          different shape (e.g. {"result": ..., "error": ...}), flag it rather
          than changing the assertion.

  FLAG-C  HTTP mocking target: urllib.request.urlopen.
          If the implementation uses requests or httpx, update the monkeypatch
          target accordingly.  Flagged so the builder knows what the test patches.

Do NOT duplicate tests from tests/test_web_access_gate.py — that file already
covers NetworkGateway.authorize() in full. These tests cover the pedal_webAccess
module itself: importability, interface shape, fetch behaviour, and gate wiring.
"""
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# 1. Importability
# ---------------------------------------------------------------------------

class TestPedalWebAccessImportable:

    def test_pedal_webAccess_is_importable(self):
        """The module must be importable and the class instantiable."""
        from signal_chain.modules.pedal_webAccess import pedal_webAccess  # noqa: N813

        instance = pedal_webAccess()
        assert instance is not None


# ---------------------------------------------------------------------------
# 2. Module interface
# ---------------------------------------------------------------------------

class TestPedalWebAccessInterface:

    def test_pedal_webAccess_follows_module_interface(self):
        """Must expose initialize() and execute() matching the BaseModule contract."""
        from signal_chain.modules.pedal_webAccess import pedal_webAccess  # noqa: N813

        instance = pedal_webAccess()

        assert callable(getattr(instance, "initialize", None)), (
            "pedal_webAccess must expose initialize()"
        )
        assert callable(getattr(instance, "execute", None)), (
            "pedal_webAccess must expose execute(function_name, parameters, caller_module=None)"
        )


# ---------------------------------------------------------------------------
# 3. Fetch succeeds when gate is enabled
# ---------------------------------------------------------------------------

class TestPedalWebAccessFetchEnabled:

    def test_fetch_returns_content_when_gate_enabled(self, monkeypatch):
        """execute('fetch') returns {'content': <non-empty str>} when web_access is ON."""
        from signal_chain.modules.network_gateway import NetworkGateway, _PermitGateway  # noqa: F401
        from signal_chain.modules.pedal_webAccess import pedal_webAccess  # noqa: N813
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        # Build a live gateway with web_access enabled.
        vm = PedalboardViewModel()
        vm.toggle_module("web_access")  # OFF → ON
        gateway = NetworkGateway(vm)

        # Mock HTTP so no real request leaves CI (FLAG-C: urllib.request.urlopen).
        fake_response = MagicMock()
        fake_response.read.return_value = b"<html><body>Hello</body></html>"
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: fake_response)

        pedal = pedal_webAccess(gateway=gateway)
        pedal.initialize()
        result = pedal.execute("fetch", {"url": "https://example.com"})

        assert "content" in result, (
            "execute('fetch') must return a dict with a 'content' key"
        )
        assert result["content"], (
            "content must be a non-empty string (FLAG-B: flag if return shape differs)"
        )


# ---------------------------------------------------------------------------
# 4. Fetch raises NetworkBlockedError when gate is disabled
# ---------------------------------------------------------------------------

class TestPedalWebAccessFetchBlocked:

    def test_fetch_raises_network_blocked_error_when_gate_disabled(self):
        """execute('fetch') raises NetworkBlockedError when web_access is OFF."""
        from signal_chain.modules.network_gateway import NetworkBlockedError, NetworkGateway
        from signal_chain.modules.pedal_webAccess import pedal_webAccess  # noqa: N813
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        # web_access starts disabled (PedalboardViewModel default).
        vm = PedalboardViewModel()
        gateway = NetworkGateway(vm)

        pedal = pedal_webAccess(gateway=gateway)
        pedal.initialize()

        with pytest.raises(NetworkBlockedError):
            pedal.execute("fetch", {"url": "https://example.com"})

    def test_no_http_call_made_when_gate_disabled(self, monkeypatch):
        """No outbound HTTP request must be made when the gateway blocks the fetch."""
        from signal_chain.modules.network_gateway import NetworkBlockedError, NetworkGateway
        from signal_chain.modules.pedal_webAccess import pedal_webAccess  # noqa: N813
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        # Track whether urllib.request.urlopen is ever called.
        http_calls: list[str] = []

        def _tracking_urlopen(url, *args, **kwargs):
            http_calls.append(str(url))
            raise AssertionError("urlopen must not be called when gate is disabled")

        monkeypatch.setattr("urllib.request.urlopen", _tracking_urlopen)

        vm = PedalboardViewModel()
        gateway = NetworkGateway(vm)  # web_access OFF → web:fetch denied

        pedal = pedal_webAccess(gateway=gateway)
        pedal.initialize()

        try:
            pedal.execute("fetch", {"url": "https://example.com"})
        except NetworkBlockedError:
            pass  # expected — gate blocked before HTTP

        assert http_calls == [], (
            "urllib.request.urlopen must not be called when NetworkBlockedError is raised "
            "(FLAG-C: update target if implementation uses requests or httpx)"
        )
