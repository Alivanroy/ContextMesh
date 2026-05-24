# Changelog

All notable changes to ContextMesh are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.4.0 — 2026-05-24

### Added — Context Intelligence v1

A new product layer on top of the v0.2/v0.3 ledger. ContextMesh now
records context *decisions* (not just usage) and explains them.

- **`ContextCandidate`** table — every context decision recorded as
  `available | selected | rejected` with `source_type`, `reason`, and
  optional `relevance_score` / `tokens_estimated`. Adapters wire this
  up automatically from tool-call streams; `contextmesh context record`
  appends manually.
- **`contextmesh inspect`** — composite `context_quality_score` (40%
  outcome + 25% avoidance + 20% evidence + 15% reuse) with the full
  breakdown in every export. Recommendations engine emits remediation
  steps when refs are missing, runs failed, or duplicates appeared.
- **`contextmesh diff`** — compare two recorded tasks. Returns refs
  only-left / shared / only-right plus quality delta plus
  failed-vs-passed remediation list. The headline workflow.
- **`contextmesh context audit`** — explainable policy checks over
  recorded candidates. Codes: `duplicate_selected_ref`,
  `low_relevance_selected`, `high_relevance_rejected`,
  `large_selected_context`, `sensitive_selected_context`,
  `no_rejected_candidates`.
- **`contextmesh context schema`** — exposes JSON Schemas for every
  context-intelligence payload: candidate, inspection, diff, audit,
  langfuse-export, otel-export.
- **`contextmesh export-langfuse`** — metadata-only payload designed
  to attach via `trace.update(metadata=...)`. ContextMesh is
  complementary to Langfuse, not a competitor.
- **`contextmesh export-otel`** — OTLP/JSON span shaped for Phoenix /
  Datadog / internal OTel collectors. No-network by design; production
  submission stays in the caller's telemetry pipeline.
- **`contextmesh export-team`** — generic no-network payload for
  internal dashboards.
- **Adapter enrichment** — Claude Code, Codex CLI, and Aider now emit
  fine-grained refs from their streams: `tool_use:<id>`,
  `tool_result:<id>`, `tool_result:pytest`,
  `tool_output:<kind>:<hash>`, `generated_packet:command_result:<hash>`,
  `prompt_block:<kind>:<hash>`. Stable hashes; raw text never copied
  into the ledger. Tool-shaped refs (`Read(app.py)`,
  `Bash(pytest tests)`) get derived candidates (`file:app.py`,
  `command:pytest tests`) so audit and diff have something to match on.
- **Two enterprise example apps** demonstrating the candidate /
  diff / audit story generalizes to non-coding agents:
  `examples/enterprise_agentic/` (support-risk classifier) and
  `examples/enterprise_rag_office/` (RAG over Office-style docs).
- 39 new tests (119 total, was 80). ruff clean. CI green on Python
  3.10 / 3.11 / 3.12.

## Unreleased

### Added

- **Context Intelligence V1**: inspect recorded runs with
  `contextmesh inspect --task-id TASK`, including selected context,
  rejected context, context quality score, recommendations, and
  Langfuse-ready metadata.
- **Context candidates**: new `contextmesh context record/show` commands and
  persistent `context_candidate` table for `available`, `selected`, and
  `rejected` context with source type, relevance score, token estimate, and
  selection reason.
- **Automatic candidate population** from adapter `context_refs` during
  `contextmesh trace`, including derived `file:` and `command:` candidates
  from tool-shaped refs such as `Read(app.py)` and `Bash(pytest tests)`.
- **Finer-grained adapter refs** for tool-use ids, tool-result ids, hashed
  tool output, distilled command-result packets, and prompt blocks.
- **Context diff**: `contextmesh diff --left A --right B` compares selected
  context, quality score, token deltas, duplicate refs, and recommendations
  between two tasks.
- **Context audit**: `contextmesh context audit --task-id TASK` flags
  low-relevance selected context, high-relevance rejected context,
  duplicated selected refs, oversized selected context, and
  sensitive-looking selected context.
