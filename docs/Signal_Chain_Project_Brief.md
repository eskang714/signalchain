# Signal Chain - Project Brief
**Version:** 1.0 Planning Complete  
**Status:** Ready for DRAFT/Implementation  
**Purpose:** Transfer document for Claude Code / Claude Cowork

---

## Core Vision

**"Giving users the ability to have personal and expanded conversations with AI."**

- **Personal:** User owns data, controls configuration, private by default
- **Expanded:** Modules extend AI capability (tools, memory, output)
- **Role:** Mediator, not competitor. Works WITH Claude, Ollama, local models. Adds coordination layer, does not replace services.

---

## Design Principles

1. Separation of concerns (every component has one responsibility)
2. Graceful degradation (works offline, works degraded)
3. User control (no artificial limits, user decides risk)
4. Defense in depth (multiple validation layers)
5. Honest about limitations ("runnable but unverified" not "safe")
6. Modular/extensible (community extends, we maintain platform)
7. K.I.S.S. (simplify to the accurate minimum)
8. Data locality (process where it lives, minimal transfers)
9. Version all data (designed for migration from day one)

---

## Architecture

**Pattern:** MVVM + PyQt6

```
src/
├── models/          # Data layer (conversations, messages, registry)
├── viewmodels/      # Business logic + state (conversation, model, module, input, output)
├── views/           # PyQt6 UI components
├── modules/         # Module system
│   ├── global/      # App-maintained
│   └── user/        # Community-maintained
├── providers/       # Provider implementations
└── utils/           # Utilities
```

**Threading:** QThread per conversation. Non-blocking UI. Multiple simultaneous generations supported. Tokens emit via signals to main thread.

---

## Module System

### Two-Tier Architecture

**Global Modules (we maintain):**
1. `conversation_history` - Memory, context, search (required, always on)
2. `file_system` - File I/O
3. `markdown_output` - Structured file generation
4. `web_access` - Internet search/fetch
5. `connected_accounts` - Auth ONLY (OAuth/API keys). Not API functionality.
6. `time` - Date/time operations

**User Modules (community maintains):**
- Isolated (cannot access other user modules)
- Auto-discovered from `modules/user/` folder
- Validated on startup, cached for session

### Module States
- 🔴 INVALID - Cannot enable (structural failure)
- 🟡 RUNNABLE BUT UNVERIFIED - Can enable (user decides risk)
- 🟢 VERIFIED - Passed AI security check (user's API key, user's cost)

### Auto-Discovery
Scan `modules/` on startup. Valid = has `module.json` + `module.py` + passes structural validation. No manual registration. Refresh button re-scans.

### Module Interface
```python
class BaseModule(ABC):
    def initialize(self): pass
    def execute(self, function_name, parameters): pass
    def shutdown(self): pass
    def get_functions(self) -> List[FunctionSchema]: pass
    def validate_parameters(self, function_name, parameters): pass
```

---

## Provider System

**Three providers in V1:**

| Provider | Auth | Model Discovery | Notes |
|----------|------|-----------------|-------|
| Claude API | OS keychain via connected_accounts | Static list | Paid, cloud |
| Ollama | None (local service) | Auto via `ollama.list()` | Free, local |
| Local GGUF | None | Manual browse + auto-detect metadata | Free, local |

**BaseProvider interface:**
```python
class BaseProvider(ABC):
    def list_models(self): pass
    def load_model(self, model_id): pass
    def unload_model(self): pass
    def generate_stream(self, messages, config) -> Iterator[str]: pass
    def validate_config(self): pass
    def estimate_memory_usage(self, model_id): pass
```

---

## Resource Management

### Pluggable ResourceManager (design in V1, extend in V1.1+)

```python
class ResourceModule(ABC):
    def get_type(self) -> ResourceType: pass      # MEMORY, COMPUTE, STORAGE, GPU
    def is_available(self) -> bool: pass
    def get_capacity(self) -> ResourceCapacity: pass
    def allocate(self, requirements): pass
    def deallocate(self, allocation): pass
```

**V1 Standard Modules:** SystemRAM, LocalGPU, LocalCPU, SystemSwap  
**V1.1+ Advanced Modules:** USBStorageArray, DistributedCompute, DeviceSwarm

