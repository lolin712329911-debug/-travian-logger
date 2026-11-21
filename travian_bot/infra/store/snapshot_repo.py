#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/snapshot_repo.py（if-09）
版本：v0.1（A4b-2）
用途：村莊快照與結構記錄的 Sheet 讀寫。
  · Sheet1     每輪追加一列（24 欄舊欄序＋did；只追加）
  · Fields／Buildings／Buildable   依 did 取代；有差異才寫；每列帶「最後變動」
  · Changes    只追加；差異由本檔以 Sheet 為準比對後產生
依賴：if-04（gsheets）、cm-10（serialize）、cm-09（parsed；只用型別，不呼叫 parsers）。
部署狀態：未部署（GA 前不 live）。

與卡片的差異（A4b-2 交接區塊有列；原因：舊源讀碼後判定「重新規劃」）
  1. `append_row(VillageSnapshot)` → `append_snapshot(sh, did, SnapshotLogRow, ...)`：C2 沒有人口、忠誠度、金銀幣、英雄、
     Plus／保護、來襲等 Sheet1 欄位，所以用本檔的 SnapshotLogRow（做法同 plan_repo.RawBuildOrder，不進 cm-01，契約不升版）。
  2. `write_structure` 不再接收「變動」：差異比對需要 Sheet 現況，只有 repo 看得到；比對與 Changes 追加都在本檔。
     解析與 gid→名稱查表不在本檔：輸入是 cm-09 的 ResField／BuildingSlot／BuildOption，名稱由呼叫端以 names 傳入（顯示用）。
  3. 新增 `buildable_due`（Buildable 是否要重抓；舊 village_log.buildable_due）。
  4. 失敗丟例外（舊版吞掉）；寫入順序＝先寫狀態分頁、再追加 Changes；某一步失敗時，前面步驟已產生的 Changes 仍會追加。
格式（全部 RAW；時間 `YYYY-MM-DDTHH:MM:SSZ`；bool TRUE／FALSE；資源展開 4 欄；工期整數秒；did 在最後；空值留空）
  Sheet1     舊 24 欄欄名與欄序不變（Apps Script 讀欄名），＋did；「抓取時間(UTC)」改 UTC 標準格式；
             「施工佇列」內容改緊湊 JSON `[{"info":…,"remaining_s":…}]`（沒有施工＝空白）。
             舊 24 欄表頭的分頁會原地補上 did 欄頭，舊資料列不動。
  Fields     aid, gid, name, level, building, cost_*×4, duration_s, last_changed_utc, did
  Buildings  aid, gid, name, level, building, last_changed_utc, did      （空地 gid／name 空白、level 0）
  Buildable  gid, name, cost_*×4, duration_s, prereq_met, unmet_json, last_changed_utc, last_checked_utc, did
  Changes    ts_utc, kind, position, gid, name, old, new, note, did      （kind 為英文列舉，見下）
  name 欄只供顯示（Gemini／人看），程式不讀回做決策。
Changes.kind：initialized、field_added／removed／type_changed／level／build_started、
  building_slot_added／slot_removed／built／removed／changed／level／build_started、
  buildable_added／removed、prereq_met／prereq_unmet。
Buildable 沒有 category 欄：cm-09 的 BuildOption 沒有分類（舊版取自 build.php 三個分頁）。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ...common import serialize
from ...common.parsed import BuildingSlot, BuildOption, QueueItem, ResField
from . import gsheets

SHEET1_TAB, FIELDS_TAB, BUILDINGS_TAB, BUILDABLE_TAB, CHANGES_TAB = (
    "Sheet1", "Fields", "Buildings", "Buildable", "Changes")

_SHEET1_V1 = (
    "抓取時間(UTC)", "伺服器時間", "村莊名", "人口", "忠誠度%",
    "金幣", "銀幣",
    "木材_存量", "木材_產量", "磚塊_存量", "磚塊_產量",
    "鋼鐵_存量", "鋼鐵_產量", "穀物_存量", "穀物_產量", "自由穀物",
    "英雄血量%", "英雄經驗%", "英雄可用冒險數",
    "施工佇列", "Plus剩餘(小時)", "新手保護剩餘(小時)",
    "來襲波數", "最快來襲剩餘(分)",
)
SHEET1_HEADER = _SHEET1_V1 + ("did",)

