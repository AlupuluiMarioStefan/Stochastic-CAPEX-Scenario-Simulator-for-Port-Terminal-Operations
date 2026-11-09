"""Hand-calculated scenarios: with all randomness switched off every timestamp is predictable."""

import unittest

from terminalsim import Duration, TerminalConfig, TerminalSimulation, security_checks_config, with_automated_cranes
from terminalsim.config import CustomsConfig, PaperCheckConfig, RestackConfig, SecurityAlertConfig, ShipClass

from .helpers import deterministic_config, run_fixed


class SingleShip(unittest.TestCase):
    def test_feeder_timeline(self):
        r = run_fixed([0], ["F"])
        s = r.records[0]
        self.assertEqual(s.confirmed, 120)  # booking takes 5 days
        self.assertEqual(s.docked_at, 120)  # no tug needed
        # t=120 is Saturday 00:00 -> wait for 06:00, then 8 h unloading
        self.assertEqual(s.unloaded_at, 134)
        self.assertEqual(s.cleared_at, 138)  # 4 h scan, terminal open
        self.assertEqual(s.delivered_at, 145)  # barge leaves at 18:00 = t 138, sails 7 h
        self.assertEqual(s.turnaround, 25)

    def test_deep_sea_is_always_towed(self):
        s = run_fixed([0], ["D"]).records[0]
        self.assertTrue(s.towed)
        self.assertEqual(s.docked_at, 130)  # 120 + 10 h tow

    def test_diversion(self):
        cfg = deterministic_config(feeder=ShipClass(60000, 60000, 9000, 1.0, 0.0, Duration.fixed(6)))
        r = run_fixed([0], ["F"], cfg)
        s = r.records[0]
        self.assertTrue(s.diverted and s.fee_above_limit)
        self.assertIsNone(s.docked_at)
        self.assertEqual(r.counters()["nr_diverted_ships_F"], 1)
        self.assertEqual(r.fraction_diverted(), 100.0)
        self.assertEqual(r.delivered_percentage(), 0.0)  # no confirmed ships

    def test_fee_below_limit_is_never_diverted(self):
        cfg = deterministic_config(feeder=ShipClass(5000, 5000, 9000, 1.0, 0.0, Duration.fixed(6)))
        self.assertFalse(run_fixed([0], ["F"], cfg).records[0].diverted)

    def test_automated_cranes_save_three_hours(self):
        cfg = with_automated_cranes(deterministic_config())
        self.assertEqual(run_fixed([0], ["F"], cfg).records[0].unloaded_at, 131)

    def test_major_problem_needs_crane_team(self):
        cfg = deterministic_config(customs=CustomsConfig(minor_prob=0.0, major_prob=1.0))
        r = run_fixed([0], ["F"], cfg)
        s = r.records[0]
        self.assertEqual(s.scan_problem, "major")
        self.assertEqual(s.scan_done_at, 134 + 4 + 4)  # scan + 4 h with team alpha
        self.assertEqual(r.stations["alpha"].requests, 2)  # unloading + major problem

    def test_minor_problem(self):
        cfg = deterministic_config(customs=CustomsConfig(minor_prob=1.0, major_prob=0.0))
        self.assertEqual(run_fixed([0], ["F"], cfg).records[0].scan_done_at, 134 + 4 + 1)

    def test_restacking_handover(self):
        cfg = deterministic_config()
        cfg.teams[0].share, cfg.teams[2].share = 0.0, 1.0  # everything to charlie
        cfg.restack = RestackConfig(prob=1.0, keep_prob=0.0, hours=2.0, handover={"bravo": 1.0})
        r = run_fixed([0], ["F"], cfg.validate())
        s = r.records[0]
        self.assertEqual((s.restacked, s.restack_team), (True, "bravo"))
        self.assertEqual(s.unload_done_at, 126 + 16)
        self.assertEqual(s.unloaded_at, 126 + 16 + 2)
        self.assertEqual(r.restacking_hours("bravo"), 2.0)
        self.assertEqual(r.counters()["restacking_by_bravo"], 1)

    def test_restacking_in_place(self):
        cfg = deterministic_config()
        cfg.teams[0].share, cfg.teams[2].share = 0.0, 1.0
        cfg.restack = RestackConfig(prob=1.0, keep_prob=1.0, hours=2.0)
        s = run_fixed([0], ["F"], cfg.validate()).records[0]
        self.assertEqual(s.restack_team, "charlie")

    def test_barge_skips_sunday(self):
        # unloading takes 14 h so the scan ends exactly at Sunday 00:00 (t=144): there is no Sunday
        # barge, the load waits for Monday 18:00 (t=186) and arrives 7 h later
        cfg = deterministic_config()
        cfg.team("alpha").unload_hours = 14.0
        s = run_fixed([0], ["F"], cfg).records[0]
        self.assertEqual(s.cleared_at, 144)
        self.assertEqual(s.delivered_at, 186 + 7)


