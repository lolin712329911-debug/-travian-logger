# -*- coding: utf-8 -*-
"""parsers/village.py（ps-01，A2a-2a）的測試：golden、樣本事實、錯誤案例、舊碼差異。
樣本：舊服 Asia 8 的 S1a／S1b（dorf1）、S12a／S12b（dorf2），都在 tests/samples/（已脫敏）。
golden 以頁面時間戳記（Travian.Game.timestamp）當案例 id，不依賴樣本檔名 a／b 的對應。
UPDATE_GOLDEN=1 會改寫 golden；改寫要在交接區塊說明原因。"""
import copy
import dataclasses
import glob
import json
import os
import re
import unittest

from bs4 import BeautifulSoup

from travian_bot.common.schema import ParseError
from travian_bot.parsers import village as V
from travian_bot.parsers import village_list as VL

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "samples")
_GOLDEN = os.path.join(_HERE, "..", "golden", "parsers", "village")
_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
_TS_RE = re.compile(r"Travian\.Game\.timestamp\s*=\s*(\d+)")


def _load(pattern):
    out = {}
    for p in sorted(glob.glob(os.path.join(_SAMPLES, pattern))):
        with open(p, encoding="utf-8") as f:
            h = f.read()
        out[int(_TS_RE.search(h).group(1))] = h
    return out


DORF1 = _load("S1?_dorf1_*.html")
DORF2 = _load("S12?_dorf2_*.html")
ALL = {**DORF1, **DORF2}


def _plain(obj):
    return json.loads(json.dumps(dataclasses.asdict(obj), ensure_ascii=False))


def _golden_check(tc, name, produced):
    """produced: {案例 id: 純資料}。"""
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


def _drop_field(html, aid):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one(f'#resourceFieldContainer a.resourceField[data-aid="{aid}"]').decompose()
    return str(soup)


def _set_incoming(html, did, n):
    new, k = re.subn(r'("id":%d,"name":"[^"]*","distance":[\d.]+,"incomingAttacksAmount":)\d+' % did,
                     lambda m: m.group(1) + str(n), html)
    assert k == 1, "樣本的 villageList 結構與測試預期不同"
    return new


def _movements_html(*rows):
    body = "".join(
        '<tr><td class="typ"><img class="%s"/></td><td><div class="mov"><span>%s</span></div>%s</td></tr>' %
        (cls, label, '<div class="dur_r"><span class="timer" value="%d"></span></div>' % secs if secs is not None else "")
        for cls, label, secs in rows)
    return '<table id="movements"><tr><th class="troopMovements header" colspan="3">x</th></tr>%s</table>' % body


class TestSamplesPresent(unittest.TestCase):
    def test_four_samples(self):
        self.assertEqual(len(DORF1), 2, "需要 S1a、S1b 兩份 dorf1")
        self.assertEqual(len(DORF2), 2, "需要 S12a、S12b 兩份 dorf2")


class TestGolden(unittest.TestCase):
    def test_dorf1(self):
        _golden_check(self, "dorf1", {f"ts{ts}": _plain(V.parse_dorf1(h)) for ts, h in DORF1.items()})

    def test_dorf2(self):
        _golden_check(self, "dorf2", {f"ts{ts}": _plain(V.parse_dorf2(h)) for ts, h in DORF2.items()})

    def test_page_facts(self):
        # villages 以數量記（座標與 id 隨脫敏而不同），內容另由 TestPageFacts 與 village_list 交叉核對
        out = {}
        for ts, h in ALL.items():
            d = _plain(V.parse_page_facts(h))
            d["villages"] = len(d["villages"]) if d["villages"] is not None else None
            out[f"ts{ts}"] = d
        _golden_check(self, "page_facts", out)


