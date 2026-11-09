# -*- coding: utf-8 -*-
"""parsers/oasis.py（ps-08，A2b）的測試：golden、樣本事實、錯誤案例、舊碼差異。
樣本：tests/samples/S16_block_asia8.json（舊服 Asia 8 區塊 JSON，249 格；原檔 cp950，已轉 UTF-8；說明見 README_A2b.md）。
golden 的案例 id 固定為 "S16"（JSON 沒有時間戳）。UPDATE_GOLDEN=1 會改寫 golden；改寫要在交接區塊說明原因。"""
import collections
import dataclasses
import json
import os
import unittest

from travian_bot.common.schema import ParseError
from travian_bot.parsers import oasis as O

_HERE = os.path.dirname(os.path.abspath(__file__))
_SAMPLES = os.path.join(_HERE, "..", "samples")
_GOLDEN = os.path.join(_HERE, "..", "golden", "parsers", "oasis")
_UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

with open(os.path.join(_SAMPLES, "S16_block_asia8.json"), encoding="utf-8") as _f:
    S16_TEXT = _f.read()
S16 = json.loads(S16_TEXT)


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


def _tile(**kw):
    """造一格：預設是未佔領、木 25%、無動物的綠洲。"""
    t = {"position": {"x": 1, "y": 2}, "did": -1, "title": "{k.fo}",
         "text": "<span>(1|2)</span><br />{a:r1} {a.r1} 25%"}
    t.update(kw)
    return t


class Golden(unittest.TestCase):
    def test_golden(self):
        produced = {"S16": {"oases": [_plain(o) for o in O.parse_block_json(S16_TEXT)]}}
        _golden_check(self, "block_oasis", produced)


class SampleFacts(unittest.TestCase):
    def setUp(self):
        self.oases = O.parse_block_json(S16_TEXT)

    def test_counts(self):
        """249 格中 32 個綠洲：未佔領 25（8 無動物、17 有動物）、已佔領 7；村莊 34 與地形 183 都忽略。"""
        self.assertEqual(len(S16["tiles"]), 249)
        self.assertEqual(len(self.oases), 32)
        self.assertEqual(collections.Counter((o.taken, bool(o.animals)) for o in self.oases),
                         {(False, False): 8, (False, True): 17, (True, False): 7})

    def test_matches_old_parse_tiles_logic(self):
        """同一份 JSON：座標與已佔領判定與舊 oasis_scan.parse_tiles 的規則（{a:r 有加成、{k.bt} 或 uid＝已佔領）一致。"""
        old = [((t["position"]["x"], t["position"]["y"]), "{k.bt}" in t["title"] or "uid" in t)
               for t in S16["tiles"] if "{a:r" in t["text"]]
        self.assertEqual([((o.x, o.y), o.taken) for o in self.oases], old)

    def test_first_free_oasis(self):
        o = self.oases[0]
        self.assertEqual(o, O.BlockOasis(x=-11, y=-79, taken=False, bonuses=((1, 25),), animals=(), owner=None))

    def test_taken_have_owner_and_no_animals_listed(self):
        taken = [o for o in self.oases if o.taken]
        self.assertTrue(all(o.owner for o in taken))
        self.assertEqual(taken[0].owner, "Dadada")
        self.assertEqual(taken[1].bonuses, ((1, 25), (3, 25)))       # 磚＋穀各 25%
        self.assertTrue(all(o.animals == () for o in taken))

    def test_free_oases_have_no_owner(self):
        self.assertTrue(all(o.owner is None for o in self.oases if not o.taken))

    def test_animals(self):
        o = next(x for x in self.oases if (x.x, x.y) == (-14, -83))
        self.assertEqual(o.animals, ((35, 1), (36, 1), (37, 1)))
        o = next(x for x in self.oases if (x.x, x.y) == (-16, -84))
        self.assertEqual(o.animals, ((35, 10), (36, 10), (37, 4)))
        self.assertTrue(all(30 < u < 41 for x in self.oases for u, _n in x.animals))     # 自然界單位 u31～u40

    def test_bonus_values(self):
        self.assertEqual(collections.Counter(b for o in self.oases for b in o.bonuses),
                         {(0, 25): 14, (1, 25): 13, (3, 25): 11, (2, 25): 4, (3, 50): 1})
        self.assertTrue(all(0 <= r <= 3 for o in self.oases for r, _p in o.bonuses))

    def test_no_village_or_terrain_cell_is_returned(self):
        villages = {(t["position"]["x"], t["position"]["y"]) for t in S16["tiles"] if t["title"].startswith("{k.dt}")}
        self.assertEqual(len(villages), 34)
        self.assertFalse(villages & {(o.x, o.y) for o in self.oases})

    def test_input_forms_agree(self):
        a = O.parse_block_json(S16_TEXT)
        self.assertEqual(O.parse_block_json(S16), a)                                  # dict
        self.assertEqual(O.parse_block_json(S16_TEXT.encode("utf-8")), a)             # bytes（UTF-8）

    def test_works_without_chinese_titles(self):
        """不依賴中文字面：把所有地形格的標題清掉結果不變。"""
        tiles = [dict(t, title="") if "{a:r" not in t["text"] and not t["title"].startswith("{") else t
                 for t in S16["tiles"]]
        self.assertEqual(O.parse_block_json({"tiles": tiles}), self.oases)


