"""
Tests for the Web Access network gate — ticket #97.

Proves that the Web Access pedal's `enabled` state gates all outbound
network calls: OFF → blocked, ON → allowed, toggle flips the gate live.

Target (not yet built):
  signal_chain.modules.web_access.NetworkGate
  signal_chain.modules.web_access.NetworkBlockedError

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-A  Gate location: signal_chain.modules.web_access.NetworkGate.
          Alternative: signal_chain.providers.network_gate or co-located
          with PedalboardViewModel.  Adjust the import path if moved.

  FLAG-B  Gate constructor: NetworkGate(pedalboard_vm: PedalboardViewModel).
          The gate holds a reference to the VM and reads
          vm._by_id["web_access"].enabled at call time (live, no snapshot).
          Alternative: NetworkGate(module: PedalModule) takes the PedalModule
          directly.  Both work; the VM form is easier to wire at app start.

  FLAG-C  Blocking behaviour: gate.check_or_raise() raises NetworkBlockedError
          (subclass of Exception) when web_access is disabled.
          Providers call self._gate.check_or_raise() before any outbound I/O.
          Alternative: gate returns an error dict / empty iterator instead of
          raising — raise is preferred (callers can't silently swallow it).

  FLAG-D  Provider integration is OUT OF SCOPE for this ticket.
          Tests here confirm only the gate's own contract.  A follow-on ticket
          wires check_or_raise() into each network-calling provider.
"""
import pytest

_xfail = pytest.mark.xfail(
    reason="NetworkGate not yet implemented — TDD red phase",
    strict=True,
)


# ---------------------------------------------------------------------------
# A. is_allowed() mirrors web_access.enabled
# ---------------------------------------------------------------------------

class TestNetworkGateAllowed:

    @_xfail
    def test_gate_blocked_when_web_access_disabled(self):
        """is_allowed() returns False when the web_access pedal is OFF."""
        from signal_chain.modules.web_access import NetworkGate
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        # web_access starts disabled (enabled=False per PedalboardViewModel init)
        gate = NetworkGate(vm)

        assert gate.is_allowed() is False, (
            "NetworkGate.is_allowed() must return False when web_access.enabled is False"
        )

    @_xfail
    def test_gate_allowed_when_web_access_enabled(self):
        """is_allowed() returns True after toggling web_access ON."""
        from signal_chain.modules.web_access import NetworkGate
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("web_access")  # OFF → ON
        gate = NetworkGate(vm)

        assert gate.is_allowed() is True, (
            "NetworkGate.is_allowed() must return True when web_access.enabled is True"
        )

    @_xfail
    def test_gate_reflects_toggle_live(self):
        """The gate reads the VM state at call time — toggle after gate creation."""
        from signal_chain.modules.web_access import NetworkGate
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        gate = NetworkGate(vm)

        assert gate.is_allowed() is False, "gate must start blocked (web_access OFF)"

        vm.toggle_module("web_access")  # OFF → ON
        assert gate.is_allowed() is True, (
            "gate.is_allowed() must update immediately when web_access is toggled ON "
            "(gate holds a live reference to the VM, not a snapshot)"
        )

        vm.toggle_module("web_access")  # ON → OFF
        assert gate.is_allowed() is False, (
            "gate.is_allowed() must update immediately when web_access is toggled OFF"
        )


# ---------------------------------------------------------------------------
# B. check_or_raise() raises NetworkBlockedError when blocked
# ---------------------------------------------------------------------------

class TestNetworkGateRaise:

    @_xfail
    def test_check_or_raise_raises_when_blocked(self):
        """check_or_raise() must raise NetworkBlockedError when web_access is OFF."""
        from signal_chain.modules.web_access import NetworkBlockedError, NetworkGate
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        gate = NetworkGate(vm)

        with pytest.raises(NetworkBlockedError):
            gate.check_or_raise()

    @_xfail
    def test_check_or_raise_does_not_raise_when_allowed(self):
        """check_or_raise() must return normally (not raise) when web_access is ON."""
        from signal_chain.modules.web_access import NetworkGate
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("web_access")  # OFF → ON
        gate = NetworkGate(vm)

        gate.check_or_raise()  # must not raise
