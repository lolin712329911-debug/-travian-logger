#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/tribe_data.py（cm-06）
版本：v0.2（v0.65：補 tribe_display_name）｜v0.1（A1b）
用途：種族資料的唯一出口（§4.1 規則 6、開發檔規則 10）。TribeSpec／UnitSpec 是凍結的資料結構，
      取代舊 dispatch.py 的全域 UNIT_SPEED／UNIT_ATTACK／UNIT_CARRY／TRIBE。
      其他模組只能經此取得種族資料，程式碼不得用種族名稱字串判斷（check_arch TRIBE_STRING）。
依賴：cm-11（schema，為了 ValidationError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  TRIBES                                 鍵 → TribeSpec（唯讀對照表）
  get_tribe(key)                         → TribeSpec；未知鍵丟 ValidationError(rule=unknown_tribe)
  resolve_tribe(name)                    → 種族鍵或 None（接受中文、英文、單複數）
  tribe_from_state(rows)                 → 種族鍵或 None（rows＝state 分頁 [[key, 值, …], …]；不開 Sheet）
  tribe_keys_by_id()                     → {頁面 tribeId: 種族鍵}（給 server_profile.verify_against_page）
  merchant_info(spec, speed)             → (載重, 格／時)；speed ≠ 1 丟 TribeDataError（倍速換算未驗證）
  cranny_factor(spec)                    → 山洞倍率（int）
  global_unit_id(spec, unit_key)         → 全域單位 id 或 None（D-21 尚未定案）
  tribe_display_name(tribe_id)           → 顯示用名稱（只供顯示；判斷種族一律走 TribeSpec，v0.2）

來源：舊 dispatch.py v1.8 的 TRIBES、TRIBE_ALIASES、resolve_tribe、tribe_from_state（✓ 已讀）；
      舊 travian_const.py 的 TRIBE_NAMES（種族 id，✓）。ROMAN_TRIBE_ID 不保留。
與舊版差異：
  1. 鍵由複數（舊 'gauls'）改為單數（C11 的 'gaul'）；別名表兩種寫法都收。
  2. 全域可變表與 configure／_apply_tribe 取消；tribe_from_state 不再開 Sheet（IO 屬 state_repo）。
  3. 兵種鍵由舊 't1'… 改為 C4 的種族內序號 'u1'…'u10'（拓荒者＝u10、首領／元老＝u9，各族一致）。

證據標記（本檔所有數值都沒有用遊戲樣本核對，TribeSpec.verified 一律 False）
  伺服器前提（使用者決定，A1b）：1 倍速、常規 Legends 世界。D-27（單位數值版本欄位）因此關閉，不實作。
  速度／攻擊／載重 u1～u6：沿用舊表（舊檔註解：Kingdoms 說明中心的一般世界表），即常規世界的標準數值。
    ✓ 官方「Community Week - Overview of Balance Changes」（support.travian.com/en/articles/201）寫明：
      調整後的數值只用在 Community Week 世界，常規世界沿用標準數值，所以常規服用本表（△ 尚未用遊戲內頁面核對）。
    參考（本專案不使用）：高盧在 Community Week 與標準值不同的只有劍士 攻擊 65→70、速度 6→7，雷法師 攻擊 90→110，
      海頓聖騎士 攻擊 140→150（防步兵 →65）。2026 夏季活動另有一組（例：海頓攻擊 95），適用範圍不明。
      萬一將來改玩 Community Week／活動服，這張表就不能直接用，要先開 C-v0.6 加單位數值版本欄位。
    開服後仍以 S8 Constants.js 與遊戲內單位頁核對（TribeSpec.verified 在核對前一律 False）。
  高盧 u7～u10：只填速度（衝車 4、投石車 3、首領 5、拓荒者 5），其餘 None。
    ✓ 拓荒者 5：官方 Community Week 單位表、Kingdoms 兵種表、社群 wiki 與夏季活動表都是 5，各版本一致。
    △ 衝車 4、投石車 3、首領 5：多個來源一致，尚未用遊戲內頁面核對。
  商人：高盧 750／24（✓ 官方種族說明）、羅馬 500／16、條頓 1000／12（△ Kingdoms 說明）。埃及 None（沒有資料，不猜）。
    倍速服的換算 ✗：官方「Game Versions and Speed」只說明部隊速度（x2、x3、x5 乘 2，x10 乘 4，並不等於倍速），
    沒有說明商人；第三方說速度與載重都乘倍速。實際載重由市場頁讀取（Merchants.capacity_each），這裡只是備援，
    所以 merchant_info 在 speed ≠ 1 時直接丟 TribeDataError，不用猜測值（本專案固定 1 倍速，不受影響；若改玩倍速服，
    先用 S3 實測再放開）。
  山洞：高盧 2 倍 △；其餘 1（官方種族說明只有高盧有山洞加成；埃及沒有資料，暫用 1）。
  城牆 gid：高盧 33、羅馬 31、條頓 32（卡片 △）；埃及 42 ✗（只有 gid 表出現 42＝石墻，歸屬是推測）。
  陷阱 gid：高盧 36（卡片）。佇列：羅馬 2 條並行（舊 runner 檔頭 ✓），其他 1。
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .schema import ValidationError