### CPU Controls
- Thread count (slider)
- Core affinity (per-core selection)
- P-core vs E-core awareness (Intel)
- Thread priority (low/normal/high)

### GPU Controls
- GPU layer offload count
- Multi-GPU split (tensor_split parameter)
- VRAM limit per model
- Fallback to CPU if VRAM exceeded

### Memory Tiers (Four-Tier System)
1. **OPTIMAL** (green) - Plenty of RAM → auto-configure
2. **RECOMMENDED** (yellow) - Tight RAM → warn, allow
3. **WILL SWAP** (orange) - Insufficient RAM → strong warning required + SSD wear warning + user must check 3 acknowledgment boxes
4. **BLOCKED** (red) - Cannot load → hard block

**SSD Wear Warning:** Heavy swapping = ~10GB/min writes. Consumer SSD (600 TBW) could degrade in weeks. Always display this in the orange tier dialog.

**mmap mode:** Available as mitigation for orange tier. Model stays on disk, OS handles paging. Helps but still slow.

---

## Local Model Wizard (5 Steps)

1. Select .gguf file (browser + links to HuggingFace/Ollama)
2. Auto-detect metadata (architecture, params, quantization, context length)
3. Configure resources (Quick Start recommended / Custom / CPU Only)
4. Test loading (actually loads, measures tokens/sec, catches errors with suggested fixes)
5. Complete (add to library)

**Batch import:** Scan folder for .gguf files, select multiple, apply recommended settings.

---

## Data Management

**Conversations:** JSON files in `~/Documents/AI_Chat/conversations/`  
**Generated files:** `~/Documents/AI_Chat/outputs/`  
**Config:** YAML in `~/.signal_chain/config/`  
**Credentials:** OS keychain (keyring library)  
**Cache:** `~/.signal_chain/cache/`

### Conversation Format (V1 schema - version field required)
```json
{
  "version": "1.0",
  "schema": "conversation.v1",
  "conversation_id": "conv_abc123",
  "created": "ISO8601",
  "model": { "provider": "ollama", "model_id": "llama3.2:3b" },
  "messages": [
    { "id": "msg_001", "role": "user", "content": "...", "timestamp": "ISO8601" }
  ],
  "metadata": { "title": "...", "tags": [], "module_usage": {} }
}
```

**Rule:** Version ALL data files. Unknown fields are ignored (forward compatibility). Migration framework built in V1 even if unused.

---

## Context Window Strategy

**Hybrid approach:**
- Recent N messages always included (default 20, configurable 10-50)
- Older messages searchable via `conversation_history.search()`
- AI calls search when it needs older context
- Token counting before send, buffer 1000 tokens for response

**Per-provider limits (configurable):**
- Claude: 180,000 tokens
- Local/Ollama: 4,096 tokens (model-dependent)

---

## Error Recovery

| Error | Strategy |
|-------|----------|
| Generation fails mid-stream | Save partial, show retry button |
| Module execution error | Continue generation, show ⚠️ indicator |
| Network drop (API) | Retry x3 with exponential backoff (2^n seconds) |
| Provider unavailable | Show specific error + actionable fix (not auto-switch) |
| Out of resources | Suggest fixes (reduce layers, smaller model, close apps) |
| Rate limit | Auto-wait retry_after seconds, show countdown |

---

## Configuration & Startup

### Startup Flow
```
config.yaml exists?
  NO  → First-run wizard
  YES → Validate (paths exist + writable + disk space)
          INVALID → Fix config dialog
          VALID   → Load global modules → Validate modules → Check providers → Start app
```

### Required Configuration (blocks startup if missing)
- Conversation history directory
- File output directory
- Module directory
- Cache directory

### Optional (can configure after startup)
- Provider API keys
- Model selection
- Module preferences

### First-Run Wizard (4 pages)
1. Welcome
2. Storage paths (required, with defaults, disk space check)
3. Provider setup (optional, skip available)
4. Ready summary

---

## UI Layout

**Three-panel layout:**
- Left (260px): Conversation list, search, grouped by time, New Chat button
- Center (flex): Chat area, model selector header, messages, input
- Right (280px, collapsible): Module panel

