"""Token budget allocator.

Given an ordered list of packets and a token budget, pack the highest-value
packets first and return the truncated list plus stats. Default priority order
favours task/uncertainty/test-failure/symbol packets over file summaries and
references.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from contextmesh.runtime.ledger import estimate_tokens

PRIORITY = {
    "task": 0,
    "uncertainty": 1,
    "test_failure": 2,
    "command_result": 2,
    "symbol": 3,
    "next_context": 4,
    "file_summary": 5,
    "repo_summary": 6,
    "symbol_ref": 7,
    "file_ref": 7,
}


@dataclass
class BudgetResult:
    packets: list[dict]
    tokens_used: int
    tokens_dropped: int
    dropped_count: int

    def as_dict(self) -> dict:
        return {
            "packets": self.packets,
            "tokens_used": self.tokens_used,
            "tokens_dropped": self.tokens_dropped,
            "dropped_count": self.dropped_count,
        }


def _packet_tokens(packet: dict) -> int:
    return estimate_tokens(json.dumps(packet, ensure_ascii=False))


def apply_budget(packets: Iterable[dict], max_tokens: int) -> BudgetResult:
    ordered = sorted(
        list(packets),
        key=lambda p: (PRIORITY.get(p.get("type", ""), 99), len(json.dumps(p))),
    )
    kept: list[dict] = []
    used = 0
    dropped = 0
    dropped_count = 0
    for packet in ordered:
        cost = _packet_tokens(packet)
        if used + cost <= max_tokens:
            kept.append(packet)
            used += cost
        else:
            dropped += cost
            dropped_count += 1
    return BudgetResult(
        packets=kept,
        tokens_used=used,
        tokens_dropped=dropped,
        dropped_count=dropped_count,
    )
