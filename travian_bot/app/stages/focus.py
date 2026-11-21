#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/focus.py（ap-12）
版本：v0.1（A6a2）
用途：英雄產量加成切換 stage：snapshot.next_target 付不起（舊 wait_res）時，domain.focus 決定要不要切，
      actions.focus_exec 送出並驗證，寫一列 Actions（動作「加成」）。僅英雄所在村。
依賴：ap-03、ap-06、dm-04、ac-04、if-07、cm-02。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `_try_focus`（✓）。與舊版的差異
  1. 觸發條件：舊版是 plan 回 wait_res；新版用快照：next_target 有值且 ready_in_s > 0、佇列還有空位。
  2. 本輪已有建城動作（rc.stage_notes 的 built）不跑（舊版 action 變 build 時加成與守衛都不跑）。
  3. 設定：FocusSettings(min_hours＝Config hero_focus_min_hours，back_to_balanced＝False，與舊 runner 傳的相同)；
     其餘用 domain 預設。距上次切換＝Actions「加成」最近一筆 result＝ok（None＝沒紀錄，不擋；讀取失敗回 0.0，擋）。
  4. 要切（成功、失敗、讀取失敗、乾跑）都在 stage_notes 記 focus_acted，守衛本輪不跑（舊 `focus_switched`）。
  5. 切換成功後重抓 dorf1 比對產量（預期＝現產量 − 現加成 + 新加成，容許差 2），不符只寫進 detail 並通知；
     並以實測產量回報 snapshot_updates["prod"]。
  6. 「不動」寫一列 skipped（舊版也寫）。
"""
from ...actions.focus_exec import read_focus, set_focus
from ...common.decisions import FOCUS_NAMES
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode
from ...common.schema import ParseError
from ...domain.focus import FocusSettings, decide_focus, hero_bonus
from ...infra.gateway import GatewayError
from ...parsers.village import parse_dorf1
from ..formatting import flv, fname
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]

_TOL = 2   # 產量驗證容許差（舊 runner）


def precondition(rc: RunContext, vc, snap) -> bool:
    if vc is None or snap is None:
        return False
    t = snap.next_target
    if t is None or t.ready_in_s <= 0:
        return False
    if snap.queue_slots_used >= vc.build_settings.queue_slots:
        return False
    if U.has_note(rc, vc.did, "built"):
        return False
    return U.hero_here(rc, vc)


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw, t = rc.gateway, snap.next_target
    head = f"{fname(t)} {flv(t.to_level - 1, t.gid)}"
    gaps = {i + 1: c - s for i, (c, s) in enumerate(zip(t.cost, snap.stock)) if c > s}
    try:
        focus = read_focus(gw)
    except (GatewayError, ParseError) as e:
        U.set_note(rc, vc.did, "focus_acted")
        rc.io.notify(f"英雄產量加成：讀取狀態失敗，略過本輪（不影響建城）: {e!r}")
        row = U.make_row(rc, vc.did, U.ACTION_FOCUS, mode, "failed", f"{head}｜讀取失敗｜{e!r}", t)
        return StageResult(status="failed", actions=[row], note=f"讀取加成失敗：{type(e).__name__}")

    age = rc.io.last_action_age_hours(rc.sh, U.ACTION_FOCUS, vc.did)
    settings = FocusSettings(min_hours=float(rc.cfg.get("hero_focus_min_hours", 1.0)), back_to_balanced=False)
    dec = decide_focus(snap, focus, settings, age)
    age_txt = "無紀錄" if age is None else f"{age:.1f}h"
    desc = (f"{head}｜目前 {FOCUS_NAMES[focus.current]}｜缺口={gaps}｜產量={list(snap.prod)}｜"
            f"加成量={list(focus.types)}｜距上次切換={age_txt}｜{dec.reason}")
    if not dec.act:
        return StageResult(status="ok", actions=[U.make_row(rc, vc.did, U.ACTION_FOCUS, mode, "skipped", desc, t)])

    U.set_note(rc, vc.did, "focus_acted")
    res = set_focus(gw, dec, mode)
    new = FOCUS_NAMES.index(dec.focus)
    expect = tuple(snap.prod[r - 1] - hero_bonus(focus.current, focus.types, r) + hero_bonus(new, focus.types, r)
                   for r in (1, 2, 3, 4))
    extra, updates = "", {}
    if res.result == "dry":
        extra = f"｜預期產量={list(expect)}"
    elif res.result == "ok":
        try:
            after = parse_dorf1(rc.get_page("dorf1.php", refresh=True))
            bad = [FOCUS_NAMES[r] for r in (1, 2, 3, 4) if abs(after.prod[r - 1] - expect[r - 1]) > _TOL]
            extra = f"｜產量 預期={list(expect)} 實際={list(after.prod)}" + ("｜驗證符合" if not bad else f"｜驗證不符：{'、'.join(bad)}")
            if bad:
                rc.io.notify(f"英雄產量加成已切到 {dec.focus}，但產量與預期不符：{'、'.join(bad)}")
            updates = {"prod": tuple(after.prod)}
        except (GatewayError, ParseError) as e:
            extra = f"｜切換後重讀產量失敗：{e!r}"
            updates = {"prod": expect}
        rc.io.notify(f"英雄產量加成：{FOCUS_NAMES[focus.current]} → {dec.focus}（{dec.reason}）")
    elif res.result == "failed":
        rc.io.notify(f"英雄產量加成切換失敗（不重試）: {res.detail}")
    row = U.make_row(rc, vc.did, U.ACTION_FOCUS, mode, res.result, f"{desc}｜{res.detail}{extra}", t)
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       snapshot_updates=updates, note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="focus", scope="village", mode_key="focus", order=40, precondition=precondition, run=run)
