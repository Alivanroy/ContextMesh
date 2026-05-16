"""Provider pricing helpers for cost-weighted metrics.

ContextMesh keeps token volume as the source of truth. Dollar estimates are
optional and only appear when the user supplies per-million-token prices via
environment variables, avoiding baked-in provider prices that age badly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceModel:
    input_per_million: float = 0.0
    cached_read_per_million: float = 0.0
    cached_write_per_million: float = 0.0
    output_per_million: float = 0.0

    @property
    def configured(self) -> bool:
        return any((
            self.input_per_million,
            self.cached_read_per_million,
            self.cached_write_per_million,
            self.output_per_million,
        ))


def _env_float(name: str) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def load_price_model() -> PriceModel:
    """Load optional USD-per-million-token prices from the environment."""
    return PriceModel(
        input_per_million=_env_float("CONTEXTMESH_PRICE_INPUT_PER_MTOK"),
        cached_read_per_million=_env_float("CONTEXTMESH_PRICE_CACHE_READ_PER_MTOK"),
        cached_write_per_million=_env_float("CONTEXTMESH_PRICE_CACHE_WRITE_PER_MTOK"),
        output_per_million=_env_float("CONTEXTMESH_PRICE_OUTPUT_PER_MTOK"),
    )


def estimate_cost_usd(
    *,
    tokens_provider_input: int,
    tokens_cached_read: int,
    tokens_cached_write: int,
    tokens_provider_output: int,
    price_model: PriceModel,
) -> float:
    """Estimate USD cost from provider-token columns and a price model."""
    return (
        tokens_provider_input * price_model.input_per_million
        + tokens_cached_read * price_model.cached_read_per_million
        + tokens_cached_write * price_model.cached_write_per_million
        + tokens_provider_output * price_model.output_per_million
    ) / 1_000_000
