"""dm-06 adventure 測試：與舊 travian_hero.plan_adventure 的 1500 組離線輸出逐案比對＋個別規則。"""
import json
import os
import unittest

from travian_bot.common.decisions import AdventureDecision
from travian_bot.common.parsed import Adventure, HeroState
from travian_bot.domain.adventure import AdventureSettings, decide_adventure

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden", "domain", "adventure.cases.json")


def _load():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


def hero(**kw):
    base = dict(status=100, at_home=True, health_pct=90, exp_pct=10, adventures_count=3, regenerating=False,
                home_did=1, in_village_did=None, adventure_no=None, arrival_in_s=None, arrival_at=None,
                difficulty_bonus=False, duration_bonus=False)
    base.update(kw)
    return HeroState(**base)


def adv(n, dur=900, icon="normal", clickable=True):
    return Adventure(number=n, distance=1.0, place="grassland", difficulty=1, hard=False, duration_s=dur,
                     x=None, y=None, icon=icon, clickable=clickable)


A3 = (adv(11, 900), adv(12, 600), adv(13, 1800, "hard"))


class TestGolden(unittest.TestCase):
    def test_matches_old_function(self):
        cases = _load()
        self.assertEqual(len(cases), 1500)
        sends = 0
        for i, c in enumerate(cases):
            going = c["status"] in (50, 9)
            h = hero(status=c["status"], health_pct=c["health"], adventure_no=c["adv_no"],
                     arrival_in_s=55 if going else None, regenerating=c["regen"], difficulty_bonus=c["dbonus"])
            advs = tuple(Adventure(number=a["number"], distance=1.0, place="grassland", difficulty=1, hard=False,
                                   duration_s=a["duration"], x=None, y=None, icon=a["icon"] or None,
                                   clickable=bool(a["has_button"] and not a["disabled"])) for a in c["advs"])
            cfg = c["cfg"]
            s = AdventureSettings(cfg["hero_min_health"], cfg["hero_hard_min_health"],
                                  frozenset(x.strip() for x in cfg["hero_allowed"].split(",")), cfg["hero_skip_on_incoming"])
            d = decide_adventure(h, advs, s, c["incoming"])
            kind, num = c["expected"]
            with self.subTest(i=i):
                self.assertIsInstance(d, AdventureDecision)
                self.assertEqual(d.act, kind == "send")
                self.assertEqual(d.adv_id, num)
                self.assertTrue(d.reason)
            sends += d.act
        self.assertGreater(sends, 50)


class TestRules(unittest.TestCase):
    S = AdventureSettings()

    def go(self, h=None, advs=A3, s=None, incoming=0):
        return decide_adventure(h or hero(), advs, s or self.S, incoming)

    def test_normal_shortest_wins(self):
        d = self.go()
        self.assertEqual((d.act, d.adv_id), (True, 12))

    def test_tie_on_duration_takes_smaller_number(self):
        d = self.go(advs=(adv(15, 600), adv(14, 600)))
        self.assertEqual(d.adv_id, 14)

    def test_hard_preferred_when_allowed_and_healthy(self):
        d = self.go(h=hero(health_pct=95), s=AdventureSettings(allowed=frozenset({"normal", "hard"})))
        self.assertEqual(d.adv_id, 13)

    def test_hard_dropped_when_health_not_high_enough(self):
        s = AdventureSettings(allowed=frozenset({"normal", "hard"}))
        self.assertEqual(self.go(h=hero(health_pct=60), s=s).adv_id, 12)
        self.assertEqual(self.go(h=hero(health_pct=61), s=s).adv_id, 13)

    def test_only_hard_allowed_but_low_health_skips(self):
        d = self.go(h=hero(health_pct=50), s=AdventureSettings(allowed=frozenset({"hard"})))
        self.assertFalse(d.act)

    def test_health_boundary(self):
        self.assertFalse(self.go(h=hero(health_pct=45)).act)
        self.assertTrue(self.go(h=hero(health_pct=46)).act)
        self.assertFalse(self.go(h=hero(health_pct=None)).act)

    def test_going_and_returning(self):
        for st in (50, 9):
            d = self.go(h=hero(status=st, at_home=False, adventure_no=12, arrival_in_s=300))
            self.assertFalse(d.act)

    def test_going_and_returning_reasons_are_specific(self):
        d50 = self.go(h=hero(status=50, at_home=False, adventure_no=12, arrival_in_s=300))
        d9 = self.go(h=hero(status=9, at_home=False, arrival_in_s=120))
        self.assertIn("已出發", d50.reason)
        self.assertIn("返回", d9.reason)
        self.assertIn("120", d9.reason)

    def test_unknown_status_skips_but_none_is_ok_when_home(self):
        self.assertFalse(self.go(h=hero(status=77)).act)
        self.assertTrue(self.go(h=hero(status=None)).act)

    def test_not_home_or_unknown_home_skips(self):
        self.assertFalse(self.go(h=hero(at_home=False)).act)
        self.assertFalse(self.go(h=hero(at_home=None)).act)

    def test_adventure_in_progress_fields_skip(self):
        self.assertFalse(self.go(h=hero(adventure_no=12)).act)
        self.assertFalse(self.go(h=hero(arrival_in_s=30)).act)

    def test_regenerating_and_difficulty_bonus_skip(self):
        self.assertFalse(self.go(h=hero(regenerating=True)).act)
        self.assertFalse(self.go(h=hero(difficulty_bonus=True)).act)

    def test_incoming(self):
        self.assertFalse(self.go(incoming=1).act)
        self.assertFalse(self.go(incoming=None).act)
        self.assertTrue(self.go(incoming=None, s=AdventureSettings(skip_on_incoming=False)).act)
        self.assertTrue(self.go(incoming=3, s=AdventureSettings(skip_on_incoming=False)).act)

    def test_empty_list(self):
        self.assertFalse(self.go(advs=()).act)

    def test_table_not_rendered_skips(self):
        d = self.go(advs=(adv(11, icon=None, clickable=None), adv(12, icon=None, clickable=None)))
        self.assertFalse(d.act)
        self.assertIn("沒有渲染", d.reason)

    def test_unclickable_skipped_not_chosen(self):
        d = self.go(advs=(adv(11, 900), adv(12, 600, clickable=False)))
        self.assertEqual(d.adv_id, 11)
        self.assertFalse(self.go(advs=(adv(11, clickable=False),)).act)
        self.assertFalse(self.go(advs=(adv(11, clickable=None),)).act)

    def test_in_village_did_not_required(self):
        self.assertTrue(self.go(h=hero(in_village_did=None)).act)

    def test_no_tribe_strings_needed_smoke(self):
        # 種族煙霧：決策不依賴種族；換 home_did 等欄位不影響結果
        self.assertEqual(self.go(h=hero(home_did=999)).adv_id, 12)


if __name__ == "__main__":
    unittest.main()
