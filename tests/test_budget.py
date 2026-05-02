from contextmesh.runtime.budget import apply_budget


def test_apply_budget_keeps_high_priority():
    packets = [
        {"type": "task", "goal": "x"},
        {"type": "test_failure", "test": "t", "file": "f.py", "minimal_trace": "..."},
        {"type": "symbol_ref", "hash": "h1"},
        {"type": "symbol_ref", "hash": "h2"},
    ]
    result = apply_budget(packets, max_tokens=20)
    types = [p["type"] for p in result.packets]
    assert "task" in types
    assert result.tokens_used <= 20


def test_apply_budget_drops_when_over_cap():
    packets = [{"type": "symbol", "name": str(i), "file": "x", "signature": "def x()", "summary": "...", "hash": str(i)} for i in range(20)]
    result = apply_budget(packets, max_tokens=30)
    assert result.dropped_count > 0
    assert result.tokens_dropped > 0
