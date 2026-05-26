from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from signal_chain.modules.base import BaseModule


@dataclass
class FunctionSchema:
    name: str
    description: str = ""


class MarkdownOutputModule(BaseModule):
    """Always-on global module — writes markdown files verbatim to output_dir."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def initialize(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        if function_name == "write_file":
            return self._write_file(parameters)
        return {"error": f"Unknown function: {function_name}"}

    def shutdown(self) -> None:
        pass

    def get_functions(self) -> list:
        return [
            FunctionSchema("write_file", "Write content verbatim to a .md file in output_dir"),
        ]

    def validate_parameters(self, function_name: str, parameters: dict) -> bool:
        return isinstance(parameters, dict)

    def _write_file(self, params: dict) -> dict:
        filename = params.get("filename", "output.md")
        content = params.get("content", "")
        file_path = self._output_dir / filename
        file_path.write_text(content)
        return {"file_path": str(file_path)}
