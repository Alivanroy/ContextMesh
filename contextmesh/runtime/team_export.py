"""Build team-tool payloads from ContextMesh inspections."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contextmesh.runtime.context_audit import audit_context_candidates
from contextmesh.runtime.inspector import inspect_task

TeamTarget = Literal["slack", "ms-teams", "linear", "jira", "github"]
VALID_TEAM_TARGETS: set[str] = {"slack", "ms-teams", "linear", "jira", "github"}


@dataclass
class TeamExport:
    task_id: str
    target: str
    payload: dict

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "target": self.target,
            "payload": self.payload,
        }


def _summary(task_id: str) -> dict:
    inspection = inspect_task(task_id)
    audit = audit_context_candidates(task_id)
    findings = [f.as_dict() for f in audit.findings]
    return {
        "task_id": task_id,
        "outcome": inspection.final_outcome_class,
        "context_quality_score": round(inspection.context_quality_score, 4),
        "useful_context_ratio": round(inspection.useful_context_ratio, 4),
        "tokens_billed": inspection.tokens_billed,
        "tokens_avoided": inspection.tokens_avoided,
        "selected_context_refs": [item.ref for item in inspection.selected_context[:10]],
        "rejected_context_refs": [item["ref"] for item in inspection.rejected_context[:10]],
        "audit_findings": findings,
        "recommendations": inspection.recommendations[:5],
    }


def _status(summary: dict) -> str:
    if any(f["severity"] == "error" for f in summary["audit_findings"]):
        return "needs_review"
    if summary["outcome"] == "passed" and summary["context_quality_score"] >= 0.7:
        return "healthy"
    if summary["outcome"] == "passed":
        return "passed_with_context_risk"
    return "failed_or_unknown"


def _headline(summary: dict) -> str:
    return (
        f"ContextMesh {summary['task_id']}: {summary['outcome']} "
        f"(quality {summary['context_quality_score']:.0%}, "
        f"useful {summary['useful_context_ratio']:.0%})"
    )


def _slack_payload(summary: dict) -> dict:
    return {
        "text": _headline(summary),
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{_headline(summary)}*"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* {_status(summary)}"},
                    {"type": "mrkdwn", "text": f"*Tokens billed:* {summary['tokens_billed']:,}"},
                    {"type": "mrkdwn", "text": f"*Tokens avoided:* {summary['tokens_avoided']:,}"},
                    {"type": "mrkdwn", "text": f"*Findings:* {len(summary['audit_findings'])}"},
                ],
            },
        ],
        "metadata": {"event_type": "contextmesh_run", "event_payload": summary},
    }


def _teams_payload(summary: dict) -> dict:
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "weight": "Bolder", "text": _headline(summary)},
                    {"type": "FactSet", "facts": [
                        {"title": "Status", "value": _status(summary)},
                        {"title": "Tokens billed", "value": f"{summary['tokens_billed']:,}"},
                        {"title": "Tokens avoided", "value": f"{summary['tokens_avoided']:,}"},
                        {"title": "Audit findings", "value": str(len(summary["audit_findings"]))},
                    ]},
                ],
            },
        }],
        "contextmesh": summary,
    }


def _issue_payload(summary: dict, *, target: str) -> dict:
    body_lines = [
        _headline(summary),
        "",
        f"Status: {_status(summary)}",
        f"Tokens billed: {summary['tokens_billed']:,}",
        f"Tokens avoided: {summary['tokens_avoided']:,}",
        "",
        "Recommendations:",
        *[f"- {rec}" for rec in summary["recommendations"]],
        "",
        "Selected context:",
        *[f"- {ref}" for ref in summary["selected_context_refs"]],
        "",
        "Rejected context:",
        *[f"- {ref}" for ref in summary["rejected_context_refs"]],
    ]
    labels = ["contextmesh", f"outcome:{summary['outcome']}", f"status:{_status(summary)}"]
    if target == "linear":
        return {
            "title": _headline(summary),
            "description": "\n".join(body_lines),
            "labelIds": labels,
            "metadata": summary,
        }
    if target == "jira":
        return {
            "fields": {
                "summary": _headline(summary),
                "description": "\n".join(body_lines),
                "labels": labels,
            },
            "contextmesh": summary,
        }
    return {
        "title": _headline(summary),
        "body": "\n".join(body_lines),
        "labels": labels,
        "contextmesh": summary,
    }


def build_team_export(task_id: str, *, target: str) -> TeamExport:
    """Return a no-network payload for a team integration target."""
    if target not in VALID_TEAM_TARGETS:
        valid = ", ".join(sorted(VALID_TEAM_TARGETS))
        raise ValueError(f"target must be one of: {valid}")
    summary = _summary(task_id)
    if target == "slack":
        payload = _slack_payload(summary)
    elif target == "ms-teams":
        payload = _teams_payload(summary)
    else:
        payload = _issue_payload(summary, target=target)
    return TeamExport(task_id=task_id, target=target, payload=payload)
