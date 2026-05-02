# Contributing to ContextMesh

Thanks for considering a contribution! ContextMesh is small and intentionally
modular — most pull requests touch a single subpackage.

## Development setup

```bash
git clone https://github.com/Alivanroy/ContextMesh.git
cd ContextMesh
poetry install        # or: pip install -e ".[dev]"
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
