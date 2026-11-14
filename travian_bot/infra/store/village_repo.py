#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/village_repo.py（if-06）
版本：v0.1（A4b-1）
用途：Villages 分頁（C6，一列一村）。A4b 只有唯讀的 load_villages，加上從 B2 提前的 set_enabled
      （村級緊急停用要用）。ensure_villages_tab、add_detected 仍留給 B2。
      人工編輯的分頁：表頭不符只報錯、不覆寫。
依賴：if-04（gsheets）、cm-01（models）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

規則
  · 沒有 Villages 分頁、或只有表頭＝單村模式，load_villages 回 []。
  · 每列用 VillageSettingsRow.from_row 讀（空白欄位採 C6 預設），讀完再驗全表規則
    （did 不重複、最多 1 列 is_capital），任何不合法丟 VillageTableError（只含列號、欄位、規則，不含值）。
  · 全空白的列略過。
"""
from typing import Any, List, Optional, Sequence

from ...common import serialize
from ...common.models import (VILLAGE_COLUMNS, ValidationError, VillageSettingsRow,
                              clip_text, validate_village_table)
from . import gsheets

VILLAGES_TAB = "Villages"
VILLAGES_HEADER = tuple(VILLAGE_COLUMNS)
NOTE_MAX = 200


class VillageTableError(ValueError):
    """Villages 分頁格式或內容不合法。訊息不含儲存格內容。"""


def _col(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _blank_row(row: Sequence[Any]) -> bool:
    return all(str(c).strip() == "" for c in row)


def _check_header(values: Sequence[Sequence[Any]]) -> None:
    head = tuple(str(c).strip() for c in values[0][:len(VILLAGES_HEADER)])
    if head != VILLAGES_HEADER:
        raise VillageTableError("Villages 表頭與 C6 不符（欄序固定：" + "、".join(VILLAGES_HEADER) + "）")


def load_villages(sh: Any) -> List[VillageSettingsRow]:
    """讀 Villages → list[VillageSettingsRow]。沒有分頁或沒有資料列回 []（單村模式）。"""
    ws = gsheets.get_worksheet(sh, VILLAGES_TAB)
    if ws is None:
        return []
    values = ws.get_all_values()
    if not values or _blank_row(values[0]):
        return []
    _check_header(values)
    rows: List[VillageSettingsRow] = []
    for i, cells in enumerate(values[1:], start=2):
        if _blank_row(cells):
            continue
        try:
            rows.append(VillageSettingsRow.from_row(cells))
        except ValidationError as exc:
            raise VillageTableError(f"Villages 第 {i} 列不合法：{exc}") from None
    errors = validate_village_table(rows)
    if errors:
        raise VillageTableError(f"Villages 全表規則不合法：{errors[0]}")
    return rows


def set_enabled(sh: Any, did: int, enabled: bool, note: Optional[str] = None) -> bool:
    """把某村的 enabled 設成 TRUE／FALSE。note 有給時放在該列既有 note 的前面（以｜分隔，≤200 字，已遮蔽機密；超長時截掉的是舊 note）。

    回傳是否寫入；沒有 Villages 分頁（單村模式）或找不到該 did 回 False。表頭不符丟 VillageTableError。
    寫入失敗直接丟出。只改這一列的 enabled（與 note），不動別的欄位。
    """
    if isinstance(did, bool) or not isinstance(did, int) or did < 1:
        raise ValueError("did 需為 int ≥ 1")
    if not isinstance(enabled, bool):
        raise ValueError("enabled 需為 bool")
    ws = gsheets.get_worksheet(sh, VILLAGES_TAB)
    if ws is None:
        return False
    values = ws.get_all_values()
    if not values or _blank_row(values[0]):
        return False
    _check_header(values)
    c_enabled = VILLAGES_HEADER.index("enabled") + 1
    c_note = VILLAGES_HEADER.index("note") + 1
    for i, cells in enumerate(values[1:], start=2):
        try:
            if serialize.from_cell(cells[0] if cells else "", "int") != did:
                continue
        except serialize.SerializeError:
            continue
        gsheets.batch_write(ws, [[serialize.to_cell(enabled, "bool")]], start=f"{_col(c_enabled)}{i}")
        if note:
            old = str(cells[c_note - 1]).strip() if len(cells) >= c_note else ""
            text = serialize.redact(note)
            merged = f"{text}｜{old}" if old else text
            gsheets.batch_write(ws, [[clip_text(merged, NOTE_MAX)]], start=f"{_col(c_note)}{i}")
        return True
    return False
