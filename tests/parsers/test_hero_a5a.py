# -*- coding: utf-8 -*-
"""tests/parsers/test_hero_a5a.py（ps-05 v0.2 追加）v0.1（A5a）：parse_hero_attributes、parse_focus_set、parse_transfer_state。
輸入是 JSON 回應文字。既有 parse_hero_status／parse_adventures 的測試不動。"""
import json
import unittest

from travian_bot.common.parsed import HeroFocus, TransferItem, TransferState
from travian_bot.common.schema import ParseError
from travian_bot.parsers.hero import parse_focus_set, parse_hero_attributes, parse_transfer_state


def attrs(cur=1, types=(336, 1120, 1120, 1120, 1120)):
    return json.dumps({"hero": {"productionType": cur, "productionTypes": list(types)}})


class AttributesTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(parse_hero_attributes(attrs(3)), HeroFocus(current=3, types=(336, 1120, 1120, 1120, 1120)))

    def test_all_current_values(self):
        for c in range(5):
            self.assertEqual(parse_hero_attributes(attrs(c)).current, c)

    def test_bad_inputs(self):
        bad = {
            "空字串": "", "空白": "  ", "非字串": None, "不是 JSON": "<html>", "JSON 陣列": "[]",
            "沒有 hero": "{}", "hero 不是物件": '{"hero": 1}',
            "current 5": attrs(5), "current -1": attrs(-1), "current bool": attrs(True),
            "current 字串": attrs("1"), "current null": attrs(None),
            "types 4 個": attrs(types=(1, 2, 3, 4)), "types 6 個": attrs(types=(1, 2, 3, 4, 5, 6)),
            "types 含字串": attrs(types=(1, 2, 3, 4, "5")), "types 含 bool": attrs(types=(1, 2, 3, 4, True)),
            "types 不是 list": json.dumps({"hero": {"productionType": 1, "productionTypes": "x"}}),
            "缺 productionTypes": json.dumps({"hero": {"productionType": 1}}),
        }
        for name, text in bad.items():
            with self.subTest(name):
                with self.assertRaises(ParseError):
                    parse_hero_attributes(text)


class FocusSetTest(unittest.TestCase):
    def test_ok(self):
        for n in range(5):
            self.assertEqual(parse_focus_set(json.dumps({"productionType": n, "x": 1})), n)

    def test_bad(self):
        for text in ("", "<html>", "[]", "{}", '{"productionType": 5}', '{"productionType": -1}',
                     '{"productionType": true}', '{"productionType": "1"}', '{"productionType": null}', None):
            with self.subTest(text):
                with self.assertRaises(ParseError):
                    parse_focus_set(text)


def item(i, amount, type_id):
    return {"id": i, "amount": amount, "typeId": type_id, "name": "x"}


def gql(stock=(10, 20, 30, 40), inv=None, village_id=7, wh=8000, gr=9000, wrap=True):
    inv = inv if inv is not None else [item(11, 500, 145), item(12, 600, 146), item(13, 700, 147), item(14, 800, 148)]
    body = {"ownPlayer": {"hero": {"inventory": inv}, "village": {"id": village_id, "resources": {
        "lumberStock": stock[0], "clayStock": stock[1], "ironStock": stock[2], "cropStock": stock[3],
        "maxStorageCapacity": wh, "maxCropStorageCapacity": gr}}}}
    return json.dumps({"data": body} if wrap else body)


class TransferStateTest(unittest.TestCase):
    def test_ok(self):
        st = parse_transfer_state(gql())
        self.assertEqual(st, TransferState(
            village_id=7, stock=(10, 20, 30, 40), capacity=(8000, 8000, 8000, 9000),
            inventory=(TransferItem(11, 500), TransferItem(12, 600), TransferItem(13, 700), TransferItem(14, 800))))

    def test_data_wrapper_is_optional(self):
        self.assertEqual(parse_transfer_state(gql(wrap=False)), parse_transfer_state(gql(wrap=True)))

    def test_inventory_is_ordered_by_resource_not_by_list_order(self):
        inv = [item(14, 800, 148), item(11, 500, 145), item(13, 700, 147), item(12, 600, 146)]
        st = parse_transfer_state(gql(inv=inv))
        self.assertEqual([x.id for x in st.inventory], [11, 12, 13, 14])

    def test_missing_resource_items_are_none(self):
        st = parse_transfer_state(gql(inv=[item(12, 600, 146)]))
        self.assertEqual(st.inventory, (None, TransferItem(12, 600), None, None))
        self.assertEqual(parse_transfer_state(gql(inv=[])).inventory, (None,) * 4)

    def test_other_items_are_ignored(self):
        inv = [item(99, 5, 1), item(11, 500, 145), "junk", None, {"typeId": 146}]   # 最後一筆沒有 id／amount：是 146 → 要丟錯
        with self.assertRaises(ParseError):
            parse_transfer_state(gql(inv=inv))
        st = parse_transfer_state(gql(inv=inv[:4]))
        self.assertEqual(st.inventory, (TransferItem(11, 500), None, None, None))

    def test_item_fields_must_be_ints(self):
        for bad in (item("11", 5, 145), item(11, "5", 145), item(11, 5.5, 145), item(True, 5, 145), item(11, None, 145)):
            with self.subTest(bad):
                with self.assertRaises(ParseError):
                    parse_transfer_state(gql(inv=[bad]))

    def test_bad_structure(self):
        good = json.loads(gql())["data"]
        def without(*path):
            d = json.loads(json.dumps(good))
            cur = d
            for k in path[:-1]:
                cur = cur[k]
            del cur[path[-1]]
            return json.dumps({"data": d})
        bad = {
            "空字串": "", "不是 JSON": "<html>", "陣列": "[]", "沒有 ownPlayer": "{}",
            "沒有 village": without("ownPlayer", "village"),
            "沒有 hero": without("ownPlayer", "hero"),
            "沒有 inventory": without("ownPlayer", "hero", "inventory"),
            "沒有 resources": without("ownPlayer", "village", "resources"),
            "沒有 village id": without("ownPlayer", "village", "id"),
            "缺 lumberStock": without("ownPlayer", "village", "resources", "lumberStock"),
            "缺 cropStock": without("ownPlayer", "village", "resources", "cropStock"),
            "缺 maxStorageCapacity": without("ownPlayer", "village", "resources", "maxStorageCapacity"),
            "缺 maxCropStorageCapacity": without("ownPlayer", "village", "resources", "maxCropStorageCapacity"),
            "庫存不是整數": gql(stock=(1, "2", 3, 4)),
            "庫存 bool": gql(stock=(True, 2, 3, 4)),
            "容量不是整數": gql(wh="8000"),
            "inventory 不是 list": json.dumps({"data": {"ownPlayer": {"hero": {"inventory": {}}, "village": good["ownPlayer"]["village"]}}}),
        }
        for name, text in bad.items():
            with self.subTest(name):
                with self.assertRaises(ParseError):
                    parse_transfer_state(text)


if __name__ == "__main__":
    unittest.main()
