#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/common/test_decisions.py（cm-02）v0.1（A1a-2）：草案結構的基本性質（欄位待 A3a～A3c 定案）。"""
import dataclasses
import unittest

from travian_bot.common import decisions, models
from travian_bot.common.decisions import (
    BUILD_KINDS, AdventureDecision, BuildDecision, ExecResult, FillInDecision, FocusDecision,
    GuardDecision, HideCandidate, HideDecision, ItemTransferDecision)

TARGET = models.BuildTarget(aid=5, gid=1, name="伐木場", to_level=3, cost=(100, 80, 60, 40), ready_in_s=0)
RESULTS = ("ok", "dry", "skipped", "failed", "deferred")


class TestDecisions(unittest.TestCase):
    def test_build_target_is_the_models_one(self):
        self.assertIs(decisions.BuildTarget, models.BuildTarget)

    def test_all_names_exported_and_frozen(self):
        for name in decisions.__all__:
            obj = getattr(decisions, name)
            if name == "BUILD_KINDS" or obj is models.BuildTarget:
                continue
            with self.subTest(name):
                self.assertTrue(dataclasses.is_dataclass(obj))
                self.assertTrue(obj.__dataclass_params__.frozen)

    def test_build_kinds_match_legacy_labels(self):
        # §6.7 舊決策標籤：等待資源、等待佇列、倉容不足、計畫卡住、無空地、已完成（＋實際升級）
        self.assertEqual(len(BUILD_KINDS), 7)
        self.assertEqual(len(set(BUILD_KINDS)), 7)
        self.assertNotIn("等待資源", BUILD_KINDS)

    def test_construct_and_plain(self):
        d = BuildDecision(kind="build", target=TARGET, reason="資源足夠")
        self.assertEqual(models.to_plain(d)["target"]["cost"], [100, 80, 60, 40])
        self.assertIsNone(d.wait_s)
        hide = HideDecision(act=True, chosen=HideCandidate(1, 2, "wood25", 3.5, None),
                            candidates=(HideCandidate(1, 2, "wood25", 3.5, None),), reason="來襲")
        self.assertEqual(models.to_plain(hide)["chosen"]["x"], 1)
        self.assertIsInstance(hide.candidates, tuple)

    def test_other_decisions_construct(self):
        GuardDecision(act=False, reason="無來襲")
        FillInDecision(act=True, target=TARGET, reason="插隊")
        FocusDecision(act=False, focus=None, reason="off")
        ItemTransferDecision(act=False, item=None, amount=None, reason="無")
        AdventureDecision(act=True, adv_id=7, reason="可出發")

    def test_exec_result_defaults(self):
        r = ExecResult(result="dry", detail="未送出")
        self.assertEqual((r.requests_used, r.verified), (0, None))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.result = "ok"


if __name__ == "__main__":
    unittest.main()