__all__ = ["TribeDataError", "UnitSpec", "TribeSpec", "TRIBES", "get_tribe", "resolve_tribe", "tribe_from_state",
           "tribe_keys_by_id", "merchant_info", "cranny_factor", "global_unit_id", "tribe_display_name"]

Res4 = Tuple[int, int, int, int]


class TribeDataError(ValueError):
    """種族資料缺漏或參數不合法（例如該族沒有商人資料）。"""


# ---------------------------------------------------------------- 結構
@dataclass(frozen=True)
class UnitSpec:
    key: str                        # 'u1'～'u10'（種族內序號，C4）
    name: str                       # 英文官方名（顯示用，不做判斷）
    speed: Optional[int]            # 格／時，1 倍速
    attack: Optional[int]
    def_inf: Optional[int]          # 對步兵防禦
    def_cav: Optional[int]          # 對騎兵防禦
    carry: Optional[int]
    cost: Optional[Res4]            # 木、磚、鐵、穀
    train_gid: Optional[int]        # 訓練建築 gid
    # None＝沒有證據（✗），不是 0


@dataclass(frozen=True)
class TribeSpec:
    key: str
    name: str                       # 中文顯示名
    tribe_id: Optional[int]         # 頁面 viewData 的 ownPlayer.tribeId
    units: Tuple[UnitSpec, ...]     # 只列有資料的兵種
    merchant_capacity: Optional[int]
    merchant_speed: Optional[int]   # 格／時，1 倍速
    cranny_factor: int
    wall_gid: Optional[int]
    trap_gid: Optional[int]
    queue_mode: str                 # 'single'（單條）或 'parallel'（資源田與建築並行）
    base_queue_slots: int           # 建城佇列基準條數（Plus 有效再 +1，由 stage 處理）
    settler_unit: Optional[str]
    chief_unit: Optional[str]
    unit_id_base: Optional[int]     # 全域單位 id＝base＋序號（D-21，未定案）
    verified: bool = False          # 資料是否已用遊戲樣本核對

    def unit(self, key: str) -> Optional[UnitSpec]:
        for u in self.units:
            if u.key == key:
                return u
        return None


def _u(key, name, speed, attack, carry, *, def_inf=None, def_cav=None, cost=None, train_gid=None):
    return UnitSpec(key, name, speed, attack, def_inf, def_cav, carry, cost, train_gid)


# ---------------------------------------------------------------- 資料
_GAUL = TribeSpec(
    key="gaul", name="高盧", tribe_id=3,
    units=(
        _u("u1", "Phalanx", 7, 15, 35),
        _u("u2", "Swordsman", 6, 65, 45),
        _u("u3", "Pathfinder", 17, 0, 0),
        _u("u4", "Theutates Thunder", 19, 90, 75),
        _u("u5", "Druidrider", 16, 45, 35),
        _u("u6", "Haeduan", 13, 140, 65),
        _u("u7", "Ram", 4, None, None),
        _u("u8", "Trebuchet", 3, None, None),
        _u("u9", "Chieftain", 5, None, None),
        _u("u10", "Settler", 5, None, None),
    ),
    merchant_capacity=750, merchant_speed=24, cranny_factor=2,
    wall_gid=33, trap_gid=36, queue_mode="single", base_queue_slots=1,
    settler_unit="u10", chief_unit="u9", unit_id_base=20,
)

