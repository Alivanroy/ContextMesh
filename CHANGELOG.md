# Changelog

All notable changes to ContextMesh are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pivot — observability layer

The product has narrowed to the open observability layer for agent context
spend. The repo-packing and indexing surfaces are no longer the headline;
the ledger and `useful_context_ratio` are. See README.md and
[docs/metrics.md](docs/metrics.md).

### Fixed
- **Aider cost-line parsing in real fixtures**: real Aider 0.86.x emits
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
