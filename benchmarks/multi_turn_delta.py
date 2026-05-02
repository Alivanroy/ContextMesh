"""Real-life scenario: a 3-turn coding task on the ContextMesh repo.

Turn 1 — agent sees the full packet bundle for the task.
Turn 2 — agent comes back to the same task; ContextMesh sends symbol_refs
         instead of full symbol packets it has already shown.
Turn 3 — same again, plus a brand-new failing test.

Prints tokens spent per turn and the cumulative savings.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contextmesh.indexer.repo_indexer import reindex
from contextmesh.packets.compressor import compress_packets, reset_seen
from contextmesh.packets.generator import generate_repo_summary, generate_symbol_packets
from contextmesh.packets.markdown import render_markdown
from contextmesh.packets.schema import TaskPacket, TestFailurePacket

ENC = tiktoken.get_encoding("cl100k_base")
TASK = "Refactor verify_reset_token to use a TokenStore"
TASK_ID = "multi-turn-demo"


def tokens(text: str) -> int:
    return len(ENC.encode(text))


def gather_packets(scope: Path) -> list[dict]:
    pkts: list[dict] = [TaskPacket(
        goal=TASK,
        constraints=["use existing tests", "avoid raw file reads"],
    ).model_dump()]
    pkts.append(generate_repo_summary(scope).model_dump())
    for py in sorted(scope.rglob("*.py")):
        if any(part in {"__pycache__", ".contextmesh"} for part in py.parts):
            continue
        for sp in generate_symbol_packets(py):
            pkts.append(sp.model_dump())
    return pkts


def render(turn: int, label: str, packets: list[dict]) -> int:
    body = render_markdown(packets, task=f"{TASK} (turn {turn} — {label})")
    n = tokens(body)
    Path(f"benchmarks/_turn_{turn}.md").write_text(body, encoding="utf-8")
    return n


def main() -> None:
    state = tempfile.mkdtemp(prefix="cm_multi_")
    os.environ["CONTEXTMESH_STATE_DIR"] = state
    os.chdir(ROOT)

    reset_seen(TASK_ID)
    reindex(ROOT / "contextmesh")
    base_packets = gather_packets(ROOT / "contextmesh")
    print(f"Total raw packets generated each turn : {len(base_packets)}")

    # Turn 1 — first time the agent sees this task
    t1_packets = compress_packets(TASK_ID, list(base_packets))
    t1 = render(1, "first sight", t1_packets)

    # Turn 2 — same task, agent comes back; everything seen → symbol_refs
    t2_packets = compress_packets(TASK_ID, list(base_packets))
    t2 = render(2, "delta only", t2_packets)

    # Turn 3 — same task + a brand-new failing test
    t3_input = list(base_packets) + [TestFailurePacket(
        test="test_token_store_used",
        file="tests/auth/test_token_store.py",
        line=17,
        assertion="AssertionError: TokenStore was not used",
        minimal_trace=">       assert store.was_used()\nE       AssertionError: TokenStore was not used",
    ).model_dump()]
    t3_packets = compress_packets(TASK_ID, t3_input)
    t3 = render(3, "delta + new failure", t3_packets)

    raw_per_turn = tokens(render_markdown(base_packets, task=TASK))

    print()
    print(f"{'Turn':<6}{'Strategy':<30}{'Packets sent':>15}{'Tokens':>10}")
    print("-" * 61)
    print(f"{'raw':<6}{'no compression':<30}{len(base_packets):>15}{raw_per_turn:>10}")
    print(f"{'1':<6}{'first turn (full)':<30}{len(t1_packets):>15}{t1:>10}")
    print(f"{'2':<6}{'delta (symbol_refs)':<30}{len(t2_packets):>15}{t2:>10}")
    print(f"{'3':<6}{'delta + new evidence':<30}{len(t3_packets):>15}{t3:>10}")

    raw_3turns = raw_per_turn * 3
    mesh_3turns = t1 + t2 + t3
    saved = (raw_3turns - mesh_3turns) / raw_3turns * 100
    print()
    print(f"Raw 3-turn cost            : {raw_3turns:>6} tokens")
    print(f"ContextMesh 3-turn cost    : {mesh_3turns:>6} tokens")
    print(f"Savings                    : {raw_3turns - mesh_3turns:>6} tokens ({saved:.1f}%)")

    # Cleanup
    for p in Path("benchmarks").glob("_turn_*.md"):
        p.unlink()
    shutil.rmtree(state, ignore_errors=True)


if __name__ == "__main__":
    main()
