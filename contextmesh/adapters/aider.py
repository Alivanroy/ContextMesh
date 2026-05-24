"""Adapter for Aider's ``.aider.chat.history.md`` format.

Aider doesn't stream JSON; it appends to a markdown chat history file.
The format we parse:

  # aider chat started at TIMESTAMP

  #### user prompt line 1
  #### (continued)

  assistant response in markdown

  > tool / system messages (single-line blockquotes)

  Tokens: 4.2k sent, 320 received. Cost: $0.013 message, $0.026 session.

Each ``####`` block opens a turn; the content up to the next ``####`` is
that turn's exchange. The ``Tokens: …`` summary line gives us provider
usage. We parse pytest output when we see it (in tool blockquotes or
fenced blocks) and use it to classify the final turn's outcome.
"""
from __future__ import annotations

import re

from contextmesh.adapters.base import Adapter, stable_text_ref
from contextmesh.adapters.claude_code import _classify_pytest_outcome, _looks_like_pytest
from contextmesh.runtime.ledger import estimate_tokens
from contextmesh.wrappers.test_runner import distill_command_output

_COST_LINE = re.compile(
    r"Tokens:\s*([\d.,]+\s*[kKmM]?)\s*sent,\s*([\d.,]+\s*[kKmM]?)\s*received\."
    r"(?:\s*Cost:\s*\$([\d.,]+))?",  # Cost: only present in summary lines, not per-turn
)
_USER_PREFIX = "####"


def _parse_count(token: str) -> int:
    raw = token.replace(",", "").strip().lower()
    multiplier = 1
    if raw.endswith("k"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return 0


class AiderAdapter(Adapter):
    name = "aider"

    def __init__(self, task_id: str, agent: str | None = None) -> None:
        super().__init__(task_id, agent)
        self._current: dict | None = None
        self._buf: list[str] = []
        self._last_pytest_outcome: str | None = None
        self._last_event_index: int | None = None

    def feed(self, line: str) -> list[dict]:
        stripped = line.rstrip("\n").rstrip("\r")
        # Section header at top of the file — treat as preamble.
        if stripped.startswith("# aider chat started"):
            return []
        if stripped.startswith(_USER_PREFIX):
            events = self._flush_turn()
            user_text = stripped[len(_USER_PREFIX):].strip()
            self._current = {"user_text": user_text}
            return events
        if self._current is None:
            return []

        # Tool / system blockquotes — Aider emits both pytest output AND the
        # ``Tokens: … sent, … received`` summary as ``> `` blockquotes, so we
        # have to check both inside and outside.
        if stripped.startswith("> "):
            content = stripped[2:]
            self._buf.append(content)
            if _looks_like_pytest(content):
                cls = _classify_pytest_outcome(content)
                if cls is not None:
                    self._last_pytest_outcome = cls
            self._capture_cost_line(content)
            return []

        # Cost summary anywhere else inside the turn body.
        self._capture_cost_line(stripped)
        self._buf.append(stripped)
        return []

    def _capture_cost_line(self, text: str) -> None:
        if self._current is None:
            return
        m = _COST_LINE.search(text)
        if not m:
            return
        self._current["tokens_sent"] = _parse_count(m.group(1))
        self._current["tokens_received"] = _parse_count(m.group(2))
        cost = m.group(3)
        if cost:
            try:
                self._current["cost_usd"] = float(cost.replace(",", ""))
            except ValueError:
                self._current["cost_usd"] = 0.0

    def _flush_turn(self) -> list[dict]:
        if self._current is None:
            return []
        turn = self._current
        body = "\n".join(self._buf)
        self._current = None
        self._buf = []

        # Detect pytest within the body for avoidance crediting.
        avoided = 0
        refs = ["user_input"]
        user_text = str(turn.get("user_text") or "")
        if user_text:
            refs.append(stable_text_ref("prompt_block:user", user_text))
        for chunk in body.split("\n\n"):
            if _looks_like_pytest(chunk) and len(chunk) > 200:
                packet = distill_command_output(["pytest"], 1, chunk)
                refs.extend([
                    "tool_output:pytest",
                    stable_text_ref("tool_output:pytest", chunk),
                    stable_text_ref("generated_packet:command_result", packet.model_dump_json()),
                ])
                avoided += max(
                    0,
                    estimate_tokens(chunk) - estimate_tokens(packet.model_dump_json()),
                )

        decision = (user_text or body[:200]).strip()
        event = {
            "task_id": self.task_id,
            "step": self._next_step(),
            "agent": self.agent,
            "context_refs": refs,
            "context_text": decision,
            "tokens_provider_input": int(turn.get("tokens_sent") or 0),
            "tokens_provider_output": int(turn.get("tokens_received") or 0),
            "tokens_avoided": avoided,
            "decision": decision[:500],
            "outcome": "in_progress",
            "outcome_class": "unknown",
        }
        return [event]

    def finalize(self) -> list[dict]:
        events = self._flush_turn()
        # Tag the last emitted turn with the auto-detected outcome.
        if events and self._last_pytest_outcome:
            events[-1]["outcome_class"] = self._last_pytest_outcome
            events[-1]["outcome"] = (
                "ok" if self._last_pytest_outcome == "passed" else "regressed"
            )
            events[-1]["decision"] = "final"
        return events
