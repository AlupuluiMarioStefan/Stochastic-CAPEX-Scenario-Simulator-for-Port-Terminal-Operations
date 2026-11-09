"""All model parameters in one serialisable object (defaults = the course assignment)."""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass, field, fields
from typing import Dict, List, Optional

from .calendars import BargeSchedule, OpeningHours

SHIP_KINDS = ("feeder", "deep-sea")


class ConfigError(ValueError):
    """Raised for inconsistent model parameters."""


@dataclass(frozen=True)
class Duration:
    """A random or fixed duration, sampled by inverse transform from a uniform number ``u``.

    Using ``u`` (instead of calling a RNG) lets every ship carry its own pre-drawn random
    numbers, which keeps scenario comparisons paired (see ``docs/MODEL.md``).
    """

    dist: str = "fixed"  # "fixed" | "uniform" | "exp"
    value: float = 0.0  # fixed
    low: float = 0.0  # uniform
    high: float = 0.0  # uniform
    mean: float = 0.0  # exp

    @staticmethod
    def fixed(value: float) -> "Duration":
        return Duration("fixed", value=value)

    @staticmethod
    def uniform(low: float, high: float) -> "Duration":
        return Duration("uniform", low=low, high=high)

    @staticmethod
    def exponential(mean: float) -> "Duration":
        return Duration("exp", mean=mean)

    def sample(self, u: float) -> float:
        if self.dist == "fixed":
            return self.value
        if self.dist == "uniform":
            return self.low + (self.high - self.low) * u
        if self.dist == "exp":
            return -self.mean * math.log(1.0 - u)
        raise ConfigError(f"unknown distribution {self.dist!r}")

    @property
    def expected(self) -> float:
        return {"fixed": self.value, "uniform": (self.low + self.high) / 2, "exp": self.mean}[self.dist]

    def validate(self, label: str) -> None:
        if self.dist not in ("fixed", "uniform", "exp"):
            raise ConfigError(f"{label}: unknown distribution {self.dist!r}")
        if self.dist == "uniform" and not 0 <= self.low <= self.high:
            raise ConfigError(f"{label}: need 0 <= low <= high")
        if self.dist == "exp" and self.mean <= 0:
            raise ConfigError(f"{label}: mean must be positive")
        if self.dist == "fixed" and self.value < 0:
            raise ConfigError(f"{label}: value must be >= 0")


@dataclass
class ShipClass:
    """Commercial and docking rules of one ship kind."""

    fee_min: float
    fee_max: float
    fee_limit: float  # quotes above this may make the ship go elsewhere
    divert_prob: float  # probability of diversion when the fee is above the limit
    tow_prob: float  # probability that a tugboat is needed (1.0 = always)
    tow_time: Duration


@dataclass
class TeamConfig:
    name: str
    share: float  # probability that an arriving ship is assigned to this crane team
    unload_hours: float
    capacity: int = 1


@dataclass
class RestackConfig:
    """After ``after_team`` unloads, restacking may be needed (with the team or a hand-over)."""

    after_team: str = "charlie"
    prob: float = 0.25
    keep_prob: float = 0.2  # restack by the same team without releasing it
    hours: float = 2.0
    handover: Dict[str, float] = field(default_factory=lambda: {"alpha": 0.5, "bravo": 0.5})


@dataclass
class CustomsConfig:
    capacity: int = 1
    scan_hours: float = 4.0
    minor_prob: float = 0.08
    minor_hours: float = 1.0
    major_prob: float = 0.02
    major_hours: float = 4.0
    major_team: str = "alpha"  # a major problem needs this crane team while customs is held


@dataclass
class PaperCheckConfig:
    """Port-inspector paper check that runs in parallel with the container scan."""

    inspector_capacity: int = 1
    min_hours: float = 1.0
    max_hours: float = 3.0


@dataclass
class SecurityAlertConfig:
    """Some scans are interrupted ``after_hours`` after they start by a security alert."""

    prob: float = 0.10
    after_hours: float = 1.0
    check_hours: float = 2.0


def _default_teams() -> List[TeamConfig]:
    return [TeamConfig("alpha", 0.40, 8.0), TeamConfig("bravo", 0.35, 11.0), TeamConfig("charlie", 0.25, 16.0)]


