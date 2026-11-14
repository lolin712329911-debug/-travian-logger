"""tests/common/test_constants.py — cm-03（v0.2：v0.65／v0.66 名稱表更新；v0.1，A1a-1）"""
import unittest

from travian_bot.common import constants as C


class ConstantsTest(unittest.TestCase):
    def test_resource_order_is_wood_clay_iron_crop(self):
        self.assertEqual((C.RES_WOOD, C.RES_CLAY, C.RES_IRON, C.RES_CROP), (0, 1, 2, 3))
        self.assertEqual(C.RES_KEYS, ("wood", "clay", "iron", "crop"))
        self.assertEqual(len(C.RES_NAMES), C.RES_COUNT)

    def test_gid_names_cover_card_requirements(self):
        for gid in (16, 17, 36, 29, 30, 44, 48):
            self.assertIn(gid, C.GID_NAMES)
        self.assertEqual(C.GID_NAMES[36], "陷阱機")      # v0.65：語言包全名；v0.1 的「陷阱」取自卡片
        self.assertEqual(C.GID_NAMES[17], "市場")
        self.assertEqual(C.GID_NAMES[16], "集結點")

    def test_old_table_preserved(self):
        # travian_const.py 原有 gid 名稱不能變；唯一例外 11：舊「糧倉」→遊戲翻譯「穀倉」（v0.66，使用者確認），
        # 所以下表的 11 已改成「穀倉」
        old = {1: "伐木場", 2: "泥坑", 3: "鐵礦場", 4: "農場", 10: "倉庫", 11: "穀倉", 15: "村莊大樓",
               16: "集結點", 17: "市場", 18: "大使館", 20: "馬廄", 22: "研究院", 23: "山洞",
               24: "城鎮廳", 25: "行宮", 26: "皇宮", 27: "寶物庫", 28: "交易所", 34: "石匠鋪",
               37: "英雄宅", 45: "供水系統", 5: "鋸木廠", 6: "磚廠", 7: "鋼鐵鑄造廠", 8: "麵粉廠",
               9: "麵包店", 13: "盔甲廠", 14: "競技場", 19: "兵營", 21: "工場", 38: "大倉庫",
               39: "大穀倉", 42: "石墻", 46: "醫院"}
        for gid, name in old.items():
            self.assertEqual(C.GID_NAMES[gid], name, gid)

    def test_unverified_gids_are_subset(self):
        self.assertTrue(C.UNVERIFIED_GIDS <= set(C.GID_NAMES))

    def test_gid_name_fallback(self):
        self.assertEqual(C.gid_name(1), "伐木場")
        self.assertEqual(C.gid_name(999), "建築(gid 999)")

    def test_old_misc_constants_preserved(self):
        self.assertEqual(C.BUILDING_GIDS, {10: "倉庫", 11: "穀倉"})
        self.assertEqual(C.BUILD_CATEGORIES, {1: "基礎", 2: "軍事", 3: "資源"})
        self.assertEqual(C.FREE_SLOT_RANGE, (19, 38))
        self.assertEqual(C.BIDI.sub("", "‪12‬"), "12")

    def test_ranges_consistent(self):
        self.assertEqual(C.RESOURCE_FIELD_AID_RANGE, (1, 18))
        self.assertEqual(C.BUILDING_AID_RANGE, (19, 40))
        lo, hi = C.FREE_SLOT_RANGE
        self.assertTrue(C.BUILDING_AID_RANGE[0] <= lo <= hi <= C.BUILDING_AID_RANGE[1])

    def test_action_names_fit_c5(self):
        for name in C.ACTION_NAMES:
            self.assertTrue(0 < len(name) <= 40)
        self.assertIn(C.ACTION_VILLAGE_SKIP, C.ACTION_NAMES)

    def test_paths_start_with_slash(self):
        for p in (C.PATH_DORF1, C.PATH_DORF2, C.PATH_BUILD):
            self.assertTrue(p.startswith("/") and p.endswith(".php"))

    def test_dropped_names_are_gone(self):
        for gone in ("RESOURCE_FIELD_PRODUCTION", "MAX_NON_CAPITAL_FIELD_LEVEL", "TRIBE_NAMES",
                     "ROMAN_TRIBE_ID", "DEFAULT_TARGET_BUILDING_LEVEL"):
            self.assertFalse(hasattr(C, gone), gone)


if __name__ == "__main__":
    unittest.main()
