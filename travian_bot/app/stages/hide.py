#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/hide.py（ap-15）
版本：v0.2（沒有集結點就不讀概況、不派兵：回 ok＋寫一列 Actions「躲兵」result＝skipped、說明「沒集結點」，不再每輪 failed／紅叉）｜v0.1（A6a2b）
用途：躲兵 stage：有來襲時讀集結點概況 → domain.hide_plan 算候選 → domain.hide_decide 決策 → actions.hide_exec 派兵躲避
      （搶奪空綠洲）→ 寫一列 Actions（動作「躲兵」）。逐村；綠洲清單與家座標取自該村的 HideContext。
依賴：ap-02、ap-03、ap-20、dm-07、dm-08、ac-06、ac-07、ps-06、if-02、cm-01、cm-02、cm-04、cm-09、cm-11
      （卡片原列 ap-06、if-07：實作沒有 import——Actions 由 run_stage 經 rc.io 寫；改列實際 import 的卡片）。
部署狀態：未部署（GA 前不 live）。未實機驗證（HTTP 三步派兵的實機仍 ✗，見 hide_exec 檔頭）。

來源：舊 hide_observe.py v0.4 的 observe（✓）＋舊 hide_troops.py 的歸來窗口等待（✓）。**重新規劃**（§5.1 b 不成立：全域 dispatch.HOME／OASES／BLOCKED）。與舊版的差異
  1. mode：舊 observe／dry／live → 新 dry／live（C9 只有 off／dry／live）。dry＝走到確認頁核對、不送出（舊 dry）；
     舊 observe（只算 plan、不開確認頁）不保留。DRY_RUN 環境下 live 降成 dry 由 run_stage 的 effective_mode 做，stage 不再自己判斷。
  2. 家座標＝HideContext.home（來自 VillageRef）；舊 home_x／home_y Config 備用已退役（config_schema 檔頭 4），「家未知就略過」不再需要。
  3. 綠洲清單用 oasis stage（ap-16）放進 rc.stage_notes 的 HideContext（U.hide_context_of）；沒有就用 vc.hide_context（可能是空的）。
  4. 候選由 hide_plan.plan 先算、再交 hide_decide.decide（A3c）；派兵走 hide_exec.send_troops（A5b，HTTP 三步），綠洲即時驗證用
     oasis_exec.verify_oasis 以 verify 參數注入。
  5. 歸來窗口等待（舊 run_once）在這裡：決策是 skip（no_units／weak）、自己的兵在 hide_wait_max_s 內歸來、而且歸來後到下一波還有
     min_lead_s 以上 → rc.io.sleep 等到歸來後重讀一次。等待時間扣掉讀頁耗時（gateway.elapsed）。
  6. **不搬**：debug_html 存檔（app 層沒有檔案 IO）；沒有候選時固定探測 tile-details（v2.77 驗 page.request.post 的診斷，已由 Gateway.request 取代）；
     側欄 incoming_symbols 與 dorf1 的交叉核對（改用 snap.incoming_attacks 與概況的張數，兩者不同只記在說明欄）。
  7. 英雄永遠不帶（sendable_units 已排除，send_troops 再核對）。
  8. （v0.2）沒有集結點（dorf2 沒有任何 gid 16 的建築，例如被打掉）：不讀概況、不派兵，寫一列「躲兵」skipped＋說明；
     dorf2 取自 rc.get_page（observe 已抓過，不多一個請求）；讀不到 dorf2 就照舊流程去讀概況。
Config：hide_min_attack（預設 20，嚴格大於）、hide_wait_max_s（預設 180；0＝不等）。send_troops 的 max_confirm／max_checks／margin／send_delay_s
  不開 Config 鍵，用函式預設（4／12／30／45）。
