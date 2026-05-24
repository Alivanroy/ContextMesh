"""Context intelligence views over recorded agent runs."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass

from sqlmodel import select

from contextmesh import __version__
from contextmesh.runtime.context_audit import audit_context_candidates
from contextmesh.runtime.context_candidates import list_candidates
from contextmesh.runtime.metrics import task_metrics
from contextmesh.storage.db import ContextCandidate, LedgerEntry, create_db_and_tables, get_session

_OUTCOME_SCORE = {
    "passed": 1.0,
    "unchanged": 0.55,
    "unknown": 0.45,
    "regressed": 0.1,
    "aborted": 0.05,
}


@dataclass
class ContextItemInsight:
    ref: str
    times_selected: int
    first_step: int
    last_step: int

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ContextRunInspection:
    task_id: str
    steps: int
    agents: list[str]
    final_outcome_class: str
    tokens_billed: int
    tokens_avoided: int
    useful_context_ratio: float
    context_quality_score: float
    score_breakdown: dict[str, float]
    selected_context: list[ContextItemInsight]
    rejected_context: list[dict]
    duplicate_ref_sends: int
    recommendations: list[str]

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "steps": self.steps,
            "agents": self.agents,
            "final_outcome_class": self.final_outcome_class,
            "tokens_billed": self.tokens_billed,
            "tokens_avoided": self.tokens_avoided,
            "useful_context_ratio": round(self.useful_context_ratio, 4),
            "context_quality_score": round(self.context_quality_score, 4),
            "score_breakdown": {
                k: round(v, 4) for k, v in self.score_breakdown.items()
            },
            "selected_context": [item.as_dict() for item in self.selected_context],
            "rejected_context": self.rejected_context,
            "duplicate_ref_sends": self.duplicate_ref_sends,
            "recommendations": self.recommendations,
            "langfuse_metadata": self.langfuse_metadata(),
        }

    def langfuse_metadata(self) -> dict:
        """Return a compact payload suitable for Langfuse trace metadata."""
        return {
            "contextmesh": {
                "version": __version__,
                "task_id": self.task_id,
                "context_quality_score": round(self.context_quality_score, 4),
                "useful_context_ratio": round(self.useful_context_ratio, 4),
                "tokens_billed": self.tokens_billed,
                "tokens_avoided": self.tokens_avoided,
                "duplicate_ref_sends": self.duplicate_ref_sends,
                "selected_context_refs": [
                    item.ref for item in self.selected_context
                ],
                "rejected_context_refs": [
                    item["ref"] for item in self.rejected_context
                ],
                "recommendations": self.recommendations,
            }
        }


@dataclass
class ContextRunDiff:
    left_task_id: str
    right_task_id: str
    left_outcome_class: str
    right_outcome_class: str
    left_context_quality_score: float
    right_context_quality_score: float
    quality_delta: float
    refs_only_left: list[str]
    refs_only_right: list[str]
    refs_shared: list[str]
    duplicate_ref_delta: int
    tokens_billed_delta: int
    tokens_avoided_delta: int
    recommendations: list[str]

    def as_dict(self) -> dict:
        return {
            "left_task_id": self.left_task_id,
            "right_task_id": self.right_task_id,
            "left_outcome_class": self.left_outcome_class,
            "right_outcome_class": self.right_outcome_class,
            "left_context_quality_score": round(self.left_context_quality_score, 4),
            "right_context_quality_score": round(self.right_context_quality_score, 4),
            "quality_delta": round(self.quality_delta, 4),
            "refs_only_left": self.refs_only_left,
            "refs_only_right": self.refs_only_right,
            "refs_shared": self.refs_shared,
            "duplicate_ref_delta": self.duplicate_ref_delta,
            "tokens_billed_delta": self.tokens_billed_delta,
            "tokens_avoided_delta": self.tokens_avoided_delta,
            "recommendations": self.recommendations,
        }


def _task_entries(task_id: str) -> list[LedgerEntry]:
    create_db_and_tables()
    with get_session() as session:
        rows = list(session.exec(
            select(LedgerEntry).where(LedgerEntry.task_id == task_id)
        ).all())
    rows.sort(key=lambda e: (e.step, e.id or 0))
    return rows


def _parse_refs(raw: str) -> list[str]:
    try:
        refs = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(refs, list):
        return []
    return [str(ref) for ref in refs if str(ref).strip()]


def _selected_context(entries: list[LedgerEntry]) -> tuple[list[ContextItemInsight], int]:
    counts: Counter[str] = Counter()
    first_step: dict[str, int] = {}
    last_step: dict[str, int] = {}
    for entry in entries:
        for ref in _parse_refs(entry.context_used):
            counts[ref] += 1
            first_step.setdefault(ref, entry.step)
            last_step[ref] = entry.step

    items = [
        ContextItemInsight(
            ref=ref,
            times_selected=count,
            first_step=first_step[ref],
            last_step=last_step[ref],
        )
        for ref, count in counts.most_common()
    ]
    duplicate_sends = sum(max(0, count - 1) for count in counts.values())
    return items, duplicate_sends


def _selected_from_candidates(
    candidates: list[ContextCandidate],
) -> tuple[list[ContextItemInsight], int]:
    counts: Counter[str] = Counter()
    first_step: dict[str, int] = {}
    last_step: dict[str, int] = {}
    for candidate in candidates:
        if candidate.status != "selected":
            continue
        counts[candidate.ref] += 1
        first_step.setdefault(candidate.ref, candidate.step)
        last_step[candidate.ref] = candidate.step

    items = [
        ContextItemInsight(
            ref=ref,
            times_selected=count,
            first_step=first_step[ref],
            last_step=last_step[ref],
        )
        for ref, count in counts.most_common()
    ]
    duplicate_sends = sum(max(0, count - 1) for count in counts.values())
    return items, duplicate_sends


def _rejected_from_candidates(candidates: list[ContextCandidate]) -> list[dict]:
    rejected = [
        {
            "ref": candidate.ref,
            "step": candidate.step,
            "source_type": candidate.source_type,
            "reason": candidate.reason,
            "relevance_score": candidate.relevance_score,
            "tokens_estimated": candidate.tokens_estimated,
        }
        for candidate in candidates
        if candidate.status == "rejected"
    ]
    rejected.sort(key=lambda item: (item["step"], item["ref"]))
    return rejected


def _recommendations(
    *,
    metrics,
    unique_refs: int,
    duplicate_ref_sends: int,
    evidence_score: float,
    reuse_score: float,
    rejected_count: int = 0,
    audit_messages: list[str] | None = None,
) -> list[str]:
    out: list[str] = []
    out.extend(audit_messages or [])
    if metrics.final_outcome_class != "passed":
        out.append(
            "Compare this run with a passed run to find missing or stale context."
        )
    if unique_refs == 0:
        out.append(
            "Record context refs for this task so ContextMesh can explain what the agent saw."
        )
    elif evidence_score < 0.5:
        out.append(
            "Attach more specific file, symbol, packet, or tool-output refs to each step."
        )
    if duplicate_ref_sends > 0 and reuse_score < 0.8:
        out.append(
            "Reduce duplicate context sends by tightening task ids or promoting repeated refs to cache."
        )
    if rejected_count == 0:
        out.append(
            "Record rejected context candidates to explain what the agent deliberately ignored."
        )
    if metrics.tokens_avoided == 0 and metrics.tokens_billed > 0:
        out.append(
            "Run with delta compression or critical-path focus to measure avoided context."
        )
    if metrics.tokens_billed > 8000 and metrics.useful_context_ratio < 1.0:
        out.append(
            "Inspect the largest context packets first; high spend did not produce a passed task."
        )
    if not out:
        out.append(
            "Context selection looks healthy; use the Langfuse metadata payload for trace comparison."
        )
    return out


def inspect_task(task_id: str) -> ContextRunInspection:
    """Summarise selected context, quality, and remediation for one task."""
    entries = _task_entries(task_id)
    candidates = list_candidates(task_id)
    audit = audit_context_candidates(task_id)
    metrics = task_metrics(task_id)
    if candidates:
        selected, duplicate_ref_sends = _selected_from_candidates(candidates)
        if not selected:
            selected, duplicate_ref_sends = _selected_context(entries)
    else:
        selected, duplicate_ref_sends = _selected_context(entries)
    rejected = _rejected_from_candidates(candidates)
    total_ref_sends = sum(item.times_selected for item in selected)
    unique_refs = len(selected)

    outcome_score = _OUTCOME_SCORE.get(metrics.final_outcome_class, 0.45)
    avoidance_score = (
        metrics.tokens_avoided / metrics.raw_baseline_estimate
        if metrics.raw_baseline_estimate > 0 else 0.0
    )
    evidence_score = min(1.0, unique_refs / metrics.steps) if metrics.steps > 0 else 0.0
    reuse_score = (
        1.0 - (duplicate_ref_sends / total_ref_sends)
        if total_ref_sends > 0 else 0.0
    )
    score = (
        outcome_score * 0.40
        + avoidance_score * 0.25
        + evidence_score * 0.20
        + reuse_score * 0.15
    )

    return ContextRunInspection(
        task_id=task_id,
        steps=metrics.steps,
        agents=sorted({entry.agent for entry in entries}),
        final_outcome_class=metrics.final_outcome_class,
        tokens_billed=metrics.tokens_billed,
        tokens_avoided=metrics.tokens_avoided,
        useful_context_ratio=metrics.useful_context_ratio,
        context_quality_score=score,
        score_breakdown={
            "outcome": outcome_score,
            "avoidance": avoidance_score,
            "evidence": evidence_score,
            "reuse": reuse_score,
        },
        selected_context=selected,
        rejected_context=rejected,
        duplicate_ref_sends=duplicate_ref_sends,
        recommendations=_recommendations(
            metrics=metrics,
            unique_refs=unique_refs,
            duplicate_ref_sends=duplicate_ref_sends,
            evidence_score=evidence_score,
            reuse_score=reuse_score,
            rejected_count=len(rejected),
            audit_messages=[
                f"{finding.code}: {finding.message}"
                for finding in audit.findings
                if finding.severity in {"error", "warn"}
            ],
        ),
    )


def _refs(inspection: ContextRunInspection) -> set[str]:
    return {item.ref for item in inspection.selected_context}


def _diff_recommendations(
    *,
    left: ContextRunInspection,
    right: ContextRunInspection,
    refs_only_left: list[str],
    refs_only_right: list[str],
    refs_shared: list[str],
) -> list[str]:
    out: list[str] = []
    if right.final_outcome_class == "passed" and left.final_outcome_class != "passed":
        if refs_only_right:
            out.append(
                "Promote refs that appear only in the passed run; they are likely missing evidence."
            )
        if refs_only_left:
            out.append(
                "Review refs that appear only in the failed run; they may be stale, noisy, or misleading."
            )
    if not refs_shared and refs_only_left and refs_only_right:
        out.append(
            "The runs share no context refs, so compare retrieval, packet export, or task-id setup first."
        )
    if right.duplicate_ref_sends < left.duplicate_ref_sends:
        out.append(
            "The right run repeated less context; copy its task-id/cache discipline."
        )
    if right.tokens_avoided > left.tokens_avoided:
        out.append(
            "The right run avoided more context; inspect its compression and focus path."
        )
    if not out:
        out.append(
            "Context sets are similar; inspect decisions and model/tool output for the remaining delta."
        )
    return out


def diff_tasks(left_task_id: str, right_task_id: str) -> ContextRunDiff:
    """Compare selected context and quality between two recorded tasks."""
    left = inspect_task(left_task_id)
    right = inspect_task(right_task_id)
    left_refs = _refs(left)
    right_refs = _refs(right)
    refs_only_left = sorted(left_refs - right_refs)
    refs_only_right = sorted(right_refs - left_refs)
    refs_shared = sorted(left_refs & right_refs)

    return ContextRunDiff(
        left_task_id=left.task_id,
        right_task_id=right.task_id,
        left_outcome_class=left.final_outcome_class,
        right_outcome_class=right.final_outcome_class,
        left_context_quality_score=left.context_quality_score,
        right_context_quality_score=right.context_quality_score,
        quality_delta=right.context_quality_score - left.context_quality_score,
        refs_only_left=refs_only_left,
        refs_only_right=refs_only_right,
        refs_shared=refs_shared,
        duplicate_ref_delta=right.duplicate_ref_sends - left.duplicate_ref_sends,
        tokens_billed_delta=right.tokens_billed - left.tokens_billed,
        tokens_avoided_delta=right.tokens_avoided - left.tokens_avoided,
        recommendations=_diff_recommendations(
            left=left,
            right=right,
            refs_only_left=refs_only_left,
            refs_only_right=refs_only_right,
            refs_shared=refs_shared,
        ),
    )
