"""Shared fixtures.

Routes ContextMesh storage to a per-test temp directory via
``CONTEXTMESH_STATE_DIR`` so tests never touch the real database.
"""
from __future__ import annotations

import os

import pytest

from contextmesh.storage import db


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    state = tmp_path / ".contextmesh"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CONTEXTMESH_STATE_DIR", str(state))
    db.reset_engine()
    db.create_db_and_tables()
    yield state
    db.reset_engine()
