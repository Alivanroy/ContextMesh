"""Append-only ledger of context usage per task step."""
from __future__ import annotations

import json
import re

from sqlmodel import select

from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
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


_TOOL_REF = re.compile(r"^(?P<tool>[A-Za-z_][\w-]*)\((?P<target>.*)\)$")
_FILE_TOOLS = {"read", "edit", "write", "notebookread", "notebookedit"}


def _source_type_from_ref(ref: str) -> str:
    prefix = ref.split(":", 1)[0].split("(", 1)[0].split(".", 1)[0].strip().lower()
    if prefix in {
        "file",
        "symbol",
        "command",
        "tool_result",
        "tool_output",
        "tool_use",
        "generated_packet",
        "prompt_block",
        "thread",
        "result",
        "turn",
        "user_input",
    }:
        return prefix
    if prefix in {"read", "edit", "write", "bash", "grep", "glob", "ls"}:
        return "tool"
    return "unknown"


def _expanded_candidate_refs(refs: list[str]) -> list[tuple[str, str]]:
    expanded: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(ref: str, reason: str) -> None:
        if not ref or ref in seen:
            return
        seen.add(ref)
        expanded.append((ref, reason))

    for ref in refs:
        add(ref, "selected by adapter context_refs")
        match = _TOOL_REF.match(ref.strip())
        if not match:
            continue
        tool = match.group("tool").lower()
        target = match.group("target").strip().strip("'\"")
        if not target:
            continue
        if tool in _FILE_TOOLS and ":" not in target:
            add(f"file:{target}", f"derived from {match.group('tool')} tool target")
        elif tool == "bash":
            add(f"command:{target[:120]}", "derived from Bash tool target")
    return expanded


def _record_selected_candidates_from_refs(
    *,
    task_id: str,
    step: int,
    refs: list[str],
) -> None:
    for ref, reason in _expanded_candidate_refs(refs):
        record_candidate(CandidateInput(
            task_id=task_id,
            step=step,
            ref=ref,
            status="selected",
            source_type=_source_type_from_ref(ref),
            reason=reason,
        ))


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

    Billing-volume rule for ``tokens_estimated`` (the input to
    ``useful_context_ratio``):

      1. If the event sets ``tokens_estimated`` explicitly, honour it.
      2. Otherwise, if any provider token field is non-zero, use the sum
         ``input + cache_read + cache_write`` — the **real** input volume
         the provider processed, not a local cl100k_base guess. This is
         what makes the metric meaningful for traced sessions.
      3. Otherwise fall back to estimating ``context_text``.
    """
    create_db_and_tables()
    refs = event.get("context_refs", []) or []
    if isinstance(refs, str):
        refs = [refs]
    context_text = event.get("context_text", "") or ""
    provider_in = int(event.get("tokens_provider_input", 0))
    cached_read = int(event.get("tokens_cached_read", 0))
    cached_write = int(event.get("tokens_cached_write", 0))
    provider_total = provider_in + cached_read + cached_write

    estimated = event.get("tokens_estimated")
    if estimated is None:
        if provider_total > 0:
            estimated = provider_total
        elif context_text:
            estimated = estimate_tokens(context_text)
        else:
            estimated = 0
    entry = LedgerEntry(
        task_id=event["task_id"],
        step=event["step"],
        agent=event.get("agent", "unknown"),
        context_used=json.dumps(refs),
        tokens_estimated=int(estimated),
        tokens_avoided=int(event.get("tokens_avoided", 0)),
        tokens_kept_compressed=int(event.get("tokens_kept_compressed", 0)),
        tokens_kept_pinned=int(event.get("tokens_kept_pinned", 0)),
        tokens_provider_input=provider_in,
        tokens_cached_read=cached_read,
        tokens_cached_write=cached_write,
        tokens_provider_output=int(event.get("tokens_provider_output", 0)),
        decision=str(event.get("decision", "")),
        outcome=str(event.get("outcome", "ok")),
        outcome_class=_normalise_outcome_class(event.get("outcome_class")),
    )
    with get_session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        _record_selected_candidates_from_refs(
            task_id=entry.task_id,
            step=entry.step,
            refs=refs,
        )
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
