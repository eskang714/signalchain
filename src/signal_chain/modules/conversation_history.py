from __future__ import annotations

from dataclasses import dataclass

from signal_chain.modules.base import BaseModule


@dataclass
class FunctionSchema:
    name: str
    description: str = ""


class ConversationHistoryModule(BaseModule):
    """Always-on global module — in-memory conversation history store."""

    def initialize(self) -> None:
        self._history: list[dict] = []

    def execute(
        self,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        if function_name == "add_message":
            return self._add_message(parameters)
        if function_name == "get_history":
            return {"history": list(self._history)}
        if function_name == "clear_history":
            self._history.clear()
            return {"cleared": True}
        return {"error": f"Unknown function: {function_name}"}

    def shutdown(self) -> None:
        self._history.clear()

    def get_functions(self) -> list:
        return [
            FunctionSchema("add_message", "Append a message to the conversation history"),
            FunctionSchema("get_history", "Return the full conversation history"),
            FunctionSchema("clear_history", "Clear all messages from the history"),
        ]

    def validate_parameters(self, function_name: str, parameters: dict) -> bool:
        return isinstance(parameters, dict)

    def _add_message(self, params: dict) -> dict:
        role = params.get("role", "")
        content = params.get("content", "")
        self._history.append({"role": role, "content": content})
        return {"added": True}
