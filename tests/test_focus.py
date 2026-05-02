from contextmesh.indexer.repo_indexer import reindex
from contextmesh.packets.compressor import compress_packets, reset_seen
from contextmesh.packets.focus import augment_with_failures, extract_failures, symbols_on_trace
from contextmesh.packets.generator import generate_symbol_packets


def _write_buggy(tmp_path):
    src = tmp_path / "reset.py"
    src.write_text(
        "import time\n"
        "\n"
        "def verify_reset_token(token):\n"
        "    \"\"\"Validates token expiry.\"\"\"\n"
        "    expires_at = time.time() - 100\n"
        "    if expires_at < time.time():\n"
        "        return False\n"
        "    return True\n"
    )
    return src


def test_symbols_on_trace_finds_containing_symbol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = _write_buggy(tmp_path)
    reindex(tmp_path)

    failure = {
        "type": "test_failure",
        "test": "test_valid_reset_token",
        "file": str(src.relative_to(tmp_path)),
        "line": 6,
        "assertion": "AssertionError: assert False == True",
        "minimal_trace": ">       assert verify_reset_token('x') == True",
    }
    found = symbols_on_trace(failure)
    names = {n for n, _, _ in found}
    assert "verify_reset_token" in names


def test_augment_inlines_body_and_pins_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = _write_buggy(tmp_path)
    reindex(tmp_path)
    sym_packets = [p.model_dump() for p in generate_symbol_packets(str(src))]
    assert sym_packets, "fixture should produce at least one symbol packet"

    failure = {
        "type": "test_failure",
        "test": "t",
        "file": str(src.relative_to(tmp_path)),
        "line": 6,
        "assertion": "expected True",
        "minimal_trace": ">   verify_reset_token('x')",
    }

    augmented, pinned = augment_with_failures(sym_packets, [failure])
    target = next(p for p in augmented if p["name"] == "verify_reset_token")
    assert target["pinned"] is True
    assert target["body"] is not None
    assert "expires_at < time.time()" in target["body"]
    assert target["hash"] in pinned


def test_pinned_symbols_survive_compression(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = _write_buggy(tmp_path)
    reindex(tmp_path)
    sym_packets = [p.model_dump() for p in generate_symbol_packets(str(src))]

    reset_seen("focus-task")
    # Turn 1: prime the seen-cache
    compress_packets("focus-task", list(sym_packets))
    # Turn 2 without focus: everything compresses to refs
    plain = compress_packets("focus-task", list(sym_packets), persist=False)
    assert all(p["type"] == "symbol_ref" for p in plain)

    # Turn 2 with focus: pinned symbol stays full
    failure = {
        "type": "test_failure", "test": "t",
        "file": str(src.relative_to(tmp_path)), "line": 6,
        "assertion": "x", "minimal_trace": "verify_reset_token",
    }
    augmented, pinned = augment_with_failures(sym_packets, [failure])
    focused = compress_packets("focus-task", augmented, persist=False, pinned_hashes=pinned)

    pinned_emitted = [p for p in focused if p.get("name") == "verify_reset_token"]
    assert len(pinned_emitted) == 1
    assert pinned_emitted[0]["type"] == "symbol"
    assert pinned_emitted[0]["pinned"] is True
    assert pinned_emitted[0]["body"] is not None


def test_extract_failures_handles_command_result():
    blob = {
        "type": "command_result",
        "command": "pytest",
        "status": "failed",
        "failures": [
            {"type": "test_failure", "test": "t1", "file": "x.py", "minimal_trace": "..."},
            {"type": "test_failure", "test": "t2", "file": "y.py", "minimal_trace": "..."},
        ],
    }
    out = extract_failures(blob)
    assert len(out) == 2
    assert out[0]["test"] == "t1"
