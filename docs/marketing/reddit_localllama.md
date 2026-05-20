# Reddit — r/LocalLLaMA

Post as a text post (self post), not a link. r/LocalLLaMA tolerates
project posts when they're technical, honest, and local-first — lead
with the local angle hard. Best time: weekday mornings US time. Flair:
"Resources" or "Tutorial | Guide" if available, otherwise none.

---

## Title

```
I built a local-first CLI that shows where your coding agent's tokens actually go (works with Ollama-driven Aider, Claude Code, Codex CLI)
```

Alternative if that's too long for the field:

```
Local-first observability for coding agents — token spend + cache usage + pass/fail, no SaaS
```

---

## Body (markdown)

Most LLM observability tooling assumes you're calling a hosted API and
piping traces to a hosted dashboard. If you run agents locally — Aider
pointed at Ollama, a home-grown loop, Codex CLI — you mostly fly blind on
*where the tokens went* and *whether the context you fed in actually
produced working code*.

**ContextMesh** is a local CLI for that. SQLite on disk, no account, no
telemetry, no network calls of its own. MIT.

It wraps a coding agent and parses its tool-call stream into a ledger:

- one row per agent turn
- token columns kept **separate** — uncached input, cache read, cache
  write, output (the four things Anthropic prices differently; most
  tools mash them into one number, and Langfuse currently double-counts
  the cached ones — langfuse#12306)
- an auto-detected outcome per task: `passed / regressed / unchanged /
  aborted` pulled from pytest output in the trace

Then it computes one strict number:

> **useful_context_ratio** = tokens spent on tasks that ended `passed` /
> tokens spent on all tasks

A task that doesn't finish scores zero. It measures whether your spend
turned into working code, not just how big the spend was.

### Why this fits a local setup

- **No SaaS.** The "dashboard" is a terminal command (`contextmesh
  dashboard`). State is a SQLite file in `.contextmesh/`.
- **Works with Ollama-driven agents.** The Aider adapter was built and
  tested against real `aider --model ollama_chat/llama3:latest` sessions
  fixing a real bug. Those rows in the benchmark are labelled
  `captured-live` — actual runs, not mocks.
- **Cost metrics are opt-in and local.** Feed per-million-token prices
  via env vars and it derives `useful_cost_ratio` and
  `cost_per_passed_task_usd`. If you run local models the "cost" is your
  own electricity/time — set the prices to whatever you want, or ignore
  it and stay on token volume.

### Two compression tricks, and they're measured

1. A per-task cache: a code symbol the agent already saw becomes a
   ~12-token reference next turn. On a 3-turn refactor that cut
   cumulative input **39%** (35,124 → 21,305 tokens).
2. Critical-path focus: when a test fails, it inlines the failing
   function's body and pins it so the cache can't strip it while the
   agent loops on the bug.

### Honest status

Alpha. One contributor. 80 tests, CI on Python 3.10–3.12. The benchmark
is small — 2 tasks × 3 agents — and every row is labelled by how real it
is (`captured-live` / `synthetic-real-shape` / `handcrafted`). A proper
multi-task benchmark is the next milestone. I'm posting now because I'd
rather get the metric design torn apart early than late.

Repo (MIT): https://github.com/Alivanroy/ContextMesh

Quick start:

```bash
git clone https://github.com/Alivanroy/ContextMesh && cd ContextMesh
pip install -e .
contextmesh init
contextmesh trace --task-id smoke --silent --from-file \
    tests/fixtures/aider_real_llama3.md -- noop
contextmesh dashboard
```

Specific thing I want feedback on: the metric scores a task **zero**
unless its tests end up passing — no partial credit. Too harsh? The
rejected softer variants are in `docs/metrics.md`. Tell me if I got it
wrong.

---

## Comment-reply notes

- If asked "does it need the cloud / send data anywhere" — hard no, say
  it plainly and point at the lack of any network code.
- If asked about non-Python repos — the trace/metric layer is
  language-agnostic (it parses the agent stream); only the optional
  symbol-expansion path is Python-only today.
- If someone wants an OpenCode or LM Studio adapter — that's exactly the
  contribution the repo wants; point them at `docs` → "Adding a new
  agent adapter" and the ~30-line `Adapter` base class.
- Do not argue if downvoted early. Answer technical questions only.
