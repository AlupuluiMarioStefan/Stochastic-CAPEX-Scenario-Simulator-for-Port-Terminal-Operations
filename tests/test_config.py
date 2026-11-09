import json
import unittest

from terminalsim import ConfigError, Duration, TerminalConfig, security_checks_config


class Config(unittest.TestCase):
    def test_roundtrip(self):
        for cfg in (TerminalConfig(), security_checks_config()):
            again = TerminalConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
            self.assertEqual(again.to_dict(), cfg.to_dict())

    def test_bundled_config_files_match_presets(self):
        from .helpers import DATA

        for name, preset in (("baseline", TerminalConfig()), ("security_checks", security_checks_config())):
            data = json.loads((DATA / "configs" / f"{name}.json").read_text())
            self.assertEqual(TerminalConfig.from_dict(data).to_dict(), preset.to_dict())

    def test_partial_dict_keeps_defaults_and_null_disables(self):
        cfg = TerminalConfig.from_dict({"arrival_rate_per_week": 12, "restack": None})
        self.assertEqual(cfg.arrival_rate_per_week, 12)
        self.assertIsNone(cfg.restack)
        self.assertEqual(cfg.feeder_share, 0.65)

    def test_validation(self):
        bad = [
            {"feeder_share": 1.5},
            {"teams": [{"name": "a", "share": 0.5, "unload_hours": 1}]},  # shares do not sum to 1
            {"customs": {"minor_prob": 0.7, "major_prob": 0.5}},
            {"customs": {"major_team": "nobody"}},
            {"security_alert": {"prob": 0.1, "after_hours": 9, "check_hours": 1}},  # after the 4 h scan
            {"unknown_key": 1},
            {"opening": {"open_hour": 22, "close_hour": 6}},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ConfigError):
                TerminalConfig.from_dict(data)

    def test_duration_sampling(self):
        self.assertEqual(Duration.fixed(6).sample(0.7), 6)
        self.assertAlmostEqual(Duration.uniform(5, 9).sample(0.5), 7)
        self.assertAlmostEqual(Duration.exponential(18).sample(1 - 1 / 2.718281828459045), 18, places=6)
        self.assertEqual(Duration.exponential(18).expected, 18)


if __name__ == "__main__":
    unittest.main()
