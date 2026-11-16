#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/focus.py（dm-04）
版本：v0.1（A3b）
用途：decide_focus(snapshot, focus, settings, hours_since_change) → FocusDecision。
      要不要切英雄資源產量加成、切到哪一種。純函式，不碰網路、不讀 Config（settings 由 A6a2 組）。
依賴：cm-02（FocusDecision、FOCUS_NAMES）、cm-09（HeroFocus）；snapshot 只用 C2 欄位（VillageSnapshot 型別不匯入）。
部署狀態：未部署（GA 前不 live）。

來源 hero_focus.py v0.3.1 的 decide_focus／hero_bonus（✓ 已讀）。重新規劃（A3b）：
  1. 缺口與產量不再由呼叫端算：缺口＝snapshot.next_target.cost − snapshot.stock（只留 >0）；產量＝snapshot.prod
     （穀為淨產量，✓ Dorf1 l4）。next_target 為 None＝沒有缺口。
  2. 加成資料用 HeroFocus（HeroState 沒有加成欄位）；None＝讀不到，不動。
  3. 回傳 FocusDecision（focus 為 FOCUS_NAMES 名稱），不再回 ("switch", 0..4)。
  4. 新增防呆：有缺口的資源，目標成本超過倉容（永遠補不齊）→ 不切。
  5. 設定值：min_hours 取 Config hero_focus_min_hours 的預設 1.0（舊函式預設 3.0，舊 runner 實際值未讀 ✗）；
     switch_ratio／crop_floor／back_to_balanced 沒有 Config 鍵，先放預設（A6a2 決定要不要開鍵）。
  hero_bonus 與 guard._hero_bonus 重複（A3a 留的事項）：不抽 common，由測試確認兩者一致。
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from ..common.decisions import FOCUS_NAMES, FocusDecision
from ..common.parsed import HeroFocus

__all__ = ["FocusSettings", "hero_bonus", "decide_focus"]


@dataclass(frozen=True)
class FocusSettings:
    min_hours: float = 1.0          # Config hero_focus_min_hours（距上次切換至少幾小時）
    switch_ratio: float = 1.3       # 目前加成的補齊時間要超過最佳的幾倍才切
    crop_floor: float = 0.0         # 切換後穀淨產量須大於此值
    back_to_balanced: bool = True   # 沒有缺口時切回平均


def hero_bonus(ptype: int, types: Sequence[int], res: int) -> int:
    """加成類型 ptype（0 平均、1～4 單押）下，英雄對資源 res（1 木、2 磚、3 鐵、4 穀）貢獻的每小時產量。"""
    if ptype == 0:
        return types[0]
    return types[ptype] if res == ptype else 0


def _keep(reason: str) -> FocusDecision:
    return FocusDecision(False, None, reason)


def _switch(t: int, reason: str) -> FocusDecision:
    return FocusDecision(True, FOCUS_NAMES[t], reason)


def decide_focus(
    snapshot: Any,                              # VillageSnapshot：用 stock、prod、cap_wh、cap_gr、next_target
    focus: Optional[HeroFocus],
    settings: FocusSettings = FocusSettings(),
    hours_since_change: Optional[float] = None,
) -> FocusDecision:
    if focus is None:
        return _keep("讀不到目前加成，不動")
    current, types = focus.current, focus.types
    if hours_since_change is not None and hours_since_change < settings.min_hours:
        return _keep(f"距上次切換 {hours_since_change:.1f}h < {settings.min_hours}h")

    production: Dict[int, int] = {r: snapshot.prod[r - 1] for r in range(1, 5)}
    gaps: Dict[int, int] = {}
    target = snapshot.next_target
    if target is not None:
        for r in range(1, 5):
            g = target.cost[r - 1] - snapshot.stock[r - 1]
            if g > 0:
                gaps[r] = g
        for r in gaps:
            cap = snapshot.cap_gr if r == 4 else snapshot.cap_wh
            if target.cost[r - 1] > cap:
                return _keep(f"目標成本（資源 {r}）{target.cost[r - 1]} 超過倉容 {cap}，補不齊，不切")

    def after(t: int, r: int) -> float:
        return production[r] - hero_bonus(current, types, r) + hero_bonus(t, types, r)

    if not gaps:
        if settings.back_to_balanced and current != 0 and after(0, 4) > settings.crop_floor:
            return _switch(0, "沒有缺口，切回平均（四種資源合計產量較高）")
        return _keep("沒有缺口")

    def fill_hours(t: int) -> float:
        worst = 0.0
        for r, g in gaps.items():
            p = after(t, r)
            if p <= 0:
                return float("inf")
            worst = max(worst, g / p)
        return worst

    ok = [t for t in range(5) if after(t, 4) > settings.crop_floor]
    if not ok:
        return _keep("所有選項穀淨產量都 ≤ 下限，不動")
    best = min(ok, key=fill_hours)
    hb, hc = fill_hours(best), fill_hours(current)
    name = FOCUS_NAMES
    if best == current:
        return _keep(f"目前 {name[current]} 已是最快（補齊約 {hc:.1f} 小時）")
    if hc <= hb * settings.switch_ratio:
        return _keep(f"{name[best]} 只快一點（{hb:.1f}h vs 目前 {hc:.1f}h），不切")
    return _switch(best, f"改 {name[best]}：補齊缺口約 {hb:.1f} 小時，目前 {name[current]} 要 {hc:.1f} 小時")
