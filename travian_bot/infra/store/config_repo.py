#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/config_repo.py（if-05）
版本：v0.1.2（A6b：set_keys 改為相鄰兩列單次寫入＋失敗還原；v0.1.1 追加 set_keys，既有行為不變）
用途：Config 分頁（key／value／note 三欄）的讀取、補齊缺少的鍵、緊急停用。
      人工編輯的分頁：只補缺的列、只改 enabled 那一列，絕不整頁覆寫。
依賴：if-04（gsheets）、if-06（village_repo；村級 disable）、cm-08（config_schema）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

與舊 sheets_writer.py（✓ 已讀）的差異（交接區塊有列）
  1. load_config 只回「原始儲存格字串」{key: value}（鍵小寫、值去空白）；型別轉換與驗證仍在
     config_schema.normalize_cfg（舊版在這裡逐鍵轉型，已搬到 cm-08）。load_normalized 是兩者的組合。
  2. 讀到的所有值都不替換成預設；缺鍵由 ensure_config_rows 補到 Sheet，再由 normalize_cfg 補預設。
  3. disable(scope, did, reason) 分帳號級與村級；**不再呼叫 notify**（infra/store 不得依賴 infra/notify，
     通知由 app 做）；寫入失敗直接丟出例外（舊版吞掉，緊急停止失敗不該被靜默）。
  4. 讀不到舊鍵不做邊界轉換（新 Sheet 重填；讀到舊鍵由 normalize_cfg 警告）。
  5. 新建的 Config 分頁第 1 列是表頭 key／value／note；既有沒有表頭的分頁維持原狀。
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...common import config_schema, serialize
from . import gsheets, village_repo

CONFIG_TAB = "Config"
CONFIG_HEADER = ("key", "value", "note")
NOTE_MAX = 200

SCOPES = ("account", "village")

# set_keys 只允許寫這些鍵（C8 村莊鎖）；其他鍵一律拒絕，避免變成通用的 Config 寫入口
SETTABLE_KEYS = ("main_did", "main_did_set_utc")


