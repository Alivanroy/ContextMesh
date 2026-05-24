"""JSON Schema contracts for context intelligence payloads."""
from __future__ import annotations

from copy import deepcopy

SCHEMA_VERSION = "contextmesh.context-intelligence.v1"


_DEFS = {
    "contextItemInsight": {
        "type": "object",
        "required": ["ref", "times_selected", "first_step", "last_step"],
        "properties": {
            "ref": {"type": "string"},
            "times_selected": {"type": "integer", "minimum": 1},
            "first_step": {"type": "integer", "minimum": 0},
            "last_step": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
    "auditFinding": {
        "type": "object",
        "required": ["code", "severity", "ref", "message"],
        "properties": {
            "code": {"type": "string"},
            "severity": {"type": "string", "enum": ["info", "warn", "error"]},
            "ref": {"type": "string"},
            "message": {"type": "string"},
            "step": {"type": ["integer", "null"], "minimum": 0},
        },
        "additionalProperties": False,
    },
    "contextCandidate": {
        "type": "object",
        "required": [
            "task_id", "step", "ref", "status", "source_type",
            "reason", "relevance_score", "tokens_estimated",
        ],
        "properties": {
            "task_id": {"type": "string"},
            "step": {"type": "integer", "minimum": 0},
            "ref": {"type": "string"},
            "status": {"type": "string", "enum": ["available", "selected", "rejected"]},
            "source_type": {"type": "string"},
            "reason": {"type": "string"},
            "relevance_score": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "tokens_estimated": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
}


def _base_schema(name: str) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://contextmesh.dev/schemas/{SCHEMA_VERSION}/{name}.json",
        "x-contextmesh-schema-version": SCHEMA_VERSION,
    }


def candidate_schema() -> dict:
    return {**_base_schema("context-candidate"), **deepcopy(_DEFS["contextCandidate"])}


def inspection_schema() -> dict:
    schema = {
        **_base_schema("context-run-inspection"),
        "type": "object",
        "required": [
            "task_id", "steps", "agents", "final_outcome_class", "tokens_billed",
            "tokens_avoided", "useful_context_ratio", "context_quality_score",
            "score_breakdown", "selected_context", "rejected_context",
            "duplicate_ref_sends", "recommendations", "langfuse_metadata",
        ],
        "properties": {
            "task_id": {"type": "string"},
            "steps": {"type": "integer", "minimum": 0},
            "agents": {"type": "array", "items": {"type": "string"}},
            "final_outcome_class": {"type": "string"},
            "tokens_billed": {"type": "integer", "minimum": 0},
            "tokens_avoided": {"type": "integer", "minimum": 0},
            "useful_context_ratio": {"type": "number", "minimum": 0, "maximum": 1},
            "context_quality_score": {"type": "number", "minimum": 0, "maximum": 1},
            "score_breakdown": {
                "type": "object",
                "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "selected_context": {
                "type": "array",
                "items": {"$ref": "#/$defs/contextItemInsight"},
            },
            "rejected_context": {"type": "array", "items": {"type": "object"}},
            "duplicate_ref_sends": {"type": "integer", "minimum": 0},
            "recommendations": {"type": "array", "items": {"type": "string"}},
            "langfuse_metadata": {"type": "object"},
        },
        "$defs": {
            "contextItemInsight": deepcopy(_DEFS["contextItemInsight"]),
        },
        "additionalProperties": False,
    }
    return schema


def diff_schema() -> dict:
    return {
        **_base_schema("context-run-diff"),
        "type": "object",
        "required": [
            "left_task_id", "right_task_id", "left_outcome_class",
            "right_outcome_class", "left_context_quality_score",
            "right_context_quality_score", "quality_delta", "refs_only_left",
            "refs_only_right", "refs_shared", "duplicate_ref_delta",
            "tokens_billed_delta", "tokens_avoided_delta", "recommendations",
        ],
        "properties": {
            "left_task_id": {"type": "string"},
            "right_task_id": {"type": "string"},
            "left_outcome_class": {"type": "string"},
            "right_outcome_class": {"type": "string"},
            "left_context_quality_score": {"type": "number"},
            "right_context_quality_score": {"type": "number"},
            "quality_delta": {"type": "number"},
            "refs_only_left": {"type": "array", "items": {"type": "string"}},
            "refs_only_right": {"type": "array", "items": {"type": "string"}},
            "refs_shared": {"type": "array", "items": {"type": "string"}},
            "duplicate_ref_delta": {"type": "integer"},
            "tokens_billed_delta": {"type": "integer"},
            "tokens_avoided_delta": {"type": "integer"},
            "recommendations": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def audit_schema() -> dict:
    return {
        **_base_schema("context-audit"),
        "type": "object",
        "required": ["task_id", "passed", "findings"],
        "properties": {
            "task_id": {"type": "string"},
            "passed": {"type": "boolean"},
            "findings": {
                "type": "array",
                "items": {"$ref": "#/$defs/auditFinding"},
            },
        },
        "$defs": {
            "auditFinding": deepcopy(_DEFS["auditFinding"]),
        },
        "additionalProperties": False,
    }


def langfuse_export_schema() -> dict:
    return {
        **_base_schema("langfuse-export"),
        "type": "object",
        "required": ["metadata", "tags"],
        "properties": {
            "trace_id": {"type": "string"},
            "metadata": {"type": "object"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def otel_export_schema() -> dict:
    return {
        **_base_schema("otel-export"),
        "type": "object",
        "required": ["task_id", "trace_id", "resourceSpans"],
        "properties": {
            "task_id": {"type": "string"},
            "trace_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
            "resourceSpans": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "object"},
            },
        },
        "additionalProperties": False,
    }


SCHEMAS = {
    "candidate": candidate_schema,
    "inspection": inspection_schema,
    "diff": diff_schema,
    "audit": audit_schema,
    "langfuse-export": langfuse_export_schema,
    "otel-export": otel_export_schema,
}


def get_context_schema(name: str) -> dict:
    try:
        return SCHEMAS[name]()
    except KeyError as exc:
        valid = ", ".join(sorted(SCHEMAS))
        raise ValueError(f"schema must be one of: {valid}") from exc


def all_context_schemas() -> dict:
    return {name: schema() for name, schema in sorted(SCHEMAS.items())}
