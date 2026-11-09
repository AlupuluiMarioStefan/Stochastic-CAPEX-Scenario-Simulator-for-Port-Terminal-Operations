"""Statistical self-check: does a run behave like the model specification says it should?

Each check compares an observed share with the configured probability and passes when the
difference is within ``Z`` standard errors, so the tolerance adapts to the sample size
(the course template only printed "Expected ~30 %" and left the judgement to the reader).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from .metrics import Results

Z = 3.5


@dataclass
class Check:
    name: str
    observed: float
    expected: float
    n: int
    passed: bool
    note: str = ""


def _share(name: str, successes: int, n: int, p: float, out: List[Check]) -> None:
    if n < 20:
        return  # too few observations to say anything
    sd = math.sqrt(max(p * (1 - p), 1e-12) / n)
    obs = successes / n
    out.append(Check(name, 100 * obs, 100 * p, n, abs(obs - p) <= Z * sd))


def check_results(results: Results, generated_arrivals: bool = True) -> List[Check]:
    """Compare a finished run against its configuration."""
    cfg, recs, out = results.config, results.records, []

    if generated_arrivals and results.end_time > 0:
        weeks = results.end_time / 168
        expected = cfg.arrival_rate_per_week * weeks
        sd = math.sqrt(expected)
        out.append(Check("arrivals per week", len(recs) / weeks, cfg.arrival_rate_per_week, len(recs),
                         abs(len(recs) - expected) <= Z * sd))
        _share("share of feeder ships", sum(r.kind == "feeder" for r in recs), len(recs), cfg.feeder_share, out)

    for kind in ("feeder", "deep-sea"):
        cls = cfg.ship_class(kind)
        quoted = [r for r in recs if r.kind == kind and r.quoted]
        p_above = max(0.0, min(1.0, (cls.fee_max - cls.fee_limit) / (cls.fee_max - cls.fee_min))) if cls.fee_max > cls.fee_min else 0.0
        _share(f"{kind}: share diverted", sum(r.diverted for r in quoted), len(quoted), p_above * cls.divert_prob, out)
        confirmed = [r for r in quoted if not r.diverted]
        if cls.tow_prob < 1:
            _share(f"{kind}: share towed", sum(r.towed for r in confirmed), len(confirmed), cls.tow_prob, out)

    assigned = [r for r in recs if r.unload_team]
    for t in cfg.teams:
        _share(f"share assigned to team {t.name}", sum(r.unload_team == t.name for r in assigned), len(assigned), t.share, out)

    rs = cfg.restack
    if rs:
        done = [r for r in recs if r.unload_team == rs.after_team and r.unloaded_at is not None]
        _share(f"restacking after team {rs.after_team}", sum(r.restacked for r in done), len(done), rs.prob, out)

    scans = [r for r in recs if r.scan_done_at is not None]
    _share("scans with a minor problem", sum(r.scan_problem == "minor" for r in scans), len(scans), cfg.customs.minor_prob, out)
    _share("scans with a major problem", sum(r.scan_problem == "major" for r in scans), len(scans), cfg.customs.major_prob, out)
    if cfg.security_alert:
        reached = [r for r in recs if r.docked_at is not None and r.unloaded_at is not None]
        _share("scans with a security alert", sum(r.alert for r in reached), len(reached), cfg.security_alert.prob, out)

    # Operating-point sanity check from the course: >= 95 % of confirmed ships are delivered in a year.
    confirmed = sum(1 for r in recs if r.quoted and not r.diverted)
    if generated_arrivals and confirmed >= 50 and results.end_time >= 4000:
        delivered = results.delivered_percentage()
        out.append(Check("loads delivered (>= 95 %)", delivered, 95.0, confirmed, delivered >= 95.0, "lower bound"))
    return out


def all_passed(checks: List[Check]) -> bool:
    return all(c.passed for c in checks)
