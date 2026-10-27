#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/models.py（cm-01）
版本：v0.1（A1a-2）｜對應契約 C-v0.5（全部 ✗ 草案，待 B1／B6 用真實樣本修正）
用途：契約資料結構（dataclass；欄位、型別、規則完全依 §6.1／§6.2，即 schema.CONTRACT_SPECS）。
      VillageRef(C1)、VillageSnapshot(C2)、TransferPlan(C3)、TroopMovePlan(C4)、ActionRow(C5)、
      VillageSettingsRow(C6)、MarketConfig(C7)、VillageLock(C8)、BuildSettings／HideContext／
      VillageContext(C9)、StageResult(C10)、ServerProfile(C11)、PlanVerdict／PlanRejection(C12)，
      以及子結構 BuildTarget、Merchants、Transit、Oasis。
依賴：cm-11（schema）、cm-10（serialize）。
部署狀態：未部署（GA 前不 live）。

設計重點
  1. 每個結構有 to_dict()／from_dict()／validate()／ensure_valid()；驗證一律呼叫 schema，
     本檔不重寫任何規則。建構物件時不自動驗證（parsers 與 stage 可先組裝再驗證）；
     從外部讀入用 from_dict()（先驗證再建構，不合法丟 ValidationError）。
  2. 有對應 Sheet 欄位者有 to_row()／from_row()（ActionRow、VillageSettingsRow）；
     儲存格格式化只呼叫 serialize，本檔不自行格式化。
  3. 資源（木、磚、鐵、穀）一律 tuple[int, int, int, int]；序列欄位用 tuple。
     frozen 為淺層唯讀（dict 欄位內容仍可被改，約定不改）。to_dict() 一律轉回 list。
  4. 不出現種族字串（§4.1 規則 6）。C11 的 tribe 預設值由 config_schema.DEFAULTS 提供，
     本檔 ServerProfile.tribe 為必填。
  5. 時間欄位一律是 UTC 字串（§6.1），不在此轉 datetime。

與舊 travian_models.py 的差異（邊界轉換由 parsers／repo 做，見 parsed.py 說明）：
  舊 State.cost／stock／prod 是 list → 新為 tuple；舊 `secs` → `*_s`；舊 Slot.gid=0（空地）→ None。
"""
import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple

from . import schema, serialize

ValidationError = schema.ValidationError
Res4 = Tuple[int, int, int, int]

# C11 預設值（tribe 不在此；見模組說明 4）
DEFAULT_GAME = "legends"
DEFAULT_SPEED = 1
DEFAULT_MAP_HALF = 200      # △ 待 S8 核對
DEFAULT_LOCALE = "zh-TW"

CONTRACT_CLASSES: Dict[str, type] = {}


# ---------------------------------------------------------------- 共用工具
def to_plain(obj: Any) -> Any:
    """dataclass／tuple／Enum 轉成純 dict／list／值（供 schema 驗證、golden 與序列化）。"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    return obj


def clip_text(text: str, max_len: int) -> str:
    """把 detail／reason 這類自由文字截到 max_len（超長加「…」）。截斷只在 serialize 做（§6.1）。"""
    return serialize.to_cell(text, "str", max_len)


def _convert(kind: Optional[str], v: Any) -> Any:
    if v is None:
        return None
    if kind is None:
        return dict(v) if isinstance(v, dict) else v
    if kind in ("res", "ints"):
        return tuple(v)
    tag, _, name = kind.partition(":")
    klass = CONTRACT_CLASSES[name]
    if tag == "S":
        return klass._build(v)
    if tag == "L":
        return tuple(klass._build(i) for i in v)
    if tag == "LL":
        return [klass._build(i) for i in v]
    raise AssertionError(f"未知欄位種類 {kind}")


class _Contract:
    """契約結構共用方法（不是 dataclass）。"""

    CONTRACT: ClassVar[str] = ""
    KINDS: ClassVar[Dict[str, str]] = {}

    def to_dict(self) -> Dict[str, Any]:
        return to_plain(self)

    def validate(self, ctx: Optional[Mapping[str, Any]] = None) -> List[ValidationError]:
        """回傳錯誤清單（空＝通過）。ctx 見 schema 模組說明。"""
        return schema.validate(self.CONTRACT, self.to_dict(), dict(ctx) if ctx else None)

    def ensure_valid(self, ctx: Optional[Mapping[str, Any]] = None) -> None:
        schema.ensure_valid(self.CONTRACT, self.to_dict(), dict(ctx) if ctx else None)

    @classmethod
    def from_dict(cls, data: Any, ctx: Optional[Mapping[str, Any]] = None, *, check: bool = True):
        """從純 dict 建構。check=True（預設）先驗證，不合法丟 ValidationError（.all 帶全部）。"""
        if check:
            schema.ensure_valid(cls.CONTRACT, data, dict(ctx) if ctx else None)
        elif not isinstance(data, dict):
            raise ValidationError(cls.CONTRACT, "", None, "type")
        return cls._build(data)

    @classmethod
    def _build(cls, data: Mapping[str, Any]):
        kw = {}
        for f in dataclasses.fields(cls):
            if f.name not in data and (f.default is not dataclasses.MISSING
                                       or f.default_factory is not dataclasses.MISSING):
                continue
            kw[f.name] = _convert(cls.KINDS.get(f.name), data.get(f.name))
        return cls(**kw)


