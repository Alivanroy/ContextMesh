import json

from jsonschema import Draft202012Validator

from contextmesh.runtime.context_schema import get_context_schema
from examples.enterprise_rag_office.office_rag_agent import run_office_rag


def test_enterprise_office_rag_generates_real_files_and_contextmesh_artifacts(tmp_path):
    artifacts = run_office_rag("office-rag-test", out_dir=tmp_path)

    answer = artifacts["answer"]
    inspection = artifacts["inspection"]
    audit = artifacts["audit"]
    langfuse = artifacts["langfuse"]
    otel = artifacts["otel"]
    slack = artifacts["slack"]
    jira = artifacts["jira"]

    assert answer["recommendation"] == "conditional_approve"
    assert inspection["final_outcome_class"] == "passed"
    assert inspection["context_quality_score"] >= 0.8
    assert len(inspection["selected_context"]) == 8
    assert len(inspection["rejected_context"]) == 5
    assert audit["passed"] is True
    assert slack["target"] == "slack"
    assert jira["target"] == "jira"

    source_files = tmp_path / "source_files"
    assert (source_files / "Acme_MSA_Renewal.docx").exists()
    assert (source_files / "Security_Due_Diligence.docx").exists()
    assert (source_files / "Legacy_2023_Renewal_Notes.docx").exists()
    assert (source_files / "SLA_Usage_Risk.xlsx").exists()

    Draft202012Validator(get_context_schema("inspection")).validate(inspection)
    Draft202012Validator(get_context_schema("audit")).validate(audit)
    Draft202012Validator(get_context_schema("langfuse-export")).validate(langfuse)
    Draft202012Validator(get_context_schema("otel-export")).validate(otel)

    for name in ["answer", "chunks", "inspection", "audit", "langfuse", "otel", "slack", "jira"]:
        assert (tmp_path / f"{name}.json").exists()
        json.loads((tmp_path / f"{name}.json").read_text())


def test_enterprise_office_rag_rejects_stale_word_doc_and_irrelevant_excel_row(tmp_path):
    artifacts = run_office_rag("office-rag-rejections", out_dir=tmp_path)

    rejected = artifacts["inspection"]["rejected_context"]
    refs = [item["ref"] for item in rejected]
    reasons = " ".join(item["reason"] for item in rejected)

    assert sum("Legacy_2023_Renewal_Notes.docx" in ref for ref in refs) == 4
    assert any("SLA_Usage_Risk.xlsx:Usage Risk:r5" in ref for ref in refs)
    assert "stale renewal document" in reasons
    assert "irrelevant commercial usage row" in reasons
