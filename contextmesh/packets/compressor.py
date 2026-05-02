"""Delta-aware packet compression.

The compressor takes a flat list of packets and a task id, and returns a
shrunken list where ``symbol`` packets the agent has already received during
this task become ``symbol_ref`` packets carrying only the hash. The cache
lives in the ``seen_packet`` table so the savings persist across CLI runs.
"""
from __future__ import annotations

from typing import Iterable

from sqlmodel import select

from contextmesh.packets.schema import SymbolPacket, SymbolRefPacket
from contextmesh.storage.db import SeenPacket, create_db_and_tables, get_session


COMPRESSIBLE_TYPES = {"symbol", "file_summary"}


def _existing_hashes(session, task_id: str) -> set[str]:
    rows = session.exec(
        select(SeenPacket.packet_hash).where(SeenPacket.task_id == task_id)
    ).all()
    return set(rows)


def _record(session, task_id: str, packet_hash: str, packet_type: str) -> None:
    session.add(SeenPacket(
        task_id=task_id,
        packet_hash=packet_hash,
        packet_type=packet_type,
    ))


def compress_packets(
    task_id: str,
    packets: Iterable[dict],
    *,
    persist: bool = True,
    pinned_hashes: set[str] | None = None,
) -> list[dict]:
    """Replace already-seen ``symbol`` packets with ``symbol_ref`` shells.

    ``pinned_hashes`` are emitted in full even when seen before — used for
    symbols on a failure trace, where the agent needs the body *this turn*
    even if it received the same packet earlier.
    """
    create_db_and_tables()
    out: list[dict] = []
    seen_now: set[str] = set()
    pins = pinned_hashes or set()

    with get_session() as session:
        seen_before = _existing_hashes(session, task_id)
        for packet in packets:
            ptype = packet.get("type")
            phash = packet.get("hash")
            is_pinned = bool(phash and phash in pins) or bool(packet.get("pinned"))

            if (
                ptype in COMPRESSIBLE_TYPES
                and phash
                and phash in seen_before
                and not is_pinned
            ):
                if ptype == "symbol":
                    ref = SymbolRefPacket(
                        hash=phash,
                        name=packet.get("name"),
                        file=packet.get("file"),
                    )
                    out.append(ref.model_dump())
                    continue
                out.append({"type": "file_ref", "hash": phash, "file": packet.get("file")})
                continue

            out.append(packet)
            if persist and phash and ptype in COMPRESSIBLE_TYPES and phash not in seen_now:
                _record(session, task_id, phash, ptype)
                seen_now.add(phash)
        if persist:
            session.commit()
    return out


def reset_seen(task_id: str | None = None) -> int:
    """Clear seen-packet records. Returns rows removed."""
    create_db_and_tables()
    with get_session() as session:
        stmt = select(SeenPacket)
        if task_id is not None:
            stmt = stmt.where(SeenPacket.task_id == task_id)
        rows = list(session.exec(stmt).all())
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)
