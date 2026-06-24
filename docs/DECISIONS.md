# Architecture Decision Records (ADRs)

Decision log for the signal-chain project's architecture and significant technical choices.

**Relationship types:** `Builds on` / `Extended by` (a decision and the one it derives from) · `Supersedes` / `Superseded by` (replacement) · `Related` (associative). ADR-001–005 are anchors — roots with no `Builds on`.

**Revision history**
- 2026-06 (#132) — consolidated scattered records into this single log (ADR-001–009).
- 2026-06 (#136) — split ADR-009 into 009 (Module Organization) and 010 (Writer Module); added the lineage graph; restated 010's per-message/pedal-driven model in one voice.
- 2026-06 (#144) — normalized all records to one structure and voice; revised ADR-010 Decision 2 to the segmenter composition (before-state and rationale in the issue comment); expanded the open-questions/follow-ups in ADR-009 and ADR-010 into tracked items; recorded #106 (ADR-008) as landed.

**Maintenance.** Open questions are validated lazily — an assumption is confirmed when the code depending on it is next touched, or when something breaks. Breakage is the signal to revisit the affected record; there is no periodic validation sweep. *(Proposed addition — strike if you'd rather not state a policy in the doc.)*

---

## ADR-001: MVVM Architecture Pattern

**Status:** Accepted · **Date:** May 2026
**Extended by:** ADR-010 (Writer Module)

### Context
A PyQt6 desktop app running multiple concurrent conversations needs reactive UI updates and clear separation of concerns.

### Decision
Use the MVVM (Model-View-ViewModel) pattern.

### Consequences
- ViewModels use PyQt signals for reactive updates.
- Views hold zero business logic; Models stay pure data.
- Slight learning curve coming from MVC.

### Alternatives Considered
- **MVC** — standard, but PyQt6's signal/slot system maps more naturally to MVVM.
- **Clean Architecture** — too much overhead for V1.
- **Flat structure** — insufficient for multi-conversation complexity.

---

## ADR-002: uv for Package Management

**Status:** Accepted · **Date:** May 2026

### Context
Need Python package and virtual-environment management.

### Decision
Use uv (Astral).

### Consequences
- Faster installs; one tool for packages and environments.
- Current industry trend; some older tutorials still assume pip.

### Alternatives Considered
- **pip + venv** — standard, but slower and needs manual activation.
- **Poetry** — popular but heavier and slower than uv.
- **pipenv** — falling out of favor.

---

## ADR-003: Apache 2.0 License

**Status:** Accepted · **Date:** May 2026

### Context
Need a license that allows future commercialization while supporting open-source adoption.

### Decision
Apache License 2.0.

### Consequences
- Allows future closed-source derivatives; patent protection from contributors; enterprise-friendly.
- Slightly longer text than MIT.

### Alternatives Considered
- **MIT** — simpler, but no patent protection.
- **GPL** — restricts commercial use too heavily.
- **BSL** — bait-and-switch perception risk.
- **Proprietary** — conflicts with portfolio goals.

---

## ADR-004: Two-Tier Module System

**Status:** Accepted · **Date:** May 2026
**Extended by:** ADR-007 (Pedal Naming), ADR-009 (Module Organization)

### Context
Need an extensible module system without an unbounded maintenance burden.

### Decision
Two tiers: **global** modules (app-maintained) and **user** modules (community-maintained). User modules are isolated from each other.

### Consequences
- Clear ownership: the app maintains the global modules; the community owns the rest.
- User modules cannot access each other (isolation).
- Module validation is two-phase (structural + optional AI security check).

### Alternatives Considered
- **Single flat system** — maintenance scope unbounded.
- **No user modules** — limits extensibility.
- **Full sandboxing** — too complex for V1.

---

## ADR-005: GitHub as Primary Platform

**Status:** Accepted · **Date:** May 2026
**Extended by:** ADR-006 (Qt/EGL CI Dependencies)

### Context
Need version control, CI/CD, project tracking, and visibility.

### Decision
GitHub for the repo, Actions for CI, Issues for tickets, Projects for tracking.

### Consequences
- All tooling in one place; public portfolio visibility.
- Direct Claude Code integration via the GitHub CLI; free for public repos.

### Alternatives Considered
- **GitLab** — equivalent, but less industry visibility.
- **Bitbucket** — less common.
- **Self-hosted** — overhead without benefit for a solo dev.

---

## ADR-006: Qt/EGL Library Dependencies in CI

**Status:** Accepted · **Date:** May 2026
**Builds on:** ADR-005 (GitHub as Primary Platform)

### Context
PyQt6 needs Qt runtime libraries even headless. `ubuntu-latest` runners don't include them, so pytest's PyQt6 import failed:

```
libEGL.so.1: cannot open shared object file: No such file or directory
```

This blocked every PyQt6-dependent test in CI.

### Decision
Install the Qt/EGL system libraries in the CI workflow via `apt-get`, and run Qt headless via `QT_QPA_PLATFORM=offscreen`:
- `libegl1` (EGL), `libgl1` (OpenGL), `libxkbcommon0` (keyboard), `libdbus-1-3` (D-Bus).

### Consequences
- **Positive:** CI imports and tests PyQt6 in headless runners without xvfb; ~2–3 s overhead.
- **Negative:** The CI environment is no longer a bare Python environment; Qt version drift between runner and dev could surface compatibility issues.

### Alternatives Considered
- **xvfb (virtual framebuffer)** — more complex, higher resource use. Rejected: unnecessary for headless testing.
- **Mock PyQt6 in tests** — rejected: we need to verify real PyQt6 integration, not just business logic.
- **Skip GUI tests in CI** — rejected: reduces confidence and defeats the purpose of CI.

### Related
- Follows from choosing PyQt6 as the UI framework; informs the CI strategy for framework-specific testing.

---

## ADR-007: Pedal Module Naming Convention

**Status:** Accepted · **Date:** June 2026
**Builds on:** ADR-004 (Two-Tier Module System)
**Extended by:** ADR-008 (Network Gateway Gating)

### Context
Pedalboard pedals shared no naming marker, so `MarkdownOutputModule`, `ConversationHistoryModule`, and `ConnectedAccountsModule` were indistinguishable from module-system infrastructure (`base`, `registry`, `runner`) and from the egress `NetworkGateway`. The ambiguity surfaced while refreshing docs: "Connected Accounts" had drifted between two different things — the provider selector users picture and the credential-vault module that actually wears the name — and nothing in the naming flagged what was or wasn't a pedal. Separately, the product's identity *is* the guitar signal chain; the naming should carry that, not read as generic Python.

### Decision
Name every pedalboard pedal `pedal_<camelCaseName>`, extending through `_<subModuleName>` for nested units:
- class: `pedal_<camelCaseName>` (e.g. `pedal_markdownOutput`)
- file: `pedal_<camelCaseName>.py` — matching the class, so the unit reads identically in import path and symbol
- sub-modules append segments: `pedal_markdownOutput_tableFormatter`

| Before | After |
|--------|-------|
| `MarkdownOutputModule` | `pedal_markdownOutput` |
| `ConversationHistoryModule` | `pedal_conversationHistory` |
| `ConnectedAccountsModule` | `pedal_connectedAccounts` |

The `pedal_` prefix is reserved for user-facing pedals. Infrastructure (`base`, `registry`, `runner`) and the egress `NetworkGateway` do not take it. The lowercase, unpolished form is deliberate branding — each module reads as an unpatched pedal waiting to be patched into the chain.

### Consequences
- **Positive:** Pedals are unmistakable and visually distinct from infrastructure, closing the naming-drift that caused the Connected Accounts confusion; future pedals get an unambiguous pattern; the naming carries the product identity.
- **Negative:** Deliberate PEP8 deviation (class names are conventionally CapWords, files snake_case). `ruff` doesn't select the `N` rules, so the suite stays green; if enabled, pedals need `N801`/`N999` ignores.
- **Negative:** Applying it touches every reference (imports, registry, tests, hints) — done as a separate chore, not silently.

### Alternatives Considered
- **`Pedal<Name>` (PascalCase, PEP8-compliant)** — rejected: reads as a finished generic class; loses the unpatched-unit branding.
- **Keep `<Name>Module`** — rejected: `Module` is shared by pedals and infrastructure, so it doesn't distinguish pedals — the exact gap that allowed the drift.
- **Function-honest names** (`ProviderManager`, `CredentialVault`) — rejected: no systematic "this is a pedal" marker and no brand identity.

### Related
- **Rename — applied.** A separate `chore` ticket performed it; the `pedal_*` files are present in the tree (`pedal_markdownOutput.py`, `pedal_conversationHistory.py`, `pedal_webAccess.py`, `pedal_connectedAccounts.py`), confirmed by direct read.
- **Provider-selector extraction** out of `app.py` (a distinct unit, not a pedal) — noted as adjacent work; status unconfirmed, left open until touched.

---

## ADR-008: Network Gateway Gating Policy

**Status:** Accepted · **Date:** June 2026
**Builds on:** ADR-007 (Pedal Naming Convention)

### Context
Wiring the generation path through a network gate (#106, complete mediation) required settling how egress is gated. Three forks had paused the work: whether a module's calls to the user's selected LLM provider are gated or always allowed; the default gateway when no policy is configured; and whether the gate covers every path or some. Saltzer & Schroeder's complete-mediation principle wants every egress through one checkpoint — but a checkpoint that blocks the app's own provider, or defaults to deny and breaks first run, is worse than the problem. The policy had to mediate egress without obstructing the provider traffic the app exists to make.

### Decision
1. **`net:provider` is always granted.** Egress to the user's selected provider is permitted unconditionally — the app can't function without reaching its provider, so that traffic is never gated.
2. **`_PermitGateway()` is the default (Null Object).** With no policy configured, the gateway permits all egress. Gating is additive and opt-in: call sites run unchanged, and stricter gateways are added without modifying them (Open/Closed).
3. **Gate the generation path only.** The provider probe/health-check path is excluded — probes run before a policy context exists and aren't user-driven egress.
4. **`net:provider` granularity is a known limit.** The scope is coarse (provider egress as a whole, not per-host/endpoint). Finer granularity is deferred and documented, not silently assumed.

### Consequences
- **Positive:** The generation path has a single mediation point without blocking the provider traffic the app depends on; the Null Object default keeps first-run and unconfigured installs working; excluding probes keeps availability checks policy-free.
- **Negative:** Coarse `net:provider` granularity — a misbehaving module reaching the provider host can't be gated more narrowly yet; always-granting provider egress is a deliberate trust assumption a stricter model might revisit.
- **Neutral:** The enforcement code lives in #106, not this ADR — now landed (merged via PR #115).

### Alternatives Considered
- **Gate `net:provider` like any other egress** — rejected: a misconfiguration or deny-by-default would break the app's core function; cost outweighs the marginal control at this scope.
- **Deny-by-default gateway** — rejected: breaks first run and contradicts the additive/opt-in model; a Null Object default is safer and OCP-friendly.
- **Gate every path, including probes** — rejected: probes predate any policy context and aren't user-driven; gating them adds complexity with no security benefit.

### Related
- Implemented by #106 — generation path wired through the gate, merged via PR #115. (The `NetworkGateway` itself merged earlier in #102.)
- Grounded in Saltzer & Schroeder (1975) complete mediation, the Null Object pattern, and the Open/Closed Principle.
- Governs the egress `NetworkGateway` (infrastructure, not a pedal, per ADR-007).

---

## ADR-009: Module Organization Scheme

**Status:** Accepted · **Date:** June 2026
**Builds on:** ADR-004 (Two-Tier Module System)
**Extended by:** ADR-010 (Writer Module)

### Context
The module layer carries two organizational schemes at once.

- **Flat modules.** Top-level files under `modules/` — `pedal_markdownOutput.py`, `pedal_conversationHistory.py`, `pedal_webAccess.py`, `pedal_connectedAccounts.py` — each a `BaseModule` subclass. Only `pedal_markdownOutput` is wired (`app.py`, for export); a sweep of all 38 modules finds no importer for the other three, so they are effectively dead code.
- **A registry/runner plug-in scheme.** `registry.py` (`ModuleRegistry`) scans `modules/global/` and `modules/user/` for folders carrying a `module.json` manifest and a `module.py`, separating global modules (built-in, always on) from user modules (enable/disable, gated by an `INVALID`/`RUNNABLE_UNVERIFIED`/`VERIFIED` state machine). `runner.py` (`ModuleRunner`) is its execution half: it dispatches `execute(module_name, function_name, parameters, caller_module)` and enforces isolation (`ModuleIsolationError` — a user module may not call another) — the runtime seam for the untrusted-module sandbox.

Neither `ModuleRegistry` nor `ModuleRunner` is wired in — each is referenced only in its own file. The only folder-style module is `modules/global/conversation_history/`, and `conversation_history` *also* exists as the dead flat `pedal_conversationHistory.py`, so one concept lives in both schemes. On top of that, the pedalboard UI's six pedals are lightweight `PedalModule` data objects in `PedalboardViewModel` (id + enabled + LED), not the `BaseModule` classes and not connected to them.

### Decision Drivers
- **Information hiding** — Parnas (1972). Decompose by isolating the design decisions likely to change behind module interfaces, not by processing steps.
- **Microkernel / plug-in architecture** — Richards (2015; 2nd ed. 2022). A minimal core plus plug-ins registered through a registry — the shape `registry.py` and `runner.py` already sketch.

### Decision
Adopt the registry/microkernel scheme (`registry.py` + `runner.py` + `modules/global/` + `modules/user/` + `module.json` + the `BaseModule` contract) as the single module organization, and wire it into the composition root. It is the concrete implementation of ADR-004's two-tier policy. Flat `pedal_*.py` modules migrate incrementally, one per ticket; the three dead flat pedals are removed or folded into folder modules rather than carried forward.

### Consequences
- **Positive:** One coherent module model; plug-in extensibility — new modules register rather than being hand-wired.
- **Negative:** Migration is incremental; the layout stays mixed until it completes.
- **Neutral:** The microkernel's usual core-bottleneck trade-off applies but is minor at this scale.

### Alternatives Considered
- **Status quo (both schemes)** — rejected: leaves the fragmentation and does nothing for the goal.
- **Big-bang reorganization** — rejected: high risk and against incremental discipline; migrate module by module.

### Open Questions / Follow-ups

#### Open questions (awaiting a decision)

**Q1 — User-module isolation enforcement.** *(latent — surfaced during this normalization; promote or strike)*
- *Question:* How is the two-tier policy's isolation actually enforced for untrusted user modules? ADR-004 names an "optional AI security check"; `ModuleRunner` raises `ModuleIsolationError` to stop one user module calling another; neither is wired, and OS-level sandboxing is unbuilt.
- *Options:* the runtime `ModuleIsolationError` seam alone (in-process, trust-the-import); an OS-level sandbox (process/permission isolation); or a structural-plus-AI validation gate at load time (ADR-004's check).
- *Decided by:* when the first real user module ships, or a security pass is scheduled — not before.

#### Follow-ups (decided, awaiting a tick)

- **Registry/runner wiring.** Wire `ModuleRegistry` and `ModuleRunner` into the composition root. Blocks ADR-010 Q3 (the `execute()` dispatch binding) — once `writer` registers as a module, that mapping is concrete.
- **Pedal cleanup.** Migrate the one live flat pedal (`pedal_markdownOutput`) into the folder scheme; remove the three dead flat pedals (`pedal_conversationHistory`, `pedal_webAccess`, `pedal_connectedAccounts`) or fold them into folder modules. One per ticket, never a sweep.

### References
- Parnas, D. L. (1972). *On the Criteria To Be Used in Decomposing Systems into Modules.* CACM, 15(12), 1053–1058.
- Richards, M. (2015; 2nd ed. 2022). *Software Architecture Patterns.* O'Reilly. (Microkernel / plug-in.)

---

## ADR-010: The Writer Module and Markdown Rendering

**Status:** Accepted · **Date:** June 2026
**Builds on:** ADR-001 (MVVM / Humble View), ADR-009 (Module Organization Scheme)

### Context
Markdown handling is split across three places with no shared home:
- display rendering sits inline in `views/conversation_view.py`;
- fenced-block handling is buried inside the `markdown`-library call there;
- markdown file export lives in `pedal_markdownOutput`.

The view holding render logic also breaks its own docstring ("zero business logic") and the Humble-View rule from ADR-001.

The gap showed up while building per-message rendering (#129): prose renders fine with the markdown pedal on, but a markdown document the model returns **inside a fence tagged `markdown`** shows as a verbatim code block instead of rendering. Worse, that document often embeds its own code fence — a `markdown` block wrapping a `python` block, both with three backticks. CommonMark closes a fence at the first run of equal-or-greater backticks, so the outer block ends early at the inner fence and everything after it mis-renders. No component owns the question: **how is fenced output rendered?**

### Decision Drivers
- **Humble View** — Fowler (2004), Gossman (2005). The view should be passive; presentation logic lives outside it for testability. Matches ADR-001 and the Humble Object used for providers.
- **Single Responsibility** — Martin (2003). One reason to change; markdown rendering currently has three.
- **Cohesion over flags** — Stevens, Myers & Constantine (1974). A module that flag-switches between markdown/code/other is weakly (logically) cohesive; a thin dispatcher delegating to per-type handlers is stronger.
- **Open/Closed** — Meyer (1988). Adding a handler should mean registering it, not editing the dispatcher.
- **YAGNI** — Beck/Jeffries; Fowler (2015). Build the structure now; don't build unused modes and handlers now.

### Decision

**1. A `writer` module with an always-on core.**
Introduce a `writer` plug-in module (ADR-009 scheme) that owns how fenced output is rendered. Its core is a thin dispatcher: handlers register into it under a tag, and it routes each fence to the matching handler. `writer.core` is the module's structural floor — always on, never pedal-gated. It owns fence-boundary detection and the **clean monospace exit**: a fence's content is rebuilt from the lines *between* the delimiters, with no trailing blank line. The core depends on no handler and no pedal.

**2. First job: relocate markdown rendering — as a segmenter.**
Move markdown rendering out of `conversation_view` into `writer.markdown` (restoring the Humble View). The core splits a message and routes the pieces:
- prose and `markdown`/`md` fences → `writer.markdown` (rendered as markdown);
- programming-language and untagged fences → the core's monospace fallback.

So **code fences never pass through the markdown library** — which is exactly why code blocks get the clean exit. The `render_markdown` routine from #129 is reused per-segment (prose and `md` content), not over the whole message. Relocated, not rolled back.

**3. Rendering is pedal-driven, frozen per message.**
The markdown pedal decides whether output renders or stays plain. Its state is captured into the `render_markdown` boolean on `ConversationMessage` at generation time and frozen there; the writer's `.message` mode consumes that frozen value. (Pedal-driven and per-message are one mechanism, not opposites: the pedal sets the value, the message freezes it.)

**4. Fence rule — a deliberate departure from CommonMark.**
With the markdown pedal on:
- `markdown`/`md` fence → contents rendered as markdown;
- programming-language fence (`python`, `bash`, …) → verbatim;
- untagged fence → verbatim.

Strict CommonMark renders every fence verbatim. We diverge because the tool exists to *display the markdown the model returns*, and models commonly wrap that markdown in a `markdown` fence. Since that block may contain same-length code fences, the unwrap can't just scan for the next bare three backticks, and an off-the-shelf CommonMark parser mis-closes it. This ADR fixes the **rule**; the nesting-aware extraction **mechanism** is deferred to the `writer.markdown` tickets and pinned by their tests.

**5. Deferred (YAGNI).** A global-override mode (`.super`) and non-markdown handlers (`writer.python`, …) are not built now. The structure leaves room; each is added test-first when needed.

**6. Naming.** Give the `render_markdown` flag and the render routine distinct names so they aren't confused.

**7. Out of scope.** Collapsible headers — `QTextEdit` renders static HTML and can't collapse sections; that needs a different widget and a separate decision.

### Consequences
- One home for "how fenced output renders," behind the `writer` interface; the view is humble again; render logic is unit-testable in isolation.
- New types and modes are additive — separate handlers in separate files, parallel-friendly.
- The clean code-block exit is a property of the composition (code skips the markdown library), not a patch.
- The core must reliably tell markdown fences from code fences — depends on the model's tagging (see Open Questions).
- Same-length embedded fences make the outer boundary ambiguous to a standard parser, so the unwrap must be nesting-aware (or nested blocks scoped out of a first cut).
- The fence behavior departs from CommonMark on purpose — it must stay documented so it's not read as a bug.

### Alternatives Considered
- **Status quo** (markdown logic stays in the view) — rejected: keeps the fragmentation and the Humble-View violation.
- **Narrow fix** (unwrap markdown fences inside `conversation_view`) — rejected: fixes the symptom, deepens the violation.
- **Whole-message rendering** (`writer.markdown` reruns #129 over the entire message) — rejected: code fences would re-enter the markdown library, bringing back the trailing-blank exit and sidelining the core. The segmenter (Decision 2) was chosen instead.

### Open Questions / Follow-ups

Two kinds of item live here. **Open questions** are forks awaiting a decision — each names its options and what will settle them. **Follow-ups** are work already decided, awaiting a tick.

#### Open questions (awaiting a decision)

**Q1 — Fence-tagging reliability.**
- *Question:* Does the model reliably wrap a returned markdown document in a `markdown`/`md` fence, so the segmenter can tell markdown from code by tag?
- *Check:* Confirm on a reply known to be Gemini. The earlier sample can't confirm it — its stored metadata read `provider: ollama` / empty `model_id`, contradicting the Gemini selection shown.
- *Blocked by:* the provider/`model_id` data-integrity bug (its own ticket). Until that's fixed or a fresh unambiguous reply is captured, no sample can be trusted to confirm the tag.
- *Bounded, not open — the untagged case:* an untagged fence gives no signal, so it falls to the monospace default (renders verbatim — the status quo). Worst case is an untagged markdown document showing as code; never a crash or data loss. That default already lives in the core (Decision 1).

**Q2 — Nested-fence boundary (the parsing exit).**
- *Question:* How does `writer.markdown` find the outer fence's end when a `markdown` block wraps a same-length code fence? This is the *parsing* half of "clean exit"; Decision 2 settled the *rendering* half (composition), not this.
- *Options:* **(A) track nesting** — a language-tagged fence line opens a frame, a bare three-backtick line closes the innermost open frame; or **(B) scope nesting out of the first cut** — v1 handles only non-nested markdown fences; nesting comes in a later tick.
- *Decided by:* the tester tick's cases — whether real output produces nested same-length fences often enough to force (A) in v1, or whether (B) covers the common case.
- *(A) must encode as test cases:* the heuristic breaks if a code block opens with a bare (untagged) fence, or is left unclosed.
- *Same mechanism, same tick:* tolerance for a closing fence trailed by whitespace — the core's close-match is currently the naive exact bare-fence match only.
- *Resolves in:* the `writer.markdown` tester tock (precedes the relocation builder tick).

**Q3 — Dispatch binding.**
- *Question:* How does `writer.<type>.<mode>` bind onto `BaseModule.execute(function_name, parameters, …)` under ADR-009? Composition is settled (Decision 2); only the call-signature mapping is open.
- *Blocked by:* the ADR-009 registry/runner wiring (see ADR-009 follow-ups) — once `writer` registers as a module, the `execute()` mapping is concrete.

#### Follow-ups (decided, awaiting a tick)

- **The relocation itself** — build `writer.markdown` as the Decision 2 segmenter; the work that closes #142's output gap. Tester tock → builder tick, gated on this ADR edit landing.
- **`_render_prose` HTML-escaping** — deferred in #140 until usage patterns are clearer; revisit when the relocation exercises prose paths.
- **Retire superseded issues** — #126 and #129 fold into `writer.markdown`; close on relocation merge.

### References
- Stevens, Myers & Constantine (1974). *Structured Design.* IBM Systems Journal, 13(2), 115–139.
- Meyer (1988). *Object-Oriented Software Construction.* Prentice Hall. (Open/Closed.)
- Martin (2003). *Agile Software Development.* Prentice Hall. (Single Responsibility.)
- Fowler (2004). *Presentation Model.* martinfowler.com.
- Gossman (2005). *Introduction to Model/View/ViewModel.*
- Beck & Jeffries. *Extreme Programming* (YAGNI); Fowler (2015). *Yagni.* martinfowler.com.