class ErrorCases(unittest.TestCase):
    def test_bad_json(self):
        for bad in ("not json", "[1,2]", "{}", '{"tiles": 5}', None, 7, b"\xb4\xcb"):
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    O.parse_block_json(bad)

    def test_empty_tiles_is_empty_result(self):
        self.assertEqual(O.parse_block_json({"tiles": []}), ())

    def test_tile_not_object(self):
        with self.assertRaises(ParseError):
            O.parse_block_json({"tiles": [5]})

    def test_oasis_without_position(self):
        for pos in (None, {"x": 1}, {"x": "1", "y": 2}, {"x": True, "y": 2}):
            with self.subTest(pos=pos):
                with self.assertRaises(ParseError):
                    O.parse_block_json({"tiles": [_tile(position=pos)]})

    def test_oasis_cannot_tell_taken_or_free(self):
        with self.assertRaises(ParseError):
            O.parse_block_json({"tiles": [_tile(title="{k.something}")]})

    def test_bonus_unreadable(self):
        with self.assertRaises(ParseError):
            O.parse_block_json({"tiles": [_tile(text="{a:r1} broken")]})

    def test_bonus_resource_out_of_range(self):
        for n in (0, 5, 9):
            with self.subTest(n=n):
                with self.assertRaises(ParseError):
                    O.parse_block_json({"tiles": [_tile(text=f"{{a:r{n}}} {{a.r{n}}} 25%")]})

    def test_animals_flag_without_units(self):
        with self.assertRaises(ParseError):
            O.parse_block_json({"tiles": [_tile(text="{a:r1} {a.r1} 25%<br />{k.animals}<br />")]})

    def test_error_message_has_no_data(self):
        with self.assertRaises(ParseError) as cm:
            O.parse_block_json({"tiles": [_tile(title="{k.secret-title}")]})
        self.assertNotIn("secret-title", str(cm.exception))


class DesignChoices(unittest.TestCase):
    def test_taken_by_uid_alone(self):
        o = O.parse_block_json({"tiles": [_tile(title="{k.fo}", uid=5)]})[0]
        self.assertTrue(o.taken)                                        # 與舊規則一致：有 uid 就是已佔領

    def test_owner_cleaned(self):
        text = "{a:r2} {a.r2} 25%<br />{k.spieler} &#x202d;Bob&#x202c; &amp; Co<br />{k.allianz} X"
        o = O.parse_block_json({"tiles": [_tile(title="{k.bt}", uid=1, text=text)]})[0]
        self.assertEqual(o.owner, "Bob & Co")

    def test_mixed_percentages_kept_per_resource(self):
        text = "{a:r3} {a.r3} 25%<br />{a:r4} {a.r4} 50%"
        o = O.parse_block_json({"tiles": [_tile(text=text)]})[0]
        self.assertEqual(o.bonuses, ((2, 25), (3, 50)))


if __name__ == "__main__":
    unittest.main()
