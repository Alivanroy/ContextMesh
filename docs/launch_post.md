# Stop adding cache savings to your token budget twice

> The four numbers your agent observability tool should be showing you,
> and what we built when we got tired of waiting.

There's a [known bug in Langfuse](https://github.com/langfuse/langfuse/issues/12306)
that's been open since Q1: when you trace an Anthropic call that hits the
prompt cache, Langfuse double-counts the cached tokens. The OpenTelemetry
GenAI semantic convention says `gen_ai.usage.input_tokens` is *total*
input (cached + uncached). pydantic-ai follows that convention. Langfuse
then adds the cache fields again on top. You get a graph that says you're
burning twice as many tokens as you actually are.

This isn't a Langfuse-specific story. Every agent observability tool I've
looked at — AgentOps, Helicone, the OpenSearch GenAI integration — treats
the four columns Anthropic actually charges differently as one number.
That's a problem because **prompt caching changes the cost calculation by
an order of magnitude.** A token read from a 5-minute cache costs 0.1× the
base rate. A token written into the cache costs 1.25×. If your dashboard
collapses these into "input tokens", you can't tell whether your agent is
spending well or paying through the nose.

So I built [ContextMesh](https://github.com/Alivanroy/ContextMesh).

## The four numbers it shows side by side

ContextMesh is a CLI that wraps any agent — `claude`, `aider`, `codex`,
your home-grown loop — and parses its tool-call stream into a typed
ledger. Two adapters ship today:

- **Claude Code** parses `--output-format stream-json` into one row per
  assistant turn, plus a synthetic row whenever a `tool_result` looked
  like distillable test output.
- **Aider** parses `.aider.chat.history.md`, picks up the `Tokens: …
  sent, … received` summary lines (whether or not Aider quoted them),
  and detects pytest pass/fail in the tool blockquotes.

Each row in the ledger keeps these columns *separate*:

| Column | What it is |
|---|---|
| `tokens_provider_input` | Tokens you paid full price for |
| `tokens_cached_read` | Tokens you got at 0.1× (cache hit) |
| `tokens_cached_write` | Tokens you paid 1.25× to write into the cache |
| `tokens_provider_output` | What the model wrote back |
| `tokens_avoided` | What ContextMesh saved on top, by distilling tool outputs and de-duping seen packets |

Plus an outcome class — `passed | regressed | unchanged | aborted | unknown`
— that the adapter sets automatically when it sees pytest output go from
failing to passing in the trace.

Here's what `contextmesh dashboard` looks like after a single agent run:

```
ContextMesh — local observability
  Tasks tracked              1
  Tokens billed (estimated)  43,118
  Tokens avoided             21,440

  Provider input tokens      14,520
  Provider output tokens      1,360
    cache reads (cheap)      36,480   (0.1× rate — actual savings)
    cache writes (1.25×)      7,200   (paid this turn, amortizes later)
  Cache hit rate             62.7%
  Avoidance ratio            33.2%
  Useful-context ratio       100.0%

Provider tokens per task
  Task         Outcome  Input   Cache R  Cache W  Output  Avoided  Cache hit
  reset-bug    passed   7,260   18,240    3,600     680       20     62.7%
```

That's the screenshot every team running coding agents at scale should be
able to make. Right now they can't.

## A single number to track over time

Underneath the four columns is a strict metric:

> **`useful_context_ratio` = (tokens spent on tasks whose final
> `outcome_class` was `passed`) / (tokens spent on all tasks)**

It is deliberately strict. A task whose final outcome is anything other
than `passed` contributes zero useful tokens. The metric rewards
*finishing*, not trying. It penalises wasted spend completely. Across
tasks, it's token-weighted, so a 100k-token task that fails counts more
than a 200-token task that passes. (Definition + the three softer
versions we considered and rejected: [docs/metrics.md](https://github.com/Alivanroy/ContextMesh/blob/main/docs/metrics.md).)

Two compounding mechanisms live on the input side, before the agent sees
the prompt:

1. **A per-task seen-cache.** Symbol packets the agent has already
   received during this task become 12-token `symbol_ref` shells on the
   next turn. Across 3 turns of a real refactor on the ContextMesh repo,
   this saved **39%** of cumulative input.
2. **Critical-path focus.** When the agent receives a `test_failure`,
   ContextMesh inlines the body of the symbol containing the failing
   line and pins it. The compressor will not downgrade it the next turn,
   even though the agent has technically seen it. So you don't lose the
   one piece of context that matters when an agent loops on the same
   bug.

Both mechanisms are *additive* to Anthropic's prompt cache. Anthropic
caches the prefix; ContextMesh shrinks what's in the prefix. The
"avoided" column shows the second part. The cache columns show the
first.

## The cross-agent benchmark

The real point of separating the columns is that you can finally compare
agents on equivalent terms. `benchmarks/harness.py` runs N tasks × M
agents and writes one JSON row per pair:

```
Task                       Agent          Outcome      Input  CacheR  CacheW  Output  Avoided  Useful%
reset-bug-failing          claude-code    regressed    7,260  18,240   3,600     680       20    0.0%  ✓
reset-bug-failing          aider          passed       5,300       0       0     344        0  100.0%  ✗
reset-bug-fixed            claude-code    passed       5,400  12,160       0     240        0  100.0%  ✓
reset-bug-fixed            aider          passed       1,309       0       0     160        0  100.0%  ✓
```

(The `✗` on `reset-bug-failing/aider` is the harness flagging that the
adapter classified the task `passed` when the expected outcome was
`regressed` — i.e., the harness caught its own fixture being one-sided.
That's the kind of self-check observability is supposed to do.)

The Aider rows are real numbers from a real Ollama-driven `aider --model
ollama_chat/llama3:latest` session captured against a buggy
`verify_reset_token`. Not synthetic.

## What this is, and what it isn't

**It is**: an open-source observability layer with a strict metric, two
working adapters, and a dashboard that shows what your agent actually
spent. 63 tests, MIT, no telemetry, no cloud account, no embeddings, no
SaaS dashboard. Local SQLite, one binary.

**It isn't**: a competitor to Aider, Claude Code, Cursor, Sourcegraph
Cody, or Repomix. It's the *meter* you put on top of them. It also isn't
trying to be Langfuse — Langfuse is for general-purpose LLM apps;
ContextMesh is opinionated for coding agents and the metric reflects
that.

The pivot from "context optimization layer" to "observability layer for
coding agents" is recent and deliberate. The original [plan.md](https://github.com/Alivanroy/ContextMesh/blob/main/plan.md)
listed an MCP proxy, RAG optimization, and a security layer for v0.3–
v0.5. We cut all three because Anthropic's MCP Tool Search and prompt
caching now do most of what those would have done. What's left is the
piece nobody else is doing well: showing where the tokens go.

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

Want to wire your agent into the harness? The
[`Adapter` ABC](https://github.com/Alivanroy/ContextMesh/blob/main/contextmesh/adapters/base.py)
is ~30 lines; the Claude Code adapter is 159, the Aider one is 130.
Issues and PRs welcome.

The repo is at [github.com/Alivanroy/ContextMesh](https://github.com/Alivanroy/ContextMesh).
The `useful_context_ratio` definition is in
[docs/metrics.md](https://github.com/Alivanroy/ContextMesh/blob/main/docs/metrics.md).
The test suite passes on Python 3.10 / 3.11 / 3.12 in CI.

Now go look at where your agent's tokens are going. You might be
surprised.
