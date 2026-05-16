from __future__ import annotations

import builtins
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def test_schema_creation_is_safe_across_first_run_processes(tmp_path):
    state = tmp_path / "concurrent-state"
    env = {
        **os.environ,
        "CONTEXTMESH_STATE_DIR": str(state),
    }
    code = "from contextmesh.storage.db import create_db_and_tables; create_db_and_tables()"

    procs = [
        subprocess.Popen([sys.executable, "-c", code], env=env, text=True)
        for _ in range(6)
    ]
    exits = [p.wait(timeout=10) for p in procs]

    assert exits == [0] * len(procs)
    assert (state / "contextmesh.db").exists()
    assert (state / "contextmesh.schema.lock").exists()


def test_first_run_index_writes_are_serialized(tmp_path):
    state = tmp_path / "index-state"
    out_path = tmp_path / "context.jsonl"
    repo = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "CONTEXTMESH_STATE_DIR": str(state),
    }
    commands = [
        [
            sys.executable, "-m", "contextmesh.cli.main",
            "index", "demo", "--json",
        ],
        [
            sys.executable, "-m", "contextmesh.cli.main",
            "export-context", "--task", "race", "--task-id", "race",
            "--path", "demo", "--format", "jsonl", "--out", str(out_path),
        ],
    ]

    procs = [subprocess.Popen(cmd, cwd=repo, env=env, text=True) for cmd in commands]
    exits = [p.wait(timeout=10) for p in procs]

    assert exits == [0, 0]
    assert out_path.exists()


def test_db_write_lock_uses_msvcrt_when_fcntl_is_unavailable(tmp_path, monkeypatch):
    from contextmesh.storage import db

    calls: list[tuple[int, int, int]] = []
    fake_msvcrt = SimpleNamespace(
        LK_LOCK=1,
        LK_UNLCK=2,
        locking=lambda fd, mode, size: calls.append((fd, mode, size)),
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError(name)
        if name == "msvcrt":
            return fake_msvcrt
        return real_import(name, *args, **kwargs)

    monkeypatch.setenv("CONTEXTMESH_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with db.db_write_lock():
        assert calls[-1][1:] == (fake_msvcrt.LK_LOCK, 1)

    assert calls[-1][1:] == (fake_msvcrt.LK_UNLCK, 1)
