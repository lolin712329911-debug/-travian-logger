# -*- coding: utf-8 -*-
"""viewData 讀取函式的共通測試。check_arch 禁止 parsers 互相 import，所以每個 parser 各有一份私有複本
`_view_data`；這裡用同一批案例對每份複本都跑一遍，改版時漏改任何一份都會失敗。
parsers/village.py（A2a-2a）已加進 MODULES。"""
import unittest

from travian_bot.parsers import hero, player, village, village_list

from ._util import SAMPLE_IDS, load_sample

MODULES = {"player": player, "village_list": village_list, "village": village, "hero": hero}

CASES = [
    ("plain object", 'var a = {viewData: {"k": 1}};', {"k": 1}),
    ("no space after colon", 'viewData:{"k":1}', {"k": 1}),
    ("space before colon", 'viewData : {"k": 1}', {"k": 1}),
    ("braces inside strings", 'viewData: {"k": "}{ \\" {"}', {"k": '}{ " {'}),
    ("nested", 'viewData: {"a": {"b": [1, {"c": 2}]}}', {"a": {"b": [1, {"c": 2}]}}),
    ("trailing script text", 'viewData: {"k": 1}, other: function() { return 1; }', {"k": 1}),
    ("first is not json, second is", 'viewData: undefined; viewData: {"k": 2}', {"k": 2}),
    ("chinese text", 'viewData: {"name": "村"}', {"name": "村"}),
    ("missing", "<html>nothing</html>", None),
    ("not json", "viewData: {oops}", None),
    ("list instead of object", "viewData: [1]", None),
    ("number", "viewData: 5", None),
    ("empty string", "", None),
    ("None", None, None),
    ("number input", 5, None),
    ("bytes input", b'viewData: {"k": 1}', None),
]


class TestViewDataHelpers(unittest.TestCase):
    def test_every_copy_behaves_the_same(self):
        for mod_name, mod in MODULES.items():
            for label, html, want in CASES:
                with self.subTest(module=mod_name, case=label):
                    self.assertEqual(mod._view_data(html), want)

    def test_real_samples(self):
        for sid in SAMPLE_IDS:
            results = [mod._view_data(load_sample(sid)) for mod in MODULES.values()]
            for r in results:
                self.assertIn("ownPlayer", r)
            self.assertTrue(all(r == results[0] for r in results))


if __name__ == "__main__":
    unittest.main()
