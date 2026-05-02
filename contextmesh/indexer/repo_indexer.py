"""Persisted, delta-aware repository indexer.

Walks the project root, hashes files, parses Python source with tree-sitter,
and stores both files and symbols in SQLite. Re-indexing skips files whose
content hash hasn't changed, and prunes records for files that have been
deleted on disk.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlmodel import select

from contextmesh.config import load_config, relpath
from contextmesh.indexer.fingerprint import (
    detect_language,
    get_file_hash,
    index_file,
    walk_repo,
)
from contextmesh.indexer.tree_sitter_parser import parse_python_source
from contextmesh.storage.db import (
    IndexedFile,
    IndexedSymbol,
    create_db_and_tables,
    get_session,
)


@dataclass
class IndexStats:
    scanned: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    removed: int = 0
    symbols: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "new": self.new,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "symbols": self.symbols,
            "failed": self.failed,
        }


def _hash_body(body: bytes | str) -> str:
    if isinstance(body, str):
        body = body.encode("utf-8", errors="ignore")
    return hashlib.sha256(body).hexdigest()[:16]


def _slice_body(source: bytes, start_line: int, end_line: int) -> bytes:
    lines = source.splitlines(keepends=True)
    return b"".join(lines[start_line - 1:end_line])


def _upsert_symbols(session, file_path: str, source: bytes) -> int:
    """Replace symbols for *file_path* with freshly-extracted ones."""
    parsed = parse_python_source(source)
    symbols = parsed["symbols"]

    # Drop existing symbols for this file before re-inserting.
    existing = session.exec(
        select(IndexedSymbol).where(IndexedSymbol.file_path == file_path)
    ).all()
    for s in existing:
        session.delete(s)

    for sym in symbols:
        body = _slice_body(source, sym.start_line, sym.end_line)
        session.add(IndexedSymbol(
            file_path=file_path,
            name=sym.name,
            parent=sym.parent,
            symbol_type=sym.symbol_type,
            signature=sym.signature,
            start_line=sym.start_line,
            end_line=sym.end_line,
            docstring=sym.docstring,
            body_hash=_hash_body(body),
        ))
    return len(symbols)


def reindex(root: str | Path | None = None) -> IndexStats:
    """Walk *root* and update the persisted index. Returns stats."""
    config = load_config()
    base = Path(root).resolve() if root else config.project_root
    create_db_and_tables()

    stats = IndexStats()
    seen_paths: set[str] = set()

    with get_session() as session:
        existing = {
            f.path: f
            for f in session.exec(select(IndexedFile)).all()
        }

        for filepath in walk_repo(base):
            stats.scanned += 1
            rel = relpath(filepath, root=config.project_root)
            seen_paths.add(rel)
            try:
                info = index_file(filepath)
            except OSError:
                stats.failed += 1
                continue

            row = existing.get(rel)
            if row is None:
                row = IndexedFile(
                    path=rel,
                    language=info["language"],
                    size=info["size"],
                    sha256=info["sha256"],
                    line_count=info["line_count"],
                    last_modified=info["last_modified"],
                )
                session.add(row)
                stats.new += 1
                changed = True
            elif row.sha256 != info["sha256"]:
                row.size = info["size"]
                row.sha256 = info["sha256"]
                row.line_count = info["line_count"]
                row.last_modified = info["last_modified"]
                row.language = info["language"]
                session.add(row)
                stats.changed += 1
                changed = True
            else:
                stats.unchanged += 1
                changed = False

            if changed and detect_language(filepath) == "python":
                try:
                    with open(filepath, "rb") as f:
                        source = f.read()
                    stats.symbols += _upsert_symbols(session, rel, source)
                except OSError:
                    stats.failed += 1

        for path, row in existing.items():
            if path not in seen_paths:
                session.delete(row)
                for sym in session.exec(
                    select(IndexedSymbol).where(IndexedSymbol.file_path == path)
                ).all():
                    session.delete(sym)
                stats.removed += 1

        session.commit()

    return stats


def list_files() -> list[IndexedFile]:
    create_db_and_tables()
    with get_session() as session:
        return list(session.exec(select(IndexedFile).order_by(IndexedFile.path)).all())


def list_symbols(file_path: str | None = None) -> list[IndexedSymbol]:
    create_db_and_tables()
    with get_session() as session:
        stmt = select(IndexedSymbol)
        if file_path:
            stmt = stmt.where(IndexedSymbol.file_path == file_path)
        return list(session.exec(stmt).all())


def find_symbol(name: str, file_path: str | None = None) -> list[IndexedSymbol]:
    create_db_and_tables()
    with get_session() as session:
        stmt = select(IndexedSymbol).where(IndexedSymbol.name == name)
        if file_path:
            stmt = stmt.where(IndexedSymbol.file_path == file_path)
        return list(session.exec(stmt).all())


def iter_indexed_python_files() -> Iterable[IndexedFile]:
    for f in list_files():
        if f.language == "python":
            yield f
