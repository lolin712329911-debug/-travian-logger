# -*- coding: utf-8 -*-
"""parsers/rally.py（ps-06，A2b）的測試：golden、樣本事實、交叉核對、錯誤案例、舊碼差異。
樣本在 tests/samples/（S6a～f 概況、S17a～d 確認頁、S17e 表單；測試帳號、原始頁、未脫敏；說明見 README_A2b.md）。
golden 以頁面時間戳記（Travian.Game.timestamp）當案例 id。UPDATE_GOLDEN=1 會改寫 golden；改寫要在交接區塊說明原因。
確認頁的 checksum 是 token：樣本是測試帳號所以保留原值（A-11⑦）。"""
import dataclasses
import json
import os
import re
import unittest

from bs4 import BeautifulSoup

from travian_bot.common.schema import ParseError
from travian_bot.parsers import rally as R

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "samples")
_GOLDEN = os.path.join(_HERE, "..", "golden", "parsers", "rally")
_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
_TS_RE = re.compile(r"Travian\.Game\.timestamp\s*=\s*(\d+)")


def _read(name):
    with open(os.path.join(_SAMPLES, name), encoding="utf-8") as f:
        return f.read()


def _ts(h):
    return int(_TS_RE.search(h).group(1))


def _load(prefix):
    return {n: _read(n) for n in sorted(os.listdir(_SAMPLES)) if n.startswith(prefix) and n.endswith(".html")}


OVERVIEWS = _load("S6")
CONFIRMS = _load("S17a"), _load("S17b"), _load("S17c"), _load("S17d")
CONFIRM_ALL = {n: h for d in CONFIRMS for n, h in d.items()}
FORM_HOME = _read("S17e_form_i11_hero_home_oasis_link.html")

S6A = OVERVIEWS["S6a_overview_asia8_return_home.html"]          # Asia 8：英雄返回，本村有兵
S6D = OVERVIEWS["S6d_overview_i11_hero_raid_oasis.html"]        # Intl 11：英雄搶奪綠洲，在家全 0
S6E = OVERVIEWS["S6e_overview_i11_hero_raid_oasis.html"]        # 同上，晚 29 秒
S6F = OVERVIEWS["S6f_overview_i11_hero_adventure.html"]         # Intl 11：英雄去冒險，inRaid×5
S17A = _read("S17a_confirm_asia8_reinforce.html")
S17B = _read("S17b_confirm_asia8_attack.html")
S17C = _read("S17c_confirm_asia8_raid.html")
S17D = _read("S17d_confirm_i11_hero_raid_oasis.html")


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
    def test_overview_golden(self):
        produced = {_ts(h): {"overview": _plain(R.parse_overview(h))} for h in OVERVIEWS.values()}
        _golden_check(self, "overview", produced)

    def test_troops_home_golden(self):
        produced = {_ts(h): {"units_home": R.parse_troops_home(h)} for h in OVERVIEWS.values()}
        _golden_check(self, "troops_home", produced)

    def test_send_confirm_golden(self):
        produced = {_ts(h): {"confirm": _plain(R.parse_send_confirm(h))} for h in CONFIRM_ALL.values()}
        _golden_check(self, "send_confirm", produced)


