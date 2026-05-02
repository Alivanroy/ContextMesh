> **2026-05-02 — scope amendment.** After a market read against Repomix,
> Aider's repo map, Sourcegraph Cody, Mem0/Letta, and Anthropic's prompt
> caching, this plan has been narrowed. The original v0.3–v0.5
> ambitions (MCP proxy, RAG optimization, security layer) are deferred
> indefinitely — Anthropic's MCP Tool Search and prompt caching now solve
> most of what those would have done. The new product is the
> **observability layer**: a typed ledger of agent context spend, with a
> single headline metric (`useful_context_ratio`) defined in
> [docs/metrics.md](docs/metrics.md). Everything below from here on is
> historical context for v0.1; the live roadmap lives in the README.

---

Great. Let’s turn it into a real project.

Project name

ContextMesh

Tagline:

The context optimization layer for coding agents, MCP workflows, RAG, and multi-agent AI systems.

Core promise:

Reduce token waste by replacing transcript-style agent communication with typed, compressed, evidence-backed context packets.

⸻

1. The product thesis

Current agents waste tokens because they repeatedly ingest:

full files
full logs
full tool schemas
full chat history
duplicate summaries
irrelevant RAG chunks
verbose inter-agent messages
stale context already seen before

ContextMesh treats context as a managed resource.

Not “make prompts shorter.”

Instead:

context becomes versioned, compressed, typed, trusted, measured, and lazily loaded.

⸻

2. First target use case

Start with the clearest pain:

Token optimization for Claude Code / Codex CLI / Cursor-style coding agents

Why this is the best MVP:

clear developer pain
easy to benchmark
easy to demo
works locally
does not require enterprise sales
can become open source quickly
can later expand to MCP, RAG, SOC agents, compliance agents


⸻

3. MVP v0.1

The first version should do only five things very well.

Feature 1 — Repository fingerprinting

Index the codebase.

Track:

files
functions
classes
imports
exports
tests
config files
hashes
last-seen state

Goal:

avoid sending the same repository facts again and again.

⸻

Feature 2 — Compressed context packets

Transform raw context into small packets.

Example:

{
  "packet_type": "code_symbol",
  "symbol": "verify_reset_token",
  "file": "src/auth/reset.py",
  "signature": "def verify_reset_token(token: str) -> bool",
  "summary": "Validates reset token and checks expiration timestamp.",
  "dependencies": ["time.time", "PasswordResetToken"],
  "tests": ["tests/auth/test_reset.py"],
  "hash": "sha256:...",
  "raw_body_available": true
}

The model sees the packet first.

It only gets the raw code body when necessary.

⸻

Feature 3 — CLI output distillation

Wrap test commands.

Instead of sending 500 lines of logs, send:

{
  "command": "pytest",
  "status": "failed",
  "failures": [
    {
      "test": "test_valid_reset_token",
      "assertion": "expected True, got False",
      "file": "tests/auth/test_reset.py",
      "line": 42,
      "minimal_trace": "verify_reset_token returned expired"
    }
  ],
  "new_failures_since_last_run": 1,
  "fixed_failures_since_last_run": 0
}

This alone can save a lot of tokens.

⸻

Feature 4 — Context ledger

Every model step gets recorded.

{
  "task_id": "T-001",
  "step": 4,
  "agent": "coder",
  "context_used": [
    "src/auth/reset.py:verify_reset_token",
    "tests/auth/test_reset.py:test_valid_reset_token"
  ],
  "tokens_estimated": 2180,
  "decision": "patch expiry comparison",
  "outcome": "tests_passed"
}

This gives the project a unique advantage:

you can measure which context actually helped.

⸻

Feature 5 — Token receipts dashboard

Simple local dashboard:

Task: fix password reset bug

Total estimated tokens: 11,420
Raw context avoided: 32,800
Repeated file reads avoided: 7
Largest token source: pytest logs
Most reused packet: auth.reset.verify_reset_token
Outcome: tests passed

This makes the value visible.

⸻

4. MVP architecture

contextmesh/
  cli/
    main.py
  indexer/
    repo_indexer.py
    tree_sitter_parser.py
    fingerprint.py
  packets/
    schema.py
    compressor.py
  runtime/
    ledger.py
    budget.py
    context_router.py
  wrappers/
    test_runner.py
    shell_runner.py
  integrations/
    claude_code.md
    codex_cli.md
    cursor.md
  dashboard/
    app.py
  storage/
    sqlite.py


⸻

5. Core CLI commands

contextmesh init
contextmesh index .
contextmesh summary
contextmesh run pytest
contextmesh packet src/auth/reset.py
contextmesh ledger
contextmesh dashboard
contextmesh export-context --task "fix reset token expiry"

Later:

contextmesh mcp-proxy
contextmesh rag-router
contextmesh agent-mailbox
contextmesh eval


⸻

6. How it integrates with Claude Code or Codex

The simplest way:

contextmesh index .
contextmesh export-context --task "Fix password reset expiry bug" > CONTEXT_PACKET.md

Then tell Claude Code / Codex:

Use CONTEXT_PACKET.md as your primary context.
Do not read full files unless the packet says raw_body_required.
Ask for exact symbols or line ranges only.
Use contextmesh run pytest instead of pytest directly.

More advanced later:

contextmesh run-agent claude "Fix password reset expiry bug"
contextmesh run-agent codex "Fix password reset expiry bug"


⸻

7. Context packet format

Use JSONL for machine readability.

Example:

