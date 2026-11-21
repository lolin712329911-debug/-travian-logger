# -*- coding: utf-8 -*-
"""ap-06 formatting（A6a1）。能對上舊 runner 的句子與舊函式逐字比對（golden 由 gen_golden_old.py 離線產生）。"""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from travian_bot.app import formatting as F
from travian_bot.common import serialize
from travian_bot.common.constants import ACTION_NAMES
from travian_bot.common.decisions import BUILD_DECISION_KINDS, BuildDecision, FactsNeed
from travian_bot.common.models import ActionRow, BuildTarget, VillageSnapshot

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "golden" / "app" / "formatting"
                     / "old_runner.expected.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 15, 8, 0, 0, tzinfo=timezone.utc)


def snap(stock=(0, 0, 0, 0), cap=(800, 800, 800, 800), queue_used=0, queue_free=0):
    return VillageSnapshot(1, "2026-11-15T08:00:00Z", tuple(stock), (1, 1, 1, 1), cap[0], cap[3], None, queue_free,
                           queue_used, None, None, (), (), 0, None, None)


def target(f):
    return BuildTarget(aid=f["aid"], gid=f["gid"], name="x", to_level=f["level"] + 1, cost=tuple(f["cost"]), ready_in_s=0)


def decision_from_old(c):
    k = c["kind"]
    if k == "wait_res":
        t = target(c["field"])
        return BuildDecision("wait_resources", t, "r", wait_s=c["secs"])
    if k == "wait_queue":
        return BuildDecision("wait_queue", None, "r", wait_s=c["secs"])
    if k == "need_storage":
        return BuildDecision("storage_too_small", target(c["field"]), "r")
    if k == "blocked":
        return BuildDecision("plan_stuck", None, c["text"])
    return BuildDecision("done", None, "r")


class DescribeGoldenTest(unittest.TestCase):
    def test_matches_old_describe_word_for_word(self):
        for c in GOLDEN["describe"]:
            d = decision_from_old(c)
            cap = c["cap"]
            s = snap(stock=c["stock"], cap=cap, queue_used=c["queue_len"])
            label, ref, detail = F.describe(d, s, c["slots"])
            self.assertEqual(label, c["label"], c["case"])
            self.assertEqual(detail, c["detail"], c["case"])
            self.assertEqual(ref.aid if ref else None, c["ref_aid"], c["case"])

    def test_mins_matches_old(self):
        for c in GOLDEN["mins"]:
            self.assertEqual(F.mins(c["secs"]), c["text"], c["secs"])

    def test_fname_flv_match_old(self):
        for c in GOLDEN["fname_flv"]:
            t = BuildTarget(aid=c["aid"], gid=c["gid"], name="x", to_level=c["level"] + 1, cost=(1, 1, 1, 1), ready_in_s=0)
            self.assertEqual(F.fname(t), c["fname"])
            self.assertEqual(F.flv(c["level"], c["gid"]), c["flv"])


