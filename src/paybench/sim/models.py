"""Pydantic entity models for the simulated payments world."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class KycStatus(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class CardStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CANCELLED = "cancelled"


class BeneficiaryStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    REVERSED = "reversed"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class TransferStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class RefundStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class DisputeStatus(StrEnum):
    OPENED = "opened"
    EVIDENCE_REQUESTED = "evidence_requested"
    UNDER_REVIEW = "under_review"
    WON = "won"
    LOST = "lost"
    EXPIRED = "expired"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class DisputeReason(StrEnum):
    UNAUTHORIZED = "unauthorized"
    NOT_RECEIVED = "not_received"
    DUPLICATE = "duplicate"
    NOT_AS_DESCRIBED = "not_as_described"
    AMOUNT_INCORRECT = "amount_incorrect"


class PaymentFlag(StrEnum):
    SUSPECTED_FRAUD = "suspected_fraud"
    NEEDS_REVIEW = "needs_review"


class Customer(StrictModel):
    id: str
    name: str
    email: str
    phone: str
    kyc_status: KycStatus = KycStatus.VERIFIED
    risk_tier: RiskTier = RiskTier.LOW
    verification_factors: dict[str, str] = Field(default_factory=dict)
    locked: bool = False
    locked_until: str | None = None
    failed_verifications: int = 0


class Account(StrictModel):
    id: str
    customer_id: str
    currency: str
    status: AccountStatus = AccountStatus.ACTIVE
    daily_outbound_used: int = 0
    daily_outbound_day: str = ""  # YYYY-MM-DD of last reset tracking
    overdraft: bool = False


class Card(StrictModel):
    id: str
    customer_id: str
    last4: str
    network: str
    status: CardStatus = CardStatus.ACTIVE


class Merchant(StrictModel):
    id: str
    name: str
    category: str
    settlement_account_id: str
    notes: str = ""


class Beneficiary(StrictModel):
    id: str
    customer_id: str
    name: str
    account_ref: str
    added_at: str
    status: BeneficiaryStatus = BeneficiaryStatus.ACTIVE
    flags: list[str] = Field(default_factory=list)


class Payment(StrictModel):
    id: str
    customer_id: str
    merchant_id: str
    amount: int
    currency: str
    status: PaymentStatus = PaymentStatus.SETTLED
    created_at: str
    settled_at: str | None = None
    memo: str = ""
    refunded_amount: int = 0
    flags: list[str] = Field(default_factory=list)
    dispute_id: str | None = None


class Transfer(StrictModel):
    id: str
    from_account: str
    beneficiary_id: str
    amount: int
    currency: str
    status: TransferStatus = TransferStatus.PENDING
    idempotency_key: str | None = None
    created_at: str
    completed_at: str | None = None
    memo: str = ""


class Refund(StrictModel):
    id: str
    payment_id: str
    amount: int
    currency: str
    status: RefundStatus = RefundStatus.COMPLETED
    created_at: str
    reason: str = ""
    idempotency_key: str | None = None


class DisputeEvidence(StrictModel):
    evidence_type: str
    content: str
    submitted_at: str


class Dispute(StrictModel):
    id: str
    payment_id: str
    reason_code: DisputeReason
    status: DisputeStatus = DisputeStatus.OPENED
    opened_at: str
    evidence_deadline: str
    evidence: list[DisputeEvidence] = Field(default_factory=list)


class Approval(StrictModel):
    id: str
    kind: str
    subject_id: str
    amount: int | None = None
    justification: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str
    decided_at: str | None = None
    resolve_at: str | None = None


class Message(StrictModel):
    id: str
    customer_id: str
    text: str
    created_at: str
    direction: str = "outbound"


class CaseLogEntry(StrictModel):
    step: int
    tool: str
    args: dict[str, Any]
    result: dict[str, Any]
    virtual_time: str
    side_effects: list[str] = Field(default_factory=list)
    fault: str | None = None


class IdempotencyRecord(StrictModel):
    key: str
    tool: str
    args_hash: str
    result: dict[str, Any]
    effect_ids: list[str] = Field(default_factory=list)
