# -*- coding: utf-8 -*-
"""parsers/village_list.py（ps-02）測試。樣本 S1a／S1b＝舊服 dorf1（脫敏，各以不同村為作用中），
golden 見 tests/golden/parsers/village_list/。單村、無側欄等情況沒有真實樣本，以改寫樣本測邏輯（交接區塊有記）。"""
import unittest

from travian_bot.common.models import VillageRef, to_plain
from travian_bot.common.schema import ParseError
from travian_bot.parsers.village_list import _active_village, parse_active_village, parse_village_list, resolve_home

from ._util import SAMPLE_IDS, check_golden, load_sample, mutate_view

HOME = {"S1a": (-125, -185), "S1b": (-128, -172)}
ACTIVE = {"S1a": 10002, "S1b": 10001}


def no_sidebar(html):
    return html.replace("listEntry village", "listEntryX village")


def no_viewdata(html):
    return html.replace("viewData", "viewDataX")


class TestSamples(unittest.TestCase):
    def test_golden(self):
        cases = []
        for sid in SAMPLE_IDS:
            h = load_sample(sid)
            cases.append({"sample": sid, "map_half": 200, "active_did": parse_active_village(h, 200),
                          "home": list(resolve_home(h, 200)), "villages": to_plain(parse_village_list(h, 200))})
        check_golden(self, "village_list", "dorf1", {"cases": cases})

    def test_active_and_home(self):
        for sid in SAMPLE_IDS:
            with self.subTest(sid=sid):
                h = load_sample(sid)
                self.assertEqual(parse_active_village(h), ACTIVE[sid])
                self.assertEqual(resolve_home(h), HOME[sid])
                self.assertEqual(_active_village(h, 200)["source"], "viewData+sidebar")

    def test_village_list(self):
        for sid in SAMPLE_IDS:
            with self.subTest(sid=sid):
                refs = parse_village_list(load_sample(sid), 200)
                self.assertEqual([r.did for r in refs], [10001, 10002])
                self.assertEqual([r.name for r in refs], ["VillageA", "VillageB"])
                self.assertEqual([(r.x, r.y) for r in refs], [(-128, -172), (-125, -185)])
                self.assertEqual([r.active for r in refs], [ACTIVE[sid] == 10001, ACTIVE[sid] == 10002])
                self.assertTrue(all(isinstance(r, VillageRef) and r.is_capital is None for r in refs))
                self.assertEqual(sum(r.active for r in refs), 1)
                self.assertEqual([r.validate({"map_half": 200}) for r in refs], [[], []])

    def test_list_is_same_whichever_village_is_active(self):
        a, b = (parse_village_list(load_sample(s)) for s in SAMPLE_IDS)
        self.assertEqual([(r.did, r.name, r.x, r.y) for r in a], [(r.did, r.name, r.x, r.y) for r in b])

    def test_distance_between_villages_is_kept_by_scrub(self):
        a = parse_village_list(load_sample("S1a"))
        self.assertEqual((abs(a[0].x - a[1].x), abs(a[0].y - a[1].y)), (3, 13))


class TestActiveVillageSources(unittest.TestCase):
    def test_single_source_still_works(self):
        for sid in SAMPLE_IDS:
            with self.subTest(sid=sid):
                h = load_sample(sid)
                v = _active_village(no_sidebar(h), None)
                self.assertEqual((v["id"], v["x"], v["y"], v["source"]), (ACTIVE[sid], *HOME[sid], "viewData"))
                v = _active_village(no_viewdata(h), None)
                self.assertEqual((v["id"], v["x"], v["y"], v["source"]), (ACTIVE[sid], *HOME[sid], "sidebar"))
                self.assertEqual(resolve_home(no_viewdata(h)), HOME[sid])

    def test_no_source_returns_none(self):
        h = no_viewdata(no_sidebar(load_sample("S1b")))
        self.assertIsNone(parse_active_village(h))
        self.assertIsNone(resolve_home(h))

    def test_coordinate_mismatch_returns_none(self):
        h = mutate_view(load_sample("S1b"), lambda o: o["ownPlayer"]["village"].update(x=-127))
        self.assertIsNone(parse_active_village(h))
        self.assertIsNone(resolve_home(h))

    def test_did_mismatch_returns_none(self):
        h = mutate_view(load_sample("S1b"), lambda o: o["ownPlayer"]["village"].update(id=10002))
        self.assertIsNone(parse_active_village(h))
        self.assertIsNone(resolve_home(h))

    def test_viewdata_village_without_id_falls_back_to_sidebar_id(self):
        h = mutate_view(load_sample("S1b"), lambda o: o["ownPlayer"]["village"].pop("id"))
        self.assertEqual(parse_active_village(h), 10001)

    def test_bad_coordinates_in_viewdata_are_ignored(self):
        for bad in (True, "-128", None, 1.5):
            with self.subTest(bad=bad):
                h = mutate_view(load_sample("S1b"), lambda o: o["ownPlayer"]["village"].update(x=bad))
                v = _active_village(h, None)
                self.assertEqual(v["source"], "sidebar")        # viewData 這一份被捨棄，側欄仍可用

    def test_map_half(self):
        h = load_sample("S1b")
        self.assertEqual(resolve_home(h, 200), HOME["S1b"])
        self.assertEqual(resolve_home(h, 172), HOME["S1b"])      # 剛好在邊界上（|y|＝172）
        self.assertIsNone(resolve_home(h, 171))
        self.assertIsNone(parse_active_village(h, 100))
        self.assertEqual(parse_active_village(h, None), 10001)

    def test_non_string_input(self):
        for bad in (None, 123, b"<html></html>"):
            self.assertIsNone(parse_active_village(bad))
            self.assertIsNone(resolve_home(bad))