- **Langfuse payload export**: `contextmesh export-langfuse --task-id TASK`
  emits trace-ready metadata and tags without adding a runtime Langfuse
  dependency.
- **OpenTelemetry payload export**: `contextmesh export-otel --task-id TASK`
  emits an OTLP/JSON-shaped context-inspection span with selected/rejected
  context events for OTel-native observability stacks.
- **Team payload export**: `contextmesh export-team --task-id TASK --target`
  emits no-network JSON for Slack, Microsoft Teams, Linear, Jira, and GitHub.
- **Context Intelligence JSON Schemas**:
  `contextmesh context schema [candidate|inspection|diff|audit|langfuse-export|all]`.
- Real-life agent scenario documentation covering command-first, tool-use,
  and chat-history agent patterns plus team integration workflows.
- **Enterprise agentic example**: runnable regulated-finance support-risk
  agent under `examples/enterprise_agentic/` that records selected/rejected
  context with ContextMesh and emits inspection, audit, Langfuse, Slack, and
  Jira artifacts.
- **Enterprise Office RAG example**: runnable mixed-document renewal agent
  under `examples/enterprise_rag_office/` that generates Word `.docx` and
  Excel `.xlsx` source files, retrieves paragraphs and worksheet rows,
  rejects stale/irrelevant office context, and emits inspection, audit,
  Langfuse, Slack, and Jira artifacts.

### Tests

- Added schema validation for emitted Context Intelligence payloads.
- Added an end-to-end CLI workflow test covering trace replay, candidates,
  audit, inspect, diff, schema export, and Langfuse export.
- Added regression coverage for the enterprise Office RAG example, including
  generated source files, selected/rejected context, and exported schemas.
- Added OpenTelemetry export coverage for runtime payloads, CLI output, schemas,
  and enterprise example artifacts.

## v0.3.0 — 2026-05-16

### Added

- **Cost-weighted metrics**: optional `estimated_cost_usd`,
  `useful_cost_ratio`, `wasted_cost_usd`, and `cost_per_passed_task_usd`
  fields when per-million-token prices are supplied through environment
  variables. Token volume remains the source of truth; dollar estimates
  are explicit and reproducible. See [docs/cost_metrics.md](docs/cost_metrics.md).
- Dashboard cost rows and per-task cost columns when pricing is configured.
- **Codex CLI adapter**: parses `codex exec --json` JSONL streams, including
  command execution events and usage from `turn.completed`.
- Default benchmark harness now includes Codex CLI fixtures, so the
  fixture-based leaderboard covers Claude Code, Aider, and Codex CLI.
  Rows now carry fixture provenance (`captured-live`,
  `synthetic-real-shape`, or `handcrafted`) so benchmark claims stay honest.
- Market benchmark snapshot for LangSmith, Langfuse, Phoenix, Helicone,
  Braintrust, MLflow, and OpenTelemetry positioning:
  `benchmarks/market_comparison_2026-05-16.md`.

### Fixed

- **First-run SQLite race**: concurrent CLI processes targeting the same
  brand-new state directory now serialize schema/index writes with a lock
  file, avoiding `table indexed_file already exists` and duplicate-index
  write errors. The lock uses `fcntl` on Unix and `msvcrt` on Windows.
- **`CONTEXTMESH_STATE_DIR` init message**: `contextmesh init` now reports
  the override state directory and leaves project `.gitignore` untouched.

### Pivot — observability layer

The product has narrowed to the open observability layer for agent context
spend. The repo-packing and indexing surfaces are no longer the headline;
the ledger and `useful_context_ratio` are. See README.md and
[docs/metrics.md](docs/metrics.md).

## v0.2.2 — 2026-05-02

### Fixed (post-v0.2.1 review feedback)

- **Package metadata version drift**: `pyproject.toml` still said
  `version = "0.1.0"` after v0.2.0 and v0.2.1 were tagged. `pip install
  -e .` reported the wrong version, and any future PyPI / release
  automation would publish under the wrong name. Bumped to `0.2.2`.