class Queueing(unittest.TestCase):
    def test_second_ship_waits_for_the_team(self):
        r = run_fixed([0, 1], ["F", "F"])
        a, b = r.records
        self.assertEqual(a.unload_wait, 0)
        self.assertEqual(b.unload_wait, 134 - 121)  # alpha is busy until 134
        self.assertEqual(b.unloaded_at, 142)
        self.assertEqual(r.stations["alpha"].max_queue_length, 1)
        # b is unloaded at Saturday 22:00 = terminal just closed: customs only opens Monday 06:00 (t=174)
        self.assertEqual(a.delivered_at, 145)
        self.assertEqual(b.cleared_at, 174 + 4)
        self.assertEqual(b.delivered_at, 168 + 10 + 8 + 7)  # Monday 10:00 -> 18:00 barge -> 7 h sailing

    def test_extra_capacity_removes_the_queue(self):
        cfg = deterministic_config()
        cfg.team("alpha").capacity = 2
        a, b = run_fixed([0, 1], ["F", "F"], cfg).records
        self.assertEqual(b.unload_wait, 0)

    def test_utilization_is_time_averaged(self):
        r = run_fixed([0], ["F"])
        # alpha is held from 120 (request) to 134; the run ends when the barge arrives (t=145)
        self.assertAlmostEqual(r.stations["alpha"].utilization, 14 / 145)


class SecurityChecks(unittest.TestCase):
    def cfg(self, alert_prob):
        cfg = deterministic_config(
            paper_check=PaperCheckConfig(1, 2.0, 2.0),
            security_alert=SecurityAlertConfig(alert_prob, 1.0, 2.0),
        )
        return cfg.validate()

    def test_alert_interrupts_scan(self):
        r = run_fixed([0], ["F"], self.cfg(1.0))
        s = r.records[0]
        self.assertTrue(s.alert and s.interrupted and s.security_checked)
        # scan starts at 134, alert at 135, check 2 h, remaining 3 h -> 140 (instead of 138)
        self.assertEqual(s.scan_done_at, 140)
        self.assertEqual(s.papers_done_at, 136)
        self.assertEqual(s.cleared_at, 140)  # the ship waits for the slower of both checks
        self.assertEqual(r.counters()["nr_interrupted_scans"], 1)

    def test_no_alert_scan_runs_normally(self):
        s = run_fixed([0], ["F"], self.cfg(0.0)).records[0]
        self.assertFalse(s.interrupted)
        self.assertEqual(s.scan_done_at, 138)
        self.assertEqual(s.cleared_at, 138)

    def test_paper_check_can_be_the_slower_one(self):
        cfg = deterministic_config(paper_check=PaperCheckConfig(1, 6.0, 6.0))
        s = run_fixed([0], ["F"], cfg).records[0]
        self.assertEqual((s.scan_done_at, s.papers_done_at, s.cleared_at), (138, 140, 140))

    def test_alert_clock_starts_when_scan_starts_not_when_ship_queues(self):
        # second ship waits for customs; its alert must fire 1 h after ITS scan starts
        cfg = self.cfg(1.0)
        cfg.paper_check = PaperCheckConfig(2, 2.0, 2.0)
        r = run_fixed([0, 1], ["F", "F"], cfg.validate())
        a, b = r.records
        self.assertTrue(a.interrupted and b.interrupted)
        self.assertGreaterEqual(b.scan_done_at - a.scan_done_at, 6 - 1e-9)  # one full interrupted scan later


