"""High-level helpers for turning files into packets."""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from contextmesh.config import relpath
from contextmesh.indexer.fingerprint import detect_language, index_file, walk_repo
from contextmesh.indexer.tree_sitter_parser import parse_python_source
from contextmesh.packets.schema import (
    FileSummaryPacket,
    RepoSummaryPacket,
    SymbolPacket,
)

KNOWN_FRAMEWORKS = {
    "pytest.ini": "pytest",
    "pyproject.toml": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "tsconfig.json": "typescript",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "manage.py": "django",
    "next.config.js": "nextjs",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def detect_frameworks(directory: Path) -> list[str]:
    out: list[str] = []
    for marker, name in KNOWN_FRAMEWORKS.items():
        if (directory / marker).exists():
            out.append(name)
    if (directory / "tests").is_dir() or (directory / "test").is_dir():
        out.append("tests")
    # pyproject inspection for fastapi / flask / django / pytest
    pyproject = directory / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
            for keyword in ("fastapi", "flask", "django", "pytest", "sqlmodel", "pydantic"):
                if keyword in text and keyword not in out:
                    out.append(keyword)
        except OSError:
            pass
    return out


def generate_repo_summary(directory: str | Path) -> RepoSummaryPacket:
    base = Path(directory)
    languages: Counter[str] = Counter()
    files = 0
    symbols = 0
    for filepath in walk_repo(base):
        files += 1
        languages[detect_language(filepath)] += 1
        if filepath.suffix == ".py":
            try:
                with open(filepath, "rb") as f:
                    parsed = parse_python_source(f.read())
                symbols += len(parsed["symbols"])
            except OSError:
                continue
    top_languages = [lang for lang, _ in languages.most_common(5) if lang != "unknown"]
    return RepoSummaryPacket(
        languages=top_languages,
        frameworks=detect_frameworks(base),
        files_indexed=files,
        symbols_indexed=symbols,
    )


def generate_file_summary(filepath: str | Path) -> FileSummaryPacket:
    info = index_file(filepath)
    return FileSummaryPacket(
        file=relpath(info["path"]),
        language=info["language"],
        size=info["size"],
        line_count=info["line_count"],
        hash=info["sha256"][:16],
    )


def generate_symbol_packets(filepath: str | Path) -> list[SymbolPacket]:
    path = Path(filepath)
    if path.suffix != ".py":
        return []
    try:
        with open(path, "rb") as f:
            source = f.read()
    except OSError:
        return []

    parsed = parse_python_source(source)
    lines = source.splitlines(keepends=True)
    out: list[SymbolPacket] = []
    rel = relpath(path)
    for sym in parsed["symbols"]:
        body = b"".join(lines[sym.start_line - 1:sym.end_line]).decode(
            "utf-8", errors="replace"
        )
        out.append(SymbolPacket(
            name=sym.name,
            file=rel,
            parent=sym.parent,
            signature=sym.signature,
            summary=sym.docstring or "No summary available.",
            hash=_hash(f"{rel}:{sym.parent}:{sym.name}:{body}"),
            raw_available=True,
        ))
    return out
