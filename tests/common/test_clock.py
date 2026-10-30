#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cm-05 clock 的測試（A1b）。golden＝舊 dispatch.parse_time 在 UTC／Europe/London 的離線輸出。"""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from travian_bot.common import clock, serialize
from travian_bot.common.server_profile import ServerTimeError, profile_from_dict

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "common" / "clock" / "dispatch_parse_time.expected.json"


def _profile(tz):
    return profile_from_dict({"server_id": "s1", "base_url": "https://ts1.example.com", "tribe": "gaul",
                              "start_utc": "2026-11-02T08:15:30Z", "server_tz": tz})


class ClockGoldenTest(unittest.TestCase):
    def test_resolve_clock_time_matches_old_parse_time(self):
        data = serialize.loads_checked(GOLDEN.read_text(encoding="utf-8"), "clock_golden")
        self.assertGreater(len(data["cases"]), 50)
        for c in data["cases"]:
            with self.subTest(tz=c["tz"], now=c["now_utc"], text=c["text"]):
                got = clock.resolve_clock_time(c["text"], serialize.parse_utc(c["now_utc"]), _profile(c["tz"]))
                self.assertEqual(serialize.to_utc_str(got), c["expected_utc"])


class UtcNowTest(unittest.TestCase):
    def test_aware_utc(self):
        now = clock.utc_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))
        self.assertLess(abs((datetime.now(timezone.utc) - now).total_seconds()), 5)


class SecsUntilTest(unittest.TestCase):
    NOW = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)

    def test_future_and_past(self):
        self.assertEqual(clock.secs_until("2026-11-02T08:01:30Z", self.NOW), 90)
        self.assertEqual(clock.secs_until("2026-11-02T08:00:00Z", self.NOW), 0)
        self.assertEqual(clock.secs_until("2026-11-02T07:00:00Z", self.NOW), 0)

    def test_rounds_up(self):
        now = self.NOW + timedelta(milliseconds=500)
        self.assertEqual(clock.secs_until("2026-11-02T08:00:10Z", now), 10)   # 9.5 → 10
        self.assertEqual(clock.secs_until("2026-11-02T08:00:01Z", now), 1)    # 0.5 → 1

    def test_accepts_datetime(self):
        self.assertEqual(clock.secs_until(self.NOW + timedelta(seconds=5), self.NOW), 5)

    def test_rejects_bad_input(self):
        with self.assertRaises(serialize.SerializeError):
            clock.secs_until("2026-11-02 08:01:30", self.NOW)
        with self.assertRaises(ServerTimeError):
            clock.secs_until(datetime(2026, 11, 2, 8, 1, 30), self.NOW)       # naive
        with self.assertRaises(ServerTimeError):
            clock.secs_until("2026-11-02T08:01:30Z", datetime(2026, 11, 2, 8, 0, 0))

    def test_default_now(self):
        future = serialize.to_utc_str(clock.utc_now() + timedelta(seconds=100))
        self.assertTrue(98 <= clock.secs_until(future) <= 101)


class ResolveClockTimeTest(unittest.TestCase):
    def test_rolls_to_next_day(self):
        now = datetime(2026, 7, 1, 22, 50, 0, tzinfo=timezone.utc)           # 倫敦 23:50（夏令 +1）
        got = clock.resolve_clock_time("00:10", now, _profile("Europe/London"))
        self.assertEqual(serialize.to_utc_str(got), "2026-07-01T23:10:00Z")   # 倫敦 7/2 00:10

    def test_same_second_is_now(self):
        now = datetime(2026, 11, 2, 8, 0, 0, 900000, tzinfo=timezone.utc)
        got = clock.resolve_clock_time("08:00:00", now, _profile("UTC"))
        self.assertEqual(serialize.to_utc_str(got), "2026-11-02T08:00:00Z")   # 微秒捨去，不進位

    def test_uses_server_timezone_not_utc(self):
        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        got = clock.resolve_clock_time("12:30", now, _profile("Asia/Taipei"))   # 台北此刻 20:00 → 隔天 12:30
        self.assertEqual(serialize.to_utc_str(got), "2026-07-02T04:30:00Z")

    def test_dst_gap_raises(self):
        now = datetime(2026, 3, 29, 0, 30, 0, tzinfo=timezone.utc)            # 倫敦 3/29 01:00 跳到 02:00
        with self.assertRaises(ServerTimeError):
            clock.resolve_clock_time("01:30", now, _profile("Europe/London"))

    def test_dst_overlap_takes_first(self):
        now = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)            # 倫敦 10/25 01:00 BST；01:30 出現兩次
        got = clock.resolve_clock_time("01:30", now, _profile("Europe/London"))
        self.assertEqual(serialize.to_utc_str(got), "2026-10-25T00:30:00Z")   # 第一次（BST）

    def test_rejects_bad_text(self):
        now = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)
        for bad in ("", "24:00", "12:60", "12:00:60", "noon", "12", None, 1200):
            with self.subTest(bad=bad):
                with self.assertRaises(ServerTimeError):
                    clock.resolve_clock_time(bad, now, _profile("UTC"))

    def test_rejects_naive_now(self):
        with self.assertRaises(ServerTimeError):
            clock.resolve_clock_time("12:00", datetime(2026, 11, 2, 8, 0, 0), _profile("UTC"))

    def test_no_quiet_hours_api(self):
        self.assertFalse(hasattr(clock, "in_quiet_hours"))


if __name__ == "__main__":
    unittest.main()
