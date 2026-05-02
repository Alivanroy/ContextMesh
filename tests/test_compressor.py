from contextmesh.packets.compressor import compress_packets, reset_seen


def _symbol(name, body_hash):
    return {
        "type": "symbol",
        "name": name,
        "file": "src/x.py",
        "parent": None,
        "signature": f"def {name}(): ...",
        "summary": "...",
        "hash": body_hash,
        "raw_available": True,
    }


def test_first_seen_packets_pass_through():
    packets = [_symbol("foo", "h1"), _symbol("bar", "h2")]
    out = compress_packets("task-A", packets)
    assert all(p["type"] == "symbol" for p in out)


def test_second_run_emits_symbol_refs():
    packets = [_symbol("foo", "h1"), _symbol("bar", "h2")]
    compress_packets("task-B", packets)
    out = compress_packets("task-B", packets)
    assert all(p["type"] == "symbol_ref" for p in out)
    assert out[0]["hash"] == "h1"
    assert out[0]["name"] == "foo"


def test_seen_cache_is_per_task():
    packets = [_symbol("foo", "h1")]
    compress_packets("task-C", packets)
    out = compress_packets("task-D", packets)
    assert out[0]["type"] == "symbol"


def test_reset_seen_clears_cache():
    packets = [_symbol("foo", "h1")]
    compress_packets("task-E", packets)
    removed = reset_seen("task-E")
    assert removed == 1
    out = compress_packets("task-E", packets)
    assert out[0]["type"] == "symbol"
