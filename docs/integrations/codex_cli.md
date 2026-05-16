# Codex CLI

OpenAI's Codex CLI runs as a local agent with shell + filesystem access.
ContextMesh can either trace `codex exec --json` directly or pre-process a
packet bundle for the prompt.

## Setup

```bash
contextmesh init
contextmesh index .
```

## Trace Mode

```bash
contextmesh trace --task-id rate-limit --agent codex-cli -- \
  codex -a never exec --json --sandbox workspace-write \
    "Add rate limiting to /login and run the tests."
```

The adapter reads `item.completed` and `turn.completed` JSONL events, records
completed shell commands, and maps Codex usage like this:

- `input_tokens - cached_input_tokens` → provider input
- `cached_input_tokens` → cache reads
- `output_tokens` → provider output

Non-JSON warning lines are ignored.

## Packet Mode

```bash
contextmesh export-context \
  --task "Add rate limiting to /login" \
  --task-id rate-limit \
  --format jsonl \
  --out .contextmesh/last_packet.jsonl

codex "Add rate limiting to /login. Follow .contextmesh/last_packet.jsonl; expand symbols only when needed."
```

JSONL is friendlier than markdown if you're injecting via tool-use calls.
Use `--budget 8000` to cap the export at, say, 8k tokens.

## Tool surface

Expose `contextmesh expand` and `contextmesh run` as the only blessed tools
the agent can call. That keeps it on the rails: it cannot accidentally `cat`
a 5000-line file.
