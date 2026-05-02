"""Terminal dashboard for the ContextMesh ledger.

The dashboard is the front door for v0.2. It answers three questions:

  1. **How much did I spend on each task, and what fraction was useful?**
     (useful_context_ratio per task — the metric defined in metrics.py)
  2. **Where is the agent re-receiving the same context?**
     (the "biggest waste" view, via find_repeat_waste)
  3. **Which steps spent the most?**
     (per-task timeline of billed vs avoided tokens)
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from contextmesh.indexer.repo_indexer import list_files, list_symbols
from contextmesh.runtime.ledger import get_ledger
from contextmesh.runtime.metrics import (
    all_task_metrics,
    find_repeat_waste,
    global_metrics,
)

_OUTCOME_COLORS = {
    "passed": "green",
    "unchanged": "yellow",
    "regressed": "red",
    "aborted": "red",
    "unknown": "dim",
}


def _ratio_pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _bar(value: int, total: int, width: int = 12) -> str:
    if total <= 0:
        return " " * width
    filled = max(0, min(width, round(value / total * width)))
    return "█" * filled + "░" * (width - filled)


def render_overview(console: Console) -> None:
    files = list_files()
    symbols = list_symbols()
    g = global_metrics()

    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="right")
    table.add_row("Files indexed", f"{len(files):,}")
    table.add_row("Symbols indexed", f"{len(symbols):,}")
    table.add_row("Tasks tracked", f"{g.tasks:,}")
    table.add_row("Tokens billed (estimated)", f"{g.tokens_billed:,}")
    table.add_row("Tokens avoided", f"{g.tokens_avoided:,}")
    table.add_row("  via delta compression", f"{g.tokens_kept_compressed:,}")
    table.add_row("  via critical-path focus", f"{g.tokens_kept_pinned:,}")
    if g.has_provider_tokens:
        table.add_row("", "")
        table.add_row("Provider input tokens", f"{g.tokens_provider_input:,}")
        table.add_row("Provider output tokens", f"{g.tokens_provider_output:,}")
        table.add_row("  cache reads (cheap)", f"[green]{g.tokens_cached_read:,}[/green]")
        table.add_row("  cache writes (1.25×)", f"[yellow]{g.tokens_cached_write:,}[/yellow]")
        table.add_row(
            "Cache hit rate",
            f"[bold]{_ratio_pct(g.aggregate_cache_hit_rate)}[/bold]",
        )
    table.add_row(
        "Avoidance ratio",
        f"[bold]{_ratio_pct(g.aggregate_avoidance_ratio)}[/bold]",
    )
    table.add_row(
        "Useful-context ratio",
        f"[bold cyan]{_ratio_pct(g.aggregate_useful_context_ratio)}[/bold cyan]",
    )
    if g.by_outcome:
        outcomes = "  ".join(
            f"[{_OUTCOME_COLORS.get(k, 'white')}]{k}[/]={v}"
            for k, v in sorted(g.by_outcome.items(), key=lambda kv: -kv[1])
        )
        table.add_row("Outcomes", outcomes)
    console.print(Panel(table, title="ContextMesh", subtitle="local observability"))


def render_per_task(console: Console) -> None:
    metrics = sorted(
        all_task_metrics(),
        key=lambda m: (-m.tokens_billed, m.task_id),
    )
    if not metrics:
        console.print("[dim]No tasks recorded yet. Run `contextmesh ledger record ...`.[/dim]")
        return

    table = Table(title="Tasks (sorted by billed tokens)")
    table.add_column("Task", style="cyan")
    table.add_column("Steps", justify="right")
    table.add_column("Outcome")
    table.add_column("Billed", justify="right")
    table.add_column("Avoided", justify="right", style="green")
    table.add_column("Compressed", justify="right")
    table.add_column("Pinned", justify="right")
    table.add_column("Useful", justify="right")

    for m in metrics:
        color = _OUTCOME_COLORS.get(m.final_outcome_class, "white")
        table.add_row(
            m.task_id,
            str(m.steps),
            f"[{color}]{m.final_outcome_class}[/]",
            f"{m.tokens_billed:,}",
            f"{m.tokens_avoided:,}",
            f"{m.tokens_kept_compressed:,}",
            f"{m.tokens_kept_pinned:,}",
            f"[bold]{_ratio_pct(m.useful_context_ratio)}[/bold]",
        )
    console.print(table)


def render_timeline(console: Console, limit: int = 25) -> None:
    """Show recent ledger entries as a billed/avoided bar chart."""
    entries = get_ledger(limit=limit)
    if not entries:
        return
    entries = list(reversed(entries))
    max_total = max((e.tokens_estimated + e.tokens_avoided) for e in entries) or 1

    table = Table(title=f"Recent steps (last {len(entries)})")
    table.add_column("Task", style="cyan")
    table.add_column("Step", justify="right")
    table.add_column("Agent")
    table.add_column("Outcome")
    table.add_column("Billed", justify="right")
    table.add_column("Avoided", justify="right", style="green")
    table.add_column("                 ", style="dim")

    for e in entries:
        billed_bar = _bar(e.tokens_estimated, max_total, width=8)
        avoided_bar = _bar(e.tokens_avoided, max_total, width=8)
        color = _OUTCOME_COLORS.get(e.outcome_class, "white")
        table.add_row(
            e.task_id,
            str(e.step),
            e.agent,
            f"[{color}]{e.outcome_class}[/]",
            f"{e.tokens_estimated:,}",
            f"{e.tokens_avoided:,}",
            f"[red]{billed_bar}[/]  [green]{avoided_bar}[/]",
        )
    console.print(table)


def render_provider_tokens(console: Console) -> None:
    """Per-task breakdown of provider-reported usage. Silent unless data exists."""
    metrics = [m for m in all_task_metrics() if m.has_provider_tokens]
    if not metrics:
        return
    metrics.sort(key=lambda m: -m.tokens_provider_input)

    table = Table(
        title="Provider tokens per task",
        caption=(
            "Input = full price · Cache R = 0.1× · Cache W = 1.25× · "
            "Avoided = ContextMesh on top"
        ),
    )
    table.add_column("Task", style="cyan")
    table.add_column("Outcome")
    table.add_column("Input", justify="right")
    table.add_column("Cache R", justify="right", style="green")
    table.add_column("Cache W", justify="right", style="yellow")
    table.add_column("Output", justify="right")
    table.add_column("Avoided", justify="right", style="green")
    table.add_column("Cache hit", justify="right")

    for m in metrics:
        color = _OUTCOME_COLORS.get(m.final_outcome_class, "white")
        table.add_row(
            m.task_id,
            f"[{color}]{m.final_outcome_class}[/]",
            f"{m.tokens_provider_input:,}",
            f"{m.tokens_cached_read:,}",
            f"{m.tokens_cached_write:,}",
            f"{m.tokens_provider_output:,}",
            f"{m.tokens_avoided:,}",
            _ratio_pct(m.cache_hit_rate),
        )
    console.print(table)


def render_waste(console: Console, threshold: int = 3) -> None:
    """Surface packet hashes hit by more than `threshold` distinct tasks."""
    waste = find_repeat_waste(threshold=threshold)
    if not waste:
        return
    table = Table(
        title=f"Repeat waste (hashes seen by > {threshold} tasks)",
        caption="Suggests inconsistent --task-id usage; consider a per-project cache.",
    )
    table.add_column("Packet hash", style="dim")
    table.add_column("Tasks", justify="right")
    table.add_column("~ tokens / send", justify="right")
    table.add_column("~ wasted", justify="right", style="red")
    for w in waste[:10]:
        table.add_row(
            w.packet_hash[:12],
            str(w.times_sent),
            str(w.estimated_tokens_per_send),
            f"{w.wasted_tokens:,}",
        )
    console.print(table)


def render_dashboard(console: Console | None = None) -> None:
    """Render every panel in order. Used by ``contextmesh dashboard``."""
    console = console or Console()
    render_overview(console)
    render_per_task(console)
    render_provider_tokens(console)
    render_timeline(console)
    render_waste(console)
