import json
from pathlib import Path

from contextmesh.adapters.claude_code import ClaudeCodeAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_session.jsonl"


def _drive(adapter: ClaudeCodeAdapter, lines: list[str]) -> list[dict]:
    out: list[dict] = []
    for line in lines:
        out.extend(adapter.feed(line))
    out.extend(adapter.finalize())
    return out


def test_blank_and_garbage_lines_are_dropped():
    adapter = ClaudeCodeAdapter("t", agent="claude")
    assert adapter.feed("") == []
    assert adapter.feed("not json\n") == []
    assert adapter.feed('"a string, not a dict"\n') == []


def test_assistant_event_yields_one_step_with_usage():
    adapter = ClaudeCodeAdapter("t", agent="claude")
    line = (
        '{"type":"assistant","message":{"content":['
        '{"type":"text","text":"Reading."},'
        '{"type":"tool_use","id":"tu_1","name":"Read","input":{"file_path":"x.py"}}'
        '],"usage":{"input_tokens":100,"cache_read_input_tokens":50,"output_tokens":10}}}'
    )
    events = adapter.feed(line)
    assert len(events) == 1
    e = events[0]
    assert e["step"] == 1
    assert e["agent"] == "claude"
    assert "Read(x.py)" in e["context_refs"]
    assert "tool_use:tu_1" in e["context_refs"]
    assert "file:x.py" in e["context_refs"]
    assert any(ref.startswith("prompt_block:assistant:") for ref in e["context_refs"])
    assert e["tokens_provider_input"] == 100
    assert e["tokens_cached_read"] == 50
    assert e["tokens_provider_output"] == 10
    assert e["outcome_class"] == "unknown"


def test_pytest_tool_result_emits_avoidance_step():
    adapter = ClaudeCodeAdapter("t", agent="claude")
    pytest_blob = (
        "============================= test session starts ==============================\n"
        + "x" * 2000
        + "\nFAILED tests/foo.py::test_x - AssertionError\n"
        + "============================== 1 failed in 0.05s ===============================\n"
    )
    line = json.dumps({
        "type": "user",
        "message": {"content": [{
            "type": "tool_result", "tool_use_id": "tu_1", "content": pytest_blob,
        }]},
    })
    events = adapter.feed(line)
    assert len(events) == 1
    assert events[0]["tokens_avoided"] > 0
    assert "tool_result:pytest" in events[0]["context_refs"]
    assert "tool_result:tu_1" in events[0]["context_refs"]
    assert any(ref.startswith("tool_output:pytest:") for ref in events[0]["context_refs"])
    assert any(
        ref.startswith("generated_packet:command_result:")
        for ref in events[0]["context_refs"]
    )


def test_non_pytest_tool_result_is_silent():
    adapter = ClaudeCodeAdapter("t")
    line = (
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"x",'
        '"content":"File edited successfully."}]}}'
    )
    assert adapter.feed(line) == []


def test_result_event_emits_final_step():
    adapter = ClaudeCodeAdapter("t")
    line = (
        '{"type":"result","subtype":"success","is_error":false,'
        '"result":"done","usage":{"input_tokens":4000,"cache_read_input_tokens":3000,'
        '"cache_creation_input_tokens":1000,"output_tokens":200}}'
    )
    events = adapter.feed(line)
    assert len(events) == 1
    e = events[0]
    assert e["decision"] == "final"
    assert e["outcome"] == "ok"
    assert any(ref.startswith("prompt_block:result:") for ref in e["context_refs"])
    assert e["tokens_cached_read"] == 3000
    assert e["tokens_cached_write"] == 1000


def test_result_event_with_error_marks_aborted():
    adapter = ClaudeCodeAdapter("t")
    line = '{"type":"result","is_error":true,"result":"oops","usage":{"input_tokens":10,"output_tokens":1}}'
    events = adapter.feed(line)
    assert events[0]["outcome_class"] == "aborted"
    assert events[0]["outcome"] == "error"


def test_full_fixture_parses_into_a_realistic_step_count():
    adapter = ClaudeCodeAdapter("reset-bug", agent="claude")
    events = _drive(adapter, FIXTURE.read_text().splitlines())
    # 3 assistant turns + 1 pytest distill + 1 result = 5 events
    assert len(events) == 5
    final = events[-1]
    assert final["decision"] == "final"
    assert final["tokens_provider_input"] == 3700
    assert final["tokens_cached_read"] == 9120
    # Final pytest output had FAILED → adapter classifies as regressed
    assert final["outcome_class"] == "regressed"
    # The pytest step should have credited some avoidance
    avoidance_steps = [e for e in events if e.get("tokens_avoided", 0) > 0]
    assert len(avoidance_steps) == 1


def test_passing_fixture_classifies_as_passed():
    fixture = Path(__file__).parent / "fixtures" / "claude_code_fixed_session.jsonl"
    adapter = ClaudeCodeAdapter("fixed", agent="claude")
    events = _drive(adapter, fixture.read_text().splitlines())
    final = events[-1]
    assert final["decision"] == "final"
    assert final["outcome_class"] == "passed"


def test_real_auth_failure_fixture_marks_aborted():
    fixture = Path(__file__).parent / "fixtures" / "claude_code_real_auth_failure.jsonl"
    adapter = ClaudeCodeAdapter("real", agent="claude")
    events = _drive(adapter, fixture.read_text().splitlines())
    final = events[-1]
    assert final["outcome_class"] == "aborted"
    assert final["outcome"] == "error"
