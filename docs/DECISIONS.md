# Architecture Decision Records (ADRs)

Decision log for signal-chain project architecture and significant technical choices.

---

## ADR-001: Use MVVM Architecture Pattern

**Status:** Accepted

**Date:** May 2026

### Context
Building a PyQt6 desktop application with multiple concurrent conversations. Need pattern that supports reactive UI updates and clear separation.

### Decision
Use MVVM (Model-View-ViewModel) pattern.

### Consequences
- ViewModels use PyQt signals for reactive updates
- Views contain zero business logic
- Models remain pure data
- Slight learning curve if developer used to MVC

### Alternatives Considered
- MVC: Standard but PyQt6's signal/slot system maps better to MVVM
- Clean Architecture: Too much overhead for V1
- Flat structure: Insufficient for multi-conversation complexity

---

## ADR-002: Use uv for Package Management

**Status:** Accepted

**Date:** May 2026

### Context
Need Python package and virtual environment management.

### Decision
Use uv (from Astral).

### Consequences
- Faster install times
- Single tool for packages and environments
- Modern industry trend in 2025-2026
- Some older tutorials assume pip

### Alternatives Considered
- pip + venv: Standard but slower, manual venv activation
- Poetry: Popular but heavier, slower than uv
- pipenv: Falling out of favor

---

## ADR-003: Apache 2.0 License

**Status:** Accepted

**Date:** May 2026

### Context
Need license that allows future commercialization while supporting open source adoption.

### Decision
Apache License 2.0.

### Consequences
- Allows future closed source derivatives
- Patent protection from contributors
- Enterprise-friendly
- Slightly longer license text than MIT

### Alternatives Considered
- MIT: Simpler but lacks patent protection
- GPL: Restricts commercial use too heavily
- BSL: Bait-and-switch perception risk
- Proprietary: Conflicts with portfolio goals

---

## ADR-004: Two-Tier Module System

**Status:** Accepted

**Date:** May 2026

### Context
Need extensible module system without infinite maintenance burden.

### Decision
Global modules (app-maintained) + User modules (community-maintained). User modules isolated from each other.

### Consequences
- Clear ownership: app maintains 6 global modules, community owns rest
- User modules cannot access each other (isolation)
- Module validation has two-phase approach (structural + optional AI security check)

### Alternatives Considered
- Single flat module system: Maintenance scope unbounded
- No user modules: Limits extensibility
- Full sandboxing: Too complex for V1

---

## ADR-005: GitHub as Primary Platform

**Status:** Accepted

**Date:** May 2026

### Context
Need version control, CI/CD, project tracking, and visibility.

### Decision
GitHub for repo, GitHub Actions for CI, GitHub Issues for tickets, GitHub Projects for tracking.

### Consequences
- All tooling in one place
- Public portfolio visibility
- Direct integration with Claude Code via GitHub CLI
- Free for public repos

### Alternatives Considered
- GitLab: Equivalent functionality but less industry visibility
- Bitbucket: Less common in 2025-2026
- Self-hosted: Overhead without benefit for solo dev

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

## ADR-008: Network Gateway Gating Policy

**Status:** Accepted

**Date:** June 2026

