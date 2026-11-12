"""Customer communication tools."""

from __future__ import annotations

from typing import Any

from paybench.sim.models import Message
from paybench.sim.tools.base import err, ok
from paybench.sim.world import World


def send_customer_message(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("customer_id")
    text = args.get("text")
    if not isinstance(cid, str) or cid not in world.customers:
        return err("NOT_FOUND", f"customer {cid} not found")
    if not isinstance(text, str) or not text.strip():
        return err("INVALID_ARGUMENT", "text is required")
    mid = world.ids.message()
    msg = Message(
        id=mid,
        customer_id=cid,
        text=text,
        created_at=world.clock.isoformat(),
        direction="outbound",
    )
    world.messages.append(msg)
    return ok(msg.model_dump(mode="json"))


def ask_customer(world: World, args: dict[str, Any]) -> dict[str, Any]:
    question = args.get("question")
    if not isinstance(question, str) or not question.strip():
        return err("INVALID_ARGUMENT", "question is required")
    q = question.lower()
    answer = "I'm not sure."
    # keyword match against customer_facts
    for key, val in sorted(world.customer_facts.items()):
        if key.lower() in q or key.lower().replace("_", " ") in q:
            answer = str(val)
            break
        # also match common phrasings
        if key == "dob" and ("dob" in q or "birth" in q or "born" in q):
            answer = str(val)
            break
        if key == "card_last4" and ("card" in q or "last4" in q or "last four" in q):
            answer = str(val)
            break
    return ok({"answer": answer})


def escalate_to_human(world: World, args: dict[str, Any]) -> dict[str, Any]:
    summary = str(args.get("summary") or "")
    reason = str(args.get("reason") or "")
    if not summary:
        return err("INVALID_ARGUMENT", "summary is required")
    world.escalated = True
    world.session_flags["escalation"] = {"summary": summary, "reason": reason}
    return ok({"escalated": True, "summary": summary, "reason": reason})
