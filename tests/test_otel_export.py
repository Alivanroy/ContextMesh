from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_candidates import CandidateInput, record_candidate
from contextmesh.runtime.ledger import record_step
from contextmesh.runtime.otel_export import build_otel_export


def _seed_otel_task(task_id: str = "otel-task") -> None:
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


def test_build_otel_export_emits_context_inspection_span_and_events():
    _seed_otel_task()

    export = build_otel_export(
        "otel-task",
        trace_id="1234567890abcdef1234567890abcdef",
        service_name="agent-platform",
    ).as_dict()

    assert export["trace_id"] == "1234567890abcdef1234567890abcdef"
    resource = export["resourceSpans"][0]["resource"]
    attrs = {item["key"]: item["value"] for item in resource["attributes"]}
    assert attrs["service.name"]["stringValue"] == "agent-platform"

    span = export["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "contextmesh.context_inspection"
    span_attrs = {item["key"]: item["value"] for item in span["attributes"]}
    assert span_attrs["gen_ai.operation.name"]["stringValue"] == "agent"
    assert span_attrs["contextmesh.context_quality_score"]["doubleValue"] > 0.7
    assert span_attrs["contextmesh.selected_context_count"]["intValue"] == 1
    assert span_attrs["contextmesh.rejected_context_count"]["intValue"] == 1

    event_names = [event["name"] for event in span["events"]]
    assert "contextmesh.context.selected" in event_names
    assert "contextmesh.context.rejected" in event_names


def test_export_otel_cli_outputs_json():
    _seed_otel_task("otel-cli")

    result = CliRunner().invoke(app, [
        "export-otel",
        "--task-id", "otel-cli",
        "--trace-id", "abcdefabcdefabcdefabcdefabcdefab",
        "--service-name", "context-platform",
    ])

    assert result.exit_code == 0
    assert '"trace_id": "abcdefabcdefabcdefabcdefabcdefab"' in result.output
    assert '"resourceSpans"' in result.output
    assert '"contextmesh.context_inspection"' in result.output
