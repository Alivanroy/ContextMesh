from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_audit import audit_context_candidates
from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
from contextmesh.runtime.inspector import inspect_task
from contextmesh.runtime.ledger import record_step


def test_context_audit_flags_selection_risks():
    record_candidate(CandidateInput(
        task_id="audit-task",
        step=1,
        ref="symbol:irrelevant_helper",
        status="selected",
        relevance_score=0.1,
    ))
    record_candidate(CandidateInput(
        task_id="audit-task",
        step=2,
        ref="symbol:irrelevant_helper",
        status="selected",
        relevance_score=0.2,
    ))
    record_candidate(CandidateInput(
        task_id="audit-task",
        step=2,
        ref="file:docs/current-reset.md",
        status="rejected",
        relevance_score=0.9,
    ))
    record_candidate(CandidateInput(
        task_id="audit-task",
        step=3,
        ref="secret:api_key",
        status="selected",
        relevance_score=0.8,
        tokens_estimated=5000,
    ))

    audit = audit_context_candidates("audit-task")
    codes = [finding.code for finding in audit.findings]

    assert audit.passed is False
    assert "duplicate_selected_ref" in codes
    assert "low_relevance_selected" in codes
    assert "high_relevance_rejected" in codes
    assert "large_selected_context" in codes
    assert "sensitive_selected_context" in codes


def test_context_audit_accepts_explicit_stale_or_sensitive_rejections():
    record_candidate(CandidateInput(
        task_id="audit-safe-reject",
        step=1,
        ref="file:legacy-policy.md",
        status="rejected",
        source_type="stale_policy",
        reason="stale policy superseded by current SLA",
        relevance_score=0.95,
    ))
    record_candidate(CandidateInput(
        task_id="audit-safe-reject",
        step=1,
        ref="file:raw-debug.md",
        status="rejected",
        source_type="debug_dump",
        reason="sensitive debug context",
        relevance_score=0.9,
    ))

    audit = audit_context_candidates("audit-safe-reject")

    assert audit.findings == []


def test_inspect_recommendations_include_audit_warnings():
    record_step(
        task_id="audit-inspect",
        step=1,
        agent="codex-cli",
        context_refs=[],
        context_text="manual",
        decision="patch",
        outcome="ok",
        outcome_class="unknown",
    )
    record_candidate(CandidateInput(
        task_id="audit-inspect",
        step=1,
        ref="symbol:bad_match",
        status="selected",
        relevance_score=0.1,
    ))

    inspection = inspect_task("audit-inspect")

    assert any("low_relevance_selected" in rec for rec in inspection.recommendations)


def test_context_audit_cli_json():
    record_candidate(CandidateInput(
        task_id="audit-cli",
        step=1,
        ref="password:raw",
        status="selected",
    ))

    result = CliRunner().invoke(app, [
        "context", "audit",
        "--task-id", "audit-cli",
        "--json",
    ])

    assert result.exit_code == 0
    assert '"passed": false' in result.output
    assert '"sensitive_selected_context"' in result.output
