#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/item_transfer.py（ap-11）
版本：v0.2（建城前自己預判目標，不再依賴 snapshot.next_target）｜v0.1.2（A6a2＋診斷輸出（print，不依賴 logging 設定）；只加 log 與 Actions detail 的道具庫存量，判斷邏輯不變）
用途：英雄道具庫 → 村莊轉資源 stage：next_target 付不起時，domain.item_transfer 決定轉哪些，
      actions.item_transfer_exec 送出並驗證，寫一列 Actions（動作「轉移」）。僅英雄所在村。
依賴：ap-03、ap-06、dm-05、ac-03、if-07、cm-02。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `_try_transfer`（✓）。與舊版的差異
  1. 觸發條件：佇列還有空位、英雄在本村；目標（need＝升級成本總量）建城前自己預判（_resolve_target，同舊流程 plan）。
  2. attack_eta_s：快照沒有，來襲數 > 0 才抓 dorf1（rc.get_page，本輪已抓過不重抓）取 Dorf1.attack_eta_s；
     沒有來襲＝None（舊 `st.attack_eta_s if st.attacks else None`）。
  3. queue_busy＝佇列已滿（舊版固定 False，因為只在 wait_res 才呼叫；這裡寫成實際判斷，precondition 下一定是 False）。
  4. 先以 state＝None 呼叫一次 decide：回 not_needed（沒來襲／ETA 太遠）就不讀 graphql（省一個請求），也不寫 Actions；
     其他結果才讀 TransferState 再決策。
  5. 設定：TransferSettings 由 Config hero_transfer_min／max_gap／eta_min 組；only_on_incoming 用預設 True
     （config_schema 沒有 transfer_exposure 鍵，需要時另開）。
  6. 成功（verified）後：快照 stock 加上轉入量、next_target.ready_in_s＝0，並清掉 rc.pages 的 dorf1，
     讓後面的 build 重新讀 dorf1（舊版「資源到位：重讀 dorf1，同一輪重新決策、開工」）。
  7. 舊版每個非 transfer 結果都寫一列；新版 not_needed 不寫（否則每輪一列），其餘寫 skipped。