- **Single source of truth**: added `contextmesh.__version__` at the
  package root and a regression test (`tests/test_version.py`) that:
  (a) asserts `__version__ == pyproject.toml`,
  (b) asserts the installed version matches the git tag at HEAD when
  one exists.
  Future drift fails CI loudly instead of shipping silently.
- **README test-count badge**: was stuck at `tests: 63` after v0.2.0
  added 16 more. Now reads `68 passing` and tracks the latest release.
- **Contributing section**: redirected from "wire a real agent into
  `contextmesh trace`" (already done for Claude Code + Aider) to the
  three actually-wanted next adapters: Codex CLI, OpenCode, Cursor.
  CONTRIBUTING.md now has a per-adapter recipe (~150 LoC each).

## v0.2.1 — 2026-05-02

### Fixed (post-v0.2.0 review feedback)

- **Traced sessions now bill real provider tokens** ([record_event](contextmesh/runtime/ledger.py)).
  Before this fix, `tokens_estimated` for adapter-emitted events fell back
  to a `cl100k_base` estimate of the tiny `context_text` (often <20 tokens
  for a turn that processed 17k of provider input). `useful_context_ratio`
  was effectively measuring nothing for traced sessions. Now: when any
  provider-token field is non-zero, `tokens_estimated` defaults to the
  sum `input + cache_read + cache_write` — the real input volume the
  provider tokenized. Locked in by `test_traced_session_billed_tokens_use_provider_numbers`.
- **Default benchmark harness no longer publishes a misclassified row**
  ([benchmarks/harness.py](benchmarks/harness.py)). The previous v0.2.0
  default paired `reset-bug-failing` (expected `regressed`) with the only
  Aider fixture available — a passing run — producing a `✗` row in every
  publication. Captured a real failing Aider+llama3 session
  ([tests/fixtures/aider_real_llama3_failing.md](tests/fixtures/aider_real_llama3_failing.md))
  and added `test_default_harness_runs_all_classify_correctly` so any
  future fixture/expected-outcome mismatch fails CI.
- **README quick-start now leads with `trace`**, not `ledger record` —
  the manual-logging path is documented as a fallback under
  `docs/architecture.md`. Roadmap line correctly notes `trace` shipped
  in v0.2 with two adapters; v0.3 is for adapters #3 and #4.

### Aider cost-line parsing in real fixtures real Aider 0.86.x emits
  the `Tokens: … sent, … received` summary inside a `> ` blockquote, and
  the per-turn variant lacks the `Cost: $…` suffix that the synthetic
  fixture had. The adapter now matches both shapes. Caught by the first
  real Ollama-driven Aider session (`tests/fixtures/aider_real_llama3.md`).
- **`expand_symbol` cwd dependency** (caught by Test 4 in the 2026-05-02
  real-world run): when the consumer cwd was outside the project root, the
  function's `os.path.exists()` check returned `False` for project-relative
  paths and the focus mechanism silently emitted no body. Now resolves
  paths against the project root in addition to cwd.

### Added
- **Aider adapter** (`contextmesh/adapters/aider.py`) — parses
  `.aider.chat.history.md`: detects user prompts via `####` markers,
  captures `Tokens: … sent, … received. Cost: $…` summary lines, and
  classifies pytest output appearing in tool blockquotes.
- **Cross-agent benchmark harness** (`benchmarks/harness.py`) — runs N
  agents × M tasks, writes JSON to `benchmarks/results/<date>.json`, and
  renders the four-columns-side-by-side leaderboard table. Default config
  uses captured stream fixtures so it runs without authentication.
- **`outcome_class` auto-detection** — both adapters now watch pytest
  tool_results; the final step's outcome is set automatically to
  `passed` / `regressed` / `unchanged` based on the most recent run.
  `useful_context_ratio` becomes non-zero out of the box.
- **Real Claude Code stream fixture** captured from a live (auth-failed)
  session to lock down the on-the-wire shape of `system`/`assistant`/`result`
  events, including `cache_creation_input_tokens` and the new
  `service_tier` / `cache_creation` ephemeral breakdown fields.
