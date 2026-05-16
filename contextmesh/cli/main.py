"""ContextMesh command-line interface."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    add_completion=False,
    help="ContextMesh — typed, evidence-backed context packets for AI coding agents.",
)
console = Console()


@app.command()
def init():
    """Initialize ContextMesh state in the current directory."""
    from contextmesh.config import DIR_NAME, env_state_dir, load_config
    from contextmesh.storage.db import create_db_and_tables

    override_state = env_state_dir()
    if override_state:
        create_db_and_tables()
        console.print(f"[green]ContextMesh initialized.[/green] State at [bold]{override_state}[/bold]")
        console.print("[dim]Using CONTEXTMESH_STATE_DIR override; project .gitignore unchanged.[/dim]")
        return

    config = load_config(create=True)
    create_db_and_tables()
    console.print(f"[green]ContextMesh initialized.[/green] State at [bold]{config.state_dir}[/bold]")
    gitignore = config.project_root / ".gitignore"
    line = f"\n{DIR_NAME}/\n"
    if gitignore.exists():
        if DIR_NAME not in gitignore.read_text(encoding="utf-8", errors="ignore"):
            with gitignore.open("a", encoding="utf-8") as f:
                f.write(line)
            console.print(f"[dim]Appended {DIR_NAME}/ to .gitignore[/dim]")
    else:
        gitignore.write_text(line.lstrip(), encoding="utf-8")
        console.print(f"[dim]Created .gitignore with {DIR_NAME}/ entry[/dim]")


@app.command()
def index(
    path: str = typer.Argument(".", help="Path to scan (relative to project root)"),
    json_output: bool = typer.Option(False, "--json", help="Emit stats as JSON"),
):
    """Index the codebase, persisting hashes and symbols for delta-aware reuse."""
    from contextmesh.indexer.repo_indexer import reindex

    stats = reindex(path)
    if json_output:
        console.print(json.dumps(stats.as_dict()))
        return
    console.print(
        f"[green]Indexed[/green] {stats.scanned} files "
        f"([cyan]{stats.new}[/cyan] new, "
        f"[cyan]{stats.changed}[/cyan] changed, "
        f"[dim]{stats.unchanged}[/dim] unchanged, "
        f"[red]{stats.removed}[/red] removed) — "
        f"{stats.symbols} symbols extracted."
    )


@app.command()
def summary():
    """Print a one-shot repo summary packet."""
    from contextmesh.config import load_config
    from contextmesh.packets.generator import generate_repo_summary

    repo = generate_repo_summary(load_config().project_root)
    console.print_json(repo.model_dump_json())


@app.command()
def packet(path: str = typer.Argument(..., help="File to generate packets for")):
    """Generate context packets for a single file (file_summary + symbols)."""
    from contextmesh.packets.generator import generate_file_summary, generate_symbol_packets

    try:
        console.print(generate_file_summary(path).model_dump_json())
    except Exception as exc:
        console.print(f"[red]error generating file_summary for {path}: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    for sp in generate_symbol_packets(path):
        console.print(sp.model_dump_json())


@app.command(name="run")
def run_command(
    command: list[str] = typer.Argument(..., help="Command to run and distill"),
    raw: bool = typer.Option(False, "--raw", help="Also print raw output"),
    timeout: int | None = typer.Option(None, "--timeout", help="Seconds before killing"),
):
    """Run a shell command and emit a compressed CommandResultPacket."""
    from contextmesh.wrappers.shell_runner import run_shell_command
    from contextmesh.wrappers.test_runner import distill_command_output

    exit_code, output = run_shell_command(command, timeout=timeout)
    if raw:
        sys.stderr.write(output)
    packet = distill_command_output(command, exit_code, output)
    console.print(packet.model_dump_json())
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command(name="export-context")
def export_context(
    task: str = typer.Option(..., "--task", help="Task description"),
    path: str = typer.Option(".", "--path", help="Path to scan"),
    format: str = typer.Option("markdown", "--format", help="markdown | jsonl"),
    out: str | None = typer.Option(None, "--out", help="Write to file instead of stdout"),
    budget: int | None = typer.Option(None, "--budget", help="Cap output to N estimated tokens"),
    no_compress: bool = typer.Option(False, "--no-compress", help="Skip delta compression"),
    task_id: str = typer.Option("default", "--task-id", help="Task id for delta cache"),
    failures: str | None = typer.Option(
        None,
        "--failures",
        help="JSONL file containing test_failure or command_result packets; "
             "their referenced symbols are inlined and pinned for this turn.",
    ),
):
    """Export typed context packets for an LLM agent."""
    from contextmesh.indexer.repo_indexer import iter_indexed_python_files, reindex
    from contextmesh.packets.compressor import compress_packets
    from contextmesh.packets.focus import augment_with_failures, extract_failures
    from contextmesh.packets.generator import generate_repo_summary, generate_symbol_packets
    from contextmesh.packets.markdown import render_markdown
    from contextmesh.packets.schema import TaskPacket
    from contextmesh.runtime.budget import apply_budget

    reindex(path)

    packets: list[dict] = [TaskPacket(
        goal=task,
        constraints=["minimize raw file reads", "use existing tests"],
    ).model_dump()]
    packets.append(generate_repo_summary(path).model_dump())

    for indexed in iter_indexed_python_files():
        for sp in generate_symbol_packets(indexed.path):
            packets.append(sp.model_dump())

    failure_dicts: list[dict] = []
    if failures:
        for line in Path(failures).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                failure_dicts.extend(extract_failures(json.loads(line)))
            except json.JSONDecodeError:
                continue
        if failure_dicts:
            packets.extend(failure_dicts)

    pinned: set[str] = set()
    if failure_dicts:
        packets, pinned = augment_with_failures(packets, failure_dicts)
        sys.stderr.write(
            f"[contextmesh] focus: pinned {len(pinned)} symbols on failure traces\n"
        )

    if not no_compress:
        packets = compress_packets(task_id, packets, pinned_hashes=pinned)

    if budget is not None:
        result = apply_budget(packets, budget)
        packets = result.packets
        sys.stderr.write(
            f"[contextmesh] budget {budget} → kept {len(packets)} packets "
            f"({result.tokens_used} tokens), dropped {result.dropped_count}\n"
        )

    if format == "jsonl":
        rendered = "\n".join(json.dumps(p, ensure_ascii=False) for p in packets)
    elif format == "markdown":
        rendered = render_markdown(packets, task=task)
    else:
        raise typer.BadParameter("format must be 'markdown' or 'jsonl'")

    if out:
        Path(out).write_text(rendered, encoding="utf-8")
        console.print(f"[green]wrote[/green] {len(packets)} packets to {out}")
    else:
        sys.stdout.write(rendered + "\n")


@app.command(name="expand")
def expand_cmd(
    file: str = typer.Argument(..., help="File path"),
    symbol: str = typer.Argument(..., help="Symbol name"),
    parent: str | None = typer.Option(None, "--parent", help="Disambiguate by parent class"),
):
    """Expand a symbol's full body. The agent calls this only when needed."""
    from contextmesh.agent.tools import expand_symbol

    body = expand_symbol(file, symbol, parent=parent)
    if body is None:
        console.print(f"[red]Symbol '{symbol}' not found in {file}[/red]")
        raise typer.Exit(code=1)
    sys.stdout.write(body + "\n")


