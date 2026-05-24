from __future__ import annotations


class ModuleIsolationError(Exception):
    """Raised when a user module attempts to call another user module directly."""


class ModuleRunner:
    def __init__(self) -> None:
        self._user_modules: set[str] = set()

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
