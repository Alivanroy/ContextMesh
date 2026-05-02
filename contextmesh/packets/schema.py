"""Pydantic schemas for context packets and intermediate types."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

PacketTrust = Literal["trusted", "untrusted", "generated"]


class EvidenceRef(BaseModel):
    ref_type: Literal["file", "symbol", "test", "cli_output", "doc"]
    path: str
    start_line: int | None = None
    end_line: int | None = None
    hash: str | None = None


class ContextPacket(BaseModel):
    packet_id: str
    packet_type: str
    summary: str
    evidence: list[EvidenceRef] = []
    confidence: float = 1.0
    raw_available: bool = True
    token_estimate: int | None = None
    trust_level: PacketTrust = "trusted"


class ExtractedImport(BaseModel):
    statement: str
    module: str | None = None
    names: list[str] = []
    line: int


class ExtractedSymbol(BaseModel):
    symbol_type: Literal["class", "function", "method"]
    name: str
    signature: str
    start_line: int
    end_line: int
    docstring: str | None = None
    parent: str | None = None


class TaskPacket(BaseModel):
    type: Literal["task"] = "task"
    goal: str
    constraints: list[str] = []


class RepoSummaryPacket(BaseModel):
    type: Literal["repo_summary"] = "repo_summary"
    languages: list[str] = []
    frameworks: list[str] = []
    files_indexed: int
    symbols_indexed: int = 0


class FileSummaryPacket(BaseModel):
    type: Literal["file_summary"] = "file_summary"
    file: str
    language: str
    size: int
    line_count: int
    hash: str


class SymbolPacket(BaseModel):
    type: Literal["symbol"] = "symbol"
    name: str
    file: str
    parent: str | None = None
    signature: str
    summary: str | None = None
    hash: str
    raw_available: bool = True
    body: str | None = None
    pinned: bool = False


class SymbolRefPacket(BaseModel):
    """Lightweight reference for symbols already seen in the current task."""
    type: Literal["symbol_ref"] = "symbol_ref"
    hash: str
    name: str | None = None
    file: str | None = None


class TestFailurePacket(BaseModel):
    type: Literal["test_failure"] = "test_failure"
    test: str
    file: str
    line: int | None = None
    assertion: str | None = None
    minimal_trace: str


class CommandResultPacket(BaseModel):
    type: Literal["command_result"] = "command_result"
    command: str
    status: Literal["success", "failed"]
    failures: list[TestFailurePacket] = []
    new_failures_since_last_run: int = 0
    fixed_failures_since_last_run: int = 0
    truncated_output_tail: str | None = None


class UncertaintyPacket(BaseModel):
    type: Literal["uncertainty"] = "uncertainty"
    value: str


class NextContextPacket(BaseModel):
    type: Literal["next_context"] = "next_context"
    items: list[str] = []
