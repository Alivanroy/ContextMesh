# Codex CLI

OpenAI's Codex CLI runs as a local agent with shell + filesystem access.
Treat ContextMesh as a pre-processor that produces the prompt context.

## Setup

```bash
contextmesh init
contextmesh index .
```

## Per-task

```bash
contextmesh export-context \
  --task "Add rate limiting to /login" \
  --task-id rate-limit \
  --format jsonl \
  --out .contextmesh/last_packet.jsonl

codex --context .contextmesh/last_packet.jsonl \
      "Add rate limiting to /login. Follow the packets; expand symbols only when needed."
```

JSONL is friendlier than markdown if you're injecting via tool-use calls.
Use `--budget 8000` to cap the export at, say, 8k tokens.

## Tool surface

Expose `contextmesh expand` and `contextmesh run` as the only blessed tools
the agent can call. That keeps it on the rails: it cannot accidentally `cat`
a 5000-line file.
