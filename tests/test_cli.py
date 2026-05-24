from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from contextmesh.cli.main import app
from contextmesh.runtime.context_candidates import list_candidates


def test_init_reports_env_state_dir_without_touching_gitignore(tmp_path, monkeypatch):
    state = tmp_path / "external-state"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("CONTEXTMESH_STATE_DIR", str(state))

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert state.name in result.output
    assert "CONTEXTMESH_STATE_DIR override" in result.output
    assert (state / "contextmesh.db").exists()
    assert not (project / ".contextmesh").exists()
    assert not (project / ".gitignore").exists()


def test_trace_from_file_records_selected_context_candidates():
    fixture = Path(__file__).parent / "fixtures" / "codex_cli_session.jsonl"

    result = CliRunner().invoke(app, [
        "trace",
        "--task-id", "cli-trace-candidates",
        "--agent", "codex-cli",
        "--silent",
        "--from-file", str(fixture),
        "--",
        "noop",
    ])

    assert result.exit_code == 0
    candidates = list_candidates("cli-trace-candidates")
    refs = [c.ref for c in candidates]
    assert any(ref.startswith("command:") for ref in refs)
    assert "turn.completed" in refs
    assert all(c.status == "selected" for c in candidates)
