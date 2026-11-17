#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/fill_in.py（ap-13）
版本：v0.1（A6a2）
用途：插隊 stage：有 build_order、主目標等資源時，看後面付得起的目標能不能先做而不拖慢主目標；
      能就用 actions.build_exec 升級，寫一列 Actions（動作「插隊」）。
依賴：ap-03、ap-06、dm-02、dm-01、dm-12、ac-02、if-07、cm-02（卡片原只列 dm-02、ac-02；候選列舉在 dm-01，驗證在 dm-12）。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `_try_fill_in`、`_fill_mode`（✓）。與舊版的差異
  1. 觸發條件：build_order 非空、next_target 付不起、佇列有空位（舊：order 且 action＝wait_res 且 fill_mode≠off）。
  2. 先用 dm-12 驗證 build_order；verdict＝hold 就不插隊（build stage 會 hold，不能在它旁邊偷建）。
  3. 候選：dm-01 fill_in_candidates（缺頁面資料時由 U.run_with_facts 補抓）→ dm-02 pick_fill_in。
     hidden 改取 snapshot.hidden（舊版用 Config hero_guard_hidden；快照未知時 domain 已處理）；
     slack＝Config fill_in_slack_min ÷ 60；attack_eta_s 取 Dorf1.attack_eta_s（來襲數 > 0 才用）。
  4. 舊 fill_mode＝dry：只記錄、不插隊，每輪都寫一列；on：只有插隊才寫。新版：mode 為 dry（含 DRY_RUN 降級）每輪寫，live 只寫插隊那列。
  5. 真的插隊（Config fill_mode＝live 且 build_exec 回 ok 或 dry）時記 stage_notes 的 built：本輪加成與守衛不跑
     （舊版「插隊成功時 action 變成 build，下面的加成與守衛本輪不跑」）。
  6. 升級成功後：快照 stock 扣成本、queue_slots_used＋1，並清掉 rc.pages 的 dorf1。
"""
from ...actions.build_exec import submit_upgrade
from ...common import serialize
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode, parse_mode
from ...domain.build_planner import fill_in_candidates
from ...domain.fill_in import pick_fill_in
from ...domain.plan_validate import parse_build_order, usable_order, validate_order, validation_need
from ...parsers.village import parse_dorf1
from ..formatting import flv, fname
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]


def precondition(rc: RunContext, vc, snap) -> bool:
    if vc is None or snap is None or not vc.build_settings.build_order:
        return False
    t = snap.next_target
    if t is None or t.ready_in_s <= 0:
        return False
    return snap.queue_slots_used < vc.build_settings.queue_slots


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw, main = rc.gateway, snap.next_target
    bs = vc.build_settings
    raw = parse_build_order(bs.build_order)
    d1 = parse_dorf1(rc.get_page("dorf1.php"))

    _, facts = U.run_with_facts(rc, lambda f: (None, validation_need(raw, d1, f, vc.is_capital)))
    verdict = validate_order(raw, d1, facts, vc.is_capital, vc.did, serialize.to_utc_str(rc.io.now()))
    if verdict.verdict != "proceed":
        return StageResult(status="skipped", note="build_order 被拒（hold），不插隊")

    order = usable_order(raw, vc.is_capital)
    def cand_step(f):
        r = fill_in_candidates(order, d1, f, bs, vc.is_capital)
        return r, (r[0].need if r[0].kind == "need_facts" else None)

    (main_dec, cands), _ = U.run_with_facts(rc, cand_step)
    if main_dec.kind != "wait_resources" or main_dec.target is None:
        return StageResult(status="skipped", note=f"主目標不是等資源（{main_dec.kind}），不插隊")
    mt = main_dec.target

    queue_secs = tuple(q.remaining_s for q in d1.queue)
    eta = d1.attack_eta_s if snap.incoming_attacks else None
    slack_h = float(rc.cfg.get("fill_in_slack_min", 0)) / 60.0
    dec = pick_fill_in(mt, cands, snap, queue_secs, bs.queue_slots, attack_eta_s=eta, slack_h=slack_h)
    head = f"主目標 {fname(mt)} {flv(mt.to_level - 1, mt.gid)}（成本 {'/'.join(map(str, mt.cost))}）"
    desc = f"{head}｜存量={list(snap.stock)}｜來襲={snap.incoming_attacks}｜{dec.reason}"

    if not dec.act:
        if mode is Mode.DRY:           # dry 階段每輪都記，方便對照；live 不洗版
            return StageResult(status="ok", actions=[U.make_row(rc, vc.did, U.ACTION_FILL_IN, mode, "skipped", desc, mt)])
        return StageResult(status="ok")

    f = dec.target
    res = submit_upgrade(gw, vc.did, f, mode)
    updates = {}
    if res.result in ("ok", "dry") and parse_mode((vc.modes or {}).get("fill_in")) is Mode.LIVE:
        U.set_note(rc, vc.did, "built")     # 舊版 fmode＝on：action 變 build，本輪加成與守衛不跑
    if res.result == "ok":
        updates = {"stock": tuple(s - c for s, c in zip(snap.stock, f.cost)),
                   "queue_slots_used": snap.queue_slots_used + 1}
        rc.pages.pop("dorf1.php", None)
        rc.io.notify(f"插隊：先升 {fname(f)} {flv(f.to_level - 1, f.gid)}")
    elif res.result == "failed":
        rc.io.notify(f"插隊升級沒有確認成功（不重試）：{res.detail}")
    row = U.make_row(rc, vc.did, U.ACTION_FILL_IN, mode, res.result, f"{desc}｜{res.detail}", f)
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       snapshot_updates=updates, note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="fill_in", scope="village", mode_key="fill_in", order=25, precondition=precondition, run=run)
