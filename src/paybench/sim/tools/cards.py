"""Card freeze/unfreeze tools."""

from __future__ import annotations

from typing import Any

from paybench.sim.models import CardStatus
from paybench.sim.tools.base import err, ok
from paybench.sim.world import World


def freeze_card(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("card_id")
    reason = str(args.get("reason") or "")
    if not isinstance(cid, str) or cid not in world.cards:
        return err("NOT_FOUND", f"card {cid} not found")
    card = world.cards[cid]
    if card.status == CardStatus.CANCELLED:
        return err("INVALID_ARGUMENT", "cannot freeze cancelled card")
    card.status = CardStatus.FROZEN
    _ = reason
    return ok(card.model_dump(mode="json"))


def unfreeze_card(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("card_id")
    if not isinstance(cid, str) or cid not in world.cards:
        return err("NOT_FOUND", f"card {cid} not found")
    card = world.cards[cid]
    if card.status != CardStatus.FROZEN:
        return err("INVALID_ARGUMENT", "card is not frozen")
    card.status = CardStatus.ACTIVE
    return ok(card.model_dump(mode="json"))
