"""
Acceptance tests – Startup & Configuration
TC-01: Fresh Install
TC-02: Valid Config
TC-03: Invalid Config – Missing Path
TC-04: Low Disk Space
"""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Skip this entire module until the implementation modules exist.
pytest.importorskip("signal_chain.models.config")
pytest.importorskip("signal_chain.viewmodels.startup")

from signal_chain.viewmodels.startup import StartupViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid_config(tmp_path: Path) -> Path:
    conversation_dir = tmp_path / "conversations"
    output_dir = tmp_path / "output"
    conversation_dir.mkdir()
    output_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "conversation_dir": str(conversation_dir),
                "output_dir": str(output_dir),
            }
        )
    )
    return config_path


@pytest.fixture()
def config_missing_dir(tmp_path: Path) -> Path:
    """Config references a conversations dir that does not exist."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "conversation_dir": str(tmp_path / "conversations"),  # missing
                "output_dir": str(output_dir),
            }
        )
    )
    return config_path


# ---------------------------------------------------------------------------
# TC-01: Fresh Install
# ---------------------------------------------------------------------------

class TestTC01FreshInstall:
    """No config file → wizard_required fires, main UI is blocked, wizard cannot be skipped."""

    def test_wizard_required_fires_when_no_config(self, tmp_path, qtbot):
        config_path = tmp_path / "config.yaml"
        assert not config_path.exists()

        vm = StartupViewModel()
        wizard_fired = []
        vm.wizard_required.connect(lambda: wizard_fired.append(True))

        vm.startup(config_path)

        assert wizard_fired, "wizard_required must be emitted when no config file exists"

    def test_main_ready_not_fired_before_wizard_completes(self, tmp_path, qtbot):
        vm = StartupViewModel()
        main_fired = []
        vm.main_ready.connect(lambda: main_fired.append(True))

        vm.startup(tmp_path / "config.yaml")

        assert not main_fired, "main_ready must not fire before the wizard is completed"
        assert not vm.is_main_ready

    def test_wizard_cannot_be_skipped_on_fresh_install(self, tmp_path, qtbot):
        vm = StartupViewModel()
        vm.startup(tmp_path / "config.yaml")

        assert not vm.can_skip_wizard(), (
            "Wizard must not be skippable when no configuration exists"
        )


# ---------------------------------------------------------------------------
# TC-02: Valid Config
# ---------------------------------------------------------------------------

class TestTC02ValidConfig:
    """Valid config.yaml → main UI loads, no wizard, modules discovered, connection state set."""

    def test_main_ready_fires_for_valid_config(self, valid_config, qtbot):
        vm = StartupViewModel()
        main_fired = []
        wizard_fired = []
        vm.main_ready.connect(lambda: main_fired.append(True))
        vm.wizard_required.connect(lambda: wizard_fired.append(True))

        vm.startup(valid_config)

        assert main_fired, "main_ready must fire when config is valid"
        assert not wizard_fired, "wizard_required must not fire when config is valid"

    def test_discovered_modules_populated(self, valid_config, qtbot):
        vm = StartupViewModel()
        vm.startup(valid_config)

        assert vm.discovered_modules is not None, (
            "discovered_modules must be set after successful startup"
        )

    def test_connection_state_available_after_startup(self, valid_config, qtbot):
        vm = StartupViewModel()
        vm.startup(valid_config)

        assert vm.connection_state is not None, (
            "connection_state must be set after successful startup"
        )


# ---------------------------------------------------------------------------
# TC-03: Invalid Config – Missing Path
# ---------------------------------------------------------------------------

class TestTC03InvalidConfigMissingPath:
    """Config references a non-existent directory → fix dialog, main UI blocked."""

    def test_fix_dialog_fires_when_path_missing(self, config_missing_dir, qtbot):
        vm = StartupViewModel()
        fix_fired = []
        vm.fix_dialog_required.connect(lambda: fix_fired.append(True))

        vm.startup(config_missing_dir)

        assert fix_fired, (
            "fix_dialog_required must fire when a configured path does not exist"
        )

    def test_main_ready_not_fired_while_fix_pending(self, config_missing_dir, qtbot):
        vm = StartupViewModel()
        main_fired = []
        vm.main_ready.connect(lambda: main_fired.append(True))

        vm.startup(config_missing_dir)

        assert not main_fired, "main_ready must not fire while a fix is still pending"

    def test_missing_paths_are_reported(self, config_missing_dir, qtbot):
        vm = StartupViewModel()
        vm.startup(config_missing_dir)

        assert vm.missing_paths, "missing_paths must be non-empty before fix_dialog_required"
        assert any("conversations" in str(p) for p in vm.missing_paths), (
            "missing_paths must identify the specific missing directory"
        )

    def test_create_missing_directories_unblocks_startup(self, config_missing_dir, qtbot):
        vm = StartupViewModel()
        main_fired = []
        vm.main_ready.connect(lambda: main_fired.append(True))

        vm.startup(config_missing_dir)
        vm.create_missing_directories()

        assert main_fired, (
            "main_ready must fire after create_missing_directories() is called"
        )
        assert all(Path(p).exists() for p in vm.missing_paths), (
            "create_missing_directories() must physically create the reported paths"
        )


# ---------------------------------------------------------------------------
# TC-04: Low Disk Space
# ---------------------------------------------------------------------------

class TestTC04LowDiskSpace:
    """< 100 MB free → disk_warning fires (with free MB), but app still starts."""

    _LOW_FREE_BYTES = 50 * 1024 * 1024    # 50 MB
    _HIGH_FREE_BYTES = 500 * 1024 * 1024  # 500 MB

    def test_disk_warning_fires_when_space_below_100mb(self, valid_config, qtbot):
        vm = StartupViewModel()
        warnings: list[int] = []
        vm.disk_warning.connect(lambda free_mb: warnings.append(free_mb))

        with patch("shutil.disk_usage", return_value=(10**9, 9 * 10**8, self._LOW_FREE_BYTES)):
            vm.startup(valid_config)

        assert warnings, "disk_warning must fire when free space is below 100 MB"
        assert warnings[0] < 100, "disk_warning must carry the free-space value in MB"

    def test_app_still_starts_despite_low_disk(self, valid_config, qtbot):
        vm = StartupViewModel()
        main_fired = []
        vm.main_ready.connect(lambda: main_fired.append(True))

        with patch("shutil.disk_usage", return_value=(10**9, 9 * 10**8, self._LOW_FREE_BYTES)):
            vm.startup(valid_config)

        assert main_fired, "main_ready must still fire when disk space is low (warning, not block)"

    def test_no_disk_warning_when_space_sufficient(self, valid_config, qtbot):
        vm = StartupViewModel()
        warnings: list[int] = []
        vm.disk_warning.connect(lambda free_mb: warnings.append(free_mb))

        with patch("shutil.disk_usage", return_value=(10**9, 5 * 10**8, self._HIGH_FREE_BYTES)):
            vm.startup(valid_config)

        assert not warnings, "disk_warning must not fire when free space is >= 100 MB"
