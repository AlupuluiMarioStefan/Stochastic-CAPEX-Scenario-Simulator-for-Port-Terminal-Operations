"""Opening hours and barge timetable (time is in hours; t = 0 is Monday 00:00, day 6 = Sunday)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class OpeningHours:
    """Cranes and customs work ``open_hour``-``close_hour`` on every day that is not closed."""

    open_hour: float = 6.0
    close_hour: float = 22.0
    closed_days: Tuple[int, ...] = (6,)

    def validate(self) -> None:
        if not 0 <= self.open_hour < self.close_hour <= 24:
            raise ValueError("need 0 <= open_hour < close_hour <= 24")
        if len(set(self.closed_days)) >= 7 or any(d not in range(7) for d in self.closed_days):
            raise ValueError("closed_days must be distinct values in 0..6 and leave one day open")

    def wait_until_open(self, t: float) -> float:
        """Hours to wait from time ``t`` until work may start (0 if the terminal is open)."""
        day, hour = int(t // 24) % 7, t % 24
        if day not in self.closed_days:
            if self.open_hour <= hour < self.close_hour:
                return 0.0
            if hour < self.open_hour:
                return self.open_hour - hour
        for d in range(1, 8):
            if (day + d) % 7 not in self.closed_days:
                return d * 24 - hour + self.open_hour
        raise ValueError("terminal is never open")  # unreachable after validate()


@dataclass(frozen=True)
class BargeSchedule:
    """One barge per day at ``departure_hour`` except on ``no_departure_days``."""

    departure_hour: float = 18.0
    no_departure_days: Tuple[int, ...] = (6,)

    def validate(self) -> None:
        if not 0 <= self.departure_hour < 24:
            raise ValueError("departure_hour must be in [0, 24)")
        if len(set(self.no_departure_days)) >= 7:
            raise ValueError("barges must sail on at least one day")

    def wait_for_departure(self, t: float) -> float:
        """Hours from ``t`` until the next barge that sails (a barge at exactly ``t`` can be caught)."""
        day, hour = int(t // 24) % 7, t % 24
        if hour <= self.departure_hour:
            wait, d = self.departure_hour - hour, day
        else:
            wait, d = 24 + self.departure_hour - hour, (day + 1) % 7
        while d in self.no_departure_days:
            wait, d = wait + 24, (d + 1) % 7
        return wait
