import math
import unittest

from terminalsim import (RecordedArrivals, TerminalConfig, TerminalSimulation, check_results, evaluate_investments,
                         replicate, summarize, summarize_runs)

from .helpers import DATA


class Statistics(unittest.TestCase):
    def test_summarize_known_values(self):
        s = summarize([1, 2, 3, 4, 5])
        self.assertEqual((s.n, s.mean), (5, 3))
        self.assertAlmostEqual(s.std, math.sqrt(2.5))
        self.assertAlmostEqual(s.half_width, 2.776 * math.sqrt(2.5) / math.sqrt(5), places=6)

    def test_summarize_edge_cases(self):
        self.assertEqual(summarize([4.0]).half_width, 0)
        self.assertTrue(math.isnan(summarize([]).mean))
        self.assertEqual(summarize([1, float("nan"), 3]).n, 2)  # NaN (e.g. no ships of a kind) is skipped


class Replications(unittest.TestCase):
    def test_replicate_uses_consecutive_seeds(self):
        res = replicate(runs=3, duration=1500, base_seed=10)
        self.assertEqual([r.seed for r in res], [10, 11, 12])
        self.assertEqual(res[1].to_dict(), TerminalSimulation(seed=11).run(1500).to_dict())

    def test_summarize_runs(self):
        res = replicate(runs=4, duration=3000)
        table = summarize_runs(res)
        self.assertIn("On-time handling (%)", table)
        self.assertEqual(table["On-time handling (%)"].n, 4)
        self.assertTrue(0 <= table["Customs utilisation (%)"].mean <= 100)

    def test_runs_must_be_positive(self):
        with self.assertRaises(ValueError):
            replicate(runs=0, duration=10)


class Investments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        arrivals = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        cfg = TerminalConfig()
        cfg.warmup_hours = 1440
        cls.report = evaluate_investments(arrivals, cfg, runs=4, base_seed=0, target=90)

    def test_grid_and_costs(self):
        rep = self.report
        self.assertEqual(len(rep.rows), 9)
        self.assertEqual(rep.warmup_ships, 157)
        costs = {(r.team_option, r.process_option): r.cost for r in rep.rows}
        self.assertEqual(costs[("No extra team", "No process investment")], 0)
        self.assertEqual(costs[("Two extra teams", "Automated cranes")], 77_000 + 35_000)
        self.assertEqual(costs[("One extra team", "Second customs team")], 55_000 + 28_000)

    def test_base_has_no_gain_over_itself(self):
        base = self.report.row("No extra team", "No process investment")
        self.assertEqual(base.gain_vs_base.mean, 0)

    def test_automation_clearly_helps(self):
        auto = self.report.row("No extra team", "Automated cranes")
        self.assertGreater(auto.gain_vs_base.ci_low, 0)  # significant under paired comparison

    def test_cheapest_choice_is_consistent(self):
        rep = self.report
        meeting = [r for r in rep.rows if r.meets_target]
        if meeting:
            self.assertEqual(rep.cheapest.cost, min(r.cost for r in meeting))
        confident = [r for r in rep.rows if r.meets_target_confidently]
        if confident:
            self.assertEqual(rep.cheapest_confident.cost, min(r.cost for r in confident))
            self.assertTrue(rep.cheapest_confident.meets_target)
        else:
            self.assertIsNone(rep.cheapest_confident)

    def test_impossible_target(self):
        arrivals = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        rep = evaluate_investments(arrivals, runs=2, target=101)
        self.assertIsNone(rep.cheapest)
        self.assertIsNone(rep.cheapest_confident)


class SelfCheck(unittest.TestCase):
    def test_correct_model_passes(self):
        for seed in range(4):
            checks = check_results(TerminalSimulation(seed=seed).run(8760))
            failed = [c.name for c in checks if not c.passed]
            self.assertEqual(failed, [], f"seed {seed}")
            self.assertGreaterEqual(len(checks), 10)

    def test_check_detects_a_wrong_specification(self):
        """The checks have power: compare a run with a *different* spec and they fail."""
        res = TerminalSimulation(seed=1).run(8760)
        res.config = res.config.copy()
        res.config.feeder_share = 0.30
        res.config.teams[0].share, res.config.teams[2].share = 0.10, 0.55
        failed = {c.name for c in check_results(res) if not c.passed}
        self.assertIn("share of feeder ships", failed)
        self.assertIn("share assigned to team alpha", failed)


class RecordedFile(unittest.TestCase):
    def test_bundled_arrivals(self):
        arr = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        self.assertEqual(len(arr), 968)
        self.assertEqual(sum(1 for _, k in arr.pairs if k == "feeder"), 642)
        self.assertEqual([t for t, _ in arr.pairs], sorted(t for t, _ in arr.pairs))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            RecordedArrivals([1, 2], ["F"])
        with self.assertRaises(ValueError):
            RecordedArrivals([1], ["X"])
        with self.assertRaises(ValueError):
            RecordedArrivals([-1], ["F"])

    def test_all_recorded_ships_finish(self):
        arr = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        res = TerminalSimulation(arrivals=arr, seed=1).run()
        self.assertEqual(len(res.records), 968)
        self.assertEqual(sum(1 for r in res.records if r.delivered_at is not None),
                         sum(1 for r in res.records if not r.diverted))


if __name__ == "__main__":
    unittest.main()
