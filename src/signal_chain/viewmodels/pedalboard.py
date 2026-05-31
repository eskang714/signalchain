from __future__ import annotations

import enum
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

# (module_id, title, [(control_label, default_value), ...])
_MODULE_SPECS: list[tuple[str, str, list[tuple[str, Any]]]] = [
    ("conv_history", "CONV. HISTORY", [("DEPTH", 10), ("WINDOW", 20), ("TOKENS", 4096)]),
    ("connected",    "CONNECTED",     [("TOKEN", 80), ("SCOPE", 3), ("EXPIRE", 7)]),
    ("markdown",     "MARKDOWN",      [("FORMAT", 2), ("LEVEL", 75), ("WRAP", 80)]),
    ("web_access",   "WEB ACCESS",    [("TIMEOUT", 10), ("DEPTH", 2), ("CACHE", 50)]),
    ("file_access",  "FILE ACCESS",   [("MAX SIZE", 10), ("DEPTH", 3), ("WATCH", 0)]),
    ("clock",        "CLOCK",         [("ZONE", 0), ("FORMAT", 0), ("INTERVAL", 5)]),
]


class LedStatus(enum.Enum):
    NO_CONNECTION = "no_connection"  # gray  — no API key / service unreachable
    CONNECTED_OFF = "connected_off"  # red   — connected but footswitch OFF
    CONNECTED_ON  = "connected_on"   # green — connected and footswitch ON


class PedalModule:
    """Observable state for one pedal in the pedalboard strip."""

    def __init__(
        self,
        module_id: str,
        title: str,
        controls: list[dict[str, Any]],
    ) -> None:
        self.module_id = module_id
        self.title = title
        self.controls = controls
        # Footswitch starts OFF; toggling ON while connected shows green.
        self.enabled: bool = False
        # Set True by the VM's connection source (fake or real).
        self.connected: bool = False

    @property
    def led_status(self) -> LedStatus:
        if not self.connected:
            return LedStatus.NO_CONNECTION
        return LedStatus.CONNECTED_ON if self.enabled else LedStatus.CONNECTED_OFF


class PedalboardViewModel(QObject):
    """ViewModel for the bottom pedalboard strip.

    Owns six PedalModule instances (one per global module).
    Exposes toggle_module() and set_module_connected() as the two
    state-mutation entry points; emits module_state_changed on toggle.

    Connection source (fake for mockup):
      All modules are marked connected=True at init.  A real implementation
      would replace this with provider.validate_config() checks.
    """

    module_state_changed = pyqtSignal(str, bool)

    def __init__(self) -> None:
        super().__init__()
        self.modules: list[PedalModule] = [
            PedalModule(
                module_id=module_id,
                title=title,
                controls=[
                    {"label": label, "value": default, "default": default}
                    for label, default in controls
                ],
            )
            for module_id, title, controls in _MODULE_SPECS
        ]
        self._by_id: dict[str, PedalModule] = {m.module_id: m for m in self.modules}

        # Fake connection source: mark all modules connected.
        # Replace with real provider.validate_config() checks in a follow-on ticket.
        for m in self.modules:
            m.connected = True

    def toggle_module(self, module_id: str) -> None:
        module = self._by_id[module_id]
        module.enabled = not module.enabled
        self.module_state_changed.emit(module_id, module.enabled)

    def set_module_connected(self, module_id: str, connected: bool) -> None:
        """Test seam: inject connection status without a real provider registry."""
        self._by_id[module_id].connected = connected
