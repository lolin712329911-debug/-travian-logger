#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/game_rules.py（cm-12）
版本：v0.1（A1b）
用途：非種族的版本／倍速規則表（文化點門檻、倍速係數、資源田等級上限、拓荒條件、新手保護）。純資料與查表函式。
依賴：cm-01（models，為了 ServerProfile 與 ValidationError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  cp_required(n_villages, profile)  → 擁有 n 個村莊所需的累計文化點（int）
  speed_rules(profile)              → SpeedRules（產量倍率、建造／訓練時間除數、部隊速度倍率、開局文化點、保護天數）
  resource_field_cap(is_capital)    → 資源田等級上限（非首都 10；首都 None＝沒有可靠資料，呼叫端不得當成無限）
  settle_requirements()             → SettleRequirements（拓荒者數量、資源、擴張槽來源）
  default_protection_days(profile)  → 新手保護天數：profile.protection_days 有填用它，否則用官方基本天數（未知倍速 None）
  MAX_NON_CAPITAL_FIELD_LEVEL       → 10
  RESOURCE_FIELD_PRODUCTION_1X      → △ 只留資料，不提供函式（見下）

只支援官方列出的倍速 1／2／3／5／10（CP_TABLE_SPEEDS）；其他倍速丟 ValidationError，不內插、不猜。

證據標記
  ✓ 官方 Travian: Legends 說明中心（support.travian.com，倍速 1、2、3、5、10）：
    「Culture Points (CP)」：文化點表，村數 1～50；欄位「Villages (settlement slots)」＝擁有的村莊數
      （第 2 村、1 倍速＝2000）。寄出拓荒者時與抵達時都要夠。
    「Game Versions and Speed」：開局文化點 500／250／167／100／50；新手保護基本天數 5／3／3／2／1
      （另有可選延長 3／3／3／2／1 天，不併入基本天數）；資源產量乘倍速；建造與訓練時間除以倍速；
      部隊速度 x2、x3、x5 乘 2、x10 乘 4（不等於倍速，所以 scale_speed 不能一律拿來換算部隊速度）。
    「Guide: Resources Explained」：一般村莊資源田最高 10 級；特殊世界的「城市」12 級。首都的上限沒查到官方數字
      → None（舊 travian_const 註解寫「首都無限」沒有出處，不採用）。
    「Settling villages」：3 個拓荒者、各 750 木磚鐵穀、文化點、空擴張槽。
    「Expansion Slots」：住所 2 個擴張槽，皇宮與指揮中心各 3 個。
  △ 各等級開出第幾個槽：住所 10 級第一槽、20 級第二槽（第三方 wiki）；皇宮 10／15／20 ✗（舊指南）；
    指揮中心級數 ✗ 沒有資料。
  ✗ 商人在倍速服的換算（官方表沒說明，見 tribe_data.merchant_info）。
  △ 資源田產量表：舊 travian_const 的表（0～10 級＝0,5,9,15,22,33,50,70,100,145,200），A1b 合併時重新查證：
    Kingdoms 說明頁（含 11 級＝280）、舊社群指南各級數字與它一致，單位是「每塊田每小時的 1 倍速產量」；
    舊註解說「累積」是錯的。但官方 Legends 文章沒有逐級數字，也還沒用 S9 樣本核對，所以只留資料不提供函式；
    核對後才用，使用時乘 speed_rules(profile).production_factor。11 級以上（僅首都）沒有 Legends 來源，不放表。
來源：舊 travian_const.py 的 RESOURCE_FIELD_PRODUCTION、MAX_NON_CAPITAL_FIELD_LEVEL（✓ 已讀）。
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .models import ServerProfile, ValidationError

__all__ = ["MAX_NON_CAPITAL_FIELD_LEVEL", "RESOURCE_FIELD_PRODUCTION_1X", "CP_TABLE_SPEEDS", "SpeedRules",
           "SlotSource", "SettleRequirements", "cp_required", "speed_rules", "resource_field_cap",
           "settle_requirements", "default_protection_days"]

MAX_NON_CAPITAL_FIELD_LEVEL = 10

