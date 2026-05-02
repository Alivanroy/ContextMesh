import os

from contextmesh.packets.generator import (
    generate_file_summary,
    generate_repo_summary,
    generate_symbol_packets,
)
from contextmesh.packets.schema import FileSummaryPacket, RepoSummaryPacket, SymbolPacket


def test_generate_repo_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.py").write_text("def f(): pass\n")
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")

    summary = generate_repo_summary(str(tmp_path))
    assert isinstance(summary, RepoSummaryPacket)
    assert summary.files_indexed == 2
    assert summary.symbols_indexed == 2


def test_generate_file_summary(tmp_path):
    f = tmp_path / "script.py"
    f.write_text("print('hello')\nprint('world')")

    summary = generate_file_summary(str(f))
    assert isinstance(summary, FileSummaryPacket)
    assert summary.language == "python"
    assert summary.line_count == 2


def test_generate_symbol_packets(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('"""Doc"""\ndef calc(n: int) -> int:\n    """Calculates square"""\n    return n * n\n')

    packets = generate_symbol_packets(str(f))
    assert len(packets) == 1
    assert isinstance(packets[0], SymbolPacket)
    assert packets[0].name == "calc"
    assert packets[0].signature == "def calc(n: int) -> int"
    assert packets[0].summary == '"""Calculates square"""'
    assert len(packets[0].hash) == 16