class OverviewFacts(unittest.TestCase):
    def test_units_keys_follow_column_order_not_icon_class(self):
        """Asia 8 是高盧，圖示 class 是 u21～u30；鍵依欄位順序＝u1、u3（238 與 23），英雄 0 省略。"""
        o = R.parse_overview(S6A)
        self.assertEqual(o.units_home, {"u1": 238, "u3": 23})
        icons = BeautifulSoup(S6A, "html.parser").select("table.troop_details[data-did] img.unit")
        self.assertTrue(any("u21" in i["class"] for i in icons))

    def test_returning_hero(self):
        o = R.parse_overview(S6A)
        self.assertEqual(len(o.movements), 1)
        m = o.movements[0]
        self.assertEqual((m.kinds, m.hostile, m.own_home, m.units), (("inReturn",), False, False, {"hero": 1}))
        self.assertEqual((m.arrive_ts, m.recall_id), (1794018151, None))
        self.assertEqual((m.role_did, m.head_did, m.link_did), (114461, 0, 114461))     # 冒險標題連結是 d=0
        self.assertEqual((o.server_ts, o.incoming_attacks, o.units_away), (1794016856, 0, None))

    def test_returning_matches_adventure_arrival(self):
        """概況的歸來時間與冒險頁 arrivalAt（epoch 秒）一致：S6b（ts 1794017928）與 S18a（arrivalAt 1794018151）。"""
        self.assertEqual(R.parse_overview(OVERVIEWS["S6b_overview_asia8_return.html"]).movements[0].arrive_ts, 1794018151)

    def test_hero_raiding_oasis_i11(self):
        o = R.parse_overview(S6D)
        self.assertEqual(o.units_home, {})                      # 英雄出門、所有兵 0：表仍在，全 0＝{}（不是 None）
        self.assertEqual([m.kinds for m in o.movements], [("inRaid",), ("inRaid",), ("inAttack",), ("outRaid",)])
        self.assertEqual(o.incoming_attacks, 3)
        out = o.movements[3]
        self.assertEqual((out.hostile, out.units, out.recall_id), (False, {"hero": 1}, 197142515))
        self.assertEqual((out.arrive_ts, out.role_did, out.head_did, out.link_did), (1794019145, 11233, 11630, 11630))
        self.assertTrue(out.section.startswith("出擊軍團"))

    def test_hostile_units_are_unknown_not_zero(self):
        for m in R.parse_overview(S6D).movements[:3]:
            self.assertTrue(m.hostile)
            self.assertEqual(set(m.units), {f"u{i}" for i in range(1, 11)} | {"hero"})
            self.assertEqual(set(m.units.values()), {None})     # 「?」＝None
            self.assertEqual(m.link_did, m.role_did)            # 來襲取來源村
            self.assertIsNone(m.recall_id)

    def test_two_pages_29s_apart_agree_on_absolute_times(self):
        a, b = R.parse_overview(S6D), R.parse_overview(S6E)
        self.assertEqual(b.server_ts - a.server_ts, 29)
        self.assertEqual([m.arrive_ts for m in a.movements], [m.arrive_ts for m in b.movements])

    def test_confirm_predicts_hero_arrival(self):
        """確認頁預計到達 1794019099（頁面 1794018226＋873）；實際約 46 秒後才按下，概況的 outRaid 到達＝1794019145。"""
        c = R.parse_send_confirm(S17D)
        out = R.parse_overview(S6D).movements[3]
        self.assertEqual(out.arrive_ts - c.epoch, 46)
        self.assertEqual((c.x, c.y), (-200, 171))
        self.assertEqual(out.head_did, 11630)                   # (200−171)×401＋(−200＋201)

    def test_hero_adventure_out_hero(self):
        o = R.parse_overview(S6F)
        self.assertEqual(o.units_home, {})
        self.assertEqual(o.incoming_attacks, 5)
        self.assertEqual([m.kinds for m in o.movements], [("inRaid",)] * 5 + [("outHero",)])
        h = o.movements[5]
        self.assertEqual((h.units, h.arrive_ts, h.recall_id, h.head_did, h.link_did), ({"hero": 1}, 1794046209, None, 0, 0))
        self.assertEqual(h.headline, "冒險")

    def test_outhero_arrival_matches_adventure_page(self):
        """冒險去程：概況 outHero 的到達＝冒險頁 arrivalAt（1794046209）。"""
        self.assertEqual(R.parse_overview(S6F).movements[5].arrive_ts, 1794046209)

    def test_stationed_and_captive_tables_are_not_movements(self):
        o = R.parse_overview(S6A)
        tables = BeautifulSoup(S6A, "html.parser").select("table.troop_details")
        self.assertEqual(len(tables), 4)            # inReturn、在家、別村駐守本村、我方駐守他村
        self.assertEqual(len(o.movements), 1)

    def test_troops_home_without_timestamp_fragment(self):
        frag = re.sub(r"Travian\.Game\.timestamp\s*=\s*\d+", "", S6A)
        self.assertEqual(R.parse_troops_home(frag), {"u1": 238, "u3": 23})
        with self.assertRaises(ParseError):
            R.parse_overview(frag)                  # 片段沒有時間戳：仍 ParseError（golden 用全頁）

    def test_troops_home_none_when_no_table(self):
        html = _edit(S6A, lambda s: [t.decompose() for t in s.select("table.troop_details[data-did]")])
        self.assertIsNone(R.parse_troops_home(html))
        self.assertIsNone(R.parse_overview(html).units_home)

    def test_troops_home_all_zero_is_empty_dict(self):
        self.assertEqual(R.parse_troops_home(S6F), {})

    def test_incoming_attacks_equals_sidebar(self):
        """hostile 張數與側欄 incomingAttacksAmount 一致（本檔樣本：3、3、5）；由 domain 核對，這裡只驗樣本事實。"""
        for h, want in ((S6D, 3), (S6E, 3), (S6F, 5)):
            self.assertEqual(R.parse_overview(h).incoming_attacks, want)
            self.assertEqual(int(re.search(r'"incomingAttacksAmount":(\d+)', h).group(1)), want)


