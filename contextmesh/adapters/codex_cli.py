"""Adapter for ``codex exec --json`` JSONL streams."""
from __future__ import annotations

import json

from contextmesh.adapters.base import Adapter, stable_text_ref
from contextmesh.adapters.claude_code import _classify_pytest_outcome, _looks_like_pytest
from contextmesh.runtime.ledger import estimate_tokens
from contextmesh.wrappers.test_runner import distill_command_output


def _int_usage(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class CodexCliAdapter(Adapter):
    name = "codex-cli"

    def __init__(self, task_id: str, agent: str | None = None) -> None:
        super().__init__(task_id, agent)
        self._thread_id: str | None = None
        self._last_message: str = ""
        self._last_pytest_outcome: str | None = None

    def feed(self, line: str) -> list[dict]:
        line = line.strip()
        if not line or not line.startswith("{"):
            return []
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(event, dict):
            return []

        etype = event.get("type")
        if etype == "thread.started":
            self._thread_id = str(event.get("thread_id") or "")
            return []
        if etype == "item.completed":
            return self._on_item_completed(event.get("item") or {})
        if etype == "turn.completed":
            return self._on_turn_completed(event.get("usage") or {})
        return []

    def _on_item_completed(self, item: dict) -> list[dict]:
        itype = item.get("type")
        if itype == "agent_message":
            self._last_message = str(item.get("text") or "")
            return []
        if itype != "command_execution":
            return []

        command = str(item.get("command") or "command")
        output = str(item.get("aggregated_output") or "")
        exit_code_raw = item.get("exit_code")
        exit_code = exit_code_raw if isinstance(exit_code_raw, int) else None
        status = str(item.get("status") or "")
        outcome_class = "unknown"
        avoided = 0

        if output and _looks_like_pytest(output):
            classified = _classify_pytest_outcome(output)
            if classified is not None:
                self._last_pytest_outcome = classified
                outcome_class = classified
            distill_exit_code = exit_code if exit_code is not None else (
                0 if classified == "passed" else 1
            )
            packet = distill_command_output(["pytest"], distill_exit_code, output)
            packet_ref = stable_text_ref("generated_packet:command_result", packet.model_dump_json())
            avoided = max(0, estimate_tokens(output) - estimate_tokens(packet.model_dump_json()))
        else:
            packet_ref = ""
        if exit_code == 0:
            outcome = "ok"
        elif exit_code is not None or status in {"failed", "cancelled", "timed_out"}:
            outcome = "error"
        else:
            outcome = "unknown"

        refs = [
            f"command:{command[:120]}",
            "tool_output:command_execution",
            stable_text_ref("tool_output:command_execution", output) if output else "",
            packet_ref,
        ]

        return [{
            "task_id": self.task_id,
            "step": self._next_step(),
            "agent": self.agent,
            "context_refs": [ref for ref in refs if ref],
            "context_text": output[-1000:] if output else command,
            "tokens_estimated": 0,
            "tokens_avoided": avoided,
            "decision": f"command: {command[:500]}",
            "outcome": outcome,
            "outcome_class": outcome_class,
        }]

    def _on_turn_completed(self, usage: dict) -> list[dict]:
        input_tokens = _int_usage(usage.get("input_tokens"))
        cached_tokens = _int_usage(usage.get("cached_input_tokens"))
        output_tokens = _int_usage(usage.get("output_tokens"))
        uncached_input = max(0, input_tokens - cached_tokens)
        outcome_class = self._last_pytest_outcome or "unknown"
        refs = ["turn.completed"]
        if self._thread_id:
            refs.append(f"thread:{self._thread_id}")
        if self._last_message:
            refs.append(stable_text_ref("prompt_block:agent_message", self._last_message))

        return [{
            "task_id": self.task_id,
            "step": self._next_step(),
            "agent": self.agent,
            "context_refs": refs,
            "context_text": self._last_message[:1000],
            "tokens_provider_input": uncached_input,
            "tokens_cached_read": cached_tokens,
            "tokens_provider_output": output_tokens,
            "decision": "final",
            "outcome": "ok",
            "outcome_class": outcome_class,
        }]
