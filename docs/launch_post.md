# Diff your failed agent run against your passed one

> A local CLI that records what your coding agent *selected*, what it
> *rejected*, and tells you what was different the time it worked.

Coding agents fail. Then the same agent passes on a re-run. The
difference is almost never the model — it's the context that got
selected. But the existing observability tools (Langfuse, LangSmith,
Phoenix, Helicone) all stop at "here's the trace." They show you what
happened. They do not show you *why* one run worked and the other
didn't.

[ContextMesh](https://github.com/Alivanroy/ContextMesh) v0.4 records
agent runs into a typed local ledger, then lets you do this:

```
$ contextmesh diff --left reset-bug-failed --right reset-bug-passed
Context diff reset-bug-failed -> reset-bug-passed
  outcome: regressed -> passed
  quality: 39.0% -> 75.0% (delta +36.0%)
  billed token delta: -11,540
  avoided token delta: -20
  duplicate ref delta: +0

                              Context ref changes
  Only left                  Shared                   Only right
  Read(tests/test_reset.py)  Bash(pytest …)           prompt_block:assistant…
  file:tests/test_reset.py   Edit(src/auth/reset.py)  prompt_block:assistant…
  generated_packet:command…  command:pytest …        prompt_block:result:19…
  prompt_block:assistant:…   file:src/auth/reset.py
  …                          result
                             tool_use:tu_1
                             tool_use:tu_2

Recommendations
  - Promote refs that appear only in the passed run; they are likely
    missing evidence.
  - Review refs that appear only in the failed run; they may be stale,
    noisy, or misleading.
```

That's the headline workflow. The rest of this post is what makes it
work.

## Context candidates: selected, rejected, *and why*

Most observability tools record what the agent received. ContextMesh
also records what the agent could have received and didn't, with a
reason. Every context decision lands in a `ContextCandidate` row with
three possible statuses:

```bash
contextmesh context record --task-id reset-bug --step 1 \
  --ref symbol:verify_reset_token --status selected \
  --source-type symbol --reason "directly covers failing test"

contextmesh context record --task-id reset-bug --step 1 \
  --ref file:docs/old-reset-policy.md --status rejected \
  --source-type doc --reason "stale reset-token flow, superseded by 2026 policy"
```

When you `diff` a failed run against a passed one, the `Only left` /
`Only right` columns are the actual difference your retrieval / agent
loop made. The recommendations call out which side to imitate.

Adapters wire this up automatically. Tracing a Claude Code, Aider, or
Codex CLI session populates candidates from the agent's tool-call
stream — `Read(app.py)` becomes both the raw tool ref and a derived
`file:app.py`; `Bash(pytest tests)` becomes both the tool ref and
`command:pytest tests`. The candidate model is the same whether
ContextMesh built it from a stream or a human typed it.

## Context audit: explainable policy checks

`contextmesh context audit` runs explainable checks against recorded
candidates and reports findings with codes you can grep, alert, or block
on:

```
$ contextmesh context audit --task-id reset-bug-failed
                  Context audit for reset-bug-failed
  Severity  Code                          Step  Ref                            Message
  warn      low_relevance_selected        2     symbol:verify_legacy_token     Selected despite relevance 0.15;
                                                                                review retrieval or selection policy.
  error     sensitive_selected_context    2     symbol:verify_legacy_token     Selected context looks sensitive;
                                                                                verify masking or policy approval.
```

The codes are: `duplicate_selected_ref`, `low_relevance_selected`,
`high_relevance_rejected`, `large_selected_context`,
`sensitive_selected_context`, `no_rejected_candidates`. Each one is a
small policy check you might otherwise hand-implement on top of a
generic observability platform. ContextMesh ships them as audit rows.

## Quality score with an actual breakdown

The headline metric is composite, not a black box. `contextmesh inspect`
shows the score and the four components it came from:

```
$ contextmesh inspect --task-id reset-bug-failed
Context inspection task=reset-bug-failed
  outcome: regressed
  steps: 5
  agents: claude-code
  context_quality_score: 39.0%
  useful_context_ratio: 0.0%
  score_breakdown: outcome=10.0%, avoidance=0.1%, evidence=100.0%, reuse=100.0%
```

Weights are explicit: outcome 40%, avoidance 25%, evidence 20%, reuse
15%. Argue with the weights. Argue with the components. They're public
and reproducible — every JSON export carries the full breakdown.

## Designed to be complementary, not competitive

ContextMesh deliberately does not own the trace store. If you already
run Langfuse, OTel collectors, Phoenix, or an internal pipeline,
ContextMesh emits the metadata to attach to them.

**Langfuse trace metadata payload:**

```
$ contextmesh export-langfuse --task-id reset-bug-passed --trace-id lf-trace-abc123
{
  "trace_id": "lf-trace-abc123",
  "metadata": {
    "contextmesh": {
      "version": "0.4.0",
      "task_id": "reset-bug-passed",
      "context_quality_score": 0.75,
      "useful_context_ratio": 1.0,
      "tokens_billed": 6020,
      "tokens_avoided": 0,
      "duplicate_ref_sends": 0,
      "selected_context_refs": [...],
      "rejected_context_refs": [],
      "recommendations": [...]
    }
  },
  "tags": ["contextmesh", "context_quality:0.75", "outcome:passed"]
}
```

**OpenTelemetry OTLP/JSON span:**

```
$ contextmesh export-otel --task-id reset-bug-passed --service-name agent-platform
{
  "resourceSpans": [{
    "resource": {"attributes": [{"key": "service.name", ...}]},
    "scopeSpans": [{
      "scope": {"name": "contextmesh.runtime.otel_export", "version": "0.4.0"},
      "spans": [{
        "traceId": "5cb73524c10d22614ea6954f5e168481",
        "spanId": "cd9f1e675e9d6160",
        "name": "contextmesh.context_inspection",
        ...
      }]
    }]
  }]
}
```

The boundary is intentional: Langfuse keeps the trace, ContextMesh keeps
the context-quality metadata. The same shape, attached to a different
backend, is `contextmesh export-team` for internal dashboards.

## Three adapters, all working off the same ledger

- **Claude Code** parses `claude --output-format stream-json`. One row
  per assistant turn, plus synthetic rows for distillable test output.
- **Codex CLI** parses `codex exec --json` JSONL. Handles
  `input_tokens - cached_input_tokens` correctly (the same OTel
  convention that produces the Langfuse double-counting bug).
- **Aider** parses `.aider.chat.history.md`. Real Aider 0.86+ output,
  blockquoted `Tokens: …` summary and all.

Each adapter is ~120–160 LoC. Adding a fourth (OpenCode, Cursor) is a
~30-line `Adapter` ABC subclass plus a fixture.

## Two real example apps

`examples/enterprise_agentic/` — a support-risk agent that selects from
contracts, SLAs, security policies, and escalation rules, with explicit
candidate decisions.

`examples/enterprise_rag_office/` — a RAG agent over Office-style docs,
showing how candidate selection + audit catches stale or sensitive
context before it reaches the model.

Both are intentionally non-coding-agent demos: the candidate / diff /
audit story generalizes to *any* context-using agent, not just code.

## Honest status

Alpha. One contributor. 119 tests across Python 3.10 / 3.11 / 3.12 in
CI, ruff clean, MIT. No telemetry, no cloud account, no SaaS. Local
SQLite, one CLI binary.

What it isn't trying to be: LangSmith, Langfuse, Phoenix. Those are full
LLM application observability suites and they win on production
workflows, dashboards, alerting, evals. ContextMesh is narrow on
purpose: *measure which context produced verified work, explain what
should change, and hand the metadata to whichever trace platform you
already run.*

## Where to start

```bash
git clone https://github.com/Alivanroy/ContextMesh
cd ContextMesh
pip install -e .

contextmesh init
contextmesh trace --task-id my-task --agent claude-code -- \
    claude -p "fix the failing test" --output-format stream-json --verbose
contextmesh inspect --task-id my-task
```

Repo: [github.com/Alivanroy/ContextMesh](https://github.com/Alivanroy/ContextMesh).
Design doc: [docs/context_intelligence_v1.md](https://github.com/Alivanroy/ContextMesh/blob/v0.4.0/docs/context_intelligence_v1.md).
Metric definition: [docs/metrics.md](https://github.com/Alivanroy/ContextMesh/blob/v0.4.0/docs/metrics.md).