class TestDorf1Samples(unittest.TestCase):
    def test_structure_invariants(self):
        for ts, h in DORF1.items():
            with self.subTest(ts=ts):
                d = V.parse_dorf1(h)
                self.assertEqual([f.aid for f in d.fields], list(range(1, 19)))
                self.assertTrue(all(f.gid in (1, 2, 3, 4) and f.url is None for f in d.fields))
                self.assertTrue(all(len(f.cost) == 4 and f.build_time_s > 0 for f in d.fields))
                self.assertEqual(len(d.stock), 4)
                self.assertEqual(len(d.prod), 4)
                self.assertTrue(all(0 <= s <= (d.cap_wh if i < 3 else d.cap_gr) for i, s in enumerate(d.stock)))
                self.assertIsInstance(d.cap_wh, int)
                self.assertEqual(d.incoming_attacks, 0)
                self.assertIsNone(d.attack_eta_s)
                self.assertTrue(all(isinstance(f.under_construction, bool) for f in d.fields))

    def test_known_facts_by_timestamp(self):
        # S1a：2 個施工佇列項目都是 dorf2 的建築（沒有資源田施工）、1 筆冒險移動列；S1b：資源田 aid 11 施工中、沒有移動列
        a, b = V.parse_dorf1(DORF1[1793407106]), V.parse_dorf1(DORF1[1793407632])
        self.assertEqual([q.remaining_s for q in a.queue], [580, 6510])
        self.assertFalse(any(f.under_construction for f in a.fields))
        self.assertEqual([(m["kind"], m["count"], m["seconds"]) for m in a.movements], [("adventure", 1, 334)])
        self.assertEqual([q.remaining_s for q in b.queue], [11758, 20668])
        self.assertEqual([(f.aid, f.gid, f.level) for f in b.fields if f.under_construction], [(11, 3, 7)])
        self.assertEqual(b.movements, ())
        self.assertEqual((a.stock, a.free_crop, a.cap_wh, a.cap_gr), ((3611, 3430, 4909, 5780), 292, 6300, 6300))
        self.assertEqual((b.stock, b.prod, b.free_crop, b.cap_wh, b.cap_gr),
                         ((428, 376, 2069, 1443), (560, 560, 392, 382), 460, 21400, 7800))

    def test_queue_info_has_no_remaining_time(self):
        for h in DORF1.values():
            for q in V.parse_dorf1(h).queue:
                self.assertTrue(q.info)
                self.assertNotIn("剩", q.info)

    def test_plus_and_protection_none_when_block_absent(self):
        for h in DORF1.values():
            d = V.parse_dorf1(h)
            self.assertIsNone(d.plus_s)
            self.assertIsNone(d.protection_s)

    def test_sidebar_timers(self):
        html = DORF1[1793407632].replace(
            "</body>", '<div id="sidebarBoxInfobox"><ul>'
            '<li>新手保護 <span class="timer" value="900">0:15:00</span></li>'
            '<li>Plus <span class="timer" value="7200">2:00:00</span></li>'
            '<li>其他 <span class="timer" value="5"></span></li></ul></div></body>')
        d = V.parse_dorf1(html)
        self.assertEqual((d.protection_s, d.plus_s), (900, 7200))

    def test_max_level_field_has_no_cost(self):
        soup = BeautifulSoup(DORF1[1793407632], "html.parser")
        a = soup.select_one('#resourceFieldContainer a.resourceField[data-aid="1"]')
        a["title"] = "鐵礦場 <span class=\"level\">等級 10</span>||已達最高等級，已不可再升級。"
        f = V.parse_dorf1(str(soup)).fields[0]
        self.assertIsNone(f.cost)
        self.assertIsNone(f.build_time_s)


