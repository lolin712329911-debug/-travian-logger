#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/build.py（ap-10）
版本：v0.1.1（GA-fix1：dorf1 抓取與升級後重讀都傳 rc.dorf1_raw_if）｜v0.1（A6a2）
用途：建城 stage：讀 build_order → 決策 → actions.build_exec 升級 → 寫 Actions；每輪寫 plan_* 四個 state 鍵。
依賴：ap-03、ap-06、dm-01、dm-12、ac-02、if-12、if-07、if-08、cm-02、cm-03（ps-01～03 用來抓 dorf1／dorf2／建築頁，v0.67 的依賴列要補）。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `run_build_cycle` 建城段、`_legacy_candidates`（✓）。流程（卡片 v0.74、規則 13、D-29／D-30）
  1. plan_repo.load_build_order：None＝沒有計畫 → 舊流程 plan(…, extra)，Actions detail 註明「無 build_order，走舊流程」。
     讀取失敗（例外）照丟，不走舊流程（stage 失敗，run_stage 寫失敗列）。
  2. 有計畫 → plan_validate：hold → 本輪不決策、不升級，只寫一列 skipped（被拒原因），不走成長清單（D-30）。
     proceed → plan_with_order（缺頁面資料時由 _util.run_with_facts 補抓）。
  3. 計畫全部達成（done）不是終點 → 成長清單第 1 層（舊流程那一套，detail 註明「計畫已達成，成長清單第 1 層」）；
     第 1 層也沒事做 → plan_status＝idle，notify 一次（D-29：第 2 層決定前維持 idle）。
  4. storage_too_small（舊 need_storage）→ 看實際成本超過哪種倉容：木磚鐵→倉庫、穀→糧倉，升對應的倉庫（不論 target_building_level）。
  5. 一輪最多 Config max_builds 個升級（舊 run_build_cycle 的迴圈）；送出成功後重讀 dorf1 再決策；dry 模式模擬「已排入」
     （touched＋佇列加長）。第一個非 build 的決策（等資源、等佇列…）寫一列「建城等待」後結束。
  6. 本輪有 build 決策（不論 mode）→ stage_notes 記 built：加成與守衛不跑（舊版 action 是 build 時它們不跑）。
  7. 升級成功後 snapshot_updates 回報 stock、queue_slots_used、queue_free_in_s、next_target；dorf1 快取已更新。

plan_* state 鍵（用 upsert_state 寫：只取代這四個帳號級鍵，不洗掉 observe 寫的村級列）
  plan_status：none（沒有 build_order，舊流程有事做）／active／exhausted（計畫用完、成長清單接手）／idle（沒事可做）。hold 時不寫。
  plan_remaining_steps：build_order 還沒達成的步驟數（沒有計畫＝0；缺 dorf2 時建築步驟一律算還沒達成）。
  plan_eta_h：△ 只有兩種算得出來：剩 0 步＝0.0；剩 1 步且知道該步工期＝（佇列最快空出＋工期）小時；其餘空白。
  plan_needs_refill：status 是 exhausted／idle，或 active 且（eta ≤ PLAN_LOW_WATER_H，或 eta 算不出來而剩餘步數 ≤ 2）。
  status 變成 exhausted／idle 時 notify 一次（用 state 前值去重；讀不到前值就當成變了）。
  8. 舊流程（沒有 build_order）且轉移功能開著、有來襲、付不起時，改做 plan(affordable_only=True) 的項目（舊 runner 同）。
  9. plan_stuck（含升倉庫／糧倉找不到、成本超過倉容）寫「計畫卡住」列並 notify，用該動作最近一列去重（6 小時）。
