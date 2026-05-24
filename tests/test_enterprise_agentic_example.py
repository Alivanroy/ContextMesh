import json

from jsonschema import Draft202012Validator

from contextmesh.runtime.context_schema import get_context_schema
from examples.enterprise_agentic.support_risk_agent import run_agent


def test_enterprise_agentic_example_generates_real_contextmesh_artifacts(tmp_path):
    artifacts = run_agent("enterprise-test", out_dir=tmp_path)

    plan = artifacts["plan"]
    inspection = artifacts["inspection"]
    audit = artifacts["audit"]
    langfuse = artifacts["langfuse"]
    otel = artifacts["otel"]
    slack = artifacts["slack"]
    jira = artifacts["jira"]

    assert plan["severity"] == "P1"
    assert plan["decision"] == "disable eu-west auth rollout flag"
    assert inspection["final_outcome_class"] == "passed"
    assert inspection["context_quality_score"] >= 0.8
    assert len(inspection["selected_context"]) == 4
    assert len(inspection["rejected_context"]) == 2
    assert audit["passed"] is True
    assert slack["target"] == "slack"
    assert jira["target"] == "jira"

    Draft202012Validator(get_context_schema("inspection")).validate(inspection)
    Draft202012Validator(get_context_schema("audit")).validate(audit)
    Draft202012Validator(get_context_schema("langfuse-export")).validate(langfuse)
    Draft202012Validator(get_context_schema("otel-export")).validate(otel)

    for name in ["plan", "inspection", "audit", "langfuse", "otel", "slack", "jira"]:
        assert (tmp_path / f"{name}.json").exists()
        json.loads((tmp_path / f"{name}.json").read_text())


def test_enterprise_agentic_example_rejects_stale_and_sensitive_context(tmp_path):
    artifacts = run_agent("enterprise-rejections", out_dir=tmp_path)

    rejected = artifacts["inspection"]["rejected_context"]
    refs = [item["ref"] for item in rejected]
    reasons = " ".join(item["reason"] for item in rejected)

    assert any("stale_reset_policy_2024" in ref for ref in refs)
    assert any("raw_debug_dump" in ref for ref in refs)
    assert "stale policy" in reasons
    assert "sensitive debug context" in reasons
