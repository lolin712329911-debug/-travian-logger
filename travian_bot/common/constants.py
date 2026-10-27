#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/constants.py（cm-03）
版本：v0.1（A1a-1）
用途：不會在執行時被改動的常數與純查表函式。不放邏輯、不 import 專案其他模組。
依賴：無（只用標準庫 re）。
部署狀態：未部署（GA 前不 live）。

來源：舊 travian_const.py（✓ 已讀）沿用並拆分——
  留在這裡：GID_NAMES（補 29、30、36、44、48）、RES_NAMES、BUILD_CATEGORIES、
            FREE_SLOT_RANGE、BIDI、BUILDING_GIDS、gid_name()
  搬去別處（本檔不保留，交接區塊有記）：
    DEFAULT_TARGET_BUILDING_LEVEL → BuildSettings 預設（A1a-2 cm-01）
    RESOURCE_FIELD_PRODUCTION、MAX_NON_CAPITAL_FIELD_LEVEL → cm-12（game_rules）
    TRIBE_NAMES → cm-06（tribe_data）
    ROMAN_TRIBE_ID → 不保留
證據標記：標 ✗ 者沒有樣本或讀碼佐證，使用前要用遊戲頁面核對（見 UNVERIFIED_GIDS）。
"""
import re

# 頁面數字外面包的方向控制字元
BIDI = re.compile(r"[‪-‮⁦-⁩]")

# ---------------- 資源索引（順序固定：木、磚、鐵、穀；§6.1）----------------
RES_WOOD, RES_CLAY, RES_IRON, RES_CROP = 0, 1, 2, 3
RES_COUNT = 4
RES_KEYS = ("wood", "clay", "iron", "crop")           # Sheet 欄名後綴：_wood／_clay／_iron／_crop
RES_NAMES = ("木材", "磚塊", "鋼鐵", "穀物")           # 顯示用（舊檔為 list，這裡改 tuple 防誤改）

# ---------------- gid 表 ----------------
# 村莊中心建築（非資源田）。舊檔註解：只驗證過倉庫／糧倉的 build.php 頁面結構
# （成本／時間寫在正文而非 title）。擴充前要先用樣本驗證格式一致。
BUILDING_GIDS = {10: "倉庫", 11: "糧倉"}

# 給 Sheet / log 顯示用的中文名稱。沒列到的 gid 會顯示成「建築(gid N)」。
GID_NAMES = {
    1: "伐木場", 2: "泥坑", 3: "鐵礦場", 4: "農場",
    5: "鋸木廠", 6: "磚廠", 7: "鋼鐵鑄造廠", 8: "麵粉廠", 9: "麵包店",
    10: "倉庫", 11: "糧倉", 13: "盔甲廠", 14: "競技場",
    15: "村莊大樓", 16: "集結點", 17: "市場", 18: "大使館",
    19: "兵營", 20: "馬廄", 21: "工場", 22: "研究院", 23: "山洞",
    24: "城鎮廳", 25: "行宮", 26: "皇宮", 27: "寶物庫", 28: "交易所",
    29: "大兵營",      # ✗ 本版新增，名稱未用樣本核對
    30: "大馬廄",      # ✗ 本版新增，名稱未用樣本核對
    34: "石匠鋪",
    36: "陷阱",        # 卡片明列「36 陷阱」（高盧；§4.2 cm-03）
    37: "英雄宅", 38: "大倉庫", 39: "大穀倉",
    42: "石墻",
    44: "指揮中心",    # ✗ 本版新增，名稱未用樣本核對
    45: "供水系統", 46: "醫院",
    48: "大工場",      # ✗ 本版新增，gid 與名稱皆未核對
}

# 本版新增、尚未用樣本或遊戲頁面核對的 gid。程式邏輯不得依賴這些名稱做判斷，
# 只能當顯示用；A0b／SAMP 取得真實樣本後核對並移出此集合。
UNVERIFIED_GIDS = frozenset({29, 30, 44, 48})


def gid_name(gid) -> str:
    return GID_NAMES.get(gid, f"建築(gid {gid})")


# 資源田 gid（1～4）與 aid 範圍（BuildTarget：aid 1～18 資源田，19～40 建築；§6.2）
RESOURCE_FIELD_GIDS = (1, 2, 3, 4)
RESOURCE_FIELD_AID_RANGE = (1, 18)
BUILDING_AID_RANGE = (19, 40)

# 村莊中心可以蓋新建築的空地範圍。39 固定是集結點、40 固定是城牆，不拿來蓋別的。
FREE_SLOT_RANGE = (19, 38)

# 空地 build.php 的 &category=1/2/3 三個分頁（舊樣本 build1~3 已確認）
BUILD_CATEGORIES = {1: "基礎", 2: "軍事", 3: "資源"}

# ---------------- 頁面路徑常數 ----------------
# 只收舊檔註解與現行流程確實出現過的三個；其他頁面（地圖、報告、市場表單等）
# 等各 parsers／actions WP 讀碼或有樣本後再補（✗ 未驗證，不憑記憶加）。
PATH_DORF1 = "/dorf1.php"
PATH_DORF2 = "/dorf2.php"
PATH_BUILD = "/build.php"

# ---------------- 動作名稱常數（Actions.action，C5：str ≤ 40）----------------
# 只收卡片與契約明列的三個；建造／躲兵等既有動作名稱待 A4b 讀 log_action 回填（✗）。
ACTION_TRANSFER_RES = "調度資源"
ACTION_TROOP_MOVE = "運兵"
ACTION_VILLAGE_SKIP = "村莊跳過"   # C8：village_lock 不符時寫入

ACTION_NAMES = frozenset({ACTION_TRANSFER_RES, ACTION_TROOP_MOVE, ACTION_VILLAGE_SKIP})
