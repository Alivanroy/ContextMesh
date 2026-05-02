# Architecture

ContextMesh is intentionally small. Every module does one thing.

## Modules

```
contextmesh/
  config.py         project-root detection, .contextmesh/ paths, ignore set
  cli/main.py       Typer CLI: init, index, export-context, run, expand,
                    ledger, dashboard, reset-cache
  indexer/
    fingerprint.py    sha256, language detection, walk_repo
    tree_sitter_parser.py  Python AST → ExtractedSymbol / ExtractedImport
    repo_indexer.py   walks the tree, persists IndexedFile/IndexedSymbol;
                      delta-aware (skips unchanged sha256)
  packets/
    schema.py         pydantic models for every packet type
    generator.py      file/repo/symbol packet builders + framework detection
    compressor.py     swaps already-seen packets for symbol_ref / file_ref
    markdown.py       renders packets as markdown for agents
  runtime/
    ledger.py         records every step (tokens spent, tokens avoided)
    budget.py         priority-ordered packet packing under a token cap
    dashboard.py      rich/terminal view over the ledger and index
  storage/db.py       sqlmodel tables + project-scoped engine
  wrappers/
    shell_runner.py   subprocess shim with timeout
    test_runner.py    pytest / jest / generic distillation
  agent/tools.py      expand_symbol / expand_symbol_indexed
```

## State

State lives in `<project>/.contextmesh/contextmesh.db`. Tables:

- `indexed_file(path PK, sha256, language, size, line_count, last_modified, last_indexed)`
- `indexed_symbol(file_path, name, parent, symbol_type, signature, body_hash, ...)`
- `seen_packet(task_id, packet_hash, packet_type, seen_at)` — delta cache
- `ledger_entry(task_id, step, agent, tokens_estimated, tokens_avoided, decision, outcome, ...)`

Tests pin `CONTEXTMESH_STATE_DIR` to `tmp_path` so they never touch the real
database.

## End-to-end flow

1. `contextmesh init` creates `.contextmesh/` and adds it to `.gitignore`.
2. `contextmesh index .` walks the repo, hashes files, and on Python files
   parses symbols. Re-runs only update files whose `sha256` changed.
3. `contextmesh export-context --task ... --task-id T` builds a packet list
   (task → repo_summary → symbols), runs it through the compressor (which
   substitutes any packet hash already seen for task `T`) and the budget
   allocator, then renders Markdown or JSONL.
4. The agent reads the packet bundle. When it needs a body, it calls
   `contextmesh expand <file> <symbol>`.
5. `contextmesh run pytest tests/` distills the test output into a
   `CommandResultPacket`. Hand that to the agent — not raw logs.
6. `contextmesh ledger record …` (or your own integration) appends a step.
7. `contextmesh dashboard` shows tokens spent vs. avoided.

## Why a typed packet schema

Strings are opaque. Typed packets let the agent — and you — reason about the
*shape* of context: which packets describe code, which describe a failure,
which are already known. That's what makes delta compression and useful-context
metrics possible.
