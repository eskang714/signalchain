from __future__ import annotations

import urllib.request

from signal_chain.modules.base import BaseModule
from signal_chain.modules.network_gateway import _PermitGateway


class pedal_webAccess(BaseModule):
    """Pedal module — HTTP fetch gated by the web:fetch scope.

    Gateway is checked before any outbound request. NetworkBlockedError
    propagates to the caller unchanged if the web_access pedal is disabled.
    """

    def __init__(self, gateway: _PermitGateway = _PermitGateway()) -> None:
        self._gateway = gateway

    def initialize(self) -> None:
        pass

    def execute(
        self,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        if function_name == "fetch":
            return self._fetch(parameters)
        return {"error": f"Unknown function: {function_name}"}

    def shutdown(self) -> None:
        pass

    def get_functions(self) -> list:
        from dataclasses import dataclass

        @dataclass
        class FunctionSchema:
            name: str
            description: str = ""

        return [
            FunctionSchema("fetch", "Fetch a URL and return its content as a string"),
        ]

    def validate_parameters(self, function_name: str, parameters: dict) -> bool:
        return isinstance(parameters, dict)

    def _fetch(self, params: dict) -> dict:
        url = params.get("url", "")
        self._gateway.authorize("web:fetch")
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8", errors="replace")
        return {"content": content, "url": url}
