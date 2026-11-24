#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/domain/adventure.py（dm-06）
版本：v0.2（修正 difficulty_bonus 死結；skip_on_incoming 預設改 False）｜v0.1（A3b）
用途：decide_adventure(hero, adventures, settings, incoming) → AdventureDecision。
      英雄冒險：該不該出發、選哪一個（adv_id＝Adventure.number；ac-05 click_adventure 吃 Adventure 物件，
      stage 用編號從同一份清單取出）。純函式。
依賴：cm-02（AdventureDecision）、cm-09（HeroState、Adventure）。
部署狀態：未部署（GA 前不 live）。

來源 travian_hero.py hero-v1.4 的 plan_adventure（✓ 已讀）。套用（小調整）：
  1. 舊的 AdventureRow／rows_match_json 不在 domain：表格與 JSON 的核對已由 ps-05 parse_adventures 做（不一致丟
     ParseError，✓ hero.py 已讀）；難度圖示與按鈕狀態已合併進 Adventure.icon／clickable。
  2. 在家判斷（A5a，與 ac-05 一致）：status 50／9 skip；at_home 必須為 True；不可有 adventure_no／arrival_in_s；
     status 只接受 100 或 None，其他值一律 skip。在家時 status 碼與 in_village_did 的結構沒有新服樣本 ✗，所以不要求 in_village_did。
  3. 體力、來襲數由參數／HeroState 給（HeroState.health_pct）。
  4. 沒有 icon（表格沒渲染）＝不能選，整體 skip。
  5. 狀態碼 50／9／100 在本檔寫死（舊 travian_hero 同；cm-03 的 HERO_STATUS 鍵名未讀 ✗，A6a2 可改引用）。

v0.2 修改：
  A. difficulty_bonus（遊戲回報「下一次普通冒險會被升成困難」）：v0.1 為真就無條件 skip，完全不看 settings.allowed，
     英雄不出門旗標就不會變，造成死結。改成算完 allowed 之後才判斷：只有 hard 不被允許（設定未開，或體力 ≤ hard_min_health）
     時才 skip；hard 被允許就照常選。
  B. skip_on_incoming 預設 True → False（有來襲也照常出發）。注意：stage 的 _settings 另有自己的預設
     （cfg.get("hero_skip_on_incoming", True)），要讓它生效須改 stage 的預設或設定檔 hero_skip_on_incoming。
"""
from dataclasses import dataclass
from typing import FrozenSet, Optional, Sequence

from ..common.decisions import AdventureDecision
from ..common.parsed import Adventure, HeroState

__all__ = ["AdventureSettings", "decide_adventure"]

_STATUS_HOME = 100
_STATUS_GOING = 50
_STATUS_RETURNING = 9


@dataclass(frozen=True)
class AdventureSettings:
    min_health: int = 45                              # Config hero_min_health：體力 ≤ 此值不出發
    hard_min_health: int = 60                         # Config hero_hard_min_health：體力 ≤ 此值不選 hard
    allowed: FrozenSet[str] = frozenset({"normal"})   # Config hero_allowed（normal、hard）
    skip_on_incoming: bool = False                    # Config hero_skip_on_incoming（v0.2：預設改 False）


def _skip(reason: str) -> AdventureDecision:
    return AdventureDecision(False, None, reason)


def decide_adventure(
    hero: HeroState,
    adventures: Sequence[Adventure],
    settings: AdventureSettings = AdventureSettings(),
    incoming: Optional[int] = None,
) -> AdventureDecision:
    if hero.status == _STATUS_GOING:
        return _skip(f"已出發（冒險 #{hero.adventure_no}，剩 {hero.arrival_in_s} 秒抵達）")
    if hero.status == _STATUS_RETURNING:
        return _skip(f"返回中，還剩 {hero.arrival_in_s} 秒")
    if hero.status is not None and hero.status != _STATUS_HOME:
        return _skip(f"未知狀態碼 {hero.status}")
    if hero.at_home is not True:
        return _skip("英雄不在家或讀不到在家狀態")
    if hero.adventure_no is not None or hero.arrival_in_s is not None:
        return _skip(f"已有進行中的冒險 #{hero.adventure_no}")
    if hero.regenerating:
        return _skip("英雄復活中")

    health = hero.health_pct
    if health is None:
        return _skip("讀不到體力")
    if health <= settings.min_health:
        return _skip(f"體力 {health}% ≤ {settings.min_health}")

    if settings.skip_on_incoming:
        if incoming is None:
            return _skip("來襲數未知")
        if incoming > 0:
            return _skip(f"有來襲 {incoming} 筆")

    if not adventures:
        return _skip("沒有可選的冒險")
    if all(a.icon is None for a in adventures):
        return _skip("冒險表格沒有渲染（讀不到難度圖示），不能選")

    allowed = set(settings.allowed)
    if health <= settings.hard_min_health:
        allowed.discard("hard")

    # v0.2：difficulty_bonus 改在 allowed 算好之後判斷。下一次普通冒險會被升成困難，
    # 只有 hard 不被允許（設定未開或體力不夠）才 skip。
    if hero.difficulty_bonus and "hard" not in allowed:
        return _skip("下一次普通冒險會提高為困難（difficulty bonus），但 hard 未允許或體力 "
                     f"{health}% ≤ {settings.hard_min_health}")

    candidates = [(0 if a.icon == "hard" else 1, a.duration_s, a.number)
                  for a in adventures if a.icon in allowed and a.clickable is True]
    if not candidates:
        return _skip(f"沒有符合難度 {sorted(allowed)} 且可按的冒險")
    _, dur, number = min(candidates)     # hard 優先（體力不夠時已排除）；同類取去程最短；同時間取編號小
    icon = next(a.icon for a in adventures if a.number == number)
    return AdventureDecision(True, number, f"冒險 #{number}（{icon}，去程 {dur // 60} 分）")
