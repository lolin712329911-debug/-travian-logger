# -*- coding: utf-8 -*-
"""A6a2：state_repo v0.1.1 的 plan_* 帳號級鍵、upsert_state、read_state。未實測（沒有整個 repo）。"""
import unittest

from travian_bot.infra.store import state_repo as SR

from .fakes import FakeSheet, patch_gspread

NOW1, NOW2 = "2026-11-15T08:00:00Z", "2026-11-15T09:00:00Z"
_p = None


def setUpModule():
    global _p
    _p = patch_gspread()
    _p.start()


def tearDownModule():
    _p.stop()


def rows_of(sh):
    return SR.gsheets.get_worksheet(sh, SR.STATE_TAB).get_all_values()[1:]


class StateRepoA6a2Test(unittest.TestCase):
    def test_plan_keys_are_account_level(self):
        for k in ("plan_status", "plan_remaining_steps", "plan_eta_h", "plan_needs_refill"):
            self.assertIn(k, SR.ACCOUNT_KEYS)
        built = SR.build_rows(101, [("plan_status", "active", "")], NOW1)
        self.assertEqual(built[0][4], "")                        # did 空白＝帳號級

    def test_upsert_keeps_village_rows_that_write_state_would_drop(self):
        sh = FakeSheet()
        SR.write_state(sh, 101, [("stock_wood", 500, ""), ("prod_wood", 100, "")], NOW1)       # observe 的村級列
        SR.upsert_state(sh, 101, [("plan_status", "active", ""), ("plan_remaining_steps", 3, "")], NOW2)
        keys = {r[0]: r for r in rows_of(sh)}
        self.assertIn("stock_wood", keys)                         # 村級列還在
        self.assertEqual(keys["plan_status"][1], "active")
        self.assertEqual(keys["plan_status"][4], "")              # 帳號級
        # 對照：write_state 只寫帳號級鍵會洗掉同村的村級列（這是 build 不能用它的原因）
        sh2 = FakeSheet()
        SR.write_state(sh2, 101, [("stock_wood", 500, "")], NOW1)
        SR.write_state(sh2, 101, [("plan_status", "active", "")], NOW2)
        self.assertNotIn("stock_wood", {r[0] for r in rows_of(sh2)})

    def test_upsert_replaces_only_same_key(self):
        sh = FakeSheet()
        SR.upsert_state(sh, 101, [("plan_status", "active", ""), ("plan_eta_h", 2.5, "")], NOW1)
        SR.upsert_state(sh, 101, [("plan_status", "idle", "")], NOW2)
        keys = {r[0]: r for r in rows_of(sh)}
        self.assertEqual(keys["plan_status"][1], "idle")
        self.assertEqual(keys["plan_status"][3], NOW2)
        self.assertEqual(keys["plan_eta_h"][3], NOW1)             # 這次沒給的鍵保留舊值與舊時間
        self.assertEqual(sum(1 for r in rows_of(sh) if r[0] == "plan_status"), 1)

    def test_upsert_blank_string_clears_value(self):
        sh = FakeSheet()
        SR.upsert_state(sh, 101, [("plan_eta_h", 2.5, "")], NOW1)
        SR.upsert_state(sh, 101, [("plan_eta_h", "", "")], NOW2)
        self.assertEqual({r[0]: r for r in rows_of(sh)}["plan_eta_h"][1], "")

    def test_read_state(self):
        sh = FakeSheet()
        self.assertEqual(SR.read_state(sh, 101, ("plan_status",)), {})                 # 沒有分頁
        SR.upsert_state(sh, 101, [("plan_status", "idle", ""), ("stock_wood", 500, "")], NOW1)
        self.assertEqual(SR.read_state(sh, 101, ("plan_status", "nope")), {"plan_status": "idle"})
        self.assertEqual(SR.read_state(sh, 202, ("stock_wood",)), {})                  # 別村的村級鍵讀不到


if __name__ == "__main__":
    unittest.main()
