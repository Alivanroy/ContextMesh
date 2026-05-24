# Context Intelligence V1

ContextMesh V1 moves from pure agent observability toward context
intelligence:

> Langfuse shows what happened in an LLM run. ContextMesh explains whether the
> context was worth using, what was repeated, and what should change before the
> next run.

## Product Wedge

ContextMesh stays agent-agnostic and local-first, but adds a higher-level
inspection layer over the ledger. The ledger remains the source of truth;
inspection converts recorded steps into context quality, selected evidence,
and recommendations.

## V1 Scope

1. Context Run Inspector
   - Show selected context refs per task.
   - Count repeated refs across steps.
   - Summarise agents, outcome, billed tokens, avoided tokens, and useful
     context ratio.

2. Context Quality Score
   - Combine task outcome, avoided-token ratio, evidence coverage, and reuse
     health.
   - Keep the score explainable through a breakdown rather than a black box.

3. Recommendations
   - Suggest specific next actions when refs are missing, a run failed, repeated
     context was sent, or avoided-token data is absent.

4. Langfuse Metadata Payload
   - Export a compact `contextmesh` metadata object that can be attached to a
     Langfuse trace.
   - Keep ContextMesh complementary: Langfuse can hold the trace, while
     ContextMesh owns context quality and remediation.

## V1 Workflow

The implemented workflow is:

```bash
contextmesh inspect --task-id reset-bug
contextmesh inspect --task-id reset-bug --json
contextmesh context record --task-id reset-bug --step 1 \
  --ref symbol:verify_reset_token --status selected \
  --source-type symbol --reason "directly covers failing test"
contextmesh context record --task-id reset-bug --step 1 \
  --ref file:docs/old-reset.md --status rejected \
  --source-type doc --reason "stale reset-token flow"
contextmesh context audit --task-id reset-bug
contextmesh context schema inspection
contextmesh diff --left reset-bug-failed --right reset-bug-passed
contextmesh diff --left reset-bug-failed --right reset-bug-passed --json
contextmesh export-langfuse --task-id reset-bug --trace-id lf-trace-id
contextmesh export-otel --task-id reset-bug --service-name agent-platform
```

The JSON output includes `langfuse_metadata`, which is intentionally shaped as
a trace metadata payload:

```json
{
  "contextmesh": {
    "context_quality_score": 0.85,
    "useful_context_ratio": 1.0,
    "selected_context_refs": ["file:auth/reset.py"],
    "recommendations": []
  }
}
```

## Context Diff

`contextmesh diff` compares two recorded tasks and highlights:

- refs that appeared only in the left task
- refs that appeared only in the right task
- refs shared by both tasks
- context quality score delta
- billed-token, avoided-token, and duplicate-ref deltas
- recommendations for moving a failed run toward a passed run

The intended workflow is to compare a failed run against a later passing run:

```bash
contextmesh diff --left reset-bug-failed --right reset-bug-passed
```

## Context Candidates

The ledger records what happened at the step level. Context candidates record
the selection layer before the model call:

- `available`: context the system considered
- `selected`: context included in the run
- `rejected`: context intentionally left out

Each candidate can include a source type, relevance score, token estimate, and
reason. This lets `contextmesh inspect` explain both sides of context
selection:

```bash
contextmesh context record --task-id reset-bug --step 1 \
  --ref symbol:verify_reset_token --status selected \
  --source-type symbol --reason "directly covers failing test"

contextmesh context record --task-id reset-bug --step 1 \
  --ref file:docs/old-reset.md --status rejected \
  --source-type doc --reason "stale reset-token flow"

contextmesh context show --task-id reset-bug
contextmesh context audit --task-id reset-bug
contextmesh inspect --task-id reset-bug --json
```

When candidates exist for a task, the inspector uses selected candidates as
the source of truth. Older ledger-only runs still work through their
`context_refs` fallback.

Adapter-driven traces automatically create `selected` candidates from each
event's `context_refs`. Manual `contextmesh ledger record` entries do not,
so lightweight ledger usage remains backwards-compatible.

Tool-shaped refs are enriched into more inspectable candidates. For example,
`Read(app.py)` records both the original tool ref and `file:app.py`, while
`Bash(pytest tests)` records both the tool ref and `command:pytest tests`.

Adapters also emit finer-grained refs when the upstream stream exposes them:

- `tool_use:<id>` for Claude Code tool-use ids
- `tool_result:<id>` and `tool_result:pytest` for pytest tool results
- `tool_output:<kind>:<hash>` for hashed tool output
- `generated_packet:command_result:<hash>` for distilled command-result packets
- `prompt_block:<kind>:<hash>` for assistant, user, result, and agent-message text

These refs are stable hashes where the original text could be large or
sensitive. They let ContextMesh compare context decisions without copying raw
prompt or tool-output bodies into the ledger.

## Context Audit

`contextmesh context audit` runs explainable policy checks over candidates:

- selected context with very low relevance
- rejected context with high relevance
- duplicate selected refs
- large selected context chunks
- sensitive-looking selected refs or reasons
- missing rejected-candidate evidence

Warning and error findings are also included in `contextmesh inspect`
recommendations, so the main run inspection points at policy risks directly.

## JSON Schemas

The context intelligence layer exposes JSON Schema contracts for integrations:

```bash
contextmesh context schema candidate
contextmesh context schema inspection
contextmesh context schema diff
contextmesh context schema audit
contextmesh context schema langfuse-export
contextmesh context schema otel-export
contextmesh context schema all
```

These schemas cover the payloads emitted by `context show --json`,
`inspect --json`, `diff --json`, `context audit --json`, and
`export-langfuse` / `export-otel`.

## Langfuse Export

ContextMesh does not need to own Langfuse tracing. Instead, it emits a compact
payload that can be attached to a Langfuse trace by the caller:

```bash
contextmesh export-langfuse --task-id reset-bug --trace-id lf-trace-id
```

The output is shaped for trace update code:

```json
{
  "trace_id": "lf-trace-id",
  "metadata": {
    "contextmesh": {
      "task_id": "reset-bug",
      "context_quality_score": 0.85,
      "useful_context_ratio": 1.0,
      "selected_context_refs": ["symbol:verify_reset_token"],
      "rejected_context_refs": ["file:docs/old-reset.md"],
      "recommendations": []
    }
  },
  "tags": ["contextmesh", "context_quality:0.85", "outcome:passed"]
}
```

This keeps the product boundary clean: Langfuse remains the trace store, while
ContextMesh owns context quality, selected/rejected context, and remediation
metadata.

## OpenTelemetry Export

ContextMesh can also emit an OTLP/JSON-shaped payload:

```bash
contextmesh export-otel --task-id reset-bug --service-name agent-platform
```

The payload contains a `contextmesh.context_inspection` span with attributes
for task id, outcome, context quality, useful-context ratio, billed tokens,
avoided tokens, duplicate sends, and selected/rejected context counts.

Selected, rejected, and recommendation records are emitted as span events:

- `contextmesh.context.selected`
- `contextmesh.context.rejected`
- `contextmesh.recommendation`

This makes ContextMesh complementary to OTel-native stacks such as Langfuse,
Phoenix, Datadog, or an internal collector. The exporter is no-network by
design; production submission should happen in the caller's telemetry pipeline.

## Later Slices

- Add a direct Langfuse submitter only after the payload shape has been
  validated in real user traces. V1 intentionally stops at
  `contextmesh export-langfuse` so users can attach the payload with their own
  Langfuse client while we validate metadata shape and permissions.
