"""Per-agent adapters that translate tool-call streams into ledger events."""
from contextmesh.adapters.aider import AiderAdapter
from contextmesh.adapters.base import Adapter
from contextmesh.adapters.claude_code import ClaudeCodeAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "claude-code": ClaudeCodeAdapter,
    "claude": ClaudeCodeAdapter,
    "aider": AiderAdapter,
}


def get_adapter(name: str) -> type[Adapter]:
    if name not in ADAPTERS:
        raise KeyError(f"unknown adapter '{name}'. Available: {sorted(ADAPTERS)}")
    return ADAPTERS[name]


__all__ = ["Adapter", "AiderAdapter", "ClaudeCodeAdapter", "ADAPTERS", "get_adapter"]
