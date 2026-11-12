"""Integer minor-unit money with checked arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Self


class MoneyError(ValueError):
    """Invalid money operation."""


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """Amount in minor units (paise/cents). Never floats."""

    amount: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount, bool) or not isinstance(self.amount, int):
            raise MoneyError(f"amount must be int, got {type(self.amount).__name__}")
        if not isinstance(self.currency, str) or not self.currency:
            raise MoneyError("currency must be a non-empty string")
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def of(cls, amount: int, currency: str) -> Self:
        return cls(amount=amount, currency=currency)

    def _check_same(self, other: Money) -> None:
        if self.currency != other.currency:
            raise MoneyError(f"currency mismatch: {self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: int) -> Money:
        if isinstance(factor, bool) or not isinstance(factor, int):
            raise MoneyError("scalar must be int")
        return Money(self.amount * factor, self.currency)

    def __rmul__(self, factor: int) -> Money:
        return self.__mul__(factor)

    def is_zero(self) -> bool:
        return self.amount == 0

    def is_positive(self) -> bool:
        return self.amount > 0

    def is_negative(self) -> bool:
        return self.amount < 0

    def to_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "currency": self.currency}


def convert_fx(
    amount: Money,
    quote_currency: str,
    rate: str | Decimal,
) -> Money:
    """Convert using decimal rate; round half-even to nearest minor unit."""
    if amount.currency.upper() == quote_currency.upper():
        return amount
    if isinstance(rate, float):
        raise MoneyError("FX rate must not be float; pass Decimal or string")
    dec_rate = rate if isinstance(rate, Decimal) else Decimal(rate)
    raw = Decimal(amount.amount) * dec_rate
    rounded = int(raw.to_integral_value(rounding=ROUND_HALF_EVEN))
    return Money(rounded, quote_currency.upper())