class TestIncomingAttacks(unittest.TestCase):
    """舊碼把 villageList 每個村的 incomingAttacksAmount 加總；新碼只看目前村。"""

    def setUp(self):
        self.html = DORF1[1793407632]
        self.active = VL.parse_active_village(self.html, 200)
        self.other = next(r.did for r in VL.parse_village_list(self.html, 200) if r.did != self.active)

    def test_other_village_attack_is_not_counted(self):
        html = _set_incoming(self.html, self.other, 3)
        self.assertEqual(V.parse_dorf1(html).incoming_attacks, 0)

    def test_active_village_attack_is_counted(self):
        html = _set_incoming(_set_incoming(self.html, self.other, 3), self.active, 2)
        self.assertEqual(V.parse_dorf1(html).incoming_attacks, 2)

    def test_unreadable_is_none(self):
        self.assertIsNone(V.parse_dorf1(self.html.replace("viewData:", "viewDataX:")).incoming_attacks)
        html = re.sub(r'"incomingAttacksAmount":\d+', '"incomingAttacksAmount":"x"', self.html)
        self.assertIsNone(V.parse_dorf1(html).incoming_attacks)

    def test_village_group_is_flattened(self):
        data = V._view_data(self.html)
        data["ownPlayer"]["villageList"] = [{"id": 1, "name": "g", "villages": data["ownPlayer"]["villageList"]}]
        self.assertEqual(V._incoming_attacks("viewData: " + json.dumps(data)), 0)


class TestDorf1Errors(unittest.TestCase):
    def setUp(self):
        self.html = DORF1[1793407632]

    def _bad(self, html):
        with self.assertRaises(ParseError):
            V.parse_dorf1(html)

    def test_bad_inputs(self):
        for bad in (None, "", "   ", b"x", 5, "<html></html>"):
            with self.subTest(bad=bad):
                self._bad(bad)

    def test_missing_resources(self):
        self._bad(self.html.replace("var resources", "var resourcez"))

    def test_missing_stock_slot(self):
        self._bad(re.sub(r'(storage:\s*\{[^}]*?)"l2":\s*\d+,', r"\1", self.html, count=1))

    def test_missing_prod_l5(self):
        self._bad(re.sub(r',\s*"l5":\s*-?\d+', "", self.html, count=1))

    def test_missing_cap(self):
        self._bad(self.html.replace("maxStorage", "maxStorag"))

    def test_warehouse_caps_differ(self):
        self._bad(re.sub(r'(maxStorage:\s*\{"l1":\s*\d+,\s*"l2":\s*)\d+', r"\g<1>1", self.html, count=1))

    def test_field_count(self):
        self._bad(_drop_field(self.html, 7))

    def test_field_without_level(self):
        soup = BeautifulSoup(self.html, "html.parser")
        a = soup.select_one('#resourceFieldContainer a.resourceField[data-aid="3"]')
        a["class"] = [c for c in a["class"] if not re.fullmatch(r"level\d+", c)]
        self._bad(str(soup))

    def test_field_with_partial_cost(self):
        soup = BeautifulSoup(self.html, "html.parser")
        a = soup.select_one('#resourceFieldContainer a.resourceField[data-aid="3"]')
        a["title"] = a["title"].replace('class="r4Big"', 'class="r9Big"')
        self._bad(str(soup))

    def test_queue_item_without_timer(self):
        soup = BeautifulSoup(self.html, "html.parser")
        soup.select_one("div.buildingList li span.timer")["value"] = "x"
        self._bad(str(soup))

    def test_page_facts_never_raise_on_missing_fields(self):
        f = V.parse_page_facts("<html></html>")
        self.assertEqual(dataclasses.astuple(f), (None,) * 7)


