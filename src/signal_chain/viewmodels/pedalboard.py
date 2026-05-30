from __future__ import annotations

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
        self.enabled: bool = True
        self.functional: bool = True

    @property
    def led_on(self) -> bool:
        return self.functional


class PedalboardViewModel(QObject):
    """ViewModel for the bottom pedalboard strip.

    Owns six PedalModule instances (one per global module).
    Exposes toggle_module() and set_module_functional() as the two
    state-mutation entry points; emits module_state_changed on toggle.
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

    def toggle_module(self, module_id: str) -> None:
        module = self._by_id[module_id]
        module.enabled = not module.enabled
        self.module_state_changed.emit(module_id, module.enabled)

    def set_module_functional(self, module_id: str, functional: bool) -> None:
        self._by_id[module_id].functional = functional
