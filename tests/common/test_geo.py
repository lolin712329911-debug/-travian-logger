#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cm-07 geo 的測試（A1b）。golden＝舊 dispatch.py v1.8 的離線輸出（MAP_SIZE=401，即 map_half=200）。"""
import unittest
from pathlib import Path

from travian_bot.common import geo, serialize

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "common" / "geo" / "dispatch_v1_8.expected.json"


def _golden():
    return serialize.loads_checked(GOLDEN.read_text(encoding="utf-8"), "geo_golden")


class GeoGoldenTest(unittest.TestCase):
    def setUp(self):
        self.g = _golden()
        self.half = self.g["map_half"]

    def test_distance(self):
        for c in self.g["distance"]:
            with self.subTest(a=c["a"], b=c["b"]):
                self.assertAlmostEqual(geo.distance(tuple(c["a"]), tuple(c["b"]), self.half),
                                       c["expected"], places=12)

    def test_wrap_delta(self):
        for c in self.g["wrap_delta"]:
            with self.subTest(a=c["a"], b=c["b"]):
                self.assertEqual(geo.wrap_delta(c["a"], c["b"], self.half), c["expected"])

    def test_map_id(self):
        for c in self.g["map_id"]:
            with self.subTest(x=c["x"], y=c["y"]):
                self.assertEqual(geo.map_id(c["x"], c["y"], self.half), c["expected"])

    def test_travel_seconds(self):
        for c in self.g["travel"]:
            with self.subTest(dist=c["dist"], speed=c["speed"]):
                self.assertEqual(geo.travel_seconds(c["dist"], c["speed"]), c["expected"])


class GeoWideGoldenTest(unittest.TestCase):
    """golden＝舊 dispatch.py v1.8 在 MAP_SIZE 401 與 801 的離線輸出，以及舊 plan() 內的單程秒數。"""
    DIR = GOLDEN.parent

    def _load(self, name):
        return serialize.loads_checked((self.DIR / name).read_text(encoding="utf-8"), name)

    def test_wrap_distance_map_id_on_two_map_sizes(self):
        cases = self._load("wrap_distance_map_id.expected.json")["cases"]
        self.assertGreater(len(cases), 200)
        self.assertEqual({c["map_half"] for c in cases}, {200, 400})
        for c in cases:
            h, p, q = c["map_half"], tuple(c["p"]), tuple(c["q"])
            with self.subTest(case=c):
                self.assertEqual(geo.wrap_delta(p[0], q[0], h), c["wrap_x"])
                self.assertEqual(geo.wrap_delta(p[1], q[1], h), c["wrap_y"])
                self.assertEqual(geo.distance(p, q, h), c["distance"])
                self.assertEqual(geo.map_id(p[0], p[1], h), c["map_id_p"])

    def test_travel_seconds_matches_old_plan(self):
        cases = self._load("travel_seconds.expected.json")["cases"]
        self.assertGreater(len(cases), 30)
        for c in cases:
            with self.subTest(case=c):
                self.assertEqual(geo.travel_seconds(c["dist"], c["speed"]), c["seconds"])


class GeoUnitTest(unittest.TestCase):
    def test_wrap_around(self):
        self.assertEqual(geo.wrap_delta(200, -200, 200), 1)        # 地圖兩端相鄰
        self.assertEqual(geo.wrap_delta(-100, 100, 200), 200)
        self.assertAlmostEqual(geo.distance((200, 200), (-200, -200), 200), 2 ** 0.5)

    def test_other_map_size(self):
        self.assertEqual(geo.wrap_delta(5, -5, 5), 1)               # 寬 11：10 繞回 1
        self.assertEqual(geo.map_id(-5, 5, 5), 1)                   # 左上角
        self.assertEqual(geo.map_id(5, -5, 5), 121)                 # 右下角＝11*11

    def test_map_id_corners_default_world(self):
        self.assertEqual(geo.map_id(-200, 200, 200), 1)
        self.assertEqual(geo.map_id(200, -200, 200), 401 * 401)

    def test_map_id_rejects_out_of_range(self):
        with self.assertRaises(geo.GeoError):
            geo.map_id(201, 0, 200)
        with self.assertRaises(geo.GeoError):
            geo.map_id(0, -201, 200)
        with self.assertRaises(geo.GeoError):
            geo.map_id(1.5, 0, 200)
        with self.assertRaises(geo.GeoError):
            geo.map_id(True, 0, 200)

    def test_bad_map_half(self):
        for bad in (0, -1, 1.5, True, None, "200"):
            with self.subTest(bad=bad):
                with self.assertRaises(geo.GeoError):
                    geo.wrap_delta(0, 1, bad)

    def test_travel_seconds_validation(self):
        self.assertEqual(geo.travel_seconds(0, 7), 0)
        self.assertEqual(geo.travel_seconds(7, 7), 3600)
        for dist, speed in ((-1, 7), (1, 0), (1, -3), (True, 7), (1, True), (float("nan"), 7)):
            with self.subTest(dist=dist, speed=speed):
                with self.assertRaises(geo.GeoError):
                    geo.travel_seconds(dist, speed)

    def test_duration_roundtrip(self):
        self.assertEqual(geo.parse_duration("0:00:00"), 0)
        self.assertEqual(geo.parse_duration("1:02:03"), 3723)
        self.assertEqual(geo.parse_duration(" 25:11:40 "), 25 * 3600 + 11 * 60 + 40)
        self.assertEqual(geo.fmt_duration(3723), "01:02:03")
        self.assertEqual(geo.fmt_duration(100 * 3600), "100:00:00")
        for s in (0, 1, 59, 60, 3599, 3600, 86399, 86400, 360000):
            self.assertEqual(geo.parse_duration(geo.fmt_duration(s)), s)

    def test_duration_rejects_bad_input(self):
        for bad in ("12:30", "1:60:00", "1:00:60", "-1:00:00", "a:b:c", "1:2:3", "", None, 5):
            with self.subTest(bad=bad):
                with self.assertRaises(geo.GeoError):
                    geo.parse_duration(bad)
        for bad in (-1, 1.5, True, "1"):
            with self.subTest(bad=bad):
                with self.assertRaises(geo.GeoError):
                    geo.fmt_duration(bad)


if __name__ == "__main__":
    unittest.main()
