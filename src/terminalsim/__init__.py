"""terminalsim - a SimPy discrete-event simulation of a container terminal.

Quick start::

    from terminalsim import TerminalSimulation, format_run_report
    results = TerminalSimulation(seed=42).run(duration=8760)
    print(format_run_report(results))
"""

from .arrivals import GeneratedArrivals, RecordedArrivals
from .calendars import BargeSchedule, OpeningHours
from .config import (
    ConfigError,
    Duration,
    TerminalConfig,
    security_checks_config,
)
from .experiments import (
    InvestmentReport,
    Summary,
    evaluate_investments,
    replicate,
    summarize,
    summarize_runs,
)
from .metrics import Results, ShipRecord
from .model import TerminalSimulation
from .report import format_investment_report, format_run_report, format_summary_table
from .scenarios import (
    Investment,
    with_automated_cranes,
    with_extra_teams,
    with_second_customs_team,
)
from .validation import Check, check_results

__version__ = "1.0.0"

__all__ = [
    "BargeSchedule", "Check", "ConfigError", "Duration", "GeneratedArrivals", "Investment",
    "InvestmentReport", "OpeningHours", "RecordedArrivals", "Results", "ShipRecord", "Summary",
    "TerminalConfig", "TerminalSimulation", "check_results", "evaluate_investments",
    "format_investment_report", "format_run_report", "format_summary_table", "replicate",
    "security_checks_config", "summarize", "summarize_runs", "with_automated_cranes",
    "with_extra_teams", "with_second_customs_team",
]
