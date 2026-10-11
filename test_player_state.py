#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""離線測試：build_state_rows（runner.py）與 write_state（sheets_writer.py）。
不連網路、不連 Sheet。用法：python test_player_state.py（或 pytest test_player_state.py）"""
from types import SimpleNamespace

import runner
import sheets_writer


def _st(cap=(4000, 4000, 4000, 3100)):
    return SimpleNamespace(cap=list(cap))


def _d(rows):
    return {k: v for k, v, _ in rows}


def test_full_info():
    info = {"tribe_id": 6, "plus_active": False,
            "cp": {"have": 1470, "need": 2000, "per_day": 70, "used": 1, "max": 1}}
    d = _d(runner.build_state_rows(info, _st(), 1))
    assert d["tribe"] == "埃及" and d["plus_active"] == "FALSE"
    assert d["cp_have"] == 1470 and d["cp_need"] == 2000 and d["cp_gap"] == 530
    assert d["cp_per_day"] == 70 and d["cp_eta_days"] == 8        # 530/70 = 7.57 → 進位 8（與 cp_summary 一致）
    assert d["village_slots_used"] == 1 and d["village_slots_max"] == 1
    assert d["queue_slots"] == 1
    assert d["cap_wood"] == 4000 and d["cap_crop"] == 3100


def test_cp_reached():
    info = {"tribe_id": 1, "plus_active": True,
            "cp": {"have": 2100, "need": 2000, "per_day": 70, "used": 1, "max": 2}}
    d = _d(runner.build_state_rows(info, _st(), 3))
    assert d["cp_gap"] == 0 and d["cp_eta_days"] == 0 and d["plus_active"] == "TRUE"


def test_cp_per_day_zero_has_no_eta():
    info = {"cp": {"have": 100, "need": 2000, "per_day": 0, "used": 1, "max": 1}}
    d = _d(runner.build_state_rows(info, _st(), 1))
    assert d["cp_gap"] == 1900 and "cp_eta_days" not in d


def test_missing_info_does_not_guess():
    d = _d(runner.build_state_rows(None, _st(cap=(0, 0, 0, 0)), 1))
    assert d == {"queue_slots": 1}                                  # 讀不到的欄位一律不列
    d = _d(runner.build_state_rows({"tribe_id": 99}, None, 2))
    assert d["tribe"] == "種族 99" and "cap_wood" not in d


def test_write_state_overwrites_and_never_raises():
    calls = []

    class WS:
        def clear(self): calls.append("clear")
        def update(self, **kw): calls.append(("update", kw))

    class SH:
        def worksheet(self, name):
            assert name == "state"
            return WS()

    old = (sheets_writer.has_sheet, sheets_writer.open_sheet)
    try:
        sheets_writer.has_sheet = lambda: True
        sheets_writer.open_sheet = lambda: SH()
        assert sheets_writer.write_state([("cp_have", 1470, "目前文化點")], "2026-10-11 05:52:04") is True
        assert calls[0] == "clear" and calls[1][0] == "update"
        vals = calls[1][1]["values"]
        assert vals[0] == sheets_writer.STATE_HEADER
        assert vals[1] == ["cp_have", 1470, "目前文化點", "2026-10-11 05:52:04"]
        assert calls[1][1]["raw"] is True and calls[1][1]["range_name"] == "A1"

        def boom():
            raise RuntimeError("網路斷了")
        sheets_writer.open_sheet = boom
        assert sheets_writer.write_state([], "x") is False           # 失敗只回 False，不丟例外
        sheets_writer.has_sheet = lambda: False
        assert sheets_writer.write_state([], "x") is False           # 沒連 Sheet：直接略過
    finally:
        sheets_writer.has_sheet, sheets_writer.open_sheet = old


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("OK", name)
