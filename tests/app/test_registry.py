# -*- coding: utf-8 -*-
"""ap-04 registry（A6a1）。"""
import unittest

from travian_bot.app import registry as R
from travian_bot.app import stage_base as SB
from travian_bot.common import schema


def mk(name, scope="village", mode_key="guard", order=10):
    return SB.Stage(name=name, scope=scope, mode_key=mode_key, order=order,
                    precondition=lambda rc, vc, snap: True, run=lambda rc, vc, snap, mode: None)


class RegistryTest(unittest.TestCase):
    def test_a6a1_table_is_empty(self):
        self.assertEqual(R.STAGES, ())
        self.assertEqual(R.village_stages(), ())
        self.assertEqual(R.account_stages(), ())

    def test_mode_keys_match_schema_c9(self):
        self.assertEqual(SB.STAGE_MODE_KEYS, schema.CTX_MODE_KEYS)
        self.assertEqual(len(SB.STAGE_MODE_KEYS), 9)

    def test_split_by_scope_and_sorted_by_order_then_name(self):
        t = [mk("b", order=2), mk("a", order=2), mk("z", order=1), mk("acc", "account", "market", 5)]
        self.assertEqual([s.name for s in R.village_stages(t)], ["z", "a", "b"])
        self.assertEqual([s.name for s in R.account_stages(t)], ["acc"])

    def test_build_stage_may_have_no_mode_key(self):
        self.assertEqual(len(R.village_stages([mk("build", mode_key=None, order=1)])), 1)

    def test_every_valid_mode_key_is_accepted(self):
        for i, k in enumerate(SB.STAGE_MODE_KEYS):
            R.validate_stages([mk(f"s{i}", mode_key=k)])

    def test_rejects_bad_tables(self):
        bad = [
            [mk("a"), mk("a")],                          # 名稱重複
            [mk("a", scope="global")],                   # scope 不合法
            [mk("a", mode_key="build")],                 # mode_key 不在 9 個鍵
            [mk("a", order=True)],                       # order 是 bool
            [mk("a", order="1")],                        # order 不是 int
            [mk("  ")],                                  # 空名稱
            ["not a stage"],
        ]
        for t in bad:
            with self.assertRaises(ValueError, msg=str(t)):
                R.village_stages(t)
            with self.assertRaises(ValueError):
                R.account_stages(t)


if __name__ == "__main__":
    unittest.main()