"""
from typing import List, Optional, Tuple

from ...actions.hide_exec import OVERVIEW_PATH, send_troops
from ...actions.oasis_exec import verify_oasis
from ...common.decisions import ExecResult
from ...common.models import StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode
from ...common.parsed import RallyOverview
from ...common.schema import ParseError
from ...domain.hide_decide import (HideCfg, ReturnWindow, attack_total, decide, hostile_arrivals, return_windows,
                                   sendable_units)
from ...domain.hide_plan import plan, unit_attacks, unit_speeds
from ...infra.gateway import GatewayError
from ...parsers.rally import parse_overview
from ...parsers.village import parse_dorf2
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "RETURN_BUFFER_S", "precondition", "run"]

RALLY_POINT_GID = 16         # 集結點（固定在 39 號位；v0.2 以「村裡有沒有 gid 16」判斷）
RETURN_BUFFER_S = 3          # 歸來時間之後再等幾秒才重讀（讓兵確實進村；舊 hide_troops.RETURN_BUFFER_S）
_WAIT_CODES = ("no_units", "weak")


def precondition(rc: RunContext, vc: Optional[VillageContext], snap: Optional[VillageSnapshot]) -> bool:
    """沒有來襲就不讀概況（省請求）。incoming_attacks 為 None＝未知：保守起見仍去讀。"""
    if vc is None or snap is None:
        return False
    return snap.incoming_attacks != 0


def _int(v, default: int) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else default


def _has_rally_point(rc: RunContext) -> Optional[bool]:
    """（v0.2）村裡有沒有集結點。dorf2 讀不到或解析失敗回 None（呼叫端照舊流程去讀概況）。"""
    try:
        d2 = parse_dorf2(rc.get_page("dorf2.php"))
    except (GatewayError, ParseError):
        return None
    return any(sl.gid == RALLY_POINT_GID for sl in d2.slots)


def _read(rc: RunContext) -> Tuple[RallyOverview, float]:
    gw = rc.gateway
    ov = parse_overview(gw.get(OVERVIEW_PATH, raw=True))
    return ov, gw.elapsed()


def _evaluate(rc: RunContext, ctx, ov: RallyOverview, cfg: HideCfg):
    units = sendable_units(ov)
    cands = plan(ctx, units, ov.server_ts, hostile_arrivals(ov), map_half=rc.profile.map_half, margin=cfg.margin,
                 server_speed=rc.profile.speed)
    return units, cands, decide(ov, cands, units, cfg)


def _fmt_window(w: ReturnWindow, now: int) -> str:
    return f"歸來 {w.return_ts - now}秒後（攻{w.attack}）→下一波 {w.next_attack_ts - now}秒後（空檔 {w.gap_s}秒）"


def _pairs(items) -> str:
    return ",".join(f"{k}x{n}" for k, n in items)


def run(rc: RunContext, vc: VillageContext, snap: VillageSnapshot, mode: Mode) -> StageResult:
    gw = rc.gateway
    ctx = U.hide_context_of(rc, vc)
    cfg = HideCfg(speeds=unit_speeds(ctx.tribe), attacks=unit_attacks(ctx.tribe),
                  min_attack=_int(rc.cfg.get("hide_min_attack"), 20))
    wait_max = _int(rc.cfg.get("hide_wait_max_s"), 180)
    map_half = rc.profile.map_half

    if _has_rally_point(rc) is False:                    # v0.2：沒有集結點（被打掉或還沒蓋）→ 不讀概況，只寫一列原因
        row = U.make_row(rc, vc.did, U.ACTION_HIDE, mode, "skipped",
                         f"沒集結點（村裡沒有集結點，無法躲兵；請重建 39 號位）｜來襲 dorf1={snap.incoming_attacks}")
        return StageResult(status="ok", actions=[row], note="沒集結點")

    try:
        ov, t_load = _read(rc)
    except (GatewayError, ParseError) as e:
        rc.io.notify(f"躲兵：讀集結點概況失敗，本輪不躲兵（不影響建城）: {e!r}")
        row = U.make_row(rc, vc.did, U.ACTION_HIDE, mode, "failed", f"讀集結點概況失敗｜{e!r}")
        return StageResult(status="failed", actions=[row], note=f"讀概況失敗：{type(e).__name__}")
    if ov.incoming_attacks == 0 and not hostile_arrivals(ov):
        return StageResult(status="skipped", note="概況沒有來襲")

    units, cands, dec = _evaluate(rc, ctx, ov, cfg)
    wins = return_windows(ov, cfg.attacks)
    first_now = ov.server_ts
    notes: List[str] = []
    waited = 0
    if wait_max > 0 and dec.kind == "skip" and dec.code in _WAIT_CODES and wins:
        w = wins[0]
        wait = w.return_ts + RETURN_BUFFER_S - ov.server_ts - (gw.elapsed() - t_load)
        enough = w.next_attack_ts - (w.return_ts + RETURN_BUFFER_S) > cfg.min_lead_s
        if 0 < wait <= wait_max and enough:
            rc.io.sleep(wait)
            waited = round(wait)
            try:
                ov, t_load = _read(rc)
            except (GatewayError, ParseError) as e:
                rc.io.notify(f"躲兵：等待歸來後重讀概況失敗（不影響建城）: {e!r}")
                row = U.make_row(rc, vc.did, U.ACTION_HIDE, mode, "failed", f"等待 {waited}s 後重讀概況失敗｜{e!r}")
                return StageResult(status="failed", actions=[row], note=f"重讀概況失敗：{type(e).__name__}")
            units, cands, dec = _evaluate(rc, ctx, ov, cfg)
        else:
            notes.append(f"有歸來窗口但沒等：等待 {wait:.0f}s（上限 {wait_max}s）、{'空檔夠' if enough else '空檔不夠'}")

    res: Optional[ExecResult] = None
    if dec.act:
        def verify(g, c):
            return verify_oasis(g, c, map_half=map_half, locale=rc.profile.locale)
        res = send_troops(gw, vc.did, dec, mode, map_half=map_half, verify=verify)

    if res is not None:
        result = "dry" if (mode is Mode.DRY and res.result == "ok") else res.result
    else:
        result = "deferred" if dec.kind == "wait" else "skipped"

    leads = ",".join(f"{(a - first_now) / 60:.1f}" for a in hostile_arrivals(ov))
    parts = [f"{dec.kind}:{dec.code}｜{dec.reason}"]
    if res is not None:
        parts.append(f"結果={res.detail}")
    parts.append(f"來襲 dorf1={snap.incoming_attacks}/概況={ov.incoming_attacks}｜提前(分)={leads}")
    parts.append(f"在家={units or '無'}｜攻擊力={attack_total(units, cfg.attacks)}（門檻>{cfg.min_attack}）")
    parts.append(f"綠洲={len(ctx.oases)}")
    if dec.act:
        parts.append(f"派出={_pairs(dec.units)}｜撐過{len(dec.scope)}波{'（一趟）' if dec.full else '（需第二趟）'}")
    if cands:
        parts.append("候選=" + ";".join(f"({c.x}|{c.y}) 單程{c.one_way_s}s{' 缺波' if c.missed else ''}" for c in cands[:2]))
    if wins:
        parts.append("窗口=" + ";".join(_fmt_window(w, first_now) for w in wins))
    if waited:
        parts.append(f"等待={waited}s")
    parts.extend(notes)
    row = U.make_row(rc, vc.did, U.ACTION_HIDE, mode, result, "｜".join(parts))

    updates = {}
    if res is not None and res.result == "ok":
        sent = {k for k, _n in dec.units}
        if ov.units_home is not None:
            updates = {"units_home": {k: n for k, n in ov.units_home.items() if k not in sent}}
        rc.io.notify(f"躲兵：已派 {_pairs(dec.units)} 到 ({dec.chosen.x}|{dec.chosen.y})")
    elif res is not None and res.result == "failed":
        rc.io.notify(f"躲兵失敗（不重試，請人工確認）: {res.detail}")
    failed = res is not None and res.result == "failed"
    return StageResult(status="failed" if failed else "ok", actions=[row], snapshot_updates=updates,
                       note=res.detail if failed else "")


STAGE = Stage(name="hide", scope="village", mode_key="hide", order=10, precondition=precondition, run=run)
