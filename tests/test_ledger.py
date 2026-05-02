from contextmesh.runtime.ledger import get_ledger, record_step, task_summary


def test_record_and_get_ledger():
    entry = record_step(
        task_id="T-001",
        step=1,
        agent="coder",
        context_refs=["test_ref"],
        context_text="def foo(): pass",
        decision="wrote foo",
        outcome="success",
        tokens_avoided=42,
    )

    assert entry.task_id == "T-001"
    assert entry.tokens_estimated > 0
    assert entry.tokens_avoided == 42

    entries = get_ledger()
    assert len(entries) == 1
    assert entries[0].task_id == "T-001"


def test_task_summary_aggregates():
    record_step("T-2", 1, "coder", [], "abc def", "step1", "ok")
    record_step("T-2", 2, "coder", [], "ghi jkl", "step2", "ok", tokens_avoided=10)

    summary = task_summary("T-2")
    assert summary["steps"] == 2
    assert summary["tokens_avoided"] == 10
    assert summary["tokens_estimated"] > 0
