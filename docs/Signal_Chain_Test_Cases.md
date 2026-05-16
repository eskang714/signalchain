# Signal Chain - Acceptance Test Cases
**Version:** 1.1  
**Format:** Given / When / Then  
**Purpose:** Code is not accepted unless these pass.

**Test Philosophy:**
Tests must be more rigorous than planning was thorough.
Planning defines the vision. Tests verify the vision exists before users stand in it.
A passing test on an edge case means the application correctly handles reality.
A blocked load with a clear error IS a passing test - correct behavior under impossible conditions.

---

## STARTUP & CONFIGURATION

### TC-01: Fresh Install
**Given** no config file exists  
**When** application launches  
**Then** first-run wizard appears before any other UI  
**And** wizard cannot be skipped  
**And** application does not start until required paths are configured

### TC-02: Valid Config
**Given** a valid config.yaml exists with all required paths  
**When** application launches  
**Then** main UI loads without wizard  
**And** module panel shows discovered modules  
**And** status bar shows connection state

### TC-03: Invalid Config - Missing Path
**Given** config.yaml exists but conversation directory does not exist  
**When** application launches  
**Then** a fix dialog appears (not wizard, not silent failure)  
**And** application offers to create the missing directory  
**And** application does not proceed to main UI until resolved

### TC-04: Low Disk Space
**Given** configured output directory has less than 100MB free  
**When** application launches  
**Then** user sees a disk space warning  
**And** application still starts (warning, not block)

---

## MODULE SYSTEM

### TC-05: Valid Module Discovery
**Given** a folder in modules/user/ contains module.json and module.py  
**And** module passes structural validation  
**When** application starts or user clicks Refresh  
**Then** module appears in module panel with 🟡 RUNNABLE BUT UNVERIFIED  
**And** user can enable it

### TC-06: Invalid Module Discovery
**Given** a folder in modules/user/ is missing module.py  
**When** application starts or user clicks Refresh  
**Then** module appears in module panel with 🔴 INVALID  
**And** toggle to enable is disabled  
**And** error message states specifically what is missing

### TC-07: Module Refresh Without Restart
**Given** main UI is open  
**When** user drops a new valid module folder into modules/user/ and clicks Refresh  
**Then** new module appears in module panel without restarting application

### TC-08: Module Name Collision
**Given** a global module named file_system exists  
**When** user installs a user module also named file_system  
**Then** user module is rejected or auto-renamed  
**And** global module is unaffected  
**And** user receives a clear explanation

### TC-09: Module Isolation Enforcement
**Given** a user module attempts to call functions from another user module directly  
**When** that call is made  
**Then** the call is blocked  
**And** calling module receives an error, not a result  
**And** target module is unaffected

### TC-10: Global Module Cannot Be Disabled
**Given** conversation_history is a global module  
**When** user views the module panel  
**Then** conversation_history has no disable toggle  
**And** it is always active in every conversation

---

## CONVERSATION MANAGEMENT

### TC-11: New Conversation
**Given** at least one provider is configured  
**When** user clicks New Chat  
**Then** model selection dialog appears grouped by provider  
**And** confirming opens a new blank conversation  
**And** new conversation appears in conversation list

### TC-12: Conversation Persistence
**Given** user has an active conversation with messages  
**When** application is closed and reopened  
**Then** conversation appears in conversation list  
**And** all messages are intact  
**And** model selection is preserved

### TC-13: Conversation Search
**Given** multiple conversations exist  
**When** user types in the search box  
**Then** list filters to matching conversations  
**And** clearing search restores full list

### TC-14: Conversation Scale - 1000 Messages
**Given** a conversation has 1000 messages  
**When** user opens it  
**Then** conversation list renders without freeze  
**And** search returns results in under 2 seconds  
**And** switching to this conversation takes under 3 seconds

---

## THREADING & CONCURRENCY

### TC-15: Multiple Simultaneous Conversations
**Given** Chat 1 is generating a response (Ollama)  
**When** user switches to Chat 2 and sends a message  
**Then** Chat 2 starts generating without waiting for Chat 1  
**And** UI remains responsive  
**And** switching back to Chat 1 shows generation still in progress or completed  
**And** no tokens from Chat 1 are lost

### TC-16: Background Generation Continuity
**Given** Chat 1 is generating a long response  
**When** user switches to Chat 2 and waits for Chat 1 to complete  
**Then** Chat 1 generation completes correctly in background  
**And** switching back shows the full completed response

### TC-17: Worker Thread Isolation
**Given** Chat 1 is generating and its worker thread throws an unhandled exception  
**When** the exception propagates  
**Then** UI thread remains responsive  
**And** Chat 2 and Chat 3 are unaffected  
**And** Chat 1 shows a recoverable error state, not a blank or frozen UI

