#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/parsers/test_buildings.py（ps-03）v0.1（A2a-2b）
樣本：S10a（測試帳號 International 11，埃及，空地建造頁，gid0）、S11a～d（舊服 Asia 8，既有建築頁，佇列滿）。
樣本是以 scrub_sample.py v0.3 脫敏的原始整頁（checksum 一律 000000），見各 .meta.json。
golden：tests/golden/parsers/buildings/build_pages.expected.json；`UPDATE_GOLDEN=1` 會改寫，更新要在交接區塊說明原因。"""
import json
import os
import unittest
from pathlib import Path

from travian_bot.common.models import to_plain
from travian_bot.common.schema import ParseError
from travian_bot.parsers.buildings import find_upgrade_url, parse_build_options, parse_building_cost

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
GOLDEN = ROOT / "golden" / "parsers" / "buildings" / "build_pages.expected.json"
S10 = "S10a_build_gid0_20261104"
S11 = ["S11a_build_gid11_20261102", "S11b_build_gid10_20261102",
       "S11c_build_gid19_20261102", "S11d_build_gid22_20261102"]


def sample(name):
    return (SAMPLES / f"{name}.html").read_text(encoding="utf-8")


def opt(html, gid):
    return next(o for o in parse_build_options(html) if o.gid == gid)


def fragment(blocked="", buttons="", cost=None, extra=""):
    """合成的單一建築頁；cost 預設 (10, 20, 30, 40)。"""
    c = cost or (10, 20, 30, 40)
    res = "".join(f'<div class="inlineIcon resource"><i class="r{i + 1}Big"></i>'
                  f'<span class="value value">\u202d{v}\u202c</span></div>' for i, v in enumerate(c))
    return (f'<div id="build" class="gid11"><div class="upgradeBuilding"><div class="contractWrapper" id="contract">'
            f'<div class="inlineIconList resourceWrapper charges">{res}'
            f'<div class="resource"><i class="cropConsumptionBig"></i><span class="value value">9</span></div></div>'
            f'<div class="upgradeBlocked">{blocked}</div></div>'
            f'<div class="upgradeButtonsContainer">{buttons}</div>{extra}</div></div>')


GREEN = ('<button class="textButtonV1 green new" onclick="this.disabled = true; window.location.href = '
         "'/dorf1.php?id=7&amp;gid=3&amp;action=build&amp;checksum=76c9cd'; return false;\">x</button>")


class TestGolden(unittest.TestCase):
    def build(self):
        cases = [{"sample": S10, "parse_build_options": to_plain(parse_build_options(sample(S10)))}]
        for s in S11:
            h = sample(s)
            cases.append({"sample": s, "parse_building_cost": to_plain(parse_building_cost(h)),
                          "find_upgrade_url": find_upgrade_url(h)})
        return {"schema_version": 1, "cases": cases}

    def test_matches_golden(self):
        cur = self.build()
        if os.environ.get("UPDATE_GOLDEN") == "1":
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.assertEqual(cur, json.loads(GOLDEN.read_text(encoding="utf-8")))


class TestBuildingCost(unittest.TestCase):
    def test_four_samples(self):
        got = [parse_building_cost(sample(s)) for s in S11]
        self.assertEqual([g.cost for g in got], [(740, 920, 645, 185), (3220, 3960, 2230, 990),
                                                 (720, 480, 895, 410), (2595, 1890, 1065, 470)])
        self.assertEqual([g.build_time_s for g in got], [7580, 16570, 4180, 10170])   # section1，不是 section2

    def test_thousand_separator_and_bidi(self):
        self.assertEqual(parse_building_cost(sample(S11[1])).cost[0], 3220)

    def test_research_page_ignores_unit_research_costs(self):
        # 研究院頁另有各兵種研究成本（標記相同）；只能讀 upgradeBuilding（v2.38 的坑）
        self.assertEqual(parse_building_cost(sample(S11[3])).cost, (2595, 1890, 1065, 470))
        self.assertIn("researches", sample(S11[3]))

    def test_afford_and_exchange_facts(self):
        a, b, c, d = [parse_building_cost(sample(s)) for s in S11]
        self.assertEqual((a.resource_short, a.exchange_disabled, a.afford_in_s), (False, None, None))
        self.assertEqual((b.resource_short, b.exchange_disabled, b.afford_in_s), (True, True, 10604))
        self.assertEqual((c.resource_short, c.exchange_disabled, c.afford_in_s), (False, None, None))
        self.assertEqual((d.resource_short, d.exchange_disabled, d.afford_in_s), (True, False, 6952))

    def test_crop_consumption_not_counted(self):
        self.assertEqual(parse_building_cost(fragment()).cost, (10, 20, 30, 40))

    def test_missing_pieces_raise(self):
        for html in ("<div id='build'><div class='research'></div></div>",
                     fragment().replace('<i class="r3Big">', '<i class="x">').replace('r3Big', 'x3'),
                     ""):
            with self.subTest(html=html[:40]):
                with self.assertRaises(ParseError):
                    parse_building_cost(html)

    def test_no_duration_is_none_not_zero(self):
        self.assertIsNone(parse_building_cost(fragment()).build_time_s)

    def test_raw_entity_bidi(self):
        h = fragment().replace("\u202d", "&#x202d;").replace("\u202c", "&#x202c;")
        self.assertEqual(parse_building_cost(h).cost, (10, 20, 30, 40))

    def test_contract_fallback(self):
        h = ('<div id="contract"><i class="r1Big"></i><span class="value value">1</span>'
             '<i class="r2Big"></i><span class="value value">2</span><i class="r3Big"></i><span class="value value">3</span>'
             '<i class="r4Big"></i><span class="value value">4</span></div>')
        self.assertEqual(parse_building_cost(h).cost, (1, 2, 3, 4))


class TestBuildOptions(unittest.TestCase):
    def setUp(self):
        self.opts = parse_build_options(sample(S10))

    def test_all_twelve_in_page_order(self):
        self.assertEqual([o.gid for o in self.opts], [23, 11, 18, 25, 27, 45, 17, 26, 24, 28, 39, 38])

    def test_buildable_ones_have_whitelisted_url(self):
        ok = [o for o in self.opts if o.buildable]
        self.assertEqual([o.gid for o in ok], [23, 11, 18, 25])
        for o in ok:
            self.assertEqual(o.url, f"/dorf2.php?id=21&gid={o.gid}&action=build&checksum=000000")
        self.assertTrue(all(o.url is None for o in self.opts if not o.buildable))

    def test_disabled_green_contractlink_is_not_buildable(self):
        o = opt(sample(S10), 27)       # 寶物庫：綠色 contractLink disabled、交換資源 disabled
        self.assertEqual((o.buildable, o.url, o.resource_short, o.exchange_disabled), (False, None, True, True))
        self.assertEqual(o.cost, (2880, 2740, 2580, 990))
        self.assertEqual(o.build_time_s, 5750)

    def test_exchange_button_states(self):
        self.assertEqual((opt(sample(S10), 45).resource_short, opt(sample(S10), 45).exchange_disabled), (True, False))
        self.assertEqual(opt(sample(S10), 23).exchange_disabled, None)

    def test_conditions_numbers_only(self):
        c = {x.gid: x for x in opt(sample(S10), 17).conditions}
        self.assertEqual((c[15].level, c[15].met, c[15].current), (3, True, None))
        self.assertEqual((c[11].level, c[11].met, c[11].current), (1, False, 0))
        c = {x.gid: x for x in opt(sample(S10), 24).conditions}
        self.assertEqual((c[22].level, c[22].current), (10, 1))

    def test_forbidden_condition_has_no_level(self):
        pal = {x.gid: x for x in opt(sample(S10), 26).conditions}[25]
        self.assertTrue(pal.forbidden)
        self.assertIsNone(pal.level)
        self.assertTrue(pal.met)

    def test_name_drops_list_number_prefix(self):
        self.assertEqual(opt(sample(S10), 23).name, "山洞")

    def test_unbuildable_by_conditions_has_no_duration(self):
        self.assertIsNone(opt(sample(S10), 17).build_time_s)
        self.assertEqual(opt(sample(S10), 17).conditions[2].name, "穀倉")

    def test_language_independent_numbers(self):
        h = sample(S10).replace("等級 3", "Level 3").replace("目前等級", "Current level")
        c = {x.gid: x for x in opt(h, 17).conditions}
        self.assertEqual((c[15].level, c[11].level, c[11].current), (3, 1, 0))

    def test_not_a_build_page(self):
        with self.assertRaises(ParseError):
            parse_build_options("<html><body>login</body></html>")

    def test_build_page_without_wrappers_is_empty(self):
        self.assertEqual(parse_build_options('<div id="build" class="gid0"></div>'), ())


class TestFindUpgradeUrl(unittest.TestCase):
    def test_green_button(self):
        self.assertEqual(find_upgrade_url(fragment(buttons=GREEN)), "/dorf1.php?id=7&gid=3&action=build&checksum=76c9cd")

    def test_queue_full_samples_have_none(self):
        for s in S11:
            with self.subTest(s):
                self.assertIsNone(find_upgrade_url(sample(s)))

    def test_gold_and_ads_and_extra_params_rejected(self):
        for href in ("/dorf2.php?id=35&amp;gid=19&amp;action=build&amp;checksum=3c16cc&amp;buildmaster",
                     "/dorf2.php?id=35&amp;gid=19&amp;action=build&amp;checksum=3c16cc&amp;as=tok",
                     "/dorf2.php?id=35&amp;gid=19&amp;action=build",
                     "https://evil.example/dorf2.php?id=1&amp;gid=1&amp;action=build&amp;checksum=ab"):
            with self.subTest(href):
                btn = (f'<button class="textButtonV1 green new" onclick="window.location.href = \'{href}\';">x</button>')
                self.assertIsNone(find_upgrade_url(fragment(buttons=btn)))

    def test_purple_video_button_not_used(self):
        btn = ('<button class="textButtonV1 purple new videoFeatureButton" onclick="useBuildingVideoFeature('
               "'/dorf2.php?id=21&amp;gid=23&amp;action=build&amp;checksum=4cdfae', undefined);\">x</button>")
        self.assertIsNone(find_upgrade_url(fragment(buttons=btn)))

    def test_disabled_green_not_used(self):
        btn = GREEN.replace("green new", "green new disabled")
        self.assertIsNone(find_upgrade_url(fragment(buttons=btn)))

    def test_old_build_class_still_works(self):
        self.assertIsNotNone(find_upgrade_url(fragment(buttons=GREEN.replace("green new", "green build"))))

    def test_gid0_page_refuses_instead_of_picking_first(self):
        with self.assertRaises(ParseError):
            find_upgrade_url(sample(S10))

    def test_no_upgrade_block_is_none(self):
        self.assertIsNone(find_upgrade_url('<div id="build"></div>'))

    def test_pure_no_state_between_calls(self):
        bad = fragment(buttons=GREEN.replace("action=build", "action=build&amp;buildmaster"))
        self.assertIsNone(find_upgrade_url(bad))
        self.assertIsNone(find_upgrade_url(bad))       # 舊版 _rejected_seen 全域集合：第二次行為必須相同


if __name__ == "__main__":
    unittest.main()
