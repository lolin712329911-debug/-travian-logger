# -*- coding: utf-8 -*-
"""parsers/tile.py（ps-09，A2b）的測試：golden、樣本事實、座標與 map_id 交叉核對、錯誤案例、舊碼差異。
樣本：tests/samples/S15a～c（tile-details 的 html 欄，`div#tileDetails` 片段；舊服 zh-TW；測試帳號、未脫敏；說明見 README_A2b.md）。
golden 的案例 id 用檔名代號（S15a／S15b／S15c；片段沒有時間戳）。UPDATE_GOLDEN=1 會改寫 golden；改寫要在交接區塊說明原因。"""
import dataclasses
import json
import os
import unittest

from bs4 import BeautifulSoup

from travian_bot.common.schema import ParseError
from travian_bot.parsers import tile as T

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "samples")
_GOLDEN = os.path.join(_HERE, "..", "golden", "parsers", "tile")
_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


def _read(name):
    with open(os.path.join(_SAMPLES, name), encoding="utf-8", newline="") as f:    # 樣本是 CRLF，原樣讀入
        return f.read()


S15A = _read("S15a_tile_oasis_free_empty.html")       # 未佔領、動物表「無」
S15B = _read("S15b_tile_oasis_free_animals.html")     # 未佔領、3 種動物
S15C = _read("S15c_tile_oasis_taken.html")            # 已佔領、沒有動物表
SAMPLES = {"S15a": S15A, "S15b": S15B, "S15c": S15C}


def _map_id(x, y):
    """geo.map_id 的公式（世界 −200～200）；測試自帶，parsers 不依賴 cm-07。"""
    return (200 - y) * 401 + (x + 201)


def _plain(obj):
    return json.loads(json.dumps(dataclasses.asdict(obj), ensure_ascii=False))


def _golden_check(tc, name, produced):
    path = os.path.join(_GOLDEN, name + ".expected.json")
    if _UPDATE:
        os.makedirs(_GOLDEN, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"schema_version": 1, "cases": [{"id": k, **v} for k, v in sorted(produced.items())]},
                      f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    with open(path, encoding="utf-8") as f:
        want = {c["id"]: {k: v for k, v in c.items() if k != "id"} for c in json.load(f)["cases"]}
    tc.assertEqual(set(want), set(produced), "golden 的案例與樣本不一致")
    for k in produced:
        with tc.subTest(case=k):
            tc.assertEqual(produced[k], want[k])


def _edit(html, fn):
    soup = BeautifulSoup(html, "html.parser")
    fn(soup)
    return str(soup)


class Golden(unittest.TestCase):
    def test_golden(self):
        produced = {k: {"tile": _plain(T.parse_tile_details(h))} for k, h in SAMPLES.items()}
        _golden_check(self, "tile_details", produced)


class SampleFacts(unittest.TestCase):
    def test_free_empty(self):
        t = T.parse_tile_details(S15A)
        self.assertEqual((t.x, t.y, t.map_id, t.occupied, t.oasis_type), (-19, -88, 115670, False, 7))
        self.assertEqual((t.owner_uid, t.alliance_id, t.owner_village), (None, None, None))
        self.assertEqual(t.animals, {})                                  # 有表但沒有 img.unit
        self.assertEqual((t.bonuses, t.distance, t.safe), (((1, 25), (3, 25)), 6.71, True))
        self.assertEqual(t.occupy_events, ("昨天, 15:39", "2 日前, 19:28", "03.11.26, 07:35"))

    def test_free_with_animals(self):
        t = T.parse_tile_details(S15B)
        self.assertEqual((t.x, t.y, t.map_id, t.occupied, t.oasis_type), (-26, -85, 114460, False, 2))
        self.assertEqual(t.animals, {35: 5, 36: 4, 37: 3})
        self.assertEqual((t.bonuses, t.distance, t.safe), (((0, 25),), 1.0, False))
        self.assertEqual(t.occupy_events, ("03.11.26, 18:38",))

    def test_taken(self):
        t = T.parse_tile_details(S15C)
        self.assertEqual((t.x, t.y, t.map_id, t.occupied, t.oasis_type), (-18, -78, 111661, True, 7))
        self.assertEqual((t.owner_uid, t.alliance_id, t.owner_village), (2702, 44, (-15, -76)))
        self.assertIsNone(t.animals)                                     # 已佔領格沒有動物表：未知≠無動物
        self.assertEqual((t.bonuses, t.distance, t.safe), (((1, 25), (3, 25)), 9.9, False))
        self.assertEqual(t.occupy_events, ("今天, 00:25",))

    def test_map_id_agrees_with_coordinates(self):
        for k, h in SAMPLES.items():
            with self.subTest(k):
                t = T.parse_tile_details(h)
                self.assertEqual(t.map_id, _map_id(t.x, t.y))

    def test_taken_oasis_map_id_is_from_dispatch_link_and_matches_kid_free_ones(self):
        """S15a、S15b 的 map_id 也等於模擬連結的 kid（兩處一致）；S15c 沒有模擬連結，只有「派遣部隊」的 targetMapId。"""
        import re
        for h in (S15A, S15B):
            self.assertEqual(int(re.search(r"kid=(\d+)", h).group(1)), T.parse_tile_details(h).map_id)
        self.assertNotIn("kid=", S15C)

    def test_safe_rule(self):
        self.assertEqual([T.parse_tile_details(h).safe for h in (S15A, S15B, S15C)], [True, False, False])

    def test_two_troop_info_tables_are_told_apart(self):
        """S15a 有兩個 id=troop_info：動物表（「無」）與報告表（class rep，「暫時沒有信息」）；結果只看前者。"""
        soup = BeautifulSoup(S15A, "html.parser")
        tables = soup.select("table#troop_info")
        self.assertEqual(len(tables), 2)
        self.assertEqual([("rep" in t["class"]) for t in tables], [False, True])
        self.assertEqual(T.parse_tile_details(S15A).animals, {})

    def test_bidi_in_numbers_does_not_matter(self):
        for h in SAMPLES.values():
            self.assertIn("\u202d", h)                                   # 樣本確實帶方向控制字元
            t = T.parse_tile_details(h)
            self.assertTrue(t.bonuses and all(p == 25 for _r, p in t.bonuses))      # 「‭‭25‬%‬」取得 25

    def test_events_keep_original_text(self):
        t = T.parse_tile_details(S15A)
        self.assertEqual(t.occupy_events[1], "2 日前, 19:28")


