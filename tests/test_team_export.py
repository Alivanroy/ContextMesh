from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
from contextmesh.runtime.ledger import record_step
from contextmesh.runtime.team_export import build_team_export


def _seed_team_task(task_id: str = "team-task") -> None:
    record_step(
        task_id=task_id,
        step=1,
        agent="codex-cli",
        context_refs=["symbol:verify_reset_token"],
        context_text="verify reset token",
        decision="patched verifier",
        outcome="tests passed",
        outcome_class="passed",
        tokens_avoided=30,
    )
    record_candidate(CandidateInput(
        task_id=task_id,
        step=1,
        ref="symbol:verify_reset_token",
        status="selected",
        source_type="symbol",
        reason="directly covers failing test",
        relevance_score=0.95,
    ))
    record_candidate(CandidateInput(
        task_id=task_id,
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale reset flow",
        relevance_score=0.1,
    ))


def test_build_team_export_slack_payload():
    _seed_team_task()

    export = build_team_export("team-task", target="slack").as_dict()

    assert export["target"] == "slack"
    assert export["payload"]["metadata"]["event_type"] == "contextmesh_run"
    assert "ContextMesh team-task" in export["payload"]["text"]


def test_build_team_export_issue_payloads():
    _seed_team_task("team-issue")

    github = build_team_export("team-issue", target="github").as_dict()
    linear = build_team_export("team-issue", target="linear").as_dict()
    jira = build_team_export("team-issue", target="jira").as_dict()

    assert "contextmesh" in github["payload"]["labels"]
    assert "metadata" in linear["payload"]
    assert "fields" in jira["payload"]
    assert "Selected context" in github["payload"]["body"]


def test_export_team_cli_outputs_ms_teams_json():
    _seed_team_task("team-cli")

    result = CliRunner().invoke(app, [
        "export-team",
        "--task-id", "team-cli",
        "--target", "ms-teams",
    ])

    assert result.exit_code == 0
    assert '"target": "ms-teams"' in result.output
    assert '"AdaptiveCard"' in result.output