class TestMovements(unittest.TestCase):
    def test_kinds_and_eta(self):
        html = _movements_html(("att1", "3 攻擊", 600), ("att1", "1 攻擊", 120), ("def1", "5 增援", 60),
                               ("hero_on_adventure", "1 冒險", 30), ("rai2", "掠奪", None), ("", "x", 5),
                               ("att1", "12 攻擊", 700))
        rows = V.parse_movements(html)
        self.assertEqual([r["kind"] for r in rows],
                         ["attack", "attack", "reinforcement", "adventure", "rai2", "unknown", "attack"])
        self.assertEqual([r["count"] for r in rows], [3, 1, 5, 1, None, None, 12])
        self.assertEqual([r["seconds"] for r in rows], [600, 120, 60, 30, None, 5, 700])
        d = V.parse_dorf1(DORF1[1793407632].replace("</body>", html + "</body>"))
        self.assertEqual(d.attack_eta_s, 120)             # 只取 kind＝attack 的最小值
        self.assertEqual(len(d.movements), 7)

    def test_no_table(self):
        self.assertEqual(V.parse_movements("<html></html>"), [])

    def test_header_rows_skipped_and_label_has_no_bidi(self):
        rows = V.parse_movements(_movements_html(("att1", "\u202d\u202d7\u202c 攻擊", 9)))
        self.assertEqual(rows[0]["count"], 7)
        self.assertNotIn("\u202d", rows[0]["label"])

    def test_bad_input(self):
        with self.assertRaises(ParseError):
            V.parse_movements(None)


class TestDorf2(unittest.TestCase):
    def test_all_slots(self):
        for ts, h in DORF2.items():
            with self.subTest(ts=ts):
                d = V.parse_dorf2(h)
                self.assertEqual([s.aid for s in d.slots], list(range(19, 41)))
                self.assertEqual(d.slots, V.parse_dorf2_slots(h))
                for s in d.slots:
                    self.assertIsInstance(s.under_construction, bool)
                    self.assertEqual(s.gid is None, s.name is None)
                    if s.gid is None:
                        self.assertEqual(s.level, 0)

    def test_under_construction_matches_queue(self):
        # S12a：兩個施工中（aid 26 gid 15、aid 32 gid 11）＝佇列 2 項；S12b：aid 21 gid 22 施工中（另一項在 dorf1 的資源田）
        a, b = V.parse_dorf2(DORF2[1793407065]), V.parse_dorf2(DORF2[1793407599])
        self.assertEqual([(s.aid, s.gid) for s in a.slots if s.under_construction], [(26, 15), (32, 11)])
        self.assertEqual([(s.aid, s.gid) for s in b.slots if s.under_construction], [(21, 22)])
        self.assertEqual(len(V._parse_queue(BeautifulSoup(DORF2[1793407065], "html.parser"))), 2)

    def test_wall_with_two_nodes_is_deduplicated(self):
        h = DORF2[1793407599]
        soup = BeautifulSoup(h, "html.parser")
        walls = soup.select('#villageContent .buildingSlot[data-aid="40"]')
        self.assertEqual(len(walls), 2)                    # 樣本確實有 top／bottom 兩個節點（舊碼回 23 筆）
        wall = next(s for s in V.parse_dorf2_slots(h) if s.aid == 40)
        self.assertEqual(wall.gid, 33)
        self.assertGreater(wall.level, 0)
        want = next(w for w in walls if w.get("data-building-id"))
        self.assertEqual(wall.level, int(want.select_one("a.level")["data-level"]))

    def test_wall_dedup_independent_of_order(self):
        soup = BeautifulSoup(DORF2[1793407599], "html.parser")
        a, b = soup.select('#villageContent .buildingSlot[data-aid="40"]')
        a.insert_before(b.extract())                       # 交換兩個節點的順序
        self.assertEqual(V.parse_dorf2_slots(str(soup)), V.parse_dorf2_slots(DORF2[1793407599]))

    def test_wall_prefers_node_with_building_id(self):
        # 樣本中兩個節點內容相同（gid、名稱、等級都一樣）；人為讓沒有 data-building-id 的節點不同，確認取的是有的那個
        for flip in (False, True):
            soup = BeautifulSoup(DORF2[1793407599], "html.parser")
            nodes = soup.select('#villageContent .buildingSlot[data-aid="40"]')
            bare = next(n for n in nodes if not n.get("data-building-id"))
            bare.select_one("a.level")["data-level"] = "9"
            if flip:
                nodes[0].insert_before(nodes[1].extract())
            wall = next(s for s in V.parse_dorf2_slots(str(soup)) if s.aid == 40)
            self.assertEqual(wall.level, 1)

    def test_duplicate_non_wall_slot_is_error(self):
        soup = BeautifulSoup(DORF2[1793407065], "html.parser")
        s = soup.select_one('#villageContent .buildingSlot[data-aid="21"]')
        s.insert_after(copy.copy(s))
        with self.assertRaises(ParseError):
            V.parse_dorf2_slots(str(soup))

    def test_missing_slot_is_error(self):
        soup = BeautifulSoup(DORF2[1793407065], "html.parser")
        soup.select_one('#villageContent .buildingSlot[data-aid="25"]').decompose()
        with self.assertRaises(ParseError):
            V.parse_dorf2_slots(str(soup))

    def test_building_without_level_is_error(self):
        soup = BeautifulSoup(DORF2[1793407065], "html.parser")
        soup.select_one('#villageContent .buildingSlot[data-aid="21"] a.level').decompose()
        with self.assertRaises(ParseError):
            V.parse_dorf2_slots(str(soup))

    def test_bad_inputs(self):
        for bad in (None, "", "<html></html>"):
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    V.parse_dorf2(bad)