未解（交接區塊）：GROWTH_TIERS 第 2 層（D-29）；PLAN_LOW_WATER_H 6 小時為 △。
"""
import dataclasses
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...actions.build_exec import submit_upgrade
from ...common import serialize
from ...common.constants import BUILDING_GIDS, gid_name
from ...common.decisions import BuildDecision, BuildTarget
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode, parse_mode
from ...common.schema import ParseError
from ...domain.build_planner import UpgradeCandidate, plan, plan_with_order
from ...domain.plan_validate import MAX_BUILDING_LEVEL, parse_build_order, usable_order, validate_order, validation_need
from ...infra.store import plan_repo
from ...parsers.buildings import parse_building_cost
from ...parsers.village import parse_dorf1, parse_dorf2
from ..formatting import ACTION_BUILD, ACTION_BUILD_WAIT, describe
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "GROWTH_TIERS", "PLAN_LOW_WATER_H", "precondition", "run"]

# 成長清單（本檔內部常數，不進 Config、不動契約）：計畫用完或沒有計畫時，依序找事做。
GROWTH_TIERS = (
    {"tier": 1, "name": "資源田升到 target_level（非首都上限 10）＋倉庫／糧倉依 target_building_level 與實際倉容需要"},
    # 第 2 層（非首都資源田滿 10 級後要蓋什麼）＝D-29 待決；決定前第 1 層沒事做就是 idle
)
PLAN_LOW_WATER_H = 6.0          # △ 計畫預估剩幾小時以內就通知補單
LOW_STEPS = 2                   # eta 算不出來時，剩這麼多步以內就通知補單
HOLD_NOTIFY_EVERY_H = 6.0       # hold 時每隔多久才再 notify（用 Actions 的「計畫被拒」列判斷）
ACTION_PLAN_HOLD = "計畫被拒"
ACTION_PLAN_STUCK = "計畫卡住"
STUCK_NOTIFY_EVERY_H = 6.0       # plan_stuck 時每隔多久才再 notify
STATE_KEYS = ("plan_status", "plan_remaining_steps", "plan_eta_h", "plan_needs_refill")
_GRAIN_GID, _WH_GID = 11, 10


def precondition(rc: RunContext, vc, snap) -> bool:
    return vc is not None and snap is not None


# ---------------------------------------------------------------- 小工具
def _min_queue(d1) -> int:
    return min((q.remaining_s for q in d1.queue), default=0)


def _caps(d1) -> Tuple[int, int, int, int]:
    return (d1.cap_wh, d1.cap_wh, d1.cap_wh, d1.cap_gr)


def _ready_s(cost, d1) -> int:
    short = [max(0, c - s) for c, s in zip(cost, d1.stock)]
    if not any(short):
        return 0
    return int(max(sh / max(p, 1) * 3600 for sh, p in zip(short, d1.prod))) + 30


def _storage_candidates(rc: RunContext, target_level: int, gids: Sequence[int]) -> List[UpgradeCandidate]:
    """dorf2 的倉庫／糧倉（gid 在 gids、沒在施工、等級 < target_level）＋建築頁的升級成本。讀不到成本的略過。"""
    out = []
    for s in parse_dorf2(rc.get_page("dorf2.php")).slots:
        if s.gid in BUILDING_GIDS and s.gid in gids and not s.under_construction and s.level < target_level:
            try:
                uc = parse_building_cost(rc.get_page(f"build.php?id={s.aid}"))
            except ParseError:
                continue
            out.append(UpgradeCandidate(s.aid, s.gid, s.level, tuple(uc.cost), uc.build_time_s, False))
    return out


def _storage_decision(rc: RunContext, d1, dec: BuildDecision) -> BuildDecision:
    """storage_too_small（目標成本超過倉容）→ 依實際成本升倉庫（木磚鐵）或糧倉（穀）；不論 target_building_level。"""
    t = dec.target
    if t is None:
        return dec
    over = [i for i, (c, m) in enumerate(zip(t.cost, _caps(d1))) if c > m]
    gid = _WH_GID if any(i < 3 for i in over) else _GRAIN_GID
    cands = _storage_candidates(rc, MAX_BUILDING_LEVEL, (gid,))
    if not cands:
        return BuildDecision("plan_stuck", t, f"目標成本超過倉容，但找不到可升級的{gid_name(gid)}（沒蓋、施工中或已滿級）")
    c = min(cands, key=lambda x: x.level)
    if c.cost is None or any(x > m for x, m in zip(c.cost, _caps(d1))):
        return BuildDecision("plan_stuck", t, f"{gid_name(gid)}升級的成本也超過倉容，需要人處理")
    ready = _ready_s(c.cost, d1)
    tgt = BuildTarget(aid=c.aid, gid=c.gid, name=gid_name(c.gid), to_level=c.level + 1, cost=c.cost, ready_in_s=ready)
    why = f"目標成本超過倉容，先升{gid_name(gid)}"
    if ready == 0:
        return BuildDecision("build", tgt, why, build_time_s=c.build_time_s)
    return BuildDecision("wait_resources", tgt, why, wait_s=ready, build_time_s=c.build_time_s)


def _remaining(order, d1, dorf2, is_capital: bool) -> int:
    """build_order 還沒達成的步驟數。建築步驟沒有 dorf2 時一律算還沒達成。"""
    from ...common.game_rules import resource_field_cap
    n = 0
    for key, lv in order:
        if key == "res" or key in (1, 2, 3, 4):
            gids = (1, 2, 3, 4) if key == "res" else (key,)
            cap = resource_field_cap(is_capital)
            want = min(lv, cap) if (key == "res" and cap is not None) else lv
            done = all(f.level >= want for f in d1.fields if f.gid in gids)
        else:
            done = dorf2 is not None and max((s.level for s in dorf2.slots if s.gid == key), default=0) >= lv
        n += 0 if done else 1
    return n


# ---------------------------------------------------------------- stage
def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw, did, bs, cfg = rc.gateway, vc.did, vc.build_settings, rc.cfg
    max_builds = int(cfg.get("max_builds", 2))
    if max_builds <= 0:
        return StageResult(status="skipped", note="max_builds＝0，本輪不升級")
    tbl = int(cfg.get("target_building_level", 0))

    raw = plan_repo.load_build_order(rc.sh, did)          # 例外照丟：讀取失敗不走舊流程
    d1 = parse_dorf1(rc.get_page("dorf1.php", raw_if=rc.dorf1_raw_if))
    now_s = serialize.to_utc_str(rc.io.now())
    rows: list = []
    order: Optional[list] = None
    facts_box = {"facts": None}

    if raw is not None:                                    # 有計畫：先驗證
        steps = parse_build_order(raw.text)
        _, facts = U.run_with_facts(rc, lambda f: (None, validation_need(steps, d1, f, vc.is_capital)))
        verdict = validate_order(steps, d1, facts, vc.is_capital, did, now_s)
        if verdict.verdict != "proceed":
            why = "；".join(f"第 {r.seq} 步 {r.rule}：{r.reason}" for r in verdict.rejected) or "build_order 被拒"
            age = rc.io.last_action_age_hours(rc.sh, ACTION_PLAN_HOLD, did, "skipped")
            if age is None or age >= HOLD_NOTIFY_EVERY_H:
                rc.io.notify(f"build_order 被拒，建城暫停（請修 Config）：{why}")
            row = U.make_row(rc, did, ACTION_PLAN_HOLD, mode, "skipped", f"build_order 被拒，本輪建城不動作｜{why}")
            return StageResult(status="ok", actions=[row], note="hold")
        order = usable_order(steps, vc.is_capital)
        facts_box["facts"] = facts

    extra_cache: Dict[str, Any] = {}

    def legacy(touched, queue_secs) -> BuildDecision:
        if "extra" not in extra_cache:
            extra_cache["extra"] = _storage_candidates(rc, tbl, (_WH_GID, _GRAIN_GID)) if tbl > 0 else []
        return plan(d1, bs, vc.is_capital, extra=extra_cache["extra"], touched=touched, queue_secs=queue_secs)

    def decide(touched, queue_secs) -> Tuple[BuildDecision, str, str]:
        """→ (決策, detail 前綴, plan_status)。"""
        if order is None:
            d = legacy(touched, queue_secs)
            if d.kind == "wait_resources" and d1.incoming_attacks \
                    and parse_mode((vc.modes or {}).get("item_transfer")) is not Mode.OFF:
                # 舊 runner：轉移功能開著、有來襲、沒有 build_order、付不起 → 改做現有資源就付得起的項目（趁資源被搶前用掉）
                alt = plan(d1, bs, vc.is_capital, extra=extra_cache.get("extra", []), touched=touched,
                           queue_secs=queue_secs, affordable_only=True)
                if alt.kind == "build":
                    return alt, "無 build_order，走舊流程｜有來襲且補不到資源，改做付得起的項目", "none"
            return _storage_decision(rc, d1, d) if d.kind == "storage_too_small" else d, \
                "無 build_order，走舊流程", ("idle" if d.kind == "done" else "none")
        d, facts = U.run_with_facts(rc, U.decision_step(
            lambda f: plan_with_order(order, d1, f, bs, vc.is_capital, touched=touched, queue_secs=queue_secs)))
        facts_box["facts"] = facts
        if d.kind != "done":
            return (_storage_decision(rc, d1, d) if d.kind == "storage_too_small" else d), "", "active"
        g = legacy(touched, queue_secs)
        if g.kind == "storage_too_small":
            g = _storage_decision(rc, d1, g)
        return g, "計畫已達成，成長清單第 1 層", ("idle" if g.kind == "done" else "exhausted")

    touched: set = set()
    queue_secs: Optional[List[int]] = None
    builds, any_live_ok, any_failed, last, last_note = 0, False, False, None, ""
    status, prefix = "none", ""
    while True:
        dec, prefix, status = decide(touched, queue_secs)
        last = dec
        if dec.kind == "need_facts":                       # run_with_facts 不會把 need_facts 留到這裡；保險
            raise RuntimeError("決策仍缺頁面資料")
        cur = dataclasses.replace(snap, stock=tuple(d1.stock), queue_slots_used=len(d1.queue),
                                  queue_free_in_s=_min_queue(d1))
        label, tgt, desc = describe(dec, cur, bs.queue_slots)
        pre = (prefix + "｜") if prefix else ""
        if dec.kind != "build" or tgt is None:
            if dec.kind == "plan_stuck":                   # 需要人處理：獨立動作名稱，用它的最近一列去重 notify
                age = rc.io.last_action_age_hours(rc.sh, ACTION_PLAN_STUCK, did, "skipped")
                if age is None or age >= STUCK_NOTIFY_EVERY_H:
                    rc.io.notify(f"建城卡住，需要人處理：{dec.reason}")
                rows.append(U.make_row(rc, did, ACTION_PLAN_STUCK, mode, "skipped", f"{pre}{label}：{desc}", tgt))
            else:
                rows.append(U.make_row(rc, did, ACTION_BUILD_WAIT, mode, "skipped", f"{pre}{label}：{desc}", tgt))
            break
        U.set_note(rc, did, "built")
        res = submit_upgrade(gw, did, tgt, mode)
        rows.append(U.make_row(rc, did, ACTION_BUILD, mode, res.result, f"{pre}{desc}｜{res.detail}", tgt))
        builds += 1
        if res.result == "ok":
            any_live_ok = True
            rc.io.notify(f"已升級：{desc}")
            d1 = parse_dorf1(rc.get_page("dorf1.php", raw_if=rc.dorf1_raw_if, refresh=True))
            touched.add(tgt.aid)
            queue_secs = None
        elif res.result == "dry":                          # 乾跑：模擬「已排入」，佇列加長、標記已動過
            touched.add(tgt.aid)
            queue_secs = [q.remaining_s for q in d1.queue] + [dec.build_time_s or 1]     # 佇列滿時下一輪決策會回 wait_queue
        else:                                              # skipped／failed：沒變化，不重試
            any_failed = any_failed or res.result == "failed"
            last_note = res.detail if res.result == "failed" else ""
            break
        if builds >= max_builds:
            break

    updates: Dict[str, Any] = {}
    if any_live_ok:
        nxt = None
        if last is not None and last.target is not None and last.kind in ("wait_resources", "build"):
            nxt = dataclasses.replace(last.target, ready_in_s=(last.wait_s or 0) if last.kind == "wait_resources" else 0)
        updates = {"stock": tuple(d1.stock), "queue_slots_used": len(d1.queue), "queue_free_in_s": _min_queue(d1),
                   "next_target": nxt}

    _write_plan_state(rc, vc, order, d1, facts_box["facts"], last, status)
    return StageResult(status="failed" if any_failed else "ok", actions=rows, snapshot_updates=updates, note=last_note)


def _write_plan_state(rc: RunContext, vc: VillageContext, order, d1, facts, last: Optional[BuildDecision],
                      status: str) -> None:
    """寫 plan_* 四鍵並在 status 變成 exhausted／idle 時 notify 一次。任何失敗只 rc.warn，不影響建城。"""
    try:
        dorf2 = facts.dorf2 if facts is not None else None
        remaining = _remaining(order, d1, dorf2, vc.is_capital) if order is not None else 0
        eta: Optional[float] = None
        if remaining == 0:
            eta = 0.0
        elif remaining == 1 and last is not None and last.build_time_s is not None and last.kind in ("build", "wait_resources"):
            eta = round((_min_queue(d1) + last.build_time_s) / 3600.0, 1)
        low = (eta <= PLAN_LOW_WATER_H) if eta is not None else (remaining <= LOW_STEPS)
        refill = status in ("exhausted", "idle") or (status == "active" and low)
        prev = None
        if rc.io.read_state is not None:
            prev = rc.io.read_state(rc.sh, vc.did, ("plan_status",)).get("plan_status")
        if rc.io.upsert_state is not None:
            rc.io.upsert_state(rc.sh, vc.did, [
                ("plan_status", status, ""), ("plan_remaining_steps", remaining, ""),
                ("plan_eta_h", "" if eta is None else eta, ""), ("plan_needs_refill", bool(refill), "")],
                serialize.to_utc_str(rc.io.now()))
        if status in ("exhausted", "idle") and prev != status:
            rc.io.notify("建城計畫已用完，成長清單接手（請補 build_order）" if status == "exhausted"
                         else "建城沒有事可做（計畫用完、成長清單第 1 層也做完）：請補 build_order")
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"stage build：寫 plan_* 狀態失敗（{type(exc).__name__}）")


STAGE = Stage(name="build", scope="village", mode_key=None, order=30, precondition=precondition, run=run)
