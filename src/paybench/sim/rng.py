"""Seeded RNG with independent named sub-streams."""

from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


def _derive_seed(parent: int, name: str) -> int:
    digest = hashlib.sha256(f"{parent}:{name}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63)


@dataclass
class Rng:
    """Wrapper around random.Random with named child streams."""

    seed: int
    _rng: random.Random = field(init=False, repr=False)
    _children: dict[str, Rng] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def child(self, name: str) -> Rng:
        if name not in self._children:
            self._children[name] = Rng(seed=_derive_seed(self.seed, name))
        return self._children[name]

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, seq: list[T]) -> T:
        if not seq:
            raise IndexError("Cannot choose from empty sequence")
        return self._rng.choice(seq)

    def sample(self, population: list[T], k: int) -> list[T]:
        return self._rng.sample(population, k)

    def shuffle(self, xs: list[T]) -> None:
        self._rng.shuffle(xs)

    def gauss(self, mu: float, sigma: float) -> float:
        return self._rng.gauss(mu, sigma)

    def lognormal_int(self, mu: float, sigma: float, minimum: int, maximum: int) -> int:
        """Draw log-normal then clamp to [minimum, maximum] as int."""
        val = int(self._rng.lognormvariate(mu, sigma))
        return max(minimum, min(maximum, val))

    def snapshot(self) -> Rng:
        return deepcopy(self)

    def restore(self, other: Rng) -> None:
        self.seed = other.seed
        self._rng = deepcopy(other._rng)
        self._children = deepcopy(other._children)