_ROMAN = TribeSpec(
    key="roman", name="羅馬", tribe_id=1,
    units=(
        _u("u1", "Legionnaire", 6, 40, 50),
        _u("u2", "Praetorian", 5, 30, 20),
        _u("u3", "Imperian", 7, 70, 50),
        _u("u4", "Equites Legati", 16, 0, 0),
        _u("u5", "Equites Imperatoris", 14, 120, 100),
        _u("u6", "Equites Caesaris", 10, 180, 70),
    ),
    merchant_capacity=500, merchant_speed=16, cranny_factor=1,
    wall_gid=31, trap_gid=None, queue_mode="parallel", base_queue_slots=2,
    settler_unit="u10", chief_unit="u9", unit_id_base=None,
)

_TEUTON = TribeSpec(
    key="teuton", name="條頓", tribe_id=2,
    units=(
        _u("u1", "Clubswinger", 7, 40, 60),
        _u("u2", "Spearfighter", 7, 10, 40),
        _u("u3", "Axefighter", 6, 60, 50),
        _u("u4", "Scout", 9, 0, 0),
        _u("u5", "Paladin", 10, 55, 110),
        _u("u6", "Teutonic Knight", 9, 150, 80),
    ),
    merchant_capacity=1000, merchant_speed=12, cranny_factor=1,
    wall_gid=32, trap_gid=None, queue_mode="single", base_queue_slots=1,
    settler_unit="u10", chief_unit="u9", unit_id_base=None,
)

_EGYPTIAN = TribeSpec(
    key="egyptian", name="埃及", tribe_id=6,
    units=(
        # 舊檔註解：舊伺服器實測（速度 ✓、u1 攻擊與載重 ✓、u2 攻擊 △ 由 295 反推約 30.6）；新服沒重驗
        _u("u1", "Slave Militia", 7, 10, 15),
        _u("u2", "Ash Warden", 6, 30, 50),
        _u("u3", "Khopesh Warrior", 7, None, None),
        _u("u4", "Sopdu Explorer", 16, None, None),
    ),
    merchant_capacity=None, merchant_speed=None, cranny_factor=1,
    wall_gid=42, trap_gid=None, queue_mode="single", base_queue_slots=1,
    settler_unit="u10", chief_unit="u9", unit_id_base=None,
)

TRIBES: Mapping[str, TribeSpec] = MappingProxyType({
    t.key: t for t in (_GAUL, _ROMAN, _TEUTON, _EGYPTIAN)})

# 頁面 tribeId → 種族鍵（舊 travian_const.TRIBE_NAMES ✓）。匈奴只有 id，沒有 TribeSpec（沒有可靠兵種表）。
_TRIBE_KEYS_BY_ID = {1: "roman", 2: "teuton", 3: "gaul", 6: "egyptian", 7: "hun"}

# 沒有 TribeSpec 的種族 id 的顯示名稱（v0.2；來源：台灣服繁中語言包 allgemein.json 的 v0～v9）。
# 只供顯示（例如 state 的 tribe 值、log），不可用來判斷種族。有 TribeSpec 的 id（1、2、3、6）一律用
# spec.name，保持與舊 bot 的 TRIBE_NAMES 相同的用語（羅馬、條頓、高盧、埃及；語言包寫「羅馬人」「日耳曼人」
# 「高盧人」「埃及人」，用語差異見 D-31）；7 匈奴沿用舊 bot。其餘為語言包原文。
_EXTRA_DISPLAY_NAMES = {0: "無種族", 4: "自然界", 5: "賴達族", 7: "匈奴", 8: "斯巴達人", 9: "維京人"}

# state 分頁 tribe 欄可能的寫法 → TRIBES 的鍵（舊 TRIBE_ALIASES ✓，加上單數鍵本身）
_ALIASES = {
    "gaul": ("高盧", "高卢", "gaul", "gauls"),
    "egyptian": ("埃及", "egyptian", "egyptians"),
    "roman": ("羅馬", "罗马", "roman", "romans"),
    "teuton": ("條頓", "条顿", "日耳曼", "teuton", "teutons"),
}


