# Stop adding cache savings to your token budget twice

> The four numbers your agent observability tool should show you
> separately — and a local CLI that does.

There's a [bug in Langfuse](https://github.com/langfuse/langfuse/issues/12306)
that's been open since Q1: when you trace an Anthropic call that hits the
prompt cache, the cached tokens get double-counted. The OpenTelemetry
GenAI semantic convention says `gen_ai.usage.input_tokens` is *total*
input (cached + uncached). pydantic-ai follows that convention. Langfuse
then adds the cache fields again on top. The graph says you're burning
twice the tokens you actually are.

This isn't a Langfuse-specific story. Most agent observability tools
collapse the four columns Anthropic charges *differently* into one
"input tokens" number. That's a problem because **prompt caching changes
the cost calculation by an order of magnitude.** A token read from a
5-minute cache costs 0.1× the base rate. A token written into the cache
costs 1.25×. Collapse those into one number and you can't tell whether an
agent is spending well or paying through the nose.

[ContextMesh](https://github.com/Alivanroy/ContextMesh) is a local CLI
that doesn't collapse them.

## The four numbers, kept separate

ContextMesh wraps a coding agent — `claude`, `codex`, `aider`, or a
home-grown loop — and parses its tool-call stream into a typed SQLite
ledger. As of v0.3.0, three adapters ship:

- **Claude Code** — parses `claude --output-format stream-json` into one
  row per assistant turn, plus a synthetic row whenever a `tool_result`
  looked like distillable test output.
- **Codex CLI** — parses `codex exec --json` JSONL (`item.completed`
  shell events, `turn.completed` usage).
- **Aider** — parses `.aider.chat.history.md`, picks up the
  `Tokens: … sent, … received` summary lines, detects pytest pass/fail
  in the tool blockquotes.

Every ledger row keeps these columns *separate*, never summed:

| Column | What it is | Anthropic price |
|---|---|---|
| `tokens_provider_input` | Uncached input | 1.0× |
| `tokens_cached_read` | Cache hit | 0.1× |
| `tokens_cached_write` | Cache write | 1.25× |
| `tokens_provider_output` | Model output | output rate |
| `tokens_avoided` | Saved on top by ContextMesh's own compression | — |

`contextmesh dashboard` renders them per task. `contextmesh metrics
--json` emits them for scripting. Each row also carries an
auto-detected `outcome_class` — `passed | regressed | unchanged |
aborted | unknown` — set from pytest output seen in the trace.

## One number to track over time

Underneath the columns is a deliberately strict metric:

> **`useful_context_ratio` = (tokens spent on tasks whose final
> `outcome_class` was `passed`) / (tokens spent on all tasks)**

A task whose final outcome is anything other than `passed` contributes
zero useful tokens. The metric rewards *finishing*, not trying, and
penalises wasted spend completely. It's token-weighted across tasks, so
a 100k-token failure counts more than a 200-token success. Full
definition, and the softer variants considered and rejected, in
[docs/metrics.md](https://github.com/Alivanroy/ContextMesh/blob/v0.3.0/docs/metrics.md).

v0.3.0 adds the cost-weighted companion: supply per-million-token prices
via env vars and the ledger produces `useful_cost_ratio`,
`wasted_cost_usd`, and `cost_per_passed_task_usd`. Token volume stays the
source of truth; dollar figures are explicit and reproducible
([docs/cost_metrics.md](https://github.com/Alivanroy/ContextMesh/blob/v0.3.0/docs/cost_metrics.md)).

## Two compression mechanisms, measured

ContextMesh's ledger is the output of two optimizations applied before
the agent sees the prompt:

1. **Per-task seen-cache.** Symbol packets the agent already received
   this task become ~12-token `symbol_ref` shells next turn. On a 3-turn
   refactor of ContextMesh's own repo this cut cumulative input by
   **39.3%** (35,124 → 21,305 tokens).
2. **Critical-path focus.** When the agent receives a `test_failure`,
   ContextMesh inlines the body of the failing symbol and *pins* it, so
   the seen-cache can't downgrade it on the next turn — the agent never
   loses the one piece of context that matters while looping on a bug.

Both are *additive* to Anthropic's prompt cache: Anthropic caches the
prefix, ContextMesh shrinks what's in it. The cache columns show the
first; the `avoided` column shows the second.

## The cross-agent leaderboard

`benchmarks/harness.py` runs N tasks × M agents and writes one row per
pair. Every row is labelled by fixture provenance so the table never
overstates how real a number is:

```
Task               Agent        Source                Outcome    Input  CacheR  CacheW  Output  Useful
reset-bug-failing  claude-code  synthetic-real-shape  regressed  7,260  18,240   3,600     680    0.0%
reset-bug-failing  aider        captured-live         regressed  1,580       0       0     180    0.0%
reset-bug-failing  codex-cli    handcrafted           regressed 16,640   8,192       0      97    0.0%
reset-bug-fixed    claude-code  synthetic-real-shape  passed     5,400  12,160       0     240  100.0%
reset-bug-fixed    aider        captured-live         passed     1,309       0       0     160  100.0%
reset-bug-fixed    codex-cli    captured-live         passed     8,893  21,760       0      61  100.0%
```

`captured-live` rows are real agent runs — the Aider rows from a real
`aider --model ollama_chat/llama3:latest` session against a buggy
`verify_reset_token`. The current market-positioning snapshot vs
LangSmith / Langfuse / Phoenix / Helicone / Braintrust / MLflow is in
[benchmarks/market_comparison_2026-05-16.md](https://github.com/Alivanroy/ContextMesh/blob/v0.3.0/benchmarks/market_comparison_2026-05-16.md).

## What it is, and what it isn't

**It is:** a local-first observability layer for coding-agent context
spend. A strict metric, three adapters, a terminal dashboard, a
cross-agent harness. 80 tests, MIT, no telemetry, no cloud account, no
embeddings, no SaaS. SQLite and one CLI.

**It isn't:** a competitor to Aider, Claude Code, Cursor, or Repomix —
it's the *meter* on top of them. It isn't trying to be LangSmith or
Langfuse either; those are full app-observability suites. ContextMesh is
narrow on purpose: *measure which coding-agent context produced verified
work, and what it cost.*

Honest status: alpha. The benchmark is still fixture-scale; v0.4 is the
real multi-task benchmark. OpenCode and Cursor adapters are next.

## Where to start

```bash
git clone https://github.com/Alivanroy/ContextMesh
cd ContextMesh
pip install -e .

contextmesh init
contextmesh trace --task-id my-task --agent claude-code -- \
    claude -p "fix the failing test" --output-format stream-json --verbose
contextmesh dashboard
```

Adding an agent is one module: the
[`Adapter` ABC](https://github.com/Alivanroy/ContextMesh/blob/v0.3.0/contextmesh/adapters/base.py)
is ~30 lines, the concrete adapters ~120–160. Issues and PRs welcome.

Repo: [github.com/Alivanroy/ContextMesh](https://github.com/Alivanroy/ContextMesh).
Tests pass on Python 3.10 / 3.11 / 3.12 in CI.
