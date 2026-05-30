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
import pytest

_xfail = pytest.mark.xfail(
    reason="PedalboardViewModel not yet implemented — TDD red phase",
    strict=True,
)

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

    @_xfail
    def test_exposes_exactly_six_modules(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        assert len(vm.modules) == 6, (
            f"PedalboardViewModel.modules must expose exactly six pedals; "
            f"got {len(vm.modules)}"
        )

    @_xfail
    def test_all_expected_module_ids_present(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        ids = [m.module_id for m in vm.modules]
        for expected in _EXPECTED_IDS:
            assert expected in ids, (
                f"module_id '{expected}' must be present in PedalboardViewModel.modules"
            )

    @_xfail
    def test_each_module_has_correct_title(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        by_id = {m.module_id: m for m in vm.modules}
        for module_id, expected_title in _EXPECTED_TITLES.items():
            assert by_id[module_id].title == expected_title, (
                f"module '{module_id}' title must be '{expected_title}'; "
                f"got '{by_id[module_id].title}'"
            )

    @_xfail
    def test_each_module_has_three_controls(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        for module in vm.modules:
            assert len(module.controls) == 3, (
                f"module '{module.module_id}' must have exactly 3 controls "
                f"(per mockup spec); got {len(module.controls)}"
            )

    @_xfail
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

    @_xfail
    def test_modules_start_enabled_by_default(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        for module in vm.modules:
            assert module.enabled is True, (
                f"module '{module.module_id}' must start enabled by default"
            )

    @_xfail
    def test_toggle_module_flips_enabled_state(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.toggle_module("conv_history")
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].enabled is False, (
            "toggle_module must disable an enabled module"
        )

        vm.toggle_module("conv_history")
        assert by_id["conv_history"].enabled is True, (
            "a second toggle_module must re-enable the module"
        )


# ---------------------------------------------------------------------------
# C. Signal on state change
# ---------------------------------------------------------------------------

class TestPedalboardSignals:

    @_xfail
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
        assert emitted[0][1] is False, (
            "module_state_changed must carry the new enabled state as the second argument"
        )


# ---------------------------------------------------------------------------
# D & E. LED derives from `functional`, not from `enabled`
# ---------------------------------------------------------------------------

class TestPedalboardLed:

    @_xfail
    def test_led_on_when_module_is_functional(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.set_module_functional("conv_history", True)
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_on is True, (
            "led_on must be True when the module is functional"
        )

    @_xfail
    def test_led_off_when_module_is_not_functional(self):
        from signal_chain.viewmodels.pedalboard import PedalboardViewModel

        vm = PedalboardViewModel()
        vm.set_module_functional("conv_history", False)
        by_id = {m.module_id: m for m in vm.modules}
        assert by_id["conv_history"].led_on is False, (
            "led_on must be False when the module is not functional, "
            "even if the module is enabled"
        )
