# Signal Chain

A desktop application for having personal, private conversations with AI.
Supports local models on your own hardware and cloud services like Claude.
Your data stays on your device.

![Tests](https://github.com/eskang714/signalchain/actions/workflows/ci.yml/badge.svg)

---

## Who This Is For

- People who want to use AI without their conversations stored on someone else's server
- Developers who want to run local models and switch between them easily
- Anyone who uses multiple AI services and wants one consistent interface

---

## What It Does

- Chat with Claude API, Ollama models, and local GGUF models from one application
- Run multiple conversations simultaneously, each with a different model
- Keep all conversation history on your own device
- Extend functionality through a module system (file access, web search, memory)
- Control exactly how much CPU, GPU, and RAM each model uses

---

## What It Is Not

This application does not replace Claude, Ollama, or any other AI service.
It is a coordination layer that works with existing services.
You bring your own API keys. You keep your own data.
We add the interface. The intelligence comes from the models you connect.

---

## Getting Started

If you want to run the application:
→ See [WORKSPACE_SETUP.md](WORKSPACE_SETUP.md)

If you want to understand the architecture:
→ See [CLAUDE.md](CLAUDE.md)

If you want to understand design decisions:
→ See [docs/Signal_Chain_Project_Brief.md](docs/Signal_Chain_Project_Brief.md)

---

## Current Status

Version 1.0 - In development.

Planned V1 features:
- Claude API, Ollama, and local GGUF model support
- Multi-conversation threading
- Module system (conversation history, file system, markdown output, web access)
- Resource management with hardware compatibility checking
- Local data storage with no required cloud sync

---

## License

Apache 2.0
