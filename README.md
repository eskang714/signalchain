# signal-chain

A desktop application for having personal, private conversations with AI.
Supports local models on your own hardware and cloud services like Claude.
Your data stays on your device.

Capabilities work like a guitar pedalboard: a modular harness of "pedals" you
patch into your signal chain and switch on or off as a conversation needs them.

![Tests](https://github.com/eskang714/signalchain/actions/workflows/ci.yml/badge.svg)

---

## Who This Is For

- People who want to use AI without their conversations stored on someone else's server
- Developers who want to run local models and switch between them easily
- Anyone who uses multiple AI services and wants one consistent interface

---

## What It Does

- Chat with cloud providers (Claude, OpenRouter, Groq, Gemini) and local models via Ollama, all from one application
- Run multiple conversations simultaneously, each with a different model
- Keep all conversation history on your own device
- Shape each conversation with a modular pedalboard of capability pedals (see below)
- Control exactly how much CPU, GPU, and RAM each model uses

---

## The Pedalboard

The pedalboard is signal-chain's modular harness: each capability is a
self-contained **pedal** you switch on or off, the way a guitarist arranges
effects in a signal chain. Patch in only what a conversation needs.

- **Conversation History** — controls how much earlier context is fed back to the model (depth, window, token budget)
- **Markdown Output** — renders the model's replies as formatted markdown
- **Connected Accounts** — manages your provider accounts: what's connected, what's valid, and which models each offers
- **Web Access** — lets a model reach the web for fetches and lookups *(in development)*
- **File Access** — lets a model read files from your machine *(in development)*
- **Clock** — gives the model awareness of the current date and time *(in development)*

Each pedal is global — it applies across every conversation — and toggles independently.

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

V1 features:
- Claude, Ollama, OpenRouter, Groq, and Gemini provider support (local models via Ollama)
- Multi-conversation threading
- Modular pedalboard of capability pedals
- Resource management with hardware compatibility checking
- Local data storage with no required cloud sync

---

## License

Apache 2.0