### TC-18: Concurrent Message Send
**Given** a conversation is currently generating  
**When** user sends another message before generation completes  
**Then** application either queues or cancels-and-replaces with defined behavior  
**And** does not produce two simultaneous generations in the same conversation  
**And** behavior is consistent and documented

### TC-19: Three Simultaneous Providers Under Load
**Given** Chat 1 uses Ollama, Chat 2 uses Claude API, Chat 3 uses local GGUF  
**And** all three are generating simultaneously  
**When** Claude API returns a mid-stream error  
**Then** Chat 2 shows error recovery (retry or partial save)  
**And** Chat 1 and Chat 3 continue unaffected  
**And** UI remains responsive throughout

---

## PROVIDERS

### TC-20: Ollama Auto Discovery
**Given** Ollama is running on localhost:11434  
**When** user opens model selection  
**Then** all models from ollama.list() appear without manual configuration

### TC-21: Ollama Not Running
**Given** Ollama is not running  
**When** user attempts to start a conversation using Ollama  
**Then** clear error message appears with actionable fix  
**And** no crash or silent failure

### TC-22: Local Model Addition via Wizard
**Given** user has a valid .gguf file  
**When** user completes the Add Local Model wizard  
**Then** metadata is auto-detected (name, size, context, quantization)  
**And** model appears in local models list and model selector

---

## RESOURCE MANAGEMENT

### TC-23: Architecture Incompatibility - Hard Block
**Given** a model requires AVX-512 or 256-bit instructions  
**And** the system CPU only supports x86-64 base instructions  
**When** user attempts to load the model  
**Then** application blocks loading with a clear incompatibility message  
**And** no workaround is offered  
**And** compatible alternative models are suggested  
**And** this block IS the correct passing behavior for this test

### TC-24: Minimum Requirements Block - Insufficient RAM
**Given** a model requires 8GB RAM  
**And** system has 3GB RAM available  
**When** user attempts to load the model  
**Then** BLOCKED dialog appears with specific reason  
**And** smaller compatible models are suggested  
**And** model does not load  
**And** system does not freeze or crash

### TC-25: Swap Warning - Orange Tier
**Given** a model requires 6GB RAM  
**And** system has 4GB RAM available  
**When** user attempts to load the model  
**Then** orange tier warning dialog appears  
**And** dialog includes SSD wear warning  
**And** expected performance in tokens/sec is shown  
**And** user must check all acknowledgment boxes to proceed  
**And** model does not load until all boxes are checked

### TC-26: CPU Core Affinity Enforcement
**Given** user sets core affinity to cores [0, 1, 2, 3] for a model  
**When** model is loaded and generating  
**Then** model process is restricted to those cores verified by OS process affinity check  
**And** cores outside the set remain available to the system

### TC-27: VRAM Limit Enforcement
**Given** user sets a VRAM limit of 4GB for a model  
**And** full model load would require 8GB VRAM  
**When** model loads  
**Then** GPU allocation does not exceed 4GB  
**And** remaining layers fall back to CPU  
**And** this is reflected in the UI resource display

---

## CONTEXT WINDOW

### TC-28: Recent Messages Limit
**Given** a conversation has 50 messages and context window is set to 20  
**When** user sends a new message  
**Then** only the most recent 20 messages are sent to the model  
**And** total tokens do not exceed provider limit

### TC-29: Token Limit Truncation
**Given** a message would cause token count to exceed provider limit  
**When** that message is sent  
**Then** oldest messages are truncated, not newest  
**And** no error is thrown to the user  
**And** generation proceeds with what fits

---

## ERROR RECOVERY

### TC-30: Mid-Stream Generation Failure
**Given** a generation is in progress  
**When** connection drops mid-stream  
**Then** partial response is saved and displayed  
**And** error indicator appears on the message  
**And** Retry button is shown  
**And** pressing Retry re-attempts the full generation

### TC-31: Module Execution Failure
**Given** AI calls a module that throws an exception  
**When** the exception is thrown  
**Then** generation continues without that module  
**And** a ⚠️ indicator appears on the message  
**And** other modules in the same conversation are unaffected

### TC-32: Rate Limit Auto-Retry
**Given** Claude API returns a 429 rate limit response  
**When** rate limit is hit  
**Then** application shows countdown timer (retry_after seconds)  
**And** request is automatically retried after the wait  
**And** user is not required to manually retry

### TC-33: Unclean Shutdown Recovery
**Given** a conversation is being saved  
**When** application is force-killed mid-write  
**Then** on next launch the conversation file is either intact or flagged as corrupted  
**And** application does not crash on load  
**And** user is informed if data was lost  
**And** all other conversations load normally

