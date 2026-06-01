from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signal_chain.viewmodels.pedalboard import PedalboardViewModel

# Scopes granted unconditionally — providers reachable out of the box.
_ALWAYS_GRANTED: frozenset[str] = frozenset({"net:provider"})

# Scopes gated on the Web Access pedal being enabled.
_WEB_ACCESS_SCOPES: frozenset[str] = frozenset({"web:fetch"})


class NetworkBlockedError(Exception):
    """Raised by NetworkGateway.authorize() when a scope is not granted."""


class NetworkGateway:
    """Scope-based authorization chokepoint for all outbound network access.

    Policy:
      - Default-deny: any unrecognised scope is blocked.
      - "net:provider": always granted (LLM providers reachable out of the box).
      - "web:fetch": granted iff the Web Access pedal (PedalModule) is enabled.

    Live state: authorize() reads module state at call time. Toggling a module
    after construction takes effect immediately on the same gateway instance.
    """

    def __init__(self, vm: PedalboardViewModel) -> None:
        self._vm = vm

    def authorize(self, scope: str) -> None:
        """Grant or deny a network scope.

        Returns None silently on grant; raises NetworkBlockedError on deny.
        """
        if scope in _ALWAYS_GRANTED:
            return

        if scope in _WEB_ACCESS_SCOPES:
            if self._vm._by_id["web_access"].enabled:
                return
            raise NetworkBlockedError(
                f"Scope '{scope}' denied: Web Access module is disabled"
            )

        raise NetworkBlockedError(
            f"Scope '{scope}' denied: not a recognised scope (default-deny)"
        )
