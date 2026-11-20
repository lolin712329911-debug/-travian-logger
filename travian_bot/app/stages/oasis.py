#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/oasis.py（ap-16）
版本：v0.1（A6a2b）
用途：綠洲清單 stage：把「這個村的綠洲候選」放進本輪的 HideContext，供 hide（ap-15）使用；清單太舊或沒有時掃描並存 Oases 分頁。
依賴：ap-02、ap-03、ap-20、ac-07、if-02、if-10、cm-01、cm-04、cm-07、cm-09、cm-10、cm-11
部署狀態：未部署（GA 前不 live）。未實機驗證。

來源：舊 oasis_store.py v0.3 的 apply、refresh（✓）＋舊 oasis_scan.py 的 free_candidates、blocked_set（✓）。**重新規劃**（§5.1 b 不成立：全域 dispatch.HOME／OASES／BLOCKED）。
行為（單一 stage，order 5，比 hide 早）
  - 有來襲（snap.incoming_attacks 為 None 或 >0）：只讀 Sheet，不掃（省時間，與舊 refresh(allow_scan=False) 一致）。該中心有資料就用（不管多舊，舊版同）；
    沒有資料就寫一列 skipped 說明原因，hide 會因為沒有候選而不動。
  - 沒有來襲：該中心的資料夠新（≤12 小時）就什麼都不做；太舊或沒有 → 掃描（radius 15、最多 30 次請求）→ 存 Oases → 換進 HideContext。
  - 中心＝HideContext 的家座標。oasis_repo 本來就依中心分開存，所以舊版「Sheet 的中心不是現在的家」的核對不需要了：換家或換伺服器
    只會是「這個中心沒有資料」。
  - mode：掃描與讀寫 Oases 都不改變遊戲狀態（ac-07 沒有 mode），所以 dry 與 live 行為相同，只差 Actions 的 mode／result
    （dry 的 result 是 dry，C5 規定 dry 不能 ok）。off 由 run_stage 略過。DRY_RUN 環境因此也會寫 Oases 分頁（機器寫、機器讀的快取，不是遊戲狀態）。
  - 寫 Sheet 失敗只 rc.warn，本輪仍用掃到的結果（舊版同）。
轉換（BlockOasis → HideContext.oases）：未被佔領且沒有動物的綠洲 → Oasis(x, y, kind, safe=None)（未驗證；派兵前 hide_exec 會即時驗證）；
  kind 由加成組成（例 wood25、wood25_crop25；≤20 字）；被佔領或有動物的 map id 放進 blocked。依距離（環繞）、座標排序。
