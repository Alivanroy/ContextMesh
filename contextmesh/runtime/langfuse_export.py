"""Build Langfuse-ready metadata payloads from ContextMesh inspections."""
from __future__ import annotations

from dataclasses import dataclass

from contextmesh.runtime.inspector import inspect_task


@dataclass
class LangfuseExport:
    task_id: str
    trace_id: str | None
    metadata: dict
    tags: list[str]

    def as_dict(self) -> dict:
        payload = {
            "metadata": self.metadata,
            "tags": self.tags,
        }
        if self.trace_id:
            payload["trace_id"] = self.trace_id
        return payload


def build_langfuse_export(
    task_id: str,
    *,
    trace_id: str | None = None,
    tags: list[str] | None = None,
) -> LangfuseExport:
    """Return a payload that can be attached to a Langfuse trace."""
    inspection = inspect_task(task_id)
    default_tags = [
        "contextmesh",
        f"context_quality:{inspection.context_quality_score:.2f}",
        f"outcome:{inspection.final_outcome_class}",
    ]
    return LangfuseExport(
        task_id=task_id,
        trace_id=trace_id,
        metadata=inspection.langfuse_metadata(),
        tags=[*(tags or []), *default_tags],
    )
