"""Build OpenTelemetry-ready payloads from ContextMesh inspections."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from contextmesh import __version__
from contextmesh.runtime.inspector import inspect_task


def _hex_id(seed: str, length: int) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:length]


def _value(value: str | int | float | bool) -> dict:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": value}
    if isinstance(value, float):
        return {"doubleValue": round(value, 4)}
    return {"stringValue": value}


def _attribute(key: str, value: str | int | float | bool) -> dict:
    return {"key": key, "value": _value(value)}


def _event(name: str, attributes: dict[str, str | int | float | bool]) -> dict:
    return {
        "name": name,
        "attributes": [_attribute(key, value) for key, value in attributes.items()],
    }


@dataclass
class OTelExport:
    task_id: str
    trace_id: str
    resource_spans: list[dict]

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "resourceSpans": self.resource_spans,
        }


def build_otel_export(
    task_id: str,
    *,
    trace_id: str | None = None,
    service_name: str = "contextmesh",
) -> OTelExport:
    """Return an OTLP/JSON-shaped payload for context intelligence metadata."""
    inspection = inspect_task(task_id)
    resolved_trace_id = trace_id or _hex_id(f"contextmesh:{task_id}:trace", 32)
    if len(resolved_trace_id) != 32 or any(c not in "0123456789abcdef" for c in resolved_trace_id):
        raise ValueError("trace_id must be a 32-character lowercase hex string")
    span_id = _hex_id(f"contextmesh:{task_id}:context-inspection", 16)

    events = [
        _event("contextmesh.context.selected", {
            "contextmesh.context.ref": item.ref,
            "contextmesh.context.times_selected": item.times_selected,
            "contextmesh.context.first_step": item.first_step,
            "contextmesh.context.last_step": item.last_step,
        })
        for item in inspection.selected_context
    ]
    events.extend(
        _event("contextmesh.context.rejected", {
            "contextmesh.context.ref": item["ref"],
            "contextmesh.context.reason": item["reason"],
            "contextmesh.context.source_type": item["source_type"],
            "contextmesh.context.relevance_score": item["relevance_score"] or 0.0,
            "contextmesh.context.tokens_estimated": item["tokens_estimated"],
        })
        for item in inspection.rejected_context
    )
    events.extend(
        _event("contextmesh.recommendation", {
            "contextmesh.recommendation": recommendation,
        })
        for recommendation in inspection.recommendations
    )

    span = {
        "traceId": resolved_trace_id,
        "spanId": span_id,
        "name": "contextmesh.context_inspection",
        "kind": "SPAN_KIND_INTERNAL",
        "attributes": [
            _attribute("gen_ai.operation.name", "agent"),
            _attribute("contextmesh.version", __version__),
            _attribute("contextmesh.task_id", inspection.task_id),
            _attribute("contextmesh.outcome", inspection.final_outcome_class),
            _attribute("contextmesh.context_quality_score", inspection.context_quality_score),
            _attribute("contextmesh.useful_context_ratio", inspection.useful_context_ratio),
            _attribute("contextmesh.tokens_billed", inspection.tokens_billed),
            _attribute("contextmesh.tokens_avoided", inspection.tokens_avoided),
            _attribute("contextmesh.steps", inspection.steps),
            _attribute("contextmesh.duplicate_ref_sends", inspection.duplicate_ref_sends),
            _attribute("contextmesh.selected_context_count", len(inspection.selected_context)),
            _attribute("contextmesh.rejected_context_count", len(inspection.rejected_context)),
        ],
        "events": events,
    }
    return OTelExport(
        task_id=task_id,
        trace_id=resolved_trace_id,
        resource_spans=[{
            "resource": {
                "attributes": [
                    _attribute("service.name", service_name),
                    _attribute("telemetry.sdk.name", "contextmesh"),
                    _attribute("telemetry.sdk.language", "python"),
                ],
            },
            "scopeSpans": [{
                "scope": {
                    "name": "contextmesh.runtime.otel_export",
                    "version": __version__,
                },
                "spans": [span],
            }],
        }],
    )
