from __future__ import annotations

from abc import ABC, abstractmethod


class BaseModule(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def execute(
        self,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict: ...

    @abstractmethod
    def shutdown(self) -> None: ...

    @abstractmethod
    def get_functions(self) -> list: ...

    @abstractmethod
    def validate_parameters(self, function_name: str, parameters: dict) -> bool: ...