def _contract(name: str, kinds: Optional[Dict[str, str]] = None):
    def deco(cls):
        cls.CONTRACT = name
        cls.KINDS = dict(kinds or {})
        CONTRACT_CLASSES[name] = cls
        return cls
    return deco


# ---------------------------------------------------------------- 子結構
@_contract("BuildTarget", {"cost": "res"})
@dataclass(frozen=True)
class BuildTarget(_Contract):
    aid: int            # 1～18 資源田，19～40 建築
    gid: int
    name: str
    to_level: int
    cost: Res4          # 木、磚、鐵、穀
    ready_in_s: int     # 0＝現在就夠


@_contract("Merchants")
@dataclass(frozen=True)
class Merchants(_Contract):
    free: int
    total: int
    capacity_each: int


@_contract("Transit", {"amount": "res"})
@dataclass(frozen=True)
class Transit(_Contract):
    from_did: Optional[int]     # 別的玩家為 None
    to_did: int
    amount: Res4
    arrive_utc: str


@_contract("Oasis")
@dataclass(frozen=True)
class Oasis(_Contract):
    x: int
    y: int
    kind: str                   # 如 wood25
    safe: Optional[bool]        # 未驗證 None


@_contract("BuildSettings")
@dataclass(frozen=True)
class BuildSettings(_Contract):
    # target_level 沒有預設：舊 DEFAULT_TARGET_BUILDING_LEVEL 的值在舊 travian_const.py，
    # 本 WP 沒收到，不猜（✗，A1b 或有人提供舊檔後再定）。
    target_level: int
    queue_slots: int = 1
    build_order: Optional[str] = None       # 格式 ✗ 待 A4b／B6


@_contract("HideContext", {"oases": "L:Oasis", "blocked": "ints"})
@dataclass(frozen=True)
class HideContext(_Contract):
    home_x: int
    home_y: int
    oases: Tuple[Oasis, ...]
    blocked: Tuple[int, ...]    # 封鎖的 map id
    tribe: str                  # 須為 TRIBES 鍵


@_contract("PlanRejection")
@dataclass(frozen=True)
class PlanRejection(_Contract):
    seq: int
    rule: str                   # bad_format／unknown_building／level_over_cap／prereq_unmet／missing_order
    reason: str


# ---------------------------------------------------------------- C1
@_contract("VillageRef")
@dataclass(frozen=True)
class VillageRef(_Contract):
    did: int
    name: str
    x: int
    y: int
    is_capital: Optional[bool]  # 頁面讀不到則 None，以 Villages 為準
    active: bool


# ---------------------------------------------------------------- C2
@_contract("VillageSnapshot", {
    "stock": "res", "prod": "res", "hidden": "res",
    "next_target": "S:BuildTarget", "merchants": "S:Merchants",
    "incoming_res": "L:Transit", "outgoing_res": "L:Transit"})
@dataclass(frozen=True)
class VillageSnapshot(_Contract):
    """每村每輪唯讀快照。stage 只能經 StageResult.snapshot_updates 提出更新。"""
    did: int
    ts_utc: str
    stock: Res4
    prod: Res4                              # 可負（穀可為負）
    cap_wh: int
    cap_gr: int
    hidden: Res4                            # 山洞可隱藏量
    queue_free_in_s: int                    # 0＝佇列空閒
    queue_slots_used: int
    next_target: Optional[BuildTarget]
    merchants: Optional[Merchants]          # 市場 0 級為 None
    incoming_res: Tuple[Transit, ...]
    outgoing_res: Tuple[Transit, ...]
    incoming_attacks: Optional[int]         # 未知 None（0 表示確定沒有）
    units_home: Optional[Dict[str, int]]    # 兵種鍵待 D-21（✗）
    units_away: Optional[Dict[str, int]]


