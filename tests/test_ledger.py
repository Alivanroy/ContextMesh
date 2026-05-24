from contextmesh.runtime.context_candidates import list_candidates
from contextmesh.runtime.ledger import get_ledger, record_event, record_step, task_summary


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


def test_record_event_turns_context_refs_into_selected_candidates():
    record_event({
        "task_id": "auto-candidates",
        "step": 1,
        "agent": "claude-code",
        "context_refs": ["Read(app.py)", "command:pytest tests"],
        "context_text": "read app and ran tests",
        "decision": "inspect and test",
        "outcome": "ok",
        "outcome_class": "unknown",
    })

    candidates = list_candidates("auto-candidates")

    assert [c.ref for c in candidates] == [
        "Read(app.py)",
        "file:app.py",
        "command:pytest tests",
    ]
    assert [c.status for c in candidates] == ["selected", "selected", "selected"]
    assert candidates[0].source_type == "tool"
    assert candidates[1].source_type == "file"
    assert candidates[1].reason == "derived from Read tool target"
    assert candidates[2].source_type == "command"


def test_record_event_derives_command_candidate_from_bash_tool_ref():
    record_event({
        "task_id": "auto-bash-candidates",
        "step": 1,
        "agent": "claude-code",
        "context_refs": ["Bash(pytest tests/test_auth.py)"],
        "context_text": "ran tests",
        "decision": "test",
        "outcome": "ok",
        "outcome_class": "unknown",
    })

    candidates = list_candidates("auto-bash-candidates")

    assert [c.ref for c in candidates] == [
        "Bash(pytest tests/test_auth.py)",
        "command:pytest tests/test_auth.py",
    ]
    assert candidates[1].source_type == "command"


def test_record_event_classifies_dotted_turn_ref():
    record_event({
        "task_id": "auto-turn-candidates",
        "step": 1,
        "agent": "codex-cli",
        "context_refs": ["turn.completed"],
        "context_text": "turn done",
        "decision": "final",
        "outcome": "ok",
    })

    candidates = list_candidates("auto-turn-candidates")

    assert candidates[0].ref == "turn.completed"
    assert candidates[0].source_type == "turn"


def test_record_step_does_not_create_context_candidates():
    record_step(
        task_id="manual-ledger",
        step=1,
        agent="coder",
        context_refs=["manual-ref"],
        context_text="manual context",
        decision="record manually",
        outcome="ok",
    )

    assert list_candidates("manual-ledger") == []
