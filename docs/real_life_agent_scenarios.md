# Real-Life Agent Scenarios

This document captures local, credential-free scenarios for validating
ContextMesh V1 against common agent workflows and team integrations.

## Scenario Results

The scenarios were run from captured fixtures and local demo scripts, without
live provider credentials.

| Scenario | Agent pattern | Command surface | Result |
| --- | --- | --- | --- |
| Codex passing fix | command execution + final turn usage | `trace`, `inspect`, `audit`, `export-langfuse`, `export-otel` | passed; 7 selected candidates; schema-valid payloads |
| Codex failing fix | command execution + failed pytest | `trace`, `diff` | regressed; diff explains context delta against passing run |
| Claude passing fix | tool-use stream + final result | `trace`, `inspect` | passed; provider cache and prompt-block refs captured |
| Claude failing fix | tool-use + pytest tool result | `trace`, `audit`, `dashboard` | regressed; generated command-result packet refs captured |
| Aider passing session | markdown chat history + token summary | `trace`, `metrics` | passed; user prompt and pytest output refs captured |
| Demo bug workflow | local pytest + packet export | `run`, `export-context` | demo completed; packet bundle generated |
| Benchmark harness | fixture matrix across agents | `benchmarks/harness.py` | all fixture outcomes correctly classified |
| Multi-turn reuse | repeated context export | `benchmarks/multi_turn_delta.py` | 39.5% token savings over three turns |

## Agent Patterns Covered

### Command-First Coding Agent

Used by Codex CLI fixtures. The agent emits command execution events and final
turn usage. ContextMesh records:

- `command:<cmd>`
- `tool_output:command_execution:<hash>`
- `generated_packet:command_result:<hash>`
- `prompt_block:agent_message:<hash>`
- `thread:<id>`

This pattern is useful for CI debugging and PR-fix workflows.

### Tool-Use Streaming Agent

Used by Claude Code fixtures. The agent emits assistant turns, tool-use ids,
tool results, and final results. ContextMesh records:

- `tool_use:<id>`
- `tool_result:<id>`
- `tool_result:pytest`
- `tool_output:pytest:<hash>`
- `generated_packet:command_result:<hash>`
- `prompt_block:assistant:<hash>`
- `prompt_block:result:<hash>`
- `file:<path>` and `command:<cmd>` where tool targets expose them

This pattern is useful for tracing exactly which file/tool output drove a fix.

### Chat-History Agent

Used by Aider fixtures. The agent writes markdown chat history rather than
JSONL. ContextMesh records:

- `user_input`
- `prompt_block:user:<hash>`
- `tool_output:pytest`
- `tool_output:pytest:<hash>`
- `generated_packet:command_result:<hash>`

This pattern is useful when the agent does not expose structured tool spans.

## Different Context Types

ContextMesh V1 now separates context into explicit candidate rows:

- `available`: considered but not necessarily used
- `selected`: included in the run
- `rejected`: intentionally left out

Important source types include:

- `file`
- `symbol`
- `command`
- `tool_use`
- `tool_result`
- `tool_output`
- `generated_packet`
- `prompt_block`
- `thread`
- `turn`

Raw prompt/tool-output bodies are not copied into refs. Large or sensitive text
is represented by stable hashes such as `prompt_block:user:<hash>`.

## Team Integrations

ContextMesh currently emits no-network payloads. Teams can attach these to
their existing webhook, CI, or app plumbing.

### Langfuse

Use:

```bash
contextmesh export-langfuse --task-id reset-bug --trace-id lf-trace-id
```

Best for AI platform teams that already use Langfuse as their trace store.
ContextMesh contributes `context_quality_score`, selected/rejected refs, and
recommendations.

### OpenTelemetry

Use:

```bash
contextmesh export-otel --task-id reset-bug --service-name agent-platform
```

Best for teams that already route GenAI traces through an OpenTelemetry
collector or OTel-native observability backend. ContextMesh contributes a
`contextmesh.context_inspection` span and selected/rejected context events.

### Slack

Use:

```bash
contextmesh export-team --task-id reset-bug --target slack
```

Best for posting a run summary into an engineering channel after a CI agent or
coding agent finishes.

### Microsoft Teams

Use:

```bash
contextmesh export-team --task-id reset-bug --target ms-teams
```

Emits an Adaptive Card-style payload with status, token use, and audit
findings.

### Linear, Jira, GitHub Issues

Use:

```bash
contextmesh export-team --task-id reset-bug --target linear
contextmesh export-team --task-id reset-bug --target jira
contextmesh export-team --task-id reset-bug --target github
```

Best for creating follow-up tickets when a run regresses, selects risky
context, or repeatedly uses stale evidence.

## Recommended Team Workflows

1. CI coding-agent job runs under `contextmesh trace`.
2. Job exports `inspect --json`, `context audit --json`, `export-langfuse`,
   and `export-otel`.
3. AI platform team attaches Langfuse metadata or sends the OTel payload to
   its collector.
4. Engineering team posts `export-team --target slack` or `ms-teams`.
5. Failed or risky runs create Linear/Jira/GitHub follow-up issues.
6. Weekly platform review uses `diff` and audit findings to tune retrieval and
   context policies.

## Direct Submitters

V1 intentionally stops at payload export. Direct Langfuse, Slack, Teams, Jira,
Linear, or GitHub network submitters should be added only after payload shape,
permissions, and customer workspace conventions are validated in real traces.
