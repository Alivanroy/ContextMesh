# Cost Metrics

ContextMesh keeps token volume as the source of truth. Dollar estimates are
optional because provider prices change and vary by model.

Set per-million-token prices in the environment before running
`contextmesh metrics` or `contextmesh dashboard`:

```bash
export CONTEXTMESH_PRICE_INPUT_PER_MTOK=3
export CONTEXTMESH_PRICE_CACHE_READ_PER_MTOK=0.3
export CONTEXTMESH_PRICE_CACHE_WRITE_PER_MTOK=3.75
export CONTEXTMESH_PRICE_OUTPUT_PER_MTOK=15
```

Then traced sessions expose:

- `estimated_cost_usd`: provider input + cache read + cache write + output
  priced by the environment model.
- `useful_cost_ratio`: cost attached to passed tasks divided by all observed
  cost.
- `wasted_cost_usd`: cost attached to non-passing final outcomes.
- `cost_per_passed_task_usd`: useful cost divided by passed task count.

The strict outcome rule matches `useful_context_ratio`: a task only counts as
useful when its final `outcome_class` is `passed`.

## Why Prices Are Explicit

ContextMesh does not ship provider-specific defaults. That avoids stale
numbers and makes benchmark reproduction honest: every published cost table
should include the exact model and price settings used.

Token-volume metrics always work without pricing. Cost metrics stay at `0.0`
until prices are configured.
