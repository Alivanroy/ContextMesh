import json
from pathlib import Path

from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_schema import get_context_schema


def _json_cli(runner: CliRunner, args: list[str]) -> dict | list:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_context_intelligence_v1_cli_workflow():
    runner = CliRunner()
    fixture = Path(__file__).parent / "fixtures" / "codex_cli_session.jsonl"

    traced = runner.invoke(app, [
        "trace",
        "--task-id", "v1-passed",
        "--agent", "codex-cli",
        "--silent",
        "--from-file", str(fixture),
        "--",
        "noop",
    ])
    assert traced.exit_code == 0

    failed = runner.invoke(app, [
        "ledger", "record",
        "--task-id", "v1-failed",
        "--step", "1",
        "--agent", "codex-cli",
        "--decision", "patched legacy helper",
        "--outcome", "tests failed",
        "--outcome-class", "regressed",
        "--ref", "symbol:legacy_reset",
        "--context-text", "legacy reset helper",
    ])
    assert failed.exit_code == 0

    rejected = runner.invoke(app, [
        "context", "record",
        "--task-id", "v1-passed",
        "--step", "1",
        "--ref", "file:docs/old-reset.md",
        "--status", "rejected",
        "--source-type", "doc",
        "--reason", "stale reset flow",
        "--relevance-score", "0.1",
        "--tokens-estimated", "200",
    ])
    assert rejected.exit_code == 0

    candidates = _json_cli(runner, ["context", "show", "--task-id", "v1-passed", "--json"])
    assert any(row["status"] == "selected" for row in candidates)
    assert any(row["status"] == "rejected" for row in candidates)

    inspection = _json_cli(runner, ["inspect", "--task-id", "v1-passed", "--json"])
    diff = _json_cli(runner, ["diff", "--left", "v1-failed", "--right", "v1-passed", "--json"])
    audit = _json_cli(runner, ["context", "audit", "--task-id", "v1-passed", "--json"])
    langfuse = _json_cli(runner, [
        "export-langfuse",
        "--task-id", "v1-passed",
        "--trace-id", "trace-v1",
    ])

    Draft202012Validator(get_context_schema("inspection")).validate(inspection)
    Draft202012Validator(get_context_schema("diff")).validate(diff)
    Draft202012Validator(get_context_schema("audit")).validate(audit)
    Draft202012Validator(get_context_schema("langfuse-export")).validate(langfuse)

    assert inspection["final_outcome_class"] == "passed"
    assert diff["right_task_id"] == "v1-passed"
    assert langfuse["trace_id"] == "trace-v1"
    assert "contextmesh" in langfuse["tags"]

    schema = _json_cli(runner, ["context", "schema", "inspection"])
    assert schema["$id"].endswith("/context-run-inspection.json")
