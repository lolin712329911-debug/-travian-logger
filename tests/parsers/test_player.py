# -*- coding: utf-8 -*-
"""parsers/player.py（ps-04）測試。樣本 S1a／S1b＝舊服 dorf1（脫敏），golden 見 tests/golden/parsers/player/。"""
import unittest

from travian_bot.common.models import to_plain
from travian_bot.common.parsed import PlayerInfo
from travian_bot.common.schema import ParseError
from travian_bot.parsers.player import parse_player_info

from ._util import SAMPLE_IDS, check_golden, load_meta, load_sample, mutate_view, view_page

OWN = {"tribeId": 3, "goldFeatures": {"travianPlus": {"isActive": True}},
       "culturalPointsOverview": {"cpProducedForNextSlot": 10, "cpNeededForNextSlot": 20, "cpProductionTotal": 5,
                                  "usedSlots": 1, "maxControllableVillages": 2}}


def page(**over):
    own = {k: (dict(v) if isinstance(v, dict) else v) for k, v in OWN.items()}
    own.update(over)
    return view_page({"ownPlayer": own})


class TestSamples(unittest.TestCase):
    def test_meta_is_scrubbed(self):
        for sid in SAMPLE_IDS:
            meta = load_meta(sid)
            self.assertIs(meta["scrubbed"], True)
            self.assertEqual(meta["sample_id"], sid)

    def test_golden(self):
        cases = [{"sample": sid, "expected": to_plain(parse_player_info(load_sample(sid)))} for sid in SAMPLE_IDS]
        check_golden(self, "player", "dorf1", {"cases": cases})

    def test_values(self):
        a, b = (parse_player_info(load_sample(s)) for s in SAMPLE_IDS)
        self.assertEqual(a, PlayerInfo(3, True, 1536, 6000, 275, 2, 2))
        self.assertEqual(b, PlayerInfo(3, True, 1538, 6000, 275, 2, 2))

    def test_same_player_whichever_village_is_active(self):
        a, b = (parse_player_info(load_sample(s)) for s in SAMPLE_IDS)
        self.assertEqual((a.tribe_id, a.plus_active, a.village_slots_max), (b.tribe_id, b.plus_active, b.village_slots_max))


class TestWholePageUnreadable(unittest.TestCase):
    def test_raises_parse_error(self):
        sample = load_sample("S1a")
        bad = [
            "", "<html></html>", None, 123, b"viewData: {}",
            sample.replace("viewData", "viewDataX"),
            "viewData: undefined",
            "viewData: [1, 2]",
            view_page({}),
            view_page({"ownPlayer": None}),
            view_page({"ownPlayer": [1]}),
            view_page({"ownPlayer": "x"}),
        ]
        for html in bad:
            with self.subTest(html=repr(html)[:40]):
                with self.assertRaises(ParseError) as cm:
                    parse_player_info(html)
                self.assertEqual(cm.exception.page, "player")

    def test_error_message_has_no_page_content(self):
        sample = mutate_view(load_sample("S1a"), lambda o: o.pop("ownPlayer"))
        with self.assertRaises(ParseError) as cm:
            parse_player_info(sample)
        text = str(cm.exception)
        for secret in ("VillageA", "VillageB", "PLAYER", "10001", "10002"):
            self.assertNotIn(secret, text)

    def test_second_viewdata_used_when_first_is_not_json(self):
        html = "x = {viewData: undefined}; y = {viewData: " + '{"ownPlayer": {"tribeId": 3}}' + "}"
        self.assertEqual(parse_player_info(html).tribe_id, 3)


class TestFields(unittest.TestCase):
    def test_plus(self):
        cases = [(True, True), (False, False), ("true", None), (1, None), (None, None)]
        for raw, want in cases:
            with self.subTest(raw=raw):
                info = parse_player_info(page(goldFeatures={"travianPlus": {"isActive": raw}}))
                self.assertEqual(info.plus_active, want)
        for gf in (None, {}, {"travianPlus": None}, {"travianPlus": {}}, "x", {"travianPlus": [1]}):
            with self.subTest(goldFeatures=gf):
                self.assertIsNone(parse_player_info(page(goldFeatures=gf)).plus_active)

    def test_tribe_id(self):
        cases = [(3, 3), ("3", 3), (3.0, 3), (3.5, None), (True, None), (False, None), (None, None), ("x", None)]
        for raw, want in cases:
            with self.subTest(raw=raw):
                self.assertEqual(parse_player_info(page(tribeId=raw)).tribe_id, want)
        own = dict(OWN)
        del own["tribeId"]
        self.assertIsNone(parse_player_info(view_page({"ownPlayer": own})).tribe_id)

    def test_cp_values_accept_numeric_text_and_integral_float(self):
        cp = {"cpProducedForNextSlot": "10", "cpNeededForNextSlot": 20.0, "cpProductionTotal": " 5 ",
              "usedSlots": 1, "maxControllableVillages": 2}
        info = parse_player_info(page(culturalPointsOverview=cp))
        self.assertEqual((info.cp_have, info.cp_need, info.cp_per_day, info.village_slots_used,
                          info.village_slots_max), (10, 20, 5, 1, 2))

    def test_cp_all_or_nothing(self):
        keys = list(OWN["culturalPointsOverview"])
        for key in keys:
            for broken in ("missing", None, True, "1.5", "x", 2.5):
                with self.subTest(key=key, broken=broken):
                    cp = dict(OWN["culturalPointsOverview"])
                    if broken == "missing":
                        del cp[key]
                    else:
                        cp[key] = broken
                    info = parse_player_info(page(culturalPointsOverview=cp))
                    self.assertEqual((info.cp_have, info.cp_need, info.cp_per_day, info.village_slots_used,
                                      info.village_slots_max), (None,) * 5)
                    self.assertEqual(info.tribe_id, 3)       # 其他欄位不受影響
                    self.assertIs(info.plus_active, True)

    def test_cp_section_unusable(self):
        for cp in (None, [], "x", 5):
            with self.subTest(cp=cp):
                info = parse_player_info(page(culturalPointsOverview=cp))
                self.assertEqual(info, PlayerInfo(3, True, None, None, None, None, None))

    def test_works_on_any_page_that_has_viewdata(self):
        html = "<html><body><div>dorf2</div><script>window.x = {viewData: " \
               '{"ownPlayer": {"tribeId": 6}, "bootstrapData": {}}};</script></body></html>'
        self.assertEqual(parse_player_info(html), PlayerInfo(6, None, None, None, None, None, None))

    def test_sample_with_edited_plus(self):
        html = mutate_view(load_sample("S1a"), lambda o: o["ownPlayer"]["goldFeatures"]["travianPlus"].update(isActive=False))
        self.assertIs(parse_player_info(html).plus_active, False)


if __name__ == "__main__":
    unittest.main()
