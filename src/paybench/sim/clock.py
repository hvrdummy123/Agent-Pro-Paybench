"""Virtual clock — no wall-clock time."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from paybench.config import EPOCH, MAX_WAIT_S


@dataclass
class Clock:
    """Deterministic virtual clock starting at a fixed epoch."""

    now: datetime = field(default_factory=lambda: EPOCH)
    epoch: datetime = field(default_factory=lambda: EPOCH)

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            self.now = self.now.replace(tzinfo=UTC)
        if self.epoch.tzinfo is None:
            self.epoch = self.epoch.replace(tzinfo=UTC)

    def advance(self, seconds: int) -> datetime:
        if seconds < 0:
            raise ValueError("cannot advance clock by negative seconds")
        self.now = self.now + timedelta(seconds=seconds)
        return self.now

    def wait(self, seconds: int) -> datetime:
        if seconds < 0 or seconds > MAX_WAIT_S:
            raise ValueError(f"wait seconds must be in [0, {MAX_WAIT_S}]")
        return self.advance(seconds)

    def isoformat(self) -> str:
        return self.now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def day_start(self) -> datetime:
        return self.now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    def seconds_since_epoch(self) -> int:
        return int((self.now - self.epoch).total_seconds())

    def snapshot(self) -> Clock:
        return deepcopy(self)

    def restore(self, other: Clock) -> None:
        self.now = other.now
        self.epoch = other.epoch
