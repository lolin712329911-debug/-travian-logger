# -*- coding: utf-8 -*-
"""tests/common/test_names_langpack.py（v0.65）
檢查 constants.GID_NAMES 與 tribe_data.tribe_display_name 的顯示名稱表（台灣服語言包）。
只測資料的內部一致性，不涉及網路與 Sheet。
"""
import unittest

from travian_bot.common import constants as C
from travian_bot.common import tribe_data as T


class GidNames(unittest.TestCase):
    def test_covers_langpack_gids_except_12(self):
        self.assertEqual(set(C.GID_NAMES), set(range(1, 51)) - {12})
        self.assertEqual(len(C.GID_NAMES), 49)

    def test_gid12_falls_back(self):
        self.assertEqual(C.gid_name(12), "建築(gid 12)")

    def test_corrected_names(self):
        self.assertEqual(C.GID_NAMES[36], "陷阱機")
        self.assertEqual(C.GID_NAMES[48], "醫神神殿")      # v0.2 的「大工場」是猜測
        self.assertEqual(C.GID_NAMES[11], "穀倉")          # v0.66：遊戲翻譯（舊 bot 用「糧倉」）
        self.assertEqual(C.GID_NAMES[13], "盔甲廠")        # 使用者確認遊戲畫面

    def test_building_gids_agree_with_gid_names(self):
        for gid, name in C.BUILDING_GIDS.items():
            self.assertEqual(C.GID_NAMES[gid], name)

    def test_unverified_and_langpack_only(self):
        self.assertEqual(C.UNVERIFIED_GIDS, frozenset({29, 30, 44, 48}))
        self.assertTrue(C.UNVERIFIED_GIDS <= C.LANGPACK_ONLY_GIDS)
        self.assertTrue(C.LANGPACK_ONLY_GIDS <= set(C.GID_NAMES))

    def test_tribe_gids_have_names(self):
        for spec in T.TRIBES.values():
            for gid in (spec.wall_gid, spec.trap_gid):
                self.assertTrue(gid is None or gid in C.GID_NAMES, (spec.key, gid))


class TribeDisplayNames(unittest.TestCase):
    def test_known_ids(self):
        want = {0: "無種族", 1: "羅馬", 2: "條頓", 3: "高盧", 4: "自然界", 5: "賴達族",
                6: "埃及", 7: "匈奴", 8: "斯巴達人", 9: "維京人"}
        for tid, name in want.items():
            self.assertEqual(T.tribe_display_name(tid), name)

    def test_spec_tribes_use_spec_name(self):
        for spec in T.TRIBES.values():
            self.assertEqual(T.tribe_display_name(spec.tribe_id), spec.name)

    def test_fallbacks(self):
        self.assertEqual(T.tribe_display_name(10), "種族 10")
        for bad in (None, True, "3", 3.0):
            self.assertEqual(T.tribe_display_name(bad), "種族 ?")

    def test_display_name_resolves_back(self):
        for tid in (1, 2, 3, 6):
            self.assertIsNotNone(T.resolve_tribe(T.tribe_display_name(tid)))


if __name__ == "__main__":
    unittest.main()
