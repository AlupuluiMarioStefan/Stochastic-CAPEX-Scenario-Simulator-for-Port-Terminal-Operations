"""Check that ``terminalsim`` models the same system as the original course scripts.

Both implementations are run ``--runs`` times (different seeds) and every metric is compared
with a two-sample z-test on the means. If the models are equivalent, |z| stays small (below 3
for essentially every metric).

    python tools/compare_with_legacy.py --runs 60

Needs the scripts in ``legacy/`` and runs from the repository root.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from terminalsim import (RecordedArrivals, TerminalConfig, TerminalSimulation, security_checks_config,  # noqa: E402
                         with_automated_cranes, with_extra_teams, with_second_customs_team)

MARKER = "# --------------------------- SOLUTION CHECK"


def load_legacy(name: str) -> dict:
    """Execute a legacy script up to its solution check and return its namespace."""
    path = ROOT / "legacy" / name
    source = path.read_text().split(MARKER)[0]
    namespace = {"__name__": "legacy"}
    previous = os.getcwd()
    os.chdir(ROOT / "legacy")  # 3_1.py reads its JSON file relative to the working directory
    try:
        exec(compile(source, str(path), "exec"), namespace)
    finally:
        os.chdir(previous)
    return namespace


def z_test(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    se = math.sqrt(va / len(a) + vb / len(b))
    return ma, mb, (ma - mb) / se if se else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=60)
    runs = ap.parse_args().runs
    rows = []

    # ---- levels 1-2: generated arrivals, one year --------------------------------------
    L2 = load_legacy("2_1.py")
    old, new = {}, {}
    for i in range(runs):
        random.seed(i)
        s = L2["ContainerTerminalSimulator"]()
        s.simulate(8760)
        o = {"feeders announced": s.nr_arrived_ships_F, "deep-sea announced": s.nr_arrived_ships_D,
             "feeders diverted": s.nr_diverted_ships_F, "deep-sea diverted": s.nr_diverted_ships_D,
             "feeders towed": s.nr_towed_ships_F, "unloaded by alpha": s.unloading_by_alpha,
             "unloaded by charlie": s.unloading_by_charlie, "ships restacked": s.nr_restacked_ships,
             "minor problems": s.nr_minor_problem, "major problems": s.nr_major_problem,
             "loads delivered": s.nr_delivered_loads_F + s.nr_delivered_loads_D,
             "mean turnaround (h)": L2["compute_average_turnaround_time"](s.turnaround_points, "all"),
             "mean feeder fee": s.sum_fees_F / s.nr_quoted_ships_F}
        r = TerminalSimulation(seed=10_000 + i).run(8760)
        c = r.counters()
        n = {"feeders announced": c["nr_arrived_ships_F"], "deep-sea announced": c["nr_arrived_ships_D"],
             "feeders diverted": c["nr_diverted_ships_F"], "deep-sea diverted": c["nr_diverted_ships_D"],
             "feeders towed": c["nr_towed_ships_F"], "unloaded by alpha": c["unloading_by_alpha"],
             "unloaded by charlie": c["unloading_by_charlie"], "ships restacked": c["nr_restacked_ships"],
             "minor problems": c["nr_minor_problem"], "major problems": c["nr_major_problem"],
             "loads delivered": c["nr_delivered_loads_F"] + c["nr_delivered_loads_D"],
             "mean turnaround (h)": r.mean_turnaround(), "mean feeder fee": c["sum_fees_F"] / c["nr_quoted_ships_F"]}
        for k in o:
            old.setdefault(k, []).append(o[k]); new.setdefault(k, []).append(n[k])
    rows += [(f"L1/2  {k}", *z_test(old[k], new[k])) for k in old]

    # ---- level 3: recorded arrivals, four investment scenarios --------------------------
    L3 = load_legacy("3_1.py")
    info = json.loads((ROOT / "data" / "ship_arrival_information.json").read_text())
    arrivals = RecordedArrivals.from_dict(info)
    scenarios = {
        "no investment": ({}, TerminalConfig()),
        "automated cranes": ({"automated_cranes": True}, with_automated_cranes(TerminalConfig())),
        "two extra teams": ({"extra_gangs": 2}, with_extra_teams(TerminalConfig(), 2)),
        "second customs": ({"second_scanning_crew": True}, with_second_customs_team(TerminalConfig())),
    }
    for name, (kwargs, cfg) in scenarios.items():
        cfg.warmup_hours = 1440
        a, b = [], []
        for i in range(runs):
            random.seed(i)
            s = L3["ContainerTerminalSimulator"]()
            s.simulate(info, **kwargs)
            a.append(L3["compute_ontime_percentage"](s))
            b.append(TerminalSimulation(cfg, arrivals, seed=10_000 + i).run().ontime_percentage())
        rows.append((f"L3    on-time %, {name}", *z_test(a, b)))

    # ---- level 4: parallel scan + paper check, security alerts ---------------------------
    L4 = load_legacy("4_1.py")
    old, new = {}, {}
    for i in range(runs):
        random.seed(i)
        s = L4["ContainerTerminalSimulator"]()
        s.simulate(8760)
        o = {"container scans": s.nr_container_scans, "paper checks": s.nr_paper_checks,
             "interrupted scans": s.nr_interrupted_scans, "security checks": s.nr_completed_security_checks,
             "loads delivered": s.nr_delivered_loads_F + s.nr_delivered_loads_D}
        c = TerminalSimulation(security_checks_config(), seed=10_000 + i).run(8760).counters()
        n = {"container scans": c["nr_container_scans"], "paper checks": c["nr_paper_checks"],
             "interrupted scans": c["nr_interrupted_scans"], "security checks": c["nr_completed_security_checks"],
             "loads delivered": c["nr_delivered_loads_F"] + c["nr_delivered_loads_D"]}
        for k in o:
            old.setdefault(k, []).append(o[k]); new.setdefault(k, []).append(n[k])
    rows += [(f"L4    {k}", *z_test(old[k], new[k])) for k in old]

    print(f"{'metric':34}{'original':>12}{'terminalsim':>13}{'z':>8}")
    for label, a, b, z in rows:
        print(f"{label:34}{a:>12.2f}{b:>13.2f}{z:>8.2f}{'   <-- differs' if abs(z) > 3 else ''}")
    worst = max(abs(r[3]) for r in rows)
    print(f"\n{len(rows)} metrics, {runs} runs each, max |z| = {worst:.2f}")
    return 0 if worst <= 3.5 else 1


if __name__ == "__main__":
    sys.exit(main())
