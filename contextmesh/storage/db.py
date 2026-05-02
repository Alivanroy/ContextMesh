"""Persistent storage for the index, ledger, and seen-packet cache."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, Session, SQLModel, create_engine

from contextmesh.config import env_state_dir, load_config

_engine = None
_engine_url: str | None = None


def _build_url() -> str:
    override = env_state_dir()
    if override:
        override.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{override / 'contextmesh.db'}"
    return load_config().db_url


def get_engine():
    global _engine, _engine_url
    url = _build_url()
    if _engine is None or _engine_url != url:
        _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
        _engine_url = url
    return _engine


def set_engine(engine) -> None:
    """Override the engine, used by tests."""
    global _engine, _engine_url
    _engine = engine
    _engine_url = str(engine.url) if engine is not None else None


def reset_engine() -> None:
    set_engine(None)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    return Session(get_engine())


class IndexedFile(SQLModel, table=True):
    __tablename__ = "indexed_file"

    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)
    language: str
    size: int
    sha256: str = Field(index=True)
    line_count: int
    last_modified: float
    last_indexed: datetime = Field(default_factory=datetime.utcnow)


class IndexedSymbol(SQLModel, table=True):
    __tablename__ = "indexed_symbol"

    id: int | None = Field(default=None, primary_key=True)
    file_path: str = Field(index=True)
    name: str = Field(index=True)
    parent: str | None = None
    symbol_type: str
    signature: str
    start_line: int
    end_line: int
    docstring: str | None = None
    body_hash: str = Field(index=True)


class LedgerEntry(SQLModel, table=True):
    __tablename__ = "ledger_entry"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    step: int
    agent: str
    context_used: str
    tokens_estimated: int
    tokens_avoided: int = 0
    tokens_kept_compressed: int = 0
    tokens_kept_pinned: int = 0
    # Provider-reported usage (Anthropic / OpenAI shape). Always cumulative
    # for the step, never lifetime — adapters reset between steps.
    tokens_provider_input: int = 0
    tokens_cached_read: int = 0
    tokens_cached_write: int = 0
    tokens_provider_output: int = 0
    decision: str
    outcome: str
    outcome_class: str = Field(default="unknown", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SeenPacket(SQLModel, table=True):
    """Tracks which packet hashes a given task/agent has already received.

    Used by the compressor to emit lightweight ``symbol_ref`` packets in place
    of full ``symbol`` packets the agent has already seen this task.
    """
    __tablename__ = "seen_packet"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    packet_hash: str = Field(index=True)
    packet_type: str
    seen_at: datetime = Field(default_factory=datetime.utcnow)
