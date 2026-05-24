# X / Twitter — launch thread (v0.4.0)

8 tweets. Post in one sitting. Tweet 1 must stand alone — most people
only see that. Attach a screenshot of the `contextmesh diff` output to
tweet 1 and the `context audit` output to tweet 5 (grab both from a
real terminal run; the exact commands are in `docs/launch_post.md`).

Repo link goes in the LAST tweet, not the first — links in tweet 1
suppress reach. No hashtags.

If a larger account in the agent/LLM space is reachable, reply-with-link
after posting beats every hashtag.

---

## Tweet 1 — hook (attach: diff screenshot)

Your agent failed. You re-ran it. It passed.

You don't know why.

Most agent observability tools show what happened. ContextMesh shows
what was *different* between the two runs.

🧵

---

## Tweet 2

`contextmesh diff --left failed-run --right passed-run`

Outputs three columns: refs only the failed run looked at, refs only
the passed run looked at, refs both shared.

Plus a remediation list: "promote the only-right refs, review the
only-left ones."

The thing you'd otherwise hand-diff in a notebook.

---

## Tweet 3

It works because ContextMesh records context *decisions*, not just
context.

Every candidate goes in with a status:
• `selected` — agent saw it
• `rejected` — agent skipped it, with a reason
• `available` — system considered it

Rejection-with-reason is what most observability tools never capture.

---

## Tweet 4

The quality score is composite, not a black box:

  outcome   40%
  avoidance 25%
  evidence  20%
  reuse     15%

Every export ships the breakdown. Argue with the weights — the
implementation is 2 lines of Python.

---

## Tweet 5 — proof (attach: audit screenshot)

`contextmesh context audit` runs explainable policy checks:

`warn   low_relevance_selected`
`error  sensitive_selected_context`
`warn   high_relevance_rejected`
`warn   duplicate_selected_ref`

The checks you'd otherwise build on top of generic observability.
Shipped as audit rows you can grep, alert, or block on.

---

## Tweet 6

Designed to be complementary, not competitive:

`contextmesh export-langfuse` → metadata payload for
`trace.update(metadata=...)`

`contextmesh export-otel` → OTLP/JSON spans for Phoenix, Datadog, your
collector

Langfuse keeps the trace. ContextMesh keeps the context quality.

---

## Tweet 7

Three adapters today, all parsing real captured streams:

• Claude Code (`stream-json`)
• Codex CLI (`exec --json`)
• Aider (`.aider.chat.history.md`)

Two enterprise examples in the repo prove the candidate/diff/audit
story isn't coding-agent-only.

---

## Tweet 8 — CTA (link goes here)

Alpha. MIT. One contributor. 119 tests, CI on Python 3.10–3.12.

Local SQLite, no SaaS, no telemetry, no cloud account.

Diff a failed run, audit its context, attach the metadata to whatever
you already run:

github.com/Alivanroy/ContextMesh

---

## Notes

- If tweet 1 gets zero engagement in ~2h, the hook is wrong — don't
  spam the rest into a void. Wait a day, re-draft tweet 1, retry once.
- Reply to every substantive reply for the first 3 hours; the algorithm
  rewards thread-author engagement.
- Best follow-up the next day: "biggest feedback so far was X, here's
  what I changed" extends the launch.
