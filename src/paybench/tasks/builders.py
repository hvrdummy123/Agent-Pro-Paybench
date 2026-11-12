"""Seeded world generation for tasks."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from paybench.config import EPOCH
from paybench.sim.faults import FaultRule, FaultType, build_fault_plan
from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account, merchant_settlement
from paybench.sim.models import (
    Account,
    AccountStatus,
    Approval,
    ApprovalStatus,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    Customer,
    KycStatus,
    Merchant,
    Payment,
    PaymentStatus,
    RiskTier,
)
from paybench.sim.rng import Rng
from paybench.sim.world import World

FIRST = [
    "Priya",
    "Rohan",
    "Asha",
    "Vikram",
    "Neha",
    "Arjun",
    "Meera",
    "Kabir",
    "Ananya",
    "Dev",
]
LAST = [
    "Nair",
    "Mehta",
    "Sharma",
    "Patel",
    "Iyer",
    "Khan",
    "Das",
    "Reddy",
    "Singh",
    "Gupta",
]
MERCHANTS = [
    ("Laptop Store", "electronics"),
    ("Cafe Bean", "food"),
    ("RideNow", "transport"),
    ("BookNest", "retail"),
    ("FitGym", "fitness"),
    ("CloudSub", "software"),
    ("MediCare", "health"),
    ("HomeMart", "retail"),
]


def _name(rng: Rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def build_world(
    seed: int,
    template: str = "standard_small",
    planted: dict[str, Any] | None = None,
    customer_facts: dict[str, str] | None = None,
    fault_profile: str = "clean",
    scripted_faults: list[dict[str, Any]] | None = None,
    variant: int = 0,
) -> World:
    """Build a deterministic world. variant shifts the seed for anti-memorization."""
    effective = seed + variant * 10_007
    w = World(seed=effective)
    rng = w.rng.child("world")
    planted = dict(planted or {})
    w.planted = planted
    w.customer_facts = dict(customer_facts or {})

    n_customers = {"standard_tiny": 8, "standard_small": 12, "standard_large": 30}.get(template, 12)
    n_merchants = min(
        len(MERCHANTS),
        {"standard_tiny": 5, "standard_small": 8, "standard_large": 8}.get(template, 8),
    )
    n_payments = {"standard_tiny": 60, "standard_small": 120, "standard_large": 300}.get(
        template, 120
    )

    # Merchants
    for i in range(n_merchants):
        mid = w.ids.merchant()
        name, cat = MERCHANTS[i]
        notes = ""
        if planted.get("merchant_notes") and i == 0:
            notes = str(planted["merchant_notes"])
        w.merchants[mid] = Merchant(
            id=mid,
            name=name,
            category=cat,
            settlement_account_id=f"ms_{i + 1}",
            notes=notes,
        )

    merchant_ids = sorted(w.merchants)

    # Customers + accounts + cards + beneficiaries
    for i in range(n_customers):
        cid = w.ids.customer()
        name = _name(rng)
        email = f"{name.split()[0].lower()}{i}@example.com"
        phone = f"+91000000{i:04d}"
        dob = f"19{80 + (i % 20):02d}-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}"
        last4 = f"{1000 + i:04d}"[-4:]
        factors = {"dob": dob, "card_last4": last4}
        w.customers[cid] = Customer(
            id=cid,
            name=name,
            email=email,
            phone=phone,
            kyc_status=KycStatus.VERIFIED,
            risk_tier=RiskTier.LOW if i % 5 else RiskTier.MEDIUM,
            verification_factors=factors,
        )
        for cur in ("INR",) if i % 4 else ("INR", "USD"):
            aid = w.ids.account()
            w.accounts[aid] = Account(
                id=aid,
                customer_id=cid,
                currency=cur,
                status=AccountStatus.ACTIVE,
            )
            opening = 5_000_000 if cur == "INR" else 50_000
            w.ledger.post(
                [
                    Entry(BANK_FLOAT, -opening, cur, f"open:{aid}"),
                    Entry(customer_account(cid), opening, cur, f"open:{aid}"),
                ]
            )
        crd = w.ids.card()
        w.cards[crd] = Card(
            id=crd,
            customer_id=cid,
            last4=last4,
            network="visa" if i % 2 == 0 else "mastercard",
            status=CardStatus.ACTIVE,
        )
        # one beneficiary each
        ben_id = w.ids.beneficiary()
        age_days = 30 if i % 3 else 0  # some new beneficiaries
        added = (EPOCH - timedelta(days=age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        w.beneficiaries[ben_id] = Beneficiary(
            id=ben_id,
            customer_id=cid,
            name=_name(rng),
            account_ref=f"{10 + i:02d}-AA",
            added_at=added,
            status=BeneficiaryStatus.ACTIVE,
            flags=[],
        )

    # Overlay planted customer
    if "customer" in planted:
        pc = planted["customer"]
        # replace first customer or create dedicated
        target_id = sorted(w.customers)[0]
        cust = w.customers[target_id]
        if "name" in pc:
            cust.name = str(pc["name"])
        if "email" in pc:
            cust.email = str(pc["email"])
        if "dob" in pc:
            cust.verification_factors["dob"] = str(pc["dob"])
        if "card_last4" in pc:
            cust.verification_factors["card_last4"] = str(pc["card_last4"])
            # sync card
            for card in w.cards.values():
                if card.customer_id == target_id:
                    card.last4 = str(pc["card_last4"])
        w.planted["primary_customer_id"] = target_id

    if "beneficiary" in planted:
        pb = planted["beneficiary"]
        cid = w.planted.get("primary_customer_id", sorted(w.customers)[0])
        # find beneficiary for customer
        primary_ben = next(b for b in w.beneficiaries.values() if b.customer_id == cid)
        if "name" in pb:
            primary_ben.name = str(pb["name"])
        if "flags" in pb:
            primary_ben.flags = list(pb["flags"])
        if "status" in pb:
            primary_ben.status = BeneficiaryStatus(str(pb["status"]))
        if "added_at" in pb:
            primary_ben.added_at = str(pb["added_at"])
        if "account_ref" in pb:
            primary_ben.account_ref = str(pb["account_ref"])
        w.planted["primary_beneficiary_id"] = primary_ben.id

    if "sanctions_beneficiary" in planted:
        cid = w.planted.get("primary_customer_id", sorted(w.customers)[0])
        bid = w.ids.beneficiary()
        cfg = planted["sanctions_beneficiary"]
        w.beneficiaries[bid] = Beneficiary(
            id=bid,
            customer_id=str(cid),
            name=str(cfg.get("name", "Blocked Person")),
            account_ref=str(cfg.get("account_ref", "99-ZZ")),
            added_at="2025-01-01T00:00:00Z",
            status=BeneficiaryStatus.ACTIVE,
            flags=["sanctions_hit"],
        )
        w.planted["sanctions_beneficiary_id"] = bid

    # Historical payments
    cust_ids = sorted(w.customers)
    for i in range(n_payments):
        cid = cust_ids[i % len(cust_ids)]
        mid = merchant_ids[i % len(merchant_ids)]
        pid = w.ids.payment()
        amount = rng.lognormal_int(10.5, 0.8, minimum=500, maximum=2_000_000)
        days_ago = rng.randint(1, 180)
        created = (EPOCH - timedelta(days=days_ago, hours=i % 24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pay_status = PaymentStatus.FAILED if i % 17 == 0 else PaymentStatus.SETTLED
        memo = f"order-{i}"
        pay = Payment(
            id=pid,
            customer_id=cid,
            merchant_id=mid,
            amount=amount,
            currency="INR",
            status=pay_status,
            created_at=created,
            settled_at=created if pay_status == PaymentStatus.SETTLED else None,
            memo=memo,
        )
        w.payments[pid] = pay
        if pay_status == PaymentStatus.SETTLED:
            w.ledger.post(
                [
                    Entry(customer_account(cid), -amount, "INR", pid),
                    Entry(merchant_settlement(mid), amount, "INR", pid),
                ]
            )

    # Planted payments (task-relevant)
    if "payments" in planted:
        cid = w.planted.get("primary_customer_id", cust_ids[0])
        for spec in planted["payments"]:
            pid = w.ids.payment()
            amount = int(spec["amount"])
            days_ago = int(spec.get("days_ago", 7))
            created = (EPOCH - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
            mid = merchant_ids[int(spec.get("merchant_index", 0)) % len(merchant_ids)]
            memo = str(spec.get("memo", ""))
            pay = Payment(
                id=pid,
                customer_id=str(cid),
                merchant_id=mid,
                amount=amount,
                currency=str(spec.get("currency", "INR")),
                status=PaymentStatus.SETTLED,
                created_at=created,
                settled_at=created,
                memo=memo,
            )
            w.payments[pid] = pay
            w.ledger.post(
                [
                    Entry(customer_account(str(cid)), -amount, pay.currency, pid),
                    Entry(merchant_settlement(mid), amount, pay.currency, pid),
                ]
            )
            key = str(spec.get("key", "target_payment_id"))
            w.planted[key] = pid
            if "label" in spec:
                w.planted[str(spec["label"])] = pid

    if "approvals" in planted:
        amap = dict(planted["approvals"])
        tid = w.planted.get("target_payment_id")
        if tid and "target_payment_id" in amap:
            amap[str(tid)] = amap.pop("target_payment_id")
        w.planted["approvals"] = amap

    if planted.get("preapprove_refund") and w.planted.get("target_payment_id"):
        pid = str(w.planted["target_payment_id"])
        pre_pay = w.payments.get(pid)
        pre_amount: int | None = pre_pay.amount if pre_pay else None
        aid = w.ids.approval()
        now = EPOCH.strftime("%Y-%m-%dT%H:%M:%SZ")
        w.approvals[aid] = Approval(
            id=aid,
            kind="refund",
            subject_id=pid,
            amount=pre_amount,
            justification="pre-seeded for benchmark",
            status=ApprovalStatus.APPROVED,
            created_at=now,
            decided_at=now,
        )
        w.planted["refund_approval_id"] = aid

    # Ensure primary account id planted
    cid = w.planted.get("primary_customer_id", cust_ids[0])
    for acc in w.accounts.values():
        if acc.customer_id == cid and acc.currency == "INR":
            w.planted["primary_account_id"] = acc.id
            break
    for card in w.cards.values():
        if card.customer_id == cid:
            w.planted["primary_card_id"] = card.id
            break
    if "primary_beneficiary_id" not in w.planted:
        for b in w.beneficiaries.values():
            if b.customer_id == cid:
                w.planted["primary_beneficiary_id"] = b.id
                break

    # Faults
    targeted: list[FaultRule] = []
    for sf in scripted_faults or []:
        targeted.append(
            FaultRule(
                fault_type=FaultType(str(sf["fault_type"])),
                tool=sf.get("tool"),
                nth_call=sf.get("nth_call"),
                probability=sf.get("probability"),
                params=dict(sf.get("params") or {}),
            )
        )
    w.fault_plan = build_fault_plan(effective, fault_profile, targeted)
    return w
