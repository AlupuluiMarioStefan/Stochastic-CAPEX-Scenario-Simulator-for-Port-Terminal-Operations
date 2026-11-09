"""Plain-text reports."""

from __future__ import annotations

from typing import Dict, List, Optional

from .experiments import InvestmentReport, Summary
from .metrics import Results
from .validation import Check


def _h(title: str) -> str:
    return f"\n{title}\n{'-' * len(title)}"


def format_run_report(results: Results, checks: Optional[List[Check]] = None) -> str:
    c, cfg = results.counters(), results.config
    out = [f"Container terminal simulation (seed {results.seed}, ended at hour {results.end_time:,.0f})"]

    out.append(_h("Ships"))
    out.append(f"{'':28}{'feeder':>10}{'deep-sea':>10}")
    rows = [("announced", "nr_arrived_ships_{}"), ("quoted", "nr_quoted_ships_{}"),
            ("diverted to other terminal", "nr_diverted_ships_{}"), ("towed", "nr_towed_ships_{}"),
            ("docked", "nr_docked_ships_{}"), ("unloaded", "nr_unloaded_ships_{}"),
            ("cleared by inspection", "nr_scanned_ships_{}"), ("delivered inland", "nr_delivered_loads_{}")]
    for label, key in rows:
        out.append(f"{label:28}{c[key.format('F')]:>10}{c[key.format('D')]:>10}")
    for kind, s in (("feeder", "F"), ("deep-sea", "D")):
        n = c[f"nr_quoted_ships_{s}"]
        if n:
            out.append(f"average fee quoted, {kind}: EUR {c[f'sum_fees_{s}'] / n:,.0f}")

    out.append(_h("Unloading and restacking"))
    for t in cfg.teams:
        out.append(f"team {t.name:8} unloaded {c['unloading_by_' + t.name]:>4}   restacked {c['restacking_by_' + t.name]:>3}"
                   f"   restack hours {results.restacking_hours(t.name):>5.0f}")
    out.append(f"ships needing restacking: {c['nr_restacked_ships']}")

    out.append(_h("Inspection"))
    out.append(f"minor problems: {c['nr_minor_problem']}   major problems: {c['nr_major_problem']}")
    if cfg.paper_check or cfg.security_alert:
        out.append(f"container scans: {c['nr_container_scans']}   paper checks: {c['nr_paper_checks']}"
                   f"   interrupted scans: {c['nr_interrupted_scans']}   security checks: {c['nr_completed_security_checks']}")

    out.append(_h("Service level"))
    if cfg.warmup_hours:
        out.append(f"ships announced before hour {cfg.warmup_hours:,.0f} left out as warm-up: {results.nr_warmup_ships}")
    out.append(f"on-time handling:   {results.ontime_percentage():.1f}%  "
               f"(agreed: feeder {cfg.agreed_hours['feeder']:.0f} h, deep-sea {cfg.agreed_hours['deep-sea']:.0f} h)")
    out.append(f"mean turnaround:    {results.mean_turnaround():.1f} h  (feeder {results.mean_turnaround('feeder'):.1f} h,"
               f" deep-sea {results.mean_turnaround('deep-sea'):.1f} h)")
    out.append(f"ships diverted:     {results.fraction_diverted():.2f}%")
    out.append(f"loads delivered:    {results.delivered_percentage():.1f}% of confirmed ships")

    out.append(_h("Resources"))
    out.append(f"{'resource':10}{'cap':>4}{'util %':>8}{'mean queue':>12}{'max queue':>11}{'mean wait h':>13}{'max wait h':>12}")
    for s in results.stations.values():
        out.append(f"{s.name:10}{s.capacity:>4}{100 * s.utilization:>8.1f}{s.mean_queue_length:>12.2f}"
                   f"{s.max_queue_length:>11}{s.mean_wait:>13.1f}{s.max_wait:>12.1f}")

    if checks:
        out.append(_h("Model self-check (observed vs. specification, tolerance = 3.5 standard errors)"))
        for k in checks:
            out.append(f"  [{'OK' if k.passed else 'FAIL'}] {k.name:34} observed {k.observed:6.1f}   expected {k.expected:6.1f}   (n={k.n})")
    return "\n".join(out)


def format_summary_table(summaries: Dict[str, Summary], runs: int) -> str:
    out = [f"Mean over {runs} replications with 95% confidence interval", ""]
    out.append(f"{'KPI':32}{'mean':>10}{'std':>9}{'95% CI':>22}")
    for name, s in summaries.items():
        out.append(f"{name:32}{s.mean:>10.2f}{s.std:>9.2f}{f'[{s.ci_low:.2f}, {s.ci_high:.2f}]':>22}")
    return "\n".join(out)


def format_investment_report(rep: InvestmentReport) -> str:
    teams = list(dict.fromkeys(r.team_option for r in rep.rows))
    procs = list(dict.fromkeys(r.process_option for r in rep.rows))
    out = [f"On-time handling, mean of {rep.runs} runs (± half-width of the 95% CI); "
           f"{rep.warmup_ships} ships left out as warm-up", ""]
    width = 26
    out.append(f"{'':18}| " + " | ".join(f"{p:<{width}}" for p in procs) + " |")
    out.append("-" * (20 + (width + 3) * len(procs)))
    for t in teams:
        cells = []
        for p in procs:
            r = rep.row(t, p)
            mark = "*" if r.meets_target_confidently else ("+" if r.meets_target else " ")
            cells.append(f"{f'{r.ontime.mean:5.1f}% ± {r.ontime.half_width:3.1f} {mark}':<{width}}")
        out.append(f"{t:<18}| " + " | ".join(cells) + " |")
    out.append(f"\n'+' mean meets the {rep.target:.0f}% target;  '*' the lower end of the 95% CI meets it as well")

    out.append("\nGain over 'no investment' (paired differences, percentage points):")
    for r in rep.rows:
        if r.cost:
            out.append(f"  {r.team_option} + {r.process_option:<22} EUR {r.cost:>7,.0f}   {r.gain_vs_base.mean:+5.1f} pp"
                       f"  [{r.gain_vs_base.ci_low:+.1f}, {r.gain_vs_base.ci_high:+.1f}]")

    def show(title, r):
        if r is None:
            return f"{title}: none reaches {rep.target:.0f}%"
        return (f"{title}: {r.team_option} + {r.process_option}, EUR {r.cost:,.0f}, "
                f"{r.ontime.mean:.1f}% on time")
    out.append("")
    out.append(show("Cheapest option meeting the target (mean)", rep.cheapest))
    out.append(show("Cheapest option meeting it with 95% confidence", rep.cheapest_confident))
    return "\n".join(out)