### TC-34: Corrupted Conversation File
**Given** a JSON file in the conversations folder is malformed  
**When** application loads  
**Then** that conversation is skipped with an error indicator  
**And** all other conversations load normally  
**And** application does not crash

---

## SECURITY & DATA INTEGRITY

### TC-35: API Key Never Exposed
**Given** a Claude API key is stored  
**When** user inspects config.yaml, application logs, and any UI element  
**Then** API key does not appear in plaintext in any of those locations

### TC-36: Cross-Platform Keychain
**Given** the application runs on macOS, Windows, and Linux  
**When** an API key is stored and retrieved  
**Then** it uses the native OS keychain on each platform  
**And** does not fall back to plaintext storage silently on any platform

### TC-37: Connected Accounts Scope Enforcement
**Given** a user module requests credentials via connected_accounts  
**When** the module calls connected_accounts.get_token("google")  
**Then** a valid token is returned if connected  
**And** connected_accounts does NOT call any Google API itself  
**And** connected_accounts does NOT process any returned data

---

## SETTINGS & PERSISTENCE

### TC-38: Provider Config Persists
**Given** user enters a Claude API key in Settings  
**When** application is restarted  
**Then** API key is retrievable (from OS keychain)  
**And** NOT stored in config.yaml as plaintext

### TC-39: Context Window Setting Applied
**Given** user changes recent message count from 20 to 10 in Settings  
**When** user sends a message in any conversation  
**Then** only 10 recent messages are included in context

---

## FEATURES

### TC-40: File Output via Markdown Module
**Given** markdown_output module is enabled and AI generates a file  
**When** file is created  
**Then** file appears as a clickable card in the chat message  
**And** file exists at configured output directory  
**And** clicking the card opens or previews the file

### TC-41: Input Behavior
**Given** user is in an active conversation  
**When** user presses Enter → message is sent  
**When** user presses Shift+Enter → newline inserted, message not sent  
**And** textarea expands to show new line

### TC-42: Empty Message Rejected
**Given** user is in an active conversation  
**When** user presses Send with an empty or whitespace-only input  
**Then** no message is sent  
**And** no generation is triggered  
**And** UI does not change state

---

## MIGRATION & VERSIONING

### TC-43: Minor Version Migration
**Given** a conversation file has version "1.0" and app is updated to "1.1"  
**When** conversation is loaded  
**Then** conversation loads without error  
**And** file is silently migrated to "1.1" format  
**And** no data is lost

### TC-44: Unknown Future Version
**Given** a conversation file has version "2.0" loaded by a "1.x" app  
**When** conversation is loaded  
**Then** application does not crash  
**And** user is informed the file was created by a newer version  
**And** application offers to skip or attempt to load with known fields only

---

## Acceptance Summary

All 44 test cases must pass for V1.0 code to be accepted.

| Category | Test Cases | Count |
|----------|-----------|-------|
| Startup & Configuration | TC-01 to TC-04 | 4 |
| Module System | TC-05 to TC-10 | 6 |
| Conversation Management | TC-11 to TC-14 | 4 |
| Threading & Concurrency | TC-15 to TC-19 | 5 |
| Providers | TC-20 to TC-22 | 3 |
| Resource Management | TC-23 to TC-27 | 5 |
| Context Window | TC-28 to TC-29 | 2 |
| Error Recovery | TC-30 to TC-34 | 5 |
| Security & Data Integrity | TC-35 to TC-37 | 3 |
| Settings & Persistence | TC-38 to TC-39 | 2 |
| Features | TC-40 to TC-42 | 3 |
| Migration & Versioning | TC-43 to TC-44 | 2 |
| **Total** | | **44** |

---

## Implementation Notes

**Highest risk - implement and test first:**
- TC-17 (worker thread isolation)
- TC-18 (concurrent message send)
- TC-19 (three providers under load)
- TC-23 (architecture incompatibility block)
- TC-33 (unclean shutdown recovery)

**Require mocking or OS-level access:**
- TC-23: mock CPU capability detection
- TC-24/25: mock system memory reporting
- TC-26: verify via psutil process affinity
- TC-27: verify via pynvml VRAM allocation
- TC-33: simulate force-kill during file write
- TC-36: test on all three target OS platforms

**On blocked states as passing tests:**
TC-23 and TC-24 pass when the application correctly blocks.
A hard block with a clear message IS the correct behavior.
Do not mistake a blocked load for a test failure.

**These are acceptance tests, not unit tests.**
Unit tests covering internal function behavior will emerge during implementation.
These 44 define correct observable behavior. Both layers are required.
