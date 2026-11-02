#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/parsed.py（cm-09）
版本：v0.2（A2a-1）｜PlayerInfo 已定案（✓，A2a-1，依舊服 dorf1 樣本 S1a／S1b）；
      其餘結構仍為草案（✗）：Dorf1／Dorf2／PageFacts 待 A2a-2，HeroState／Adventure 等待 A2b
用途：解析結果結構（parsers 的輸出、domain 與 app 的輸入）：Dorf1、Dorf2、PlayerInfo、HeroState、
      Adventure、RallyOverview、MarketState、Oasis、TileSafety、PageFacts（D-18）。
依賴：cm-01（models；Oasis／Merchants／Transit 直接沿用，不重複定義）。
部署狀態：未部署（GA 前不 live）。

與舊 travian_models.py（✓ 已讀）的邊界轉換（由 A2a 的 parsers 負責，不帶進本層）：
  舊 Field（aid, gid, level, cost, secs, building, url）→ ResField：
    cost list → tuple；secs → build_time_s；building → under_construction（選擇器未驗證，所以 Optional：
    None＝讀不出來）；url=""→None。
  舊 Slot → BuildingSlot：gid=0（空地）→ None、name 空 → None；building 同上。
  舊 State → Dorf1：
    attacks=0 同時代表「沒有」與「不知道」→ incoming_attacks：0＝確定沒有、None＝未知；
    queue（剩餘秒數）＋queue_info（文字）兩個平行 list → QueueItem(remaining_s, info) 一個 tuple；
    cap 的長度與順序未確認（✗，A2a 讀 parse_dorf1 後定案；此處草案先用 cap_wh／cap_gr 對齊 C2）；
    attack_eta_s：沒有來襲＝None；movements 的元素結構未確認（✗），先用 Mapping。
讀不到的值用 None，不用 0／-1／"-"（§6.1）；解析失敗由 parsers 丟 ParseError，不回傳預設值。

本檔結構沒有 schema 規格（還不是契約）；測試與 golden 用 models.to_plain() 轉純資料。
"""
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .models import Merchants, Oasis, Res4, Transit

__all__ = [
    "Oasis", "ResField", "QueueItem", "Dorf1", "BuildingSlot", "Dorf2", "PlayerInfo", "HeroState",
    "Adventure", "RallyOverview", "MarketState", "TileSafety", "PageFacts",
]


# ---------------------------------------------------------------- dorf1（資源田頁）
@dataclass(frozen=True)
class ResField:
    aid: int
    gid: int                                    # 1 木 2 磚 3 鐵 4 穀
    level: int
    cost: Optional[Res4]                        # 升到下一級；木、磚、鐵、穀
    build_time_s: Optional[int]
    under_construction: Optional[bool]          # ✗ 選擇器未驗證
    url: Optional[str]                          # 已知的興建／擴建網址；None＝呼叫端自己找


@dataclass(frozen=True)
class QueueItem:
    remaining_s: int
    info: str                                   # 例「農場 等級 1」


@dataclass(frozen=True)
class Dorf1:
    stock: Res4
    prod: Res4
    cap_wh: int                                 # ✗ 舊 cap 長度順序待 A2a
    cap_gr: int
    free_crop: int
    fields: Tuple[ResField, ...]
    queue: Tuple[QueueItem, ...]
    incoming_attacks: Optional[int]
    attack_eta_s: Optional[int]
    movements: Tuple[Mapping[str, Any], ...]    # ✗ 元素結構待 A2a
    protection_s: Optional[int]
    plus_s: Optional[int]


# ---------------------------------------------------------------- dorf2（村莊中心）
@dataclass(frozen=True)
class BuildingSlot:
    aid: int
    gid: Optional[int]                          # None＝空地（舊 gid=0）
    level: int
    name: Optional[str]
    under_construction: Optional[bool]          # ✗ 選擇器未驗證


@dataclass(frozen=True)
class Dorf2:
    slots: Tuple[BuildingSlot, ...]


# ---------------------------------------------------------------- 玩家／英雄／冒險
@dataclass(frozen=True)
class PlayerInfo:
    """玩家資訊（A2a-1 定案 ✓）。來源是頁內 `viewData.ownPlayer`，dorf1、dorf2 皆含（舊服樣本 ✓）。
    tribe_id＝tribeId；plus_active＝goldFeatures.travianPlus.isActive（人工在遊戲內開關，有開就用；系統不購買）；
    cp_have／cp_need／cp_per_day／village_slots_used／village_slots_max＝culturalPointsOverview 的
    cpProducedForNextSlot／cpNeededForNextSlot／cpProductionTotal／usedSlots／maxControllableVillages。
    讀不到＝None；cp_* 與 village_slots_* 五欄同進同出（任一缺漏，五欄全為 None）。"""
    tribe_id: Optional[int]
    plus_active: Optional[bool]
    cp_have: Optional[int]
    cp_need: Optional[int]
    cp_per_day: Optional[int]
    village_slots_used: Optional[int]
    village_slots_max: Optional[int]


@dataclass(frozen=True)
class HeroState:
    """✗ travian_hero.py 尚未讀（△），欄位為最小猜想，A2b／A3c 定案。"""
    alive: Optional[bool]
    health_pct: Optional[int]
    home_did: Optional[int]
    at_home: Optional[bool]


@dataclass(frozen=True)
class Adventure:
    """✗ 同上。"""
    adv_id: Optional[int]
    x: Optional[int]
    y: Optional[int]
    danger: Optional[str]
    duration_s: Optional[int]


# ---------------------------------------------------------------- 集結點／市場／地圖
@dataclass(frozen=True)
class RallyOverview:
    units_home: Optional[Dict[str, int]]        # 兵種鍵待 D-21（✗）
    units_away: Optional[Dict[str, int]]
    incoming_attacks: Optional[int]
    movements: Tuple[Mapping[str, Any], ...]    # ✗


@dataclass(frozen=True)
class MarketState:
    merchants: Optional[Merchants]              # 市場 0 級為 None
    incoming: Tuple[Transit, ...]
    outgoing: Tuple[Transit, ...]


@dataclass(frozen=True)
class TileSafety:
    x: int
    y: int
    safe: Optional[bool]                        # 未驗證 None
    reason: Optional[str]


# ---------------------------------------------------------------- 頁面事實（D-18）
@dataclass(frozen=True)
class PageFacts:
    """供 server_profile.verify_against_page 與 parsers 用。全部 Optional：頁面讀不到就是 None。
    欄位語意為草案（✗，A2b 對照 S9 樣本定案；D-18 全文不在本切片內，只照 cm-09 卡片列的項目建）。"""
    tz_name: Optional[str]                      # Travian.Game.timeZone（IANA）
    tz_offset_s: Optional[int]                  # 伺服器相對 UTC 的位移秒數（✗ 語意待 A2b）
    lang: Optional[str]                         # <html lang>
    gpack: Optional[str]                        # 頁面 gpack 版號，例 '678.2'
    tribe_id: Optional[int]
    server_ts_utc: Optional[str]                # 頁面時間戳記，已轉 UTC 字串（C 契約格式）
    first_did: Optional[int]                    # 首個 d= 連結的村 id
    first_x: Optional[int]
    first_y: Optional[int]
