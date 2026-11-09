"""Optional matplotlib figures (``pip install terminalsim[plots]``)."""

from __future__ import annotations

from typing import Optional

from .experiments import InvestmentReport
from .metrics import Results


def _plt():
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    return plt


def _finish(fig, path: Optional[str]):
    if path:
        fig.savefig(path, dpi=140, bbox_inches="tight")
    return fig


def plot_turnaround(results: Results, path: Optional[str] = None, window: int = 25):
    """Turnaround time against announcement time, with a rolling mean per ship kind."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(10, 5))
    for kind, color in (("feeder", "tab:blue"), ("deep-sea", "tab:orange")):
        pts = [(r.announced, r.turnaround) for r in results.measured() if r.kind == kind and r.delivered_at is not None]
        if not pts:
            continue
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=8, alpha=0.3, color=color)
        roll = [sum(ys[max(0, i - window + 1): i + 1]) / len(ys[max(0, i - window + 1): i + 1]) for i in range(len(ys))]
        ax.plot(xs, roll, color=color, lw=2, label=f"{kind} (rolling mean of {window})")
        ax.axhline(results.config.agreed_hours[kind], color=color, ls="--", lw=1, alpha=0.7)
    ax.set_xlabel("announcement time (hours)")
    ax.set_ylabel("turnaround time (hours)")
    ax.set_title("Turnaround time per ship (dashed: agreed handling time)")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, path)


def plot_utilization(results: Results, path: Optional[str] = None):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7, 4))
    names = list(results.stations)
    ax.bar(names, [100 * results.stations[n].utilization for n in names], color="tab:green")
    ax.set_ylabel("utilisation (%)")
    ax.set_title("Resource utilisation")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    return _finish(fig, path)


def plot_investments(report: InvestmentReport, path: Optional[str] = None):
    """Grouped bars of on-time % with 95 % CI per scenario and the target line."""
    plt = _plt()
    teams = list(dict.fromkeys(r.team_option for r in report.rows))
    procs = list(dict.fromkeys(r.process_option for r in report.rows))
    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.8 / len(procs)
    for j, p in enumerate(procs):
        rows = [report.row(t, p) for t in teams]
        xs = [i + (j - (len(procs) - 1) / 2) * width for i in range(len(teams))]
        ax.bar(xs, [r.ontime.mean for r in rows], width, yerr=[r.ontime.half_width for r in rows], capsize=3, label=p)
    ax.axhline(report.target, color="red", ls="--", label=f"target {report.target:.0f}%")
    ax.set_xticks(range(len(teams)), teams)
    ax.set_ylabel("on-time handling (%)")
    lows = [r.ontime.ci_low for r in report.rows]
    ax.set_ylim(max(0, min(lows + [report.target]) - 5), 100)
    ax.set_title(f"Investment scenarios ({report.runs} runs each, 95% CI)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(procs) + 1, frameon=False)
    ax.grid(axis="y", alpha=0.3)
    return _finish(fig, path)
