"""
Tests for PedalboardViewModel — ticket #91

Target (not yet built):
  signal_chain.viewmodels.pedalboard.PedalboardViewModel

These tests cover only the ViewModel layer — observable properties and signals.
The view widgets (PedalWidget / Pedalboard) are visual; they are verified by
manual QA, not this file.

CONTRACT CHOICES (flagged — builder must confirm or amend):

  FLAG-1  Module access: `vm.modules` returns a list of PedalModule objects,
          each with a `.module_id` str attribute.  If the builder prefers named
          attributes (vm.conv_history, etc.) these tests must be updated.

  FLAG-2  Control representation: `module.controls` is a list of dicts with
          keys {"label": str, "value": <default>, "default": <default>}.
          If the builder uses a dataclass (ControlSchema) the assertion style
          stays the same; only the access syntax changes.

  FLAG-3  functional vs enabled are SEPARATE flags.
            enabled  — user has pressed the ON footswitch (togglable).
            functional — module is actually working (e.g. API key present,
                         file path valid).  LED is on iff functional is True,
                         even when enabled is True.
          If the builder collapses these (functional == enabled), tests D/E
          become redundant and can be removed.

  FLAG-4  Signal name: module_state_changed(module_id: str, enabled: bool).
          If the builder chooses a different name or signature, update test F.

  FLAG-5  Toggle method: `vm.toggle_module(module_id: str)` flips enabled.
          Alternative: `vm.set_module_enabled(module_id, bool)`.

  FLAG-6  Functional setter: `vm.set_module_functional(module_id: str, v: bool)`
          used only in tests to inject status without a real module registry.
          If the builder exposes a different injection point, update tests D/E.
"""

_EXPECTED_IDS = [
    "conv_history",
    "connected",
    "markdown",
    "web_access",
    "file_access",
    "clock",
]

_EXPECTED_TITLES = {
    "conv_history": "CONV. HISTORY",
    "connected":    "CONNECTED",
    "markdown":     "MARKDOWN",
    "web_access":   "WEB ACCESS",
    "file_access":  "FILE ACCESS",
    "clock":        "CLOCK",
}

# Controls from mockup spec (label, default value).
_CONV_HISTORY_CONTROLS = [("DEPTH", 10), ("WINDOW", 20), ("TOKENS", 4096)]


# ---------------------------------------------------------------------------
# A. Structural shape
# ---------------------------------------------------------------------------

class TestPedalboardViewModelStructure:

    def test_exposes_exactly_six_modules(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        assert len(vm.modules) == 6, (
            f"PedalboardViewModel.modules must expose exactly six pedals; "
            f"got {len(vm.modules)}"
        )

    def test_all_expected_module_ids_present(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        ids = [m.module_id for m in vm.modules]
        for expected in _EXPECTED_IDS:
            assert expected in ids, (
                f"module_id '{expected}' must be present in PedalboardViewModel.modules"
            )

    def test_each_module_has_correct_title(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        by_id = {m.module_id: m for m in vm.modules}
        for module_id, expected_title in _EXPECTED_TITLES.items():
            assert by_id[module_id].title == expected_title, (
                f"module '{module_id}' title must be '{expected_title}'; "
                f"got '{by_id[module_id].title}'"
            )

    def test_each_module_has_three_controls(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        for module in vm.modules:
            assert len(module.controls) == 3, (
                f"module '{module.module_id}' must have exactly 3 controls "
                f"(per mockup spec); got {len(module.controls)}"
            )

    def test_conv_history_control_labels_and_defaults(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        by_id = {m.module_id: m for m in vm.modules}
        controls = by_id["conv_history"].controls

        for i, (expected_label, expected_default) in enumerate(_CONV_HISTORY_CONTROLS):
            assert controls[i]["label"] == expected_label, (
                f"conv_history control[{i}] label must be '{expected_label}'"
            )
            assert controls[i]["default"] == expected_default, (
                f"conv_history control[{i}] default must be {expected_default}"
            )


# ---------------------------------------------------------------------------
# B. Enabled / toggle state
# ---------------------------------------------------------------------------

class TestPedalboardToggle:

    def test_modules_start_disabled_by_default(self):
        """Modules start with footswitch OFF (enabled=False) so LED renders red
        (connected+off) until the user explicitly enables the module."""
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        for module in vm.modules:
            assert module.enabled is False, (
                f"module '{module.module_id}' must start disabled by default "
                "(connected+off → red LED until user toggles ON)"
            )

    def test_toggle_module_flips_enabled_state(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        # Module starts disabled (False); first toggle enables it.
        vm.toggle_module("conv_history")
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].enabled is True, (
            "toggle_module must enable a disabled module"
        )

        vm.toggle_module("conv_history")
        assert by_id["conv_history"].enabled is False, (
            "a second toggle_module must disable the module again"
        )


# ---------------------------------------------------------------------------
# C. Signal on state change
# ---------------------------------------------------------------------------

class TestPedalboardSignals:

    def test_toggle_emits_module_state_changed(self, qtbot):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        emitted: list[tuple[str, bool]] = []
        vm.module_state_changed.connect(
            lambda mid, enabled: emitted.append((mid, enabled))
        )

        vm.toggle_module("web_access")

        assert len(emitted) == 1, (
            "toggle_module must emit module_state_changed exactly once"
        )
        assert emitted[0][0] == "web_access", (
            "module_state_changed must carry the module_id as the first argument"
        )
        assert emitted[0][1] is True, (
            "module_state_changed must carry the new enabled state (True after first toggle)"
        )


# ---------------------------------------------------------------------------
# D–F. LED uses 3-state LedStatus, not a boolean.
#
# Bug reproduced: the old model had led_on = functional (boolean), and
# functional defaulted to True, so every pedal rendered constant green.
# The fix replaces functional with a (connected, enabled) pair that drives
# a LedStatus enum: NO_CONNECTION (gray), CONNECTED_OFF (red), CONNECTED_ON
# (green).
# ---------------------------------------------------------------------------

class TestPedalboardLed:

    def test_led_gray_when_not_connected(self):
        """No API connection → gray regardless of footswitch state."""
        from signal_chain.viewmodels.pedalboard import LedStatus, PedalboardViewModel

        vm = PedalboardViewModel()
        vm.set_module_connected("conv_history", False)
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_status is LedStatus.NO_CONNECTION, (
            "led_status must be NO_CONNECTION when the module has no API connection"
        )

    def test_led_red_when_connected_and_disabled(self):
        """Connected + footswitch OFF → red (connected_off)."""
        from signal_chain.viewmodels.pedalboard import LedStatus, PedalboardViewModel

        vm = PedalboardViewModel()
        # connected=True is already set by the fake source; enabled starts False.
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_status is LedStatus.CONNECTED_OFF, (
            "led_status must be CONNECTED_OFF when connected and not enabled"
        )

    def test_led_green_when_connected_and_enabled(self):
        """Connected + footswitch ON → green (connected_on)."""
        from signal_chain.viewmodels.pedalboard import LedStatus, PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("conv_history")   # False → True
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_status is LedStatus.CONNECTED_ON, (
            "led_status must be CONNECTED_ON when connected and enabled"
        )

    def test_led_gray_overrides_enabled_when_no_connection(self):
        """Gray wins even if footswitch is ON — connection is the precondition."""
        from signal_chain.viewmodels.pedalboard import LedStatus, PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("conv_history")           # enable it
        vm.set_module_connected("conv_history", False)  # lose connection
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_status is LedStatus.NO_CONNECTION, (
            "led_status must be NO_CONNECTION regardless of enabled when not connected"
        )