**Model selector:** In chat header. Switch triggers new generation context.  
**Module usage:** Each assistant message shows which modules were used.  
**Generated files:** Inline as clickable cards in chat.  
**Status bar:** Connection • Module count • Auto-save • Resource usage

### Input
- Auto-expanding textarea
- Enter = send, Shift+Enter = newline
- Attach file button
- Module toggle (shows count enabled)

### Module Panel
- [🔄 Refresh] re-scans modules directory
- [📁 Open Folder] opens modules/user/ in file explorer
- Global section (always enabled, no toggle)
- User section (toggle per module)
- Status dots: 🟢 🟡 🔴
- [+ Install Module] button

---

## Settings Structure

1. **General** - Startup, storage paths, privacy, auto-save
2. **Appearance** - Theme, layout, font, chat display
3. **Providers** - Claude API key, Ollama URL, local model paths
4. **Models** - Local model library, performance settings, resource management
5. **Modules** - Installed modules, defaults, validation settings
6. **Context** - Recent message count, token limits, search settings
7. **Advanced** - Error recovery, concurrency limits, logging, experimental features

---

## Version Strategy

**V1.0 (MVP - now):**
Core features. Pluggable ResourceManager architecture. Standard resource modules. Version fields in all data.

**V1.1-1.5 (post-launch):**
Advanced hardware modules (USB arrays, distributed compute, device swarms). Experimental features section (off by default). Automatic transparent migration.

**V2.0 (if needed, ~1-2 years):**
Only if V1 architecture becomes limiting. Tool-assisted migration. Backup before migrate. Coexistence option.

### Migration Rules
- Every file has `version` field
- Unknown fields: ignore (don't error)
- Minor upgrades: automatic, transparent
- Major upgrades: wizard, backup first, user confirms

---

## Experimental / Future Features (V1.1+)

All gated behind Settings → Advanced → Experimental Features (disabled by default).

- USB storage array as distributed swap (complexity 9/10, drive wear warning required)
- Distributed inference across network devices (Petals-like, complexity 7/10)
- Device swarm pooling (phones, Raspberry Pis as compute nodes)
- Custom resource scripts (community-driven, plugin system)

**Philosophy:** Show complexity rating, expected performance, drive wear warnings, alternatives. User must acknowledge before enabling. We inform, warn, enable. We do not gatekeep.

---

## Key Decisions Log

| Decision | Choice | Reason |
|----------|--------|--------|
| Architecture | MVVM + PyQt6 | Clear separation, mature UI framework |
| Threading | QThread per conversation | Simple, Qt-native, meets multi-chat requirement |
| Storage | JSON files → SQLite → NoSQL | Simple start, evolve based on need |
| Validation | Two-phase (structural + optional AI) | Honest about limits, user decides |
| Credentials | OS keychain | Security, not stored in files |
| Module types | Global (us) + User (community) | Finite maintenance burden |
| Auth module | connected_accounts auth ONLY | Prevents infinite maintenance scope |
| Providers | All three in V1 | Maximum flexibility |
| Model limits | None (disk space is constraint) | User autonomy |
| Resource system | Pluggable from V1 | Enables V1.1+ extensions without breaking |
| Swap/paging | Orange tier (warn + allow) | Emergency fallback, user informed |
| SSD wear | Always warn in swap mode | Honest about hardware impact |
| Version migration | Built into V1 | Design for evolution from day one |
| Role | Mediator not competitor | Sustainable, works with existing services |

---

## Technology Stack

- **Language:** Python 3.11+
- **UI:** PyQt6
- **Local inference:** llama-cpp-python
- **Ollama:** ollama Python client
- **Cloud:** anthropic Python SDK
- **Config:** PyYAML
- **Credentials:** keyring
- **Resource monitoring:** psutil, pynvml (GPU)
- **Token counting:** tiktoken (Claude/OpenAI), llama tokenizer (local)
- **Storage:** JSON (V1), SQLite option (V2)

---

## What This Application Is Not

- Not replacing Claude, Ollama, or any LLM service
- Not competing with existing providers
- Not a hosted service (client-side only)
- Not responsible for module security (informed user choice)
- Not responsible for external validation costs (user's API key)

---

*This document represents the complete V1.0 planning output. Carry forward into implementation.*
