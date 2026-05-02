"""Per-project configuration and storage paths.

ContextMesh keeps state under a per-project ``.contextmesh/`` directory at the
nearest ancestor that contains a ``.contextmesh`` marker, falling back to the
current working directory. This keeps fingerprints, the ledger, and the seen
cache scoped to a single repository.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DIR_NAME = ".contextmesh"
DB_FILE = "contextmesh.db"
DEFAULT_IGNORES = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", "node_modules",
    "dist", "build", ".next", ".nuxt", ".cache",
    DIR_NAME,
}


@dataclass(frozen=True)
class Config:
    project_root: Path
    state_dir: Path
    db_path: Path

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


def find_project_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / DIR_NAME).is_dir():
            return parent
    return cur


def load_config(start: Path | None = None, *, create: bool = True) -> Config:
    root = find_project_root(start)
    state = root / DIR_NAME
    if create:
        state.mkdir(parents=True, exist_ok=True)
    db = state / DB_FILE
    return Config(project_root=root, state_dir=state, db_path=db)


def relpath(path: str | Path, *, root: Path | None = None) -> str:
    """Return *path* relative to the project root, falling back to absolute."""
    p = Path(path).resolve()
    base = (root or load_config(create=False).project_root).resolve()
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def is_ignored(path: str, ignores: set[str] = DEFAULT_IGNORES) -> bool:
    parts = set(Path(path).parts)
    return bool(parts & ignores)


def env_state_dir() -> Path | None:
    """Allow overriding state dir for tests via ``CONTEXTMESH_STATE_DIR``."""
    raw = os.environ.get("CONTEXTMESH_STATE_DIR")
    return Path(raw).resolve() if raw else None
