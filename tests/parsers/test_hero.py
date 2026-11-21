# -*- coding: utf-8 -*-
"""parsers/hero.py（ps-05，A2b）的測試：golden、樣本事實、錯誤案例、舊碼差異、constants.HERO_STATUS。
樣本在 tests/samples/（S18a～d、S17e、S6a～f 的 HUD；測試帳號、未脫敏；說明見 README_A2b.md）。
golden 以頁面時間戳記（Travian.Game.timestamp）當案例 id；沒有時間戳的片段用固定字串。
UPDATE_GOLDEN=1 會改寫 golden；改寫要在交接區塊說明原因。"""
import dataclasses
import json
import os
import re
import unittest

from bs4 import BeautifulSoup

from travian_bot.common import constants as C
from travian_bot.common.schema import ParseError
from travian_bot.parsers import hero as H

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "samples")
_GOLDEN = os.path.join(_HERE, "..", "golden", "parsers", "hero")
_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
_TS_RE = re.compile(r"Travian\.Game\.timestamp\s*=\s*(\d+)")


def _read(name):
    with open(os.path.join(_SAMPLES, name), encoding="utf-8") as f:
        return f.read()


def _ts(h):
    return int(_TS_RE.search(h).group(1))


ADV_ASIA_A = _read("S18a_adventure_raw_asia8_return.html")      # status 9，18 筆
ADV_ASIA_B = _read("S18b_adventure_raw_asia8_return.html")      # status 9，17 筆，體力 24%
ADV_I11 = _read("S18c_adventure_raw_i11_going.html")            # status 50，1 筆
TABLE_FRAGMENT = _read("S18d_adventure_dom_asia8_table.html")   # 渲染後 #heroAdventure（與 S18a 同一時間的表格）
FORM_HOME = _read("S17e_form_i11_hero_home_oasis_link.html")    # 英雄在家（HUD heroHome）
OVERVIEWS = {n: _read(n) for n in sorted(os.listdir(_SAMPLES)) if n.startswith("S6") and n.endswith(".html")}

_EMPTY_DIV = '<div id="heroAdventure" class="contentV2"></div>'


def _with_table(raw=ADV_ASIA_A, fragment=TABLE_FRAGMENT):
    """把渲染後的 #heroAdventure 內容放回原始頁的空 div，等同瀏覽器的 page.content()。"""
    assert raw.count(_EMPTY_DIV) == 1
    return raw.replace(_EMPTY_DIV, _EMPTY_DIV[:-6] + fragment + "</div>")


def _plain(obj):
    return json.loads(json.dumps(dataclasses.asdict(obj), ensure_ascii=False))


def _golden_check(tc, name, produced):
    path = os.path.join(_GOLDEN, name + ".expected.json")
    if _UPDATE:
        os.makedirs(_GOLDEN, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"schema_version": 1, "cases": [{"id": k, **v} for k, v in sorted(produced.items(), key=lambda kv: str(kv[0]))]},
                      f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    with open(path, encoding="utf-8") as f:
        want = {c["id"]: {k: v for k, v in c.items() if k != "id"} for c in json.load(f)["cases"]}
    tc.assertEqual(set(want), set(produced), "golden 的案例與樣本不一致")
    for k in produced:
        with tc.subTest(case=k):
            tc.assertEqual(produced[k], want[k])


def _edit_fragment(fragment, fn):
    soup = BeautifulSoup(fragment, "html.parser")
    fn(soup)
    return str(soup)


class HeroStatusGolden(unittest.TestCase):
    def test_golden(self):
        pages = {_ts(h): h for h in [ADV_ASIA_A, ADV_ASIA_B, ADV_I11, FORM_HOME, *OVERVIEWS.values()]}
        produced = {k: {"state": _plain(H.parse_hero_status(h))} for k, h in pages.items()}
        _golden_check(self, "hero_status", produced)

    def test_adventures_golden(self):
        produced = {}
        for h in (ADV_ASIA_A, ADV_ASIA_B, ADV_I11):
            produced[_ts(h)] = {"adventures": [_plain(a) for a in H.parse_adventures(h)]}
        produced["S18a+S18d"] = {"adventures": [_plain(a) for a in H.parse_adventures(_with_table())]}
        _golden_check(self, "adventures", produced)


