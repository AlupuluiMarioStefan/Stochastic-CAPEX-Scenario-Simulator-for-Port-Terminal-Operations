"""Shared test helpers: a fully deterministic configuration and the data directory."""

from pathlib import Path

from terminalsim import Duration, RecordedArrivals, TerminalConfig, TerminalSimulation
from terminalsim.config import CustomsConfig, PaperCheckConfig, SecurityAlertConfig, ShipClass, TeamConfig

DATA = Path(__file__).resolve().parent.parent / "data"


def deterministic_config(**overrides) -> TerminalConfig:
    """No randomness left: every ship goes to alpha, pays EUR 5000, needs no problems.

    Hand-calculated timeline of a feeder announced at t=0 (see test_model.py):
    quote 120 -> open at 126 -> unloaded 134 -> scanned 138 -> barge 138 -> delivered 145.
    """
    cfg = TerminalConfig()
    cfg.feeder = ShipClass(5000, 5000, 9000, 0.0, 0.0, Duration.fixed(6))
    cfg.deep_sea = ShipClass(30000, 30000, 50000, 0.0, 1.0, Duration.fixed(10))
    cfg.teams = [TeamConfig("alpha", 1.0, 8.0), TeamConfig("bravo", 0.0, 11.0), TeamConfig("charlie", 0.0, 16.0)]
    cfg.restack = None
    cfg.customs = CustomsConfig(minor_prob=0.0, major_prob=0.0)
    cfg.sail = Duration.fixed(7)
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg.validate()


def run_fixed(times, kinds, cfg=None, seed=0):
    """Run recorded arrivals to completion; returns the Results."""
    return TerminalSimulation(cfg or deterministic_config(), RecordedArrivals(times, kinds), seed=seed).run()
