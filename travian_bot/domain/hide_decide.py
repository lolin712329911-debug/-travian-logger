#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/hide_decide.py（dm-08）
版本：v0.1（A3c）
用途：躲兵決策（純函式）：看集結點概況與 hide_plan 算好的候選，決定躲或不躲、派哪些兵、撐過哪幾波、候選順序，
      以及自己的兵歸來後到下一波之間的空檔（歸來窗口）。不碰網路、不讀全域、不讀時區（epoch 秒）。
依賴：cm-01、cm-02、cm-09（卡片列的三張；本檔實際只 import cm-02、cm-09）。
部署狀態：未部署（GA 前不 live）。

公開介面
  HideCfg(speeds, attacks, lookahead_min=90, cluster_min=120, min_lead_s=120, min_attack=None, include_unverified=True, margin=30)
  sendable_units(overview)               → 本村在家兵力（不含英雄、不含 0）
  hostile_arrivals(overview)             → 敵方來襲到達 epoch（已排序）
  attack_total(units, attacks)           → 攻擊力合計（沒列的兵種算 0）
  decide(overview, candidates, units, cfg) → HideDecision
  return_windows(overview, attacks)      → list[ReturnWindow]（歸來窗口，依歸來時間排序）

來源：舊 hide_troops.py v0.5（✓ 已讀）的 decide、attack_total、return_windows、home_units、incoming_arrivals。
重新規劃（§5.1 b 不成立：舊 decide 內部呼叫 dispatch.plan 並讀 dispatch.HOME／OASES／BLOCKED／UNIT_* 全域）：
  候選由 hide_plan.plan 先算好傳入，速度表與攻擊力表由呼叫端用 hide_plan.unit_speeds／unit_attacks 放進 HideCfg
  （本檔不依賴 cm-06）。判斷順序與文字與舊 decide 逐條相同：
  no_units → unknown_speed → weak（min_attack，嚴格大於才派）→ no_future → too_far（wait）→ too_close → no_oasis → go。
差異：①now／arrivals 是 epoch，不是 datetime②來襲到達時間取自 RallyOverview（ps-06，hostile 且有計時器）
  ③兵力鍵 u1… 而非 t1…，hero 永遠不派（即使傳進來也會被 unknown_speed 擋下，不會被當成可派兵種）
  ④「一趟撐過全部」改由 HideDecision.full 表示，不再用 reason 開頭字串判斷。
