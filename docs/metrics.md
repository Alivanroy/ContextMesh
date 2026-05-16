# Metrics

ContextMesh's headline output is **useful_context_ratio**, a single number
that answers: *what fraction of the tokens you spent on this task went
into work that actually finished?*

This document defines the metric, its inputs, and its limits.

---

## Inputs

Every step the agent records into the ledger ([LedgerEntry](../contextmesh/storage/db.py))
carries six numeric fields:

| Field | Meaning |
| --- | --- |
| `tokens_estimated` | Tokens billed to the model on this step (input only) |
| `tokens_avoided` | Total tokens *not* sent because of any ContextMesh mechanism |
| `tokens_kept_compressed` | Subset of `tokens_avoided` saved by the per-task delta cache (`symbol` → `symbol_ref`) |
| `tokens_kept_pinned` | Subset of `tokens_avoided` saved by critical-path focus (only the body of the symbol on the failure trace was inlined; the rest stayed compact) |
| `outcome` | Free-text outcome string |
| `outcome_class` | One of `passed`, `unchanged`, `regressed`, `aborted`, `unknown` |

By construction:

```
tokens_avoided ≥ tokens_kept_compressed + tokens_kept_pinned
```

There can be other sources of avoidance (e.g. distilled test output) lumped
into `tokens_avoided` but not yet attributed to a finer bucket.

### How `tokens_estimated` is populated

For events recorded via `contextmesh ledger record` (manual usage),
`tokens_estimated` is the local `cl100k_base` estimate of `context_text`.

For events recorded via `contextmesh trace` (where an adapter parses an
agent's tool-call stream), `tokens_estimated` defaults to the **real
input volume the provider processed**:

```
tokens_estimated = tokens_provider_input + tokens_cached_read + tokens_cached_write
```

That is the raw token count the provider tokenized, not a local guess.
This is what makes `useful_context_ratio` meaningful for traced sessions:
the metric reports against billable provider volume, even though the
four-column dashboard view keeps the components separate so cost can be
weighted later.

Adapters can override this by setting `tokens_estimated` explicitly on a
particular event (the Claude Code adapter does this for its synthetic
"distilled pytest tool_result" steps, where the credited savings live in
`tokens_avoided` and the billed-volume column should be zero).

### Optional cost weighting

Cost metrics are disabled until you provide per-million-token prices via
environment variables. See [cost_metrics.md](cost_metrics.md) for the exact
settings.

When configured, ContextMesh reports `estimated_cost_usd`,
`useful_cost_ratio`, `wasted_cost_usd`, and `cost_per_passed_task_usd`.
These use the same final-outcome rule as `useful_context_ratio`: passed
tasks get useful credit; non-passing tasks count as waste.

---

## Definitions

### Per-task

For task `T` with steps `s₁ … sₙ`:

```
billed(T)         = Σᵢ sᵢ.tokens_estimated
avoided(T)        = Σᵢ sᵢ.tokens_avoided
raw_baseline(T)   = billed(T) + avoided(T)
final_outcome(T)  = sₙ.outcome_class
useful(T)         = billed(T)   if final_outcome(T) == "passed"
                    0           otherwise
```

```
useful_context_ratio(T) = useful(T) / billed(T)
                        ∈ {0, 1}        (per task)
avoidance_ratio(T)      = avoided(T) / raw_baseline(T)
                        ∈ [0, 1]
```

### Aggregate

Across the set of all tasks `𝒯`, both ratios are token-weighted:

```
aggregate_useful_context_ratio = Σ useful(T)  / Σ billed(T)
aggregate_avoidance_ratio       = Σ avoided(T) / Σ raw_baseline(T)
```

A token-weighted average means a 100k-token task that fails counts more
against the ratio than a 200-token task that passes, which is the right
incentive: the metric should track wasted spend, not raw counts.

---

## Why "passed only"

The strict `passed-or-zero` rule is deliberate. Three softer versions were
considered and rejected:

1. **Crediting `unchanged` partially** — invites gaming. An agent that
   writes nothing always lands in `unchanged`.
2. **Step-level crediting** — gives credit to intermediate steps even when
   the task aborted. We measure outcomes, not effort.
3. **Subjective quality scores** — would require a judge model and break
   reproducibility across providers.

The current rule means `useful_context_ratio` is **conservative** and easy
to compare across agents. A score of 0.6 means you finished tasks worth
60% of your token spend; a score of 0.95 means you nailed nearly all of
it.

---

## Outcome classes

| Class | When to use |
| --- | --- |
| `passed` | Tests / acceptance criteria pass after this step |
| `unchanged` | No code changed, or tests in same state as before |
| `regressed` | Tests that previously passed now fail |
| `aborted` | Agent gave up, hit context limit, or was cancelled |
| `unknown` | No verification happened |

Only the `outcome_class` of the **last** step in a task is used for the
ratio. Intermediate-step outcomes are recorded for later analysis but do
not affect the metric.

---

## What this metric is not

- **Not a quality score.** A passing task can ship a hack. We measure
  spend efficiency, not code quality.
- **Not a replacement for SWE-bench.** Use a real benchmark to measure
  capability; use this to measure cost.
- **Not provider-comparable in absolute terms.** Token counters differ
  across providers (`cl100k_base` is a baseline, not ground truth). Use
  the metric for *relative* comparisons within a single provider/agent.

---

## Reading the dashboard

Run `contextmesh dashboard`. Three panels matter:

1. **Overview** — `aggregate_useful_context_ratio` is the headline.
   `aggregate_avoidance_ratio` is the percentage of would-be raw context
   that ContextMesh avoided sending.
2. **Tasks** — sortable per-task view. The `Useful` column is the
   per-task ratio (always 0 or 100% with the strict rule above).
3. **Repeat waste** — packet hashes that have been sent across more than
   N tasks, suggesting either bad `--task-id` discipline or a packet that
   should be promoted to a per-project cache.

---

## Reproducibility checklist

When publishing a benchmark with these numbers, include:

- [ ] Provider + model name + version
- [ ] Tokenizer used for `tokens_estimated`
- [ ] Whether prompt caching was enabled
- [ ] Repo + commit indexed
- [ ] Set of tasks (descriptions, expected outcome)
- [ ] Final ledger as JSON (`contextmesh metrics --json`)
