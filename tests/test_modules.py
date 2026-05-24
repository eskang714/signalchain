"""
Acceptance tests – Module System
TC-05: Valid Module Discovery
TC-06: Invalid Module Discovery
TC-07: Module Refresh Without Restart
TC-08: Module Name Collision
TC-09: Module Isolation Enforcement
TC-10: Global Module Cannot Be Disabled

Target modules (not yet implemented):
  signal_chain.modules.registry.ModuleRegistry
  signal_chain.modules.registry.ModuleRecord
  signal_chain.modules.registry.ModuleState
  signal_chain.modules.runner.ModuleRunner

Filesystem contract for a valid user module directory:
  modules/user/<module_name>/
    module.json  — {"name": "<name>", "description": "..."}
    module.py    — contains a class implementing BaseModule interface

Module states:
  ModuleState.INVALID             — structural failure, cannot be enabled
  ModuleState.RUNNABLE_UNVERIFIED — valid structure, user decides risk
  ModuleState.VERIFIED            — passed AI security check (requires external call)

FLAG TC-09 (mechanism is design-dependent):
  Problem: "user module attempts to call functions from another user module directly"
  is ambiguous about HOW the direct call is made (Python import, shared reference,
  or via the runner registry API).
  Options:
    A) Context-variable approach: ModuleRunner tracks the currently-executing user
       module and blocks any re-entrant execute() call targeting another user module.
       Test can be written now — assumes runner.execute() accepts a caller_module kwarg.
    B) Proxy-injection approach: modules receive wrapped proxies; the proxy checks
       the call stack and raises ModuleIsolationError.  Testable once proxies exist.
    C) Subprocess sandbox: user modules run in a subprocess with no shared object
       references. Inter-process call attempts simply fail with a communication error.
  Recommendation: Option A for V1 (simplest, consistent with single-process design).
  Tests below implement Option A and will need updating if B or C is chosen.
  Waiting for human decision.
"""
import json
from pathlib import Path

import pytest

_xfail = pytest.mark.xfail(
    reason="module system not yet implemented - TDD red phase",
    strict=True,
)

# Names that are always reserved for global modules.
_GLOBAL_NAMES = {
    "conversation_history",
    "file_system",
    "markdown_output",
    "web_access",
    "connected_accounts",
    "time",
}


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def _write_user_module(
    user_dir: Path,
    name: str,
    *,
    has_json: bool = True,
    has_py: bool = True,
) -> Path:
    """Create a minimal user-module directory structure under user_dir/."""
    mod_dir = user_dir / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    if has_json:
        (mod_dir / "module.json").write_text(
            json.dumps({"name": name, "description": f"{name} test module"})
        )
    if has_py:
        (mod_dir / "module.py").write_text(
            "class Module:\n"
            "    def initialize(self): pass\n"
            "    def execute(self, fn, params): return {}\n"
            "    def shutdown(self): pass\n"
            "    def get_functions(self): return []\n"
            "    def validate_parameters(self, fn, params): return True\n"
        )
    return mod_dir


def _write_global_module(global_dir: Path, name: str) -> Path:
    """Create a minimal global-module directory structure under global_dir/."""
    mod_dir = global_dir / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "module.json").write_text(
        json.dumps({"name": name, "description": f"{name} global module"})
    )
    (mod_dir / "module.py").write_text("class Module: pass\n")
    return mod_dir


# ---------------------------------------------------------------------------
# TC-05: Valid Module Discovery
# ---------------------------------------------------------------------------

class TestTC05ValidModuleDiscovery:
    """A folder with module.json + module.py → RUNNABLE_UNVERIFIED, can be enabled."""

    @_xfail
    def test_valid_module_gets_runnable_unverified_state(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry, ModuleState

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "my_tool")

        registry = ModuleRegistry(user_dir=user_dir)
        records = registry.scan()

        my_tool = next((r for r in records if r.name == "my_tool"), None)
        assert my_tool is not None, "Valid module must appear in scan results"
        assert my_tool.state == ModuleState.RUNNABLE_UNVERIFIED, (
            "A structurally valid user module must get state RUNNABLE_UNVERIFIED"
        )

    @_xfail
    def test_valid_module_can_be_enabled(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "my_tool")

        registry = ModuleRegistry(user_dir=user_dir)
        records = registry.scan()

        my_tool = next(r for r in records if r.name == "my_tool")
        assert my_tool.can_enable is True, (
            "A RUNNABLE_UNVERIFIED module must have can_enable=True so the user can toggle it"
        )

    @_xfail
    def test_valid_module_name_read_from_manifest(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "weather_lookup")

        registry = ModuleRegistry(user_dir=user_dir)
        names = [r.name for r in registry.scan()]

        assert "weather_lookup" in names, (
            "Module name must be read from module.json and appear in the registry"
        )