ledger_app = typer.Typer(help="Inspect and append to the context ledger.")
app.add_typer(ledger_app, name="ledger")


@ledger_app.command("show")
def ledger_show(
    limit: int = typer.Option(10, help="How many entries"),
    task_id: str | None = typer.Option(None, help="Filter by task id"),
):
    """Show recent ledger entries."""
    from contextmesh.runtime.ledger import get_ledger

    entries = get_ledger(limit, task_id=task_id)
    if not entries:
        console.print("Ledger is empty.")
        return
    table = Table(title="Context Ledger")
    table.add_column("Task", style="cyan")
    table.add_column("Step", justify="right")
    table.add_column("Agent")
    table.add_column("Spent", justify="right", style="green")
    table.add_column("Avoided", justify="right", style="yellow")
    table.add_column("Decision")
    table.add_column("Outcome", style="magenta")
    for e in entries:
        table.add_row(
            e.task_id,
            str(e.step),
            e.agent,
            f"{e.tokens_estimated:,}",
            f"{e.tokens_avoided:,}",
            (e.decision[:30] + "…") if len(e.decision) > 30 else e.decision,
            e.outcome,
        )
    console.print(table)


@ledger_app.command("record")
def ledger_record(
    task_id: str = typer.Option(..., "--task-id"),
    step: int = typer.Option(..., "--step"),
    agent: str = typer.Option("coder", "--agent"),
    decision: str = typer.Option(..., "--decision"),
    outcome: str = typer.Option("ok", "--outcome"),
    outcome_class: str = typer.Option(
        "unknown",
        "--outcome-class",
        help="passed | unchanged | regressed | aborted | unknown",
    ),
    refs: list[str] = typer.Option([], "--ref", help="Repeatable evidence reference"),
    context_text: str = typer.Option("", "--context-text"),
    tokens_avoided: int = typer.Option(0, "--tokens-avoided"),
    tokens_kept_compressed: int = typer.Option(0, "--tokens-kept-compressed"),
    tokens_kept_pinned: int = typer.Option(0, "--tokens-kept-pinned"),
):
    """Append a step to the context ledger."""
    from contextmesh.runtime.ledger import record_step

    entry = record_step(
        task_id=task_id,
        step=step,
        agent=agent,
        context_refs=list(refs),
        context_text=context_text,
        decision=decision,
        outcome=outcome,
        outcome_class=outcome_class,
        tokens_avoided=tokens_avoided,
        tokens_kept_compressed=tokens_kept_compressed,
        tokens_kept_pinned=tokens_kept_pinned,
    )
    console.print(
        f"[green]recorded[/green] step {entry.step} for {entry.task_id} "
        f"({entry.tokens_estimated} tokens, outcome={entry.outcome_class})"
    )


