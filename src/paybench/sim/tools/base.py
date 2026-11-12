"""Tool response helpers and dispatch context."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import orjson

from paybench.config import DEFAULT_TOOL_LATENCY_S
from paybench.sim.world import World

ErrorCode = str


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def err(
    code: ErrorCode,
    message: str,
    *,
    retryable: bool = False,
    retry_after_s: int | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "retry_after_s": retry_after_s,
        },
    }


def args_hash(args: dict[str, Any]) -> str:
    payload = orjson.dumps(args, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(payload).hexdigest()


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[World, dict[str, Any]], dict[str, Any]]
    latency_s: int = DEFAULT_TOOL_LATENCY_S
    is_action: bool = False
    supports_idempotency: bool = False


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self.tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [self.tools[k] for k in sorted(self.tools)]


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def customer_public(world: World, customer_id: str) -> dict[str, Any]:
    c = world.customers[customer_id]
    verified = customer_id in world.verified_customers
    base: dict[str, Any] = {
        "id": c.id,
        "name": c.name,
        "kyc_status": c.kyc_status.value,
        "risk_tier": c.risk_tier.value,
        "locked": c.locked,
    }
    if verified:
        base["email"] = c.email
        base["phone"] = c.phone
    else:
        base["email"] = mask_email(c.email)
        base["phone"] = mask_phone(c.phone)
    return base