# ---------------------------------------------------------------------------
# TC-06: Invalid Module Discovery
# ---------------------------------------------------------------------------

class TestTC06InvalidModuleDiscovery:
    """A folder missing module.py → INVALID, toggle disabled, specific error message."""

    @_xfail
    def test_module_missing_py_gets_invalid_state(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry, ModuleState

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "broken_tool", has_py=False)  # no module.py

        registry = ModuleRegistry(user_dir=user_dir)
        records = registry.scan()

        broken = next((r for r in records if r.name == "broken_tool"), None)
        assert broken is not None, "Invalid module must still appear in scan results"
        assert broken.state == ModuleState.INVALID, (
            "A module missing module.py must receive state INVALID"
        )

    @_xfail
    def test_invalid_module_cannot_be_enabled(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "broken_tool", has_py=False)

        registry = ModuleRegistry(user_dir=user_dir)
        broken = next(r for r in registry.scan() if r.name == "broken_tool")

        assert broken.can_enable is False, (
            "An INVALID module must have can_enable=False — the toggle must be disabled"
        )

    @_xfail
    def test_invalid_module_error_names_missing_file(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "broken_tool", has_py=False)

        registry = ModuleRegistry(user_dir=user_dir)
        broken = next(r for r in registry.scan() if r.name == "broken_tool")

        assert broken.error_message, "INVALID module must have a non-empty error_message"
        assert "module.py" in broken.error_message.lower(), (
            "error_message must name the specific missing file so the user knows what to fix"
        )


# ---------------------------------------------------------------------------
# TC-07: Module Refresh Without Restart
# ---------------------------------------------------------------------------

class TestTC07ModuleRefreshWithoutRestart:
    """A fresh scan() after adding a module directory picks it up without restarting."""

    @_xfail
    def test_new_module_appears_after_rescan(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "existing_module")

        registry = ModuleRegistry(user_dir=user_dir)
        first_scan = registry.scan()
        assert len(first_scan) == 1

        # Simulate user dropping a new module folder into user_dir
        _write_user_module(user_dir, "new_module")

        second_scan = registry.scan()
        names = [r.name for r in second_scan]

        assert "new_module" in names, (
            "A module added after the initial scan must appear in a subsequent scan "
            "without restarting the application"
        )
        assert "existing_module" in names, (
            "Existing modules must still be present after a re-scan"
        )

    @_xfail
    def test_removed_module_disappears_after_rescan(self, tmp_path):
        import shutil
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        _write_user_module(user_dir, "to_be_removed")
        _write_user_module(user_dir, "stays")

        registry = ModuleRegistry(user_dir=user_dir)
        assert len(registry.scan()) == 2

        shutil.rmtree(user_dir / "to_be_removed")

        names = [r.name for r in registry.scan()]
        assert "to_be_removed" not in names, (
            "A module folder removed from disk must disappear on the next scan"
        )
        assert "stays" in names


# ---------------------------------------------------------------------------
# TC-08: Module Name Collision
# ---------------------------------------------------------------------------

