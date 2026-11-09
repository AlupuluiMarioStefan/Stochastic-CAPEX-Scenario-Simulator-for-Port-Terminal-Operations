"""Run from the repository root:  python examples/quickstart.py"""

from terminalsim import TerminalSimulation, check_results, format_run_report

results = TerminalSimulation(seed=42).run(duration=8760)        # one year, reproducible
print(format_run_report(results, check_results(results)))

print("on-time:", f"{results.ontime_percentage():.1f}%")
print("customs utilisation:", f"{results.stations['customs'].utilization:.0%}")
slowest = max((r for r in results.records if r.delivered_at), key=lambda r: r.turnaround)
print(f"slowest ship: #{slowest.ship_id} ({slowest.kind}) needed {slowest.turnaround:.0f} h")
