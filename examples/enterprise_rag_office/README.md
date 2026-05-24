# Enterprise RAG Over Office Documents

This example simulates a real enterprise RAG workflow over office files:

- Word `.docx` contract and security documents
- Excel `.xlsx` SLA and usage-risk workbooks
- stale documents that should be rejected
- a deterministic RAG agent that records context decisions in ContextMesh

The scenario: procurement asks whether a vendor renewal can be approved for an
enterprise customer that now requires EU residency, P1 support commitments, and
evidence that authentication incidents have improved.

## Run

```bash
bash examples/enterprise_rag_office/run_office_rag_demo.sh
```

Outputs are written to:

```text
examples/enterprise_rag_office/out/
```

The demo creates office files at runtime under `out/source_files/`, extracts
RAG chunks, records selected/rejected candidates, and exports:

- `answer.json`
- `inspection.json`
- `audit.json`
- `langfuse.json`
- `otel.json`
- `slack.json`
- `jira.json`
- generated `.docx` and `.xlsx` source files

## What It Demonstrates

This is the enterprise pattern teams usually mean by "RAG":

1. Documents live in mixed office formats.
2. The agent retrieves paragraphs and worksheet rows.
3. The agent must reject stale policies and irrelevant financial rows.
4. The decision must be auditable by platform, support, procurement, and
   security teams.

ContextMesh records all of that as context candidates, then produces inspect,
audit, Langfuse, OpenTelemetry, and team payloads.
