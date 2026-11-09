"""What if the terminal also worked on Sundays? Compare two configurations with confidence intervals.

Run from the repository root:  python examples/custom_scenario.py
"""

from terminalsim import OpeningHours, RecordedArrivals, TerminalConfig, replicate, summarize

arrivals = RecordedArrivals.from_json("data/ship_arrival_information.json")

today = TerminalConfig()
sundays = TerminalConfig(opening=OpeningHours(closed_days=()))     # open 06:00-22:00 seven days a week
for cfg in (today, sundays):
    cfg.warmup_hours = 1440

for name, cfg in (("closed on Sundays", today), ("open on Sundays", sundays)):
    runs = replicate(cfg, arrivals, runs=20, base_seed=0)          # same seeds => paired comparison
    s = summarize([r.ontime_percentage() for r in runs])
    t = summarize([r.mean_turnaround() for r in runs])
    print(f"{name:18} on-time {s.mean:5.1f}% ± {s.half_width:.1f}   mean turnaround {t.mean:5.1f} h ± {t.half_width:.1f}")
