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
