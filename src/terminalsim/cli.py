"""Command line interface: ``terminalsim simulate | replicate | invest | config``."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
from pathlib import Path

from . import __version__
from .arrivals import RecordedArrivals
from .config import PRESETS, ConfigError, TerminalConfig
from .experiments import evaluate_investments, replicate, summarize_runs
from .model import TerminalSimulation
from .report import format_investment_report, format_run_report, format_summary_table
from .validation import check_results

DEFAULT_ARRIVALS = Path("data/ship_arrival_information.json")


def _common(p: argparse.ArgumentParser, with_arrivals_default: bool = False) -> None:
    p.add_argument("--preset", choices=sorted(PRESETS), default="baseline",
                   help="baseline = levels 1-3, security = level 4 (parallel checks + alerts)")
    p.add_argument("--config", metavar="JSON", help="config file (overrides the preset; missing keys keep defaults)")
    p.add_argument("--arrivals", metavar="JSON", help="recorded arrivals; omit for generated (Poisson) arrivals")
    p.add_argument("--duration", type=float, help="hours to simulate (default 8760 for generated arrivals)")
    p.add_argument("--seed", type=int, default=None, help="random seed (default: random, printed in the report)")
    p.add_argument("--warmup", type=float, default=None, help="hours of warm-up left out of the KPIs")


def _setup(args, default_warmup=None):
    cfg = TerminalConfig.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8"))) if args.config else PRESETS[args.preset]()
    warmup = args.warmup if args.warmup is not None else default_warmup
    if warmup is not None:
        cfg.warmup_hours = warmup
    cfg.validate()
    arrivals = RecordedArrivals.from_json(args.arrivals) if args.arrivals else None
    duration = args.duration if args.duration is not None else (None if arrivals else 8760.0)
    return cfg, arrivals, duration


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="terminalsim", description="Container terminal discrete-event simulation (SimPy).")
    p.add_argument("--version", action="version", version=f"terminalsim {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("simulate", help="one run with a full report")
    _common(s)
    s.add_argument("--json", metavar="FILE", help="write counters, KPIs and resource stats as JSON")
    s.add_argument("--csv", metavar="FILE", help="write one row per ship")
    s.add_argument("--plot", metavar="PNG", help="turnaround-time plot (needs matplotlib)")

    r = sub.add_parser("replicate", help="many independent runs with confidence intervals")
    _common(r)
    r.add_argument("--runs", type=int, default=20)

    i = sub.add_parser("invest", help="compare investment scenarios (needs recorded arrivals)")
    _common(i)
    i.add_argument("--runs", type=int, default=10)
    i.add_argument("--target", type=float, default=90.0, help="required on-time percentage")
    i.add_argument("--plot", metavar="PNG", help="bar chart of the scenarios (needs matplotlib)")

    c = sub.add_parser("config", help="print a preset as JSON (a starting point for your own config)")
    c.add_argument("--preset", choices=sorted(PRESETS), default="baseline")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "config":
            print(json.dumps(PRESETS[args.preset]().to_dict(), indent=2))
            return 0

        if args.command == "invest":
            arrivals_path = args.arrivals or (str(DEFAULT_ARRIVALS) if DEFAULT_ARRIVALS.exists() else None)
            if not arrivals_path:
                print("error: invest needs --arrivals (e.g. data/ship_arrival_information.json)", file=sys.stderr)
                return 2
            args.arrivals = arrivals_path
            cfg, arrivals, _ = _setup(args, default_warmup=1440.0)
            report = evaluate_investments(arrivals, cfg, runs=args.runs, base_seed=args.seed or 0, target=args.target)
            print(format_investment_report(report))
            if args.plot:
                from .plots import plot_investments

                plot_investments(report, args.plot)
                print(f"\nplot written to {args.plot}")
            return 0

        cfg, arrivals, duration = _setup(args)
        if args.command == "replicate":
            results = replicate(cfg, arrivals, runs=args.runs, duration=duration, base_seed=args.seed or 0)
            print(format_summary_table(summarize_runs(results), args.runs))
            return 0

        results = TerminalSimulation(cfg, arrivals, seed=args.seed).run(duration)
        checks = check_results(results, generated_arrivals=arrivals is None)
        print(format_run_report(results, checks))
        if args.json:
            Path(args.json).write_text(json.dumps(results.to_dict(), indent=2))
        if args.csv:
            names = [f.name for f in dataclasses.fields(results.records[0])] if results.records else []
            with open(args.csv, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(names + ["turnaround"])
                for rec in results.records:
                    w.writerow([getattr(rec, n) for n in names] + [rec.turnaround])
        if args.plot:
            from .plots import plot_turnaround

            plot_turnaround(results, args.plot)
            print(f"\nplot written to {args.plot}")
        return 0 if all(c.passed for c in checks) else 1
    except (ConfigError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
