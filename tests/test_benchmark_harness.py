from io import StringIO

from benchmarks.harness import default_agents, default_tasks, render, run


def test_harness_runs_all_combinations(monkeypatch):
    # The harness sets CONTEXTMESH_STATE_DIR per run; conftest's autouse
    # fixture restores isolation for the test itself, so we can just call run().
    tasks = default_tasks()
    agents = default_agents()
    report = run(tasks, agents)

    assert len(report["runs"]) == len(tasks) * len(agents)
    for r in report["runs"]:
        assert "metrics" in r
        m = r["metrics"]
        # Every run must surface the four provider columns and useful_context_ratio
        for key in (
            "tokens_provider_input",
            "tokens_cached_read",
            "tokens_cached_write",
            "tokens_provider_output",
            "tokens_avoided",
            "useful_context_ratio",
            "final_outcome_class",
        ):
            assert key in m


def test_default_harness_runs_all_classify_correctly():
    """Every default (task, agent) pair must produce the expected outcome.

    A failing row in the published leaderboard would undermine the whole
    metric, so we lock this in. If you add a new default task, add a
    fixture for every default agent that produces the expected outcome.
    """
    tasks = default_tasks()
    agents = default_agents()
    report = run(tasks, agents)
    misclassified = [
        f"{r['agent']}/{r['task']['id']} got {r['metrics']['final_outcome_class']}"
        f" (expected {r['task']['expected_outcome']})"
        for r in report["runs"] if not r["outcome_correctly_classified"]
    ]
    assert not misclassified, "default harness has misclassified rows: " + "; ".join(misclassified)


def test_traced_session_billed_tokens_use_provider_numbers():
    """Regression: when an event carries provider-token fields, the metric
    must bill those numbers, not a local cl100k_base estimate of the
    tiny ``context_text``."""
    from contextmesh.runtime.ledger import record_event
    from contextmesh.runtime.metrics import task_metrics

    record_event({
        "task_id": "T-prov", "step": 1, "agent": "claude-code",
        "context_text": "hi",  # ~1 local token
        "decision": "tiny", "outcome": "ok", "outcome_class": "passed",
        "tokens_provider_input": 5_400,
        "tokens_cached_read": 12_160,
        "tokens_cached_write": 0,
        "tokens_provider_output": 240,
    })
    m = task_metrics("T-prov")
    # Must bill the real provider input volume, not the cl100k_base of "hi".
    assert m.tokens_billed == 5_400 + 12_160
    assert m.useful_context_ratio == 1.0


def test_harness_render_emits_leaderboard():
    tasks = default_tasks()
    agents = default_agents()
    report = run(tasks, agents)
    buf = StringIO()
    render(report, file=buf)
    out = buf.getvalue()
    assert "ContextMesh benchmark" in out
    assert "Useful%" in out
    for r in report["runs"]:
        assert r["task"]["id"] in out
        assert r["agent"] in out