class HeroStatusFacts(unittest.TestCase):
    def test_returning_asia8(self):
        s = H.parse_hero_status(ADV_ASIA_A)
        self.assertEqual((s.status, s.at_home, s.health_pct, s.exp_pct, s.adventures_count), (9, False, 51, 59, 18))
        self.assertEqual((s.home_did, s.in_village_did, s.adventure_no), (34593, None, None))
        self.assertEqual((s.arrival_in_s, s.arrival_at), (329, 1794018151))
        self.assertEqual((s.regenerating, s.difficulty_bonus, s.duration_bonus), (False, False, False))

    def test_arrival_at_is_epoch_of_page_plus_arrival_in(self):
        for h in (ADV_ASIA_A, ADV_ASIA_B, ADV_I11):
            s = H.parse_hero_status(h)
            self.assertEqual(s.arrival_at, _ts(h) + s.arrival_in_s)

    def test_going_adventure_i11(self):
        s = H.parse_hero_status(ADV_I11)
        self.assertEqual((s.status, s.at_home, s.adventure_no, s.home_did), (50, False, 85, 65222))
        self.assertEqual((s.health_pct, s.exp_pct, s.adventures_count), (91, 37, 1))
        self.assertEqual(s.arrival_in_s, 1843)

    def test_status_names(self):
        self.assertEqual(C.HERO_STATUS[H.parse_hero_status(ADV_ASIA_A).status], "returning")
        self.assertEqual(C.HERO_STATUS[H.parse_hero_status(ADV_I11).status], "adventure")

    def test_hud_only_page(self):
        """表單頁沒有英雄 JSON：只有 HUD 欄位，其餘 None（英雄在家圖示）。"""
        s = H.parse_hero_status(FORM_HOME)
        self.assertEqual((s.at_home, s.health_pct, s.exp_pct), (True, 82, 37))
        for f in ("status", "regenerating", "home_did", "in_village_did", "adventure_no", "arrival_in_s", "arrival_at",
                  "difficulty_bonus", "duration_bonus", "adventures_count"):
            self.assertIsNone(getattr(s, f), f)

    def test_hud_matches_adventure_page_in_overview(self):
        """同一英雄在概況頁與冒險頁的 HUD 讀到相同數字（S6c 與 S18b 同時段：體力 24%、冒險 17）。"""
        a = H.parse_hero_status(OVERVIEWS["S6c_overview_asia8_return.html"])
        b = H.parse_hero_status(ADV_ASIA_B)
        self.assertEqual((a.health_pct, a.exp_pct, a.adventures_count), (b.health_pct, b.exp_pct, b.adventures_count))
        self.assertEqual((a.health_pct, a.adventures_count), (24, 17))

    def test_hud_all_overviews(self):
        for name, h in OVERVIEWS.items():
            with self.subTest(name):
                s = H.parse_hero_status(h)
                self.assertIsNotNone(s.health_pct)
                self.assertIsNone(s.status)                 # 概況頁沒有英雄 JSON


class AdventureFacts(unittest.TestCase):
    def test_counts_match_hud(self):
        """JSON 筆數與 HUD 冒險數吻合（Asia 8：18／17；Intl 11：1）。"""
        for h in (ADV_ASIA_A, ADV_ASIA_B, ADV_I11):
            self.assertEqual(len(H.parse_adventures(h)), H.parse_hero_status(h).adventures_count)

    def test_fields_without_table(self):
        adv = H.parse_adventures(ADV_ASIA_A)
        self.assertEqual(len(adv), 18)
        a = adv[0]
        self.assertEqual((a.number, a.place, a.difficulty, a.hard, a.duration_s), (18, "grassland", 1, False, 1787))
        self.assertAlmostEqual(a.distance, 9.43398, places=5)      # 保留 JSON 原值，不取整
        self.assertEqual((a.x, a.y, a.icon, a.clickable), (None, None, None, None))
        self.assertEqual({a.difficulty for a in adv}, {1, 2, 3})
        self.assertFalse(any(a.hard for a in adv))                # 樣本沒有 difficulty 0

    def test_going_page_single_adventure_matches_status(self):
        adv = H.parse_adventures(ADV_I11)
        self.assertEqual(len(adv), 1)
        self.assertEqual(adv[0].number, H.parse_hero_status(ADV_I11).adventure_no)
        self.assertEqual((adv[0].place, adv[0].difficulty, adv[0].duration_s), ("hill", 2, 2880))

    def test_with_rendered_table(self):
        adv = H.parse_adventures(_with_table())
        self.assertEqual(len(adv), 18)
        self.assertEqual({a.icon for a in adv}, {"normal"})        # JSON 1／2／3 的圖示全是 normal
        self.assertEqual({a.clickable for a in adv}, {False})      # 英雄在路上：18 顆按鈕全 disabled
        # 其他欄位與沒有表格時相同
        plain = H.parse_adventures(ADV_ASIA_A)
        for a, b in zip(adv, plain):
            self.assertEqual(dataclasses.replace(a, icon=None, clickable=None), b)

    def test_table_without_json_is_error(self):
        with self.assertRaises(ParseError):
            H.parse_adventures(TABLE_FRAGMENT)                     # 片段沒有 viewData


