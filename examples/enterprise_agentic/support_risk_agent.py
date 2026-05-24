"""Enterprise support-risk triage agent powered by ContextMesh.

The agent is deliberately local and deterministic. It simulates a production
agent that receives an enterprise escalation, chooses policy/runbook/customer
context, rejects stale or sensitive context, produces an action plan, and emits
ContextMesh observability payloads for platform and team workflows.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from contextmesh.runtime.context_audit import audit_context_candidates
from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
from contextmesh.runtime.inspector import inspect_task
from contextmesh.runtime.langfuse_export import build_langfuse_export
from contextmesh.runtime.ledger import estimate_tokens, record_step
from contextmesh.runtime.otel_export import build_otel_export
from contextmesh.runtime.team_export import build_team_export
from contextmesh.storage.db import create_db_and_tables

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCES = DATA / "context_sources"


@dataclass
class SourceDecision:
    ref: str
    status: str
    source_type: str
    relevance_score: float
    reason: str
    text: str


def _load_escalation(path: Path = DATA / "escalation.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_sources(source_dir: Path = SOURCES) -> dict[str, str]:
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(source_dir.glob("*.md"))
    }


def _score_source(name: str, text: str, escalation: dict) -> float:
    haystack = f"{name} {text}".lower()
    signals = [str(signal).lower() for signal in escalation.get("signals", [])]
    score = sum(1 for signal in signals if signal in haystack) / max(1, len(signals))
    if "enterprise" in haystack and escalation.get("tier") == "enterprise":
        score += 0.2
    if "p1" in haystack or "rollback" in haystack:
        score += 0.15
    if name == "security_policy" and escalation.get("tier") == "enterprise":
        score += 0.35
    return min(1.0, round(score, 2))


def choose_context(escalation: dict, sources: dict[str, str]) -> list[SourceDecision]:
    decisions: list[SourceDecision] = []
    for name, text in sources.items():
        ref = f"file:examples/enterprise_agentic/data/context_sources/{name}.md"
        score = _score_source(name, text, escalation)
        status = "selected"
        reason = "relevant to enterprise auth escalation"
        source_type = "policy"
        lowered = f"{name} {text}".lower()

        if "raw debug" in lowered or "password_reset_token" in lowered:
            status = "rejected"
            reason = "contains sensitive debug context not needed for customer-safe planning"
            source_type = "debug_dump"
            score = max(score, 0.8)
        elif "legacy" in lowered or "superseded" in lowered or "2024" in name:
            status = "rejected"
            reason = "stale policy superseded by current SLA and runbook"
            source_type = "stale_policy"
            score = max(score, 0.45)
        elif score < 0.25:
            status = "available"
            reason = "available but weak match for this escalation"

        decisions.append(SourceDecision(
            ref=ref,
            status=status,
            source_type=source_type,
            relevance_score=score,
            reason=reason,
            text=text,
        ))
    return decisions


def build_action_plan(escalation: dict, decisions: list[SourceDecision]) -> dict:
    selected_refs = [d.ref for d in decisions if d.status == "selected"]
    rejected_refs = [d.ref for d in decisions if d.status == "rejected"]
    selected_text = "\n\n".join(d.text for d in decisions if d.status == "selected")
    impact = escalation.get("impact", "").lower()
    is_p1 = escalation.get("tier") == "enterprise" and (
        "credential rotation" in impact
        or "rotate credentials" in impact
        or "privileged" in impact
    )
    rollback = "rollback" in selected_text.lower()
    return {
        "ticket_id": escalation["ticket_id"],
        "customer": escalation["customer"],
        "severity": "P1" if is_p1 else "P2",
        "decision": "disable eu-west auth rollout flag" if rollback else "continue diagnosis",
        "selected_context_refs": selected_refs,
        "rejected_context_refs": rejected_refs,
        "actions": [
            "assign incident commander and customer success owner",
            "acknowledge customer within 15 minutes",
            "disable eu-west auth rollout flag if synthetic privileged reset fails",
            "run privileged password-reset synthetic test",
            "send customer-safe update without raw tokens, hostnames, or operator ids",
            "open permanent-fix ticket for reset-token verifier regression",
        ],
        "customer_update": (
            "We are treating this as a priority incident affecting privileged "
            "password-reset flows in eu-west. We are validating a regional "
            "mitigation and will provide the next update within 30 minutes."
        ),
    }


def run_agent(task_id: str, out_dir: Path | None = None) -> dict:
    create_db_and_tables()
    escalation = _load_escalation()
    decisions = choose_context(escalation, _load_sources())
    selected = [d for d in decisions if d.status == "selected"]
    plan = build_action_plan(escalation, decisions)
    context_text = "\n\n".join(d.text for d in selected)

    for decision in decisions:
        record_candidate(CandidateInput(
            task_id=task_id,
            step=1,
            ref=decision.ref,
            status=decision.status,
            source_type=decision.source_type,
            reason=decision.reason,
            relevance_score=decision.relevance_score,
            tokens_estimated=estimate_tokens(decision.text),
        ))

    outcome_class = "passed" if plan["severity"] == "P1" and "disable" in plan["decision"] else "regressed"
    record_step(
        task_id=task_id,
        step=1,
        agent="enterprise-support-risk-agent",
        context_refs=[d.ref for d in selected],
        context_text=context_text,
        decision=plan["decision"],
        outcome="action plan generated",
        outcome_class=outcome_class,
        tokens_avoided=sum(estimate_tokens(d.text) for d in decisions if d.status == "rejected"),
    )

    artifacts = {
        "plan": plan,
        "decisions": [asdict(d) | {"text": f"{estimate_tokens(d.text)} tokens"} for d in decisions],
        "inspection": inspect_task(task_id).as_dict(),
        "audit": audit_context_candidates(task_id).as_dict(),
        "langfuse": build_langfuse_export(task_id, trace_id=f"enterprise-{task_id}").as_dict(),
        "otel": build_otel_export(task_id, service_name="enterprise-support-risk-agent").as_dict(),
        "slack": build_team_export(task_id, target="slack").as_dict(),
        "jira": build_team_export(task_id, target="jira").as_dict(),
    }

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in artifacts.items():
            (out_dir / f"{name}.json").write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", default="enterprise-acme-p1")
    parser.add_argument("--out", type=Path, default=ROOT / "out")
    args = parser.parse_args()

    if "CONTEXTMESH_STATE_DIR" not in os.environ:
        os.environ["CONTEXTMESH_STATE_DIR"] = str(args.out / ".contextmesh")
    artifacts = run_agent(args.task_id, out_dir=args.out)
    inspection = artifacts["inspection"]
    print(
        f"{args.task_id}: {inspection['final_outcome_class']} "
        f"quality={inspection['context_quality_score']:.2f} "
        f"selected={len(inspection['selected_context'])} "
        f"rejected={len(inspection['rejected_context'])}"
    )
    print(f"wrote artifacts to {args.out}")


if __name__ == "__main__":
    main()
