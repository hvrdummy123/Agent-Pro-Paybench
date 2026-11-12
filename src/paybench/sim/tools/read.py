"""Read tools."""

from __future__ import annotations

from typing import Any

from paybench.sim.policy import get_policy_section
from paybench.sim.tools.base import customer_public, err, ok
from paybench.sim.world import World


def search_customers(world: World, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip().lower()
    if not query:
        return err("INVALID_ARGUMENT", "query is required")
    hits = []
    for c in world.customers.values():
        blob = f"{c.name} {c.email} {c.phone}".lower()
        if query in blob:
            hits.append(customer_public(world, c.id))
    hits.sort(key=lambda x: x["id"])
    return ok({"customers": hits, "count": len(hits)})


def get_customer(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("customer_id")
    if not isinstance(cid, str) or cid not in world.customers:
        return err("NOT_FOUND", f"customer {cid} not found")
    return ok(customer_public(world, cid))


def get_account(world: World, args: dict[str, Any]) -> dict[str, Any]:
    aid = args.get("account_id")
    if not isinstance(aid, str) or aid not in world.accounts:
        return err("NOT_FOUND", f"account {aid} not found")
    acc = world.accounts[aid]
    # reset daily window if day rolled
    day = world.clock.day_start().strftime("%Y-%m-%d")
    if acc.daily_outbound_day != day:
        acc.daily_outbound_used = 0
        acc.daily_outbound_day = day
    return ok(
        {
            "id": acc.id,
            "customer_id": acc.customer_id,
            "currency": acc.currency,
            "balance": world.account_balance(acc.id),
            "status": acc.status.value,
            "daily_outbound_used": acc.daily_outbound_used,
            "limits": {
                "daily_outbound": 5_000_000 if acc.currency == "INR" else 60_000,
            },
        }
    )


def list_payments(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("customer_id")
    if not isinstance(cid, str) or cid not in world.customers:
        return err("NOT_FOUND", f"customer {cid} not found")
    status = args.get("status")
    since = args.get("since")
    limit = int(args.get("limit") or 50)
    if limit < 1 or limit > 50:
        return err("INVALID_ARGUMENT", "limit must be 1..50")
    cursor = args.get("cursor")
    items = [p for p in world.payments.values() if p.customer_id == cid]
    if isinstance(status, str):
        items = [p for p in items if p.status.value == status]
    if isinstance(since, str):
        items = [p for p in items if p.created_at >= since]
    items.sort(key=lambda p: (p.created_at, p.id), reverse=True)
    start = 0
    if isinstance(cursor, str) and cursor:
        for i, p in enumerate(items):
            if p.id == cursor:
                start = i + 1
                break
    page = items[start : start + limit]
    next_cursor = page[-1].id if len(page) == limit and start + limit < len(items) else None
    return ok(
        {
            "payments": [
                {
                    "id": p.id,
                    "amount": p.amount,
                    "currency": p.currency,
                    "status": p.status.value,
                    "created_at": p.created_at,
                    "merchant_id": p.merchant_id,
                }
                for p in page
            ],
            "next_cursor": next_cursor,
        }
    )


def get_payment(world: World, args: dict[str, Any]) -> dict[str, Any]:
    pid = args.get("payment_id")
    if not isinstance(pid, str) or pid not in world.payments:
        return err("NOT_FOUND", f"payment {pid} not found")
    p = world.payments[pid]
    refunds = [r.model_dump(mode="json") for r in world.refunds.values() if r.payment_id == pid]
    return ok(
        {
            **p.model_dump(mode="json"),
            "refunds": refunds,
        }
    )


def get_merchant(world: World, args: dict[str, Any]) -> dict[str, Any]:
    mid = args.get("merchant_id")
    if not isinstance(mid, str) or mid not in world.merchants:
        return err("NOT_FOUND", f"merchant {mid} not found")
    return ok(world.merchants[mid].model_dump(mode="json"))


def list_transfers(world: World, args: dict[str, Any]) -> dict[str, Any]:
    aid = args.get("account_id")
    if not isinstance(aid, str) or aid not in world.accounts:
        return err("NOT_FOUND", f"account {aid} not found")
    since = args.get("since")
    limit = int(args.get("limit") or 50)
    if limit < 1 or limit > 50:
        return err("INVALID_ARGUMENT", "limit must be 1..50")
    cursor = args.get("cursor")
    items = [t for t in world.transfers.values() if t.from_account == aid]
    if isinstance(since, str):
        items = [t for t in items if t.created_at >= since]
    items.sort(key=lambda t: (t.created_at, t.id), reverse=True)
    start = 0
    if isinstance(cursor, str) and cursor:
        for i, t in enumerate(items):
            if t.id == cursor:
                start = i + 1
                break
    page = items[start : start + limit]
    next_cursor = page[-1].id if len(page) == limit and start + limit < len(items) else None
    return ok(
        {
            "transfers": [t.model_dump(mode="json") for t in page],
            "next_cursor": next_cursor,
        }
    )


def get_dispute(world: World, args: dict[str, Any]) -> dict[str, Any]:
    did = args.get("dispute_id")
    if not isinstance(did, str) or did not in world.disputes:
        return err("NOT_FOUND", f"dispute {did} not found")
    return ok(world.disputes[did].model_dump(mode="json"))


def get_fx_rate(world: World, args: dict[str, Any]) -> dict[str, Any]:
    base = str(args.get("base", "")).upper()
    quote = str(args.get("quote", "")).upper()
    key = f"{base}:{quote}"
    if key not in world.fx_rates:
        return err("NOT_FOUND", f"no FX rate for {key}")
    return ok({"base": base, "quote": quote, "rate": world.fx_rates[key]})


def get_policy(world: World, args: dict[str, Any]) -> dict[str, Any]:
    _ = world
    section = args.get("section")
    text = get_policy_section(section if isinstance(section, str) else None)
    return ok({"policy": text})
