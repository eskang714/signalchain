"""
Tests for the network gateway scope-authorization contract — ticket #98.

Supersedes the boolean-gate contract from ticket #97.

TARGET (not yet built):
  signal_chain.modules.web_access.NetworkGateway
  signal_chain.modules.web_access.NetworkBlockedError

CONTRACT (source of truth for this file):
  - DEFAULT-DENY: any scope not explicitly granted raises NetworkBlockedError.
  - "net:provider" is always granted (providers reachable out of the box).
  - "web:fetch" is granted only while the Web Access module is enabled.
    The gateway reads live module state at authorize() call time — NOT a
    snapshot from construction time. Toggling the module flips the result
    for the SAME gateway instance immediately.
  - A denied scope raises NetworkBlockedError; a granted scope returns None.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-1  Class name: NetworkGateway.
          Old name (ticket #97 boolean gate) was NetworkGate.  Renamed to
          reflect the richer scope contract.  If the builder keeps NetworkGate,
          update the import.

  FLAG-2  Constructor: NetworkGateway(pedalboard_vm: PedalboardViewModel).
          Reads vm._by_id["web_access"].enabled at authorize() call time.
          Alternative: NetworkGateway(web_access_module: PedalModule) takes
          the module directly; both are equivalent.

  FLAG-3  Method: authorize(scope: str) -> None.
          Returns None silently when granted; raises NetworkBlockedError when
          denied.  Alternative name: check(scope), request(scope).

  FLAG-4  Scope strings: "net:provider" and "web:fetch".
          If the builder uses a different naming convention (e.g. "provider",
          "web_access", or an enum), update the string literals here.
"""
import pytest

_xfail = pytest.mark.xfail(
    reason="NetworkGateway scope contract not yet implemented — TDD red phase",
    strict=True,
)


# ---------------------------------------------------------------------------
# A. Default-deny policy and built-in scopes
# ---------------------------------------------------------------------------

class TestScopeAuthorization:

    @_xfail
    def test_unknown_scope_is_denied_by_default(self):
        """An unrecognised scope string must be denied (default-deny policy)."""
        from signal_chain.modules.web_access import NetworkBlockedError, NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        gateway = NetworkGateway(vm)

        with pytest.raises(NetworkBlockedError):
            gateway.authorize("unknown:scope")

    @_xfail
    def test_net_provider_scope_is_always_granted(self):
        """net:provider must be granted regardless of module state (providers reachable out of the box)."""
        from signal_chain.modules.web_access import NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        gateway = NetworkGateway(vm)

        gateway.authorize("net:provider")  # must not raise

    @_xfail
    def test_net_provider_granted_even_when_web_access_is_off(self):
        """net:provider is independent of the web_access toggle."""
        from signal_chain.modules.web_access import NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        # web_access starts disabled; net:provider must still pass
        gateway = NetworkGateway(vm)

        gateway.authorize("net:provider")  # must not raise


# ---------------------------------------------------------------------------
# B. web:fetch scope tied to Web Access module state
# ---------------------------------------------------------------------------

class TestWebFetchScope:

    @_xfail
    def test_web_fetch_denied_when_web_access_module_is_off(self):
        """web:fetch is denied while the Web Access pedal is disabled."""
        from signal_chain.modules.web_access import NetworkBlockedError, NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        # web_access starts disabled (enabled=False per PedalboardViewModel init)
        gateway = NetworkGateway(vm)

        with pytest.raises(NetworkBlockedError):
            gateway.authorize("web:fetch")

    @_xfail
    def test_web_fetch_granted_when_web_access_module_is_on(self):
        """web:fetch is granted while the Web Access pedal is enabled."""
        from signal_chain.modules.web_access import NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("web_access")  # OFF → ON
        gateway = NetworkGateway(vm)

        gateway.authorize("web:fetch")  # must not raise

    @_xfail
    def test_web_fetch_reflects_live_toggle_on_same_gateway_instance(self):
        """Toggling web_access after gateway construction flips web:fetch authorization immediately."""
        from signal_chain.modules.web_access import NetworkBlockedError, NetworkGateway
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        gateway = NetworkGateway(vm)

        # web_access OFF → denied
        with pytest.raises(NetworkBlockedError):
            gateway.authorize("web:fetch")

        # toggle ON → granted
        vm.toggle_module("web_access")
        gateway.authorize("web:fetch")  # must not raise

        # toggle back OFF → denied again
        vm.toggle_module("web_access")
        with pytest.raises(NetworkBlockedError):
            gateway.authorize("web:fetch")
