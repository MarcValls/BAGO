---
description: Switch Pi to the OpenAI provider and reasoning model used by Codex CLI
argument-hint: "[reasoning-level]"
---

Use the OpenAI provider configured in `.pi/settings.json` (mirrors the Codex CLI `model_provider = "openai"` setup). Resolve the API key from `OPENAI_API_KEY` or Pi's `/login openai` flow; never embed secrets.

Switch the active model to the best available OpenAI reasoning model and set the thinking level to ${1:-high} (Codex CLI uses `model_reasoning_effort = "high"` by default). Prefer `o3-mini` or `o1` when the task needs extended reasoning; fall back to `gpt-4o` for fast, low-cost turns.

Before executing any BAGO-sensitive step, re-read `.bago/runtime/ACTIVE_HANDOFF.md` and `AGENTS.md`.
