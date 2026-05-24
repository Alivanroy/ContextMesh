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
[![tests: 115](https://img.shields.io/badge/tests-115%20passing-brightgreen.svg)](https://github.com/Alivanroy/ContextMesh/actions)
[![version: v0.3.0](https://img.shields.io/badge/version-v0.3.0-blue.svg)](https://github.com/Alivanroy/ContextMesh)

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

For v0.3 work, the same ledger can also produce optional cost-weighted
metrics such as `$ / passed task` when you provide model prices; see
[docs/cost_metrics.md](docs/cost_metrics.md).

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

# 4. Or wrap Codex CLI
contextmesh trace --task-id reset-bug --agent codex-cli -- \
    codex -a never exec --json --sandbox workspace-write \
    "fix the failing test"

# 5. Or wrap an Aider session via its chat history
aider --model claude-sonnet ...
contextmesh trace --task-id reset-bug --agent aider --silent \
    --from-file .aider.chat.history.md -- noop

# 6. See where the tokens went
contextmesh dashboard
contextmesh metrics --task-id reset-bug --json
contextmesh context record --task-id reset-bug --step 1 \
    --ref symbol:verify_reset_token --status selected \
    --source-type symbol --reason "directly covers failing test"
contextmesh context record --task-id reset-bug --step 1 \
    --ref file:docs/old-reset.md --status rejected \
    --source-type doc --reason "stale reset-token flow"
contextmesh context audit --task-id reset-bug
contextmesh context schema inspection
contextmesh inspect --task-id reset-bug
contextmesh diff --left reset-bug-failed --right reset-bug-passed
contextmesh export-langfuse --task-id reset-bug --trace-id lf-trace-id
contextmesh export-otel --task-id reset-bug --service-name agent-platform
contextmesh export-team --task-id reset-bug --target slack
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
| `contextmesh context record` | Record available, selected, or rejected context candidates |
| `contextmesh context show --task-id TASK` | Show context candidates and selection reasons for a task |
| `contextmesh context audit --task-id TASK` | Flag candidate selection risks such as low relevance, duplicate refs, large context, or sensitive refs |
| `contextmesh context schema [NAME]` | Print JSON Schema for context intelligence payloads |
| `contextmesh inspect --task-id TASK` | Inspect context quality, selected refs, recommendations, and Langfuse metadata |
| `contextmesh diff --left A --right B` | Compare selected context and quality between two tasks |
| `contextmesh export-langfuse --task-id TASK` | Emit a trace-ready Langfuse metadata payload |
| `contextmesh export-otel --task-id TASK` | Emit an OTLP/JSON-shaped payload with context inspection spans and selected/rejected context events |
| `contextmesh export-team --task-id TASK --target TARGET` | Emit Slack, Teams, Linear, Jira, or GitHub-ready JSON |
| `contextmesh waste --threshold N` | List packet hashes sent across > N tasks |
| `contextmesh ledger show \| record` | View / append ledger entries |
| `contextmesh index [path]` | Walk repo, persist file hashes & symbols |
| `contextmesh run <cmd...>` | Distill pytest / jest / shell output into one packet |
| `contextmesh export-context --task ...` | Bundle packets for an agent |
| `contextmesh expand <file> <symbol>` | Print a symbol's exact body on demand |
| `contextmesh reset-cache` | Clear the per-task seen-cache |

## Roadmap

- **v0.2** — observability layer with two real adapters
  (Claude Code stream-json, Aider chat history). Ledger, metrics,
  dashboard, delta cache, critical-path focus, `contextmesh trace`.
- **v0.3 (current)** — Codex CLI adapter, cost-weighted metrics
  (`useful_cost_ratio`, `$ / passed task`), and safer concurrent first-run
  state setup.
- **v0.4** — published benchmark: useful-context ratio across 4+ agents
  on 10–20 tasks, including SWE-bench Lite cases. Real cache numbers,
  no synthetic fixtures in the headline rows.
- **v0.5** — packet schema as a portable spec (JSON Schema + Protobuf)
  so other tools can write into the same ledger format. OpenTelemetry
  GenAI export path.
- **v0.6** — context intelligence layer: inspect selected context, score
  context quality, recommend fixes, and emit Langfuse-ready trace metadata.

The earlier `plan.md` listed MCP proxy, RAG optimization, and a security
layer. Those are deferred indefinitely — Anthropic's MCP Tool Search
already solves the MCP token tax inside Claude Code, and the cost of
splitting attention across four product surfaces is not worth it.

See [plan.md](plan.md), [docs/architecture.md](docs/architecture.md),
[docs/context_intelligence_v1.md](docs/context_intelligence_v1.md), and
[docs/real_life_agent_scenarios.md](docs/real_life_agent_scenarios.md) for detail.

## Demo

```bash
bash demo/run_demo.sh
```

Seeds a tiny repo with a buggy `verify_reset_token`, runs `pytest`
through the distiller, and exports a focused packet bundle for the agent.

## Enterprise Agentic Example

```bash
bash examples/enterprise_agentic/run_enterprise_demo.sh
```

Runs a deterministic enterprise support-risk agent for a regulated-finance
customer escalation. The agent selects SLA, contract, runbook, and security
context, rejects stale/sensitive context, produces a P1 mitigation plan, and
exports ContextMesh inspection, audit, Langfuse, OpenTelemetry, Slack, and
Jira payloads.

## Enterprise Office RAG Example

```bash
bash examples/enterprise_rag_office/run_office_rag_demo.sh
```

Runs a real mixed-document RAG flow over generated Word `.docx` contract and
security notes plus an Excel `.xlsx` SLA/risk workbook. The agent selects
renewal-critical paragraphs and worksheet rows, rejects stale and irrelevant
office context, produces a conditional approval, and exports ContextMesh
inspection, audit, Langfuse, OpenTelemetry, Slack, and Jira artifacts.

## Benchmarks

```bash
python3 benchmarks/harness.py
python3 benchmarks/multi_turn_delta.py
```

The default harness compares Claude Code, Aider, and Codex CLI fixtures on
the same passing/failing reset-token tasks and labels each row by fixture
provenance. The current market snapshot lives in
[benchmarks/market_comparison_2026-05-16.md](benchmarks/market_comparison_2026-05-16.md).

## Integrations

Drop-in guides under [`docs/integrations/`](docs/integrations/):

- [Claude Code](docs/integrations/claude_code.md)
- [Codex CLI](docs/integrations/codex_cli.md)
- [Cursor](docs/integrations/cursor.md)

## Contributing

Pull requests welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). v0.3 ships
adapters for Claude Code (`stream-json`), Codex CLI (`exec --json`), and
Aider (`.aider.chat.history.md`). The fastest ways to help right now:

1. **Add the next adapter** — OpenCode or Cursor's local conversation log.
   The base ABC is ~30 LoC, the existing concrete
   adapters are ~150 LoC each, and there's a fixture-based test pattern
   to copy in `tests/test_adapter_*.py`.
2. **Add a tree-sitter language** (TS / Go / Rust) to the indexer so the
   `expand`/focus path works on polyglot repos.
3. **Run `contextmesh trace` against your real workflow** and open an
   issue with a screenshot of the dashboard or a failing-trace bug.
4. **Broaden the benchmark**: add richer coding tasks and compare Claude
   Code, Codex CLI, Aider, OpenCode, and Cursor on identical fixtures.

## License

MIT — see [LICENSE](LICENSE).