_RES = ("cost_wood", "cost_clay", "cost_iron", "cost_crop")
FIELDS_HEADER = ("aid", "gid", "name", "level", "building") + _RES + ("duration_s", "last_changed_utc", "did")
BUILDINGS_HEADER = ("aid", "gid", "name", "level", "building", "last_changed_utc", "did")
BUILDABLE_HEADER = (("gid", "name") + _RES + ("duration_s", "prereq_met", "unmet_json",
                                              "last_changed_utc", "last_checked_utc", "did"))
CHANGES_HEADER = ("ts_utc", "kind", "position", "gid", "name", "old", "new", "note", "did")

_FIELDS_N, _BUILDINGS_N, _BUILDABLE_N = 10, 5, 9      # 資料欄數（後面接 last_changed 等 meta 欄與 did）
BUILDABLE_MAX_AGE_S = 24 * 3600
NAME_MAX, NOTE_MAX = 40, 300


class SnapshotTableError(RuntimeError):
    """分頁表頭不符且不能安全處理（不覆寫既有紀錄）。"""


@dataclass(frozen=True)
class SnapshotLogRow:
    """Sheet1 一列（舊 scrape_and_log.build_row 的 24 欄）。None＝讀不到，寫成空白。"""
    ts_utc: str                                 # 抓取時間，UTC 標準格式
    server_time: Optional[str]                  # 頁面伺服器時間文字（只供記錄）
    village_name: str
    population: Optional[int]
    loyalty_pct: Optional[int]
    gold: Optional[int]
    silver: Optional[int]
    stock: Optional[Sequence[int]]              # 木、磚、鐵、穀
    prod: Optional[Sequence[int]]
    free_crop: Optional[int]
    hero_health_pct: Optional[int]
    hero_exp_pct: Optional[int]
    hero_adventures: Optional[int]
    queue: Sequence[QueueItem]
    plus_hours: Optional[float]
    protection_hours: Optional[float]
    attacks: Optional[int]
    attack_eta_min: Optional[int]


@dataclass(frozen=True)
class StructureResult:
    changes: Tuple[Tuple[Any, ...], ...]        # 這次追加到 Changes 的列
    initialized: Tuple[str, ...]                # 這次「初始化」的分頁
    wrote: Tuple[str, ...]                      # 這次有寫入的分頁
    buildings_changed: bool                     # Buildings 有差異（呼叫端用來決定要不要重抓 Buildable）


# ---------------------------------------------------------------- 小工具
def _check_did(did: Any) -> None:
    if isinstance(did, bool) or not isinstance(did, int) or did < 1:
        raise ValueError("did 需為 int ≥ 1")


def _c(v: Any, t: str, max_len: Optional[int] = None) -> Any:
    return serialize.to_cell(v, t, max_len)


def _hdr(row: Sequence[Any]) -> Tuple[str, ...]:
    return tuple(str(c).strip() for c in row)


def _pad(row: Sequence[Any], width: int) -> List[str]:
    cells = [str(c) for c in list(row)[:width]]
    return cells + [""] * (width - len(cells))


def _lv(s: Any) -> int:
    return int(s) if str(s).isdigit() else 0


def _gid_cell(s: Any) -> Any:
    return int(s) if str(s).isdigit() else ""


def _name(gid: Optional[int], own: Optional[str], names: Optional[Mapping[int, str]]) -> Optional[str]:
    return own or (names or {}).get(gid) or None


def _res_cells(cost: Optional[Sequence[int]]) -> List[Any]:
    return list(serialize.res_to_cells(cost)) if cost is not None else [""] * 4


# ---------------------------------------------------------------- Sheet1
def sheet1_cells(row: SnapshotLogRow, did: int) -> List[Any]:
    _check_did(did)
    stock = list(serialize.res_to_cells(row.stock)) if row.stock is not None else [None] * 4
    prod = list(serialize.res_to_cells(row.prod)) if row.prod is not None else [None] * 4
    queue = [{"info": q.info, "remaining_s": q.remaining_s} for q in row.queue] or None
    cells = [
        _c(row.ts_utc, "utc"), _c(row.server_time, "str", 40), _c(row.village_name, "str", 60),
        _c(row.population, "int"), _c(row.loyalty_pct, "int"), _c(row.gold, "int"), _c(row.silver, "int"),
        _c(stock[0], "int"), _c(prod[0], "int"), _c(stock[1], "int"), _c(prod[1], "int"),
        _c(stock[2], "int"), _c(prod[2], "int"), _c(stock[3], "int"), _c(prod[3], "int"),
        _c(row.free_crop, "int"),
        _c(row.hero_health_pct, "int"), _c(row.hero_exp_pct, "int"), _c(row.hero_adventures, "int"),
        _c(queue, "json"), _c(row.plus_hours, "float"), _c(row.protection_hours, "float"),
        _c(row.attacks, "int"), _c(row.attack_eta_min, "int"),
        did,
    ]
    assert len(cells) == len(SHEET1_HEADER)
    return cells


