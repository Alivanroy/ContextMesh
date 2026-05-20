# Hacker News — Show HN

## Submission

**Title** (71 chars — HN limit is 80):

```
Show HN: ContextMesh – see where your coding agent's tokens actually go
```

**URL:**

```
https://github.com/Alivanroy/ContextMesh
```

Submit Tuesday–Thursday, ~8:00–9:30am US Eastern. Avoid Mon/Fri and
weekends. Do not submit and walk away — be at the keyboard for the first
3 hours to answer comments.

---

## First comment (post immediately after submitting)

ContextMesh is a local CLI that wraps a coding agent (`claude`, `codex`,
`aider`) and logs every step into a SQLite ledger — token volume, cache
usage, and whether the task's tests ended up passing.

The thing that started it: most agent-observability tools collapse the
four token columns Anthropic prices *differently* — uncached input
(1.0×), cache read (0.1×), cache write (1.25×), output — into one "input
tokens" number. Langfuse currently goes further and double-counts the
cached tokens (langfuse/langfuse#12306, open since Q1). If your dashboard
does that, you genuinely cannot tell whether an agent is spending well.

ContextMesh keeps the four columns separate, never summed, and ties them
to an outcome. The headline metric is deliberately strict:

  useful_context_ratio = tokens spent on tasks that ended `passed`
                       / tokens spent on all tasks

A task that doesn't finish contributes zero useful tokens. It rewards
finishing, not trying.

What's actually real right now, and what isn't, because HN will check:

- Three adapters work (Claude Code stream-json, Codex CLI exec --json,
  Aider chat history). ~120–160 LoC each.
- The benchmark is fixture-scale — 2 tasks × 3 agents. Every row in the
  leaderboard is labelled `captured-live` / `synthetic-real-shape` /
  `handcrafted` so it never overstates itself. The `captured-live` rows
  are real `aider + ollama llama3` runs. v0.4 is the real benchmark.
- It's alpha, MIT, one contributor, no users yet. 80 tests, CI on
  3.10–3.12. No telemetry, no cloud account, no SaaS.

It is not trying to be LangSmith/Langfuse — those are full app
observability suites. This is narrow on purpose: measure which
coding-agent context produced verified work, and what it cost.

Repo: https://github.com/Alivanroy/ContextMesh
Metric definition: docs/metrics.md
Market positioning vs the incumbents: benchmarks/market_comparison_2026-05-16.md

Happy to be told the metric is wrong — the strict pass-or-zero rule is
the most arguable design decision and I'd rather hear it here.

---

## Pre-written replies to likely comments

**"Isn't this just Langfuse / LangSmith?"**
> Those trace any LLM app and are far more mature for production
> dashboards, evals, and alerting. ContextMesh is local-first and
> narrow: it only does coding agents, and its primary metric is
> outcome-coupled (did the context produce a passing task) rather than
> latency/cost-only. It's a meter, not a suite. The market table in the
> repo lays out where it's behind — which is most places.

**"Anthropic prompt caching already solves repeated context."**
> It does, for the prefix, inside Anthropic. ContextMesh's compression
> is additive — it shrinks what's *in* the prefix (de-dupes symbols the
> agent already saw this task) and the cache columns show Anthropic's
> part separately. Also: caching doesn't tell you whether the context
> was *useful*, only that it was cheap to resend.

**"pass-or-zero is too strict / a passing task can still ship a hack."**
> Agreed it's strict, and it deliberately doesn't measure code quality —
> only spend efficiency. The softer variants (partial credit for
> `unchanged`, step-level credit) are documented and rejected in
> docs/metrics.md because they're all gameable. Open to a better rule.

**"Why no real Claude benchmark numbers?"**
> Honest answer: the headline `claude-code` rows are
> `synthetic-real-shape` — the stream schema and usage columns are real,
> the magnitudes are demo-scale. A live authenticated multi-task Claude
> run is the v0.4 blocker. The Aider rows are genuinely captured-live.

**"Python-only indexing is limiting."**
> The trace/ledger/metric layer is language-agnostic — it parses the
> agent's stream, not your code. Only the optional `expand`/focus
> packet path uses tree-sitter and is Python-only today. TS/Go are
> roadmap.