# ✗ 未核對（見檔頭）；1 倍速、無任何加成的每小時產量。目前沒有任何函式使用它。
RESOURCE_FIELD_PRODUCTION_1X = {0: 0, 1: 5, 2: 9, 3: 15, 4: 22, 5: 33,
                                6: 50, 7: 70, 8: 100, 9: 145, 10: 200}

# ---------------------------------------------------------------- 文化點表（第 i 個元素＝擁有 i+1 個村莊）
_CP_X1 = (
    0, 2000, 8000, 20000, 39000, 65000, 99000, 141000, 191000, 251000,
    319000, 397000, 486000, 584000, 692000, 811000, 941000, 1082000, 1234000, 1397000,
    1572000, 1759000, 1957000, 2168000, 2391000, 2627000, 2874000, 3135000, 3409000, 3695000,
    3995000, 4308000, 4634000, 4974000, 5327000, 5695000, 6076000, 6471000, 6881000, 7304000,
    7742000, 8195000, 8662000, 9143000, 9640000, 10151000, 10677000, 11219000, 11775000, 12347000)
_CP_X2 = (
    0, 800, 3900, 10000, 19400, 32400, 49300, 70300, 95500, 125300,
    159600, 198700, 242800, 291800, 346100, 405600, 470500, 540900, 616900, 698600,
    786100, 879400, 978700, 1084100, 1195600, 1313300, 1437200, 1567600, 1704300, 1847600,
    1997400, 2153900, 2317000, 2487000, 2663700, 2847400, 3038000, 3235600, 3440300, 3652100,
    3871000, 4097300, 4330800, 4571600, 4819800, 5075500, 5338700, 5609400, 5887700, 6173600)
_CP_X3 = (
    0, 500, 2600, 6700, 12900, 21600, 32900, 46900, 63700, 83500,
    106400, 132500, 161900, 194600, 230700, 270400, 313700, 360600, 411300, 465700,
    524000, 586300, 652500, 722700, 797000, 875500, 958200, 1045000, 1136200, 1231700,
    1331600, 1435900, 1544700, 1658000, 1775800, 1898300, 2025300, 2157100, 2293500, 2434700,
    2580700, 2731500, 2887200, 3047700, 3213200, 3383700, 3559100, 3739600, 3925100, 4115800)
_CP_X5 = (
    0, 300, 1600, 4000, 7800, 13000, 19700, 28100, 38200, 50100,
    63800, 79500, 97100, 116700, 138400, 162200, 188200, 216400, 246800, 279400,
    314400, 351800, 391500, 433600, 478200, 525300, 574900, 627000, 681700, 739000,
    799000, 861600, 926800, 994800, 1065500, 1139000, 1215200, 1294200, 1376100, 1460800,
    1548400, 1638900, 1732300, 1828600, 1927900, 2030200, 2135500, 2243800, 2355100, 2469500)
_CP_X10 = (
    0, 200, 800, 2000, 3900, 6500, 9900, 14100, 19100, 25100,
    31900, 39700, 48600, 58400, 69200, 81100, 94100, 108200, 123400, 139700,
    157200, 175900, 195700, 216800, 239100, 262700, 287400, 313500, 340900, 369500,
    399500, 430800, 463400, 497400, 532700, 569500, 607600, 647100, 688100, 730400,
    774200, 819500, 866200, 914300, 964000, 1015100, 1067700, 1121900, 1177500, 1234700)

_CP_TABLE: Dict[int, Tuple[int, ...]] = {1: _CP_X1, 2: _CP_X2, 3: _CP_X3, 5: _CP_X5, 10: _CP_X10}
CP_TABLE_SPEEDS = tuple(sorted(_CP_TABLE))
_CP_MAX_VILLAGES = 50


def cp_required(n_villages: int, profile: ServerProfile) -> int:
    """擁有 n_villages 個村莊（含新村）所需的累計文化點。第 1 村＝0；第 2 村、1 倍速＝2000。

    n_villages 需為 1～50；profile.speed 需是官方表列出的倍速（見 CP_TABLE_SPEEDS），
    否則丟 ValidationError（rule=range／unsupported_speed），不內插、不猜。
    """
    if isinstance(n_villages, bool) or not isinstance(n_villages, int) \
            or not 1 <= n_villages <= _CP_MAX_VILLAGES:
        raise ValidationError("CPTable", "n_villages", n_villages, "range")
    table = _CP_TABLE.get(profile.speed)
    if table is None:
        raise ValidationError("CPTable", "speed", profile.speed, "unsupported_speed")
    return table[n_villages - 1]