def append_snapshot(sh: Any, did: int, row: SnapshotLogRow) -> int:
    """追加一列 Sheet1。回傳 1。表頭是舊 24 欄就補上 did 欄頭；其他不符丟 SnapshotTableError（不覆寫）。"""
    cells = sheet1_cells(row, did)
    ws, _ = gsheets.ensure_worksheet(sh, SHEET1_TAB, rows=1000, cols=len(SHEET1_HEADER))
    first = _hdr(ws.row_values(1))
    if ws.col_count < len(SHEET1_HEADER):
        ws.add_cols(len(SHEET1_HEADER) - ws.col_count)
    if not first or first == _SHEET1_V1:
        gsheets.batch_write(ws, [list(SHEET1_HEADER)], start="A1")
    elif first != SHEET1_HEADER:
        raise SnapshotTableError("Sheet1 的表頭不符，未寫入")
    return gsheets.batch_write(ws, [cells])


# ---------------------------------------------------------------- 狀態分頁共用
def _load(values: Sequence[Sequence[Any]], header: Tuple[str, ...], did: int):
    """→ (表頭相符, {key: 這個 did 的舊列}, [其他 did 的列])。表頭不符＝整頁視為空（狀態分頁由機器產生，可重建）。"""
    width, did_s = len(header), str(did)
    ok = bool(values) and _hdr(values[0][:width]) == header
    old: Dict[str, List[str]] = {}
    others: List[List[str]] = []
    if ok:
        for r in values[1:]:
            cells = _pad(r, width)
            if not cells[0].strip():
                continue
            if cells[-1].strip() == did_s:
                old[cells[0].strip()] = cells
            else:
                others.append(cells)
    return ok, old, others


def _diff(ok, old, others, header, n, watch, did, new_rows, now, *, stamp_checked=False, refresh=False):
    """→ (events, init, payload 或 None)。events＝[(added|changed|removed, 新列字串, 舊列字串)]。"""
    init = (not ok) or not old
    events, out, seen = [], [], set()
    for r in new_rows:
        rs = [str(c) for c in r]
        if rs[0] in seen:
            raise ValueError("同一分頁的 key 重複")
        seen.add(rs[0])
        o = old.get(rs[0])
        if init:
            last = now
        elif o is None:
            events.append(("added", rs, None))
            last = now
        elif any(o[c] != rs[c] for c in watch):
            events.append(("changed", rs, o))
            last = now
        else:
            last = o[n].strip() or now
        out.append(list(r) + [last] + ([now] if stamp_checked else []) + [did])
    if not init:
        events.extend(("removed", None, o) for k, o in old.items() if k not in seen)
    if not (init or events or refresh):
        return events, init, None

    def sk(r):
        d, k = str(r[-1]).strip(), str(r[0]).strip()
        return (int(d) if d.isdigit() else 1 << 60, int(k) if k.isdigit() else 1 << 60)

    return events, init, [list(header)] + sorted(others + out, key=sk)


def _write(ws, values, payload) -> None:
    width = max([len(payload[0])] + [len(r) for r in values])
    payload = [_pad(r, width) if len(r) < width else list(r) for r in payload]
    stale = len(values) - len(payload)
    if stale > 0:
        payload += [[""] * width for _ in range(stale)]      # 蓋掉尾端多出的舊列（不先 clear）
    if ws.row_count < len(payload):
        ws.add_rows(len(payload) - ws.row_count)
    if ws.col_count < width:
        ws.add_cols(width - ws.col_count)
    gsheets.batch_write(ws, payload, start="A1")


# ---------------------------------------------------------------- 各分頁的列與變動
def fields_rows(fields: Sequence[ResField], names: Optional[Mapping[int, str]], old: Mapping[str, Sequence[str]]):
    """Playwright 有時讀不到成本。成本是 None 且等級沒變時沿用舊成本與工期，不清成空白（舊 village_log 行為）。"""
    rows = []
    for f in sorted(fields, key=lambda x: x.aid):
        cost, dur = _res_cells(f.cost), _c(f.build_time_s, "int")
        if f.cost is None:
            o = old.get(str(f.aid))
            if o and o[3] == str(f.level) and all(o[i].strip() != "" for i in range(5, 10)):
                cost = [serialize.from_cell(o[i], "int") for i in range(5, 9)]
                dur = serialize.from_cell(o[9], "int")
        rows.append([_c(f.aid, "int"), _c(f.gid, "int"), _c(_name(f.gid, None, names), "str", NAME_MAX),
                     _c(f.level, "int"), _c(f.under_construction, "bool")] + cost + [dur])
    return rows


