from __future__ import annotations

from typer.testing import CliRunner

from contextmesh.cli.main import app


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
