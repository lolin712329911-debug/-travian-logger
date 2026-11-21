#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/guard.py（ap-14）
版本：v0.1（A6a2）
用途：庫存防搶＋防溢出守衛 stage：付不起（wait_res）或佇列忙（wait_queue）時，domain.guard 預估溢出與暴露，
      必要時用 actions.focus_exec 把英雄產量加成移到成本最低的資源，寫一列 Actions（動作「防搶加成」）。僅英雄所在村。
依賴：ap-03、ap-06、dm-03、dm-01、ac-04、if-07、cm-02（卡片原寫 dm-03、ac-02、ac-03；守衛實際動作是 set_focus，
      佇列忙時算下一目標缺口用 dm-01 next_target，所以改列 dm-01、ac-04）。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `_try_guard`、`_guard_mode`、`_next_target`（✓）。與舊版的差異
  1. 順序（使用者定案：維持舊行為）：focus 先、守衛後。本輪 focus 切了／失敗（stage_notes 的 focus_acted）或已有建城動作
     （built）守衛不跑。
  2. 舊規則「守衛 live 要 focus_mode＝auto」保留：guard 為 dry 時一律可跑；否則 focus mode 不能是 off。
  3. 暴露：Config guard_exposure（incoming／always）；mode 為 dry 時一律用 always（guard.py 檔頭第 4 點）。
     山洞隱藏量取 snapshot.hidden（None 時 domain 只看溢出），舊 Config hero_guard_hidden 不再用。
  4. 缺口：wait_res 用 next_target 的缺口；wait_queue 先不帶缺口跑，只有「真的想切」才算下一目標缺口
     （沒有 build_order、下一目標正在施工、讀頁失敗、任何例外都退回不帶缺口，與舊版相同）。
  5. 守衛沒有冷卻（使用者 2026-10-18 決定），也不看 hero_focus_min_hours。
  6. 「不動」只在 mode 為 dry 時寫一列（舊 gmode＝dry）；切換成功後用預期產量回報 snapshot_updates["prod"]。
"""
from ...actions.focus_exec import read_focus, set_focus
from ...common.decisions import FOCUS_NAMES, BuildDecision, FocusDecision
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode, parse_mode
from ...common.schema import ParseError
from ...domain.build_planner import next_target
from ...domain.focus import hero_bonus
from ...domain.guard import GuardParams, decide_guard, gaps_from_decision
from ...domain.plan_validate import parse_build_order, usable_order
from ...infra.gateway import GatewayError
from ...parsers.village import parse_dorf1
from ..formatting import flv, fname
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]


def precondition(rc: RunContext, vc, snap) -> bool:
    if vc is None or snap is None:
        return False
    if U.has_note(rc, vc.did, "built") or U.has_note(rc, vc.did, "focus_acted"):
        return False
    slots, t = vc.build_settings.queue_slots, snap.next_target
    wait_queue = snap.queue_slots_used >= slots
    wait_res = (not wait_queue) and t is not None and t.ready_in_s > 0
    if not (wait_res or wait_queue):
        return False
    modes = vc.modes or {}
    if parse_mode(modes.get("guard")) is not Mode.DRY and parse_mode(modes.get("focus")) is Mode.OFF:
        return False                        # 舊規則：守衛 live 要 focus 開著
    return U.hero_here(rc, vc)


def _next_gaps(rc: RunContext, vc: VillageContext, snap: VillageSnapshot):
    """佇列忙時：假設佇列已空，下一目標的 (缺口, 幾小時後可買, 說明)；算不出來回 None。任何例外都回 None。"""
    text = vc.build_settings.build_order
    if not text:
        return None
    try:
        order = usable_order(parse_build_order(text), vc.is_capital)
        if not order:
            return None
        d1 = parse_dorf1(rc.get_page("dorf1.php"))
        d, _ = U.run_with_facts(rc, U.decision_step(
            lambda f: next_target(order, d1, f, vc.build_settings, vc.is_capital)))
        got = gaps_from_decision(d, snap.stock, snap.queue_free_in_s / 3600.0)
    except (GatewayError, ParseError, RuntimeError, ValueError):
        return None
    if got is None:
        return None
    gaps, ready_h = got
    nt = d.target
    return gaps, ready_h, f"｜下一目標 {fname(nt)} {flv(nt.to_level - 1, nt.gid)}｜{ready_h:.2f}h 後可買｜下一目標缺口={gaps}"


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw = rc.gateway
    t = snap.next_target if snap.queue_slots_used < vc.build_settings.queue_slots else None   # None＝佇列忙
    gaps = None
    if t is not None:
        got = gaps_from_decision(BuildDecision("wait_resources", t, ""), snap.stock, 0.0)
        gaps = got[0] if got else None
    exposure = "always" if mode is Mode.DRY else str(rc.cfg.get("guard_exposure", "incoming"))
    head = f"{fname(t)} {flv(t.to_level - 1, t.gid)}｜" if t is not None else "施工佇列忙｜"
    desc = (f"{head}存量={list(snap.stock)}｜產量={list(snap.prod)}｜缺口={gaps}｜來襲={snap.incoming_attacks}"
            f"｜暴露模式={exposure}")
    try:
        focus = read_focus(gw)
    except (GatewayError, ParseError) as e:
        rc.io.notify(f"庫存守衛：讀取狀態失敗，略過本輪（不影響建城）: {e!r}")
        row = U.make_row(rc, vc.did, U.ACTION_GUARD, mode, "failed", f"{desc}｜讀取失敗｜{e!r}", t)
        return StageResult(status="failed", actions=[row], note=f"讀取加成失敗：{type(e).__name__}")

    params = GuardParams()
    dec = decide_guard(snap, focus.current, focus.types, exposure_mode=exposure, gaps=gaps, params=params)
    if dec.act and t is None:               # 佇列忙：只有真的想切才去查下一目標缺口
        nt = _next_gaps(rc, vc, snap)
        if nt is None:
            desc += "｜下一目標缺口算不出來（正在施工／無 build_order／讀頁失敗），只看溢出與暴露"
        else:
            gaps, ready_h, note = nt
            desc += note
            dec = decide_guard(snap, focus.current, focus.types, exposure_mode=exposure, gaps=gaps,
                               ready_in_h=ready_h, params=params)
    desc += f"｜目前 {FOCUS_NAMES[focus.current]}｜{dec.reason}"
    if not dec.act:
        if mode is Mode.DRY:
            return StageResult(status="ok", actions=[U.make_row(rc, vc.did, U.ACTION_GUARD, mode, "skipped", desc, t)])
        return StageResult(status="ok")

    res = set_focus(gw, FocusDecision(True, FOCUS_NAMES[dec.focus], dec.reason), mode)
    updates = {}
    if res.result == "ok":
        updates = {"prod": tuple(snap.prod[r - 1] - hero_bonus(focus.current, focus.types, r)
                                 + hero_bonus(dec.focus, focus.types, r) for r in (1, 2, 3, 4))}
        rc.io.notify(f"庫存守衛：加成 {FOCUS_NAMES[focus.current]} → {FOCUS_NAMES[dec.focus]}（{dec.reason}）")
    elif res.result == "failed":
        rc.io.notify(f"庫存守衛切換加成失敗（不重試）: {res.detail}")
    row = U.make_row(rc, vc.did, U.ACTION_GUARD, mode, res.result, f"{desc}｜{res.detail}", t)
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       snapshot_updates=updates, note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="guard", scope="village", mode_key="guard", order=50, precondition=precondition, run=run)