class RandomRuns(unittest.TestCase):
    def test_same_seed_same_result(self):
        a = TerminalSimulation(seed=7).run(3000).to_dict(include_records=True)
        b = TerminalSimulation(seed=7).run(3000).to_dict(include_records=True)
        c = TerminalSimulation(seed=8).run(3000).to_dict(include_records=True)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_records_are_consistent(self):
        for cfg in (TerminalConfig(), security_checks_config()):
            for seed in range(3):
                r = TerminalSimulation(cfg, arrivals=None, seed=seed).run(4000)
                for s in r.records:
                    stages = [s.announced, s.confirmed, s.docked_at, s.unload_done_at, s.unloaded_at, s.cleared_at, s.delivered_at]
                    stages = [x for x in stages if x is not None]
                    self.assertEqual(stages, sorted(stages), msg=f"ship {s.ship_id} goes back in time")
                    self.assertGreaterEqual(s.unload_wait, 0)
                    if s.diverted:
                        self.assertIsNone(s.docked_at)
                c = r.counters()
                for k in ("F", "D"):  # the funnel only narrows
                    self.assertLessEqual(c[f"nr_quoted_ships_{k}"], c[f"nr_arrived_ships_{k}"])
                    self.assertLessEqual(c[f"nr_docked_ships_{k}"], c[f"nr_quoted_ships_{k}"] - c[f"nr_diverted_ships_{k}"])
                    self.assertLessEqual(c[f"nr_unloaded_ships_{k}"], c[f"nr_docked_ships_{k}"])
                    self.assertLessEqual(c[f"nr_scanned_ships_{k}"], c[f"nr_unloaded_ships_{k}"])
                    self.assertLessEqual(c[f"nr_delivered_loads_{k}"], c[f"nr_scanned_ships_{k}"])
                done = sum(1 for s in r.records if s.unload_done_at is not None)
                self.assertEqual(sum(c[f"unloading_by_{t.name}"] for t in r.config.teams), done)
                for st in r.stations.values():
                    self.assertTrue(0 <= st.utilization <= 1 + 1e-9, st)

    def test_generated_arrivals_need_a_duration(self):
        with self.assertRaises(ValueError):
            TerminalSimulation(seed=1).run()


class CommonRandomNumbers(unittest.TestCase):
    def test_ship_luck_is_identical_across_scenarios(self):
        from terminalsim import RecordedArrivals
        from .helpers import DATA

        arr = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        base = TerminalSimulation(TerminalConfig(), arr, seed=3).run()
        better = TerminalSimulation(with_automated_cranes(TerminalConfig()), arr, seed=3).run()
        self.assertEqual([r.fee for r in base.records], [r.fee for r in better.records])
        self.assertEqual([r.diverted for r in base.records], [r.diverted for r in better.records])
        self.assertEqual([r.unload_team for r in base.records], [r.unload_team for r in better.records])
        self.assertGreater(better.ontime_percentage(), base.ontime_percentage())

    def test_warmup_ships_are_excluded_from_kpis(self):
        from terminalsim import RecordedArrivals
        from .helpers import DATA

        arr = RecordedArrivals.from_json(DATA / "ship_arrival_information.json")
        cfg = TerminalConfig()
        cfg.warmup_hours = 1440
        r = TerminalSimulation(cfg, arr, seed=1).run()
        self.assertEqual(r.nr_warmup_ships, sum(1 for t, _ in arr.pairs if t < 1440))
        self.assertEqual(r.nr_warmup_ships, 157)
        self.assertTrue(all(s.announced >= 1440 for s in r.measured()))


if __name__ == "__main__":
    unittest.main()