@app.command()
def dashboard():
    """Render the local terminal dashboard."""
    from contextmesh.runtime.dashboard import render_dashboard

    render_dashboard(console)


@app.command(name="trace")
def trace_cmd(
    command: list[str] = typer.Argument(..., help="Agent command to wrap (e.g. claude -p ...)"),
    task_id: str = typer.Option(..., "--task-id", help="Task id to attach this run to"),
    agent: str = typer.Option("claude-code", "--agent", help="Adapter name"),
    silent: bool = typer.Option(False, "--silent", help="Suppress agent stdout passthrough"),
    from_file: str | None = typer.Option(
        None,
        "--from-file",
        help="Replay agent stream-json from a file instead of spawning a subprocess",
    ),
):
    """Wrap an agent CLI and populate the ledger from its tool-call stream.

    Example:

        contextmesh trace --task-id reset-bug -- \
            claude -p "Fix the failing test" --output-format stream-json --verbose
    """
    import subprocess

    from contextmesh.adapters import get_adapter
    from contextmesh.runtime.ledger import record_event

    try:
        adapter_cls = get_adapter(agent)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    adapter = adapter_cls(task_id=task_id, agent=agent)
    recorded = 0

    def handle_line(raw: str) -> None:
        nonlocal recorded
        if not silent:
            sys.stdout.write(raw)
            sys.stdout.flush()
        for event in adapter.feed(raw):
            record_event(event)
            recorded += 1

    if from_file:
        with open(from_file, encoding="utf-8") as f:
            for raw in f:
                handle_line(raw)
        for event in adapter.finalize():
            record_event(event)
            recorded += 1
        console.print(f"[green]traced[/green] {recorded} steps from {from_file}")
        return

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for raw in proc.stdout:
            handle_line(raw)
    finally:
        rc = proc.wait()
        for event in adapter.finalize():
            record_event(event)
            recorded += 1

    console.print(
        f"[green]traced[/green] {recorded} steps into task '{task_id}' (exit {rc})"
    )
    if rc != 0:
        raise typer.Exit(code=rc)


@app.command(name="metrics")
def metrics_cmd(
    task_id: str | None = typer.Option(None, "--task-id", help="Single task; default: aggregate"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON"),
):
    """Print useful_context_ratio and supporting metrics."""
    from contextmesh.runtime.metrics import global_metrics, task_metrics

    if task_id:
        m = task_metrics(task_id).as_dict()
    else:
        m = global_metrics().as_dict()

    if json_output:
        console.print(json.dumps(m, indent=2))
        return

    for k, v in m.items():
        console.print(f"  {k}: [bold]{v}[/bold]")


@app.command(name="waste")
def waste_cmd(
    threshold: int = typer.Option(3, "--threshold", help="Tasks-per-hash above which we flag"),
    json_output: bool = typer.Option(False, "--json"),
):
    """List packet hashes the seen-cache should have suppressed."""
    from contextmesh.runtime.metrics import find_repeat_waste

    rows = find_repeat_waste(threshold=threshold)
    if json_output:
        console.print(json.dumps([
            {
                "packet_hash": r.packet_hash,
                "times_sent": r.times_sent,
                "tasks": r.tasks,
                "wasted_tokens": r.wasted_tokens,
            }
            for r in rows
        ], indent=2))
        return

    if not rows:
        console.print(f"[dim]No repeat waste above threshold={threshold}.[/dim]")
        return
    for r in rows[:20]:
        console.print(
            f"  {r.packet_hash[:12]}  tasks={r.times_sent:>3}  "
            f"~wasted={r.wasted_tokens:>5} tokens"
        )


@app.command(name="reset-cache")
def reset_cache(task_id: str | None = typer.Option(None, "--task-id")):
    """Forget which packets were already shown to the agent."""
    from contextmesh.packets.compressor import reset_seen

    n = reset_seen(task_id)
    console.print(f"[yellow]cleared[/yellow] {n} seen-packet rows")


def run() -> None:
    app()


if __name__ == "__main__":
    app()
