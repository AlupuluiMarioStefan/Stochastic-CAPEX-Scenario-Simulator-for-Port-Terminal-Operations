"""Investment options of the course (extra crane teams, automated cranes, second customs team)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .config import TerminalConfig


def with_extra_teams(cfg: TerminalConfig, n: int) -> TerminalConfig:
    """``n`` extra crane gangs: the first one joins team bravo, the second team charlie."""
    cfg = cfg.copy()
    for i, name in enumerate(("bravo", "charlie"), start=1):
        if n >= i:
            cfg.team(name).capacity += 1
    return cfg


def with_automated_cranes(cfg: TerminalConfig, hours_saved: float = 3.0) -> TerminalConfig:
    """Every unloading is ``hours_saved`` shorter and the unloading team restacks itself."""
    cfg = cfg.copy()
    cfg.crane_time_reduction = hours_saved
    cfg.restack_in_place = True
    return cfg


def with_second_customs_team(cfg: TerminalConfig) -> TerminalConfig:
    cfg = cfg.copy()
    cfg.customs.capacity += 1
    return cfg


@dataclass(frozen=True)
class Investment:
    name: str
    cost: float
    apply: Callable[[TerminalConfig], TerminalConfig]


def default_team_options() -> List[Investment]:
    return [
        Investment("No extra team", 0, lambda c: c),
        Investment("One extra team", 55_000, lambda c: with_extra_teams(c, 1)),
        Investment("Two extra teams", 77_000, lambda c: with_extra_teams(c, 2)),
    ]


def default_process_options() -> List[Investment]:
    return [
        Investment("No process investment", 0, lambda c: c),
        Investment("Automated cranes", 35_000, with_automated_cranes),
        Investment("Second customs team", 28_000, with_second_customs_team),
    ]
