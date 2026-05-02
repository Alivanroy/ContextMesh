from contextmesh.runtime.ledger import record_step
from contextmesh.runtime.metrics import (
    all_task_metrics,
    find_repeat_waste,
    global_metrics,
    task_metrics,
)


def _step(task_id, step, *, billed_text="x" * 4, kept_compressed=0, kept_pinned=0, outcome_class="unknown"):
    return record_step(
        task_id=task_id,
        step=step,
        agent="t",
        context_refs=[],
        context_text=billed_text,
        decision="d",
        outcome="ok",
        outcome_class=outcome_class,
        tokens_kept_compressed=kept_compressed,
        tokens_kept_pinned=kept_pinned,
    )


def test_task_metrics_passed_yields_full_ratio():
    _step("T1", 1, kept_compressed=10, kept_pinned=5, outcome_class="passed")
    m = task_metrics("T1")
    assert m.steps == 1
    assert m.final_outcome_class == "passed"
    assert m.useful_context_ratio == 1.0
    assert m.tokens_avoided == 15  # max(0, 10+5)
    assert m.tokens_kept_compressed == 10
    assert m.tokens_kept_pinned == 5


def test_task_metrics_failed_yields_zero_ratio():
    _step("T2", 1, billed_text="x" * 100, outcome_class="regressed")
    m = task_metrics("T2")
    assert m.useful_context_ratio == 0.0
    assert m.tokens_billed > 0


def test_task_metrics_only_uses_final_step_outcome():
    _step("T3", 1, outcome_class="passed")
    _step("T3", 2, outcome_class="aborted")
    m = task_metrics("T3")
    assert m.final_outcome_class == "aborted"
    assert m.useful_context_ratio == 0.0


def test_global_metrics_token_weighted():
    _step("big", 1, billed_text="x" * 800, outcome_class="passed")
    _step("tiny", 1, billed_text="x" * 4, outcome_class="aborted")
    g = global_metrics()
    assert g.tasks == 2
    # Most billed tokens went to a passed task → ratio close to 1
    assert g.aggregate_useful_context_ratio > 0.95
    assert g.by_outcome["passed"] == 1
    assert g.by_outcome["aborted"] == 1


def test_all_task_metrics_lists_each_task_once():
    _step("a", 1, outcome_class="passed")
    _step("a", 2, outcome_class="passed")
    _step("b", 1, outcome_class="passed")
    metrics = {m.task_id: m for m in all_task_metrics()}
    assert set(metrics.keys()) == {"a", "b"}
    assert metrics["a"].steps == 2


def test_provider_tokens_aggregate_per_task_and_global():
    from contextmesh.runtime.ledger import record_event
    from contextmesh.runtime.metrics import global_metrics, task_metrics

    record_event({
        "task_id": "P1", "step": 1, "agent": "claude",
        "context_text": "x" * 40, "decision": "d", "outcome": "ok",
        "outcome_class": "passed",
        "tokens_provider_input": 1000,
        "tokens_cached_read": 4000,
        "tokens_cached_write": 200,
        "tokens_provider_output": 50,
    })
    m = task_metrics("P1")
    assert m.has_provider_tokens
    assert m.tokens_provider_input == 1000
    assert m.tokens_cached_read == 4000
    assert m.tokens_cached_write == 200
    assert m.tokens_provider_output == 50
    # cache_hit_rate = 4000 / (1000 + 4000 + 200)
    assert abs(m.cache_hit_rate - 4000 / 5200) < 1e-6

    g = global_metrics()
    assert g.has_provider_tokens
    assert g.tokens_cached_read >= 4000
    assert g.aggregate_cache_hit_rate > 0


def test_find_repeat_waste_flags_cross_task_hashes():
    from contextmesh.packets.compressor import compress_packets

    pkt = lambda h: {
        "type": "symbol", "name": "x", "file": "f.py", "parent": None,
        "signature": "def x()", "summary": "", "hash": h,
    }
    for tid in ["t1", "t2", "t3", "t4", "t5"]:
        compress_packets(tid, [pkt("shared")])

    waste = find_repeat_waste(threshold=3)
    assert any(w.packet_hash == "shared" for w in waste)
    record = next(w for w in waste if w.packet_hash == "shared")
    assert record.times_sent == 5
    assert record.wasted_tokens > 0
