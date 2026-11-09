"""The generalised calendars must reproduce the course's hard-coded if/elif chains exactly."""

import random
import unittest

from terminalsim import BargeSchedule, OpeningHours


def legacy_wait_until_open(current_time):  # verbatim logic of the original scripts
    week_hr = current_time % 168
    if week_hr < 6: return 6 - week_hr
    elif week_hr < 22: return 0
    elif week_hr < 30: return 30 - week_hr
    elif week_hr < 46: return 0
    elif week_hr < 54: return 54 - week_hr
    elif week_hr < 70: return 0
    elif week_hr < 78: return 78 - week_hr
    elif week_hr < 94: return 0
    elif week_hr < 102: return 102 - week_hr
    elif week_hr < 118: return 0
    elif week_hr < 126: return 126 - week_hr
    elif week_hr < 142: return 0
    else: return 168 - week_hr + 6


def legacy_barge_wait(now):
    day = int(now // 24) % 7
    hour = now % 24
    if hour <= 18:
        wait, departure_day = 18 - hour, day
    else:
        wait, departure_day = 24 + 18 - hour, (day + 1) % 7
    if departure_day == 6:
        wait += 24
    return wait


class CalendarEquivalence(unittest.TestCase):
    def test_opening_hours_match_original(self):
        cal, rng = OpeningHours(), random.Random(1)
        times = [rng.uniform(0, 8760) for _ in range(20000)]
        times += [d * 24 + h for d in range(14) for h in (0, 5.999, 6, 21.999, 22, 23.5)]  # boundaries
        for t in times:
            self.assertAlmostEqual(cal.wait_until_open(t), legacy_wait_until_open(t), places=6, msg=f"t={t}")

    def test_barge_matches_original(self):
        barge, rng = BargeSchedule(), random.Random(2)
        times = [rng.uniform(0, 8760) for _ in range(20000)]
        times += [d * 24 + h for d in range(14) for h in (0, 17.999, 18, 18.001, 23.9)]
        for t in times:
            self.assertAlmostEqual(barge.wait_for_departure(t), legacy_barge_wait(t), places=6, msg=f"t={t}")


class CalendarFeatures(unittest.TestCase):
    def test_sunday_is_closed(self):
        cal = OpeningHours()
        self.assertEqual(cal.wait_until_open(6 * 24 + 10), 20)  # Sunday 10:00 -> Monday 06:00

    def test_custom_schedule(self):
        cal = OpeningHours(open_hour=8, close_hour=18, closed_days=(5, 6))
        self.assertEqual(cal.wait_until_open(4 * 24 + 19), 61)  # Friday 19:00 -> Saturday/Sunday closed -> Monday 08:00

    def test_never_open_is_rejected(self):
        with self.assertRaises(ValueError):
            OpeningHours(closed_days=tuple(range(7))).validate()
        with self.assertRaises(ValueError):
            BargeSchedule(no_departure_days=tuple(range(7))).validate()

    def test_two_closed_days_for_barges(self):
        barge = BargeSchedule(departure_hour=18, no_departure_days=(5, 6))
        self.assertEqual(barge.wait_for_departure(4 * 24 + 20), 22 + 48)  # Fri 20:00 -> Mon 18:00


if __name__ == "__main__":
    unittest.main()
