from pathlib import Path

from contextmesh.adapters import get_adapter
from contextmesh.adapters.codex_cli import CodexCliAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "codex_cli_session.jsonl"
FAILING_FIXTURE = Path(__file__).parent / "fixtures" / "codex_cli_failing_session.jsonl"


def _drive(adapter: CodexCliAdapter, text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines(keepends=True):
        out.extend(adapter.feed(line))
    out.extend(adapter.finalize())
    return out


def test_codex_cli_fixture_records_command_and_turn_usage():
    events = _drive(CodexCliAdapter("codex-task"), FIXTURE.read_text())

    assert len(events) == 2
    command, final = events
    assert command["decision"].startswith("command:")
    assert command["tokens_estimated"] == 0
    assert command["outcome_class"] == "passed"

    assert final["decision"] == "final"
    assert final["outcome_class"] == "passed"
    assert final["tokens_provider_input"] == 30653 - 21760
    assert final["tokens_cached_read"] == 21760
    assert final["tokens_provider_output"] == 61
    assert "thread:thread-codex-fixture" in final["context_refs"]


def test_codex_cli_failing_fixture_classifies_regression():
    events = _drive(CodexCliAdapter("codex-task"), FAILING_FIXTURE.read_text())

    assert events[-1]["outcome_class"] == "regressed"
    assert events[-1]["tokens_provider_input"] == 24832 - 8192
    assert events[-1]["tokens_cached_read"] == 8192


def test_codex_cli_ignores_non_json_lines():
    adapter = CodexCliAdapter("codex-task")
    assert adapter.feed("2026-05-16 WARN not json\n") == []
    assert adapter.feed("not json\n") == []


def test_codex_cli_missing_exit_code_does_not_default_to_success():
    adapter = CodexCliAdapter("codex-task")
    events = adapter.feed(
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"python broken.py","status":"failed"}}\n'
    )

    assert events[0]["outcome"] == "error"
    assert events[0]["outcome_class"] == "unknown"


def test_codex_cli_completed_command_without_exit_code_is_unknown():
    adapter = CodexCliAdapter("codex-task")
    events = adapter.feed(
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"python maybe.py","status":"completed"}}\n'
    )

    assert events[0]["outcome"] == "unknown"
    assert events[0]["outcome_class"] == "unknown"


def test_codex_cli_tolerates_malformed_usage_fields():
    events = _drive(
        CodexCliAdapter("codex-task"),
        '{"type":"turn.completed","usage":{'
        '"input_tokens":"not-a-number",'
        '"cached_input_tokens":null,'
        '"output_tokens":"2"'
        "}}\n",
    )

    assert events[-1]["tokens_provider_input"] == 0
    assert events[-1]["tokens_cached_read"] == 0
    assert events[-1]["tokens_provider_output"] == 2


def test_adapter_registry_exposes_codex_cli_aliases():
    assert get_adapter("codex-cli") is CodexCliAdapter
    assert get_adapter("codex") is CodexCliAdapter
