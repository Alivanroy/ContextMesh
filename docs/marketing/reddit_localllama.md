# Reddit — r/LocalLLaMA (v0.4.0)

Self post, not link post. Flair: "Resources" or "Tutorial | Guide".
Best time: weekday mornings US time. r/LocalLLaMA tolerates project
posts when they're technical, honest, and local-first.

---

## Title

```
ContextMesh v0.4 – diff a failed local-agent run against the passed one and see exactly which context was missing (works with Aider/Ollama, Codex CLI, Claude Code)
```

If too long for the title field:

```
Local-first CLI: diff your failed agent run against the passed one, get a remediation list
```

---

## Body (markdown)

If you run coding agents locally — Aider against Ollama, Codex CLI,
home-grown loops — you've hit this: the same agent fails one run,
passes on the rerun, and you can't tell what context made the
difference. The existing observability tools (Langfuse, Phoenix,
Helicone) show you what *happened*. They don't show you *why* one run
worked.

**ContextMesh** is a local CLI for that. SQLite on disk, no account, no
telemetry, no network calls. MIT.

v0.4 adds three things that make the failed-vs-passed comparison
real:

### 1. `contextmesh diff` — the headline workflow

```
$ contextmesh diff --left reset-bug-failed --right reset-bug-passed
Context diff reset-bug-failed -> reset-bug-passed
  outcome: regressed -> passed
  quality: 39.0% -> 75.0% (delta +36.0%)
  billed token delta: -11,540

  Only left                  Shared                   Only right
  Read(tests/test_reset.py)  Bash(pytest …)           prompt_block:assistant…
  file:tests/test_reset.py   Edit(src/auth/reset.py)  prompt_block:result:…
  generated_packet:command…
  prompt_block:result:a2…

Recommendations
  - Promote refs that appear only in the passed run; they are likely
    missing evidence.
  - Review refs that appear only in the failed run; they may be stale,
    noisy, or misleading.
```

The "Only left" column is the actual context the failed run looked at
and the passed one didn't. The "Only right" is the opposite. The
recommendation is the obvious-once-you-see-it remediation.

### 2. Selected / Rejected / Available, with reasons

The ledger now records context *decisions*, not just context that was
sent. Every candidate goes in with a status, a reason, and an optional
relevance score:

```bash
contextmesh context record --task-id my-task --step 1 \
  --ref symbol:verify_token --status selected \
  --source-type symbol --reason "directly covers failing test"

contextmesh context record --task-id my-task --step 1 \
  --ref file:docs/old-policy.md --status rejected \
  --source-type doc --reason "superseded by 2026 policy"
```

The Aider / Claude / Codex adapters wire this up automatically from
each agent's tool-call stream. Manual `ledger record` entries keep
working as before.

### 3. Policy audit you can grep

```
$ contextmesh context audit --task-id my-task
  warn   low_relevance_selected      2  symbol:verify_legacy_token
         Selected despite relevance 0.15; review retrieval or selection policy.
  error  sensitive_selected_context  2  symbol:verify_legacy_token
         Selected context looks sensitive; verify masking or policy approval.
```

Codes: `duplicate_selected_ref`, `low_relevance_selected`,
`high_relevance_rejected`, `large_selected_context`,
`sensitive_selected_context`, `no_rejected_candidates`. These are the
checks you'd otherwise hand-implement on top of generic observability.
ContextMesh ships them.

### Why this fits a local setup

- **No SaaS, no API key required.** State is a SQLite file under
  `.contextmesh/`. The "dashboard" is a terminal command.
- **Aider + Ollama tested.** The Aider adapter was built and verified
  against real `aider --model ollama_chat/llama3:latest` sessions
  fixing a real bug. Captured fixture in the repo; labelled
  `captured-live` in the harness.
- **Exports to whatever you already run.** `contextmesh export-langfuse`
  emits a metadata payload designed to attach via `trace.update()`.
  `contextmesh export-otel` emits OTLP/JSON spans. `contextmesh
  export-team` is a no-network internal-dashboard payload. ContextMesh
  doesn't try to own your trace store.

### Quality score with an actual breakdown

```
context_quality_score: 39.0%
score_breakdown: outcome=10.0%, avoidance=0.1%, evidence=100.0%, reuse=100.0%
```

Weights are explicit (outcome 40%, avoidance 25%, evidence 20%, reuse
15%) and the components are public. Composite metric, no black box.

### Honest status

Alpha. One contributor. 119 tests across Python 3.10–3.12 in CI, ruff
clean. The benchmark is small — 2 tasks × 3 agents — and every row is
labelled `captured-live | synthetic-real-shape | handcrafted`. I'm
posting now because I'd rather get the quality-score weights and the
strict `passed-or-zero` `useful_context_ratio` rule torn apart early
than late.

Repo (MIT): https://github.com/Alivanroy/ContextMesh
Design doc: docs/context_intelligence_v1.md

Quick start:

```bash
git clone https://github.com/Alivanroy/ContextMesh && cd ContextMesh
pip install -e .
contextmesh init
contextmesh trace --task-id smoke --silent --from-file \
    tests/fixtures/claude_code_session.jsonl -- noop
contextmesh trace --task-id smoke-passed --silent --from-file \
    tests/fixtures/claude_code_fixed_session.jsonl -- noop
contextmesh diff --left smoke --right smoke-passed
```

Specific thing I want feedback on: the audit rules. There are 6 codes
in v0.4. What's missing for your workflow?

---

## Comment-reply notes

- If asked "does it work with [non-Python lang]" — the trace / ledger /
  metric / candidate / audit layer is language-agnostic. Only the
  optional symbol-expansion path uses tree-sitter-python.
- If asked "does this work with OpenCode / Cursor / Cline" — adapters
  follow a ~150-LoC template, CONTRIBUTING.md has the recipe. Codex
  CLI was the v0.3 addition; OpenCode is the natural next one.
- If asked about cost (USD) — `contextmesh metrics` shows token volume
  by default; export per-million-token prices via env vars to get
  `useful_cost_ratio` and `$/passed-task` (docs/cost_metrics.md).
- Do not argue if downvoted early. Answer technical questions only.
