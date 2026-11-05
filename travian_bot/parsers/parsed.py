#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/parsed.py（cm-09）
版本：v0.4（A2a-2b）｜BuildCondition／BuildOption／UpgradeCost 於 A2a-2b 定案（✓ 依 S10 一份、S11 四份樣本，見各類說明）；
      v0.3（A2a-2a）：PlayerInfo 已定案（✓，A2a-1）；Dorf1／Dorf2／PageFacts 於 A2a-2a 定案
      （✓ 依舊服樣本 S1a／S1b、S12a／S12b；PageFacts 欄位語意仍待 A2b 對照 S9，見該類說明）；
      其餘結構仍為草案（✗）：HeroState／Adventure 等待 A2b
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
    cap：maxStorage 的 l1～l4＝木／磚／鐵／糧（✓）；木磚鐵共用倉庫容量，三者不相等視為頁面異常（ParseError），
    所以 Dorf1 只留 cap_wh／cap_gr（對齊 C2）；
    attack_eta_s：沒有來襲＝None；movements 的元素結構於 A2a-2a 定案（見 Dorf1）。
讀不到的值用 None，不用 0／-1／"-"（§6.1）；解析失敗由 parsers 丟 ParseError，不回傳預設值。

本檔結構沒有 schema 規格（還不是契約）；測試與 golden 用 models.to_plain() 轉純資料。
"""
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .models import Merchants, Oasis, Res4, Transit

__all__ = [
    "Oasis", "ResField", "QueueItem", "Dorf1", "BuildingSlot", "Dorf2", "PlayerInfo", "HeroState",
    "Adventure", "BuildCondition", "BuildOption", "UpgradeCost", "RallyOverview", "MarketState", "TileSafety", "PageVillage", "PageFacts",
]


# ---------------------------------------------------------------- dorf1（資源田頁）
@dataclass(frozen=True)
class ResField:
    aid: int
    gid: int                                    # 1 木 2 磚 3 鐵 4 穀
    level: int
    cost: Optional[Res4]                        # 升到下一級；木、磚、鐵、穀
    build_time_s: Optional[int]
    under_construction: Optional[bool]          # ✓ class `underConstruction`（A2a-2a 用 S1b 驗證）；parsers 一律回 bool
    url: Optional[str]                          # 已知的興建／擴建網址；parse_dorf1 不填（None）：頁面上的連結只是
                                                # build.php?id=N，升級網址由 ps-03 find_upgrade_url 從建築頁取


@dataclass(frozen=True)
class QueueItem:
    remaining_s: int
    info: Optional[str]                         # 頁面顯示文字「名稱 等級 N」（只供顯示與記錄，不拿來做判斷）；讀不到＝None


@dataclass(frozen=True)
class Dorf1:
    stock: Res4
    prod: Res4
    cap_wh: int                                 # maxStorage l1～l3（木磚鐵共用，三者須相等）
    cap_gr: int                                 # maxStorage l4
    free_crop: int                              # production l5＝可用穀物（l4＝淨產量，見 stock／prod 的第 4 格）
    fields: Tuple[ResField, ...]
    queue: Tuple[QueueItem, ...]
    incoming_attacks: Optional[int]             # 目前這個村的來襲數（viewData.villageList 中作用中村那筆）；
                                                # 0＝確定沒有、None＝讀不到。注意：不是帳號全部村的總和
    attack_eta_s: Optional[int]                 # movements 中 kind＝attack 的最小剩餘秒數；沒有＝None
    movements: Tuple[Mapping[str, Any], ...]    # 每筆 {kind, count, seconds, label}：
                                                #   kind：attack（img.att1）／reinforcement（img.def1）／adventure（img.hero_on_adventure）；
                                                #   其餘未見 class 原樣保留（無 class＝'unknown'）；att1／def1 只憑舊註解，待 S7
                                                #   count：label 開頭的整數（語意依 kind 而異，adventure 為冒險數）或 None
                                                #   seconds：span.timer 的 value 或 None；label：頁面文字（只供記錄）
    protection_s: Optional[int]                 # #sidebarBoxInfobox 的「新手保護」倒數秒數；舊服樣本沒有該區塊＝None
                                                # （✗ 新手保護字樣待 S9 找結構選擇器，v0.31）
    plus_s: Optional[int]                       # 同區塊的 Plus 剩餘秒數；舊服樣本 Plus 啟用但無此區塊＝None，行為只依 PlayerInfo.plus_active


# ---------------------------------------------------------------- dorf2（村莊中心）
@dataclass(frozen=True)
class BuildingSlot:
    aid: int
    gid: Optional[int]                          # None＝空地（舊 gid=0）
    level: int
    name: Optional[str]                         # data-name（頁面語言的顯示文字，只供記錄；身分以 gid 為準）
    under_construction: Optional[bool]          # ✓ class `underConstruction`（A2a-2a 用 S12a／S12b 與施工佇列對照驗證）；parsers 一律回 bool


@dataclass(frozen=True)
class Dorf2:
    """全部建築位（aid 19～40，共 22 個，依 aid 排序）。城牆（aid 40）等級大於 0 時頁面有 top／bottom 兩個節點，
    parsers 取有 data-building-id 者，所以每個 aid 只出現一次。"""
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


# ---------------------------------------------------------------- 建築頁（build.php）
@dataclass(frozen=True)
class BuildCondition:
    """空地建造頁（gid0）上一棟建築的前置條件（✓ S10：`span.buildingCondition`）。
    gid＝onclick 的 `open('building', N)`；level＝要求等級（取 span 內數字；被劃掉的禁止項沒有等級＝None）；
    met＝class 沒有 `error`；current＝未達成時 title 內的目前等級（取數字，達成時 title 沒有數字＝None）；
    forbidden＝名稱被 line-through（「不能已經有這棟」，例：蓋皇宮前不能有行宮）。
    name 是頁面語言的顯示文字，只供記錄；判斷用 gid。"""
    gid: Optional[int]
    name: Optional[str]
    level: Optional[int]
    met: bool
    current: Optional[int]
    forbidden: bool


@dataclass(frozen=True)
class BuildOption:
    """空地建造頁的一棟可（或不可）蓋的建築（舊 `parse_build_options` 的 dict 的結構化版）。
    cost＝木、磚、鐵、穀（讀不全四格＝None，不給縮水清單）；穀物消耗（cropConsumptionBig）不算。
    build_time_s＝`div.section1` 的一般工期（section2＝看廣告加速，不取）；頁面沒顯示＝None（舊版是 0）。
    buildable＝有綠色、未 disabled、網址通過白名單的興建按鈕；url＝該網址，否則 None。
      佇列是否已滿無法從本頁判斷（✗，S10 沒有同時刻 dorf1；佇列滿時綠色按鈕消失只在 S11 的既有建築頁見過），
      所以 buildable＝False 不等於資源或條件不足：原因要看 resource_short／afford_in_s／conditions，都沒有＝未知。
    resource_short＝`.upgradeBlocked` 內有「交換資源」按鈕（資源不足的頁面表現）。
    exchange_disabled＝該按鈕是否 disabled；沒有按鈕＝None。（舊名 exceeds_storage 取消：S10／S11 中 disabled 與
      「成本合計大於庫存合計」吻合，與「成本超過容量」不符，那是推測。）
    afford_in_s＝`div.errorMessage` 內 `span.timer` 的 value（資源預計湊齊的剩餘秒數）；沒有＝None。
    conditions＝前置條件（只出現在還不能蓋的建築上）。"""
    gid: int
    name: Optional[str]
    cost: Optional[Res4]
    build_time_s: Optional[int]
    buildable: bool
    url: Optional[str]
    resource_short: bool
    exchange_disabled: Optional[bool]
    afford_in_s: Optional[int]
    conditions: Tuple[BuildCondition, ...]


@dataclass(frozen=True)
class UpgradeCost:
    """既有建築頁（build.php?id=<aid>，村莊中心建築）的升級成本（舊 `parse_building_cost` 的 (cost, secs)）。
    只讀 `div.upgradeBuilding` 區塊（研究院頁還有各兵種研究成本，標記相同，不能掃整頁）。
    欄位語意同 BuildOption 的同名欄位。cost 讀不全＝解析失敗，由 parsers 丟 ParseError（不回傳空 list）。"""
    cost: Res4
    build_time_s: Optional[int]
    resource_short: bool
    exchange_disabled: Optional[bool]
    afford_in_s: Optional[int]


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
class PageVillage:
    """viewData.ownPlayer.villageList 的一筆（只取 id 與座標；名稱不帶，完整清單用 parsers/village_list）。"""
    did: int
    x: int
    y: int


@dataclass(frozen=True)
class PageFacts:
    """供 server_profile.verify_against_page 與 parsers 用。全部 Optional：頁面讀不到就是 None，不丟 ParseError。
    A2a-2a 定案欄位與來源（✓ 舊服樣本 6 份 dorf1／dorf2）：
      tz_name＝Travian.Game.timeZone；tz_offset_s＝Travian.Game.timezoneOffsetToUTC 的原值；
      lang＝<html lang>；gpack＝CDN 路徑 /gpack/<版號>/；tribe_id＝viewData.ownPlayer.tribeId；
      server_ts＝Travian.Game.timestamp（epoch 秒，頁面產生時間；parsers 不格式化，需要字串由呼叫端經 serialize）；
      villages＝viewData.ownPlayer.villageList 各村 (did, x, y)，任何一筆讀不到則整個為 None（不給殘缺清單）。
    變動（相對 v0.2 草案）：server_ts_utc（字串）→ server_ts（epoch 秒；parsers 不得格式化時間）；
      first_did／first_x／first_y 移除（D-18 v0.30：執行期不讀 karte.php?d=）；新增 villages。
    ✗ 仍待 A2b 對照 S9：tz_offset_s 的單位（舊服 6 份樣本全為 0，無法判斷是秒還是小時）；hard／soft 分級。
    ⚠ 舊服 Asia 8 樣本：頁面時區為 Europe/London、offset 0，頁面顯示的完成時間與 UTC 一致（例：timestamp＋580 秒
      ＝00:48:06 UTC，頁面顯示「完成時間於 00:48」），不是台北時間；新服的 server_tz 以 S8／S9 為準。"""
    tz_name: Optional[str]
    tz_offset_s: Optional[int]
    lang: Optional[str]
    gpack: Optional[str]
    tribe_id: Optional[int]
    server_ts: Optional[int]
    villages: Optional[Tuple[PageVillage, ...]]
