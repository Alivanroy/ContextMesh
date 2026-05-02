"""Cross-agent benchmark harness — the v0.4 scaffolding.

Runs a list of tasks against a list of agent adapters (using captured stream
fixtures by default; replace with real CLI invocations once authenticated)
and writes one JSON record per (task, agent) into ``benchmarks/results/``.

Each record includes the four-numbers-side-by-side view that anchors the
launch post: input / cache_read / cache_write / output / avoided.

Usage:
    python3 benchmarks/harness.py
    python3 benchmarks/harness.py --output benchmarks/results/2026-05-02.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contextmesh.adapters import get_adapter  # noqa: E402
from contextmesh.runtime.ledger import record_event  # noqa: E402
from contextmesh.runtime.metrics import task_metrics  # noqa: E402
from contextmesh.storage import db  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


@dataclass
class Task:
    task_id: str
    description: str
    expected_outcome: str  # "passed" | "regressed" — what the fixture should produce


@dataclass
class AgentSource:
    """One concrete way to populate the ledger for a task.

    ``runner`` returns an iterable of stream lines for a given task. The
    default implementation just reads a fixture file; override to spawn a
    real subprocess.
    """
    name: str          # agent label written to the ledger ("claude-code" / "aider")
    adapter_key: str   # registry key ("claude-code" or "aider")
    runner: Callable[[Task], list[str]]


def _fixture_runner(filename_for: Callable[[Task], str]) -> Callable[[Task], list[str]]:
    def runner(task: Task) -> list[str]:
        path = FIXTURES / filename_for(task)
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    return runner


def default_tasks() -> list[Task]:
    return [
        Task(
            task_id="reset-bug-failing",
            description="Diagnose the verify_reset_token failure (test still failing)",
            expected_outcome="regressed",
        ),
        Task(
            task_id="reset-bug-fixed",
            description="Patch verify_reset_token comparison; verify tests pass",
            expected_outcome="passed",
        ),
    ]


def default_agents() -> list[AgentSource]:
    """Two agents wired to fixtures so the harness runs without auth."""

    def claude_fixture(task: Task) -> str:
        if task.expected_outcome == "passed":
            return "claude_code_fixed_session.jsonl"
        return "claude_code_session.jsonl"

    def aider_fixture(task: Task) -> str:
        # We only have a passing fixture for Aider; reuse for both demo tasks.
        return "aider_session.md"

    return [
        AgentSource(name="claude-code", adapter_key="claude-code",
                    runner=_fixture_runner(claude_fixture)),
        AgentSource(name="aider", adapter_key="aider",
                    runner=_fixture_runner(aider_fixture)),
    ]


def _run_one(task: Task, source: AgentSource) -> dict:
    """Drive an adapter through *source*'s stream and snapshot metrics."""
    state = tempfile.mkdtemp(prefix=f"cm_bench_{source.name}_")
    os.environ["CONTEXTMESH_STATE_DIR"] = state
    db.reset_engine()
    db.create_db_and_tables()

    try:
        adapter_cls = get_adapter(source.adapter_key)
        adapter = adapter_cls(task_id=task.task_id, agent=source.name)
        for line in source.runner(task):
            for event in adapter.feed(line):
                record_event(event)
        for event in adapter.finalize():
            record_event(event)

        m = task_metrics(task.task_id)
        return {
            "task": {
                "id": task.task_id,
                "description": task.description,
                "expected_outcome": task.expected_outcome,
            },
            "agent": source.name,
            "metrics": m.as_dict(),
            "outcome_correctly_classified":
                m.final_outcome_class == task.expected_outcome,
        }
    finally:
        db.reset_engine()
        os.environ.pop("CONTEXTMESH_STATE_DIR", None)


def run(tasks: list[Task], agents: list[AgentSource]) -> dict:
    runs = [_run_one(task, agent) for task in tasks for agent in agents]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tasks": [t.__dict__ for t in tasks],
        "agents": [a.name for a in agents],
        "runs": runs,
    }


def render(report: dict, *, file=sys.stdout) -> None:
    print("=" * 96, file=file)
    print(f"ContextMesh benchmark — {report['generated_at']}", file=file)
    print("=" * 96, file=file)
    header = (
        f"{'Task':<26} {'Agent':<14} {'Outcome':<10} "
        f"{'Input':>7} {'CacheR':>7} {'CacheW':>7} {'Output':>7} {'Avoided':>8} {'Useful%':>8}"
    )
    print(header, file=file)
    print("-" * len(header), file=file)
    for r in report["runs"]:
        m = r["metrics"]
        useful = m["useful_context_ratio"] * 100
        marker = "  ✓" if r["outcome_correctly_classified"] else "  ✗"
        print(
            f"{r['task']['id']:<26} {r['agent']:<14} "
            f"{m['final_outcome_class']:<10} "
            f"{m['tokens_provider_input']:>7,} "
            f"{m['tokens_cached_read']:>7,} "
            f"{m['tokens_cached_write']:>7,} "
            f"{m['tokens_provider_output']:>7,} "
            f"{m['tokens_avoided']:>8,} "
            f"{useful:>7.1f}%{marker}",
            file=file,
        )
    print("-" * len(header), file=file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None,
                        help="Path to write JSON report (default: benchmarks/results/<date>.json)")
    args = parser.parse_args()

    tasks = default_tasks()
    agents = default_agents()
    report = run(tasks, agents)
    render(report)

    out_path = Path(args.output) if args.output else (
        ROOT / "benchmarks" / "results" / f"{datetime.now(timezone.utc).date()}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
