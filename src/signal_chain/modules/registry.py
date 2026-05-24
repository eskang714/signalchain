from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class ModuleState(Enum):
    INVALID = auto()
    RUNNABLE_UNVERIFIED = auto()
    VERIFIED = auto()


@dataclass
class ModuleRecord:
    name: str
    state: ModuleState
    is_global: bool
    enabled: bool
    can_enable: bool
    error_message: str = ""


class ModuleRegistry:
    def __init__(
        self,
        user_dir: Path,
        global_dir: Path | None = None,
    ) -> None:
        self._user_dir = user_dir
        self._global_dir = global_dir
        self._disabled_user_modules: set[str] = set()

    def scan(self) -> list[ModuleRecord]:
        records: list[ModuleRecord] = []
        global_names: set[str] = set()

        if self._global_dir is not None and self._global_dir.exists():
            for entry in sorted(self._global_dir.iterdir()):
                if entry.is_dir():
                    record = self._scan_global_module(entry)
                    records.append(record)
                    if record.state != ModuleState.INVALID:
                        global_names.add(record.name)

        if self._user_dir.exists():
            for entry in sorted(self._user_dir.iterdir()):
                if entry.is_dir():
                    records.append(self._scan_user_module(entry, global_names))

        return records

    def disable(self, name: str) -> None:
        if self._is_global_name(name):
            return
        self._disabled_user_modules.add(name)

    def _is_global_name(self, name: str) -> bool:
        if self._global_dir is None or not self._global_dir.exists():
            return False
        for entry in self._global_dir.iterdir():
            if entry.is_dir():
                n, _ = self._read_manifest_name(entry)
                if n == name:
                    return True
        return False

    def _scan_global_module(self, path: Path) -> ModuleRecord:
        name, error = self._read_manifest_name(path)
        if name is None:
            return ModuleRecord(
                name=path.name,
                state=ModuleState.INVALID,
                is_global=True,
                enabled=False,
                can_enable=False,
                error_message=error or "missing or malformed module.json",
            )
        return ModuleRecord(
            name=name,
            state=ModuleState.RUNNABLE_UNVERIFIED,
            is_global=True,
            enabled=True,
            can_enable=False,
        )

    def _scan_user_module(self, path: Path, global_names: set[str]) -> ModuleRecord:
        name, error = self._read_manifest_name(path)
        if name is None:
            return ModuleRecord(
                name=path.name,
                state=ModuleState.INVALID,
                is_global=False,
                enabled=False,
                can_enable=False,
                error_message=error or "missing or malformed module.json",
            )

        if name in global_names:
            return ModuleRecord(
                name=name,
                state=ModuleState.INVALID,
                is_global=False,
                enabled=False,
                can_enable=False,
                error_message=(
                    f"name '{name}' conflicts with global module '{name}'; "
                    "rename this module to enable it"
                ),
            )

        if not (path / "module.py").exists():
            return ModuleRecord(
                name=name,
                state=ModuleState.INVALID,
                is_global=False,
                enabled=False,
                can_enable=False,
                error_message=f"missing module.py in '{name}'",
            )

        return ModuleRecord(
            name=name,
            state=ModuleState.RUNNABLE_UNVERIFIED,
            is_global=False,
            enabled=name not in self._disabled_user_modules,
            can_enable=True,
        )

    @staticmethod
    def _read_manifest_name(path: Path) -> tuple[str | None, str | None]:
        manifest = path / "module.json"
        if not manifest.exists():
            return None, f"missing module.json in '{path.name}'"
        try:
            data = json.loads(manifest.read_text())
            name = data.get("name")
            if not name:
                return None, f"module.json in '{path.name}' has no 'name' field"
            return str(name), None
        except Exception as exc:
            return None, f"malformed module.json in '{path.name}': {exc}"
