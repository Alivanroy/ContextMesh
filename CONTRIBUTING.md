# Contributing to ContextMesh

Thanks for considering a contribution! ContextMesh is small and intentionally
modular — most pull requests touch a single subpackage.

## Development setup

```bash
git clone https://github.com/Alivanroy/ContextMesh.git
cd ContextMesh
poetry install        # or: pip install -e . && pip install pytest pytest-cov ruff
pytest                # full test suite must pass
```

State is stored under `.contextmesh/` per project. Tests pin
`CONTEXTMESH_STATE_DIR` to a `tmp_path`, so they never touch the real DB.

## Project layout

```
contextmesh/
  cli/         user-facing typer commands
  indexer/     fingerprint + tree-sitter parsing + persisted index
  packets/     pydantic schemas, generators, compressor, markdown export
  runtime/     ledger, token budget, terminal dashboard
  storage/     sqlmodel tables and engine
  wrappers/    shell/test runners that emit CommandResultPacket
  agent/       tools an agent can call (`expand_symbol`, ...)
```

## Adding a new agent adapter

The hottest gap. v0.3 ships Claude Code (`stream-json`), Codex CLI
(`exec --json`), and Aider (`.aider.chat.history.md`); the next ones to
wire are:

- **OpenCode** — also stream-based, has tool-call envelopes. Same template.
- **Cursor** — local SQLite conversation log; the adapter polls or
  diffs the file rather than reading from a subprocess.

Recipe:

1. Drop a module under `contextmesh/adapters/<name>.py` subclassing
   `Adapter` with a stateful `feed(line) → list[event_dict]`.
2. Capture a real session as a fixture under `tests/fixtures/`. Synthetic
   fixtures are *only* OK as fallbacks; the headline tests should
   verify against captured-from-the-wild output.
3. Register it in `contextmesh/adapters/__init__.py`.
4. Mirror `tests/test_adapter_claude_code.py` for tests.

Targeting ~150 LoC of adapter + ~80 LoC of tests + 1 fixture file.

## Adding a tree-sitter language

1. `pip install tree-sitter-<lang>`.
2. Add a parse function alongside `parse_python_source` that returns the same
   `{"symbols": [...], "imports": [...]}` shape.
3. Wire it into `repo_indexer._upsert_symbols` based on `detect_language(...)`.
4. Add a focused test under `tests/`.

## Style

- No emojis in source or docs.
- Don't over-document: comments only for non-obvious *why*.
- Prefer narrow tests. Run `pytest -x -q` while iterating.
- Keep packet schemas additive and backwards-compatible (new optional fields,
  not field renames).

## Reporting issues

Please include:
- ContextMesh version (`pip show contextmesh`).
- Python version and OS.
- The full output of the failing command with `--raw` if applicable.
- A minimal repo or snippet that reproduces.

## Code of conduct

Be kind. Disagree about ideas, not people.
