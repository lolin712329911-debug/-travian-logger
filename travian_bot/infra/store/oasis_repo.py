#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/oasis_repo.py（if-10）
版本：v0.1（A4b-2）
用途：Oases 分頁（機器寫、Python 讀）：區塊掃描結果，依「掃描中心」取代，其他中心的列原樣保留。
依賴：if-04（gsheets）、cm-10（serialize）、cm-09（parsed；只用 BlockOasis 型別）。
部署狀態：未部署（GA 前不 live）。

與舊 oasis_store.py（✓ 已讀 save／load）的差異（A4b-2 交接區塊有列）
  1. 不依賴 dispatch.HOME：中心 (x, y) 由參數傳入；舊 save 整份清空，現在只取代該中心的列（B2 多中心的基礎）。
  2. 寫法同 state_repo：一次 update 寫整頁，尾端多出的舊列用空白列蓋掉（不先 clear）。
  3. `save` 拒絕空清單（掃到 0 個綠洲多半是頁面或請求異常，不拿來清掉舊資料）。
  4. 「資料夠不夠新、中心對不對」的判斷屬於 app：`list_centers` 回傳每個中心的最新更新時間與列數，由呼叫端判斷。
     舊 load 回傳 (oases, age, center) 的 age／center 因此拆出去。
  5. 欄位改嚴格格式（舊版加成是中文字串、kind 是 taken_oasis／free_oasis）：
       x, y, taken(TRUE/FALSE), bonuses_json, animals_json, owner, updated_utc, center_x, center_y
     bonuses_json＝[[資源索引 0..3＝木磚鐵穀, 百分比],…]；animals_json＝[[單位 id, 數量],…]；沒有就空白。
  6. 表頭不符（例如舊 9 欄中文表頭）：Oases 可重掃重建，視為空表重寫。讀取時表頭不符回空清單。
  7. 讀到壞列（欄位解析失敗）丟 OasisTableError，不悄悄略過。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...common import serialize
from ...common.parsed import BlockOasis
from . import gsheets

OASES_TAB = "Oases"
OASES_HEADER = ("x", "y", "taken", "bonuses_json", "animals_json", "owner", "updated_utc", "center_x", "center_y")
_N = len(OASES_HEADER)
OWNER_MAX = 60


class OasisTableError(RuntimeError):
    """Oases 分頁裡有讀不懂的列。"""


@dataclass(frozen=True)
class CenterInfo:
    x: int
    y: int
    updated_utc: Optional[str]      # 該中心最新一列的更新時間；讀不到＝None
    count: int


def _check_center(center: Any) -> Tuple[int, int]:
    if (not isinstance(center, (tuple, list)) or len(center) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) for v in center)):
        raise ValueError("center 需為 (x, y) 兩個整數")
    return int(center[0]), int(center[1])


def _pad(row: Sequence[Any]) -> List[str]:
    cells = [str(c) for c in list(row)[:_N]]
    return cells + [""] * (_N - len(cells))


def _header_ok(values: Sequence[Sequence[Any]]) -> bool:
    return bool(values) and tuple(str(c).strip() for c in values[0][:_N]) == OASES_HEADER


def _center_of(cells: Sequence[str]) -> Optional[Tuple[int, int]]:
    cx, cy = cells[7].strip(), cells[8].strip()
    ok = lambda s: s.lstrip("-").isdigit()   # noqa: E731
    return (int(cx), int(cy)) if ok(cx) and ok(cy) else None


def _row(o: BlockOasis, now: str, center: Tuple[int, int]) -> List[Any]:
    bonuses = [[b[0], b[1]] for b in o.bonuses] or None
    animals = [[a[0], a[1]] for a in o.animals] or None
    return [serialize.to_cell(o.x, "int"), serialize.to_cell(o.y, "int"), serialize.to_cell(o.taken, "bool"),
            serialize.to_cell(bonuses, "json"), serialize.to_cell(animals, "json"),
            serialize.to_cell(o.owner, "str", OWNER_MAX), now, center[0], center[1]]


