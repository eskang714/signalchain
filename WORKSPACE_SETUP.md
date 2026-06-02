# Workspace Setup Guide
## signal-chain

---

## Before You Start

Check these prerequisites. If anything is missing, install it before continuing.

```bash
python --version     # need 3.11 or higher
git --version        # need any recent version
code --version       # VS Code
```

If Python is below 3.11, download from python.org directly.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/eskang714/signalchain.git
cd signalchain
```

---

## Step 2: Install uv (Package Manager)

uv replaces pip and virtualenv. One tool handles both.

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:
```bash
uv --version
```

---

## Step 3: Install Dependencies

```bash
uv sync --extra dev
```

This creates a virtual environment and installs everything in pyproject.toml.
You do not need to activate it manually. uv handles this.

Verify:
```bash
uv run python --version
uv run pytest --version
```

---

## Step 4: VS Code Setup

Open the project:
```bash
code .
```

Install these extensions (search in Extensions panel):
```
Python          (Microsoft)
Pylance         (Microsoft)
Ruff            (Astral Software)
GitLens         (GitKraken)
```

When VS Code asks which Python interpreter to use, select the one in `.venv/`.

---

## Step 5: Verify Tests Run

```bash
uv run pytest
```

Expected output on fresh clone: tests collected, most failing (no implementation yet).
This is correct. Failing tests against no code is the right starting state.

---

## Step 6: Verify Linter

```bash
uv run ruff check .
uv run ruff format --check .
```

Fix any issues before writing new code.

---

## Step 7: Verify Git Config

```bash
git config user.name
git config user.email
```

If empty:
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

---

## Daily Workflow

```bash
# Start of day
git pull

# Before committing
uv run ruff check .
uv run pytest

# Commit
git add .
git commit -m "descriptive message of what changed"
git push
```

---

## Folder Reference

```
signalchain/
├── CLAUDE.md                  # Read this first if using Claude Code
├── src/signal_chain/
│   ├── models/                # Data layer
│   ├── viewmodels/            # Business logic + signals
│   ├── views/                 # PyQt6 UI only
│   ├── providers/             # Claude, Ollama, OpenRouter, Groq, Gemini
│   ├── modules/               # Plugin system
│   └── utils/                 # Shared helpers
├── tests/                     # All test files
├── docs/                      # Documentation
├── .github/workflows/         # CI configuration
└── pyproject.toml             # All project config
```

---

## Environment Variables

Copy the example file:
```bash
cp .env.example .env
```

Never commit `.env`. It is in `.gitignore`.

Do not put API keys in `.env` for this project.
API keys are stored in OS keychain via the application.
The `.env` file is for development flags only.

---

## Running the Application

```bash
uv run python -m signal_chain.main
```

---

## Common Issues

**uv command not found:**
Restart terminal after installation.

**PyQt6 import error:**
```bash
uv sync --extra dev
```

**Tests not discovered:**
Confirm test files are named `test_*.py` and functions start with `test_`.

**Ruff errors on commit:**
Run `uv run ruff format .` to auto-fix formatting.
Run `uv run ruff check --fix .` to auto-fix lint issues.

---

## Reference Documents

Read in this order before contributing:

1. `CLAUDE.md` - architecture rules and patterns
2. `Signal_Chain_Project_Brief.md` - full planning and decisions
3. `Signal_Chain_Test_Cases.md` - acceptance criteria

A feature is not done until its acceptance test passes.