# ---------------------------------------------------------------- 倍速係數（✓ 官方「Game Versions and Speed」）
@dataclass(frozen=True)
class SpeedRules:
    speed: int
    production_factor: int            # 資源產量 ×
    build_divisor: int                # 建造時間 ÷
    train_divisor: int                # 訓練時間 ÷
    troop_speed_factor: int           # 部隊速度 ×（不等於倍速：x3、x5 乘 2，x10 乘 4）
    start_cp: int                     # 開局文化點
    protection_days: int              # 新手保護基本天數
    protection_extension_days: int    # 可選延長天數（不含在 protection_days 內）


_SPEED_RULES: Dict[int, SpeedRules] = {
    1: SpeedRules(1, 1, 1, 1, 1, 500, 5, 3),
    2: SpeedRules(2, 2, 2, 2, 2, 250, 3, 3),
    3: SpeedRules(3, 3, 3, 3, 2, 167, 3, 3),
    5: SpeedRules(5, 5, 5, 5, 2, 100, 2, 2),
    10: SpeedRules(10, 10, 10, 10, 4, 50, 1, 1),
}


def speed_rules(profile: ServerProfile) -> SpeedRules:
    """依 profile.speed 取倍速係數。不在官方表的倍速丟 ValidationError(rule=unsupported_speed)。"""
    rules = _SPEED_RULES.get(profile.speed)
    if rules is None:
        raise ValidationError("SpeedRules", "speed", profile.speed, "unsupported_speed")
    return rules


def resource_field_cap(is_capital: bool) -> Optional[int]:
    """資源田等級上限。非首都 10（✓ 官方）；首都沒有可靠資料 → None（呼叫端不得當成「無限」）。"""
    if not isinstance(is_capital, bool):
        raise TypeError("is_capital 需為 bool")
    return None if is_capital else MAX_NON_CAPITAL_FIELD_LEVEL


# ---------------------------------------------------------------- 拓荒
@dataclass(frozen=True)
class SlotSource:
    """提供擴張槽的建築。slots＝槽數（✓ 官方「Expansion Slots」）；
    levels＝每個槽需要的建築等級（空 tuple＝沒有資料 ✗；levels_verified 一律 False：△／✗）。"""
    gid: int
    slots: int
    levels: Tuple[int, ...]
    levels_verified: bool


@dataclass(frozen=True)
class SettleRequirements:
    settlers: int
    cost_each: Tuple[int, int, int, int]        # 出發時要有的資源，木、磚、鐵、穀
    cp_checked_at: Tuple[str, ...]              # 'send'（寄出）與 'arrive'（抵達）都要有足夠文化點
    slot_sources: Tuple[SlotSource, ...]


_SETTLE = SettleRequirements(
    settlers=3,
    cost_each=(750, 750, 750, 750),
    cp_checked_at=("send", "arrive"),
    slot_sources=(
        SlotSource(gid=25, slots=2, levels=(10, 20), levels_verified=False),      # 住所（gid 見 constants.GID_NAMES）△
        SlotSource(gid=26, slots=3, levels=(10, 15, 20), levels_verified=False),  # 皇宮 ✗
        SlotSource(gid=44, slots=3, levels=(), levels_verified=False),            # 指揮中心：級數沒有資料 ✗
    ),
)


def settle_requirements() -> SettleRequirements:
    """拓荒條件（✓ 官方：3 拓荒者、各 750、文化點、空擴張槽與槽數；各槽的建築等級 △／✗，見檔頭）。"""
    return _SETTLE


def default_protection_days(profile: ServerProfile) -> Optional[int]:
    """新手保護天數：Config／profile 有填（server_protection_days）就用它；沒填用官方基本天數
    （x1＝5、x2／x3＝3、x5＝2、x10＝1；不含可選延長，見 SpeedRules）；倍速不在官方表回 None（未知）。"""
    if profile.protection_days is not None:
        return profile.protection_days
    rules = _SPEED_RULES.get(profile.speed)
    return None if rules is None else rules.protection_days