class ErrorCases(unittest.TestCase):
    def test_not_a_string(self):
        for bad in (None, "", "   ", 5, b"x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    H.parse_hero_status(bad)
                with self.assertRaises(ParseError):
                    H.parse_adventures(bad)

    def test_no_hud_no_json(self):
        with self.assertRaises(ParseError):
            H.parse_hero_status("<html><body>nothing</body></html>")

    def test_json_without_status(self):
        bad = ADV_ASIA_A.replace('"status":{"status":9', '"status":{"statusX":9')
        self.assertNotEqual(bad, ADV_ASIA_A)
        with self.assertRaises(ParseError):
            H.parse_hero_status(bad)

    def test_adventures_json_missing(self):
        for h in (OVERVIEWS["S6c_overview_asia8_return.html"], "<html></html>"):
            with self.assertRaises(ParseError):
                H.parse_adventures(h)

    def test_adventure_missing_field(self):
        bad = ADV_I11.replace('"travelingDuration":2880', '"travelingDurationX":2880')
        self.assertNotEqual(bad, ADV_I11)
        with self.assertRaises(ParseError):
            H.parse_adventures(bad)

    def _mismatch(self, fn):
        page = _with_table(fragment=_edit_fragment(TABLE_FRAGMENT, fn))
        with self.assertRaises(ParseError):
            H.parse_adventures(page)

    def test_table_row_count_mismatch(self):
        self._mismatch(lambda s: s.select("table.adventureList tbody tr")[-1].decompose())

    def test_table_place_mismatch(self):
        def f(s):
            img = s.select_one("table.adventureList tbody tr td.place img")
            img["class"] = ["forest"]
        self._mismatch(f)

    def test_table_distance_mismatch(self):
        def f(s):
            td = s.select_one("table.adventureList tbody tr td.distance")
            td.string = "12.5 資源田"
        self._mismatch(f)

    def test_table_duration_mismatch(self):
        def f(s):
            d = s.select_one("table.adventureList tbody tr td.duration div.duration")
            d.string = "00:29:48"
        self._mismatch(f)

    def test_distance_tolerance(self):
        """距離容許 0.15：頁面四捨五入（9.43 vs 9.43398）不算不一致；差 0.1 以內也過。"""
        def f(s):
            td = s.select_one("table.adventureList tbody tr td.distance")
            td.string = "9.5 資源田"
        page = _with_table(fragment=_edit_fragment(TABLE_FRAGMENT, f))
        self.assertEqual(len(H.parse_adventures(page)), 18)

    def test_error_message_has_no_page_content(self):
        def f(s):
            s.select_one("table.adventureList tbody tr td.distance").string = "12.5 資源田"
        page = _with_table(fragment=_edit_fragment(TABLE_FRAGMENT, f))
        with self.assertRaises(ParseError) as cm:
            H.parse_adventures(page)
        self.assertNotIn("12.5", str(cm.exception))


class OldCodeDifferences(unittest.TestCase):
    def test_hard_is_difficulty_zero(self):
        bad = ADV_I11.replace('"difficulty":2', '"difficulty":0')
        self.assertNotEqual(bad, ADV_I11)
        a = H.parse_adventures(bad)[0]
        self.assertEqual((a.difficulty, a.hard), (0, True))

    def test_status_code_kept_raw(self):
        bad = ADV_ASIA_A.replace('"status":{"status":9', '"status":{"status":777')
        self.assertEqual(H.parse_hero_status(bad).status, 777)     # 未知狀態碼原樣保留，意義由 domain 用 HERO_STATUS 判斷


class HeroStatusConstants(unittest.TestCase):
    def test_codes(self):
        self.assertEqual((C.HERO_STATUS_HOME, C.HERO_STATUS_DEAD, C.HERO_STATUS_RETURNING, C.HERO_STATUS_HIDING,
                          C.HERO_STATUS_ADVENTURE, C.HERO_STATUS_CAPTIVE, C.HERO_STATUS_STATIONED),
                         (100, 101, 9, 40, 50, 102, 103))
        self.assertEqual({C.HERO_STATUS_OUT_ATTACK, C.HERO_STATUS_OUT_RAID, C.HERO_STATUS_OUT_SUPPLY}, {3, 4, 5})

    def test_table_complete_and_unique(self):
        self.assertEqual(set(C.HERO_STATUS), {3, 4, 5, 9, 40, 50, 100, 101, 102, 103})
        self.assertEqual(len(set(C.HERO_STATUS.values())), len(C.HERO_STATUS))


if __name__ == "__main__":
    unittest.main()
