"""Filesystem fingerprinting primitives."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from contextmesh.config import DEFAULT_IGNORES

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


def detect_language(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return LANGUAGE_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "unknown")


def get_file_hash(filepath: str | Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def index_file(filepath: str | Path) -> dict:
    path = Path(filepath)
    stat = path.stat()
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            line_count = sum(1 for _ in f)
    except OSError:
        line_count = 0

    return {
        "path": str(path),
        "language": detect_language(path),
        "size": stat.st_size,
        "sha256": get_file_hash(path),
        "last_modified": stat.st_mtime,
        "line_count": line_count,
    }


def walk_repo(root: str | Path, *, ignores: set[str] = DEFAULT_IGNORES) -> Iterable[Path]:
    """Yield candidate files under *root*, skipping ignored directories.

    Pruning happens in-place so we never descend into vendor or virtualenv
    directories, even on huge repos.
    """
    import os

    root = str(root)
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignores]
        for name in files:
            if name == ".DS_Store" or name.endswith(".pyc"):
                continue
            yield Path(current) / name
