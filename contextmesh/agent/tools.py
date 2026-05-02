"""Tools an agent can call when a packet's raw body is needed."""
from __future__ import annotations

from pathlib import Path

from contextmesh.config import load_config
from contextmesh.indexer.repo_indexer import find_symbol
from contextmesh.indexer.tree_sitter_parser import parse_python_source


def _resolve(filepath: str | Path) -> Path | None:
    """Resolve *filepath* to an absolute, existing path.

    Tries (in order):
      1. The path as-given (handles absolute paths and cwd-relative paths).
      2. The path joined to the project root (handles repo-relative paths
         the indexer stored when cwd was the project root).

    Returns ``None`` if neither resolves to an existing file.
    """
    raw = Path(filepath)
    if raw.is_file():
        return raw.resolve()

    try:
        project_root = load_config(create=False).project_root
    except OSError:
        return None
    candidate = (project_root / filepath).resolve()
    if candidate.is_file():
        return candidate
    return None


def expand_symbol(
    filepath: str,
    symbol_name: str,
    *,
    parent: str | None = None,
) -> str | None:
    """Return the source body for *symbol_name* in *filepath*.

    *filepath* may be absolute, cwd-relative, or project-relative
    (the form stored in :class:`~contextmesh.packets.schema.SymbolPacket`).
    If *parent* is given (e.g. ``"PasswordResetToken"``) the lookup is
    disambiguated to that class.
    """
    resolved = _resolve(filepath)
    if resolved is None:
        return None
    try:
        source = resolved.read_bytes()
    except OSError:
        return None

    parsed = parse_python_source(source)
    candidates = [
        s for s in parsed["symbols"]
        if s.name == symbol_name and (parent is None or s.parent == parent)
    ]
    if not candidates:
        return None

    sym = candidates[0]
    lines = source.decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[sym.start_line - 1:sym.end_line])


def expand_symbol_indexed(name: str, *, file_path: str | None = None) -> str | None:
    """Expand a symbol via the persisted index. Disambiguates by file path."""
    matches = find_symbol(name, file_path=file_path)
    if not matches:
        return None
    sym = matches[0]
    return expand_symbol(sym.file_path, sym.name, parent=sym.parent)
