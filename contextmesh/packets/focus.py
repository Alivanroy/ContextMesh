"""Critical-path focusing: inline bodies of symbols mentioned in failure traces.

When a test fails, the symbol containing the failing line — and any other
symbol named in the trace or assertion — becomes load-bearing context for
the next agent turn. The compressor would otherwise replace these with
``symbol_ref``s on subsequent runs, which is exactly the wrong move when
the symbol is the bug.

This module finds those symbols, inlines their bodies into the existing
``SymbolPacket``s, marks them ``pinned=True``, and returns the set of
hashes the compressor should leave alone.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from contextmesh.agent.tools import expand_symbol
from contextmesh.indexer.repo_indexer import find_symbol, list_symbols

IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z_0-9]+\b")
STOP_WORDS = {
    "self", "cls", "True", "False", "None", "assert", "def", "class",
    "return", "import", "from", "as", "if", "else", "elif", "for", "while",
    "try", "except", "finally", "with", "in", "is", "not", "and", "or",
    "py", "test", "tests", "Error", "Exception", "AssertionError",
}


def _trace_text(failure: dict) -> str:
    return " ".join(filter(None, [
        failure.get("minimal_trace") or "",
        failure.get("assertion") or "",
        failure.get("test") or "",
    ]))


def symbols_on_trace(failure: dict) -> list[tuple[str, str | None, str]]:
    """Return ``[(name, parent, file), ...]`` for symbols mentioned by *failure*.

    Combines two signals:
    1. The containing symbol at ``failure.file`` / ``failure.line``.
    2. Any indexed symbol whose name appears as an identifier in the trace.
    """
    out: list[tuple[str, str | None, str]] = []
    seen: set[tuple[str, str | None, str]] = set()

    file_path = failure.get("file")
    line = failure.get("line")
    if file_path and line:
        for sym in list_symbols(file_path):
            if sym.start_line <= line <= sym.end_line:
                key = (sym.name, sym.parent, sym.file_path)
                if key not in seen:
                    out.append(key)
                    seen.add(key)

    for token in IDENTIFIER.findall(_trace_text(failure)):
        if token in STOP_WORDS or len(token) <= 2:
            continue
        for sym in find_symbol(token):
            key = (sym.name, sym.parent, sym.file_path)
            if key not in seen:
                out.append(key)
                seen.add(key)

    return out


def extract_failures(blob: dict) -> list[dict]:
    """Pull ``test_failure`` packets out of a CommandResult or a bare failure."""
    t = blob.get("type")
    if t == "test_failure":
        return [blob]
    if t == "command_result":
        return list(blob.get("failures") or [])
    return []


def augment_with_failures(
    packets: Iterable[dict],
    failures: Iterable[dict],
) -> tuple[list[dict], set[str]]:
    """Inline bodies for symbols on failure traces.

    Returns ``(new_packets, pinned_hashes)`` — the compressor must receive
    *pinned_hashes* so it doesn't downgrade these symbols to refs.
    """
    targets: set[tuple[str, str | None, str]] = set()
    for f in failures:
        targets.update(symbols_on_trace(f))

    if not targets:
        return list(packets), set()

    pinned: set[str] = set()
    out: list[dict] = []
    for packet in packets:
        if packet.get("type") != "symbol":
            out.append(packet)
            continue
        key = (packet.get("name"), packet.get("parent"), packet.get("file"))
        if key in targets:
            file_path = packet.get("file")
            body = expand_symbol(file_path, packet["name"], parent=packet.get("parent")) if file_path else None
            packet = {**packet, "pinned": True}
            if body:
                packet["body"] = body
            if packet.get("hash"):
                pinned.add(packet["hash"])
        out.append(packet)
    return out, pinned
