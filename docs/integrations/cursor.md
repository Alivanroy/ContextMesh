# Cursor

Cursor doesn't expose a native shell tool, so the ContextMesh integration is
file-based: you generate a packet bundle and `@`-mention it.

## Setup

```bash
contextmesh init
contextmesh index .
```

## Per-task

```bash
contextmesh export-context \
  --task "Refactor token validation to use a TokenStore" \
  --task-id token-store \
  --format markdown \
  --out CONTEXT_PACKET.md
```

In Cursor's chat: `@CONTEXT_PACKET.md` and prompt:

> Use the packets above as your primary context. Use `Read file` only on
> files mentioned in the packets, and only on the lines indicated by their
> `symbol` packets. Run tests via the terminal with
> `contextmesh run pytest`.

## Rules file

Drop a `.cursor/rules/contextmesh.md` like:

```markdown
- Prefer `contextmesh expand <file> <symbol>` over `Read file` when a
  packet shows `raw_available: true`.
- Treat any packet whose `type` is `symbol_ref` as already known — do not
  re-read it.
- Append a ledger step at the end of every task with
  `contextmesh ledger record`.
```
