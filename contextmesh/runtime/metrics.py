"""Useful-context metrics over the ledger.

The headline metric is :func:`useful_context_ratio`. Definition (see
``docs/metrics.md`` for the long form):

    For a single task with ledger steps ``s_1 ... s_n``, with
    ``t_i = s_i.tokens_estimated`` and final outcome class ``c``:

        useful_tokens(task)  = sum(t_i)  if c == "passed"
                             = 0         otherwise
        billed_tokens(task)  = sum(t_i)
        useful_context_ratio(task) = useful_tokens / billed_tokens

    Across tasks, the *aggregate* ratio is token-weighted:

        aggregate = sum(useful_tokens) / sum(billed_tokens)

This is deliberately strict: a task whose final outcome is anything other
than ``passed`` contributes zero useful tokens, so wasted context is fully
penalised. The metric rewards *finishing*, not *trying*.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from sqlmodel import select

from contextmesh.storage.db import LedgerEntry, create_db_and_tables, get_session


@dataclass
class TaskMetrics:
    task_id: str
    steps: int
    final_outcome_class: str
    tokens_billed: int
    tokens_avoided: int
    tokens_kept_compressed: int
    tokens_kept_pinned: int
    useful_context_ratio: float
    raw_baseline_estimate: int  # tokens_billed + tokens_avoided
    tokens_provider_input: int = 0
    tokens_cached_read: int = 0
    tokens_cached_write: int = 0
    tokens_provider_output: int = 0

    @property
    def has_provider_tokens(self) -> bool:
        return any((
            self.tokens_provider_input,
            self.tokens_cached_read,
            self.tokens_cached_write,
            self.tokens_provider_output,
        ))

    @property
    def cache_hit_rate(self) -> float:
        denom = (
            self.tokens_provider_input
            + self.tokens_cached_read
            + self.tokens_cached_write
        )
        return self.tokens_cached_read / denom if denom > 0 else 0.0

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "steps": self.steps,
            "final_outcome_class": self.final_outcome_class,
            "tokens_billed": self.tokens_billed,
            "tokens_avoided": self.tokens_avoided,
            "tokens_kept_compressed": self.tokens_kept_compressed,
            "tokens_kept_pinned": self.tokens_kept_pinned,
            "tokens_provider_input": self.tokens_provider_input,
            "tokens_cached_read": self.tokens_cached_read,
            "tokens_cached_write": self.tokens_cached_write,
            "tokens_provider_output": self.tokens_provider_output,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "useful_context_ratio": round(self.useful_context_ratio, 4),
            "raw_baseline_estimate": self.raw_baseline_estimate,
        }


@dataclass
class GlobalMetrics:
    tasks: int
    by_outcome: dict[str, int]
    tokens_billed: int
    tokens_avoided: int
    tokens_kept_compressed: int
    tokens_kept_pinned: int
    aggregate_useful_context_ratio: float
    aggregate_avoidance_ratio: float
    tokens_provider_input: int = 0
    tokens_cached_read: int = 0
    tokens_cached_write: int = 0
    tokens_provider_output: int = 0

    @property
    def has_provider_tokens(self) -> bool:
        return any((
            self.tokens_provider_input,
            self.tokens_cached_read,
            self.tokens_cached_write,
            self.tokens_provider_output,
        ))

    @property
    def aggregate_cache_hit_rate(self) -> float:
        denom = (
            self.tokens_provider_input
            + self.tokens_cached_read
            + self.tokens_cached_write
        )
        return self.tokens_cached_read / denom if denom > 0 else 0.0

    def as_dict(self) -> dict:
        return {
            "tasks": self.tasks,
            "by_outcome": dict(self.by_outcome),
            "tokens_billed": self.tokens_billed,
            "tokens_avoided": self.tokens_avoided,
            "tokens_kept_compressed": self.tokens_kept_compressed,
            "tokens_kept_pinned": self.tokens_kept_pinned,
            "tokens_provider_input": self.tokens_provider_input,
            "tokens_cached_read": self.tokens_cached_read,
            "tokens_cached_write": self.tokens_cached_write,
            "tokens_provider_output": self.tokens_provider_output,
            "aggregate_cache_hit_rate": round(self.aggregate_cache_hit_rate, 4),
            "aggregate_useful_context_ratio": round(self.aggregate_useful_context_ratio, 4),
            "aggregate_avoidance_ratio": round(self.aggregate_avoidance_ratio, 4),
        }


def _all_entries() -> list[LedgerEntry]:
    create_db_and_tables()
    with get_session() as session:
        return list(session.exec(select(LedgerEntry)).all())


def _by_task(entries: Iterable[LedgerEntry]) -> dict[str, list[LedgerEntry]]:
    out: dict[str, list[LedgerEntry]] = {}
    for e in entries:
        out.setdefault(e.task_id, []).append(e)
    for steps in out.values():
        steps.sort(key=lambda e: (e.step, e.id or 0))
    return out


def task_metrics(task_id: str) -> TaskMetrics:
    grouped = _by_task(_all_entries())
    steps = grouped.get(task_id, [])
    return _task_metrics_from_steps(task_id, steps)


def _task_metrics_from_steps(task_id: str, steps: list[LedgerEntry]) -> TaskMetrics:
    if not steps:
        return TaskMetrics(
            task_id=task_id,
            steps=0,
            final_outcome_class="unknown",
            tokens_billed=0,
            tokens_avoided=0,
            tokens_kept_compressed=0,
            tokens_kept_pinned=0,
            useful_context_ratio=0.0,
            raw_baseline_estimate=0,
        )
    billed = sum(s.tokens_estimated for s in steps)
    avoided = sum(s.tokens_avoided for s in steps)
    compressed = sum(s.tokens_kept_compressed for s in steps)
    pinned = sum(s.tokens_kept_pinned for s in steps)
    provider_in = sum(s.tokens_provider_input for s in steps)
    cached_read = sum(s.tokens_cached_read for s in steps)
    cached_write = sum(s.tokens_cached_write for s in steps)
    provider_out = sum(s.tokens_provider_output for s in steps)
    final = steps[-1].outcome_class
    useful = billed if final == "passed" else 0
    ratio = useful / billed if billed > 0 else 0.0
    return TaskMetrics(
        task_id=task_id,
        steps=len(steps),
        final_outcome_class=final,
        tokens_billed=billed,
        tokens_avoided=avoided,
        tokens_kept_compressed=compressed,
        tokens_kept_pinned=pinned,
        useful_context_ratio=ratio,
        raw_baseline_estimate=billed + avoided,
        tokens_provider_input=provider_in,
        tokens_cached_read=cached_read,
        tokens_cached_write=cached_write,
        tokens_provider_output=provider_out,
    )


def all_task_metrics() -> list[TaskMetrics]:
    grouped = _by_task(_all_entries())
    return [_task_metrics_from_steps(t, steps) for t, steps in grouped.items()]


def global_metrics() -> GlobalMetrics:
    metrics = all_task_metrics()
    if not metrics:
        return GlobalMetrics(
            tasks=0, by_outcome={}, tokens_billed=0, tokens_avoided=0,
            tokens_kept_compressed=0, tokens_kept_pinned=0,
            aggregate_useful_context_ratio=0.0, aggregate_avoidance_ratio=0.0,
        )
    by_outcome = Counter(m.final_outcome_class for m in metrics)
    billed = sum(m.tokens_billed for m in metrics)
    avoided = sum(m.tokens_avoided for m in metrics)
    compressed = sum(m.tokens_kept_compressed for m in metrics)
    pinned = sum(m.tokens_kept_pinned for m in metrics)
    provider_in = sum(m.tokens_provider_input for m in metrics)
    cached_read = sum(m.tokens_cached_read for m in metrics)
    cached_write = sum(m.tokens_cached_write for m in metrics)
    provider_out = sum(m.tokens_provider_output for m in metrics)
    useful = sum(m.tokens_billed for m in metrics if m.final_outcome_class == "passed")
    return GlobalMetrics(
        tasks=len(metrics),
        by_outcome=dict(by_outcome),
        tokens_billed=billed,
        tokens_avoided=avoided,
        tokens_kept_compressed=compressed,
        tokens_kept_pinned=pinned,
        aggregate_useful_context_ratio=useful / billed if billed > 0 else 0.0,
        aggregate_avoidance_ratio=avoided / (billed + avoided) if (billed + avoided) > 0 else 0.0,
        tokens_provider_input=provider_in,
        tokens_cached_read=cached_read,
        tokens_cached_write=cached_write,
        tokens_provider_output=provider_out,
    )


# ----- waste detection -----

@dataclass
class WasteRecord:
    """A packet hash sent to the same agent more than ``threshold`` times."""
    packet_hash: str
    times_sent: int
    tasks: list[str]
    estimated_tokens_per_send: int
    wasted_tokens: int


def find_repeat_waste(threshold: int = 3) -> list[WasteRecord]:
    """Identify packet hashes the seen-cache should have suppressed.

    A hash that appears in more than ``threshold`` distinct tasks suggests
    either bad ``--task-id`` discipline (each task being treated as new) or
    a packet that should be promoted to a per-project cache.
    """
    from contextmesh.storage.db import SeenPacket

    create_db_and_tables()
    with get_session() as session:
        rows = list(session.exec(select(SeenPacket)).all())

    by_hash: dict[str, list[SeenPacket]] = {}
    for r in rows:
        by_hash.setdefault(r.packet_hash, []).append(r)

    out: list[WasteRecord] = []
    for h, entries in by_hash.items():
        tasks = sorted({e.task_id for e in entries})
        if len(tasks) > threshold:
            # Rough cost estimate: typical SymbolPacket JSON ~ 80 tokens.
            per_send = 80 if entries[0].packet_type == "symbol" else 30
            wasted = (len(tasks) - 1) * per_send
            out.append(WasteRecord(
                packet_hash=h,
                times_sent=len(tasks),
                tasks=tasks,
                estimated_tokens_per_send=per_send,
                wasted_tokens=wasted,
            ))
    out.sort(key=lambda w: w.wasted_tokens, reverse=True)
    return out
