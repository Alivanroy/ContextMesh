"""Record and query context candidates for a task."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlmodel import select

from contextmesh.storage.db import ContextCandidate, create_db_and_tables, get_session

VALID_CANDIDATE_STATUSES = {"available", "selected", "rejected"}


@dataclass
class CandidateInput:
    task_id: str
    step: int
    ref: str
    status: str
    source_type: str = "unknown"
    reason: str = ""
    relevance_score: float | None = None
    tokens_estimated: int = 0


def _normalise_status(status: str) -> str:
    value = status.strip().lower()
    if value not in VALID_CANDIDATE_STATUSES:
        valid = ", ".join(sorted(VALID_CANDIDATE_STATUSES))
        raise ValueError(f"candidate status must be one of: {valid}")
    return value


def record_candidate(candidate: CandidateInput) -> ContextCandidate:
    """Append one context candidate decision."""
    create_db_and_tables()
    row = ContextCandidate(
        task_id=candidate.task_id,
        step=candidate.step,
        ref=candidate.ref,
        status=_normalise_status(candidate.status),
        source_type=candidate.source_type or "unknown",
        reason=candidate.reason,
        relevance_score=candidate.relevance_score,
        tokens_estimated=max(0, int(candidate.tokens_estimated)),
    )
    with get_session() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def list_candidates(
    task_id: str,
    *,
    status: str | None = None,
) -> list[ContextCandidate]:
    """Return candidates for a task, ordered by step and insertion id."""
    create_db_and_tables()
    with get_session() as session:
        stmt = select(ContextCandidate).where(ContextCandidate.task_id == task_id)
        if status:
            stmt = stmt.where(ContextCandidate.status == _normalise_status(status))
        rows = list(session.exec(stmt).all())
    rows.sort(key=lambda c: (c.step, c.id or 0))
    return rows


def candidate_as_dict(candidate: ContextCandidate) -> dict:
    """Serialize a SQLModel candidate without leaking ORM internals."""
    return asdict(CandidateInput(
        task_id=candidate.task_id,
        step=candidate.step,
        ref=candidate.ref,
        status=candidate.status,
        source_type=candidate.source_type,
        reason=candidate.reason,
        relevance_score=candidate.relevance_score,
        tokens_estimated=candidate.tokens_estimated,
    ))