{"type":"task","goal":"Fix password reset expiry bug","constraints":["minimize raw file reads","use existing tests"]}
{"type":"repo_summary","language":"python","frameworks":["fastapi","pytest"],"files_indexed":143}
{"type":"symbol","name":"verify_reset_token","file":"src/auth/reset.py","signature":"def verify_reset_token(token: str) -> bool","summary":"Validates token and checks expiry.","hash":"a91f","raw_available":true}
{"type":"test_failure","test":"test_valid_reset_token","file":"tests/auth/test_reset.py","line":42,"assertion":"expected True, got False","minimal_trace":"verify_reset_token returned expired"}
{"type":"uncertainty","value":"Need to verify whether expires_at is seconds or milliseconds."}
{"type":"next_context","items":["body:verify_reset_token","schema:password_reset_tokens"]}

For human-facing agent prompts, export to Markdown.

⸻

8. Differentiator: useful-context ratio

Most tools measure only token count.

ContextMesh should measure:

repeated_context_ratio
raw_context_ratio
compressed_context_ratio
useful_context_ratio
context_reuse_rate
tokens_per_successful_task
tokens_per_failed_attempt
tool_schema_token_load
log_token_load

The most important metric:

useful progress per token

That can become your signature concept.

⸻

9. The open-source positioning

GitHub description:

ContextMesh is an open-source context optimization layer for AI coding agents. It reduces token waste by indexing repositories, compressing code and CLI outputs into typed context packets, tracking what agents have already seen, and exposing evidence-backed context to Claude Code, Codex, Cursor, MCP, and local LLM workflows.

README opening:

# ContextMesh

AI coding agents do not need more context.
They need better context.

ContextMesh helps coding agents spend fewer tokens by replacing full files,
verbose logs, and repeated tool outputs with typed, compressed, evidence-backed
context packets.


⸻

10. Roadmap

v0.1 — Local coding-agent optimizer

repo indexing
symbol fingerprints
context packets
pytest/npm test output compression
context ledger
markdown export
basic dashboard

v0.2 — Multi-agent Context Mesh

agent mailboxes
semantic state packets
agent-to-agent context deduplication
context receipts
role-specific context views

v0.3 — MCP optimization

MCP proxy
lazy tool schema loading
tool capability graph
tool-call result compression
tool-risk labeling

v0.4 — RAG optimization

proof-oriented retrieval
claim/evidence/contradiction packets
retrieval budget allocator
document context receipts

v0.5 — Security layer

prompt-injection firewall
untrusted context labeling
policy engine
context quarantine
data/instruction separation


⸻

11. Research framing

Paper title:

ContextMesh: Delta-Aware Context Compression and Evidence-Gated Retrieval for Multi-Agent LLM Systems

Core research question:

Can delta-aware, evidence-gated context packets reduce token usage in coding agents and multi-agent systems without reducing task success?

Main contribution:

1. typed semantic context packets
2. context ledger with token receipts
3. delta-aware repository memory
4. CLI output distillation
5. multi-agent context deduplication
6. useful-progress-per-token evaluation metric


⸻

12. Build plan for the first week

Day 1 — Repo skeleton

mkdir contextmesh
cd contextmesh
poetry init
poetry add typer rich pydantic sqlmodel tree-sitter tree-sitter-python tiktoken pytest

Create:

contextmesh/cli/main.py
contextmesh/indexer/fingerprint.py
contextmesh/storage/db.py
contextmesh/packets/schema.py

Day 2 — File indexing

Index:

path
language
size
sha256
last_modified
line_count

Day 3 — Symbol extraction

Start with Python only.

Extract:

functions
classes
methods
signatures
line ranges
docstrings
imports

Day 4 — Packet generation

Generate:

repo_summary
file_summary
symbol_packet
test_packet
uncertainty_packet

Day 5 — CLI output compressor

Support:

pytest
npm test
generic shell command

Day 6 — Ledger

Track:

task_id
step
context refs
estimated token count
outcome

Day 7 — Demo

Demo scenario:

1. Take a small repo with a failing test.
2. Run normal Claude/Codex workflow.
3. Run ContextMesh-assisted workflow.
4. Compare tokens, logs, repeated reads, and result quality.


⸻

13. First technical schema

from pydantic import BaseModel
from typing import Literal, Optional, List


class EvidenceRef(BaseModel):
    ref_type: Literal["file", "symbol", "test", "cli_output", "doc"]
    path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    hash: Optional[str] = None


class ContextPacket(BaseModel):
    packet_id: str
    packet_type: str
    summary: str
    evidence: List[EvidenceRef] = []
    confidence: float = 1.0
    raw_available: bool = True
    token_estimate: Optional[int] = None
    trust_level: Literal["trusted", "untrusted", "generated"] = "trusted"


⸻

14. First slogan options

Stop paying twice for the same context.

The context control plane for AI agents.

Better context. Fewer tokens. Safer agents.

A token economy for agentic AI.

My favorite:

Stop paying twice for the same context.

It is simple, memorable, and developer-friendly.

⸻

15. Immediate next move

Start with the GitHub repo as an open-source project:

ContextMesh
MIT or Apache-2.0 license
Python CLI
Developer-first README
One strong demo
One benchmark table

The first public demo should show:

Before:
Agent reads 6 files, 2 full logs, 40k estimated input tokens.

After:
Agent receives 9 packets, 2 exact function bodies, 1 compressed test failure, 12k estimated input tokens.

Result:
Same patch, fewer tokens, cleaner reasoning path.

This is concrete enough to build, benchmark, and post publicly.