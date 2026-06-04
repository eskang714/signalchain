# Architecture Decision Records (ADRs)

Decision log for signal-chain project architecture and significant technical choices.

---

## ADR-006: Qt/EGL Library Dependencies in GitHub Actions CI

**Status:** Accepted

**Date:** May 2026

### Context
PyQt6 applications require Qt runtime libraries to function, even in headless (GUI-less) environments. GitHub Actions runners on `ubuntu-latest` do not include these libraries by default, causing import failures when pytest attempts to load PyQt6 modules.

The initial CI workflow failed with:
```
libEGL.so.1: cannot open shared object file: No such file or directory
```

This prevented any PyQt6-dependent tests from running in the automated CI pipeline.

### Decision
Add system-level Qt/EGL library dependencies to the CI workflow via `apt-get install`. Specifically:
- `libegl1` - EGL library
- `libgl1` - OpenGL library
- `libxkbcommon0` - Keyboard input handling
- `libdbus-1-3` - D-Bus daemon (Qt dependency)

Configure Qt to run in offscreen mode using the `QT_QPA_PLATFORM=offscreen` environment variable, which tells Qt to render without accessing a display server.

### Consequences
- **Positive:** CI workflow now successfully imports and tests PyQt6 code in headless runners. Tests that exercise GUI components can run without requiring display virtualization (xvfb).
- **Positive:** Minimal overhead—library installation adds ~2-3 seconds to CI runtime.
- **Negative:** CI environment is no longer a "bare" Python environment; it includes Qt system dependencies that would not be present in minimal deployment targets.
- **Negative:** If Qt library versions in the runner diverge from development environments, compatibility issues may arise.

### Alternatives Considered

1. **Use xvfb (Virtual Framebuffer)**
   - Install and configure xvfb to provide a virtual display
   - More complex setup, higher resource usage
   - Better isolation from host system libraries
   - **Rejected:** Unnecessary complexity for headless testing

2. **Mock PyQt6 in Tests**
   - Mock Qt components during testing, test only business logic
   - Reduces Qt library dependency in CI
   - **Rejected:** We need to verify actual PyQt6 integration, not just business logic

3. **Skip GUI Tests in CI**
   - Mark GUI tests with `@pytest.mark.skip` in CI
   - Reduces CI requirements
   - **Rejected:** Reduces confidence in GUI code quality; defeats purpose of CI

### Related Decisions
- Follows from the choice to use PyQt6 as the UI framework
- Informs the CI/CD strategy for handling framework-specific testing requirements

---

## ADR-007: Pedal Module Naming Convention

**Status:** Accepted

**Date:** June 2026

### Context
Pedalboard pedal modules shared no naming marker. `MarkdownOutputModule`, `ConversationHistoryModule`, and `ConnectedAccountsModule` were indistinguishable in code from module-system infrastructure (`base`, `registry`, `runner`) and from the egress `NetworkGateway`. This ambiguity surfaced concretely while refreshing customer-facing docs: "Connected Accounts" had drifted between two distinct things — the provider selector a user pictures and the credential-vault module that actually wears the name — and the mismatch went unnoticed precisely because nothing in the naming signalled what was or wasn't a pedal.

Beyond disambiguation, the project's identity is the guitar signal chain: pedals patched into a chain. The naming should carry that identity, not read as generic Python.

### Decision
Name every pedalboard pedal module with the `pedal_<camelCaseName>` convention, extending through `_<subModuleName>` segments for nested units:

- class: `pedal_<camelCaseName>` (e.g. `pedal_markdownOutput`)
- file: `pedal_<camelCaseName>.py` — matching the class, so the unit reads identically in the import path and the symbol
- sub-modules append further segments: `pedal_markdownOutput_tableFormatter`

| Before | After |
|--------|-------|
| `MarkdownOutputModule` | `pedal_markdownOutput` |
| `ConversationHistoryModule` | `pedal_conversationHistory` |
| `ConnectedAccountsModule` | `pedal_connectedAccounts` |

The `pedal_` prefix is reserved for user-facing pedals. Module-system infrastructure (`base`, `registry`, `runner`) and the egress `NetworkGateway` do not take it.

The lowercase, unpolished form is a deliberate branding choice: each module reads as an unpatched pedal unit waiting to be patched into the signal chain, reinforcing the pedalboard identity — not merely a fix for the naming-drift that prompted it.

### Consequences
- **Positive:** Pedals are unmistakable at a glance and visually distinct from infrastructure, closing the class of naming-drift that surfaced the Connected Accounts confusion.
- **Positive:** Future pedals (Web Access, File Access, Clock) get an unambiguous pattern, and nested sub-modules have a defined form.
- **Positive:** The naming carries the product's signal-chain identity.
- **Negative:** Deliberate PEP8 deviation — class names are conventionally CapWords and module files snake_case. `ruff`'s current config doesn't select the `N` (pep8-naming) rules, so the suite stays green; if they're ever enabled, pedal modules will need `N801`/`N999` ignores.
- **Negative:** Applying the convention requires a rename touching every reference (imports, registry, tests, type hints) — done as a separate chore, not silently.

### Alternatives Considered

1. **`Pedal<Name>` (PascalCase, PEP8-compliant)**
   - Same `Pedal` marker, conventional casing, no lint concern.
   - **Rejected:** Reads as a finished, generic class; loses the unpatched-unit feel that carries the branding.

2. **Keep the existing `<Name>Module` suffix**
   - No churn.
   - **Rejected:** `Module` is shared by pedals and infrastructure alike, so it doesn't distinguish pedals — the exact gap that allowed the drift.

3. **Function-honest names without a pedal marker** (`ProviderManager`, `CredentialVault`)
   - Names each unit for what it does.
   - **Rejected:** No systematic "this is a pedal" marker, and carries no brand identity.

### Related Decisions
- Applied by a separate `chore` ticket that performs the rename across the codebase.
- Adjacent to the planned extraction of the provider-selector backend out of `app.py` (a distinct unit, not a pedal).

---