#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/guard.py（dm-03）
版本：v0.1（A3a）
用途：庫存防搶＋防溢出：預估下一輪結束時各資源的「溢出」與「超過山洞隱藏量的暴露」，挑英雄資源加成類型讓兩者合計最小（純函式）。
依賴：cm-01（models）、cm-02（decisions）。
部署狀態：未部署（GA 前不 live）。

來源：舊 stock_guard.py v0.3（✓ 已讀；演算法完全沿用。注意舊 v0.3 新增部分「未部署、未實測」，本檔同樣未實測）。
與舊版差異：
  1. 舊檔 from hero_focus import hero_bonus, RES_NAME 取消（舊根目錄 import；且 domain 不能 import 其他 domain）。
     hero_bonus 的 3 行邏輯在本檔私有 _hero_bonus；A3b（dm-04 focus）會有同樣的一份，要不要抽到 common 由 A3b 決定。
  2. 加成類型一律是整數碼（hero.productionType：0 平均、1 木、2 磚、3 鐵、4 穀），types＝productionTypes（長度 5）。
  3. 資料改由 VillageSnapshot 取：stock／prod／hidden（每種資源各一個）／cap_wh／cap_gr／incoming_attacks。
     cap 兩者都 ≤ 0（沒讀到）時用舊預設容量 {4000, 4000, 4000, 3100}。
  4. 評分參數改成 GuardParams。lambda：exposure＝'always' 或有來襲才用 lambda_exposure，否則 0（舊 runner 的 gmode 邏輯；
     dry 模式由 stage 傳 'always'）。off 模式由 stage 處理（不呼叫）。
  5. 回傳 GuardDecision（act、focus、reason）取代 ("keep"/"switch", 類型, 原因)。
  6. gaps_from_plan → gaps_from_decision（吃 BuildDecision）。