class TestTC08ModuleNameCollision:
    """User module with the same name as a global module is rejected or renamed;
    global is unaffected; user receives a clear explanation."""

    @_xfail
    def test_global_module_unaffected_by_collision(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry, ModuleState

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()

        _write_global_module(global_dir, "file_system")
        _write_user_module(user_dir, "file_system")  # name collision

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        records = registry.scan()

        global_record = next(
            (r for r in records if r.name == "file_system" and r.is_global), None
        )
        assert global_record is not None, (
            "The global file_system module must still appear after a name collision"
        )
        assert global_record.state != ModuleState.INVALID, (
            "The global module must not be invalidated by a conflicting user module"
        )

    @_xfail
    def test_colliding_user_module_is_rejected_or_renamed(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry, ModuleState

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()

        _write_global_module(global_dir, "file_system")
        _write_user_module(user_dir, "file_system")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        records = registry.scan()

        user_records = [r for r in records if not r.is_global]
        # Either the user module was rejected (INVALID with collision message)
        # or it was auto-renamed (its name != "file_system")
        for r in user_records:
            if r.name == "file_system":
                assert r.state == ModuleState.INVALID, (
                    "A user module whose name collides with a global must be INVALID"
                )
                break
        else:
            # No user record named "file_system" → it was renamed; that's acceptable too
            pass

    @_xfail
    def test_collision_explanation_is_provided(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry, ModuleState

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()

        _write_global_module(global_dir, "file_system")
        _write_user_module(user_dir, "file_system")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        records = registry.scan()

        # Find either an INVALID user record for "file_system" or a renamed record
        user_file_system = next(
            (r for r in records if not r.is_global and "file_system" in r.name),
            None,
        )
        if user_file_system is not None and user_file_system.state == ModuleState.INVALID:
            assert user_file_system.error_message, (
                "Collision must produce a non-empty error_message explaining the conflict"
            )
            assert "file_system" in user_file_system.error_message.lower(), (
                "error_message must name the conflicting global module"
            )


# ---------------------------------------------------------------------------
# TC-09: Module Isolation Enforcement
# ---------------------------------------------------------------------------

class TestTC09ModuleIsolationEnforcement:
    """Direct user-to-user module calls are blocked; caller receives an error;
    target module is unaffected.

    See module-level FLAG TC-09 for the design decision this test assumes.
    Tests target Option A: ModuleRunner.execute() with a caller_module kwarg.
    """

    @_xfail
    def test_user_module_calling_another_user_module_is_blocked(self):
        from signal_chain.modules.runner import ModuleIsolationError, ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("module_a")
        runner.register_user_module("module_b")

        # module_a tries to directly call module_b through the runner
        with pytest.raises(ModuleIsolationError):
            runner.execute(
                module_name="module_b",
                function_name="any_function",
                parameters={},
                caller_module="module_a",  # user module calling another user module
            )

    @_xfail
    def test_target_module_unaffected_after_blocked_call(self):
        from signal_chain.modules.runner import ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("module_a")
        runner.register_user_module("module_b")

        # The blocked call (swallow isolation error so test can continue)
        try:
            runner.execute("module_b", "any_function", {}, caller_module="module_a")
        except Exception:
            pass

        # Target module must still work when called legitimately (no caller_module)
        result = runner.execute("module_b", "any_function", {})
        assert result is not None, (
            "module_b must still execute normally after a blocked cross-module call"
        )

    @_xfail
    def test_caller_receives_error_not_result(self):
        from signal_chain.modules.runner import ModuleIsolationError, ModuleRunner

        runner = ModuleRunner()
        runner.register_user_module("module_a")
        runner.register_user_module("module_b")

        error_raised = False
        try:
            runner.execute("module_b", "any_function", {}, caller_module="module_a")
        except ModuleIsolationError:
            error_raised = True

        assert error_raised, (
            "The calling module must receive a ModuleIsolationError, not a successful result"
        )


# ---------------------------------------------------------------------------
# TC-10: Global Module Cannot Be Disabled
# ---------------------------------------------------------------------------

class TestTC10GlobalModuleCannotBeDisabled:
    """conversation_history is always present, always enabled, has no disable toggle."""

    @_xfail
    def test_conversation_history_appears_in_scan_results(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()
        _write_global_module(global_dir, "conversation_history")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        names = [r.name for r in registry.scan()]

        assert "conversation_history" in names, (
            "conversation_history must always appear in the module list"
        )

    @_xfail
    def test_global_module_has_no_enable_toggle(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()
        _write_global_module(global_dir, "conversation_history")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        conv_hist = next(
            r for r in registry.scan() if r.name == "conversation_history"
        )

        assert conv_hist.is_global is True
        assert conv_hist.can_enable is False, (
            "Global modules must not have a disable toggle (can_enable must be False)"
        )

    @_xfail
    def test_global_module_always_enabled(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()
        _write_global_module(global_dir, "conversation_history")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        conv_hist = next(
            r for r in registry.scan() if r.name == "conversation_history"
        )

        assert conv_hist.enabled is True, (
            "conversation_history must always be enabled in every conversation"
        )

    @_xfail
    def test_global_module_stays_enabled_after_disable_attempt(self, tmp_path):
        from signal_chain.modules.registry import ModuleRegistry

        user_dir = tmp_path / "user"
        global_dir = tmp_path / "global"
        user_dir.mkdir()
        global_dir.mkdir()
        _write_global_module(global_dir, "conversation_history")

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        registry.disable("conversation_history")  # attempt to disable

        conv_hist = next(
            r for r in registry.scan() if r.name == "conversation_history"
        )
        assert conv_hist.enabled is True, (
            "Calling disable() on a global module must have no effect"
        )
