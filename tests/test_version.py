"""Lock pyproject ↔ package ↔ git tag versions to a single source of truth.

This catches the v0.2.0/v0.2.1 drift caught by an external review: the git
tag was ``v0.2.1`` while ``pyproject.toml`` still said ``0.1.0``. Future
release automation breaks silently when those disagree, so we make
``ruff + pytest`` fail loudly instead.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import contextmesh

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
SEMVER = re.compile(r'(?m)^version\s*=\s*"([^"]+)"')


def _pyproject_version() -> str:
    m = SEMVER.search(PYPROJECT.read_text(encoding="utf-8"))
    assert m, "no version line in pyproject.toml"
    return m.group(1)


def test_pyproject_matches_package_version():
    assert contextmesh.__version__ == _pyproject_version(), (
        "contextmesh.__version__ and pyproject.toml are out of sync; bump both."
    )


def _semver_tuple(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", s))


def test_pyproject_version_is_not_older_than_any_published_tag():
    """Catches the actual v0.2.0/v0.2.1 bug: pyproject left at 0.1.0
    while ``v0.2.1`` was already pushed.

    Rule: pyproject version must be >= the highest semver tag.
    Mid-bump commits (pyproject ahead of last tag) are fine; this only
    fails when a published tag is *newer* than pyproject — i.e. the
    package would `pip install` under a stale name.
    """
    git_dir = PYPROJECT.parent / ".git"
    if not git_dir.exists():
        return

    out = subprocess.run(
        ["git", "tag", "--list", "v*"],
        capture_output=True, text=True, cwd=PYPROJECT.parent,
    ).stdout.strip().splitlines()
    if not out:
        return

    latest = max(out, key=_semver_tuple)
    if _semver_tuple(contextmesh.__version__) < _semver_tuple(latest):
        raise AssertionError(
            f"pyproject / __version__ is {contextmesh.__version__!r} but"
            f" the highest published git tag is {latest!r}. Bump"
            f" pyproject.toml and contextmesh/__init__.py to match or"
            f" exceed it before merging."
        )