class TestVillageListErrors(unittest.TestCase):
    def assertParseError(self, html, map_half=None):
        with self.assertRaises(ParseError) as cm:
            parse_village_list(html, map_half)
        self.assertEqual(cm.exception.page, "village_list")
        text = str(cm.exception)
        for secret in ("VillageA", "VillageB", "PLAYER", "10001", "10002"):
            self.assertNotIn(secret, text)
        return text

    def edit(self, fn, base="S1b"):
        return mutate_view(load_sample(base), fn)

    def test_unreadable_pages(self):
        for html in ("", None, 123, "<html></html>", no_viewdata(load_sample("S1a")),
                     self.edit(lambda o: o.pop("ownPlayer"))):
            with self.subTest(html=repr(html)[:30]):
                self.assertParseError(html)

    def test_village_list_field_problems(self):
        def own(o):
            return o["ownPlayer"]
        mutations = {
            "missing": lambda o: own(o).pop("villageList"),
            "empty": lambda o: own(o).update(villageList=[]),
            "not a list": lambda o: own(o).update(villageList={"id": 1}),
            "item not object": lambda o: own(o)["villageList"].append("x"),
            "no name": lambda o: own(o)["villageList"][0].pop("name"),
            "blank name": lambda o: own(o)["villageList"][0].update(name="  "),
            "bool id": lambda o: own(o)["villageList"][0].update(id=True),
            "text coordinate": lambda o: own(o)["villageList"][0].update(x="-128"),
            "duplicate did": lambda o: own(o)["villageList"][1].update(id=10001),
            "no active id": lambda o: own(o)["village"].pop("id"),
            "active not in list": lambda o: own(o)["village"].update(id=99999),
            "no active village": lambda o: own(o).pop("village"),
        }
        for label, fn in mutations.items():
            with self.subTest(label):
                self.assertParseError(self.edit(fn))

    def test_sidebar_conflicts(self):
        def own(o):
            return o["ownPlayer"]
        cases = {
            "list has a village the sidebar lacks": lambda o: own(o)["villageList"].append(
                {"id": 10003, "name": "VillageC", "x": 1, "y": 2}),
            "sidebar has a village the list lacks": lambda o: own(o).update(villageList=own(o)["villageList"][:1]),
            "coordinates differ": lambda o: own(o)["villageList"][0].update(x=-127),
            "active village differs": lambda o: own(o)["village"].update(id=10002),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                text = self.assertParseError(self.edit(fn))
                self.assertIn("不一致", text)

    def test_contract_violations(self):
        long_name = "x" * 61
        self.assertIn("VillageRef", self.assertParseError(
            no_sidebar(self.edit(lambda o: o["ownPlayer"]["villageList"][0].update(name=long_name)))))
        # 座標範圍只在有給 map_half 時檢查（同 schema 的 ctx 慣例）
        self.assertEqual(len(parse_village_list(
            no_sidebar(self.edit(lambda o: o["ownPlayer"]["villageList"][0].update(x=999))))), 2)
        self.assertIn("VillageRef", self.assertParseError(
            no_sidebar(self.edit(lambda o: o["ownPlayer"]["villageList"][0].update(x=999))), 200))

    def test_map_half_applies_to_list(self):
        self.assertEqual(len(parse_village_list(load_sample("S1b"), 200)), 2)
        self.assertParseError(load_sample("S1b"), 100)

    def test_no_sidebar_is_not_a_conflict(self):
        refs = parse_village_list(no_sidebar(load_sample("S1b")))
        self.assertEqual([(r.did, r.active) for r in refs], [(10001, True), (10002, False)])

    def test_single_village_page_without_sidebar(self):
        def one(o):
            o["ownPlayer"]["villageList"] = o["ownPlayer"]["villageList"][:1]
        refs = parse_village_list(no_sidebar(self.edit(one)))          # 改寫樣本，非真實單村頁
        self.assertEqual(len(refs), 1)
        self.assertEqual((refs[0].did, refs[0].active, refs[0].is_capital), (10001, True, None))


if __name__ == "__main__":
    unittest.main()
