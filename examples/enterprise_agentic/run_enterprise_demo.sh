#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

STATE_DIR="${CONTEXTMESH_STATE_DIR:-$(mktemp -d)}"
OUT_DIR="${1:-examples/enterprise_agentic/out}"
TASK_ID="${TASK_ID:-enterprise-acme-p1}"

export CONTEXTMESH_STATE_DIR="$STATE_DIR"
export PYTHONPATH="$ROOT_DIR"

python3 examples/enterprise_agentic/support_risk_agent.py \
  --task-id "$TASK_ID" \
  --out "$OUT_DIR"

contextmesh context show --task-id "$TASK_ID" --json > "$OUT_DIR/context_candidates.json"
contextmesh context audit --task-id "$TASK_ID" --json > "$OUT_DIR/context_audit_cli.json"
contextmesh inspect --task-id "$TASK_ID" --json > "$OUT_DIR/inspection_cli.json"
contextmesh export-langfuse --task-id "$TASK_ID" --trace-id "enterprise-$TASK_ID" \
  > "$OUT_DIR/langfuse_cli.json"
contextmesh export-team --task-id "$TASK_ID" --target slack > "$OUT_DIR/slack_cli.json"
contextmesh export-team --task-id "$TASK_ID" --target jira > "$OUT_DIR/jira_cli.json"

echo "ContextMesh state: $STATE_DIR"
echo "Artifacts: $OUT_DIR"
