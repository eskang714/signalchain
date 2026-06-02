# signal-chain - CLAUDE.md
# Shared context for all Claude Code sessions.
# Place this file in project root.

## What This Project Is
Desktop LLM chat application. Supports Claude, Ollama, OpenRouter, Groq, and Gemini (local models via Ollama).
Role: Mediator between user and existing LLM services. Not a replacement for any service.
Philosophy: User owns data, user controls resources, no artificial limits, honest about limitations.

## Architecture
Pattern: MVVM (Model-View-ViewModel)
UI Framework: PyQt6
Threading: QThread per conversation (non-blocking UI, multiple simultaneous generations)
Language: Python 3.11+

```
src/signal_chain/
├── models/        # Data layer - conversations, messages, config
├── viewmodels/    # Business logic + state, exposes signals to views
├── views/         # PyQt6 UI components only, no logic
├── providers/     # Claude, Ollama, OpenRouter, Groq, Gemini
├── modules/       # Two-tier plugin system
│   ├── global/    # App-maintained: conversation_history, markdown_output, connected_accounts, web_access, file_access, clock
│   └── user/      # Community-maintained, isolated
├── resources/     # Resource management (RAM, GPU, CPU)
└── utils/         # Shared helpers
```

## MVVM Rules (enforce strictly)
- Views contain zero business logic
- ViewModels expose PyQt signals, never import from views
- Models are pure data, no UI imports
- Providers implement BaseProvider interface, nothing else
- Modules implement BaseModule interface, nothing else

## Key Interfaces

### BaseProvider
```python
class BaseProvider(ABC):
    def list_models(self) -> List[ModelInfo]: ...
    def load_model(self, model_id: str) -> None: ...
    def generate_stream(self, messages: List[Message], config: GenerationConfig) -> Iterator[str]: ...
    def validate_config(self) -> bool: ...
```

### BaseModule
```python
class BaseModule(ABC):
    def initialize(self) -> None: ...
    def execute(self, function_name: str, parameters: dict, caller_module: str | None = None) -> dict: ...
    def shutdown(self) -> None: ...
    def get_functions(self) -> List[FunctionSchema]: ...
```

## Critical Behaviors (must pass acceptance tests)
- Multiple conversations generate simultaneously without blocking UI
- Worker thread crash must not affect UI thread or other conversations
- Model blocked by architecture incompatibility returns clear error, does not load
- Insufficient RAM shows tiered warning (optimal/recommended/swap/blocked)
- API keys stored in OS keychain only, never in config files or logs
- Corrupted conversation file is skipped, app continues loading others
- Module execution timeout: 30 seconds, then terminate cleanly

## Tooling
- Package manager: uv
- Linter/formatter: ruff
- Tests: pytest
- CI: GitHub Actions (.github/workflows/ci.yml)

## Commit & Attribution Convention
- Commits use conventional commit format (feat, fix, test, docs, refactor, chore, ci)
- Do NOT add Co-Authored-By trailers to commit messages
- Attribution for AI-assisted commits goes in the PR comment, not the commit body
- Squash merge uses the PR title (conventional format) as the commit title
- One ticket, one task, one branch
- Keep PR titles (commit subjects) under 72 characters — GitHub truncates longer
titles during squash merge, splitting content into the extended description
- Always include "Closes #XX" in the squash commit extended description (not just
the PR body) — the PR body is replaced on squash; only the commit body persists
to trigger GitHub's auto-close

## What to Flag Rather Than Decide
If you encounter an architectural question not answered here, stop and flag it.
Do not make unilateral architectural decisions.
Implementation decisions (how to write a function) are yours.
Design decisions (what the system does) come back to the human.

## Reference Documents
- Full planning brief: Signal_Chain_Project_Brief.md
- Acceptance tests: Signal_Chain_Test_Cases.md
