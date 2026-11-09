"""Replications, confidence intervals and the investment comparison (level 3)."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .config import TerminalConfig
from .metrics import Results
from .model import TerminalSimulation
from .scenarios import Investment, default_process_options, default_team_options

# two-sided 95 % Student-t critical values for 1..30 degrees of freedom
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160,
         2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056,
         2.052, 2.048, 2.045, 2.042]


@dataclass(frozen=True)
class Summary:
    """Mean of independent replications with a 95 % confidence interval."""

    n: int
    mean: float
    std: float
    ci_low: float
    ci_high: float

    @property
    def half_width(self) -> float:
        return (self.ci_high - self.ci_low) / 2


def summarize(values: Sequence[float]) -> Summary:
    vals = [v for v in values if not math.isnan(v)]
    n = len(vals)
    if n == 0:
        return Summary(0, float("nan"), float("nan"), float("nan"), float("nan"))
    mean = sum(vals) / n
    if n == 1:
        return Summary(1, mean, 0.0, mean, mean)
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    t = _T975[n - 2] if n - 1 <= 30 else 1.96
    hw = t * std / math.sqrt(n)
    return Summary(n, mean, std, mean - hw, mean + hw)


KPIS: Dict[str, Callable[[Results], float]] = {
    "On-time handling (%)": lambda r: r.ontime_percentage(),
    "Mean turnaround, all (h)": lambda r: r.mean_turnaround(),
    "Mean turnaround, feeder (h)": lambda r: r.mean_turnaround("feeder"),
    "Mean turnaround, deep-sea (h)": lambda r: r.mean_turnaround("deep-sea"),
    "Ships diverted (%)": lambda r: r.fraction_diverted(),
    "Loads delivered (%)": lambda r: r.delivered_percentage(),
    "Customs utilisation (%)": lambda r: 100 * r.stations["customs"].utilization,
    "Mean customs wait (h)": lambda r: r.stations["customs"].mean_wait,
    **{f"Team {n} utilisation (%)": (lambda r, n=n: 100 * r.stations[n].utilization if n in r.stations else float("nan"))
       for n in ("alpha", "bravo", "charlie")},
}


def replicate(config: Optional[TerminalConfig] = None, arrivals=None, *, runs: int = 10,
              duration: Optional[float] = None, base_seed: int = 0) -> List[Results]:
    """Independent replications ``base_seed, base_seed + 1, ...``."""
    if runs < 1:
        raise ValueError("runs must be >= 1")
    return [TerminalSimulation(config, arrivals, seed=base_seed + i).run(duration) for i in range(runs)]


def summarize_runs(results: Sequence[Results], kpis: Optional[Dict[str, Callable]] = None) -> Dict[str, Summary]:
    return {name: summarize([f(r) for r in results]) for name, f in (kpis or KPIS).items()}


# --------------------------------------------------------------------------- investments
@dataclass
class ScenarioResult:
    team_option: str
    process_option: str
    cost: float
    ontime: Summary  # on-time percentage over the replications
    gain_vs_base: Summary  # paired difference to the no-investment scenario
    meets_target: bool  # mean >= target (the course's criterion)
    meets_target_confidently: bool  # lower end of the 95 % CI >= target


@dataclass
class InvestmentReport:
    rows: List[ScenarioResult]
    target: float
    runs: int
    warmup_ships: int
    cheapest: Optional[ScenarioResult]  # cheapest whose mean meets the target
    cheapest_confident: Optional[ScenarioResult]  # cheapest whose CI lower bound meets it

    def row(self, team_option: str, process_option: str) -> ScenarioResult:
        return next(r for r in self.rows if r.team_option == team_option and r.process_option == process_option)


def evaluate_investments(
    arrivals,
    config: Optional[TerminalConfig] = None,
    *,
    runs: int = 10,
    base_seed: int = 0,
    target: float = 90.0,
    team_options: Optional[List[Investment]] = None,
    process_options: Optional[List[Investment]] = None,
) -> InvestmentReport:
    """Simulate every combination of team and process investment ``runs`` times.

    All scenarios use the same seeds *and* the same per-ship random numbers, so a ship has the
    same fee, luck and so on in every scenario (common random numbers). The paired differences in
    ``gain_vs_base`` are therefore far less noisy than a comparison of independent runs.
    """
    config = config or TerminalConfig()
    team_options = team_options or default_team_options()
    process_options = process_options or default_process_options()

    per_scenario: Dict[tuple, List[float]] = {}
    warmup_ships = 0
    for team, proc in itertools.product(team_options, process_options):
        cfg = proc.apply(team.apply(config))
        results = replicate(cfg, arrivals, runs=runs, base_seed=base_seed)
        per_scenario[(team.name, proc.name)] = [r.ontime_percentage() for r in results]
        warmup_ships = results[0].nr_warmup_ships
    base_key = (team_options[0].name, process_options[0].name)

    rows: List[ScenarioResult] = []
    for team, proc in itertools.product(team_options, process_options):
        scores = per_scenario[(team.name, proc.name)]
        s = summarize(scores)
        gain = summarize([a - b for a, b in zip(scores, per_scenario[base_key])])
        rows.append(ScenarioResult(team.name, proc.name, team.cost + proc.cost, s, gain,
                                   s.mean >= target, s.ci_low >= target))

    def cheapest(pred):
        best = None
        for r in rows:  # first of equal cost wins, like the original script
            if pred(r) and (best is None or r.cost < best.cost):
                best = r
        return best

    return InvestmentReport(rows, target, runs, warmup_ships,
                            cheapest(lambda r: r.meets_target),
                            cheapest(lambda r: r.meets_target_confidently))