class TestPageFacts(unittest.TestCase):
    def test_values_on_every_sample(self):
        for ts, h in ALL.items():
            with self.subTest(ts=ts):
                f = V.parse_page_facts(h)
                self.assertEqual((f.tz_name, f.tz_offset_s, f.lang, f.gpack, f.tribe_id, f.server_ts),
                                 ("Europe/London", 0, "zh-TW", "692.2", 3, ts))

    def test_villages_agree_with_village_list(self):
        for ts, h in ALL.items():
            with self.subTest(ts=ts):
                want = tuple((r.did, r.x, r.y) for r in VL.parse_village_list(h, 200))
                got = tuple((v.did, v.x, v.y) for v in V.parse_page_facts(h).villages)
                self.assertEqual(got, want)

    def test_village_with_unreadable_coordinate_makes_list_none(self):
        data = V._view_data(DORF1[1793407632])
        self.assertEqual(len(V._page_villages(data)), 2)
        data["ownPlayer"]["villageList"][1]["y"] = "-44"           # 字串不算座標
        self.assertIsNone(V._page_villages(data))
        data["ownPlayer"]["villageList"] = []
        self.assertIsNone(V._page_villages(data))
        self.assertIsNone(V._page_villages(None))

    def test_server_ts_is_an_integer_not_a_string(self):
        self.assertIsInstance(V.parse_page_facts(DORF1[1793407632]).server_ts, int)

    def test_lang_from_html_tag_not_from_js(self):
        h = DORF1[1793407632].replace('lang="zh-TW"', 'lang="en"', 1)
        self.assertEqual(V.parse_page_facts(h).lang, "en")

    def test_bad_input(self):
        for bad in (None, 5, b"x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    V.parse_page_facts(bad)


class TestContract(unittest.TestCase):
    def test_pure_and_frozen(self):
        h = DORF1[1793407632]
        self.assertEqual(V.parse_dorf1(h), V.parse_dorf1(h))
        d = V.parse_dorf1(h)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            d.free_crop = 0
        self.assertIsInstance(d.fields, tuple)
        self.assertIsInstance(d.queue, tuple)
        self.assertIsInstance(d.stock, tuple)

    def test_error_messages_do_not_leak_page_content(self):
        secret = "SECRETNAME"
        try:
            V.parse_dorf1("<html><title>%s</title></html>" % secret)
        except ParseError as e:
            self.assertNotIn(secret, str(e))
            self.assertEqual(e.page, "village")


if __name__ == "__main__":
    unittest.main()