"""
import dataclasses
import logging

from ...actions.item_transfer_exec import execute_item_transfer, read_transfer_state
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode
from ...common.schema import ParseError
from ...domain.build_planner import plan
from ...domain.item_transfer import TransferSettings, decide_item_transfer
from ...infra.gateway import GatewayError
from ...infra.store import plan_repo
from ...parsers.village import parse_dorf1
from ..formatting import flv, fname
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]

_log = logging.getLogger("item_transfer")


class log:  # noqa: N801  診斷用：同時走 logging 與 print（GitHub log 一定看得到）
    @staticmethod
    def info(msg, *args):
        try:
            text = msg % args if args else msg
        except Exception:  # 格式錯誤也不能影響建城
            text = f"{msg} {args}"
        _log.info(text)
        print(f"[item_transfer] {text}", flush=True)


def precondition(rc: RunContext, vc, snap) -> bool:
    """建城前執行：不看 next_target（observe 一律給 None），目標由 run() 自己預判。"""
    if vc is None or snap is None:
        log.info("item_transfer 略過：vc／snap 為 None")
        return False
    if snap.queue_slots_used >= vc.build_settings.queue_slots:
        log.info("item_transfer 略過：佇列已滿（%s/%s）", snap.queue_slots_used, vc.build_settings.queue_slots)
        return False
    here = U.hero_here(rc, vc)
    if not here:
        log.info("item_transfer 略過：hero_here=False（英雄不在本村或讀不到）")
    return here


def _resolve_target(rc: RunContext, vc: VillageContext, snap: VillageSnapshot):
    """→ (BuildTarget｜None, 說明)。與 build stage 的「無 build_order 舊流程」用同一個 plan()，不寫任何東西。
    目前只支援：沒有 build_order 且 target_building_level＝0（Config 現況）。其餘情況略過並說明原因。"""
    if snap.next_target is not None:                     # 前面有 stage 已補上就直接用
        return snap.next_target, "snapshot.next_target"
    try:
        raw = plan_repo.load_build_order(rc.sh, vc.did)
    except Exception as e:  # noqa: BLE001  讀不到就不猜，略過（建城 stage 自己會處理）
        return None, f"讀 build_order 失敗，略過（{type(e).__name__}）"
    if raw is not None:
        return None, "有 build_order：建城前還不能預判目標，略過（需要 build 拆出預判函式）"
    if int(rc.cfg.get("target_building_level", 0)) > 0:
        return None, "target_building_level>0（含倉庫／糧倉候選）：建城前還不能預判目標，略過"
    d1 = parse_dorf1(rc.get_page("dorf1.php", raw_if=rc.dorf1_raw_if))
    d = plan(d1, vc.build_settings, vc.is_capital, extra=[], touched=set(), queue_secs=None)
    if d.kind != "wait_resources" or d.target is None:
        return None, f"建城決策是 {d.kind}（不是等資源），不需轉"
    if (d.wait_s or 0) <= 0:
        return None, "目標已付得起，不需轉"
    return dataclasses.replace(d.target, ready_in_s=d.wait_s), "預判（舊流程 plan）"


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw = rc.gateway
    cfg = rc.cfg
    t, why = _resolve_target(rc, vc, snap)
    log.info("item_transfer 目標：%s｜%s", (f"{t.name} →L{t.to_level} cost={t.cost}" if t is not None else None), why)
    if t is None:
        return StageResult(status="skipped", note=why)
    settings = TransferSettings(min_inventory=int(cfg.get("hero_transfer_min", 20000)),
                                max_gap=int(cfg.get("hero_transfer_max_gap", 1000)),
                                eta_min=int(cfg.get("hero_transfer_eta_min", 45)))
    need = tuple(t.cost)
    queue_busy = snap.queue_slots_used >= vc.build_settings.queue_slots
    eta = parse_dorf1(rc.get_page("dorf1.php")).attack_eta_s if snap.incoming_attacks else None

    pre = decide_item_transfer(need, None, queue_busy, eta, settings)
    log.info("item_transfer 預判：kind=%s｜incoming_attacks=%s｜attack_eta_s=%s｜門檻=%s分｜mode=%s",
             pre.kind, snap.incoming_attacks, eta, settings.eta_min, mode)
    if pre.kind == "not_needed":
        return StageResult(status="skipped", note=pre.reason)

    head = f"{fname(t)} {flv(t.to_level - 1, t.gid)}"
    try:
        state = read_transfer_state(gw)
    except (GatewayError, ParseError) as e:
        rc.io.notify(f"英雄道具庫轉移：讀取狀態失敗，略過本輪（不影響建城）: {e!r}")
        row = U.make_row(rc, vc.did, U.ACTION_ITEM_TRANSFER, mode, "failed", f"{head}｜讀取狀態失敗｜{e!r}", t)
        return StageResult(status="failed", actions=[row], note=f"讀取轉移狀態失敗：{type(e).__name__}")

    dec = decide_item_transfer(need, state, queue_busy, eta, settings)
    gaps = [max(0, need[i] - state.stock[i]) for i in range(4)]
    inv = [(getattr(it, "amount", None) if it is not None else None) for it in state.inventory]
    log.info("item_transfer 決策：kind=%s｜缺口=%s｜道具庫=%s｜村莊現量=%s", dec.kind, gaps, inv, list(state.stock))
    desc = f"{head}｜{dec.kind}：{dec.reason}｜缺口={gaps}｜道具庫={inv}｜來襲ETA={eta}"
    if not dec.act:
        return StageResult(status="ok", actions=[U.make_row(rc, vc.did, U.ACTION_ITEM_TRANSFER, mode, "skipped", desc, t)])

    res = execute_item_transfer(gw, dec, mode)
    updates = {}
    if res.result == "ok":
        moved = {ln.resource: ln.amount for ln in dec.lines}
        updates = {"stock": tuple(snap.stock[i] + moved.get(i, 0) for i in range(4)),
                   "next_target": dataclasses.replace(t, ready_in_s=0)}
        rc.pages.pop("dorf1.php", None)           # 資源已變：後面的 build 重讀 dorf1
        rc.io.notify(f"已從英雄道具庫轉資源：{res.detail}")
    elif res.result == "failed":
        rc.io.notify(f"英雄道具庫轉移沒有確認成功（不重試）：{res.detail}")
    row = U.make_row(rc, vc.did, U.ACTION_ITEM_TRANSFER, mode, res.result, f"{desc}｜{res.detail}", t)
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       snapshot_updates=updates, note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="item_transfer", scope="village", mode_key="item_transfer", order=20,
              precondition=precondition, run=run)
