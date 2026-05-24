# Hacker News — Show HN (v0.4.0)

## Submission

**Title** (76 chars):

```
Show HN: ContextMesh – diff your failed agent run against your passed one
```

**URL:**

```
https://github.com/Alivanroy/ContextMesh
```

Submit Tuesday–Thursday, 8:00–9:30am US Eastern. Stay at the keyboard
for the first 3 hours to answer comments. Don't reply to downvotes;
reply to questions.

---

## First comment (post immediately after submitting)

ContextMesh is a local CLI that records coding-agent runs into a typed
SQLite ledger — token volume, cache usage, which test ended up passing.
The v0.4 release adds something most observability tools don't: it
records what the agent *rejected* with a reason, and lets you diff two
runs.

The demo:

```
$ contextmesh diff --left reset-bug-failed --right reset-bug-passed
Context diff reset-bug-failed -> reset-bug-passed
  outcome: regressed -> passed
  quality: 39.0% -> 75.0% (delta +36.0%)
  billed token delta: -11,540

  Only left                  Shared                   Only right
  Read(tests/test_reset.py)  Bash(pytest …)           prompt_block:assistant…
  file:tests/test_reset.py   Edit(src/auth/reset.py)  prompt_block:result:…
  generated_packet:command…  …
  prompt_block:result:a2…

Recommendations
  - Promote refs that appear only in the passed run; they are likely
    missing evidence.
  - Review refs that appear only in the failed run; they may be stale,
    noisy, or misleading.
```

That's two real fixtures from `tests/fixtures/` (a real-shape Claude
Code stream-json and its passing counterpart). The diff happens against
a `ContextCandidate` table that records every context decision as
`available | selected | rejected` with a `source_type`, `reason`, and
optional `relevance_score`.

The quality score on the left is composite, not opaque. Breakdown is
shipped in the output:

  score_breakdown: outcome=10.0%, avoidance=0.1%, evidence=100.0%, reuse=100.0%

Weights: outcome 40%, avoidance 25%, evidence 20%, reuse 15%. Argue with
the components or the weights — they're public and reproducible.

The audit is the second-most-interesting bit. Real run, real finding:

```
$ contextmesh context audit --task-id reset-bug-failed
  warn      low_relevance_selected       2  symbol:verify_legacy_token
            Selected despite relevance 0.15; review retrieval or selection policy.
  error     sensitive_selected_context   2  symbol:verify_legacy_token
            Selected context looks sensitive; verify masking or policy approval.
```

What's actually real right now, since HN will check:

- Three working adapters: Claude Code (`stream-json`), Codex CLI
  (`exec --json`), Aider (`.aider.chat.history.md`). Real captured
  fixtures, not synthesized.
- Five new CLI commands in v0.4: `inspect`, `diff`,
  `context record/show/audit/schema`, `export-langfuse`, `export-otel`,
  `export-team`.
- The Langfuse export is metadata-only (designed to attach to an
  existing trace via `trace.update(metadata=...)`). ContextMesh
  deliberately does not own the trace store. Same shape for the OTel
  OTLP/JSON export.
- 119 tests, ruff clean, CI on Python 3.10/3.11/3.12. Alpha, MIT, one
  contributor. No telemetry, no SaaS.

What it isn't trying to be: LangSmith / Langfuse / Phoenix. Those are
full app-observability suites and they win on dashboards / alerting /
evals. ContextMesh is narrow on purpose — measure which context
produced verified work, explain what should change, and hand the
metadata to whichever trace backend you already run.

Two enterprise examples in `examples/` show the candidate / diff /
audit story generalizes to non-coding agents too — a support-risk
classifier and a RAG-over-office-docs agent.

Repo: https://github.com/Alivanroy/ContextMesh
Design doc: docs/context_intelligence_v1.md
Most arguable design decision: the strict `passed-or-zero`
`useful_context_ratio` (docs/metrics.md has the rejected softer
variants). Tell me it's wrong here.

---

## Pre-written replies to likely comments

**"Isn't this just Langfuse with extra steps?"**
> The product surfaces don't overlap: Langfuse stores traces;
> ContextMesh stores *context decisions* (selected/rejected/available
> with reasons) and computes quality from outcome. The
> `export-langfuse` command emits a metadata payload designed to
> attach to a Langfuse trace via `trace.update()`. Complementary by
> design.

**"The `pass-or-zero` rule is too strict."**
> Agreed it's strict, and the softer variants (partial credit for
> `unchanged`, step-level scoring) are documented and rejected in
> `docs/metrics.md` because they're all gameable. Open to a better
> rule — the metric implementation is 2 lines.

**"How do you get `relevance_score` for `context audit` to work?"**
> Recorded by whoever's making the selection decision — usually your
> RAG reranker or retrieval layer. The audit is a check, not a
> retriever; it doesn't compute scores, it acts on them. If you don't
> have scores, the relevance-based findings just don't fire; duplicate
> / large / sensitive findings still work.

**"Why not OpenInference?"**
> The OTel export uses OTLP/JSON spans with `gen_ai.*`-style
> attributes; adding OpenInference semantic conventions is one
> attribute-key change. Open issue or PR if you want it.

**"Tree-sitter-python only — what about other languages?"**
> The trace/ledger/metric/candidate/audit layer is
> language-agnostic — it parses the agent's stream, not your code. Only
> the optional symbol-expansion path uses tree-sitter. The Codex
> adapter has been smoke-tested fine against non-Python repos.
