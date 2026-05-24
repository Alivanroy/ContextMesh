import json

import pytest
from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_audit import audit_context_candidates
from contextmesh.runtime.context_candidates import (
    CandidateInput,
    candidate_as_dict,
    list_candidates,
    record_candidate,
)
from contextmesh.runtime.context_schema import (
    SCHEMA_VERSION,
    all_context_schemas,
    get_context_schema,
)
from contextmesh.runtime.inspector import diff_tasks, inspect_task
from contextmesh.runtime.langfuse_export import build_langfuse_export
from contextmesh.runtime.ledger import record_step
from contextmesh.runtime.otel_export import build_otel_export


def _validate(payload: dict, schema_name: str) -> None:
    Draft202012Validator(get_context_schema(schema_name)).validate(payload)


def test_context_schema_exports_all_named_schemas():
    schemas = all_context_schemas()

    assert set(schemas) == {
        "audit",
        "candidate",
        "diff",
        "inspection",
        "langfuse-export",
        "otel-export",
    }
    assert schemas["inspection"]["x-contextmesh-schema-version"] == SCHEMA_VERSION
    assert "selected_context" in schemas["inspection"]["properties"]
    assert schemas["candidate"]["properties"]["status"]["enum"] == [
        "available",
        "selected",
        "rejected",
    ]


def test_unknown_context_schema_raises_clear_error():
    with pytest.raises(ValueError, match="schema must be one of"):
        get_context_schema("nope")


def test_context_schema_cli_outputs_one_schema():
    result = CliRunner().invoke(app, ["context", "schema", "audit"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["$id"].endswith("/context-audit.json")
    assert "findings" in payload["properties"]


def test_context_schema_cli_outputs_all_schemas():
    result = CliRunner().invoke(app, ["context", "schema"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "candidate" in payload
    assert "langfuse-export" in payload
    assert "otel-export" in payload


def test_context_payloads_validate_against_published_schemas():
    record_step(
        task_id="schema-left",
        step=1,
        agent="codex-cli",
        context_refs=[],
        context_text="failed context",
        decision="try old helper",
        outcome="failed",
        outcome_class="regressed",
    )
    record_candidate(CandidateInput(
        task_id="schema-left",
        step=1,
        ref="symbol:legacy_reset",
        status="selected",
        source_type="symbol",
        reason="old helper",
        relevance_score=0.2,
        tokens_estimated=40,
    ))
    record_step(
        task_id="schema-right",
        step=1,
        agent="codex-cli",
        context_refs=[],
        context_text="passed context",
        decision="try verifier",
        outcome="passed",
        outcome_class="passed",
        tokens_avoided=20,
    )
    record_candidate(CandidateInput(
        task_id="schema-right",
        step=1,
        ref="symbol:verify_reset_token",
        status="selected",
        source_type="symbol",
        reason="direct match",
        relevance_score=0.9,
        tokens_estimated=80,
    ))
    record_candidate(CandidateInput(
        task_id="schema-right",
        step=1,
        ref="file:docs/old-reset.md",
        status="rejected",
        source_type="doc",
        reason="stale",
        relevance_score=0.1,
        tokens_estimated=100,
    ))

    candidate_payload = candidate_as_dict(list_candidates("schema-right")[0])
    inspection_payload = inspect_task("schema-right").as_dict()
    diff_payload = diff_tasks("schema-left", "schema-right").as_dict()
    audit_payload = audit_context_candidates("schema-right").as_dict()
    langfuse_payload = build_langfuse_export(
        "schema-right",
        trace_id="trace-schema",
    ).as_dict()
    otel_payload = build_otel_export(
        "schema-right",
        trace_id="1234567890abcdef1234567890abcdef",
    ).as_dict()

    _validate(candidate_payload, "candidate")
    _validate(inspection_payload, "inspection")
    _validate(diff_payload, "diff")
    _validate(audit_payload, "audit")
    _validate(langfuse_payload, "langfuse-export")
    _validate(otel_payload, "otel-export")
