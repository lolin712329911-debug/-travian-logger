import re
import unittest

from tests.domain._hide_helpers import MAP_HALF, ctx_from_case, load_golden, movement, overview
from travian_bot.common.decisions import HIDE_CODES, HIDE_KINDS, HideCandidate, HideDecision
from travian_bot.domain import hide_decide as HD
from travian_bot.domain import hide_plan as HP

G = load_golden()
NOW = 1_800_000_000


def cfg(**kw):
    base = dict(speeds={"u1": 7, "u2": 6}, attacks={"u1": 15, "u2": 65})
    base.update(kw)
    return HD.HideCfg(**base)


def cand(x, covered, distance, safe=True):
    return HideCandidate(x, 0, "k", distance, safe, covered=tuple(covered))


class GoldenDecide(unittest.TestCase):
    def test_matches_old_decide_and_plan(self):
        kinds = set()
        for i, c in enumerate(G["cases"]):
            with self.subTest(case=i):
                e, k = c["expected"], c["cfg"]
                ov = overview(c["now_ts"], c["arrivals"], c["units"])
                cf = HD.HideCfg(speeds=HP.unit_speeds(c["tribe"]), attacks=HP.unit_attacks(c["tribe"]),
                                lookahead_min=k["lookahead_min"], cluster_min=k["cluster_min"], margin=k["margin"],
                                min_lead_s=k["min_lead_s"], min_attack=k["min_attack"], include_unverified=k["include_unverified"])
                cands = HP.plan(ctx_from_case(c), c["units"], c["now_ts"], HD.hostile_arrivals(ov), map_half=MAP_HALF, margin=cf.margin)
                d = HD.decide(ov, cands, c["units"], cf)
                want = e["reason"]
                if e["code"] == "unknown_speed":                  # 舊鍵 t7 → 新鍵 u7（唯一預期差異）
                    want = re.sub(r"\bt(\d+)", r"u\1", want)
                self.assertEqual((d.kind, d.code, d.reason), (e["action"], e["code"], want))
                self.assertEqual(list(d.scope), e["scope"])
                self.assertEqual([[x.x, x.y, x.one_way_s, x.back_ts] for x in d.candidates],
                                 [r[:4] for r in e["cands"]])
                self.assertEqual([len([a for a in d.scope if a in x.covered]) for x in d.candidates] if d.act else [],
                                 [r[4] for r in e["cands"]] if d.act else [])
                self.assertEqual([list(p) for p in d.units], [["u" + k[1:], n] for k, n in e["units"]])
                self.assertEqual(d.act, e["action"] == "go")
                self.assertEqual(d.chosen, d.candidates[0] if d.act else None)
                kinds.add((d.kind, d.code))
        self.assertEqual(len(kinds), 8)         # 八種結果都有涵蓋到


