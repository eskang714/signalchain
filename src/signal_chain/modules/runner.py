from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class ModuleIsolationError(Exception):
    """Raised when a user module attempts to call another user module directly."""


class ModuleRunner(QObject):
    module_error = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._user_modules: set[str] = set()
        self._module_instances: dict[str, object] = {}

    def register_user_module(self, name: str) -> None:
        self._user_modules.add(name)

    def execute(
        self,
        module_name: str,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        if (
            caller_module is not None
            and caller_module in self._user_modules
            and module_name in self._user_modules
        ):
            raise ModuleIsolationError(
                f"User module '{caller_module}' is not allowed to call "
                f"user module '{module_name}' directly"
            )
        return {}

    def execute_safe(
        self,
        module_name: str,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        try:
            if (
                caller_module is not None
                and caller_module in self._user_modules
                and module_name in self._user_modules
            ):
                raise ModuleIsolationError(
                    f"User module '{caller_module}' is not allowed to call "
                    f"user module '{module_name}' directly"
                )
            instance = self._module_instances.get(module_name)
            if instance is None:
                raise RuntimeError(
                    f"Module '{module_name}' has no callable implementation"
                )
            return instance.execute(function_name, parameters, caller_module)  # type: ignore[union-attr]
        except ModuleIsolationError:
            raise
        except Exception as exc:
            self.module_error.emit(module_name, str(exc))
            return {"error": str(exc)}