# ---------------------------------------------------------------- C3
@_contract("TransferPlan", {"amount": "res"})
@dataclass(frozen=True)
class TransferPlan(_Contract):
    # Transit 分頁另有 ts_utc／result／detail（非 C3 欄位），不在此做 to_row；見交接區塊。
    plan_id: str                # T + YYYYMMDDHHMM + -來源-目標
    from_did: int
    to_did: int
    amount: Res4
    merchants_needed: int
    arrive_utc: str
    reason: str
    mode: str                   # off／dry／live


# ---------------------------------------------------------------- C4
@_contract("TroopMovePlan")
@dataclass(frozen=True)
class TroopMovePlan(_Contract):
    plan_id: str                # M + YYYYMMDDHHMM + -來源-目標
    from_did: int
    to_did: int
    units: Dict[str, int]       # 鍵 u1～u10、hero（定義待 D-21 ✗）
    kind: str                   # reinforce／recall（其他待 D-3）
    arrive_utc: Optional[str]
    reason: str
    mode: str


# ---------------------------------------------------------------- C5
ACTION_CELLS = (   # Actions 目標 10 欄，欄序固定：(欄名, 儲存格型別, 可空)
    ("ts_utc", "utc", True), ("action", "str", True), ("aid", "int", True), ("gid", "int", True),
    ("level", "int", True), ("cost", "str", True), ("mode", "str", True), ("result", "str", True),
    ("detail", "str", False), ("did", "int", True),
)
ACTION_COLUMNS = tuple(c[0] for c in ACTION_CELLS)


def _pad(cells: Sequence[Any], n: int) -> List[Any]:
    """Sheet 讀回的列可能尾端被截短：補空白；多出的尾欄（未來追加）忽略。"""
    row = list(cells)[:n]
    return row + [""] * (n - len(row))


