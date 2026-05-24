from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
from contextmesh.runtime.langfuse_export import build_langfuse_export
from contextmesh.runtime.ledger import record_step


def _seed_export_task(task_id: str = "langfuse-task") -> None:
    record_step(
        task_id=task_id,
        step=1,
        agent="codex-cli",
        context_refs=[],
        context_text="selected context",
        decision="patch",
        outcome="passed",
        outcome_class="passed",
        tokens_avoided=25,
    )
    record_candidate(CandidateInput(
        task_id=task_id,
        step=1,
        ref="symbol:verify_reset_token",
        status="selected",
        source_type="symbol",
        reason="directly covers test",
    ))
    record_candidate(CandidateInput(
        task_id=task_id,
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale flow",
    ))


def test_build_langfuse_export_includes_trace_metadata_and_tags():
    _seed_export_task()

    export = build_langfuse_export(
        "langfuse-task",
        trace_id="trace-123",
        tags=["release:v1"],
    ).as_dict()

    assert export["trace_id"] == "trace-123"
    assert "release:v1" in export["tags"]
    assert "contextmesh" in export["tags"]
    metadata = export["metadata"]["contextmesh"]
    assert metadata["task_id"] == "langfuse-task"
    assert metadata["selected_context_refs"] == ["symbol:verify_reset_token"]
    assert metadata["rejected_context_refs"] == ["file:docs/old-reset.md"]


def test_export_langfuse_cli_outputs_json():
    _seed_export_task("langfuse-cli")
    runner = CliRunner()

    result = runner.invoke(app, [
        "export-langfuse",
        "--task-id", "langfuse-cli",
        "--trace-id", "trace-cli",
        "--tag", "env:test",
    ])

    assert result.exit_code == 0
    assert '"trace_id": "trace-cli"' in result.output
    assert '"env:test"' in result.output
    assert '"selected_context_refs"' in result.output