def buildings_rows(slots: Sequence[BuildingSlot], names: Optional[Mapping[int, str]]):
    return [[_c(s.aid, "int"), _c(s.gid, "int"), _c(_name(s.gid, s.name, names), "str", NAME_MAX),
             _c(s.level, "int"), _c(s.under_construction, "bool")]
            for s in sorted(slots, key=lambda x: x.aid)]


def _unmet(o: BuildOption) -> Optional[List[Dict[str, Any]]]:
    out = []
    for c in o.conditions:
        if not c.met:
            out.append({k: v for k, v in (("gid", c.gid), ("name", c.name), ("level", c.level),
                                          ("current", c.current), ("forbidden", c.forbidden)) if v is not None})
    return out or None


def buildable_rows(options: Sequence[BuildOption], names: Optional[Mapping[int, str]]):
    rows = []
    for o in sorted(options, key=lambda x: x.gid):
        unmet = _unmet(o)
        rows.append([_c(o.gid, "int"), _c(_name(o.gid, o.name, names), "str", NAME_MAX)] + _res_cells(o.cost)
                    + [_c(o.build_time_s, "int"), _c(unmet is None, "bool"), _c(unmet, "json")])
    return rows


def _ch(now, kind, pos, gid, name, old, new, note, did) -> List[Any]:
    return [now, kind, pos, _gid_cell(gid), name, old, new, _c(note, "str", NOTE_MAX), did]


def fields_changes(events, now, did) -> List[List[Any]]:
    out = []
    for ev, new, old in events:
        if ev == "added":
            out.append(_ch(now, "field_added", f"field:{new[0]}", new[1], new[2], "", new[3], "", did))
        elif ev == "removed":
            out.append(_ch(now, "field_removed", f"field:{old[0]}", old[1], old[2], old[3], "", "", did))
        else:
            pos = f"field:{new[0]}"
            if old[1] != new[1]:
                out.append(_ch(now, "field_type_changed", pos, new[1], new[2], old[1], new[1], "", did))
            if old[3] != new[3]:
                out.append(_ch(now, "field_level", pos, new[1], new[2], old[3], new[3], "", did))
            if old[4] != "TRUE" and new[4] == "TRUE":
                out.append(_ch(now, "field_build_started", pos, new[1], new[2], new[3], str(_lv(new[3]) + 1), "", did))
    return out


def buildings_changes(events, now, did) -> List[List[Any]]:
    out = []
    for ev, new, old in events:
        if ev == "added":
            out.append(_ch(now, "building_slot_added", f"building:{new[0]}", new[1], new[2], "", new[3], "", did))
        elif ev == "removed":
            out.append(_ch(now, "building_slot_removed", f"building:{old[0]}", old[1], old[2], old[3], "", "", did))
        else:
            pos, og, ng = f"building:{new[0]}", old[1], new[1]
            if og == "" and ng != "":
                out.append(_ch(now, "building_built", pos, ng, new[2], "", new[3],
                               "under_construction" if new[4] == "TRUE" else "", did))
            elif og != "" and ng == "":
                out.append(_ch(now, "building_removed", pos, og, old[2], old[3], "", "", did))
            elif og != ng:
                out.append(_ch(now, "building_changed", pos, ng, new[2], og, ng, "", did))
            else:
                if old[3] != new[3]:
                    out.append(_ch(now, "building_level", pos, ng, new[2], old[3], new[3], "", did))
                if old[4] != "TRUE" and new[4] == "TRUE":
                    out.append(_ch(now, "building_build_started", pos, ng, new[2], new[3], str(_lv(new[3]) + 1), "", did))
    return out


def buildable_changes(events, now, did) -> List[List[Any]]:
    """prereq_met 欄 idx 7、unmet_json 欄 idx 8。只有 unmet_json 文字改變（前置建築升一級）不記，Buildings 已記過。"""
    out = []
    for ev, new, old in events:
        if ev == "added":
            out.append(_ch(now, "buildable_added", "buildable", new[0], new[1], "", new[7], new[8], did))
        elif ev == "removed":
            out.append(_ch(now, "buildable_removed", "buildable", old[0], old[1], old[7], "", "", did))
        elif old[7] != "TRUE" and new[7] == "TRUE":
            out.append(_ch(now, "prereq_met", "buildable", new[0], new[1], "FALSE", "TRUE", "", did))
        elif old[7] == "TRUE" and new[7] != "TRUE":
            out.append(_ch(now, "prereq_unmet", "buildable", new[0], new[1], "TRUE", "FALSE", new[8], did))
    return out