class SendConfirmFacts(unittest.TestCase):
    def test_three_event_types_asia8(self):
        got = [(c.event_type, c.trip_s, c.units["u1"], c.village_did, (c.x, c.y), c.villagename)
               for c in map(R.parse_send_confirm, (S17A, S17B, S17C))]
        self.assertEqual(got, [(5, 6861, 10, 34593, (-28, -72), "doga的村莊"),
                               (3, 6861, 10, 34593, (-28, -72), "doga的村莊"),
                               (4, 6861, 10, 34593, (-28, -72), "doga的村莊")])

    def test_type_from_event_type_not_headline(self):
        c = R.parse_send_confirm(S17B)
        self.assertEqual((c.event_type, c.kind_text), (3, "正在攻擊 doga的村莊"))
        # 標題改掉，類型不變
        html = _edit(S17B, lambda s: s.select_one("td.troopHeadline").clear())
        self.assertEqual(R.parse_send_confirm(html).event_type, 3)

    def test_checksum_from_onclick_and_hidden_is_empty(self):
        for h, cs in ((S17A, "a91737"), (S17B, "65a9b6"), (S17C, "757d68"), (S17D, "482735")):
            soup = BeautifulSoup(h, "html.parser")
            self.assertEqual(soup.select_one('input[name="checksum"]')["value"], "")
            self.assertEqual(R.parse_send_confirm(h).checksum, cs)

    def test_units_keep_all_eleven_keys_with_zero(self):
        c = R.parse_send_confirm(S17A)
        self.assertEqual(list(c.units), [f"u{i}" for i in range(1, 11)] + ["hero"])
        self.assertEqual(c.units["hero"], 0)
        self.assertEqual(sum(c.units.values()), 10)

    def test_hero_alone_to_oasis(self):
        c = R.parse_send_confirm(S17D)
        self.assertEqual((c.event_type, c.trip_s, c.village_did), (4, 873, 65222))
        self.assertEqual((c.x, c.y, c.villagename), (-200, 171, None))
        self.assertEqual({k: v for k, v in c.units.items() if v}, {"hero": 1})
        self.assertEqual((c.scout_target, c.catapult_target1, c.catapult_target2), (None, None, None))
        self.assertEqual((c.epoch, c.kind_text, c.has_confirm), (1794019099, "掠奪荒廢之綠州", True))

    def test_trip_matches_visible_countdown(self):
        for h in CONFIRM_ALL.values():
            soup = BeautifulSoup(h, "html.parser")
            m = re.search(r"(\d+):(\d{2}):(\d{2})", soup.select_one("div#in").get_text())
            shown = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            self.assertEqual(R.parse_send_confirm(h).trip_s, shown)

    def test_target_values_when_set(self):
        html = _edit(S17A, lambda s: s.select_one('input[name="troops[0][scoutTarget]"]').attrs.update(value="1"))
        self.assertEqual(R.parse_send_confirm(html).scout_target, "1")      # 有值的樣子 ✗ 未見，原樣字串


