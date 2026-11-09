"""Ship arrival sources: generated (Poisson) or recorded (JSON file)."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple, Union


class GeneratedArrivals:
    """Poisson arrival process with a feeder/deep-sea mix. Infinite: needs a ``duration``."""

    finite = False

    def __init__(self, rate_per_week: float, feeder_share: float):
        self.rate_per_week, self.feeder_share = rate_per_week, feeder_share

    def stream(self, seed) -> Iterator[Tuple[float, str]]:
        rng = random.Random(f"{seed}:arrivals")
        t = 0.0
        while True:
            t += rng.expovariate(self.rate_per_week / 168)
            yield t, ("feeder" if rng.random() <= self.feeder_share else "deep-sea")


class RecordedArrivals:
    """Fixed arrival times and ship types, e.g. from ``ship_arrival_information.json``."""

    finite = True

    def __init__(self, times: Sequence[float], kinds: Sequence[str]):
        if len(times) != len(kinds):
            raise ValueError("arrival times and ship types must have the same length")
        full = {"F": "feeder", "D": "deep-sea", "feeder": "feeder", "deep-sea": "deep-sea"}
        try:
            pairs = [(float(t), full[k]) for t, k in zip(times, kinds)]
        except KeyError as exc:
            raise ValueError(f"unknown ship type {exc}; use 'F' or 'D'") from exc
        if any(t < 0 for t, _ in pairs):
            raise ValueError("arrival times must be >= 0")
        self.pairs: List[Tuple[float, str]] = sorted(pairs, key=lambda p: p[0])

    def __len__(self) -> int:
        return len(self.pairs)

    @property
    def span(self) -> float:
        return self.pairs[-1][0] if self.pairs else 0.0

    def stream(self, seed=None) -> Iterator[Tuple[float, str]]:
        return iter(self.pairs)

    @classmethod
    def from_dict(cls, data: dict) -> "RecordedArrivals":
        try:
            return cls(data["ship_arrival_times"], data["ship_types"])
        except KeyError as exc:
            raise ValueError(f"arrival file is missing key {exc}") from exc

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "RecordedArrivals":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
