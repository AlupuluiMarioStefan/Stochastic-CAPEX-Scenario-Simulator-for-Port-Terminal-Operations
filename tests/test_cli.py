import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from terminalsim.cli import main

from .helpers import DATA


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def test_simulate_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            js, cs = Path(tmp, "r.json"), Path(tmp, "r.csv")
            code, out, _ = run_cli("simulate", "--seed", 42, "--json", js, "--csv", cs)
            self.assertEqual(code, 0)
            self.assertIn("Model self-check", out)
            data = json.loads(js.read_text())
            self.assertEqual(data["seed"], 42)
            self.assertIn("nr_arrived_ships_F", data["counters"])
            with cs.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), sum(data["counters"][k] for k in ("nr_arrived_ships_F", "nr_arrived_ships_D")))

    def test_same_seed_same_output(self):
        self.assertEqual(run_cli("simulate", "--seed", 5)[1], run_cli("simulate", "--seed", 5)[1])

    def test_security_preset(self):
        code, out, _ = run_cli("simulate", "--preset", "security", "--seed", 1)
        self.assertEqual(code, 0)
        self.assertIn("interrupted scans", out)
        self.assertIn("inspector", out)

    def test_recorded_arrivals(self):
        code, out, _ = run_cli("simulate", "--arrivals", DATA / "ship_arrival_information.json", "--warmup", 1440, "--seed", 1)
        self.assertEqual(code, 0)
        self.assertIn("left out as warm-up: 157", out)

    def test_replicate(self):
        code, out, _ = run_cli("replicate", "--runs", 3, "--duration", 2000)
        self.assertEqual(code, 0)
        self.assertIn("95% confidence", out)

    def test_invest(self):
        code, out, _ = run_cli("invest", "--arrivals", DATA / "ship_arrival_information.json", "--runs", 2)
        self.assertEqual(code, 0)
        self.assertIn("Automated cranes", out)
        self.assertIn("Cheapest option", out)

    def test_config_command_and_config_file(self):
        code, out, _ = run_cli("config", "--preset", "security")
        self.assertEqual(code, 0)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "c.json")
            cfg = json.loads(out)
            cfg["arrival_rate_per_week"] = 4
            f.write_text(json.dumps(cfg))
            code, out, _ = run_cli("simulate", "--config", f, "--seed", 3)
            self.assertEqual(code, 0)

    def test_errors_return_exit_code_2(self):
        self.assertEqual(run_cli("simulate", "--config", "/nonexistent.json")[0], 2)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "bad.json")
            f.write_text(json.dumps({"feeder_share": 7}))
            code, _, err = run_cli("simulate", "--config", f)
            self.assertEqual(code, 2)
            self.assertIn("feeder_share", err)


if __name__ == "__main__":
    unittest.main()
