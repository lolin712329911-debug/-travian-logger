#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/build_planner.py（dm-01）
版本：v0.1.1（GA-fix1／D-39：plan() 成本讀不到不回 done；storage_fix 訊息「穀倉」）｜v0.1（A3a）
用途：建城決策（純函式，不碰網路、不讀 Sheet、不用全域變數）。回傳 BuildDecision（cm-02）。
      plan()                  舊流程（沒有 build_order）：資源田＋（呼叫端給的）倉庫／糧倉的 ROI 規則
      plan_with_order()       依 build_order 嚴格照順序建城（自動補前置條件、倉容不足自動先升倉庫／糧倉）
      fill_in_candidates()    主目標等資源時，列出後面「現在就付得起」的候選（給 fill_in.pick_fill_in）
      next_target()           佇列忙時假設佇列空，算「下一個目標」（給 guard.gaps_from_decision 算缺口）
依賴：cm-01（models）、cm-02（decisions）、cm-03（constants）、cm-09（parsed）、cm-12（game_rules）。
部署狀態：未部署（GA 前不 live）。

來源：舊 travian_agent.py 的 plan／plan_with_order／plan_fill_ins／_roi_key（✓ 已讀）與 runner._next_target（✓ 已讀）。
與舊版差異（演算法不變；已用舊函式做逐案對照，見 tests/domain/test_build_planner.py）：
  1. 舊 plan_with_order 的 get(path)（抓 dorf2／build.php／空地建造頁）取消。缺資料時回傳
     BuildDecision(kind="need_facts", need=FactsNeed(...))，由 app stage 抓好放進 BuildFacts 後再呼叫（可重複，
     一輪最多 3～5 次）。每次呼叫都從頭算，結果只取決於輸入，所以重複呼叫是安全的。
  2. 全域 TARGET_LEVEL／QUEUE_SLOTS／IS_CAPITAL → BuildSettings.target_level／queue_slots 與 is_capital 參數
     （BuildSettings 沒有 is_capital：它在 C9 VillageContext，由 stage 傳入）。
  3. 資料結構：舊 Field／State／Slot → parsed.ResField／Dorf1／BuildingSlot；空地 gid 由 0 改為 None；
     舊 Field.secs → build_time_s（None 時排序用 0）。
  4. 「本輪已送出（touched）」：舊 runner 把它們標成 building＝True；新版直接傳 touched，規則相同。
     乾跑模擬「已排入的升級佔佇列」＝呼叫端把 queue_secs 加長（預設用 dorf1.queue）。
  5. 倉庫／糧倉（BUILDING_GIDS）的舊流程候選（runner._legacy_candidates）由 stage 讀 build.php 後以 extra 傳入。
  6. 回傳值：("wait_res", 秒, f)→BuildDecision("wait_resources", target, wait_s)；("build", f)→("build", target)；
     ("blocked", 說明)→"plan_stuck"；("no_slot", gid)→"no_free_slot"；其餘同名對應（見 _to_decision）。
  7. 舊碼會在條件的 gid／level 是 None 時當掉；新版回 plan_stuck（不猜）。
  9. （D-39，行為變更）舊流程候選全空時，若有資源田低於目標但成本讀不到，回 plan_stuck，不回 done（舊碼回 done，
     會把「讀不到資料」報成「已完成」）。
  8. 資源田 ROI 表用 game_rules.RESOURCE_FIELD_PRODUCTION_1X（△ 未用 S9 樣本核對；舊碼線上一直在用同一張表）。
