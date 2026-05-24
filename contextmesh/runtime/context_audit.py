"""Policy-style checks for recorded context candidates."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from contextmesh.runtime.context_candidates import list_candidates
from contextmesh.storage.db import ContextCandidate

_SENSITIVE_TERMS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "private_key",
    "token",
)


@dataclass
class ContextAuditFinding:
    code: str
    severity: str
    ref: str
    message: str
    step: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ContextAudit:
    task_id: str
    findings: list[ContextAuditFinding]

    @property
    def passed(self) -> bool:
        return not any(f.severity in {"error", "warn"} for f in self.findings)

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def _looks_sensitive(candidate: ContextCandidate) -> bool:
    haystack = f"{candidate.ref} {candidate.reason}".lower()
    return any(term in haystack for term in _SENSITIVE_TERMS)


def _has_explicit_safe_rejection(candidate: ContextCandidate) -> bool:
    reason = candidate.reason.lower()
    return (
        candidate.source_type in {"stale_policy", "debug_dump"}
        or "stale" in reason
        or "sensitive" in reason
        or "superseded" in reason
    )


def audit_context_candidates(
    task_id: str,
    *,
    low_relevance_threshold: float = 0.3,
    high_relevance_threshold: float = 0.75,
    large_token_threshold: int = 4000,
) -> ContextAudit:
    """Find context selection risks in one task's candidates."""
    candidates = list_candidates(task_id)
    findings: list[ContextAuditFinding] = []
    selected = [c for c in candidates if c.status == "selected"]
    rejected = [c for c in candidates if c.status == "rejected"]

    selected_counts = Counter(c.ref for c in selected)
    for ref, count in sorted(selected_counts.items()):
        if count > 1:
            findings.append(ContextAuditFinding(
                code="duplicate_selected_ref",
                severity="warn",
                ref=ref,
                message=f"Selected {count} times; consider caching or collapsing repeated context.",
            ))

    for candidate in candidates:
        score = candidate.relevance_score
        if candidate.status == "selected" and score is not None and score < low_relevance_threshold:
            findings.append(ContextAuditFinding(
                code="low_relevance_selected",
                severity="warn",
                ref=candidate.ref,
                step=candidate.step,
                message=(
                    f"Selected despite relevance {score:.2f}; review retrieval or selection policy."
                ),
            ))
        if (
            candidate.status == "rejected"
            and score is not None
            and score >= high_relevance_threshold
            and not _has_explicit_safe_rejection(candidate)
        ):
            findings.append(ContextAuditFinding(
                code="high_relevance_rejected",
                severity="warn",
                ref=candidate.ref,
                step=candidate.step,
                message=(
                    f"Rejected despite relevance {score:.2f}; this may be missing evidence."
                ),
            ))
        if candidate.status == "selected" and candidate.tokens_estimated > large_token_threshold:
            findings.append(ContextAuditFinding(
                code="large_selected_context",
                severity="info",
                ref=candidate.ref,
                step=candidate.step,
                message=(
                    f"Selected {candidate.tokens_estimated:,} tokens; consider chunking or summarising."
                ),
            ))
        if candidate.status == "selected" and _looks_sensitive(candidate):
            findings.append(ContextAuditFinding(
                code="sensitive_selected_context",
                severity="error",
                ref=candidate.ref,
                step=candidate.step,
                message="Selected context looks sensitive; verify masking or policy approval.",
            ))

    if selected and not rejected:
        findings.append(ContextAuditFinding(
            code="no_rejected_candidates",
            severity="info",
            ref="",
            message="No rejected candidates recorded; selection rationale is incomplete.",
        ))

    return ContextAudit(task_id=task_id, findings=findings)
