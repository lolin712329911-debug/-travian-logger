#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/hide_plan.py（dm-07）
版本：v0.1（A3c）
用途：躲兵計畫（純函式）。給定家、候選綠洲、在家兵力、現在與來襲到達時間，算出每個綠洲「現在出發」的
      單程／返回時間與撐過哪幾波，並提供推薦（recommend）。不碰網路、不讀全域、不讀時區（時間一律 epoch 秒）。
依賴：cm-01（HideContext）、cm-02（HideCandidate）、cm-06（tribe_data）、cm-07（geo）。
部署狀態：未部署（GA 前不 live）。

公開介面
  unit_speeds(tribe)                     → {'u1': 格/時, …}（可拿來躲兵的兵種；給 hide_decide.HideCfg）
  unit_attacks(tribe)                    → {'u1': 單兵攻擊, …}（沒資料的兵種不列，視為 0）
  slowest_speed(tribe, units)            → 派出兵力中最慢的速度；有未知兵種／英雄／沒有兵 → None
  plan_at_speed(ctx, speed, now_ts, arrivals_ts, *, map_half, margin=30) → list[HideCandidate]（依距離、座標排序）
  plan(ctx, units, now_ts, arrivals_ts, *, map_half, margin=30, server_speed=1) → list[HideCandidate]
  recommend(candidates, include_unverified=False) → HideCandidate 或 None

來源：舊 dispatch.py v1.8（✓ 已讀）的 plan、recommend、TRIBES 兵種表；舊 hide_troops.decide 的速度選取（最慢者）。
套用（五條都成立，§5.1）：公式與舊 plan 相同（距離環繞、單程＝round(距離÷速度×3600)、back＝now＋2×單程、
  撐過＝now＜a＜back－margin），差別只有：①HOME／OASES／BLOCKED／MAP_SIZE 全域改成 HideContext＋map_half 參數
  ②datetime／timedelta 改 epoch 整數秒③兵種鍵 t1… 改 u1…，速度／攻擊力表改由 tribe_data 取得
  ④blocked 是 map id（C9），舊版是座標集合⑤結果由 dict 改 HideCandidate。
舊版 TRIBES 表「只收步兵／騎兵，攻城器、拓荒者、首領不收」：新版以 ESCAPE_UNITS（u1～u6）重現——u7、u8 攻城器、
  u9 首領、u10 拓荒者在各族一致（tribe_data 檔頭 ✓，u1～u6 為戰鬥兵種 △ 以官方兵種表為準）。
倍速：單兵速度表是 1 倍速值；server_speed 只是簡單相乘，官方對倍速服部隊速度另有換算（tribe_data 檔頭 ✗），
  本專案固定 1 倍速，不受影響；換倍速服前要先實測，且一律以確認頁的單程秒數為準（舊版安全原則）。
"""
from typing import Dict, List, Mapping, Optional, Sequence

from ..common import geo, tribe_data
from ..common.decisions import HideCandidate
from ..common.models import HideContext

__all__ = ["ESCAPE_UNITS", "unit_speeds", "unit_attacks", "slowest_speed", "plan_at_speed", "plan", "recommend"]

# 可拿來避難的兵種（見檔頭說明）。英雄（hero）永遠不在內。
ESCAPE_UNITS = tuple(f"u{i}" for i in range(1, 7))


def unit_speeds(tribe: str) -> Dict[str, int]:
    """該族可避難兵種的速度（格／時，1 倍速）；沒有速度資料的兵種不列。tribe 未知丟 ValidationError。"""
    spec = tribe_data.get_tribe(tribe)
    return {u.key: u.speed for u in spec.units if u.key in ESCAPE_UNITS and u.speed is not None}


def unit_attacks(tribe: str) -> Dict[str, int]:
    """該族可避難兵種的單兵攻擊力；沒有資料（None）的兵種不列（hide_decide 算 0，保守）。"""
    spec = tribe_data.get_tribe(tribe)
    return {u.key: u.attack for u in spec.units if u.key in ESCAPE_UNITS and u.attack is not None}


def slowest_speed(tribe: str, units: Mapping[str, int]) -> Optional[int]:
    """派出兵力中最慢的速度（部隊一起走取最慢）。數量為 0 的鍵忽略；沒有兵、含英雄或速度表沒有的兵種 → None。"""
    speeds = unit_speeds(tribe)
    keys = [k for k, n in units.items() if n]
    if not keys or any(k not in speeds for k in keys):
        return None
    return min(speeds[k] for k in keys)


def plan_at_speed(ctx: HideContext, speed: float, now_ts: int, arrivals_ts: Sequence[int], *,
                  map_half: int, margin: int = 30) -> List[HideCandidate]:
    """以指定速度（格／時，已含倍速）算每個候選綠洲。回傳依 (距離, (x, y)) 排序；ctx.blocked（map id）內的綠洲略過。
    座標超出 ±map_half 的綠洲丟 GeoError（綠洲清單在 repo 邊界已驗證，這裡不吞）。"""
    arrivals = sorted(arrivals_ts)
    blocked = frozenset(ctx.blocked)
    home = (ctx.home_x, ctx.home_y)
    rows: List[HideCandidate] = []
    for o in ctx.oases:
        mid = geo.map_id(o.x, o.y, map_half)
        if mid in blocked:
            continue
        d = geo.distance(home, (o.x, o.y), map_half)
        one_way = geo.travel_seconds(d, speed)
        back = now_ts + 2 * one_way
        safe_until = back - margin
        rows.append(HideCandidate(
            x=o.x, y=o.y, kind=o.kind, distance=d, safe=o.safe, map_id=mid,
            one_way_s=one_way, back_ts=back,
            covered=tuple(a for a in arrivals if now_ts < a < safe_until),
            missed=tuple(a for a in arrivals if a >= safe_until)))
    rows.sort(key=lambda c: (c.distance, (c.x, c.y)))
    return rows


def plan(ctx: HideContext, units: Mapping[str, int], now_ts: int, arrivals_ts: Sequence[int], *,
         map_half: int, margin: int = 30, server_speed: float = 1) -> List[HideCandidate]:
    """依在家兵力（{'u1': n, …}，不含英雄）算候選。兵種速度未知（或沒有兵、含英雄）→ 空 list
    （hide_decide 會以 unknown_speed／no_units 擋下，不會用錯表派兵）。arrivals_ts 請給「全部未來來襲」，
    hide_decide 會自行取要撐過的範圍。"""
    speed = slowest_speed(ctx.tribe, units)
    if speed is None:
        return []
    return plan_at_speed(ctx, speed * server_speed, now_ts, arrivals_ts, map_half=map_half, margin=margin)


def recommend(candidates: Sequence[HideCandidate], include_unverified: bool = False) -> Optional[HideCandidate]:
    """最近的、能撐過全部來襲（missed 為空）的綠洲；include_unverified＝False 時 safe 必須是 True。沒有則 None。
    candidates 要是 plan 回傳的順序（距離近→遠）。"""
    for c in candidates:
        if not c.missed and (c.safe is True or include_unverified):
            return c
    return None
