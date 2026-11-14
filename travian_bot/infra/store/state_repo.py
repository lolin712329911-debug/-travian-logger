#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/state_repo.py（if-08）
版本：v0.1（A4b-1）
用途：state 分頁（Python 機器寫、Apps Script／Gemini 讀）：每村各一組 key／value，依 did 區塊取代。
依賴：if-04（gsheets）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

格式（草案，待你同意升契約）：  key｜value｜note｜updated_utc｜did
  · 前 4 欄的位置與舊版相同，Apps Script 的 readState_（讀 A、B、D 欄）不用改；did 是追加欄。
  · did 空白＝帳號級（ACCOUNT_KEYS：種族、Plus、文化點、村莊名額）；其餘鍵屬於該村。
  · value 的 bool 寫 TRUE／FALSE；updated_utc 是 `YYYY-MM-DDTHH:MM:SSZ`。全部 RAW。

與舊 sheets_writer.write_state（✓ 已讀）的差異
  1. 舊版整頁清空再寫；新版只取代這個 did 的列（與有給帳號級鍵時的帳號級列），其他村的列原樣保留。
  2. 寫法：一次 update 把整頁寫回，尾端多出的舊列用空白列蓋掉（不先 clear，寫到一半失敗不會清空別村）。
  3. 帳號級鍵「本次有給才取代」：這次沒給的帳號級鍵（例如頁面讀不到文化點）會留著舊值，但 updated_utc 是舊的，
     讀的人以 updated_utc 判斷是否過期（舊版是整頁覆蓋，讀不到就消失）。
  4. 其他村保留下來的列是以字串寫回（Sheet 讀回來的就是字串；Apps Script 以 Number() 轉，不影響）。
  5. 表頭不符（例如舊 4 欄版）：state 是機器產生、可重建，視為空表重寫；人工編輯的分頁不適用這條。
  6. 失敗丟例外（舊版吞掉回 False）。
"""
from typing import Any, List, Sequence, Tuple

from ...common import serialize
from . import gsheets

STATE_TAB = "state"
STATE_HEADER = ("key", "value", "note", "updated_utc", "did")
ACCOUNT_KEYS = frozenset({"tribe", "plus_active", "cp_have", "cp_need", "cp_gap", "cp_eta_days",
                          "cp_per_day", "village_slots_used", "village_slots_max"})
NOTE_MAX = 200
_N = len(STATE_HEADER)


def _value_cell(v: Any) -> Any:
    if isinstance(v, bool):
        return serialize.to_cell(v, "bool")
    if isinstance(v, int):
        return serialize.to_cell(v, "int")
    if isinstance(v, float):
        return serialize.to_cell(v, "float")
    if isinstance(v, str):
        return serialize.to_cell(v, "str")
    raise ValueError(f"state 的值型別不合法（{type(v).__name__}）")


def build_rows(did: int, rows: Sequence[Tuple[str, Any, str]], updated_utc: str) -> List[List[Any]]:
    """[(key, value, note)] → 儲存格列（帳號級鍵 did 留空）。None 值的鍵略過（讀不到就不列）。"""
    if isinstance(did, bool) or not isinstance(did, int) or did < 1:
        raise ValueError("did 需為 int ≥ 1")
    stamp = serialize.to_cell(updated_utc, "utc")
    out, seen = [], set()
    for key, value, note in rows:
        if not isinstance(key, str) or not key.strip() or any(ch.isspace() for ch in key):
            raise ValueError("state 的 key 不可為空或含空白")
        if key in seen:
            raise ValueError("state 的 key 重複")
        seen.add(key)
        if value is None:
            continue
        out.append([key, _value_cell(value), serialize.to_cell(serialize.redact(note or ""), "str", NOTE_MAX),
                    stamp, "" if key in ACCOUNT_KEYS else did])
    return out


def _pad(row: Sequence[Any]) -> List[str]:
    cells = [str(c) for c in list(row)[:_N]]
    return cells + [""] * (_N - len(cells))


def merge_rows(old_rows: Sequence[Sequence[Any]], did: int, new_rows: Sequence[Sequence[Any]]) -> List[List[Any]]:
    """舊列（不含表頭）＋這個 did 的新列 → 合併後的全部列（帳號級在前，村依 did 由小到大）。"""
    has_account = any(r[4] == "" for r in new_rows)
    kept = []
    for r in old_rows:
        cells = _pad(r)
        if not cells[0].strip():
            continue
        if cells[4].strip() == str(did):
            continue                                    # 這個村的舊列：整組取代
        if cells[4].strip() == "" and has_account:
            continue                                    # 帳號級舊列：這次有給才取代
        kept.append(cells)
    allrows: List[List[Any]] = kept + [list(r) for r in new_rows]

    def sort_key(r):
        d = str(r[4]).strip()
        return (0, 0) if d == "" else (1, int(d)) if d.isdigit() else (2, 0)

    return sorted(allrows, key=sort_key)               # sorted 穩定：同一區塊內維持原順序


def write_state(sh: Any, did: int, rows: Sequence[Tuple[str, Any, str]], updated_utc: str) -> int:
    """把一個村的 state 寫進分頁（依 did 區塊取代）。回傳這次寫入的列數（不含保留的其他列）。"""
    new_rows = build_rows(did, rows, updated_utc)
    ws, _ = gsheets.ensure_worksheet(sh, STATE_TAB, rows=100, cols=_N)
    values = ws.get_all_values()
    header_ok = bool(values) and tuple(str(c).strip() for c in values[0][:_N]) == STATE_HEADER
    old = values[1:] if header_ok else []
    merged = merge_rows(old, did, new_rows)
    payload: List[List[Any]] = [list(STATE_HEADER)] + merged
    stale = len(values) - len(payload)
    if stale > 0:
        payload += [[""] * _N for _ in range(stale)]    # 蓋掉尾端多出的舊列（不先 clear）
    if ws.row_count < len(payload):
        ws.add_rows(len(payload) - ws.row_count)
    if ws.col_count < _N:
        ws.add_cols(_N - ws.col_count)
    gsheets.batch_write(ws, payload, start="A1")
    return len(new_rows)