- **Provider-tokens dashboard panel** — per-task table with Input / Cache R
  / Cache W / Output / Avoided / Cache hit-rate columns; overview gains a
  cache section when provider data is present.
- **`contextmesh trace`** — wrap any agent CLI and populate the ledger from
  its tool-call stream. Ships with the Claude Code adapter
  (`--agent claude-code`); supports `--from-file` for replaying captured
  stream-json without spawning the agent.
- **`contextmesh/adapters/`** package — base `Adapter` ABC and the first
  concrete adapter (`ClaudeCodeAdapter`) that parses `claude --output-format
  stream-json` events into ledger entries, including provider-token usage
  (`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`,
  `output_tokens`) and automatic pytest tool-result distillation.
- `LedgerEntry.tokens_provider_input`, `tokens_cached_read`,
  `tokens_cached_write`, `tokens_provider_output` — surfaced separately so
  Anthropic prompt-caching savings are visible alongside ContextMesh
  savings.
- `runtime.ledger.record_event(dict)` — single entry point used by adapters.
- **`useful_context_ratio` metric** with a precise definition
  ([docs/metrics.md](docs/metrics.md)) and aggregation across tasks.
- `contextmesh metrics` and `contextmesh waste` commands.
- `LedgerEntry.tokens_kept_compressed`, `tokens_kept_pinned`, and
  `outcome_class` (`passed | unchanged | regressed | aborted | unknown`).
- `runtime/metrics.py`: `task_metrics`, `global_metrics`, and
  `find_repeat_waste` — surfaces packets being re-sent across tasks.
- Dashboard v2: per-task ratio table, recent-step timeline with
  billed-vs-avoided bars, and a repeat-waste panel.
- **Critical-path focusing** (`contextmesh/packets/focus.py`): when an export
  is given `--failures <file.jsonl>`, ContextMesh finds the symbol containing
  each failing line plus any indexed symbol named in the trace, inlines its
  body into the matching `SymbolPacket`, marks it `pinned=True`, and tells
  the compressor to leave it alone for this turn.
- `compress_packets(..., pinned_hashes=...)` — emit pinned symbols in full
  even when the seen-cache would normally downgrade them to `symbol_ref`.
- `SymbolPacket.body` and `SymbolPacket.pinned` fields; markdown export
  renders the body in a fenced block when present.
- Persisted index: `IndexedFile` and `IndexedSymbol` tables; `contextmesh index`
  now stores file hashes and symbols and skips unchanged files on re-runs.
- Delta-aware compressor: already-seen `symbol` packets become tiny
  `symbol_ref` packets per-task. Cleared with `contextmesh reset-cache`.
- Markdown exporter for `contextmesh export-context`; JSONL still available
  via `--format jsonl`.
- Token budget allocator (`--budget N`) drops low-priority packets first.
- Terminal dashboard (`contextmesh dashboard`) showing files, symbols,
  ledger entries, and a useful-context ratio.
- Multi-language fingerprinting (extension-based detection); jest/mocha/npm
  test output distillation alongside pytest.
- Project-scoped state under `.contextmesh/`; `CONTEXTMESH_STATE_DIR` env var
  for tests.
- `contextmesh expand --parent` to disambiguate methods with the same name.
- Integration guides for Claude Code, Codex CLI, and Cursor.
- CI workflow, ruff config, MIT LICENSE, real README.

### Fixed
- Pytest distillation no longer joins trace lines with the literal string `\n`.
- Pytest distillation now captures the `E AssertionError: ...` message rather
  than just the exception type.
- `index` command no longer drops every result it computes.
- Ledger no longer creates a SQLite file in the user's CWD on import.
- Tree-sitter end-line off-by-one when nodes end with a newline.
- `walk_repo` prunes `__pycache__`, `.venv`, `node_modules`, etc.

### Removed
- Top-level scratch script (`test_ts.py`) and committed runtime artifacts
  (`contextmesh.db`, demo `*.txt`/`*.md` outputs).