class ErrorCases(unittest.TestCase):
    def test_bad_input(self):
        for bad in (None, "", "  ", 3, b"x"):
            with self.subTest(bad=bad):
                for fn in (R.parse_overview, R.parse_troops_home, R.parse_send_confirm):
                    with self.assertRaises(ParseError):
                        fn(bad)

    def test_overview_wrong_pages(self):
        for h in (FORM_HOME, S17A, "<html>Travian.Game.timestamp = 5;</html>"):
            with self.subTest(h[:30]):
                with self.assertRaises(ParseError):
                    R.parse_overview(h)

    def test_units_row_wrong_length(self):
        html = _edit(S6A, lambda s: s.select_one("table.troop_details.inReturn tbody.units.last td.unit").decompose())
        with self.assertRaises(ParseError):
            R.parse_overview(html)

    def test_units_cell_garbage(self):
        html = _edit(S6A, lambda s: s.select_one("table.troop_details.inReturn tbody.units.last td.unit").__setattr__("string", "abc"))
        with self.assertRaises(ParseError):
            R.parse_overview(html)

    def test_confirm_not_a_confirm_page(self):
        for h in (S6A, FORM_HOME):
            with self.assertRaises(ParseError):
                R.parse_send_confirm(h)

    def test_confirm_missing_checksum_button(self):
        html = _edit(S17A, lambda s: s.select_one("button#confirmSendTroops").decompose())
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_onclick_without_checksum(self):
        html = _edit(S17A, lambda s: s.select_one("button#confirmSendTroops").attrs.update(onclick="return false;"))
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_missing_at(self):
        html = _edit(S17A, lambda s: s.select_one("span#at").decompose())
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_negative_trip(self):
        html = _edit(S17A, lambda s: s.select_one("span#at").attrs.update(value="1"))
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_bad_action(self):
        html = _edit(S17A, lambda s: s.select_one('input[name="action"]').attrs.update(value="troopsSend/abc"))
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_village_id_mismatch(self):
        html = _edit(S17A, lambda s: s.select_one('input[name="troops[0][villageId]"]').attrs.update(value="99999"))
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_missing_troop_field(self):
        html = _edit(S17A, lambda s: s.select_one('input[name="troops[0][t11]"]').decompose())
        with self.assertRaises(ParseError):
            R.parse_send_confirm(html)

    def test_confirm_missing_coordinates_or_type(self):
        for name in ("x", "y", "eventType"):
            with self.subTest(name):
                html = _edit(S17A, lambda s, n=name: s.select_one(f'input[name="{n}"]').decompose())
                with self.assertRaises(ParseError):
                    R.parse_send_confirm(html)

    def test_error_messages_hold_no_secrets(self):
        html = _edit(S17A, lambda s: s.select_one('input[name="troops[0][villageId]"]').attrs.update(value="99999"))
        with self.assertRaises(ParseError) as cm:
            R.parse_send_confirm(html)
        self.assertNotIn("a91737", str(cm.exception))
        self.assertNotIn("99999", str(cm.exception))


class OldCodeDifferences(unittest.TestCase):
    def test_hero_is_included_in_home_units(self):
        html = _edit(S6A, lambda s: s.select_one("table.troop_details[data-did] tbody.units.last").select("td.unit")[10].__setattr__("string", "1"))
        self.assertEqual(R.parse_troops_home(html), {"u1": 238, "u3": 23, "hero": 1})

    def test_old_t_keys_are_gone(self):
        for h in (S6A, S6D):
            self.assertFalse([k for k in R.parse_overview(h).units_home if k.startswith("t")])
        self.assertNotIn("t1", R.parse_send_confirm(S17A).units)

    def test_c2_accepts_parser_output(self):
        """units_home 的輸出可直接放進 C2（鍵 u1～u10／hero、零省略）。"""
        from travian_bot.common import schema
        base = schema.contract_examples()["VillageSnapshot"]["valid"][0]["data"]
        for h in OVERVIEWS.values():
            data = dict(base, units_home=R.parse_overview(h).units_home)
            self.assertEqual(schema.validate("VillageSnapshot", data), [])


if __name__ == "__main__":
    unittest.main()
