"""Markdown rendering of context packets, suitable for pasting into agents."""
from __future__ import annotations

from collections.abc import Iterable


def _line(packet: dict) -> str:
    t = packet.get("type", "?")
    if t == "task":
        cs = ", ".join(packet.get("constraints", [])) or "none"
        return f"- **Task**: {packet['goal']} _(constraints: {cs})_"
    if t == "repo_summary":
        langs = ", ".join(packet.get("languages", [])) or "?"
        fws = ", ".join(packet.get("frameworks", [])) or "—"
        return (
            f"- **Repo**: {packet.get('files_indexed', 0)} files, "
            f"{packet.get('symbols_indexed', 0)} symbols · langs: {langs} · stack: {fws}"
        )
    if t == "file_summary":
        return (
            f"- **File** `{packet['file']}` ({packet['language']}, "
            f"{packet['line_count']} lines, hash {packet['hash']})"
        )
    if t == "symbol":
        parent = f"{packet['parent']}." if packet.get("parent") else ""
        summary = (packet.get("summary") or "").strip().strip('"')
        pinned = " (pinned: critical path)" if packet.get("pinned") else ""
        head = (
            f"- **Symbol** `{parent}{packet['name']}` in `{packet['file']}`{pinned}\n"
            f"    - signature: `{packet['signature']}`\n"
            f"    - hash: `{packet['hash']}`\n"
            f"    - summary: {summary or '_(none)_'}"
        )
        if packet.get("body"):
            head += f"\n    - body:\n```python\n{packet['body']}\n```"
        return head
    if t == "symbol_ref":
        return f"- **Seen-symbol** `{packet.get('name', '?')}` (hash `{packet['hash']}`) — request body if needed"
    if t == "file_ref":
        return f"- **Seen-file** `{packet.get('file', '?')}` (hash `{packet['hash']}`)"
    if t == "test_failure":
        loc = f"{packet['file']}:{packet.get('line', '?')}"
        return (
            f"- **Test failure** `{packet['test']}` at `{loc}`\n"
            f"    - assertion: {packet.get('assertion') or '_(unknown)_'}\n"
            f"    - trace:\n```\n{packet['minimal_trace']}\n```"
        )
    if t == "command_result":
        head = (
            f"- **Command** `{packet['command']}` → **{packet['status']}** "
            f"({len(packet.get('failures', []))} failures)"
        )
        rest = "\n".join(_line(f | {"type": "test_failure"}) for f in packet.get("failures", []))
        return head + (f"\n{rest}" if rest else "")
    if t == "uncertainty":
        return f"- **Uncertainty**: {packet.get('value', '')}"
    if t == "next_context":
        items = ", ".join(packet.get("items", []))
        return f"- **Next context request**: {items}"
    return f"- **{t}**: {packet}"


def render_markdown(packets: Iterable[dict], *, task: str | None = None) -> str:
    out: list[str] = []
    out.append("# ContextMesh Context Packet")
    out.append("")
    if task:
        out.append(f"**Task:** {task}")
        out.append("")
    out.append("## Packets")
    out.append("")
    for p in packets:
        out.append(_line(p))
    out.append("")
    out.append("---")
    out.append(
        "_Symbols marked **Seen-symbol** were already provided earlier in this task. "
        "Ask for raw bodies via `contextmesh expand <file> <symbol>` only when needed._"
    )
    return "\n".join(out)