def save(sh: Any, center: Tuple[int, int], oases: Sequence[BlockOasis], *, now: str) -> int:
    """只取代這個中心的列（其他中心保留）。回傳寫入的綠洲列數。now＝UTC 標準格式字串。"""
    c = _check_center(center)
    stamp = serialize.to_cell(now, "utc")
    if not oases:
        raise ValueError("oases 為空，不寫入（避免清掉舊資料）")
    seen = set()
    for o in oases:
        if (o.x, o.y) in seen:
            raise ValueError("oases 有重複座標")
        seen.add((o.x, o.y))
    new_rows = [_row(o, stamp, c) for o in sorted(oases, key=lambda o: (o.x, o.y))]

    ws, _ = gsheets.ensure_worksheet(sh, OASES_TAB, rows=500, cols=_N)
    values = ws.get_all_values()
    others: List[List[str]] = []
    if _header_ok(values):
        for r in values[1:]:
            cells = _pad(r)
            if not any(x.strip() for x in cells):
                continue
            if _center_of(cells) != c:
                others.append(cells)                 # 其他中心（含讀不懂中心的列）原樣保留

    def sk(r):
        ctr = _center_of([str(v) for v in r])
        x, y = str(r[0]).strip(), str(r[1]).strip()
        return (ctr or (1 << 40, 1 << 40), int(x) if x.lstrip("-").isdigit() else 1 << 40,
                int(y) if y.lstrip("-").isdigit() else 1 << 40)

    payload: List[List[Any]] = [list(OASES_HEADER)] + sorted(others + new_rows, key=sk)
    width = max([_N] + [len(r) for r in values])
    payload = [list(r) + [""] * (width - len(r)) for r in payload]
    stale = len(values) - len(payload)
    if stale > 0:
        payload += [[""] * width for _ in range(stale)]
    if ws.row_count < len(payload):
        ws.add_rows(len(payload) - ws.row_count)
    if ws.col_count < width:
        ws.add_cols(width - ws.col_count)
    gsheets.batch_write(ws, payload, start="A1")
    return len(new_rows)


def _pairs(cell: str) -> Tuple[Tuple[int, int], ...]:
    data = serialize.from_cell(cell, "json")
    if data is None:
        return ()
    out = []
    for item in data:
        if (not isinstance(item, list) or len(item) != 2
                or any(isinstance(v, bool) or not isinstance(v, int) for v in item)):
            raise serialize.SerializeError("pairs 格式不合法")
        out.append((item[0], item[1]))
    return tuple(out)


def load(sh: Any, center: Tuple[int, int]) -> List[BlockOasis]:
    """讀這個中心的綠洲（依 x、y 排序）。沒有分頁、表頭不符、或沒有這個中心回空清單。"""
    c = _check_center(center)
    ws = gsheets.get_worksheet(sh, OASES_TAB)
    if ws is None:
        return []
    values = ws.get_all_values()
    if not _header_ok(values):
        return []
    out = []
    for i, r in enumerate(values[1:], start=2):
        cells = _pad(r)
        if _center_of(cells) != c:
            continue
        try:
            x, y = serialize.from_cell(cells[0], "int"), serialize.from_cell(cells[1], "int")
            taken = serialize.from_cell(cells[2], "bool")
            if x is None or y is None or taken is None:
                raise serialize.SerializeError("必填欄空白")
            out.append(BlockOasis(x=x, y=y, taken=taken, bonuses=_pairs(cells[3]), animals=_pairs(cells[4]),
                                  owner=serialize.from_cell(cells[5], "str")))
        except serialize.SerializeError as exc:
            raise OasisTableError(f"Oases 第 {i} 列讀不懂：{exc}") from None
    return sorted(out, key=lambda o: (o.x, o.y))


def list_centers(sh: Any) -> List[CenterInfo]:
    """分頁裡有哪些掃描中心（依 x、y 排序）。沒有分頁或表頭不符回空清單。"""
    ws = gsheets.get_worksheet(sh, OASES_TAB)
    if ws is None:
        return []
    values = ws.get_all_values()
    if not _header_ok(values):
        return []
    acc: Dict[Tuple[int, int], List[Any]] = {}
    for r in values[1:]:
        cells = _pad(r)
        ctr = _center_of(cells)
        if ctr is None:
            continue
        slot = acc.setdefault(ctr, [None, 0])
        slot[1] += 1
        try:
            t = serialize.parse_utc(cells[6])
        except serialize.SerializeError:
            continue
        if slot[0] is None or t > slot[0][0]:
            slot[0] = (t, cells[6].strip())
    return [CenterInfo(k[0], k[1], v[0][1] if v[0] else None, v[1]) for k, v in sorted(acc.items())]
