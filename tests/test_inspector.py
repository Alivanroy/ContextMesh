from contextmesh.runtime.inspector import diff_tasks, inspect_task
from contextmesh.runtime.ledger import record_step


def test_inspector_scores_passed_run_with_selected_context():
    record_step(
        task_id="inspect-pass",
        step=1,
        agent="codex-cli",
        context_refs=["file:auth/reset.py", "symbol:verify_reset_token"],
        context_text="def verify_reset_token(): pass",
        decision="patched reset token verification",
        outcome="tests passed",
        outcome_class="passed",
        tokens_avoided=50,
    )

    inspection = inspect_task("inspect-pass")

    assert inspection.task_id == "inspect-pass"
    assert inspection.final_outcome_class == "passed"
    assert inspection.context_quality_score > 0.7
    assert [item.ref for item in inspection.selected_context] == [
        "file:auth/reset.py",
        "symbol:verify_reset_token",
    ]
    assert inspection.langfuse_metadata()["contextmesh"]["selected_context_refs"] == [
        "file:auth/reset.py",
        "symbol:verify_reset_token",
    ]


def test_inspector_flags_missing_refs_and_failed_outcome():
    record_step(
        task_id="inspect-fail",
        step=1,
        agent="aider",
        context_refs=[],
        context_text="large unstructured context",
        decision="attempted patch",
        outcome="still failing",
        outcome_class="regressed",
    )

    inspection = inspect_task("inspect-fail")

    assert inspection.context_quality_score < 0.4
    assert inspection.selected_context == []
    assert any("Record context refs" in rec for rec in inspection.recommendations)
    assert any("Compare this run" in rec for rec in inspection.recommendations)


def test_inspector_counts_duplicate_ref_sends():
    record_step(
        task_id="inspect-dupes",
        step=1,
        agent="claude-code",
        context_refs=["symbol:User.reset"],
        context_text="x" * 40,
        decision="read symbol",
        outcome="ok",
        outcome_class="unchanged",
    )
    record_step(
        task_id="inspect-dupes",
        step=2,
        agent="claude-code",
        context_refs=["symbol:User.reset"],
        context_text="x" * 40,
        decision="read symbol again",
        outcome="ok",
        outcome_class="unchanged",
    )

    inspection = inspect_task("inspect-dupes")

    assert inspection.duplicate_ref_sends == 1
    assert inspection.selected_context[0].times_selected == 2
    assert any("duplicate context sends" in rec for rec in inspection.recommendations)


def test_diff_tasks_highlights_context_added_in_passed_run():
    record_step(
        task_id="diff-failed",
        step=1,
        agent="codex-cli",
        context_refs=["file:auth/reset.py", "symbol:legacy_reset"],
        context_text="legacy reset helper",
        decision="patched old helper",
        outcome="tests still failing",
        outcome_class="regressed",
    )
    record_step(
        task_id="diff-passed",
        step=1,
        agent="codex-cli",
        context_refs=["file:auth/reset.py", "symbol:verify_reset_token"],
        context_text="verified reset token logic",
        decision="patched verifier",
        outcome="tests passed",
        outcome_class="passed",
        tokens_avoided=30,
    )

    diff = diff_tasks("diff-failed", "diff-passed")

    assert diff.left_outcome_class == "regressed"
    assert diff.right_outcome_class == "passed"
    assert diff.quality_delta > 0
    assert diff.refs_shared == ["file:auth/reset.py"]
    assert diff.refs_only_left == ["symbol:legacy_reset"]
    assert diff.refs_only_right == ["symbol:verify_reset_token"]
    assert any("Promote refs" in rec for rec in diff.recommendations)
    assert any("Review refs" in rec for rec in diff.recommendations)


def test_diff_tasks_json_payload_rounds_scores():
    record_step(
        task_id="diff-json-left",
        step=1,
        agent="aider",
        context_refs=[],
        context_text="missing refs",
        decision="try",
        outcome="unknown",
        outcome_class="unknown",
    )
    record_step(
        task_id="diff-json-right",
        step=1,
        agent="aider",
        context_refs=["file:auth/reset.py"],
        context_text="specific refs",
        decision="try",
        outcome="ok",
        outcome_class="unchanged",
    )

    payload = diff_tasks("diff-json-left", "diff-json-right").as_dict()

    assert payload["left_task_id"] == "diff-json-left"
    assert payload["right_task_id"] == "diff-json-right"
    assert isinstance(payload["quality_delta"], float)
    assert payload["refs_only_right"] == ["file:auth/reset.py"]
