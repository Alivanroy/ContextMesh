from io import StringIO

from rich.console import Console

from contextmesh.runtime.dashboard import (
    render_dashboard,
    render_overview,
    render_per_task,
    render_provider_tokens,
    render_timeline,
    render_waste,
)
from contextmesh.runtime.ledger import record_event, record_step


def _capture(fn) -> str:
    buf = StringIO()
    console = Console(file=buf, width=120, color_system=None, force_terminal=False)
    fn(console)
    return buf.getvalue()


def test_overview_renders_when_empty():
    out = _capture(render_overview)
    assert "ContextMesh" in out
    assert "Useful-context ratio" in out


def test_per_task_renders_with_data():
    record_step(
        task_id="dash-1",
        step=1,
        agent="claude",
        context_refs=[],
        context_text="x" * 40,
        decision="patch",
        outcome="ok",
        outcome_class="passed",
        tokens_kept_compressed=20,
    )
    out = _capture(render_per_task)
    assert "dash-1" in out
    assert "passed" in out


def test_timeline_renders_recent_steps():
    record_step(
        task_id="dash-2", step=1, agent="aider",
        context_refs=[], context_text="x" * 50,
        decision="d", outcome="ok", outcome_class="passed",
        tokens_kept_compressed=30,
    )
    out = _capture(render_timeline)
    assert "dash-2" in out
    assert "aider" in out


def test_waste_panel_silent_when_empty():
    out = _capture(render_waste)
    assert out == ""


def test_provider_panel_silent_without_data():
    record_step(
        task_id="no-prov", step=1, agent="t",
        context_refs=[], context_text="x" * 30,
        decision="d", outcome="ok", outcome_class="passed",
    )
    out = _capture(render_provider_tokens)
    assert out == ""


def test_provider_panel_renders_when_data_present():
    record_event({
        "task_id": "with-prov", "step": 1, "agent": "claude-code",
        "context_text": "x" * 20, "decision": "d", "outcome": "ok",
        "outcome_class": "passed",
        "tokens_provider_input": 1234,
        "tokens_cached_read": 9876,
        "tokens_cached_write": 200,
        "tokens_provider_output": 75,
    })
    out = _capture(render_provider_tokens)
    assert "with-prov" in out
    assert "1,234" in out
    assert "9,876" in out
    assert "Cache hit" in out


def test_overview_includes_provider_section_when_data_present():
    record_event({
        "task_id": "ov-prov", "step": 1, "agent": "claude-code",
        "context_text": "x" * 20, "decision": "d", "outcome": "ok",
        "outcome_class": "passed",
        "tokens_provider_input": 500,
        "tokens_cached_read": 2000,
    })
    out = _capture(render_overview)
    assert "Cache hit rate" in out
    assert "cache reads" in out


def test_full_dashboard_runs_without_error():
    record_step(
        task_id="full", step=1, agent="t",
        context_refs=[], context_text="x" * 30,
        decision="d", outcome="ok", outcome_class="passed",
    )
    out = _capture(render_dashboard)
    assert "ContextMesh" in out
    assert "full" in out
