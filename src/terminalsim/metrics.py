"""Per-ship records and the aggregated results of one simulation run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

from .config import TerminalConfig
from .stations import StationStats

KIND_SUFFIX = {"feeder": "F", "deep-sea": "D"}


@dataclass
class ShipRecord:
    """Everything that happened to one ship. ``None`` means the step was not (yet) reached."""

    ship_id: int
    kind: str
    announced: float
    confirmed: float
    fee: Optional[float] = None
    fee_above_limit: bool = False
    diverted: bool = False
    towed: bool = False
    docked_at: Optional[float] = None
    unload_team: Optional[str] = None  # team the ship was assigned to
    unload_wait: float = 0.0  # hours queued for that team
    unload_done_at: Optional[float] = None  # unloading finished (before restacking)
    restack_team: Optional[str] = None
    restack_hours: float = 0.0
    restacked: bool = False
    unloaded_at: Optional[float] = None  # unloading incl. restacking finished
    customs_wait: float = 0.0
    scan_done_at: Optional[float] = None
    scan_problem: Optional[str] = None  # "minor" | "major"
    alert: bool = False  # a security alert was raised for this scan
    interrupted: bool = False
    security_checked: bool = False
    papers_done_at: Optional[float] = None
    cleared_at: Optional[float] = None  # all inspections finished
    delivered_at: Optional[float] = None

    @property
    def turnaround(self) -> Optional[float]:
        """Hours from fee confirmation until the load reaches the inland terminal."""
        return None if self.delivered_at is None else self.delivered_at - self.confirmed

    @property
    def quoted(self) -> bool:
        return self.fee is not None


@dataclass
class Results:
    config: TerminalConfig
    seed: int
    end_time: float
    records: List[ShipRecord]
    stations: Dict[str, StationStats]

    # ----------------------------------------------------------- selection
    def _sel(self, pred: Callable[[ShipRecord], bool], kind: Optional[str] = None) -> List[ShipRecord]:
        return [r for r in self.records if (kind is None or r.kind == kind) and pred(r)]

    def count(self, pred: Callable[[ShipRecord], bool] = lambda r: True, kind: Optional[str] = None) -> int:
        return len(self._sel(pred, kind))

    def measured(self) -> List[ShipRecord]:
        """Ships announced after the warm-up period."""
        return [r for r in self.records if r.announced >= self.config.warmup_hours]

    @property
    def nr_warmup_ships(self) -> int:
        return len(self.records) - len(self.measured())

    # ---------------------------------------------------------- KPIs
    def turnaround_times(self, kind: Optional[str] = None, measured_only: bool = True) -> List[float]:
        pool = self.measured() if measured_only else self.records
        return [r.turnaround for r in pool if r.delivered_at is not None and (kind is None or r.kind == kind)]

    def mean_turnaround(self, kind: Optional[str] = None) -> float:
        values = self.turnaround_times(kind)
        return sum(values) / len(values) if values else float("nan")

    def ontime_percentage(self) -> float:
        """Share of measured, delivered ships handled within the agreed time of their kind."""
        done = [r for r in self.measured() if r.delivered_at is not None]
        if not done:
            return 0.0
        ok = sum(r.turnaround <= self.config.agreed_hours[r.kind] for r in done)
        return 100.0 * ok / len(done)

    def fraction_diverted(self, kind: Optional[str] = None) -> float:
        quoted = self.count(lambda r: r.quoted, kind)
        return 100.0 * self.count(lambda r: r.diverted, kind) / quoted if quoted else 0.0

    def delivered_percentage(self) -> float:
        """Delivered loads as a share of confirmed (quoted and not diverted) ships."""
        confirmed = self.count(lambda r: r.quoted and not r.diverted)
        return 100.0 * self.count(lambda r: r.delivered_at is not None) / confirmed if confirmed else 0.0

    def restacking_hours(self, team: str) -> float:
        return sum(r.restack_hours for r in self.records if r.restacked and r.restack_team == team)

    def utilization(self) -> Dict[str, float]:
        return {name: s.utilization for name, s in self.stations.items()}

    # ---------------------------------------------- counters (names of the course template)
    def counters(self) -> Dict[str, float]:
        c: Dict[str, float] = {}
        for kind, s in KIND_SUFFIX.items():
            c[f"nr_arrived_ships_{s}"] = self.count(kind=kind)
            c[f"nr_quoted_ships_{s}"] = self.count(lambda r: r.quoted, kind)
            c[f"sum_fees_{s}"] = sum(r.fee for r in self._sel(lambda r: r.quoted, kind))
            c[f"nr_fees_{s}_above"] = self.count(lambda r: r.fee_above_limit, kind)
            c[f"nr_diverted_ships_{s}"] = self.count(lambda r: r.diverted, kind)
            c[f"nr_towed_ships_{s}"] = self.count(lambda r: r.towed, kind)
            c[f"nr_docked_ships_{s}"] = self.count(lambda r: r.docked_at is not None, kind)
            c[f"nr_unloaded_ships_{s}"] = self.count(lambda r: r.unloaded_at is not None, kind)
            c[f"nr_scanned_ships_{s}"] = self.count(lambda r: r.cleared_at is not None, kind)
            c[f"nr_delivered_loads_{s}"] = self.count(lambda r: r.delivered_at is not None, kind)
        for team in self.config.teams:
            c[f"unloading_by_{team.name}"] = self.count(lambda r: r.unload_done_at is not None and r.unload_team == team.name)
            c[f"restacking_by_{team.name}"] = self.count(lambda r: r.restacked and r.restack_team == team.name)
        c["nr_restacked_ships"] = self.count(lambda r: r.restacked)
        c["nr_minor_problem"] = self.count(lambda r: r.scan_problem == "minor")
        c["nr_major_problem"] = self.count(lambda r: r.scan_problem == "major")
        c["nr_container_scans"] = self.count(lambda r: r.scan_done_at is not None)
        c["nr_paper_checks"] = self.count(lambda r: r.papers_done_at is not None)
        c["nr_interrupted_scans"] = self.count(lambda r: r.interrupted)
        c["nr_completed_security_checks"] = self.count(lambda r: r.security_checked)
        return c

    def to_dict(self, include_records: bool = False) -> dict:
        d = {
            "seed": self.seed,
            "end_time": self.end_time,
            "counters": self.counters(),
            "kpis": {
                "ontime_percentage": self.ontime_percentage(),
                "mean_turnaround_all": self.mean_turnaround(),
                "mean_turnaround_feeder": self.mean_turnaround("feeder"),
                "mean_turnaround_deep_sea": self.mean_turnaround("deep-sea"),
                "diverted_percentage": self.fraction_diverted(),
                "delivered_percentage": self.delivered_percentage(),
                "warmup_ships": self.nr_warmup_ships,
            },
            "stations": {n: asdict(s) for n, s in self.stations.items()},
        }
        if include_records:
            d["records"] = [asdict(r) for r in self.records]
        return d