# ---------------------------------------------------------------- 查詢
def get_tribe(key: str) -> TribeSpec:
    """依鍵取 TribeSpec；未知鍵丟 ValidationError(rule=unknown_tribe)。"""
    spec = TRIBES.get(key) if isinstance(key, str) else None
    if spec is None:
        raise ValidationError("TribeSpec", "tribe", key, "unknown_tribe")
    return spec


def _norm(name: Any) -> str:
    return str(name or "").strip().casefold().rstrip("人族")


def resolve_tribe(name: Any) -> Optional[str]:
    """state 的 tribe 值（例：高盧）→ TRIBES 的鍵；認不得回 None。規則同舊 resolve_tribe。"""
    t = _norm(name)
    if not t:
        return None
    for key, names in _ALIASES.items():
        if t in (_norm(n) for n in names):
            return key
    return None


def tribe_from_state(rows: Optional[Iterable[Any]]) -> Optional[str]:
    """從 state 分頁的列（[[key, 值, …], …]）找 tribe 列 → 種族鍵；找不到或認不得回 None。不拋例外。"""
    try:
        for row in rows or ():
            if row and str(row[0]).strip() == "tribe" and len(row) > 1:
                return resolve_tribe(row[1])
    except (TypeError, ValueError, IndexError):
        return None
    return None


def tribe_keys_by_id() -> Dict[int, str]:
    """頁面 tribeId → 種族鍵（複本）。供 server_profile.verify_against_page 的 tribe_keys_by_id 參數。"""
    return dict(_TRIBE_KEYS_BY_ID)


def merchant_info(spec: TribeSpec, speed: int) -> Tuple[int, int]:
    """(載重, 格／時)，1 倍速的值。speed＝伺服器倍速（int≥1）。

    官方沒有說明商人在倍速服的換算（✗，見檔頭），所以 speed ≠ 1 一律丟 TribeDataError，不用猜測值；
    該族沒有商人資料也丟 TribeDataError。實際載重請讀市場頁（Merchants.capacity_each）。
    """
    if isinstance(speed, bool) or not isinstance(speed, int) or speed < 1:
        raise TribeDataError("speed 需為 int ≥ 1")
    if spec.merchant_capacity is None or spec.merchant_speed is None:
        raise TribeDataError("該種族沒有商人資料")
    if speed != 1:
        raise TribeDataError("商人在倍速服的換算尚未驗證（speed 需為 1）")
    return spec.merchant_capacity, spec.merchant_speed


def cranny_factor(spec: TribeSpec) -> int:
    """山洞容量倍率。"""
    return spec.cranny_factor


def global_unit_id(spec: TribeSpec, unit_key: str) -> Optional[int]:
    """種族內序號 'u1'～'u10' → 全域單位 id（D-21：高盧 21～30）。沒有資料回 None；鍵不合法丟 TribeDataError。"""
    if not isinstance(unit_key, str) or not unit_key.startswith("u") or not unit_key[1:].isdigit():
        raise TribeDataError("兵種鍵需為 u1～u10")
    n = int(unit_key[1:])
    if not 1 <= n <= 10:
        raise TribeDataError("兵種鍵需為 u1～u10")
    return None if spec.unit_id_base is None else spec.unit_id_base + n


def tribe_display_name(tribe_id: Any) -> str:
    """頁面 tribeId → 顯示用名稱。有 TribeSpec 的用 spec.name，其餘查 _EXTRA_DISPLAY_NAMES，
    都沒有回「種族 N」（與舊 runner 的備援寫法相同）；tribeId 不是 int（含 bool、None）回「種族 ?」。
    只供顯示，不可拿來判斷種族。"""
    if isinstance(tribe_id, bool) or not isinstance(tribe_id, int):
        return "種族 ?"
    key = _TRIBE_KEYS_BY_ID.get(tribe_id)
    spec = TRIBES.get(key) if key else None
    if spec is not None:
        return spec.name
    return _EXTRA_DISPLAY_NAMES.get(tribe_id, f"種族 {tribe_id}")