class Hand(unittest.TestCase):
    def test_value_domains(self):
        self.assertTrue({"skip", "wait", "go"} <= set(HIDE_KINDS))
        self.assertIn("ok", HIDE_CODES)

    def test_no_units_and_zero_counts(self):
        ov = overview(NOW, [NOW + 600])
        for u in ({}, {"u1": 0}):
            d = HD.decide(ov, [], u, cfg())
            self.assertEqual((d.kind, d.code, d.act), ("skip", "no_units", False))

    def test_hero_or_siege_is_unknown_speed(self):
        ov = overview(NOW, [NOW + 600])
        d = HD.decide(ov, [], {"u1": 3, "hero": 1}, cfg())
        self.assertEqual(d.code, "unknown_speed")
        self.assertIn("hero", d.reason)
        self.assertEqual(HD.decide(ov, [], {"u7": 1}, cfg()).code, "unknown_speed")

    def test_weak_is_strictly_greater(self):
        ov = overview(NOW, [NOW + 600])
        c = [cand(1, [NOW + 600], 5)]
        d = HD.decide(ov, c, {"u1": 2}, cfg(min_attack=30))               # 15×2＝30，不超過
        self.assertEqual(d.code, "weak")
        self.assertEqual(d.units, (("u1", 2),))
        self.assertTrue(HD.decide(ov, c, {"u1": 3}, cfg(min_attack=30)).act)  # 45 > 30
        self.assertTrue(HD.decide(ov, c, {"u1": 1}, cfg(min_attack=None)).act)  # None＝不檢查

    def test_unlisted_attack_counts_zero(self):
        self.assertEqual(HD.attack_total({"u1": 2, "u9": 5}, {"u1": 10}), 20)

    def test_lead_boundaries(self):
        c = lambda a: [cand(1, [a], 5)]
        ok = lambda lead: HD.decide(overview(NOW, [NOW + lead]), c(NOW + lead), {"u1": 9}, cfg())
        self.assertEqual(ok(119).code, "too_close")
        self.assertEqual(ok(120).code, "ok")                              # lead < 120 才擋
        self.assertEqual(ok(5400).code, "ok")                             # 90 分整
        d = ok(5401)
        self.assertEqual((d.kind, d.code, d.act), ("wait", "too_far", False))
        self.assertIn("90", d.reason)

    def test_no_future(self):
        d = HD.decide(overview(NOW, [NOW - 5, NOW]), [], {"u1": 1}, cfg())   # a > now 才算未來
        self.assertEqual(d.code, "no_future")
        self.assertEqual(HD.decide(overview(NOW, []), [], {"u1": 1}, cfg()).code, "no_future")

    def test_only_hostile_with_timer_counts(self):
        ov = overview(NOW, [NOW + 600], extra=[movement(("inReturn",), NOW + 300), movement(("outRaid",), NOW + 200),
                                              movement(("inAttack",), None)])
        self.assertEqual(HD.hostile_arrivals(ov), [NOW + 600])

    def test_scope_cluster_and_full_ordering(self):
        a1, a2, a3 = NOW + 600, NOW + 600 + 3600, NOW + 600 + 7201     # a3 超出 120 分 → 不在 scope
        ov = overview(NOW, [a1, a2, a3])
        near_part = cand(1, [a1], 2)             # 只撐過第一波
        far_full = cand(2, [a1, a2, a3], 9)      # 撐過全部
        mid_full = cand(3, [a1, a2], 5)          # 撐過 scope 全部
        d = HD.decide(ov, [near_part, mid_full, far_full], {"u1": 1}, cfg())
        self.assertEqual(d.scope, (a1, a2))
        self.assertTrue(d.full)
        self.assertEqual([c.x for c in d.candidates], [3, 2, 1])         # 先全程（近→遠，依輸入順序），再部分
        self.assertEqual(d.chosen.x, 3)
        self.assertEqual(d.reason, "可一趟撐過範圍內全部來襲")

    def test_partial_sorted_by_coverage_then_distance_and_second_trip_reason(self):
        a = [NOW + 600, NOW + 1200, NOW + 1800]
        ov = overview(NOW, a)
        p1, p2, p3, never = cand(1, a[:1], 1), cand(2, a[:2], 9), cand(3, a[:2], 4), cand(4, a[1:], 1)
        d = HD.decide(ov, [p1, p2, p3, never], {"u1": 1}, cfg())
        self.assertFalse(d.full)
        self.assertEqual([c.x for c in d.candidates], [3, 2, 1])         # 撐 2 波（近→遠）、再撐 1 波；沒撐過第一波的丟掉
        self.assertEqual(d.reason, "只能撐過前幾波，返回後需再發第二趟")

    def test_no_oasis(self):
        ov = overview(NOW, [NOW + 600])
        d = HD.decide(ov, [cand(1, [], 3)], {"u1": 1}, cfg())
        self.assertEqual((d.code, d.units, d.scope), ("no_oasis", (("u1", 1),), (NOW + 600,)))
        self.assertEqual(HD.decide(ov, [], {"u1": 1}, cfg()).code, "no_oasis")

    def test_include_unverified(self):
        ov = overview(NOW, [NOW + 600])
        rows = [cand(1, [NOW + 600], 1, safe=None), cand(2, [NOW + 600], 2, safe=True)]
        self.assertEqual([c.x for c in HD.decide(ov, rows, {"u1": 1}, cfg(include_unverified=True)).candidates], [1, 2])
        self.assertEqual([c.x for c in HD.decide(ov, rows, {"u1": 1}, cfg(include_unverified=False)).candidates], [2])

    def test_returns_frozen_decision(self):
        d = HD.decide(overview(NOW, [NOW + 600]), [cand(1, [NOW + 600], 1)], {"u1": 1}, cfg())
        self.assertIsInstance(d, HideDecision)
        with self.assertRaises(Exception):
            d.act = False


class Helpers(unittest.TestCase):
    def test_sendable_units(self):
        ov = overview(NOW, units_home={"u1": 5, "u2": 0, "hero": 1})
        self.assertEqual(HD.sendable_units(ov), {"u1": 5})
        self.assertEqual(HD.sendable_units(overview(NOW, units_home=None)), {})

    def test_return_windows(self):
        ret = lambda ts, u: movement(("inReturn",), ts, u)
        ov = overview(NOW, [NOW + 3000, NOW + 9000], extra=[
            ret(NOW + 1000, {"u1": 10, "u2": 2, "hero": 1}),     # 有：下一波 NOW+3000，英雄不算
            ret(NOW + 500, {"u1": None}),                         # 兵力讀不到 → 略過
            ret(NOW + 600, {"u1": None, "u2": 3}),                # 一部分讀不到（有的兵種有數字）也略過，不能只算讀得到的
            ret(NOW - 5, {"u1": 4}),                              # 已歸來 → 略過
            ret(NOW + 9500, {"u1": 4}),                           # 歸來後沒有來襲 → 略過
            ret(NOW + 2000, {"hero": 1}),                         # 只有英雄 → 沒兵略過
            movement(("outRaid",), NOW + 700, {"u1": 4}),         # 不是歸來
        ])
        w = HD.return_windows(ov, {"u1": 15, "u2": 65})
        self.assertEqual(len(w), 1)
        self.assertEqual((w[0].return_ts, w[0].units, w[0].attack, w[0].next_attack_ts, w[0].gap_s),
                         (NOW + 1000, (("u1", 10), ("u2", 2)), 150 + 130, NOW + 3000, 2000))

    def test_return_windows_sorted(self):
        ret = lambda ts: movement(("inReturn",), ts, {"u1": 1})
        ov = overview(NOW, [NOW + 5000], extra=[ret(NOW + 3000), ret(NOW + 1000), ret(NOW + 2000)])
        self.assertEqual([x.return_ts for x in HD.return_windows(ov, {})], [NOW + 1000, NOW + 2000, NOW + 3000])


if __name__ == "__main__":
    unittest.main()
