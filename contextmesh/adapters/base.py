"""Adapter contract — translate one agent's tool-call stream into ledger events.

Each adapter consumes its agent's NDJSON stream (or whatever) line by line
and yields events shaped like :func:`contextmesh.runtime.ledger.record_event`
kwargs. ``contextmesh trace`` glues a subprocess + an adapter + the ledger.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Adapter(ABC):
    """Stateful, line-fed parser for an agent's stream output."""

    name: str = "base"

    def __init__(self, task_id: str, agent: str | None = None) -> None:
        self.task_id = task_id
        self.agent = agent or self.name
        self.step = 0

    def _next_step(self) -> int:
        self.step += 1
        return self.step

    @abstractmethod
    def feed(self, line: str) -> list[dict]:
        """Process one line of agent output.

        Returns zero or more ledger-event dicts. The trace command records
        each one immediately; never buffer beyond what's strictly needed
        to correlate paired events (e.g. tool_use ↔ tool_result).
        """

    def finalize(self) -> list[dict]:
        """Called after the stream ends. Default: nothing to flush."""
        return []