@dataclass
class TerminalConfig:
    """Complete parameter set. ``TerminalConfig()`` is the baseline of levels 1-3."""

    # arrivals (used only for generated arrivals; recorded arrivals bring their own times)
    arrival_rate_per_week: float = 8.0
    feeder_share: float = 0.65
    booking_hours: float = 120.0  # announcement -> fee quotation / confirmation
    feeder: ShipClass = field(default_factory=lambda: ShipClass(4000, 12000, 9000, 0.30, 0.30, Duration.fixed(6)))
    deep_sea: ShipClass = field(default_factory=lambda: ShipClass(25000, 60000, 50000, 0.10, 1.0, Duration.exponential(18)))
    # unloading
    teams: List[TeamConfig] = field(default_factory=_default_teams)
    restack: Optional[RestackConfig] = field(default_factory=RestackConfig)
    crane_time_reduction: float = 0.0  # automated cranes: hours saved per unloading
    restack_in_place: bool = False  # automated cranes: the unloading team always restacks itself
    # inspection
    customs: CustomsConfig = field(default_factory=CustomsConfig)
    paper_check: Optional[PaperCheckConfig] = None  # level 4
    security_alert: Optional[SecurityAlertConfig] = None  # level 4
    # calendars and last mile
    opening: OpeningHours = field(default_factory=OpeningHours)
    barge: BargeSchedule = field(default_factory=BargeSchedule)
    sail: Duration = field(default_factory=lambda: Duration.uniform(5, 9))
    # measurement
    warmup_hours: float = 0.0  # ships announced before this are simulated but not measured
    agreed_hours: Dict[str, float] = field(default_factory=lambda: {"feeder": 104.0, "deep-sea": 130.0})

    # ---------------------------------------------------------------- helpers
    def ship_class(self, kind: str) -> ShipClass:
        return self.feeder if kind == "feeder" else self.deep_sea

    def team(self, name: str) -> TeamConfig:
        for t in self.teams:
            if t.name == name:
                return t
        raise ConfigError(f"unknown team {name!r}")

    def copy(self) -> "TerminalConfig":
        return copy.deepcopy(self)

    def validate(self) -> "TerminalConfig":
        def prob(label, p):
            if not 0 <= p <= 1:
                raise ConfigError(f"{label} must be a probability in [0, 1], got {p}")

        if self.arrival_rate_per_week <= 0:
            raise ConfigError("arrival_rate_per_week must be positive")
        prob("feeder_share", self.feeder_share)
        if self.booking_hours < 0 or self.warmup_hours < 0:
            raise ConfigError("booking_hours and warmup_hours must be >= 0")
        for kind in SHIP_KINDS:
            c = self.ship_class(kind)
            if not 0 <= c.fee_min <= c.fee_max:
                raise ConfigError(f"{kind}: need 0 <= fee_min <= fee_max")
            prob(f"{kind}.divert_prob", c.divert_prob)
            prob(f"{kind}.tow_prob", c.tow_prob)
            c.tow_time.validate(f"{kind}.tow_time")
            if kind not in self.agreed_hours:
                raise ConfigError(f"agreed_hours is missing {kind!r}")
        if not self.teams or len({t.name for t in self.teams}) != len(self.teams):
            raise ConfigError("teams must be a non-empty list of uniquely named teams")
        if abs(sum(t.share for t in self.teams) - 1) > 1e-9:
            raise ConfigError("team shares must sum to 1")
        for t in self.teams:
            if t.capacity < 1 or t.unload_hours - self.crane_time_reduction < 0 or t.share < 0:
                raise ConfigError(f"invalid team {t.name!r}")
        names = {t.name for t in self.teams}
        if self.restack is not None:
            r = self.restack
            prob("restack.prob", r.prob)
            prob("restack.keep_prob", r.keep_prob)
            if r.after_team not in names or not set(r.handover) <= names or r.hours < 0:
                raise ConfigError("restack refers to unknown teams or has negative hours")
            if abs(sum(r.handover.values()) - 1) > 1e-9:
                raise ConfigError("restack.handover shares must sum to 1")
        c = self.customs
        prob("customs.minor_prob", c.minor_prob)
        prob("customs.major_prob", c.major_prob)
        if c.minor_prob + c.major_prob > 1 or c.capacity < 1 or c.scan_hours <= 0:
            raise ConfigError("invalid customs settings")
        if c.major_team not in names:
            raise ConfigError(f"customs.major_team {c.major_team!r} is not a team")
        if self.paper_check is not None:
            p = self.paper_check
            if p.inspector_capacity < 1 or not 0 <= p.min_hours <= p.max_hours:
                raise ConfigError("invalid paper_check settings")
        if self.security_alert is not None:
            a = self.security_alert
            prob("security_alert.prob", a.prob)
            if not 0 <= a.after_hours < c.scan_hours:
                raise ConfigError("security_alert.after_hours must be shorter than customs.scan_hours")
        self.sail.validate("sail")
        try:
            self.opening.validate()
            self.barge.validate()
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        return self

    # ---------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TerminalConfig":
        """Build from a (possibly partial) dict; missing keys keep their defaults and an
        explicit ``null`` switches an optional section (restack, paper_check, ...) off."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"unknown config keys: {sorted(unknown)}")
        cfg = cls()
        simple = ("arrival_rate_per_week", "feeder_share", "booking_hours", "crane_time_reduction",
                  "restack_in_place", "warmup_hours")
        for key in simple:
            if key in data:
                setattr(cfg, key, data[key])
        if "agreed_hours" in data:
            cfg.agreed_hours = dict(data["agreed_hours"])
        for key in ("feeder", "deep_sea"):
            if key in data:
                d = dict(data[key])
                d["tow_time"] = Duration(**d["tow_time"]) if isinstance(d.get("tow_time"), dict) else d["tow_time"]
                setattr(cfg, key, ShipClass(**d))
        if "teams" in data:
            cfg.teams = [TeamConfig(**t) for t in data["teams"]]
        for key, klass in (("restack", RestackConfig), ("paper_check", PaperCheckConfig),
                           ("security_alert", SecurityAlertConfig), ("customs", CustomsConfig)):
            if key in data:
                setattr(cfg, key, None if data[key] is None else klass(**data[key]))
        if "opening" in data:
            d = dict(data["opening"]); d["closed_days"] = tuple(d.get("closed_days", (6,)))
            cfg.opening = OpeningHours(**d)
        if "barge" in data:
            d = dict(data["barge"]); d["no_departure_days"] = tuple(d.get("no_departure_days", (6,)))
            cfg.barge = BargeSchedule(**d)
        if "sail" in data:
            cfg.sail = Duration(**data["sail"])
        return cfg.validate()


def security_checks_config() -> TerminalConfig:
    """Level 4: scan and paper check in parallel, with security alerts that interrupt scans."""
    cfg = TerminalConfig()
    cfg.paper_check = PaperCheckConfig()
    cfg.security_alert = SecurityAlertConfig()
    return cfg.validate()


PRESETS = {"baseline": TerminalConfig, "security": security_checks_config}