candidates 必須是 hide_plan.plan 回傳的順序（距離近→遠）；且 plan 的 arrivals 要包含 scope 內全部來襲。
margin 只給呼叫 hide_plan 用（decide 不用；covered 已含 margin 的結果）。
"""
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple

from ..common.decisions import HideCandidate, HideDecision
from ..common.parsed import RallyOverview

__all__ = ["HideCfg", "ReturnWindow", "sendable_units", "hostile_arrivals", "attack_total", "decide", "return_windows"]


@dataclass(frozen=True)
class HideCfg:
    speeds: Mapping[str, float]                 # 可派兵種 → 格／時（hide_plan.unit_speeds）；不在表內＝速度未知
    attacks: Mapping[str, int]                  # 單兵攻擊力（hide_plan.unit_attacks）；沒列算 0
    lookahead_min: int = 90                     # 第一波超過幾分鐘才到就先等（wait）
    cluster_min: int = 120                      # 第一波之後幾分鐘內的來襲要一起撐
    min_lead_s: int = 120                       # 第一波至少還有幾秒（來不及兩步驟派兵）；歸來窗口的「空檔夠不夠」也用它
    min_attack: Optional[int] = None            # 派出兵力攻擊力合計必須嚴格大於它；None＝不檢查（Config hide_min_attack）
    include_unverified: bool = True             # False＝只用 safe 為 True 的綠洲（舊預設 True：發兵前一律即時驗證）
    margin: int = 30                            # 給 hide_plan 的安全緩衝秒數


@dataclass(frozen=True)
class ReturnWindow:
    """自己的兵歸來後、下一波來襲前的空檔（舊 return_windows 的 dict）。"""
    return_ts: int
    units: Tuple[Tuple[str, int], ...]
    attack: int
    next_attack_ts: int
    gap_s: int


def sendable_units(overview: RallyOverview) -> dict:
    """本村在家兵力：不含英雄、不含 0；沒有在家表（units_home 為 None）→ {}。"""
    return {k: n for k, n in (overview.units_home or {}).items() if k != "hero" and n}


def hostile_arrivals(overview: RallyOverview) -> List[int]:
    """敵方來襲（inRaid／inAttack）的到達 epoch，已排序；沒有計時器的略過。"""
    return sorted(m.arrive_ts for m in overview.movements if m.hostile and m.arrive_ts)


def attack_total(units: Mapping[str, int], attacks: Mapping[str, int]) -> int:
    return sum(attacks.get(u, 0) * n for u, n in units.items() if n)


def _skip(code: str, reason: str, units=(), scope=()):
    return HideDecision(False, None, (), reason, kind="skip", code=code, units=tuple(units), scope=tuple(scope))


def decide(overview: RallyOverview, candidates: Sequence[HideCandidate], units: Mapping[str, int],
           cfg: HideCfg) -> HideDecision:
    now = overview.server_ts
    units = {k: n for k, n in units.items() if n}
    pairs = tuple(sorted(units.items()))
    if not units:
        return _skip("no_units", "村裡沒有可派的兵")
    unknown = [u for u in units if u not in cfg.speeds]
    if unknown:
        return _skip("unknown_speed", f"兵種速度未知：{','.join(sorted(unknown))}（請先量測或加進 speeds）")
    if cfg.min_attack is not None:
        total = attack_total(units, cfg.attacks)
        if total <= cfg.min_attack:
            return _skip("weak", f"攻擊力合計 {total} 不超過 {cfg.min_attack}（動物底值 10 的兩倍，派出去可能白送）", pairs)
    fut = [a for a in hostile_arrivals(overview) if a > now]
    if not fut:
        return _skip("no_future", "沒有未來的來襲")
    lead = fut[0] - now
    if lead > cfg.lookahead_min * 60:
        return HideDecision(False, None, (), f"第一波還有 {lead / 60:.0f} 分鐘（> {cfg.lookahead_min}）",
                            kind="wait", code="too_far")
    if lead < cfg.min_lead_s:
        return _skip("too_close", f"第一波只剩 {lead:.0f} 秒，來不及兩步驟派兵")
    scope = [a for a in fut if a <= fut[0] + cfg.cluster_min * 60]
    rows = list(candidates)
    if not cfg.include_unverified:
        rows = [c for c in rows if c.safe is True]
    covered_in_scope = lambda c: [a for a in scope if a in c.covered]
    full = [c for c in rows if len(covered_in_scope(c)) == len(scope)]
    part = sorted((c for c in rows if c not in full and scope[0] in c.covered),
                  key=lambda c: (-len(covered_in_scope(c)), c.distance if c.distance is not None else float("inf")))
    cands = full + part
    if not cands:
        return _skip("no_oasis", "沒有任何綠洲能撐過第一波", pairs, scope)
    reason = "可一趟撐過範圍內全部來襲" if full else "只能撐過前幾波，返回後需再發第二趟"
    return HideDecision(True, cands[0], tuple(cands), reason, kind="go", code="ok", units=pairs,
                        scope=tuple(scope), full=bool(full))


def return_windows(overview: RallyOverview, attacks: Mapping[str, int]) -> List[ReturnWindow]:
    """自己的兵（inReturn）歸來後、下一波來襲前的空檔，依歸來時間排序。
    只列：歸來還沒到（> now）、歸來後還有來襲、兵力欄位都讀得到（不含英雄；None＝顯示 ? 就略過）、有兵。
    用途：兵歸來的那一刻要有一次 run 把它們再派出去（舊 v2.79 ③ 的 12 分 24 秒空檔）。"""
    now = overview.server_ts
    hostile = hostile_arrivals(overview)
    out = []
    for m in overview.movements:
        if "inReturn" not in m.kinds or not m.arrive_ts or m.arrive_ts <= now:
            continue
        body = {k: n for k, n in m.units.items() if k != "hero"}
        if any(n is None for n in body.values()):
            continue
        us = {k: n for k, n in body.items() if n}
        nxt = [a for a in hostile if a > m.arrive_ts]
        if not us or not nxt:
            continue
        out.append(ReturnWindow(m.arrive_ts, tuple(sorted(us.items())), attack_total(us, attacks),
                                nxt[0], nxt[0] - m.arrive_ts))
    return sorted(out, key=lambda w: w.return_ts)
