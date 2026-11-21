import unittest

from tests.domain._hide_helpers import MAP_HALF, ctx_from_case, load_golden
from travian_bot.common import geo, tribe_data
from travian_bot.common.decisions import HideCandidate
from travian_bot.common.models import HideContext, Oasis
from travian_bot.domain import hide_plan as HP

G = load_golden()


class GoldenTables(unittest.TestCase):
    def test_tables_match_old_dispatch(self):
        for tribe, exp in G["tables"].items():
            with self.subTest(tribe=tribe):
                self.assertEqual(HP.unit_speeds(tribe), exp["speeds"])
                self.assertEqual(HP.unit_attacks(tribe), exp["attacks"])

    def test_siege_chief_settler_never_escape(self):
        for tribe in tribe_data.TRIBES:
            for k in ("u7", "u8", "u9", "u10", "hero"):
                self.assertNotIn(k, HP.unit_speeds(tribe))


class GoldenPlan(unittest.TestCase):
    def test_plan_rows_and_recommend_match_old(self):
        n = 0
        for i, c in enumerate(G["cases"]):
            if c["plan"] is None:
                continue
            n += 1
            with self.subTest(case=i):
                ctx = ctx_from_case(c)
                got = HP.plan_at_speed(ctx, c["plan"]["speed"], c["now_ts"], c["arrivals"],
                                       map_half=MAP_HALF, margin=c["cfg"]["margin"])
                rows = [[g.x, g.y, round(g.distance, 9), g.one_way_s, g.back_ts, not g.missed, len(g.covered), len(g.missed),
                         bool(g.safe), g.map_id] for g in got]
                self.assertEqual(rows, c["plan"]["rows"])
                strict, loose = HP.recommend(got), HP.recommend(got, True)
                self.assertEqual(None if strict is None else [strict.x, strict.y], c["plan"]["rec_strict"])
                self.assertEqual(None if loose is None else [loose.x, loose.y], c["plan"]["rec_loose"])
        self.assertGreater(n, 300)

    def test_plan_with_units_uses_slowest(self):
        c = next(c for c in G["cases"] if c["plan"] and len(c["units"]) > 1)
        ctx = ctx_from_case(c)
        a = HP.plan(ctx, c["units"], c["now_ts"], c["arrivals"], map_half=MAP_HALF, margin=c["cfg"]["margin"])
        b = HP.plan_at_speed(ctx, c["plan"]["speed"], c["now_ts"], c["arrivals"], map_half=MAP_HALF, margin=c["cfg"]["margin"])
        self.assertEqual(a, b)


class Basics(unittest.TestCase):
    def ctx(self, oases, blocked=(), tribe="gaul", home=(0, 0)):
        return HideContext(home_x=home[0], home_y=home[1], oases=tuple(oases), blocked=tuple(blocked), tribe=tribe)

    def test_slowest_speed(self):
        self.assertEqual(HP.slowest_speed("gaul", {"u1": 5, "u2": 3}), 6)       # 方陣 7、劍士 6
        self.assertEqual(HP.slowest_speed("gaul", {"u1": 5, "u2": 0}), 7)       # 數量 0 的忽略
        self.assertIsNone(HP.slowest_speed("gaul", {}))
        self.assertIsNone(HP.slowest_speed("gaul", {"u7": 2}))                  # 攻城器不躲
        self.assertIsNone(HP.slowest_speed("gaul", {"u1": 5, "hero": 1}))       # 英雄永遠不帶

    def test_plan_empty_when_speed_unknown(self):
        ctx = self.ctx([Oasis(3, 4, "wood25", True)])
        self.assertEqual(HP.plan(ctx, {"u7": 1}, 1000, [2000], map_half=MAP_HALF), [])
        self.assertEqual(HP.plan(ctx, {}, 1000, [2000], map_half=MAP_HALF), [])

    def test_unknown_tribe_raises(self):
        with self.assertRaises(Exception):
            HP.unit_speeds("nope")

    def test_numbers_by_hand(self):
        # 距離 5（3-4-5）、速度 6 → 單程 3000 秒、back＝1000＋6000；margin 30
        ctx = self.ctx([Oasis(3, 4, "wood25", True)])
        (c,) = HP.plan_at_speed(ctx, 6, 1000, [2000, 7000, 7100], map_half=MAP_HALF)
        self.assertEqual((c.distance, c.one_way_s, c.back_ts, c.map_id), (5.0, 3000, 7000, geo.map_id(3, 4, 200)))
        self.assertEqual(c.covered, (2000,))        # 7000 ≥ 7000－30 → 沒撐過
        self.assertEqual(c.missed, (7000, 7100))
        self.assertEqual((c.x, c.y, c.kind, c.safe), (3, 4, "wood25", True))

    def test_margin_boundary(self):
        ctx = self.ctx([Oasis(3, 4, "k", True)])
        (c,) = HP.plan_at_speed(ctx, 6, 1000, [6969, 6970], map_half=MAP_HALF, margin=30)   # safe_until＝6970
        self.assertEqual((c.covered, c.missed), ((6969,), (6970,)))

    def test_arrival_exactly_now_is_not_covered(self):
        ctx = self.ctx([Oasis(3, 4, "k", True)])
        (c,) = HP.plan_at_speed(ctx, 6, 1000, [1000, 1001], map_half=MAP_HALF)
        self.assertEqual(c.covered, (1001,))        # 嚴格 now < a

    def test_past_arrival_is_neither(self):
        ctx = self.ctx([Oasis(3, 4, "k", True)])
        (c,) = HP.plan_at_speed(ctx, 6, 1000, [900], map_half=MAP_HALF)
        self.assertEqual((c.covered, c.missed), ((), ()))

    def test_blocked_by_map_id_and_sorting(self):
        o = [Oasis(10, 0, "a", None), Oasis(-3, 0, "b", None), Oasis(0, 5, "c", None), Oasis(3, 0, "d", None)]
        ctx = self.ctx(o, blocked=[geo.map_id(0, 5, 200)])
        got = HP.plan_at_speed(ctx, 6, 0, [], map_half=MAP_HALF)
        self.assertEqual([(c.x, c.y) for c in got], [(-3, 0), (3, 0), (10, 0)])   # 同距離依座標；封鎖的被略過

    def test_wraparound_distance(self):
        ctx = self.ctx([Oasis(-199, 0, "a", None)], home=(199, 0))
        (c,) = HP.plan_at_speed(ctx, 6, 0, [], map_half=MAP_HALF)
        self.assertEqual(c.distance, 3.0)           # 寬 401：199→-199 繞過去是 3

    def test_out_of_range_oasis_raises(self):
        ctx = self.ctx([Oasis(201, 0, "a", None)])
        with self.assertRaises(geo.GeoError):
            HP.plan_at_speed(ctx, 6, 0, [], map_half=MAP_HALF)

    def test_recommend(self):
        mk = lambda safe, missed: HideCandidate(0, 0, "k", 1.0, safe, missed=missed)
        rows = [mk(None, ()), mk(True, (5,)), mk(True, ()), mk(False, ())]
        self.assertIs(HP.recommend(rows), rows[2])                       # 要 safe 且撐過全部
        self.assertIs(HP.recommend(rows, include_unverified=True), rows[0])
        self.assertIsNone(HP.recommend([mk(True, (1,))]))
        self.assertIsNone(HP.recommend([]))


if __name__ == "__main__":
    unittest.main()
