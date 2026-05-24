from pathlib import Path

from contextmesh.adapters.aider import AiderAdapter, _parse_count

FIXTURE = Path(__file__).parent / "fixtures" / "aider_session.md"


def _drive(adapter: AiderAdapter, text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines(keepends=True):
        out.extend(adapter.feed(line))
    out.extend(adapter.finalize())
    return out


def test_parse_count_handles_k_and_commas():
    assert _parse_count("4.2k") == 4_200
    assert _parse_count("1,234") == 1_234
    assert _parse_count("12k") == 12_000
    assert _parse_count("0.5m") == 500_000
    assert _parse_count("garbage") == 0


def test_user_marker_opens_a_turn():
    adapter = AiderAdapter("t")
    assert adapter.feed("# aider chat started at 2026\n") == []
    # Header before first #### is dropped
    assert adapter.feed("blah\n") == []
    # First ####
    assert adapter.feed("#### do the thing\n") == []
    events = adapter.finalize()
    assert len(events) == 1
    assert events[0]["context_text"] == "do the thing"
    assert any(ref.startswith("prompt_block:user:") for ref in events[0]["context_refs"])


def test_cost_line_is_captured():
    adapter = AiderAdapter("t")
    adapter.feed("#### prompt\n")
    adapter.feed("some response\n")
    adapter.feed("Tokens: 4.2k sent, 320 received. Cost: $0.013 message, $0.013 session.\n")
    events = adapter.finalize()
    assert events[0]["tokens_provider_input"] == 4_200
    assert events[0]["tokens_provider_output"] == 320


def test_pytest_in_blockquote_classifies_outcome():
    adapter = AiderAdapter("t")
    adapter.feed("#### run tests\n")
    adapter.feed("> ============================= test session starts ===============\n")
    adapter.feed("> tests/foo.py .                                              [100%]\n")
    adapter.feed("> ============================== 1 passed in 0.04s ============\n")
    adapter.feed("Tokens: 1.1k sent, 24 received. Cost: $0.001 message, $0.001 session.\n")
    events = adapter.finalize()
    assert events[-1]["outcome_class"] == "passed"
    assert "tool_output:pytest" in events[-1]["context_refs"]
    assert any(ref.startswith("tool_output:pytest:") for ref in events[-1]["context_refs"])
    assert any(
        ref.startswith("generated_packet:command_result:")
        for ref in events[-1]["context_refs"]
    )


def test_full_aider_fixture():
    adapter = AiderAdapter("reset-bug", agent="aider")
    events = _drive(adapter, FIXTURE.read_text())

    assert len(events) == 2
    first, second = events
    assert first["context_text"].startswith("Fix the failing reset token test")
    assert first["tokens_provider_input"] == 4_200
    assert first["tokens_provider_output"] == 320

    assert second["decision"] == "final"
    assert second["outcome_class"] == "passed"
    assert second["tokens_provider_input"] == 1_100
    assert second["tokens_provider_output"] == 24


def test_adapter_registry_exposes_aider():
    from contextmesh.adapters import get_adapter

    cls = get_adapter("aider")
    assert cls.__name__ == "AiderAdapter"


def test_real_aider_session_with_blockquoted_cost_line():
    """Regression: real Aider emits ``> Tokens: …`` inside a blockquote, not
    as a plain line. The synthetic fixture had it un-quoted; the real one
    surfaced the bug."""
    fixture = Path(__file__).parent / "fixtures" / "aider_real_llama3.md"
    if not fixture.exists():
        return  # fixture optional
    adapter = AiderAdapter("real-aider", agent="aider")
    events = _drive(adapter, fixture.read_text())

    assert len(events) >= 1
    edit_event = events[0]
    # Real run: "Tokens: 989 sent, 136 received." in a > blockquote
    assert edit_event["tokens_provider_input"] >= 800
    assert edit_event["tokens_provider_output"] >= 100
    # Final pytest passed → outcome auto-classified
    final = events[-1]
    if "passed" in fixture.read_text().lower():
        assert final["outcome_class"] == "passed"
