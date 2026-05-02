# Packet schema reference

All packets are pydantic models defined in
[`contextmesh/packets/schema.py`](../contextmesh/packets/schema.py). They
share a `type` discriminator so they can be streamed as JSONL.

## `task`

The user's goal and constraints. Always the first packet in an export.

```json
{"type": "task", "goal": "Fix password reset expiry bug",
 "constraints": ["minimize raw file reads", "use existing tests"]}
```

## `repo_summary`

A bird's-eye view of the indexed repository.

```json
{"type": "repo_summary", "languages": ["python"],
 "frameworks": ["pytest", "fastapi"], "files_indexed": 143, "symbols_indexed": 412}
```

## `file_summary`

One per file the agent might care about.

```json
{"type": "file_summary", "file": "src/auth/reset.py",
 "language": "python", "size": 412, "line_count": 18, "hash": "9a3c..."}
```

## `symbol`

Functions, methods, and classes with signature + docstring. The body stays
on disk; the agent calls `contextmesh expand` only when needed.

```json
{"type": "symbol", "name": "verify_reset_token",
 "file": "src/auth/reset.py", "parent": null,
 "signature": "def verify_reset_token(token: str) -> bool",
 "summary": "Validates token and checks expiration timestamp.",
 "hash": "f12888eb...", "raw_available": true}
```

## `symbol_ref` / `file_ref`

The compressor emits these when the agent has already seen a packet's hash
during the same task. They cost ~10 tokens each.

```json
{"type": "symbol_ref", "hash": "f12888eb...",
 "name": "verify_reset_token", "file": "src/auth/reset.py"}
```

## `test_failure`

One per failing test, distilled from raw pytest/jest output.

```json
{"type": "test_failure", "test": "test_valid_reset_token",
 "file": "tests/auth/test_reset.py", "line": 10,
 "assertion": "AssertionError: assert False == True",
 "minimal_trace": ">       assert verify_reset_token(...) == True\\nE       AssertionError: ..."}
```

## `command_result`

The wrapper packet that contains 0..N `test_failure` packets plus
metadata. Only emitted by `contextmesh run`.

```json
{"type": "command_result", "command": "pytest tests/",
 "status": "failed", "failures": [...],
 "new_failures_since_last_run": 1, "fixed_failures_since_last_run": 0}
```

## `uncertainty`

Anything ambiguous the agent should resolve before patching.

```json
{"type": "uncertainty",
 "value": "Need to verify whether expires_at is seconds or milliseconds."}
```

## `next_context`

What the agent thinks it needs next — a hint for the next CLI invocation.

```json
{"type": "next_context",
 "items": ["body:verify_reset_token", "schema:password_reset_tokens"]}
```

## Trust levels

`ContextPacket.trust_level` is one of `trusted | untrusted | generated`. The
v0.5 security layer will use this to quarantine context that came from
documents or web tools rather than the local filesystem.
