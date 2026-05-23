import shutil
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from signal_chain.models.config import AppConfig

_DISK_WARN_MB = 100


class StartupViewModel(QObject):
    wizard_required = pyqtSignal()
    main_ready = pyqtSignal()
    fix_dialog_required = pyqtSignal()
    disk_warning = pyqtSignal(int)  # free space in MB

    def __init__(self) -> None:
        super().__init__()
        self.is_main_ready: bool = False
        self.discovered_modules: list | None = None
        self.connection_state: str | None = None
        self.missing_paths: list[Path] = []
        self._config: AppConfig | None = None

    def startup(self, config_path: Path) -> None:
        if not config_path.exists():
            self.wizard_required.emit()
            return

        self._config = AppConfig.from_yaml(config_path)
        self._validate_and_start()

    def _validate_and_start(self) -> None:
        assert self._config is not None

        missing = [p for p in self._config.required_dirs() if not p.exists()]
        if missing:
            self.missing_paths = missing
            self.fix_dialog_required.emit()
            return

        free_bytes = shutil.disk_usage(self._config.output_dir).free
        free_mb = free_bytes // (1024 * 1024)
        if free_mb < _DISK_WARN_MB:
            self.disk_warning.emit(free_mb)

        self.discovered_modules = []
        self.connection_state = "disconnected"
        self.is_main_ready = True
        self.main_ready.emit()

    def can_skip_wizard(self) -> bool:
        return self._config is not None

    def create_missing_directories(self) -> None:
        for path in self.missing_paths:
            path.mkdir(parents=True, exist_ok=True)
        # missing_paths intentionally kept so callers can verify paths were created
        self._validate_and_start()
