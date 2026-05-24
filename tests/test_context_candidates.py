from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_candidates import (
    CandidateInput,
    list_candidates,
    record_candidate,
)
from contextmesh.runtime.inspector import inspect_task
from contextmesh.runtime.ledger import record_step


def test_record_and_list_context_candidates():
    selected = record_candidate(CandidateInput(
        task_id="candidate-task",
        step=1,
        ref="symbol:verify_reset_token",
        status="selected",
        source_type="symbol",
        reason="covers failing assertion",
        relevance_score=0.92,
        tokens_estimated=120,
    ))
    rejected = record_candidate(CandidateInput(
        task_id="candidate-task",
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale reset flow",
        relevance_score=0.2,
        tokens_estimated=300,
    ))

    assert selected.status == "selected"
    assert rejected.status == "rejected"
    assert [c.ref for c in list_candidates("candidate-task")] == [
        "symbol:verify_reset_token",
        "file:docs/old-reset.md",
    ]
    assert [c.ref for c in list_candidates("candidate-task", status="rejected")] == [
        "file:docs/old-reset.md",
    ]


def test_inspector_prefers_explicit_candidates_over_ledger_refs():
    record_step(
        task_id="candidate-inspect",
        step=1,
        agent="codex-cli",
        context_refs=["symbol:legacy_ledger_ref"],
        context_text="legacy ref",
        decision="patch",
        outcome="passed",
        outcome_class="passed",
    )
    record_candidate(CandidateInput(
        task_id="candidate-inspect",
        step=1,
        ref="symbol:verify_reset_token",
        status="selected",
        source_type="symbol",
        reason="direct match",
    ))
    record_candidate(CandidateInput(
        task_id="candidate-inspect",
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale doc",
    ))

    inspection = inspect_task("candidate-inspect")

    assert [item.ref for item in inspection.selected_context] == [
        "symbol:verify_reset_token",
    ]
    assert inspection.rejected_context[0]["ref"] == "file:docs/old-reset.md"
    metadata = inspection.langfuse_metadata()["contextmesh"]
    assert metadata["selected_context_refs"] == ["symbol:verify_reset_token"]
    assert metadata["rejected_context_refs"] == ["file:docs/old-reset.md"]


def test_inspector_falls_back_to_ledger_refs_when_only_rejected_candidates_exist():
    record_step(
        task_id="candidate-rejected-only",
        step=1,
        agent="codex-cli",
        context_refs=["symbol:ledger_selected"],
        context_text="ledger ref",
        decision="patch",
        outcome="ok",
        outcome_class="unknown",
    )
    record_candidate(CandidateInput(
        task_id="candidate-rejected-only",
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale doc",
    ))

    inspection = inspect_task("candidate-rejected-only")

    assert [item.ref for item in inspection.selected_context] == [
        "symbol:ledger_selected",
    ]
    assert inspection.rejected_context[0]["ref"] == "file:docs/old-reset.md"


def test_context_cli_record_and_show_json():
    runner = CliRunner()

    result = runner.invoke(app, [
        "context", "record",
        "--task-id", "cli-candidate",
        "--step", "1",
        "--ref", "symbol:verify_reset_token",
        "--status", "selected",
        "--source-type", "symbol",
        "--reason", "direct match",
        "--relevance-score", "0.95",
        "--tokens-estimated", "42",
    ])
    assert result.exit_code == 0

    shown = runner.invoke(app, [
        "context", "show",
        "--task-id", "cli-candidate",
        "--json",
    ])

    assert shown.exit_code == 0
    assert '"ref": "symbol:verify_reset_token"' in shown.output
    assert '"status": "selected"' in shown.output
