#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/item_transfer.py（ap-11）
版本：v0.3（功能2：有 build_order 也預判目標（照 fill_in.py 的驗證＋plan_with_order 流程）；不管來襲，付不起且道具庫夠就轉；轉成功後一併清掉 build.php?id= 的頁面快取；預判失敗寫一列原因）｜v0.2（建城前自己預判目標，不再依賴 snapshot.next_target）｜v0.1.2（A6a2＋診斷輸出（print，不依賴 logging 設定）；只加 log 與 Actions detail 的道具庫存量，判斷邏輯不變）
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
v0.3（功能2）變更
  8. 不管來襲：TransferSettings.only_on_incoming 寫死 False。付不起（目標在等資源）、佇列有空位、英雄在本村，
     且缺口 ≤ hero_transfer_max_gap、道具庫每種要轉的 ≥ hero_transfer_min 且 ≥ 缺口，就轉（這兩個值請在 Config 調整）。
  9. 有 build_order 也預判：parse_build_order → validate_order（非 proceed 就略過，build stage 會寫「計畫被拒」）→
     usable_order → plan_with_order（parallel_cells＝True，與 build stage 一致）；計畫已達成改走成長清單第 1 層（舊 plan，
     target_building_level>0 仍略過）。目標回 storage_too_small（build 會先升倉庫／糧倉）時不預判。
 10. build_order 取自 vc.build_settings.build_order（與 plan_repo 同為 Config 的 build_order 鍵），省掉每輪一次 Sheet 讀取。
 11. 轉成功後除了 dorf1，也清掉 rc.pages 內 build.php?id= 開頭的頁面（空地建造清單、建築頁）：否則新蓋建築時，規劃器讀到的
     是轉資源前的舊頁面（沒有綠色按鈕），會誤判成 blocked。
 12. 不成功要寫原因：決策不轉（缺口太大、道具庫不足、超過倉容…）、轉移失敗、預判本身失敗，都寫一列 Actions「轉移」並帶原因；
     「目標已付得起」「不是等資源」這類不需要轉的情況不寫（否則每輪一列）。
