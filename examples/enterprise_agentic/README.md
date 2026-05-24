# Enterprise Agentic Example

This is a runnable enterprise-style agent that uses ContextMesh as its context
intelligence layer.

The scenario is a regulated-finance customer escalation:

- customer: Acme Financial Group
- issue: password reset links fail after an auth rollout
- impact: privileged operators cannot rotate credentials
- agent goal: choose the right policy/runbook/customer context, reject stale or
  sensitive context, and produce a customer-safe action plan

## Run

```bash
bash examples/enterprise_agentic/run_enterprise_demo.sh
```

Artifacts are written to:

```text
examples/enterprise_agentic/out/
```

The script uses `CONTEXTMESH_STATE_DIR` if provided. Otherwise it creates a
temporary state directory.

## What It Demonstrates

The agent records:

- selected context: current SLA, customer contract notes, auth rollout runbook,
  security communications policy
- rejected context: stale 2024 reset policy and raw debug dump with sensitive
  token-like content
- action plan: P1 classification, rollback/mitigation decision, customer-safe
  update, follow-up actions

ContextMesh then emits:

- `inspection.json`: context quality and recommendations
- `audit.json`: policy findings for selected/rejected context
- `langfuse.json`: trace metadata payload
- `otel.json`: OpenTelemetry OTLP/JSON-shaped context-inspection payload
- `slack.json`: team channel payload
- `jira.json`: issue payload for follow-up work

## Why This Is Enterprise-Relevant

Real enterprise agent deployments need more than a final answer. They need to
show:

- which context the agent selected
- which context it rejected and why
- whether risky context was used
- how the run should appear in observability tools
- how support, platform, and engineering teams should receive the result

This example keeps all of that local and deterministic so it can run in CI.

## Example Commands

```bash
contextmesh context show --task-id enterprise-acme-p1
contextmesh context audit --task-id enterprise-acme-p1
contextmesh inspect --task-id enterprise-acme-p1
contextmesh export-langfuse --task-id enterprise-acme-p1 --trace-id enterprise-enterprise-acme-p1
contextmesh export-otel --task-id enterprise-acme-p1 --service-name enterprise-support-risk-agent
contextmesh export-team --task-id enterprise-acme-p1 --target slack
contextmesh export-team --task-id enterprise-acme-p1 --target jira
```

## Extension Points

This project can be adapted into a real internal agent by replacing the local
`data/` files with:

- CRM account records
- support ticket payloads
- incident-management policies
- service runbooks
- security communication policies
- customer-safe response templates

Keep ContextMesh in the loop at the selection boundary: record every candidate,
including rejected candidates, before the final agent answer is delivered.