class DescribeNewTest(unittest.TestCase):
    def test_gid11_name_is_deliberately_new(self):
        t = BuildTarget(aid=30, gid=11, name="x", to_level=10, cost=(1, 1, 1, 1), ready_in_s=0)
        self.assertEqual(F.fname(t), "穀倉")      # 舊 runner 是「糧倉」；v0.66 改名，不是回歸

    def test_covers_all_nine_kinds(self):
        self.assertEqual(set(F.KIND_LABELS), set(BUILD_DECISION_KINDS))
        self.assertEqual(len(BUILD_DECISION_KINDS), 9)
        t = BuildTarget(aid=3, gid=1, name="x", to_level=2, cost=(1, 1, 1, 1), ready_in_s=0)
        for k in BUILD_DECISION_KINDS:
            d = BuildDecision(k, t if k in ("build", "wait_resources", "storage_too_small") else None, "原因",
                              wait_s=60, need=FactsNeed("dorf2") if k == "need_facts" else None)
            label, ref, detail = F.describe(d, snap(), 1)
            self.assertEqual(label, F.KIND_LABELS[k])
            self.assertTrue(detail)

    def test_build_and_new_kinds_text(self):
        t = BuildTarget(aid=3, gid=1, name="x", to_level=5, cost=(1, 1, 1, 1), ready_in_s=0)
        self.assertEqual(F.describe(BuildDecision("build", t, "r"), snap(), 1)[2], "升級 伐木場(slot 3) L4→L5")
        self.assertIn("沒有任何候選付得起", F.describe(BuildDecision("no_affordable", None, "r"), snap(), 1)[2].replace("付得起", "付得起"))
        self.assertIn("aid=7", F.describe(BuildDecision("need_facts", None, "r", need=FactsNeed("build_options", 7)), snap(), 1)[2])
        self.assertEqual(F.describe(BuildDecision("no_free_slot", None, "要蓋 倉庫，但村莊沒有空地"), snap(), 1)[2],
                         "要蓋 倉庫，但村莊沒有空地")

    def test_wait_without_time_omits_estimate(self):
        t = BuildTarget(aid=3, gid=1, name="x", to_level=5, cost=(500, 0, 0, 0), ready_in_s=0)
        d = BuildDecision("wait_resources", t, "r", wait_s=None)
        self.assertNotIn("預計約", F.describe(d, snap(), 1)[2])
        self.assertNotIn("後再試", F.describe(BuildDecision("wait_queue", None, "r"), snap(), 1)[2])

    def test_wait_resources_falls_back_to_target_ready_in(self):
        t = BuildTarget(aid=3, gid=1, name="x", to_level=5, cost=(500, 0, 0, 0), ready_in_s=600)
        self.assertIn("預計約 10分", F.describe(BuildDecision("wait_resources", t, "r"), snap(), 1)[2])

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            F.describe(BuildDecision("nope", None, "r"), snap(), 1)


class WithQueueTest(unittest.TestCase):
    def test_empty_and_busy(self):
        self.assertEqual(F.with_queue("X", snap()), "X｜目前沒有施工中的項目")
        self.assertEqual(F.with_queue("X", snap(queue_used=1, queue_free=300)), "X｜施工中 1 項，最早約 5分 後空出")


class ConstantsAndLogTest(unittest.TestCase):
    def test_action_names(self):
        self.assertEqual((F.ACTION_BUILD, F.ACTION_BUILD_WAIT), ("升級", "建城等待"))
        self.assertNotIn(F.ACTION_BUILD, ACTION_NAMES)             # cm-03 沒動
        for a in (F.ACTION_BUILD, F.ACTION_BUILD_WAIT):
            row = ActionRow(ts_utc="2026-11-15T08:00:00Z", action=a, aid=None, gid=None, level=None, cost=None,
                            mode="live", result="deferred", detail="", did=1)
            self.assertEqual(row.validate(), [])

    def test_now_str_is_utc_standard(self):
        self.assertEqual(F.now_str(NOW), "2026-11-15T08:00:00Z")
        serialize.parse_utc(F.now_str(NOW))

    def test_log_line_format(self):
        self.assertEqual(F.log_line(NOW, "INFO", "observe", 101, "完成"), "2026-11-15T08:00:00Z INFO observe 101 完成")
        self.assertEqual(F.log_line(NOW, "WARN", "main", None, "x"), "2026-11-15T08:00:00Z WARN main - x")

    def test_log_line_redacts_and_is_single_line(self):
        line = F.log_line(NOW, "ERROR", "s", 1, "Cookie: sessionid=SECRET\n第二行")
        self.assertNotIn("SECRET", line)
        self.assertNotIn("\n", line)

    def test_log_line_rejects_bad_level(self):
        with self.assertRaises(ValueError):
            F.log_line(NOW, "DEBUG", "s", 1, "x")


if __name__ == "__main__":
    unittest.main()