def _read_cells(contract: str, spec, cells: Sequence[Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for (name, type_, nullable), cell in zip(spec, _pad(cells, len(spec))):
        try:
            data[name] = serialize.from_cell(cell, type_, nullable)
        except serialize.SerializeError:
            raise ValidationError(contract, name, None, "cell_format") from None
    return data


@_contract("ActionRow")
@dataclass(frozen=True)
class ActionRow(_Contract):
    ts_utc: str
    action: str
    aid: Optional[int]
    gid: Optional[int]
    level: Optional[int]
    cost: Optional[str]         # 'w,c,i,g'；Sheet 唯一的逗號字串
    mode: str
    result: str                 # ok／dry／skipped／failed／deferred（中文只放 detail）
    detail: str                 # ≤300，可空字串
    did: int

    COLUMNS: ClassVar[Tuple[str, ...]] = ACTION_COLUMNS

    @property
    def cost_res(self) -> Optional[List[int]]:
        return None if self.cost is None else serialize.cost_str_to_res(self.cost)

    def to_row(self, ctx: Optional[Mapping[str, Any]] = None) -> List[Any]:
        """寫出前先驗證（不合法丟 ValidationError）；長文字請先用 clip_text。"""
        self.ensure_valid(ctx)
        try:
            return [serialize.to_cell(getattr(self, n), t) for n, t, _ in ACTION_CELLS]
        except serialize.SerializeError:
            raise ValidationError(self.CONTRACT, "", None, "cell_format") from None

    @classmethod
    def from_row(cls, cells: Sequence[Any], ctx: Optional[Mapping[str, Any]] = None) -> "ActionRow":
        return cls.from_dict(_read_cells(cls.CONTRACT, ACTION_CELLS, cells), ctx)


# ---------------------------------------------------------------- C6
VILLAGE_CELLS = (  # Villages 分頁，一列一村，欄序固定
    ("did", "int", True), ("name", "str", True), ("enabled", "bool", True), ("role", "str", True),
    ("is_capital", "bool", True), ("queue_slots", "int", True), ("build_order", "str", True),
    ("hide_mode", "str", True), ("guard_mode", "str", True), ("fill_mode", "str", True),
    ("priority", "int", True), ("note", "str", True),
)
VILLAGE_COLUMNS = tuple(c[0] for c in VILLAGE_CELLS)
_VILLAGE_BLANK_DEFAULTS = {"enabled": True, "role": "resource", "is_capital": False,
                           "queue_slots": 1, "priority": 100}


@_contract("VillageSettingsRow")
@dataclass(frozen=True)
class VillageSettingsRow(_Contract):
    did: int
    name: str
    enabled: bool = True
    role: str = "resource"                  # capital／resource／military／other
    is_capital: bool = False
    queue_slots: int = 1
    build_order: Optional[str] = None
    hide_mode: Optional[str] = None         # 空白＝用 Config
    guard_mode: Optional[str] = None
    fill_mode: Optional[str] = None
    priority: int = 100                     # 越小越先
    note: Optional[str] = None

    COLUMNS: ClassVar[Tuple[str, ...]] = VILLAGE_COLUMNS

    def to_row(self, ctx: Optional[Mapping[str, Any]] = None) -> List[Any]:
        self.ensure_valid(ctx)
        try:
            return [serialize.to_cell(getattr(self, n), t) for n, t, _ in VILLAGE_CELLS]
        except serialize.SerializeError:
            raise ValidationError(self.CONTRACT, "", None, "cell_format") from None

    @classmethod
    def from_row(cls, cells: Sequence[Any], ctx: Optional[Mapping[str, Any]] = None) -> "VillageSettingsRow":
        """儲存格空白時，enabled／role／is_capital／queue_slots／priority 採 C6 預設；
        did、name 空白＝錯誤；格式不合法（如 enabled 填 yes）＝ValidationError(cell_format)。"""
        data = _read_cells(cls.CONTRACT, VILLAGE_CELLS, cells)
        for k, default in _VILLAGE_BLANK_DEFAULTS.items():
            if data[k] is None:
                data[k] = default
        return cls.from_dict(data, ctx)


def validate_village_table(rows: Sequence[VillageSettingsRow],
                           ctx: Optional[Mapping[str, Any]] = None) -> List[ValidationError]:
    """C6 全表規則：did 不重複、最多 1 列 is_capital=TRUE（另含每列欄位驗證）。"""
    return schema.validate("VillageSettingsTable", [r.to_dict() for r in rows],
                           dict(ctx) if ctx else None)


# ---------------------------------------------------------------- C7（Config 鍵，§6.4；預設 ✗ 草案）
@_contract("MarketConfig")
@dataclass(frozen=True)
class MarketConfig(_Contract):
    market_max_per_ship: int = 0            # 0＝不限
    market_min_ship: int = 200
    market_reserve_hours: float = 2.0
    market_target_fill_pct: int = 80
    market_max_ships_per_run: int = 3


# ---------------------------------------------------------------- C8
@_contract("VillageLock")
@dataclass(frozen=True)
class VillageLock(_Contract):
    main_did: Optional[int] = None
    main_did_set_utc: Optional[str] = None


# ---------------------------------------------------------------- C9
@_contract("VillageContext", {"build_settings": "S:BuildSettings", "hide_context": "S:HideContext"})
@dataclass(frozen=True)
class VillageContext(_Contract):
    did: int
    name: str
    x: int
    y: int
    is_capital: bool
    role: str
    enabled: bool
    priority: int
    build_settings: BuildSettings
    modes: Dict[str, str]                   # 鍵 fill_in／guard／item_transfer／focus／hide／oasis／hero／market／troops
    hide_context: HideContext               # 規則：hide_context.tribe == ServerProfile.tribe（ctx["tribe"]）


# ---------------------------------------------------------------- C10
@_contract("StageResult", {"actions": "LL:ActionRow"})
@dataclass
class StageResult(_Contract):
    """stage 的回傳。可變（stage 邊跑邊加 actions）；由 app 統一寫入 Actions。"""
    status: str                             # ok／skipped／failed／deferred
    actions: List[ActionRow] = field(default_factory=list)
    snapshot_updates: Dict[str, Any] = field(default_factory=dict)   # 鍵須是 C2 欄位名
    note: str = ""                          # failed 時不可為空
    requests_used: int = 0
    elapsed_s: float = 0.0


# ---------------------------------------------------------------- C11
@_contract("ServerProfile")
@dataclass(frozen=True)
class ServerProfile(_Contract):
    server_id: str
    base_url: str                           # https://主機，不含路徑與帳密
    tribe: str                              # 必填；預設值由 config_schema.DEFAULTS 提供
    start_utc: str
    server_tz: str                          # IANA 名稱，＝頁面 Travian.Game.timeZone
    game: str = DEFAULT_GAME
    speed: int = DEFAULT_SPEED
    map_half: int = DEFAULT_MAP_HALF
    protection_days: Optional[int] = None   # △
    version: Optional[str] = None           # 頁面 gpack 版號
    locale: str = DEFAULT_LOCALE


# ---------------------------------------------------------------- C12
@_contract("PlanVerdict", {"rejected": "L:PlanRejection"})
@dataclass(frozen=True)
class PlanVerdict(_Contract):
    did: int
    checked_utc: str
    verdict: str                            # proceed／hold
    next_seq: Optional[int]                 # 整份讀不到為 None
    rejected: Tuple[PlanRejection, ...] = ()