class ErrorCases(unittest.TestCase):
    def test_bad_input(self):
        for bad in (None, "", "   ", 3, b"x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    T.parse_tile_details(bad)

    def test_no_tile_details_root(self):
        with self.assertRaises(ParseError):
            T.parse_tile_details("<div>hello</div>")

    def test_not_an_oasis(self):
        html = _edit(S15A, lambda s: s.select_one("#tileDetails").attrs.update({"class": ["village"]}))
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)

    def test_no_centermap_link(self):
        html = _edit(S15A, lambda s: s.select_one("a[data-centermap]").decompose())
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)

    def test_centermap_without_coordinates(self):
        html = _edit(S15A, lambda s: s.select_one("a[data-centermap]").attrs.update(href="/karte.php"))
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)

    def test_map_id_fallback_to_kid(self):
        """沒有 targetMapId 才取模擬連結的 kid（卡片規則）。"""
        def f(s):
            for a in s.select("a[href]"):
                a["href"] = a["href"].replace("targetMapId=", "targetX=")
        t = T.parse_tile_details(_edit(S15A, f))
        self.assertEqual(t.map_id, 115670)

    def test_no_map_id_at_all(self):
        def f(s):
            for a in s.select("a[href]"):
                a["href"] = a["href"].replace("targetMapId=", "x1=").replace("kid=", "k1=")
        with self.assertRaises(ParseError):
            T.parse_tile_details(_edit(S15A, f))

    def test_title_status_mismatch(self):
        for html in (_edit(S15A, lambda s: s.select_one("#map_details").insert(0, BeautifulSoup('<table id="village_info"></table>', "html.parser"))),
                     _edit(S15C, lambda s: s.select_one("#village_info").decompose())):
            with self.subTest():
                with self.assertRaises(ParseError):
                    T.parse_tile_details(html)

    def test_title_without_status_words(self):
        html = _edit(S15A, lambda s: s.select_one("h1.titleInHeader").__setattr__("string", "Oasis"))
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)
        # 其他語系略過標題核對
        self.assertEqual(T.parse_tile_details(html, locale="en").map_id, 115670)

    def test_animal_row_without_count(self):
        html = _edit(S15B, lambda s: s.select_one("#map_details table#troop_info td.val").decompose())
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)

    def test_bonus_resource_out_of_range(self):
        html = _edit(S15A, lambda s: s.select_one("#distribution i").attrs.update({"class": ["r9"]}))
        with self.assertRaises(ParseError):
            T.parse_tile_details(html)

    def test_error_message_has_no_page_content(self):
        html = _edit(S15A, lambda s: s.select_one("a[data-centermap]").attrs.update(href="/karte.php?secret=1"))
        with self.assertRaises(ParseError) as cm:
            T.parse_tile_details(html)
        self.assertNotIn("secret", str(cm.exception))


class DesignChoices(unittest.TestCase):
    def test_unoccupied_without_animal_table_is_unknown_not_safe(self):
        html = _edit(S15A, lambda s: s.select_one("#map_details table#troop_info").decompose())
        t = T.parse_tile_details(html)
        self.assertIsNone(t.animals)
        self.assertFalse(t.occupied)
        self.assertFalse(t.safe)

    def test_missing_alliance_is_none(self):
        def f(s):
            for tr in s.select("#village_info tr"):
                if tr.select_one("a[href^='/alliance/']"):
                    tr.decompose()
        t = T.parse_tile_details(_edit(S15C, f))
        self.assertEqual((t.owner_uid, t.alliance_id, t.owner_village), (2702, None, (-15, -76)))

    def test_distance_without_unit_text(self):
        html = _edit(S15B, lambda s: s.select_one("#distance td.bold").__setattr__("string", "12.34"))
        self.assertEqual(T.parse_tile_details(html).distance, 12.34)

    def test_no_distance_is_none(self):
        html = _edit(S15B, lambda s: s.select_one("#distance").decompose())
        self.assertIsNone(T.parse_tile_details(html).distance)

    def test_no_recent_occupy_judgement_in_parser(self):
        """舊 recent_occupy_warning 靠「今天／昨天」字樣：不進 parser；S15c 的事件含「今天」但 safe 只看佔領與動物。"""
        t = T.parse_tile_details(S15C)
        self.assertIn("今天", t.occupy_events[0])
        self.assertFalse(hasattr(T, "recent_occupy_warning"))
        self.assertFalse(hasattr(T, "is_safe"))


if __name__ == "__main__":
    unittest.main()
