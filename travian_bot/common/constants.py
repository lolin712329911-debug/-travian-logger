#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/constants.py（cm-03）
版本：v0.3（v0.65／v0.66：GID_NAMES 以台灣服語言包補齊，gid 11 改「穀倉」，新增 LANGPACK_ONLY_GIDS）｜v0.2（A2b：補 HERO_STATUS）｜v0.1（A1a-1）
用途：不會在執行時被改動的常數與純查表函式。不放邏輯、不 import 專案其他模組。
依賴：無（只用標準庫 re）。
部署狀態：未部署（GA 前不 live）。

來源：舊 travian_const.py（✓ 已讀）沿用並拆分——
  留在這裡：GID_NAMES（v0.1 補 29、30、36、44、48；v0.3 依台灣服語言包 allgemein.json 補齊到 49 筆，見下）、RES_NAMES、BUILD_CATEGORIES、
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
BUILDING_GIDS = {10: "倉庫", 11: "穀倉"}     # v0.3：11 由舊用語「糧倉」改為遊戲畫面的「穀倉」（v0.66）

# 給 Sheet / log 顯示用的中文名稱。沒列到的 gid 會顯示成「建築(gid N)」。
# v0.3：依台灣服繁中語言包 allgemein.json（鍵名 gid1～gid50）補齊，共 49 筆。
#   只供顯示（Sheet 的 name 欄、log），不可拿來在 parsers 做中文字面比對。
#   gid 13＝盔甲廠 ✓（使用者確認遊戲畫面）、gid 11＝穀倉 ✓（使用者確認遊戲翻譯；舊 bot 用「糧倉」，v0.66 起不再使用）。
#   語言包沒有 gid12；「Legends 把鐵匠鋪併入盔甲廠」只是整理者的推測、沒有樣本佐證 ✗。
#   plan_validate 以「gid 存在於 GID_NAMES」檢查 build_order，所以若實際遊戲有 gid 12 會被誤擋，
#   須用新伺服器的 Buildable 樣本確認。
GID_NAMES = {
    1: "伐木場",
    2: "泥坑",
    3: "鐵礦場",
    4: "農場",
    5: "鋸木廠",
    6: "磚廠",
    7: "鋼鐵鑄造廠",
    8: "麵粉廠",
    9: "麵包店",
    10: "倉庫",
    11: "穀倉",   # ✓ 遊戲翻譯（使用者確認）；舊 bot 用「糧倉」
    13: "盔甲廠",   # ✓ 使用者確認遊戲畫面
    14: "競技場",
    15: "村莊大樓",
    16: "集結點",
    17: "市場",
    18: "大使館",
    19: "兵營",
    20: "馬廄",
    21: "工場",
    22: "研究院",
    23: "山洞",
    24: "城鎮廳",
    25: "行宮",
    26: "皇宮",
    27: "寶物庫",
    28: "交易所",
    29: "大兵營",   # ✗ 名稱只有語言包，未用樣本核對
    30: "大馬廄",   # ✗ 名稱只有語言包，未用樣本核對
    31: "城牆",
    32: "土牆",
    33: "木牆",
    34: "石匠鋪",
    35: "釀酒廠",
    36: "陷阱機",   # 卡片明列「36 陷阱」（高盧；§4.2 cm-03）；語言包全名「陷阱機」
    37: "英雄宅",
    38: "大倉庫",
    39: "大穀倉",
    40: "世界奇觀",
    41: "放牧水槽",
    42: "石墻",
    43: "臨時的墻",
    44: "指揮中心",   # ✗ 名稱只有語言包，未用樣本核對
    45: "供水系統",
    46: "醫院",
    47: "防禦牆",
    48: "醫神神殿",   # ✗ 名稱只有語言包（v0.2 的「大工場」是猜測，已更正），未用樣本核對
    49: "港口",
    50: "障礙物",
}

# 本版新增、尚未用樣本或遊戲頁面核對的 gid。程式邏輯不得依賴這些名稱做判斷，
# 只能當顯示用；A0b／SAMP 取得真實樣本後核對並移出此集合。
# v0.3：語言包已提供 29、30、44、48 的名稱（48 與 v0.2 的猜測不同，已更正），但語言包不是實機畫面樣本，
#   所以仍留在此集合，等實機畫面確認後才移除。
UNVERIFIED_GIDS = frozenset({29, 30, 44, 48})

# v0.3：名稱只來自語言包（舊 travian_const.py 沒有、也沒有樣本佐證）的 gid；是 UNVERIFIED_GIDS 的超集。
# 純備忘用，程式不依賴；有樣本核對過的就從這裡移出。
LANGPACK_ONLY_GIDS = frozenset({29, 30, 31, 32, 33, 35, 36, 40, 41, 43, 44, 47, 48, 49, 50})


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

# ---------------- 英雄狀態碼（v0.2，A2b；§11.6-F 的舊服 Variables.js 與 A2b 樣本）----------------
# 冒險頁 viewData 的 hero.status.status 原樣整數。純常數、不含邏輯。
# 樣本實證 ✓：9（返回，Asia 8 兩份）、50（去冒險，Intl 11 一份）；
# 其餘來自舊服 Variables.js（§11.6-F），沒有頁面樣本佐證 ✗，使用前先對樣本。
HERO_STATUS_OUT_ATTACK = 3     # ✗ 出擊（攻擊）
HERO_STATUS_OUT_RAID = 4       # ✗ 出擊（搶奪）
HERO_STATUS_OUT_SUPPLY = 5     # ✗ 出擊（增援）
HERO_STATUS_RETURNING = 9      # ✓ 返回（冒險返回；A2b 樣本）
HERO_STATUS_HIDING = 40        # ✗ 躲避
HERO_STATUS_ADVENTURE = 50     # ✓ 冒險（去程；A2b 樣本）
HERO_STATUS_HOME = 100         # ✗ 在村
HERO_STATUS_DEAD = 101         # ✗ 死亡
HERO_STATUS_CAPTIVE = 102      # ✗ 被俘
HERO_STATUS_STATIONED = 103    # ✗ 駐守他村

HERO_STATUS = {
    HERO_STATUS_OUT_ATTACK: "out_attack", HERO_STATUS_OUT_RAID: "out_raid",
    HERO_STATUS_OUT_SUPPLY: "out_supply", HERO_STATUS_RETURNING: "returning",
    HERO_STATUS_HIDING: "hiding", HERO_STATUS_ADVENTURE: "adventure",
    HERO_STATUS_HOME: "home", HERO_STATUS_DEAD: "dead",
    HERO_STATUS_CAPTIVE: "captive", HERO_STATUS_STATIONED: "stationed",
}

# ---------------- 動作名稱常數（Actions.action，C5：str ≤ 40）----------------
# 只收卡片與契約明列的三個；建造／躲兵等既有動作名稱待 A4b 讀 log_action 回填（✗）。
ACTION_TRANSFER_RES = "調度資源"
ACTION_TROOP_MOVE = "運兵"
ACTION_VILLAGE_SKIP = "村莊跳過"   # C8：village_lock 不符時寫入

ACTION_NAMES = frozenset({ACTION_TRANSFER_RES, ACTION_TROOP_MOVE, ACTION_VILLAGE_SKIP})