"""
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from ..common.constants import BUILDING_GIDS, FREE_SLOT_RANGE, gid_name
from ..common.decisions import BuildDecision, BuildFacts, BuildTarget, FactsNeed, FillCandidate
from ..common.game_rules import RESOURCE_FIELD_PRODUCTION_1X, resource_field_cap
from ..common.models import BuildSettings
from ..common.parsed import Dorf1, Dorf2

__all__ = ["UpgradeCandidate", "plan", "plan_with_order", "fill_in_candidates", "next_target"]

_EMPTY_WAIT_S = 600          # 舊碼：佇列判定忙、但讀不到剩餘秒數時的預設等待


@dataclass(frozen=True)
class UpgradeCandidate:
    """一個可升級／可蓋的候選。level＝目前等級（新蓋＝0）；cost＝升到下一級；None＝讀不到。"""
    aid: int
    gid: int
    level: int
    cost: Optional[Tuple[int, int, int, int]]
    build_time_s: Optional[int]
    under_construction: bool = False


class _Need(Exception):
    def __init__(self, need: FactsNeed):
        super().__init__(need)
        self.need = need


# ---------------------------------------------------------------- 共用小工具
def _secs(f: UpgradeCandidate) -> int:
    return f.build_time_s or 0


def _roi_key(f: UpgradeCandidate):
    """排序鍵：(有無 ROI 資料, 花費÷每小時新增產量, 工期)，越小越優先；查不到產量表時退回（總花費、工期）。"""
    gain = RESOURCE_FIELD_PRODUCTION_1X.get(f.level + 1)
    base = RESOURCE_FIELD_PRODUCTION_1X.get(f.level)
    cost = sum(f.cost)
    if f.gid not in (1, 2, 3, 4) or gain is None or base is None or gain <= base or cost <= 0:
        return (2, cost, _secs(f))
    return (1, cost / (gain - base), _secs(f))


def _label(f: UpgradeCandidate) -> str:
    return f"{gid_name(f.gid)} {f.level + 1} 級（aid={f.aid}）"


def _target(f: UpgradeCandidate, ready_in_s: int) -> BuildTarget:
    return BuildTarget(aid=f.aid, gid=f.gid, name=gid_name(f.gid), to_level=f.level + 1,
                       cost=tuple(f.cost), ready_in_s=ready_in_s)


def _to_decision(r: tuple) -> BuildDecision:
    k = r[0]
    if k == "wait_queue":
        return BuildDecision("wait_queue", None, f"施工佇列已滿，約 {r[1]} 秒後有空位", wait_s=r[1])
    if k == "wait_res":
        f = r[2]
        return BuildDecision("wait_resources", _target(f, r[1]), f"{_label(f)}：資源不足，約 {r[1]} 秒後湊齊",
                             wait_s=r[1], build_time_s=f.build_time_s)
    if k == "build":
        f = r[1]
        return BuildDecision("build", _target(f, 0), f"{_label(f)}：資源足夠，可以開工", build_time_s=f.build_time_s)
    if k == "need_storage":
        f = r[1]
        return BuildDecision("storage_too_small", _target(f, 0), f"{_label(f)}：成本超過倉容，要先升倉庫／糧倉",
                             build_time_s=f.build_time_s)
    if k == "blocked":
        return BuildDecision("plan_stuck", None, str(r[1]))
    if k == "no_slot":
        return BuildDecision("no_free_slot", None, f"要蓋 {gid_name(r[1])}，但村莊沒有空地")
    if k == "no_affordable":
        return BuildDecision("no_affordable", None, "沒有現有資源就付得起的候選")
    if k == "done":
        return BuildDecision("done", None, "已全部達成")
    raise AssertionError(f"未知動作 {k}")


def _from_dorf1(dorf1: Dorf1, touched) -> List[UpgradeCandidate]:
    return [UpgradeCandidate(f.aid, f.gid, f.level, f.cost, f.build_time_s,
                             bool(f.under_construction) or f.aid in touched) for f in dorf1.fields]


def _queue_of(dorf1: Dorf1, queue_secs) -> List[int]:
    return [q.remaining_s for q in dorf1.queue] if queue_secs is None else list(queue_secs)


def _cap(dorf1: Dorf1) -> Tuple[int, int, int, int]:
    return (dorf1.cap_wh, dorf1.cap_wh, dorf1.cap_wh, dorf1.cap_gr)


def _wait_res(f, stock, prod):
    short = [max(0, c - s) for c, s in zip(f.cost, stock)]
    if any(short):
        secs = max(sh / max(p, 1) * 3600 for sh, p in zip(short, prod))
        return ("wait_res", int(secs) + 30, f)
    return ("build", f)


# ---------------------------------------------------------------- plan（舊流程）
def plan(dorf1: Dorf1, settings: BuildSettings, is_capital: bool, *, extra: Sequence[UpgradeCandidate] = (),
         touched=(), queue_secs: Optional[Sequence[int]] = None, affordable_only: bool = False) -> BuildDecision:
    """舊流程（沒有 build_order）。extra＝倉庫／糧倉等村莊中心候選（呼叫端已用 target_building_level 篩過等級）。
    affordable_only＝只在現有資源就付得起的候選裡挑；沒有就回 kind='no_affordable'。"""
    touched = set(touched)
    queue = _queue_of(dorf1, queue_secs)
    if len(queue) >= settings.queue_slots:
        return _to_decision(("wait_queue", min(queue) + 5))
    cap_lv = resource_field_cap(is_capital)
    eff_target = settings.target_level if cap_lv is None else min(settings.target_level, cap_lv)
    fields = _from_dorf1(dorf1, touched) + [UpgradeCandidate(f.aid, f.gid, f.level, f.cost, f.build_time_s,
                                                              f.under_construction or f.aid in touched) for f in extra]
    cands = [f for f in fields if f.cost and not f.under_construction
             and (f.gid in BUILDING_GIDS or f.level < eff_target)]
    if not cands:
        # D-39：有資源田低於目標、卻因讀不到成本而被排除，不是「已完成」。回 plan_stuck 讓人處理（與 plan_with_order 同訊息）
        unreadable = [f for f in dorf1.fields if f.cost is None and not f.under_construction
                      and f.aid not in touched and f.level < eff_target]
        if unreadable:
            return _to_decision(("blocked", "資源田的升級成本讀不到（頁面 title 被前端 JS 清空？）"))
        return _to_decision(("done",))
    if affordable_only:
        cands = [f for f in cands if all(c <= s for c, s in zip(f.cost, dorf1.stock))]
        if not cands:
            return _to_decision(("no_affordable",))
    pool = [f for f in cands if f.gid == 4] if dorf1.free_crop < 5 else cands
    pool = pool or cands
    f = min(pool, key=_roi_key)
    if any(c > m for c, m in zip(f.cost, _cap(dorf1))):
        return _to_decision(("need_storage", f))
    return _to_decision(_wait_res(f, dorf1.stock, dorf1.prod))


# ---------------------------------------------------------------- plan_with_order
def _order_core(order, dorf1: Dorf1, facts: BuildFacts, settings: BuildSettings, is_capital: bool,
                touched, queue: List[int], start: int, trace):
    """舊 plan_with_order 的本體；回傳舊式 tuple；缺資料丟 _Need。"""
    stock, prod, cap = dorf1.stock, dorf1.prod, _cap(dorf1)
    fields0 = _from_dorf1(dorf1, touched)
    if len(queue) >= settings.queue_slots:
        return ("wait_queue", min(queue) + 5)
    cache = {}

    def q_wait():
        return ("wait_queue", (min(queue) + 5) if queue else _EMPTY_WAIT_S)

    def slots():
        d2: Optional[Dorf2] = facts.dorf2
        if d2 is None:
            raise _Need(FactsNeed("dorf2"))
        return d2.slots

    def options():
        if "opts" not in cache:
            lo, hi = FREE_SLOT_RANGE
            empty = sorted(s.aid for s in slots() if s.gid is None and lo <= s.aid <= hi and s.aid not in touched)
            aid = empty[0] if empty else None
            if aid is not None and aid not in facts.options:
                raise _Need(FactsNeed("build_options", aid))
            cache["empty"] = aid
            cache["opts"] = facts.options[aid] if aid is not None else ()
        return cache["opts"], cache["empty"]

    fixing = set()

    def storage_fix(f):
        over_res = any(c > m for c, m in zip(f.cost[:3], cap[:3]))
        gid, name = (10, "倉庫") if over_res else (11, "穀倉")
        if gid in fixing:
            return ("blocked", f"{name}自己的升級成本就超過容量，無法自動補救")
        lvl = max((s.level for s in slots() if s.gid == gid), default=0)
        if lvl >= 20:
            return ("blocked", f"成本超過{name}容量，但{name}已滿級")
        fixing.add(gid)
        try:
            r = resolve(gid, lvl + 1)
        finally:
            fixing.discard(gid)
        return r if r is not None else ("blocked", f"成本超過{name}容量，但{name}已達目標等級（資料不一致）")

    def decide(f):
        if any(c > m for c, m in zip(f.cost, cap)):
            return storage_fix(f)
        return _wait_res(f, stock, prod)

    def fields_action(gids, level, need_all):
        cap_lv = resource_field_cap(is_capital)
        if gids == (1, 2, 3, 4) and cap_lv is not None:
            level = min(level, cap_lv)
        fs = [f for f in fields0 if f.gid in gids]
        if not need_all and any(f.level >= level for f in fs):
            return None
        todo = [f for f in fs if f.level < level]
        if not todo:
            return None
        avail = [f for f in todo if f.cost and not f.under_construction and f.aid not in touched]
        if not avail:
            if any(f.under_construction or f.aid in touched for f in todo):
                return q_wait()
            return ("blocked", "資源田的升級成本讀不到（頁面 title 被前端 JS 清空？）")
        pool = [f for f in avail if f.gid == 4] if dorf1.free_crop < 5 else avail
        pool = pool or avail
        if need_all:
            f = min(pool, key=_roi_key)
        else:
            f = min(pool, key=lambda x: (-x.level, sum(x.cost), _secs(x)))
        return decide(f)

    def resolve(gid, level, depth=0, need_all=False):
        if depth > 3:
            return ("blocked", f"前置條件套了太多層（卡在 gid {gid}）")
        if gid in (1, 2, 3, 4):
            return fields_action((gid,), level, need_all)
        mine = [s for s in slots() if s.gid == gid]
        if mine:
            best = max(mine, key=lambda s: s.level)
            if best.level >= level:
                return None
            if best.under_construction or best.aid in touched:
                return q_wait()
            if best.aid not in facts.upgrade_costs:
                raise _Need(FactsNeed("upgrade_cost", best.aid))
            uc = facts.upgrade_costs[best.aid]
            if uc is None or not uc.cost:
                return q_wait() if queue else (
                    "blocked", f"{BUILDING_GIDS.get(gid, gid_name(gid))} (aid={best.aid}) 讀不到升級成本（已達最高等級？）")
            return decide(UpgradeCandidate(best.aid, gid, best.level, uc.cost, uc.build_time_s, False))
        if any(s.aid in touched and s.gid is None for s in slots()):
            return q_wait()
        opts, empty = options()
        if empty is None:
            return ("no_slot", gid)
        entry = next((o for o in opts if o.gid == gid), None)
        if entry is None:
            return ("blocked", f"gid {gid} 不在可蓋清單裡（種族不能蓋、已達數量上限，或空地頁面讀取失敗）")
        name = entry.name or gid_name(gid)
        if entry.cost is None:
            return ("blocked", f"{name} 的建造成本讀不全，不猜")
        f = UpgradeCandidate(empty, gid, 0, entry.cost, entry.build_time_s, False)
        if entry.buildable:
            return decide(f)
        unmet = [c for c in entry.conditions if not c.met]
        for c in unmet:
            if c.forbidden:
                return ("blocked", f"{name} 被 {c.name} 擋住（村莊裡不能已經有它）")
        for c in unmet:
            if c.gid is None or c.level is None:
                return ("blocked", f"{name} 的前置條件讀不全（gid／等級缺漏），不猜")
            r = resolve(c.gid, c.level, depth + 1)
            if r is not None:
                return r
        if unmet:
            return q_wait() if queue else ("blocked", f"{name}：頁面說條件沒達成，但村莊資料看起來已達成")
        r = decide(f)
        if r[0] == "build":
            return ("blocked", f"{name} 沒有綠色按鈕、也沒有未達成的條件（原因不明）")
        return r

    for idx, (key, level) in enumerate(order):
        if idx < start:
            continue
        r = fields_action((1, 2, 3, 4), level, True) if key == "res" else resolve(key, level, need_all=True)
        if r is not None:
            if trace is not None:
                trace.append(idx)
            return r
    if trace is not None:
        trace.append(len(order))
    return ("done",)


def _need_decision(n: FactsNeed) -> BuildDecision:
    what = {"dorf2": "村莊中心頁（dorf2）", "upgrade_cost": f"aid={n.aid} 的建築頁",
            "build_options": f"aid={n.aid} 空地的建造清單"}[n.kind]
    return BuildDecision("need_facts", None, f"缺資料：{what}", need=n)


def plan_with_order(order: Sequence[Tuple[Any, int]], dorf1: Dorf1, facts: BuildFacts, settings: BuildSettings,
                    is_capital: bool, *, touched=(), queue_secs: Optional[Sequence[int]] = None,
                    start: int = 0) -> BuildDecision:
    """依 build_order（[('res', 2), (15, 3), …]，已通過 plan_validate）決定下一步。
    缺頁面資料回 kind='need_facts'（need 說明要哪一頁）；其餘規則與舊 plan_with_order 相同。
    start：從 order[start:] 開始找第一個還沒達成的目標（前面當作已達成）。"""
    try:
        r = _order_core(order, dorf1, facts, settings, is_capital, set(touched), _queue_of(dorf1, queue_secs),
                        start, None)
    except _Need as n:
        return _need_decision(n.need)
    return _to_decision(r)


def fill_in_candidates(order: Sequence[Tuple[Any, int]], dorf1: Dorf1, facts: BuildFacts, settings: BuildSettings,
                       is_capital: bool, *, touched=(), queue_secs: Optional[Sequence[int]] = None,
                       max_scan: int = 4) -> Tuple[BuildDecision, List[FillCandidate]]:
    """主目標（第一個還沒達成的）是 wait_resources 時，列出後面目標中「現在就付得起」的候選
    （依 build_order 順序，最多往後檢查 max_scan 個未達成的目標，排除和主目標同一格者）。
    主目標不是 wait_resources、或缺資料時候選為空。純規則。"""
    touched, queue = set(touched), _queue_of(dorf1, queue_secs)
    try:
        trace: List[int] = []
        main = _order_core(order, dorf1, facts, settings, is_capital, touched, queue, 0, trace)
        if main[0] != "wait_res" or not trace:
            return _to_decision(main), []
        main_aid, cands = main[2].aid, []
        j, scanned = trace[-1] + 1, 0
        while j < len(order) and scanned < max_scan:
            t: List[int] = []
            r = _order_core(order, dorf1, facts, settings, is_capital, touched, queue, j, t)
            if r[0] == "done" or not t:
                break
            scanned += 1
            if r[0] == "build" and r[1].aid != main_aid and all(r[1].aid != c.target.aid for c in cands):
                cands.append(FillCandidate(_target(r[1], 0), r[1].build_time_s))
            j = t[-1] + 1
    except _Need as n:
        return _need_decision(n.need), []
    return _to_decision(main), cands


def next_target(order: Sequence[Tuple[Any, int]], dorf1: Dorf1, facts: BuildFacts, settings: BuildSettings,
                is_capital: bool, *, touched=()) -> BuildDecision:
    """佇列忙時：假設佇列已空，回傳「下一個目標」的決策（kind 為 wait_resources／build 時 target 有值；
    其他 kind 表示算不出缺口）。舊 runner._next_target 回傳 action tuple；卡片原寫回傳 BuildTarget／None，
    改回傳 BuildDecision 是因為 need_facts 要能傳回呼叫端。"""
    return plan_with_order(order, dorf1, facts, settings, is_capital, touched=touched, queue_secs=())
