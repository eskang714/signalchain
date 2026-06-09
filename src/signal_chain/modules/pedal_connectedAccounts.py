from __future__ import annotations

from dataclasses import dataclass

import keyring

from signal_chain.modules.base import BaseModule

_KEYRING_SERVICE = "signalchain"

# Demo tokens pre-seeded so the module can be exercised without a real OAuth flow.
# Real tokens written via store_token replace these.
_DEMO_TOKENS: dict[str, str] = {
    "google": "demo_google_oauth_token",
    "github": "demo_github_oauth_token",
}


@dataclass
class FunctionSchema:
    name: str
    description: str = ""


class pedal_connectedAccounts(BaseModule):
    """Always-on global module — manages OAuth tokens and API keys via keyring.

    Auth passthrough only: retrieves and stores credentials, never calls external APIs.
    """

    def initialize(self) -> None:
        self._tokens: dict[str, str] = dict(_DEMO_TOKENS)
        for service, placeholder in _DEMO_TOKENS.items():
            try:
                real = keyring.get_password(_KEYRING_SERVICE, f"oauth_{service}")
                if real:
                    self._tokens[service] = real
            except Exception:
                pass

    def execute(
        self,
        function_name: str,
        parameters: dict,
        caller_module: str | None = None,
    ) -> dict:
        if function_name == "get_token":
            return self._get_token(parameters)
        if function_name == "store_token":
            return self._store_token(parameters)
        if function_name == "remove_token":
            return self._remove_token(parameters)
        if function_name == "list_providers":
            return {"providers": list(self._tokens.keys())}
        return {"error": f"Unknown function: {function_name}"}

    def shutdown(self) -> None:
        self._tokens.clear()

    def get_functions(self) -> list:
        return [
            FunctionSchema("get_token", "Retrieve a stored OAuth token for a service"),
            FunctionSchema("store_token", "Store an OAuth token for a service"),
            FunctionSchema("remove_token", "Remove a stored OAuth token for a service"),
            FunctionSchema("list_providers", "List all connected service providers"),
        ]

    def validate_parameters(self, function_name: str, parameters: dict) -> bool:
        return isinstance(parameters, dict)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_token(self, params: dict) -> dict:
        service = params.get("service", "")
        token = self._tokens.get(service)
        return {"token": token, "service": service}

    def _store_token(self, params: dict) -> dict:
        service = params.get("service", "")
        token = params.get("token", "")
        self._tokens[service] = token
        try:
            keyring.set_password(_KEYRING_SERVICE, f"oauth_{service}", token)
        except Exception:
            pass
        return {"service": service, "stored": True}

    def _remove_token(self, params: dict) -> dict:
        service = params.get("service", "")
        self._tokens.pop(service, None)
        return {"service": service, "removed": True}