# ---------------------------------------------------------------- Changes 與主入口
def _changes_ws(sh: Any):
    ws, _ = gsheets.ensure_worksheet(sh, CHANGES_TAB, rows=1000, cols=len(CHANGES_HEADER))
    first = _hdr(ws.row_values(1))
    if ws.col_count < len(CHANGES_HEADER):
        ws.add_cols(len(CHANGES_HEADER) - ws.col_count)
    if not first:
        gsheets.batch_write(ws, [list(CHANGES_HEADER)], start="A1")
    elif first != CHANGES_HEADER:
        raise SnapshotTableError("Changes 的表頭不符，未寫入（不覆寫既有紀錄）")
    return ws


def write_structure(sh: Any, did: int, *, now: str, fields: Optional[Sequence[ResField]] = None,
                    buildings: Optional[Sequence[BuildingSlot]] = None,
                    buildable: Optional[Sequence[BuildOption]] = None,
                    names: Optional[Mapping[int, str]] = None) -> StructureResult:
    """把這個村的結構寫進 Fields／Buildings／Buildable，比對後把變動追加到 Changes。

    None 或空序列＝這輪沒有這份資料，該分頁不動（空序列不會清空分頁）。now＝UTC 標準格式字串。
    Buildable 一旦傳入就會寫（更新「最後確認」）；要不要重抓由呼叫端用 buildable_due／StructureResult.buildings_changed 決定。
    """
    _check_did(did)
    stamp = _c(now, "utc")
    changes: List[List[Any]] = []
    initialized: List[str] = []
    wrote: List[str] = []
    b_changed = False

    def run(tab, header, n, watch, build, gen, *, checked=False, refresh=False):
        nonlocal b_changed
        ws, _ = gsheets.ensure_worksheet(sh, tab, rows=100, cols=len(header))
        values = ws.get_all_values()
        ok, old, others = _load(values, header, did)
        rows = build(old)
        events, init, payload = _diff(ok, old, others, header, n, watch, did, rows, stamp,
                                      stamp_checked=checked, refresh=refresh)
        if payload is not None:
            _write(ws, values, payload)
            wrote.append(tab)
        if init:
            initialized.append(tab)
            changes.append([stamp, "initialized", tab.lower(), "", "", "", str(len(rows)), "", did])
        changes.extend(gen(events, stamp, did))
        return bool(events)

    err: Optional[BaseException] = None
    try:
        if fields:
            run(FIELDS_TAB, FIELDS_HEADER, _FIELDS_N, (1, 3, 4), lambda old: fields_rows(fields, names, old), fields_changes)
        if buildings:
            b_changed = run(BUILDINGS_TAB, BUILDINGS_HEADER, _BUILDINGS_N, (1, 3, 4),
                            lambda old: buildings_rows(buildings, names), buildings_changes)
        if buildable:
            run(BUILDABLE_TAB, BUILDABLE_HEADER, _BUILDABLE_N, (7, 8),
                lambda old: buildable_rows(buildable, names), buildable_changes, checked=True, refresh=True)
    except Exception as exc:  # noqa: BLE001
        err = exc
    if changes:
        try:
            gsheets.batch_write(_changes_ws(sh), changes)
        except Exception:  # noqa: BLE001
            if err is None:
                raise
    if err is not None:
        raise err
    return StructureResult(tuple(tuple(c) for c in changes), tuple(initialized), tuple(wrote), b_changed)


def buildable_due(sh: Any, did: int, *, now: str) -> bool:
    """Buildable 要重抓嗎？沒有分頁、表頭不同、這個 did 沒資料、或最舊的「最後確認」超過 24 小時。"""
    _check_did(did)
    ws = gsheets.get_worksheet(sh, BUILDABLE_TAB)
    if ws is None:
        return True
    ok, old, _ = _load(ws.get_all_values(), BUILDABLE_HEADER, did)
    if not ok or not old:
        return True
    stamps = []
    for r in old.values():
        try:
            stamps.append(serialize.parse_utc(r[_BUILDABLE_N + 1]))
        except serialize.SerializeError:
            pass
    if not stamps:
        return True
    return (serialize.parse_utc(now) - min(stamps)).total_seconds() >= BUILDABLE_MAX_AGE_S