def _col(n: int) -> str:
    """1 起算的欄號 → A1 欄字母。"""
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _default_cell(value: Any) -> Any:
    """DEFAULTS 的值 → 要寫進儲存格的值（None＝空白）。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return serialize.to_cell(value, "bool")
    if isinstance(value, int):
        return serialize.to_cell(value, "int")
    if isinstance(value, float):
        return serialize.to_cell(value, "float")
    return serialize.to_cell(str(value), "str")


def parse_rows(values: Sequence[Sequence[Any]]) -> Dict[str, str]:
    """get_all_values() → {key: value}。鍵轉小寫去空白；空鍵與表頭列（key／value）略過；重複的鍵以後面為準。"""
    out: Dict[str, str] = {}
    for row in values:
        if not row:
            continue
        key = str(row[0]).strip().lower()
        if not key:
            continue
        val = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        if key == CONFIG_HEADER[0] and val.lower() == CONFIG_HEADER[1]:
            continue
        out[key] = val
    return out


def missing_rows(existing_keys) -> List[List[Any]]:
    """依 config_schema.ORDER 列出 Sheet 還沒有的鍵 → [key, 預設值, 說明]。"""
    have = {str(k).strip().lower() for k in existing_keys}
    return [[k, _default_cell(config_schema.DEFAULTS[k]), serialize.to_cell(config_schema.NOTES[k], "str")]
            for k in config_schema.ORDER if k not in have]


def ensure_config_rows(ws: Any, values: Sequence[Sequence[Any]]) -> List[List[Any]]:
    """Config 缺哪一列就補哪一列（只補缺的，已有的列不動）。回傳實際寫入的列（含新分頁的表頭）；沒有缺列回 []。

    values 是呼叫端已讀進來的 get_all_values()（不多打請求）。寫在既有資料最後一列之後；
    分頁是空的就連表頭一起寫。RAW 純文字，避免 build_order 之類的值被 Sheets 轉型。
    """
    rows = missing_rows(parse_rows(values))
    if not rows:
        return []
    start = len(values) + 1
    if start == 1:
        rows = [list(CONFIG_HEADER)] + rows
    need = start + len(rows) - 1
    if ws.row_count < need:
        ws.add_rows(need - ws.row_count)
    if ws.col_count < len(CONFIG_HEADER):
        ws.add_cols(len(CONFIG_HEADER) - ws.col_count)
    gsheets.batch_write(ws, rows, start=f"A{start}")
    return rows


def load_config(sh: Any, *, ensure: bool = True) -> Dict[str, str]:
    """讀 Config → {key: 原始儲存格字串}。分頁不存在就建立；ensure=True 時順手補齊缺少的鍵。

    讀取、建立、補齊的任何失敗都直接丟出（呼叫端中止本輪）；不回傳預設值。
    補上去的鍵也包含在回傳值裡（以寫進去的字串為準）。
    """
    ws, _ = gsheets.ensure_worksheet(sh, CONFIG_TAB, rows=100, cols=len(CONFIG_HEADER))
    values = [list(r) for r in ws.get_all_values()]
    if ensure:
        values = values + [[str(c) for c in r] for r in ensure_config_rows(ws, values)]
    return parse_rows(values)


def load_normalized(sh: Any, *, ensure: bool = True) -> Tuple[Dict[str, Any], List[config_schema.CfgProblem]]:
    """load_config ＋ config_schema.normalize_cfg → (cfg, problems)。"""
    return config_schema.normalize_cfg(load_config(sh, ensure=ensure))


def _stop_note(base: str, reason: str) -> str:
    text = f"{base}｜自動停用：{serialize.redact(reason)}" if base else f"自動停用：{serialize.redact(reason)}"
    return serialize.to_cell(text, "str", NOTE_MAX)


def disable(sh: Any, scope: str, did: Optional[int], reason: str) -> bool:
    """緊急停用。scope='account'：Config 的 enabled 設成 FALSE（沒有那列就補一列），原因寫進 note 欄；
    scope='village'：Villages 該村的 enabled 設成 FALSE（村級錯誤不關帳號）。

    回傳是否真的寫入；village 且沒有 Villages 分頁（單村模式）或找不到該 did 回 False（無法持久化，
    只靠 app 通知）。寫入失敗丟例外。不通知：通知由 app 做。
    """
    if scope not in SCOPES:
        raise ValueError("scope 只能是 account 或 village")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("disable 需要原因")
    if scope == "village":
        if isinstance(did, bool) or not isinstance(did, int) or did < 1:
            raise ValueError("village 級 disable 需要 did（int ≥ 1）")
        return village_repo.set_enabled(sh, did, False, note=reason)

    ws, _ = gsheets.ensure_worksheet(sh, CONFIG_TAB, rows=100, cols=len(CONFIG_HEADER))
    values = ws.get_all_values()
    note = _stop_note(serialize.to_cell(config_schema.NOTES["enabled"], "str"), reason)
    for i, row in enumerate(values, start=1):
        if row and str(row[0]).strip().lower() == "enabled":
            gsheets.batch_write(ws, [["FALSE", note]], start=f"B{i}")
            return True
    if not values:
        gsheets.batch_write(ws, [list(CONFIG_HEADER)], start="A1")
    gsheets.batch_write(ws, [["enabled", "FALSE", note]])
    return True


def set_keys(sh: Any, values: Dict[str, str]) -> bool:
    """寫入 SETTABLE_KEYS 內的鍵（C8 村莊鎖：第一次記錄 main_did／main_did_set_utc）。

    已有的列只改 B 欄（value）；沒有的列補在最後（含說明）。不動其他列。鍵不在白名單、值不是字串
    丟 ValueError；寫入失敗直接丟出（村莊鎖寫不進去不該靜默）。回傳是否真的寫入（values 為空回 False）。

    兩個鍵必須同時有或同時空（config_schema 會把只寫一半視為 error），所以盡量單次寫入：
      ①兩個鍵都已有列且相鄰（ensure_config_rows 依 ORDER 補列，正常情況如此）→ B 欄一次寫兩格
      ②兩個鍵都沒有列 → 一次補兩列
      ③其他（只寫一個鍵、兩列不相鄰、一有一無）→ 逐一寫；後面失敗時把已改的既有列還原再丟出
    """
    if not values:
        return False
    for k, v in values.items():
        if k not in SETTABLE_KEYS:
            raise ValueError("set_keys 只能寫 " + "、".join(SETTABLE_KEYS))
        if not isinstance(v, str) or not v.strip():
            raise ValueError("set_keys 的值需為非空字串")
    ws, _ = gsheets.ensure_worksheet(sh, CONFIG_TAB, rows=100, cols=len(CONFIG_HEADER))
    values_now = ws.get_all_values()
    if not values_now:
        gsheets.batch_write(ws, [list(CONFIG_HEADER)], start="A1")
        values_now = [list(CONFIG_HEADER)]
    rows_at: Dict[str, int] = {}
    old_value: Dict[str, str] = {}
    for i, row in enumerate(values_now, start=1):
        if row:
            k = str(row[0]).strip().lower()
            rows_at[k] = i
            old_value[k] = str(row[1]) if len(row) > 1 and row[1] is not None else ""
    keys = [k for k in SETTABLE_KEYS if k in values]
    cells = {k: serialize.to_cell(values[k], "str") for k in keys}

    def _note(k: str) -> str:
        return serialize.to_cell(config_schema.NOTES.get(k, ""), "str")

    if len(keys) == 2:
        a, b = keys
        if a in rows_at and b in rows_at and rows_at[b] == rows_at[a] + 1:
            gsheets.batch_write(ws, [[cells[a]], [cells[b]]], start=f"B{rows_at[a]}")
            return True
        if a not in rows_at and b not in rows_at:
            gsheets.batch_write(ws, [[a, cells[a], _note(a)], [b, cells[b], _note(b)]])
            return True

    done: List[str] = []
    try:
        for key in keys:
            if key in rows_at:
                gsheets.batch_write(ws, [[cells[key]]], start=f"B{rows_at[key]}")
                done.append(key)
            else:
                gsheets.batch_write(ws, [[key, cells[key], _note(key)]])
    except Exception:
        for key in done:                      # 還原已改的既有列（best-effort；補上去的新列無法精準還原）
            try:
                gsheets.batch_write(ws, [[old_value.get(key, "")]], start=f"B{rows_at[key]}")
            except Exception:  # noqa: BLE001
                pass
        raise
    return True