"""
import dataclasses
import logging

from ...actions.item_transfer_exec import execute_item_transfer, read_transfer_state
from ...common import serialize
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode
from ...common.schema import ParseError
from ...domain.build_planner import plan, plan_with_order
from ...domain.item_transfer import TransferSettings, decide_item_transfer
from ...domain.plan_validate import parse_build_order, usable_order, validate_order, validation_need
from ...infra.gateway import GatewayError
from ...parsers.village import parse_dorf1
from ..formatting import flv, fname
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]

_log = logging.getLogger("item_transfer")
_ERR_PREFIX = "預判失敗"          # _resolve_target 的說明以此開頭＝預判本身出錯，run() 會寫一列原因


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


def _wait_target(d, src: str):
    """建城決策 → (等資源的 BuildTarget｜None, 說明)。只有「等資源且還要等」才需要轉。"""
    if d.kind != "wait_resources" or d.target is None:
        return None, f"建城決策是 {d.kind}（不是等資源），不需轉"
    if (d.wait_s or 0) <= 0:
        return None, "目標已付得起，不需轉"
    return dataclasses.replace(d.target, ready_in_s=d.wait_s), src


def _legacy_target(rc: RunContext, vc: VillageContext, d1, src: str):
    """沒有 build_order（或計畫已達成）時，與 build stage 舊流程用同一個 plan() 預判；不寫任何東西。
    target_building_level>0（含倉庫／糧倉候選）建城前還不能預判，略過。"""
    if int(rc.cfg.get("target_building_level", 0)) > 0:
        return None, "target_building_level>0（含倉庫／糧倉候選）：建城前還不能預判目標，略過"
    d = plan(d1, vc.build_settings, vc.is_capital, extra=[], touched=set(), queue_secs=None)
    return _wait_target(d, src)


def _resolve_target(rc: RunContext, vc: VillageContext, snap: VillageSnapshot):
    """→ (BuildTarget｜None, 說明)。與 build stage 用同一套規則預判「這輪要蓋什麼、付不付得起」，不寫任何東西。
    有 build_order：驗證（非 proceed 略過）→ plan_with_order；沒有：舊流程 plan。預判出錯回 (None, "預判失敗…")。"""
    if snap.next_target is not None:                     # 前面有 stage 已補上就直接用
        return snap.next_target, "snapshot.next_target"
    bs = vc.build_settings
    d1 = parse_dorf1(rc.get_page("dorf1.php", raw_if=rc.dorf1_raw_if))
    if not bs.build_order:
        return _legacy_target(rc, vc, d1, "預判（舊流程 plan）")
    try:
        steps = parse_build_order(bs.build_order)
        _, facts = U.run_with_facts(rc, lambda f: (None, validation_need(steps, d1, f, vc.is_capital)))
        verdict = validate_order(steps, d1, facts, vc.is_capital, vc.did, serialize.to_utc_str(rc.io.now()))
        if verdict.verdict != "proceed":
            return None, "build_order 被拒（hold），不預判（build stage 會寫計畫被拒）"
        order = usable_order(steps, vc.is_capital)
        d, _ = U.run_with_facts(rc, U.decision_step(
            lambda f: plan_with_order(order, d1, f, bs, vc.is_capital, touched=(), queue_secs=None,
                                      parallel_cells=True)))
        if d.kind == "done":                             # 計畫已達成 → build 會走成長清單第 1 層
            return _legacy_target(rc, vc, d1, "預判（計畫已達成，成長清單第 1 層）")
    except (GatewayError, ParseError, RuntimeError) as e:
        return None, f"{_ERR_PREFIX}（{type(e).__name__}：{e}），略過；build stage 會自己處理"
    return _wait_target(d, "預判（build_order）")


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw = rc.gateway
    cfg = rc.cfg
    t, why = _resolve_target(rc, vc, snap)
    log.info("item_transfer 目標：%s｜%s", (f"{t.name} →L{t.to_level} cost={t.cost}" if t is not None else None), why)
    if t is None:
        if why.startswith(_ERR_PREFIX):                  # 預判本身出錯：寫一列原因（其餘「不需轉」不寫，避免每輪一列）
            row = U.make_row(rc, vc.did, U.ACTION_ITEM_TRANSFER, mode, "skipped", why)
            return StageResult(status="ok", actions=[row], note=why[:200])
        return StageResult(status="skipped", note=why)
    # v0.3：不管來襲（only_on_incoming＝False）；缺口上限與道具庫門檻由 Config hero_transfer_max_gap／hero_transfer_min 決定
    settings = TransferSettings(min_inventory=int(cfg.get("hero_transfer_min", 20000)),
                                max_gap=int(cfg.get("hero_transfer_max_gap", 1000)),
                                eta_min=int(cfg.get("hero_transfer_eta_min", 45)),
                                only_on_incoming=False)
    need = tuple(t.cost)
    queue_busy = snap.queue_slots_used >= vc.build_settings.queue_slots
    eta = parse_dorf1(rc.get_page("dorf1.php")).attack_eta_s if snap.incoming_attacks else None   # 只用於說明文字
    log.info("item_transfer 預判：incoming_attacks=%s｜attack_eta_s=%s（不影響是否轉）｜缺口門檻=%s｜道具庫門檻=%s｜mode=%s",
             snap.incoming_attacks, eta, settings.max_gap, settings.min_inventory, mode)
    if queue_busy:
        return StageResult(status="skipped", note="施工佇列已滿，不轉")

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
        for k in [k for k in rc.pages if k.startswith("build.php?id=")]:
            rc.pages.pop(k, None)                 # v0.3：空地建造清單／建築頁也是轉資源前的舊頁面（沒有綠色按鈕），一併重抓
        rc.io.notify(f"已從英雄道具庫轉資源：{res.detail}")
    elif res.result == "failed":
        rc.io.notify(f"英雄道具庫轉移沒有確認成功（不重試）：{res.detail}")
    row = U.make_row(rc, vc.did, U.ACTION_ITEM_TRANSFER, mode, res.result, f"{desc}｜{res.detail}", t)
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       snapshot_updates=updates, note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="item_transfer", scope="village", mode_key="item_transfer", order=20,
              precondition=precondition, run=run)
