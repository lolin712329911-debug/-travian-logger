# -*- coding: utf-8 -*-
"""if-05 set_keys：白名單、單次寫入、補列、失敗還原（假 worksheet，無網路）。"""
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from travian_bot.infra.store import config_repo as cr


class _WS:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]

    def get_all_values(self):
        return [list(r) for r in self.rows]


def _run(rows, values, fail_on=None):
    """回傳 (結果, 寫入呼叫清單)；fail_on＝第幾次 batch_write 丟例外（1 起算）。"""
    ws, calls = _WS(rows), []

    def fake_write(w, data, start=None):
        calls.append((start, [list(r) for r in data]))
        if fail_on is not None and len(calls) == fail_on:
            raise RuntimeError("boom")

    with mock.patch.object(cr.gsheets, "ensure_worksheet", return_value=(ws, False)), \
            mock.patch.object(cr.gsheets, "batch_write", side_effect=fake_write):
        try:
            res = cr.set_keys(object(), values)
        except Exception as exc:  # noqa: BLE001
            res = exc
    return res, calls


BASE = [["key", "value", "note"], ["enabled", "TRUE", ""], ["main_did", "", ""], ["main_did_set_utc", "", ""]]
BOTH = {"main_did": "7", "main_did_set_utc": "2026-11-21T00:00:00Z"}


class SetKeys(unittest.TestCase):
    def test_empty_returns_false_without_io(self):
        res, calls = _run(BASE, {})
        self.assertIs(res, False)
        self.assertEqual(calls, [])

    def test_whitelist_and_blank_rejected(self):
        for bad in ({"enabled": "FALSE"}, {"main_did": ""}, {"main_did": 7}):
            res, calls = _run(BASE, bad)
            self.assertIsInstance(res, ValueError)
            self.assertEqual(calls, [])

    def test_adjacent_existing_rows_single_write(self):
        res, calls = _run(BASE, BOTH)
        self.assertIs(res, True)
        self.assertEqual(calls, [("B3", [["7"], ["2026-11-21T00:00:00Z"]])])

    def test_both_missing_single_append(self):
        res, calls = _run(BASE[:2], BOTH)
        self.assertIs(res, True)
        self.assertEqual(len(calls), 1)
        self.assertEqual([r[0] for r in calls[0][1]], ["main_did", "main_did_set_utc"])

    def test_single_key_only_changes_b_column(self):
        res, calls = _run(BASE, {"main_did": "7"})
        self.assertIs(res, True)
        self.assertEqual(calls, [("B3", [["7"]])])

    def test_empty_sheet_writes_header_first(self):
        res, calls = _run([], BOTH)
        self.assertIs(res, True)
        self.assertEqual(calls[0], ("A1", [["key", "value", "note"]]))
        self.assertEqual(len(calls), 2)

    def test_non_adjacent_rows_fall_back_and_rollback_on_failure(self):
        rows = [["key", "value", "note"], ["main_did", "", ""], ["enabled", "TRUE", ""], ["main_did_set_utc", "", ""]]
        res, calls = _run(rows, BOTH, fail_on=2)
        self.assertIsInstance(res, RuntimeError)
        # 第 1 次寫 main_did、第 2 次（失敗）寫 set_utc、第 3 次還原 main_did 為舊值
        self.assertEqual(calls[0], ("B2", [["7"]]))
        self.assertEqual(calls[2], ("B2", [[""]]))

    def test_single_write_failure_propagates(self):
        res, calls = _run(BASE, BOTH, fail_on=1)
        self.assertIsInstance(res, RuntimeError)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