v0.3 原則（沿用）：補齊時間＝max(ready_in_h, 最慢缺口÷產量)；slack 夾到 ≤ switch_ratio；守衛本身沒有冷卻。
穀產量請給含英雄加成的淨產量（snapshot.prod[3]＝dorf1 的 l4）。
"""
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from ..common.decisions import BuildDecision, GuardDecision
from ..common.models import VillageSnapshot

__all__ = ["DEFAULT_CAPACITY", "GuardParams", "exposure", "overflow", "score_stock", "decide_guard",
           "gaps_from_decision"]

DEFAULT_CAPACITY = {1: 4000, 2: 4000, 3: 4000, 4: 3100}
_LABEL = {0: "平均", 1: "木", 2: "磚", 3: "鐵", 4: "穀"}
_EXPOSURES = ("incoming", "always")


@dataclass(frozen=True)
class GuardParams:
    horizon_h: float = 1.25          # 輪距中位 48 分、最長 73 分
    slack: float = 1.3
    min_gain: float = 150.0          # 評分單位
    crop_floor: float = 0.0
    lambda_exposure: float = 0.5     # △ 未校準
    switch_ratio: float = 1.3        # 和 focus.decide_focus 的 1.3 對齊


def _hero_bonus(ptype: int, types: Sequence[int], res: int) -> int:
    if ptype == 0:
        return types[0]
    return types[ptype] if res == ptype else 0


def _cap_of(snapshot: VillageSnapshot) -> Mapping[int, float]:
    if snapshot.cap_wh <= 0 and snapshot.cap_gr <= 0:
        return DEFAULT_CAPACITY
    return {1: snapshot.cap_wh, 2: snapshot.cap_wh, 3: snapshot.cap_wh, 4: snapshot.cap_gr}


def exposure(stock: Mapping[int, float], production: Mapping[int, float], hours: float,
             hidden: Mapping[int, float], capacity: Mapping[int, float]) -> dict:
    """{1..4: 預估 hours 小時後超過隱藏量的數量}。超過倉容的部分是溢出，不算暴露。"""
    out = {}
    for r in (1, 2, 3, 4):
        proj = max(0.0, min(capacity[r], stock[r] + production[r] * hours))
        out[r] = max(0.0, proj - hidden[r])
    return out


def overflow(stock: Mapping[int, float], production: Mapping[int, float], hours: float,
             capacity: Mapping[int, float]) -> dict:
    """{1..4: 預估 hours 小時內超過倉容而浪費掉的數量}。"""
    return {r: max(0.0, stock[r] + production[r] * hours - capacity[r]) for r in (1, 2, 3, 4)}


def _dicts(snapshot: VillageSnapshot):
    stock = {i + 1: snapshot.stock[i] for i in range(4)}
    prod = {i + 1: snapshot.prod[i] for i in range(4)}
    hidden = {i + 1: snapshot.hidden[i] for i in range(4)}
    return stock, prod, hidden, _cap_of(snapshot)


def score_stock(snapshot: VillageSnapshot, params: GuardParams = GuardParams(),
                lambda_exposure: Optional[float] = None) -> Tuple[float, float, float]:
    """以目前產量算 (評分, 溢出, 暴露)；評分＝溢出＋lambda×暴露。"""
    stock, prod, hidden, cap = _dicts(snapshot)
    lam = params.lambda_exposure if lambda_exposure is None else lambda_exposure
    w = sum(overflow(stock, prod, params.horizon_h, cap).values())
    e = sum(exposure(stock, prod, params.horizon_h, hidden, cap).values())
    return w + lam * e, w, e


def decide_guard(snapshot: VillageSnapshot, current: Optional[int], types: Optional[Sequence[int]], *,
                 exposure_mode: str = "incoming", gaps: Optional[Mapping[int, float]] = None,
                 ready_in_h: float = 0.0, params: GuardParams = GuardParams()) -> GuardDecision:
    """候選須滿足：穀產量 > crop_floor；有缺口時補齊時間 ≤ 最快候選 × min(slack, switch_ratio)。
    gaps 是 None＝不限制補齊時間；{}（目標現在就付得起）＝所有候選補齊時間都是 ready_in_h，也不限制。
    要比目前少 min_gain（評分）以上才切。"""
    if exposure_mode not in _EXPOSURES:
        raise ValueError(f"exposure_mode 需為 {_EXPOSURES}")
    if current is None or not types:
        return GuardDecision(False, "讀不到目前加成，不動", exposure_mode)
    lam = params.lambda_exposure if (exposure_mode == "always" or snapshot.incoming_attacks) else 0.0
    slack = min(params.slack, params.switch_ratio)
    stock, production, hidden, cap = _dicts(snapshot)
    h = params.horizon_h

    def after(t, r):
        return production[r] - _hero_bonus(current, types, r) + _hero_bonus(t, types, r)

    def prod_after(t):
        return {r: after(t, r) for r in (1, 2, 3, 4)}

    def expo(t):
        return sum(exposure(stock, prod_after(t), h, hidden, cap).values())

    def waste(t):
        return sum(overflow(stock, prod_after(t), h, cap).values())

    def score(t):
        return waste(t) + lam * expo(t)

    def fill(t):
        worst = 0.0
        for r, g in (gaps or {}).items():
            p = after(t, r)
            if p <= 0:
                return float("inf")
            worst = max(worst, g / p)
        return max(worst, ready_in_h) if gaps is not None else worst

    now, w_now, e_now = score(current), waste(current), expo(current)
    if now <= 0:
        return GuardDecision(False, f"{h:.2f} 小時內不會溢出，也不會超過隱藏量", exposure_mode)
    ok = [t for t in range(5) if after(t, 4) > params.crop_floor]
    if not ok:
        return GuardDecision(False, "所有選項穀產量都 ≤ 下限，不動", exposure_mode)
    best_fill = min(fill(t) for t in ok)
    allowed = [t for t in ok if fill(t) <= best_fill * slack]
    best = min(allowed, key=lambda t: (score(t), t != current))
    sb = score(best)
    if best == current or sb > now - params.min_gain:
        return GuardDecision(False, f"目前評分 {now:.0f}（溢出 {w_now:.0f}、暴露 {e_now:.0f}），"
                                    f"沒有能少 {params.min_gain:.0f} 以上的選項", exposure_mode)
    tag = "溢出" if w_now > 0 else "暴露"
    return GuardDecision(True, f"改 {_LABEL[best]}（{tag}）：評分 {now:.0f} → {sb:.0f}"
                               f"（溢出 {w_now:.0f}→{waste(best):.0f}、暴露 {e_now:.0f}→{expo(best):.0f}）"
                               + (f"，補齊缺口約 {fill(best):.1f}h" if gaps else "，無缺口：只是停放／避溢出"),
                         exposure_mode, best)


def gaps_from_decision(decision: BuildDecision, stock: Sequence[int], ready_in_h: float):
    """把 build_planner 的決策轉成 (gaps, ready_in_h)；算不出缺口回 None（呼叫端改傳 gaps=None）。
    wait_resources → 缺口＝成本 − 存量（只放 >0 的，鍵 1..4）；build → 現在就付得起，缺口 {}；
    其他（wait_queue、storage_too_small、plan_stuck、no_free_slot、done、need_facts…）一律 None。"""
    if decision.kind not in ("wait_resources", "build") or decision.target is None:
        return None
    gaps = {i + 1: c - s for i, (c, s) in enumerate(zip(decision.target.cost, stock)) if c > s}
    return gaps, max(0.0, float(ready_in_h))
