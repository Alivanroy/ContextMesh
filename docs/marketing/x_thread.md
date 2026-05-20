# X / Twitter — launch thread

7 tweets. Post the thread in one sitting. Tweet 1 must stand alone — most
people only see that one. Attach a screenshot of `contextmesh dashboard`
to tweet 1 and the leaderboard table to tweet 5 (grab both from a real
terminal run before posting). Repo link goes in the LAST tweet, not the
first — links in tweet 1 suppress reach.

Hashtags are noise; skip them. If a larger account in the agent/LLM
space is reachable, a reply-with-link after posting beats hashtags.

---

## Tweet 1 — hook (attach: dashboard screenshot)

Your coding agent's dashboard says "input tokens: 43,118."

Anthropic charges 4 different rates for those tokens — uncached, cache
read, cache write, output. Collapse them into one number and you can't
tell if your agent is spending well or burning money.

ContextMesh keeps them separate. 🧵

---

## Tweet 2

It wraps any coding agent — Claude Code, Codex CLI, Aider — and parses
its tool-call stream into a local SQLite ledger.

One row per turn. Four token columns, never summed. Plus: did the task's
tests actually pass?

No cloud account. No telemetry. One CLI.

---

## Tweet 3

The bug that started it:

Langfuse double-counts Anthropic cache tokens (langfuse#12306, open
since Q1). Cached input gets counted once by the OTel convention, then
again when the cache fields are added on top.

If your cost graph does this, it's ~2× wrong.

---

## Tweet 4

The headline metric is one strict number:

useful_context_ratio = tokens on tasks that ended `passed`
                     / tokens on all tasks

A task that doesn't finish scores zero. No partial credit.

It measures whether your spend produced working code — not just how big
the spend was.

---

## Tweet 5 — proof (attach: leaderboard screenshot)

It runs a cross-agent leaderboard. Every row is labelled by how real the
data is — `captured-live`, `synthetic-real-shape`, `handcrafted` — so it
never overstates itself.

The Aider rows are real `aider + ollama llama3` runs fixing a real bug.

---

## Tweet 6

Two compression tricks, both measured, both additive to Anthropic's
prompt cache:

• per-task cache: a symbol the agent already saw → a 12-token reference
• critical-path focus: a failing test pins the buggy function's body

On a 3-turn refactor: 39% fewer input tokens.

---

## Tweet 7 — CTA (link goes here)

Alpha. MIT. One contributor. 80 tests, CI on Python 3.10–3.12.

It's not trying to be LangSmith — it's the meter you put on top of your
agent. Narrow on purpose.

Tear the metric apart, wire your agent in, or just watch where your
tokens go:

github.com/Alivanroy/ContextMesh

---

## Notes

- If tweet 1 gets zero traction in ~2h, the hook is wrong — don't post
  the rest into a void. Re-draft tweet 1 and try once more another day.
- Reply to every substantive reply for the first few hours; the
  algorithm rewards thread-author engagement.
- A short follow-up the next day ("biggest piece of feedback so far
  was X, here's what I changed") extends the life of the launch.
