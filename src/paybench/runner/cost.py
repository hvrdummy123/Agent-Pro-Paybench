"""Token cost accounting from pricing.yaml."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

_PRICING_CACHE: dict[str, Any] | None = None


def load_pricing(path: Path | None = None) -> dict[str, Any]:
    global _PRICING_CACHE
    if path is not None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    if _PRICING_CACHE is not None:
        return _PRICING_CACHE
    pkg_path = resources.files("paybench.runner").joinpath("pricing.yaml")
    raw = yaml.safe_load(pkg_path.read_text(encoding="utf-8"))
    _PRICING_CACHE = raw if isinstance(raw, dict) else {}
    return _PRICING_CACHE


def _entry_for_model(pricing: dict[str, Any], model_key: str) -> dict[str, Any] | None:
    models = pricing.get("models") or {}
    raw = models.get(model_key)
    if isinstance(raw, dict):
        return raw
    if ":" in model_key:
        provider, mid = model_key.split(":", 1)
        composite = f"{provider}:{mid}"
        raw2 = models.get(composite)
        if isinstance(raw2, dict):
            return raw2
    return None


def compute_cost_usd(
    model_key: str,
    *,
    tokens_in: int,
    tokens_out: int,
    pricing: dict[str, Any] | None = None,
) -> tuple[float, bool]:
    """Return (cost_usd, has_placeholder_pricing)."""
    table = pricing if pricing is not None else load_pricing()
    entry = _entry_for_model(table, model_key)
    if not entry:
        return (0.0, False)
    placeholder = bool(entry.get("placeholder", False))
    in_per_m = float(entry.get("input_per_million", 0.0))
    out_per_m = float(entry.get("output_per_million", 0.0))
    cost = (tokens_in / 1_000_000.0) * in_per_m + (tokens_out / 1_000_000.0) * out_per_m
    return (cost, placeholder)


def has_placeholder_prices(pricing: dict[str, Any] | None = None) -> bool:
    table = pricing if pricing is not None else load_pricing()
    models = table.get("models") or {}
    return any(bool(v.get("placeholder")) for v in models.values() if isinstance(v, dict))
