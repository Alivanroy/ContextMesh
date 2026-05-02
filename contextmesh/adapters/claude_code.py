"""Adapter for ``claude --output-format stream-json``.

The Claude Code CLI emits NDJSON events of the shape:

  {"type": "system", "subtype": "init", ...}
  {"type": "assistant", "message": {"content": [...], "usage": {...}}}
  {"type": "user", "message": {"content": [{"type": "tool_result", ...}]}}
  ...
  {"type": "result", "subtype": "success", "usage": {...}, "result": "..."}

This adapter turns that stream into one ledger step per assistant turn,
plus an extra synthetic step when a `tool_result` looked like distillable
test output (we credit the difference into ``tokens_avoided``), plus a
final ``result`` step with the closing usage numbers.
"""
from __future__ import annotations

import json
from typing import Any

from contextmesh.adapters.base import Adapter
from contextmesh.runtime.ledger import estimate_tokens
from contextmesh.wrappers.test_runner import distill_command_output


_PYTEST_MARKERS = ("test session starts", "FAILED ", "PASSED ", "passed in", "failed in")


def _looks_like_pytest(text: str) -> bool:
    return any(m in text for m in _PYTEST_MARKERS)


def _classify_pytest_outcome(text: str) -> str | None:
    """Return ``passed`` / ``regressed`` / ``unchanged`` for a pytest blob, or ``None``."""
    has_failed = " failed" in text.lower() or "FAILED " in text
    has_passed = " passed" in text.lower() or "PASSED " in text
    if has_failed and not has_passed:
        return "regressed"
    if has_failed and has_passed:
        return "regressed"  # mixed run still has failures
    if has_passed:
        return "passed"
    if "no tests ran" in text.lower():
        return "unchanged"
    return None


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                out.append(block.get("text") or block.get("content") or "")
            elif isinstance(block, str):
                out.append(block)
        return "".join(out)
    return ""


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"

    def __init__(self, task_id: str, agent: str | None = None) -> None:
        super().__init__(task_id, agent)
        self._last_pytest_outcome: str | None = None

    def feed(self, line: str) -> list[dict]:
        line = line.strip()
        if not line:
            return []
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(event, dict):
            return []

        t = event.get("type")
        if t == "assistant":
            return self._on_assistant(event)
        if t == "user":
            return self._on_user(event)
        if t == "result":
            return self._on_result(event)
        return []

    def _on_assistant(self, event: dict) -> list[dict]:
        msg = event.get("message", {}) or {}
        content = msg.get("content", []) or []
        usage = msg.get("usage", {}) or {}

        tool_calls: list[str] = []
        text_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use":
                tool = block.get("name", "tool")
                inp = block.get("input", {})
                target = ""
                if isinstance(inp, dict):
                    target = inp.get("file_path") or inp.get("path") or inp.get("command", "")
                tool_calls.append(f"{tool}({str(target)[:60]})" if target else tool)
            elif btype == "text":
                text_parts.append(block.get("text", ""))

        decision = " ".join(text_parts).strip()
        if not decision:
            decision = "; ".join(tool_calls) or "no-op"

        return [{
            "task_id": self.task_id,
            "step": self._next_step(),
            "agent": self.agent,
            "context_refs": tool_calls,
            "context_text": decision,
            "tokens_provider_input": int(usage.get("input_tokens", 0)),
            "tokens_cached_read": int(usage.get("cache_read_input_tokens", 0)),
            "tokens_cached_write": int(usage.get("cache_creation_input_tokens", 0)),
            "tokens_provider_output": int(usage.get("output_tokens", 0)),
            "decision": decision[:500],
            "outcome": "in_progress",
            "outcome_class": "unknown",
        }]

    def _on_user(self, event: dict) -> list[dict]:
        msg = event.get("message", {}) or {}
        content = msg.get("content", []) or []
        events: list[dict] = []

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = _flatten_content(block.get("content"))
            if not text or not _looks_like_pytest(text):
                continue
            classified = _classify_pytest_outcome(text)
            if classified is not None:
                self._last_pytest_outcome = classified
            packet = distill_command_output(["pytest"], 0 if "passed in" in text else 1, text)
            raw_tokens = estimate_tokens(text)
            distilled_tokens = estimate_tokens(packet.model_dump_json())
            avoided = max(0, raw_tokens - distilled_tokens)
            if avoided <= 0:
                continue
            events.append({
                "task_id": self.task_id,
                "step": self._next_step(),
                "agent": self.agent,
                "context_refs": ["tool_result:pytest"],
                "context_text": "",
                "tokens_estimated": 0,
                "tokens_avoided": avoided,
                "decision": "distilled pytest tool_result",
                "outcome": "ok",
                "outcome_class": "unknown",
            })
        return events

    def _on_result(self, event: dict) -> list[dict]:
        usage = event.get("usage", {}) or {}
        is_error = bool(event.get("is_error"))
        result_text = str(event.get("result") or "")[:1000]
        if is_error:
            outcome_class = "aborted"
        elif self._last_pytest_outcome:
            outcome_class = self._last_pytest_outcome
        else:
            outcome_class = "unknown"
        return [{
            "task_id": self.task_id,
            "step": self._next_step(),
            "agent": self.agent,
            "context_refs": ["result"],
            "context_text": result_text,
            "tokens_provider_input": int(usage.get("input_tokens", 0)),
            "tokens_cached_read": int(usage.get("cache_read_input_tokens", 0)),
            "tokens_cached_write": int(usage.get("cache_creation_input_tokens", 0)),
            "tokens_provider_output": int(usage.get("output_tokens", 0)),
            "decision": "final",
            "outcome": "error" if is_error else "ok",
            "outcome_class": outcome_class,
        }]
