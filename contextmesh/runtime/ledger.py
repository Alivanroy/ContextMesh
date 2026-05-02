"""Append-only ledger of context usage per task step."""
from __future__ import annotations

import json

from sqlmodel import select

from contextmesh.storage.db import LedgerEntry, create_db_and_tables, get_session


def estimate_tokens(text: str, *, encoding: str = "cl100k_base") -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding(encoding).encode(text))
    except Exception:
        return max(1, len(text) // 4)


VALID_OUTCOME_CLASSES = {"passed", "unchanged", "regressed", "aborted", "unknown"}


def _normalise_outcome_class(value: str | None) -> str:
    if not value:
        return "unknown"
    v = value.strip().lower()
    return v if v in VALID_OUTCOME_CLASSES else "unknown"


def record_step(
    task_id: str,
    step: int,
    agent: str,
    context_refs: list[str],
    context_text: str,
    decision: str,
    outcome: str,
    *,
    tokens_avoided: int = 0,
    tokens_kept_compressed: int = 0,
    tokens_kept_pinned: int = 0,
    outcome_class: str = "unknown",
) -> LedgerEntry:
    create_db_and_tables()
    avoided_total = max(
        tokens_avoided,
        tokens_kept_compressed + tokens_kept_pinned,
    )
    entry = LedgerEntry(
        task_id=task_id,
        step=step,
        agent=agent,
        context_used=json.dumps(context_refs),
        tokens_estimated=estimate_tokens(context_text),
        tokens_avoided=avoided_total,
        tokens_kept_compressed=tokens_kept_compressed,
        tokens_kept_pinned=tokens_kept_pinned,
        decision=decision,
        outcome=outcome,
        outcome_class=_normalise_outcome_class(outcome_class),
    )
    with get_session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def record_event(event: dict) -> LedgerEntry:
    """Append a step from an adapter-emitted event dict.

    Adapters (``contextmesh/adapters/*``) emit dicts shaped like the kwargs
    of :func:`record_step` plus optional provider-token fields. This helper
    is the single entry point so the schema mapping lives in one place.
    """
    create_db_and_tables()
    refs = event.get("context_refs", []) or []
    if isinstance(refs, str):
        refs = [refs]
    context_text = event.get("context_text", "") or ""
    estimated = event.get("tokens_estimated")
    if estimated is None:
        estimated = estimate_tokens(context_text) if context_text else 0
    entry = LedgerEntry(
        task_id=event["task_id"],
        step=event["step"],
        agent=event.get("agent", "unknown"),
        context_used=json.dumps(refs),
        tokens_estimated=int(estimated),
        tokens_avoided=int(event.get("tokens_avoided", 0)),
        tokens_kept_compressed=int(event.get("tokens_kept_compressed", 0)),
        tokens_kept_pinned=int(event.get("tokens_kept_pinned", 0)),
        tokens_provider_input=int(event.get("tokens_provider_input", 0)),
        tokens_cached_read=int(event.get("tokens_cached_read", 0)),
        tokens_cached_write=int(event.get("tokens_cached_write", 0)),
        tokens_provider_output=int(event.get("tokens_provider_output", 0)),
        decision=str(event.get("decision", "")),
        outcome=str(event.get("outcome", "ok")),
        outcome_class=_normalise_outcome_class(event.get("outcome_class")),
    )
    with get_session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def get_ledger(limit: int = 10, *, task_id: str | None = None) -> list[LedgerEntry]:
    create_db_and_tables()
    with get_session() as session:
        stmt = select(LedgerEntry).order_by(LedgerEntry.id.desc())
        if task_id:
            stmt = stmt.where(LedgerEntry.task_id == task_id)
        return list(session.exec(stmt.limit(limit)).all())


def task_summary(task_id: str) -> dict:
    create_db_and_tables()
    with get_session() as session:
        entries = list(session.exec(
            select(LedgerEntry).where(LedgerEntry.task_id == task_id)
        ).all())
    if not entries:
        return {
            "task_id": task_id,
            "steps": 0,
            "tokens_estimated": 0,
            "tokens_avoided": 0,
            "tokens_kept_compressed": 0,
            "tokens_kept_pinned": 0,
            "final_outcome_class": "unknown",
        }
    return {
        "task_id": task_id,
        "steps": len(entries),
        "tokens_estimated": sum(e.tokens_estimated for e in entries),
        "tokens_avoided": sum(e.tokens_avoided for e in entries),
        "tokens_kept_compressed": sum(e.tokens_kept_compressed for e in entries),
        "tokens_kept_pinned": sum(e.tokens_kept_pinned for e in entries),
        "last_outcome": entries[-1].outcome,
        "final_outcome_class": entries[-1].outcome_class,
    }
