"""The discrete-event model of the container terminal (SimPy processes)."""

from __future__ import annotations

import random
from typing import List, Optional

import simpy

from .arrivals import GeneratedArrivals, RecordedArrivals
from .config import TerminalConfig
from .metrics import Results, ShipRecord
from .stations import Station

ALERT_CAUSE = "security alert"
_DRAWS = ("fee", "divert", "tow", "tow_time", "team", "restack", "keep", "handover",
          "problem", "alert", "paper", "sail")


class _Draws:
    """The uniform random numbers of one ship, drawn up-front in a fixed order.

    Because every ship owns its numbers, the same ship has the same fee, the same lucky or
    unlucky draws, ... in every scenario that is simulated with the same seed. Scenario
    differences are then caused by the scenario and not by random noise (common random numbers).
    """

    __slots__ = _DRAWS

    def __init__(self, seed: int, ship_id: int):
        rng = random.Random(f"{seed}:ship:{ship_id}")
        for name in _DRAWS:
            setattr(self, name, rng.random())


def _pick(options, u: float):
    """Pick a key from ``[(key, probability), ...]`` with the uniform number ``u``."""
    acc = 0.0
    for key, p in options:
        acc += p
        if u < acc:
            return key
    return options[-1][0]


class TerminalSimulation:
    """Simulates ships through booking, docking, unloading, inspection and barge delivery.

    Args:
        config: model parameters (``TerminalConfig()`` = course baseline).
        arrivals: ``GeneratedArrivals`` (default, from the config) or ``RecordedArrivals``.
        seed: reproducible results; ``None`` picks a random seed (stored in the results).
    """

    def __init__(self, config: Optional[TerminalConfig] = None, arrivals=None, seed: Optional[int] = None):
        self.config = (config or TerminalConfig()).validate()
        self.arrivals = arrivals or GeneratedArrivals(self.config.arrival_rate_per_week, self.config.feeder_share)
        self.seed = random.SystemRandom().randrange(2**32) if seed is None else seed
        self.records: List[ShipRecord] = []

    # --------------------------------------------------------------- run
    def run(self, duration: Optional[float] = None) -> Results:
        """Run for ``duration`` hours, or until every recorded ship is finished if ``None``."""
        if duration is None and not self.arrivals.finite:
            raise ValueError("generated arrivals never end; pass a duration")
        env = simpy.Environment()
        cfg = self.config
        self.env = env
        self.teams = {t.name: Station(env, t.name, t.capacity) for t in cfg.teams}
        self.customs = Station(env, "customs", cfg.customs.capacity)
        self.inspector = (
            Station(env, "inspector", cfg.paper_check.inspector_capacity) if cfg.paper_check else None
        )
        self.records = []
        env.process(self._generator(env))
        env.run() if duration is None else env.run(until=duration)
        stations = {s.name: s.stats() for s in [*self.teams.values(), self.customs, self.inspector] if s}
        return Results(cfg, self.seed, env.now, self.records, stations)

    def _generator(self, env):
        for n, (announce, kind) in enumerate(self.arrivals.stream(self.seed)):
            yield env.timeout(max(0.0, announce - env.now))
            rec = ShipRecord(n, kind, env.now, env.now + self.config.booking_hours)
            self.records.append(rec)
            env.process(self._ship(env, rec, _Draws(self.seed, n)))

    # -------------------------------------------------------------- ship
    def _ship(self, env, rec: ShipRecord, u: _Draws):
        cfg = self.config
        cls = cfg.ship_class(rec.kind)

        # Task 1 - booking: wait for the quotation; expensive quotes may divert the ship.
        yield env.timeout(cfg.booking_hours)
        rec.fee = cls.fee_min + (cls.fee_max - cls.fee_min) * u.fee
        if rec.fee > cls.fee_limit:
            rec.fee_above_limit = True
            if u.divert < cls.divert_prob:
                rec.diverted = True
                return

        # Task 2 - docking, with a tugboat if needed (tugboats are not a bottleneck).
        if cls.tow_prob >= 1.0 or u.tow < cls.tow_prob:
            rec.towed = True
            yield env.timeout(cls.tow_time.sample(u.tow_time))
        rec.docked_at = env.now

        # Task 3 - unloading by one crane team (+ optional restacking).
        yield from self._unload(env, rec, u)

        # Task 4 - customs scan (and, in parallel, the paper check).
        started = env.event()
        scan = env.process(self._scan(env, rec, started, u))
        if cfg.security_alert and u.alert < cfg.security_alert.prob:
            rec.alert = True
            env.process(self._alert(env, scan, started))
        if self.inspector:
            yield scan & env.process(self._paper_check(env, rec, u))
        else:
            yield scan
        rec.cleared_at = env.now

        # Task 5 - next barge, then sailing to the inland terminal.
        yield env.timeout(cfg.barge.wait_for_departure(env.now) + cfg.sail.sample(u.sail))
        rec.delivered_at = env.now

    def _unload(self, env, rec: ShipRecord, u: _Draws):
        cfg = self.config
        team = cfg.team(_pick([(t.name, t.share) for t in cfg.teams], u.team))
        station = self.teams[team.name]
        rec.unload_team = team.name
        req, rec.unload_wait = yield from station.acquire()
        yield env.timeout(cfg.opening.wait_until_open(env.now))  # work only in opening hours
        yield env.timeout(team.unload_hours - cfg.crane_time_reduction)
        rec.unload_done_at = env.now

        rs = cfg.restack
        if rs is not None and team.name == rs.after_team and u.restack < rs.prob:
            if cfg.restack_in_place or u.keep < rs.keep_prob:
                rec.restack_team = team.name  # keeps the crane team it already holds
                yield env.timeout(rs.hours)
                station.release(req)
            else:  # hand the ship over to another team
                station.release(req)
                other = _pick(list(rs.handover.items()), u.handover)
                rec.restack_team = other
                req2, _ = yield from self.teams[other].acquire()
                yield env.timeout(rs.hours)
                self.teams[other].release(req2)
            rec.restack_hours = rs.hours
            rec.restacked = True
        else:
            station.release(req)
        rec.unloaded_at = env.now

    def _scan(self, env, rec: ShipRecord, started, u: _Draws):
        cfg, c = self.config, self.config.customs
        req, rec.customs_wait = yield from self.customs.acquire()
        yield env.timeout(cfg.opening.wait_until_open(env.now))
        started.succeed()  # the real scan starts now (queueing does not count towards alerts)
        try:
            yield env.timeout(c.scan_hours)
        except simpy.Interrupt as interruption:
            if interruption.cause == ALERT_CAUSE:
                rec.interrupted = True
                yield env.timeout(cfg.security_alert.check_hours)
                rec.security_checked = True
                yield env.timeout(c.scan_hours - cfg.security_alert.after_hours)
        # Outcome of the scan: minor problem (extra hours) or major problem (needs a crane team).
        if u.problem < c.minor_prob:
            yield env.timeout(c.minor_hours)
            rec.scan_problem = "minor"
        elif u.problem < c.minor_prob + c.major_prob:
            station = self.teams[c.major_team]
            req2, _ = yield from station.acquire()
            yield env.timeout(c.major_hours)
            station.release(req2)
            rec.scan_problem = "major"
        rec.scan_done_at = env.now
        self.customs.release(req)

    def _alert(self, env, scan_process, started):
        """Interrupts the scan ``after_hours`` after it really started (if still running)."""
        yield started
        yield env.timeout(self.config.security_alert.after_hours)
        if scan_process.is_alive:
            scan_process.interrupt(ALERT_CAUSE)

    def _paper_check(self, env, rec: ShipRecord, u: _Draws):
        pc = self.config.paper_check
        req, _ = yield from self.inspector.acquire()
        yield env.timeout(self.config.opening.wait_until_open(env.now))
        yield env.timeout(pc.min_hours + (pc.max_hours - pc.min_hours) * u.paper)
        rec.papers_done_at = env.now
        self.inspector.release(req)
