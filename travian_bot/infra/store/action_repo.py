#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/action_repo.py（if-07）
版本：v0.1（A4b-1）
用途：Actions 分頁（C5，10 欄，只追加）：寫入動作紀錄、查某動作最近一次成功距今幾小時。
依賴：if-04（gsheets）、cm-01（models）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

與舊 sheets_writer.py（✓ 已讀）的差異（交接區塊有列）
  1. 格式：舊 9 欄、USER_ENTERED、時間 `YYYY-MM-DD HH:MM:SS`、cost 用 `/`、result 為中文；
     新 10 欄（C5，多 did）、RAW、時間 UTC `…T…Z`、cost 用 `,`、result 為 ok／dry／skipped／failed／deferred。
     舊格式不帶進來，也不做轉換（新 Sheet）。
  2. log_actions 一次寫多列（C10：stage 回傳 actions 清單由 app 統一寫入），一個 append 請求；
     寫入前逐列驗證，任何一列不合法就整批不寫（丟 ValidationError）。log_action 是單列版。
  3. 寫入失敗丟出例外（舊版吞掉只印 log）；要不要「不影響升級」由 app 決定。
  4. 不再用模組全域旗標記「表頭檢查過了」：每次寫入多讀第 1 列（一個請求），表頭不符丟 ValueError、不改表頭。
  5. last_action_age_hours 預設比對 result='ok'（舊 '成功'）；多了 did 篩選；
     四欄（時間、動作、結果、did）一次 batch_get 讀完（舊版 col_values×2＋cell＝3 次）。
     讀不到、時間讀不懂時仍保守回 0.0（擋住切換），並用 warn 回報（預設 print，已遮蔽）。
  6. detail 在寫入前由這裡 redact 並截到 300 字（最後一道把關；呼叫端仍應自己先處理）。
"""
import dataclasses
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Sequence

from ...common import serialize
from ...common.models import ACTION_COLUMNS, ActionRow, clip_text
from . import gsheets

ACTIONS_TAB = "Actions"
ACTIONS_HEADER = tuple(ACTION_COLUMNS)
DETAIL_MAX = 300


def _col(name: str) -> str:
    n = ACTIONS_HEADER.index(name) + 1
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _ensure_ws(sh: Any) -> Any:
    ws, created = gsheets.ensure_worksheet(sh, ACTIONS_TAB, rows=1000, cols=len(ACTIONS_HEADER))
    first = [] if created else ws.row_values(1)
    if not any(str(c).strip() for c in first):
        gsheets.batch_write(ws, [list(ACTIONS_HEADER)], start="A1")
    elif tuple(str(c).strip() for c in first[:len(ACTIONS_HEADER)]) != ACTIONS_HEADER:
        raise ValueError("Actions 表頭與 C5 不符（欄序固定），不改動；請檢查分頁")
    return ws


def _safe(row: ActionRow) -> ActionRow:
    if not isinstance(row, ActionRow):
        raise TypeError("log_actions 只收 ActionRow")
    return dataclasses.replace(row, detail=clip_text(serialize.redact(row.detail or ""), DETAIL_MAX))


def log_actions(sh: Any, rows: Sequence[ActionRow]) -> int:
    """把多列 ActionRow 追加到 Actions（一個請求）。回傳寫入列數；空清單不碰 Sheet。"""
    if not rows:
        return 0
    cells = [_safe(r).to_row() for r in rows]          # 全部先驗證，任何一列不合法就整批不寫
    ws = _ensure_ws(sh)
    return gsheets.batch_write(ws, cells)


def log_action(sh: Any, row: ActionRow) -> int:
    return log_actions(sh, [row])


def _flat(value_range: Any) -> List[str]:
    """batch_get 的一個欄範圍（[[v], [], [v]…]）→ 字串清單，索引＝列號－1。"""
    return ["" if not r else str(r[0]) for r in (value_range or [])]


def last_action_age_hours(sh: Any, action: str, did: Optional[int] = None, result: str = "ok", *,
                          now: Optional[datetime] = None,
                          warn: Callable[[str], None] = print) -> Optional[float]:
    """Actions 最近一筆（動作＝action、結果＝result；有給 did 就也要符合）距現在幾小時。

    沒有分頁或沒有這種列回 None。讀取失敗、或有這種列但時間讀不懂 → 回 0.0（保守：擋住切換）並 warn。
    給「最短切換間隔」用：排程每輪都是全新的行程，記不住上次。
    """
    try:
        ws = gsheets.get_worksheet(sh, ACTIONS_TAB)
        if ws is None:
            return None
        ts, acts, res, dids = (_flat(v) for v in ws.batch_get(
            [f"{_col(c)}:{_col(c)}" for c in ("ts_utc", "action", "result", "did")]))
        want_did = None if did is None else str(did)
        top = min(len(acts), len(res)) - 1
        idx = next((i for i in range(top, 0, -1)
                    if acts[i].strip() == action and res[i].strip() == result
                    and (want_did is None or (dids[i].strip() if i < len(dids) else "") == want_did)), None)
        if idx is None:
            return None
        raw = ts[idx] if idx < len(ts) else ""
        try:
            t = serialize.parse_utc(raw)
        except serialize.SerializeError:
            warn(f"Actions 最近一筆「{serialize.redact(action)}」的時間讀不懂，保守當成剛剛才發生")
            return 0.0
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - t).total_seconds() / 3600)
    except Exception as exc:  # noqa: BLE001  保守：讀取失敗＝擋住切換
        warn(f"讀取 Actions 最近一筆「{serialize.redact(action)}」失敗，保守當成剛剛才發生：{type(exc).__name__}")
        return 0.0