### Context
Wiring the generation path through a network gate (#106, "complete mediation") required settling how egress is gated. Three forks had paused that work: whether a module's calls to the user's selected LLM provider are gated or always allowed; what the default gateway should be when no policy is configured; and whether the gate applies to every network path or only some. Saltzer & Schroeder's complete-mediation principle argues every egress should pass one checkpoint — but a checkpoint that blocks the app's own provider, or that defaults to deny and breaks first run, is worse than the problem it solves. The policy had to mediate egress without obstructing the provider traffic the app exists to make.

### Decision
1. **`net:provider` is always granted.** A module's egress to the user's selected LLM provider is permitted unconditionally — the app cannot function if it cannot reach its own provider, so that traffic is never gated.
2. **`_PermitGateway()` is the default (Null Object).** When no gating policy is configured, the gateway is a Null Object that permits all egress. Gating is therefore additive and opt-in: call sites run unchanged, and stricter gateways are introduced without modifying them (Open/Closed).
3. **Gate the generation path only.** The network gate sits on the generation path; the provider probe/health-check path is excluded. Probes run to establish availability before a policy context exists and are not user-driven egress.
4. **`net:provider` scope granularity is a known limitation.** The `net:provider` scope is coarse — it permits provider egress as a whole, not per-host or per-endpoint. Finer granularity is deferred and documented as a limitation rather than silently assumed.

### Consequences
- **Positive:** The generation path has a single mediation point (complete mediation) without blocking the provider traffic the app depends on.
- **Positive:** The Null Object default keeps first-run and unconfigured installs working; gating stays opt-in and extensible.
- **Positive:** Excluding the probe path keeps availability checks simple and policy-free.
- **Negative:** `net:provider` granularity is coarse — a compromised or misbehaving module reaching the provider host cannot be gated more narrowly under the current scope.
- **Negative:** Always-granting provider egress is a deliberate trust assumption about provider traffic that a stricter model might later revisit.
- **Neutral:** The policy unblocks #106; the gate's enforcement code lands there, not in this ADR.

### Alternatives Considered

1. **Gate `net:provider` like any other egress**
   - Subject the provider traffic to the same policy checks.
   - **Rejected:** a misconfiguration or deny-by-default would break the app's core function (reaching its provider); the cost outweighs the marginal control given the coarse scope.

2. **Deny-by-default gateway**
   - Block all egress unless explicitly permitted.
   - **Rejected:** breaks first run and unconfigured installs and contradicts the additive/opt-in model; a Null Object default is safer and OCP-friendly.

3. **Gate every path, including probes**
   - Apply the gate to health-check/probe traffic as well.
   - **Rejected:** probes run before a policy context exists and are not user-driven egress; gating them adds complexity with no security benefit.

### Related Decisions
- Unblocks #106 (Complete Mediation — wire the generation path through the network gate).
- Grounded in Saltzer & Schroeder (1975) complete mediation, the Null Object pattern, and the Open/Closed Principle (SOLID).
- Governs the egress `NetworkGateway` (named as infrastructure, not a pedal, per ADR-007).

---

## ADR-009: Module Organization Scheme and the Writer Pattern

**Status:** Proposed

**Date:** June 2026

### Context

The module layer currently carries two organizational schemes at the same time.

1. **Flat modules.** Top-level files under `src/signal_chain/modules/` — `pedal_markdownOutput.py`, `pedal_conversationHistory.py`, `pedal_webAccess.py`, `pedal_connectedAccounts.py` — each a `BaseModule` subclass. Only one is actually wired: `app.py` imports and instantiates `pedal_markdownOutput` (for export). The other three are referenced nowhere outside their own files — a sweep of the whole package (38 modules) finds no importer — so they are effectively dead code.
2. **A registry / runner plug-in scheme.** `registry.py` (`ModuleRegistry`) scans `modules/global/` and `modules/user/` for module folders, each carrying a `module.json` manifest and a `module.py`, separating global modules (built-in, always enabled) from user modules (custom, enable/disable, gated by an `INVALID` / `RUNNABLE_UNVERIFIED` / `VERIFIED` state machine). `runner.py` (`ModuleRunner`) is the execution half of the same scheme: it dispatches `execute(module_name, function_name, parameters, caller_module)` and enforces isolation — a user module may not directly call another user module (`ModuleIsolationError`) — the runtime seam for the untrusted-module sandbox work.

Both `ModuleRegistry` and `ModuleRunner` are built but not wired in: each is referenced only in its own file, so the composition root reaches neither. The only folder-style module that exists is `modules/global/conversation_history/` — and `conversation_history` also exists as the (dead) flat `pedal_conversationHistory.py`, so the same concept is represented in both schemes. A third disconnect sits on top: the pedalboard UI's six pedals are lightweight `PedalModule` data objects in `PedalboardViewModel` (id + enabled flag + LED), not the `BaseModule` pedal classes and not connected to them.

Markdown handling is fragmented across three places that share no home: display rendering lives inline in `views/conversation_view.py`; fenced-block handling is implicit inside the `markdown`-library call made there; and markdown file export lives in `pedal_markdownOutput` (a `BaseModule` exposing a `write_file` function).

This fragmentation surfaced concretely while building per-message rendering (#129): prose renders correctly when the markdown pedal is on, but a markdown document the model returns inside a fenced block tagged `markdown` is shown as a verbatim code block (which is correct CommonMark) rather than rendered. Inspection of real output revealed a compounding complication: the markdown document itself embeds a code fence — a `markdown`-tagged block wrapping a `python`-tagged block, both using three backticks. Because CommonMark closes a fence at the first run of backticks of equal-or-greater length, the outer block terminates at the inner fence's bare-backtick terminator and everything after it mis-renders. So the rendering decision this ADR assigns an owner must also cope with markdown documents that embed same-length code fences. No single component owns the decision "how is fenced output rendered?"

### Decision Drivers

- **Information hiding / modular decomposition** — Parnas (1972). Decompose a system by isolating the design decisions likely to change and hiding each behind a module interface, rather than by processing steps. "How fenced content renders" is exactly such a decision and should sit behind one interface.
- **Single Responsibility** — Martin (2003), which descends from Parnas and from cohesion: a module should have one reason to change. Markdown rendering currently has three places that change for the same reason.
- **Coupling & cohesion** — Stevens, Myers & Constantine (1974). Functional cohesion is the strongest form; logical cohesion — grouping things merely because they are the same "kind" — is weak. A single module that switches between markdown/code/other by a flag would be logically cohesive; a thin dispatcher delegating to separately-cohesive per-type handlers is stronger, and matches the intent to keep each content type separate.
- **Microkernel / plug-in architecture** — Richards, *Software Architecture Patterns* (2015; 2nd ed. 2022). A minimal core plus plug-in modules registered through a plug-in registry; a natural fit for product applications with pluggable, versioned features. This is precisely the shape `registry.py` and `runner.py` already sketch.
- **Humble View / Presentation Model** — Fowler (2004); Gossman's MVVM (2005). The view should be passive, with presentation logic held outside it for testability. `conversation_view`'s own docstring states "zero business logic," yet it currently holds render logic. This aligns with ADR-001 and the Humble Object already used for providers.
- **Open/Closed Principle** — Meyer (1988). Software entities should be open for extension but closed for modification: adding a new handler later should mean registering it, not editing the dispatcher.
- **YAGNI** — Beck/Jeffries (Extreme Programming), with Fowler's refinement that YAGNI governs presumptive features, not the effort to make software easier to modify. Building the structure now is fine; building unused modes and handlers now is not. YAGNI's precondition — continuous refactoring, automated tests, CI — is satisfied by the project's tick-tock TDD and CI.

### Decision

1. **Single module model.** Adopt the registry / microkernel plug-in scheme (`registry.py` + `runner.py` + `modules/global/` + `modules/user/` + `module.json` + the `BaseModule` contract) as the one module organization, and wire it into the composition root. Flat `pedal_*.py` modules migrate to it incrementally, one per ticket; the three dead flat pedals (`pedal_conversationHistory`, `pedal_webAccess`, `pedal_connectedAccounts`) are removed or folded into folder modules rather than carried forward.
2. **The `writer` module.** Introduce a `writer` plug-in module that owns the rendered output of fenced content. It is a thin dispatcher over per-type handlers (`writer.<type>`) with per-mode functions (`.message`, `.super`), so new types and modes are added without modifying the core (Open/Closed).
3. **First application — `writer.markdown.message`.** Implement markdown per-message rendering under `writer.markdown`. The render logic is relocated out of `views/conversation_view.py` (restoring the Humble View), and `writer.markdown` calls the existing `render_markdown` routine from #129 — that work is relocated, not rolled back.
4. **Fence behavior (intentional departure from CommonMark).** When the markdown pedal is on: a fence whose language tag is `markdown`/`md` has its contents rendered as markdown; a fence tagged as a programming language (`python`, `bash`, …) stays verbatim; an untagged fence stays verbatim. This deliberately diverges from strict CommonMark (which renders every fence verbatim) because the tool exists to display the markdown the model returns, and models commonly deliver a markdown document inside a `markdown`-tagged fence. That document may itself contain code fences of the same delimiter length, so extracting the outer block's contents cannot rely on scanning for the next bare run of three backticks — nor on an off-the-shelf CommonMark parser, which mis-closes equal-length nested fences. This ADR fixes the dispatch rule; the nesting-aware extraction mechanism, and whether nested blocks are handled or scoped out of a first cut, are implementation choices deferred to the `writer.markdown` ticket and pinned by its tests.
5. **Deferred (YAGNI).** `.super` (global-override mode) and non-markdown handlers (`writer.python`, …) are not built now. The structure leaves room for them; each is added test-first when actually needed.
6. **Naming.** Disambiguate the `render_markdown` flag (the per-message boolean stamped at generation) from the render routine; give them distinct names in the implementation.
7. **Out of scope.** Foldable/collapsible headers. `QTextEdit` renders static HTML and cannot collapse sections; that would require a different display widget (e.g. `QWebEngineView`) and is a separate decision if ever pursued.

### Consequences

- **Positive:** One cohesive home per concern; "how fenced output renders" is hidden behind `writer`'s interface.
- **Positive:** The view becomes humble again, and render logic becomes unit-testable in isolation.
- **Positive:** New content types and modes are additive; separate handlers in separate files enable parallel work.
- **Positive:** The dual-scheme ambiguity resolves as the migration proceeds; the layout becomes uniform.
- **Negative:** Migration is incremental work; the module layout stays mixed until it completes.
- **Negative:** `writer` must reliably tell markdown fences from code fences, which depends on the model's fence tagging (see Open Questions).
- **Negative:** Markdown documents routinely embed code fences; with equal-length backticks the outer block's boundary is ambiguous to a standard parser, so the unwrap must be nesting-aware — or nested blocks must be explicitly scoped out of a first cut.
- **Negative:** The fence-rendering behavior departs from CommonMark; intentional, but it must stay documented so it is not mistaken for a defect.
- **Neutral:** Implementation lands in separate tickets after acceptance; this ADR commits to direction, not code.
- **Neutral:** The microkernel's usual trade-off — the core can become a dependency bottleneck — applies but is minor at this scale.

### Alternatives Considered

1. **Status quo** — keep both schemes and patch markdown in the view.
   - **Rejected:** leaves the fragmentation and the Humble-View violation, and does nothing for the broader "organize all modules" goal.
2. **Narrow fix only** — unwrap markdown fences inside `conversation_view`.
   - **Rejected:** fixes the visible bug but deepens the violation (more logic in the view) and ignores the scheme split.
3. **Big-bang reorganization** of every module at once.
   - **Rejected:** high risk and against incremental discipline; migration can proceed module by module.

### Open Questions / Follow-ups

- **Fence tagging (evidence in hand, with a caveat).** The fence rule assumes the model tags markdown documents with a `markdown`/`md` info string. Real output does tag the document `markdown`, so the signal exists. Caveat: that conversation's stored model metadata read `provider: ollama` / empty `model_id`, which did not match the Gemini selection shown in the app — confirm the behavior on a reply known to come from Gemini, and that it holds consistently. An untagged fence still carries no signal to separate markdown from code.
- **Nested fences.** A `markdown`-tagged block can wrap a same-length code fence. Decide the handling at implementation time, driven by the tester tick's fence cases: track nesting (treat a language-tagged fence line as an opener and a bare three-backtick line as closing the innermost open fence) or scope nested blocks out of the first cut. The nesting heuristic works for well-tagged output but breaks if a code block is opened with a bare fence or a fence is left unclosed.
- **Dispatch mapping.** How `writer.<type>.<mode>` maps onto `BaseModule.execute(function_name, parameters, …)` is to be settled in the implementation ticket.
- **Registry/runner wiring & pedal cleanup.** Wiring `ModuleRegistry` and `ModuleRunner` into the composition root, migrating the one live flat pedal (`pedal_markdownOutput`), and deleting the three dead ones, are separate follow-up tickets.

### Related Decisions

- Extends ADR-001 (MVVM) and the Humble Object pattern already used for providers — relocating render out of the view restores the Humble View.
- Records the per-message → pedal-driven reversal of #129's markdown rendering: that render logic is relocated into `writer.markdown` (gated by the markdown pedal), not rolled back — see Context and Decision 3.
- The `writer.markdown` implementation, the registry/runner wiring, and deletion of the three dead flat pedals are separate follow-up tickets.
- Cut by #132; absorbs the parked #129 branch (`feat/per-message-rendering`, 8a4e613) during implementation.

### References

- Parnas, D. L. (1972). *On the Criteria To Be Used in Decomposing Systems into Modules.* Communications of the ACM, 15(12), 1053–1058.
- Stevens, W. P., Myers, G. J., & Constantine, L. L. (1974). *Structured Design.* IBM Systems Journal, 13(2), 115–139.
- Meyer, B. (1988). *Object-Oriented Software Construction.* Prentice Hall. (Open/Closed Principle.)
- Martin, R. C. (2003). *Agile Software Development: Principles, Patterns, and Practices.* Prentice Hall. (Single Responsibility Principle.)
- Fowler, M. (2004). *Presentation Model.* martinfowler.com.
- Gossman, J. (2005). *Introduction to Model/View/ViewModel pattern for building WPF apps.*
- Richards, M. (2015; 2nd ed. 2022). *Software Architecture Patterns.* O'Reilly Media. (Microkernel / plug-in architecture.)
- Beck, K., & Jeffries, R. *Extreme Programming* (YAGNI); Fowler, M. (2015). *Yagni.* martinfowler.com.

---