# ContextMesh

> **See where your agent's tokens go. Prove which context produced the fix.**

ContextMesh is the open-source observability layer for AI coding agents.
Every step an agent takes — every file it reads, every test it runs, every
packet it receives — gets logged to a local ledger with one number that
matters most:

> **`useful_context_ratio`** — the fraction of tokens you spent on tasks
> that actually finished.

[![CI](https://github.com/Alivanroy/ContextMesh/actions/workflows/ci.yml/badge.svg)](https://github.com/Alivanroy/ContextMesh/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
![status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)
[![tests: 63](https://img.shields.io/badge/tests-63%20passing-brightgreen.svg)](https://github.com/Alivanroy/ContextMesh/actions)

---

## Why

Every coding agent — Claude Code, Codex, Cursor, Aider, your home-grown
agent — burns tokens you can't see. Repeated file reads, redundant tool
schemas, full-text logs the model will never use. Anthropic's prompt cache
helps, but only inside Claude. Aider's repo map helps, but only inside
Aider. Nobody publishes a single agent-agnostic number for *was that
context worth what you paid?*

ContextMesh does. The `useful_context_ratio` metric (defined precisely in
[docs/metrics.md](docs/metrics.md)) sits on top of a typed, evidence-backed
ledger that any agent can write to.

## Install

```bash
git clone https://github.com/Alivanroy/ContextMesh.git
cd ContextMesh
pip install -e .
```

Requires Python 3.10+.

## Quick start

```bash
# 1. One-time: set up the local state directory
contextmesh init

# 2. Try it on a captured session (no auth required)
contextmesh trace --task-id smoke --silent --from-file \
    tests/fixtures/claude_code_fixed_session.jsonl -- noop

# 3. Or wrap a real Claude Code run end-to-end
contextmesh trace --task-id reset-bug --agent claude-code -- \
    claude -p "fix the failing test" --output-format stream-json --verbose

# 4. Or wrap an Aider session via its chat history
aider --model claude-sonnet ...
contextmesh trace --task-id reset-bug --agent aider --silent \
    --from-file .aider.chat.history.md -- noop

# 5. See where the tokens went
contextmesh dashboard
contextmesh metrics --task-id reset-bug --json
```

For workflows where you'd rather log each agent step manually, see
[`contextmesh ledger record`](docs/architecture.md) — the same ledger
schema, just populated by hand.

The dashboard shows four panels:

```
ContextMesh — local observability
  Tasks tracked              17
  Tokens billed              43,118
  Tokens avoided             21,440
    via delta compression    13,920
    via critical-path focus   7,520
  Avoidance ratio            33.2%
  Useful-context ratio       71.4%
  Outcomes                   passed=12  regressed=2  unchanged=3

Tasks (sorted by billed tokens)
  reset-bug   3 steps  passed     billed=4,210   avoided=2,140  useful=100%
  perf-fix    7 steps  regressed  billed=11,332  avoided=4,801  useful=  0%
  ...

Recent steps                            Billed (red) vs Avoided (green)
  reset-bug  step 1  passed     4,210   ███████░  ███░░░░░
  perf-fix   step 7  regressed  9,400   ████████  █░░░░░░░
  ...

Repeat waste (hashes seen by > 3 tasks)
  cd5ac08    tasks=8   ~wasted=560 tokens
  daf83f24   tasks=6   ~wasted=400 tokens
```

## Two mechanisms behind the metric

ContextMesh's ledger is more than a logger. It's the output of two
optimizations the agent uses on the way in:

1. **Per-task delta cache.** A `SeenPacket` table records every packet
   hash an agent has already received for a given task id. On the next
   turn, those `symbol` packets become tiny `symbol_ref` shells. Counted
   into `tokens_kept_compressed`.

2. **Critical-path focus.** When the agent receives a `test_failure`
   packet, ContextMesh inlines the body of the failing symbol and pins
   it — the compressor will not downgrade it on the next turn, even
   though the agent has seen it before. Counted into `tokens_kept_pinned`.

Both mechanisms are exposed via [`export-context --failures`](docs/integrations/),
but they're not the headline anymore. The headline is what you can
*measure*.

## Commands

| Command | What it does |
| --- | --- |
| `contextmesh init` | Create `.contextmesh/` and add it to `.gitignore` |
| `contextmesh dashboard` | **Front door.** Render overview, per-task table, timeline, waste view |
| `contextmesh metrics [--task-id]` | Print useful-context ratio + breakdown |
| `contextmesh waste --threshold N` | List packet hashes sent across > N tasks |
| `contextmesh ledger show \| record` | View / append ledger entries |
| `contextmesh index [path]` | Walk repo, persist file hashes & symbols |
| `contextmesh run <cmd...>` | Distill pytest / jest / shell output into one packet |
| `contextmesh export-context --task ...` | Bundle packets for an agent |
| `contextmesh expand <file> <symbol>` | Print a symbol's exact body on demand |
| `contextmesh reset-cache` | Clear the per-task seen-cache |

## Roadmap

- **v0.2 (current)** — observability layer with two real adapters
  (Claude Code stream-json, Aider chat history). Ledger, metrics,
  dashboard, delta cache, critical-path focus, `contextmesh trace`.
- **v0.3** — adapters #3 and #4: Codex CLI / OpenCode (subprocess +
  stream events) and Cursor (local SQLite conversation log).
- **v0.4** — published benchmark: useful-context ratio across 4+ agents
  on 10–20 tasks, including SWE-bench Lite cases. Real cache numbers,
  no synthetic fixtures in the headline rows.
- **v0.5** — packet schema as a portable spec (JSON Schema + Protobuf)
  so other tools can write into the same ledger format. OpenTelemetry
  GenAI export path.

The earlier `plan.md` listed MCP proxy, RAG optimization, and a security
layer. Those are deferred indefinitely — Anthropic's MCP Tool Search
already solves the MCP token tax inside Claude Code, and the cost of
splitting attention across four product surfaces is not worth it.

See [plan.md](plan.md) and [docs/architecture.md](docs/architecture.md)
for detail.

## Demo

```bash
bash demo/run_demo.sh
```

Seeds a tiny repo with a buggy `verify_reset_token`, runs `pytest`
through the distiller, and exports a focused packet bundle for the agent.

## Integrations

Drop-in guides under [`docs/integrations/`](docs/integrations/):

- [Claude Code](docs/integrations/claude_code.md)
- [Codex CLI](docs/integrations/codex_cli.md)
- [Cursor](docs/integrations/cursor.md)

## Contributing

Pull requests welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). The fastest
ways to help right now:

1. **Wire a real agent into `contextmesh trace`.** The v0.3 work above —
   one adapter per agent, ~150 LoC each.
2. **Add a tree-sitter language** (TS / Go / Rust) to the indexer.
3. **Run the metric on your repo** and open an issue with a screenshot.

## License

MIT — see [LICENSE](LICENSE).