"""
from datetime import timezone
from typing import Optional, Sequence, Tuple

from ...actions.oasis_exec import OasisExecError, scan
from ...common import geo, serialize
from ...common.models import HideContext, Oasis, StageResult, VillageContext, VillageSnapshot
from ...common.modes import Mode
from ...common.parsed import BlockOasis
from ...common.schema import ParseError
from ...infra.gateway import GatewayError
from ...infra.store.oasis_repo import OasisTableError
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "MAX_AGE_H", "RADIUS", "MAX_REQUESTS", "kind_of", "to_hide_oases", "precondition", "run"]

MAX_AGE_H = 12.0
RADIUS = 15
MAX_REQUESTS = 30
_RES = ("wood", "clay", "iron", "crop")      # 資源索引 0..3＝木磚鐵穀
KIND_MAX = 20


# ---------------------------------------------------------------- 純函式
def kind_of(bonuses: Sequence[Tuple[int, int]]) -> str:
    """加成 → kind。例 ((0, 25),) → wood25；((0, 25), (3, 25)) → wood25_crop25；沒有加成 → oasis。"""
    parts = [f"{_RES[i]}{pct}" if isinstance(i, int) and 0 <= i < 4 else f"r{i}_{pct}" for i, pct in bonuses]
    return ("_".join(parts) or "oasis")[:KIND_MAX]


def to_hide_oases(oases: Sequence[BlockOasis], home: Tuple[int, int], map_half: int) -> Tuple[Tuple[Oasis, ...], Tuple[int, ...]]:
    """掃描結果 → (候選, blocked map id)。候選：未被佔領且沒有動物；依 (距離, x, y) 排序。"""
    free, blocked = [], set()
    for o in oases:
        if o.taken or o.animals:
            blocked.add(geo.map_id(o.x, o.y, map_half))
        else:
            free.append((geo.distance(home, (o.x, o.y), map_half), o.x, o.y, o))
    free.sort(key=lambda r: r[:3])
    return tuple(Oasis(x=o.x, y=o.y, kind=kind_of(o.bonuses), safe=None) for _d, _x, _y, o in free), tuple(sorted(blocked))


def _age_hours(updated_utc: Optional[str], now) -> Optional[float]:
    if not updated_utc:
        return None
    try:
        t = serialize.parse_utc(updated_utc)
    except (serialize.SerializeError, ValueError, TypeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 3600.0


def _apply(rc: RunContext, vc: VillageContext, oases: Sequence[BlockOasis]):
    base = U.hide_context_of(rc, vc)
    free, blocked = to_hide_oases(oases, (base.home_x, base.home_y), rc.profile.map_half)
    U.set_hide_context(rc, vc.did, HideContext(home_x=base.home_x, home_y=base.home_y, oases=free, blocked=blocked,
                                                tribe=base.tribe))
    return len(free), len(blocked)


# ---------------------------------------------------------------- stage
def precondition(rc: RunContext, vc: Optional[VillageContext], snap: Optional[VillageSnapshot]) -> bool:
    return vc is not None


def run(rc: RunContext, vc: VillageContext, snap: Optional[VillageSnapshot], mode: Mode) -> StageResult:
    io = rc.io
    if io.oasis_centers is None:
        return StageResult(status="skipped", note="StageIO.oasis_centers 沒接，略過綠洲清單")
    base = U.hide_context_of(rc, vc)
    center = (base.home_x, base.home_y)
    result = "ok" if mode is Mode.LIVE else "dry"
    incoming = snap is None or snap.incoming_attacks != 0
    now = io.now()

    def row(res: str, detail: str):
        return U.make_row(rc, vc.did, U.ACTION_OASIS, mode, res, f"中心={center}｜{detail}")

    try:
        info = next((c for c in io.oasis_centers(rc.sh) if (c.x, c.y) == center), None)
        age = _age_hours(info.updated_utc, now) if info is not None else None
        fresh = info is not None and info.count > 0 and age is not None and age <= MAX_AGE_H

        if incoming:                                         # 有來襲：只讀、不掃
            oases = list(io.oasis_load(rc.sh, center)) if info is not None else []
            if not oases:
                return StageResult(status="ok", actions=[row("skipped", "有來襲，但這個中心沒有綠洲資料；來襲時不掃描")])
            n_free, n_blocked = _apply(rc, vc, oases)
            return StageResult(status="ok", note=f"讀 Sheet：候選 {n_free}、排除 {n_blocked}")
        if fresh:
            return StageResult(status="skipped", note=f"綠洲資料 {age:.1f} 小時，夠新")

        n0 = rc.gateway.request_count()
        found = scan(rc.gateway, center, RADIUS, map_half=rc.profile.map_half, max_requests=MAX_REQUESTS, sleep=io.sleep)
        if not found:
            return StageResult(status="failed", actions=[row("failed", "掃到 0 個綠洲，不寫入、清單維持原狀")],
                               note="掃到 0 個綠洲")
        saved = "已存 Oases"
        try:
            io.oasis_save(rc.sh, center, found, now=serialize.to_utc_str(now))
        except Exception as exc:  # noqa: BLE001 —— 寫 Sheet 失敗不影響本輪使用
            rc.warn(f"oasis：寫 Oases 分頁失敗（本輪仍使用掃描結果）：{type(exc).__name__}")
            saved = f"寫 Oases 失敗（{type(exc).__name__}），本輪仍使用"
        n_free, n_blocked = _apply(rc, vc, found)
        why = "沒有資料" if info is None else f"資料 {age:.1f} 小時，太舊" if age is not None else "更新時間讀不懂"
        return StageResult(status="ok", actions=[row(
            result, f"{why}→掃描 {len(found)} 個綠洲（半徑 {RADIUS}）｜候選 {n_free}、排除 {n_blocked}｜{saved}"
                    f"｜請求 {rc.gateway.request_count() - n0}")])
    except (GatewayError, ParseError, OasisExecError, OasisTableError, ValueError) as e:
        rc.io.notify(f"綠洲清單：失敗，清單維持原狀（不影響建城）: {e!r}")
        return StageResult(status="failed", actions=[row("failed", f"失敗｜{e!r}")], note=f"{type(e).__name__}")


STAGE = Stage(name="oasis", scope="village", mode_key="oasis", order=5, precondition=precondition, run=run)
