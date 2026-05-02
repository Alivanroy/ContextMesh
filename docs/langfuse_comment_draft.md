# Draft comment for langfuse/langfuse#12306

> Paste this on https://github.com/langfuse/langfuse/issues/12306 once
> you're satisfied with the wording.

---

Bumping this — the double-counting still surfaces in Langfuse v3.x when
tracing Anthropic via pydantic-ai/genai-prices, and the cost graph for
any coding agent that uses prompt caching is roughly 2× the real spend.

For anyone hitting this and wanting an interim option: I built a small
local observability tool ([Alivanroy/ContextMesh](https://github.com/Alivanroy/ContextMesh))
that takes a different approach to the same data. Rather than collapsing
the four Anthropic usage fields into one OTel `input_tokens` value, it
keeps them separate per ledger row:

| Column | Anthropic field | Pricing |
|---|---|---|
| `tokens_provider_input` | `input_tokens` (uncached) | 1.0× |
| `tokens_cached_read` | `cache_read_input_tokens` | 0.1× |
| `tokens_cached_write` | `cache_creation_input_tokens` | 1.25× (5min) / 2.0× (1h) |
| `tokens_provider_output` | `output_tokens` | output rate |

Two adapters today (Claude Code stream-json, Aider chat history); the
shapes are pulled out in
[contextmesh/adapters/claude_code.py](https://github.com/Alivanroy/ContextMesh/blob/main/contextmesh/adapters/claude_code.py)
if useful as a reference for how to map Anthropic's three input fields
without summing them.

Happy to contribute the mapping back to Langfuse if there's appetite —
the rule is just: emit each Anthropic field as its own metric, never
sum them into the OTel-spec total.
