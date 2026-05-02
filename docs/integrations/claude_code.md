# Claude Code

[Claude Code](https://claude.com/claude-code) is an interactive coding agent
that already supports running shell commands and reading local files —
exactly the surface ContextMesh assumes.

## One-time setup

```bash
contextmesh init
contextmesh index .
```

Add a `CLAUDE.md` to your repo root so Claude Code learns the protocol:

```markdown
# Working with ContextMesh

This repo uses ContextMesh to keep context small. When you start a task:

1. Read `CONTEXT_PACKET.md` first. It has typed packets for the relevant
   files and any failing tests. Do **not** read full files until you've
   exhausted the packets.
2. When a packet shows `raw_available: true` and you need the body, run:
   `contextmesh expand <file> <symbol>` — never `cat` the whole file.
3. Run tests via `contextmesh run pytest tests/<...>` (or
   `contextmesh run npm test`). The output is a single JSON packet, not
   500 lines of pytest noise.
4. Before finishing, append a ledger step:
   `contextmesh ledger record --task-id <id> --step <n> \
     --decision "<what you did>" --outcome ok`.
```

## Per-task workflow

```bash
# 1. Generate the packet
contextmesh export-context \
  --task "Fix password reset expiry bug" \
  --task-id reset-bug \
  --format markdown \
  --out CONTEXT_PACKET.md

# 2. Hand the file to Claude Code
claude "Use CONTEXT_PACKET.md as your primary context. Fix the bug."
```

The `--task-id` is what makes the second call cheap — packet hashes already
shown to the agent for `reset-bug` come back as `symbol_ref`s.

## Tip: stop logs from blowing the context window

Add a hook (`.claude/settings.json`) that rewrites bare `pytest` calls to
`contextmesh run pytest`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq '.tool_input.command |= sub(\"^pytest\"; \"contextmesh run pytest\")'"
          }
        ]
      }
    ]
  }
}
```
