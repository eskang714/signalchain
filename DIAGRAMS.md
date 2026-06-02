# System Diagrams

---

## Component Diagram

Shows the high-level parts of the system and how they connect.

```mermaid
graph TD
User([User])

subgraph Application["signal-chain (Client Device)"]
UI[Views\nPyQt6 UI Components]
VM[ViewModels\nBusiness Logic + Signals]
MOD[Module System\nconversation_history\nmarkdown_output\nconnected_accounts\nweb_access\nfile_access\nclock]
RES[Resource Manager\nCPU / GPU / RAM\nCompatibility Checks]

subgraph Providers["Providers"]
P1[Claude API Provider]
P2[Ollama Provider]
P3[OpenRouter Provider]
P4[Groq Provider]
P5[Gemini Provider]
end

subgraph Storage["Local Storage"]
S1[Conversations\nJSON Files]
S2[Config\nYAML Files]
S3[Credentials\nOS Keychain]
end
end

subgraph External["External Services"]
E1[Anthropic Claude API]
E2[Ollama Local Service]
E3[OpenRouter API]
E4[Groq API]
E5[Google Gemini API]
end

User --> UI
UI --> VM
VM --> MOD
VM --> Providers
VM --> Storage
VM --> RES
P1 --> E1
P2 --> E2
P3 --> E3
P4 --> E4
P5 --> E5
```

---

## Sequence Diagram

Shows what happens step by step when a user sends a message.

```mermaid
sequenceDiagram
actor User
participant View as View (UI)
participant VM as ViewModel
participant Worker as QThread Worker
participant Provider as Provider
participant LLM as LLM Service

User->>View: Types message, presses Enter
View->>VM: emit input_submitted signal
VM->>VM: Build context (recent messages + modules)
VM->>Worker: Start generation thread
Worker->>Provider: generate_stream(messages, config)
Provider->>LLM: API call / local inference

loop Streaming tokens
LLM-->>Provider: token
Provider-->>Worker: token
Worker-->>VM: emit token_received signal
VM-->>View: emit ui_update signal
View-->>User: Token appears in chat
end

Worker-->>VM: emit generation_complete signal
VM->>VM: Save conversation to disk
VM-->>View: emit message_saved signal
View-->>User: Input re-enabled
```

---

## Module State Diagram

Shows the validation states a module can be in.

```mermaid
stateDiagram-v2
[*] --> Discovered: Module folder found on scan

Discovered --> Invalid: Missing files\nor broken structure
Discovered --> Runnable: Passes structural\nvalidation

Runnable --> Verified: User runs\nAI security check
Runnable --> Enabled: User enables\n(accepts risk)

Verified --> Enabled: User enables

Invalid --> [*]: Cannot be enabled

Enabled --> Disabled: User disables
Disabled --> Enabled: User enables
```

---

## Resource Tier State Diagram

Shows how the application responds to available RAM when loading a model.

```mermaid
stateDiagram-v2
[*] --> Check: User requests model load

Check --> Optimal: RAM ≥ 2x model size\nFull performance
Check --> Recommended: RAM ≥ 1.3x model size\nSlight slowdown
Check --> WillSwap: RAM ≥ 0.7x model size\nDisk paging\nSSD wear warning
Check --> Blocked: RAM < 0.3x model size\nCannot load

Optimal --> Loaded: Auto-configure\nand load
Recommended --> Loaded: Warn user\nthen load
WillSwap --> Acknowledged: User checks\nall 3 warnings
Acknowledged --> Loaded: Load with\nmmap enabled
Blocked --> [*]: Hard block\nSuggest alternatives
```
