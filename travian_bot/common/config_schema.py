#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/config_schema.py（cm-08）
版本：v0.1（A1b）
用途：Config 分頁的鍵登記（型別、預設、允許值、範圍、說明）、讀入時的型別轉換與驗證、
      由 Config 組出 ServerProfile（C11）與單村的 VillageContext（C9）。純函式，不讀環境變數、不開 Sheet。
依賴：cm-01（models）、cm-04（modes）、cm-06（tribe_data）、cm-10（serialize）、cm-11（schema）、
      cm-12（game_rules）、cm-13（server_profile）。
部署狀態：未部署（GA 前不 live）。

公開介面
  SCHEMA_VERSION、DEFAULTS、ORDER、NOTES、KEYS、REQUIRED_KEYS、MODE_KEYS、DEFAULT_TRIBE
  normalize_cfg(raw)        → (cfg, problems)：鍵轉小寫、值轉型；空白＝預設；不合法＝預設並回報
  validate_cfg(cfg)         → list[CfgProblem]（空＝全部正常）
  profile_from_cfg(cfg)     → ServerProfile（server_* 與 tribe 任何問題都丟 ValidationError，不用預設頂替）
  merge_settings(cfg, village_rows, refs) → list[VillageContext]（A1b 只有單村模式；多村列由 B2 補）

與舊 sheets_writer.py（✓ 已讀）的差異（交接區塊有列）
  1. 沿用 28 個舊鍵中的 22 個（鍵名、型別、預設不變，除下列）；target_level 預設 2→10（已決定）；
     hero_focus_min_hours 改 float（§6.1 `*_hours`）；hide_mode 預設 observe→off；build_order 空白＝None。
  2. 舊鍵取代：hero_adventure→hero_mode；hero_transfer_mode→transfer_mode；hero_focus_mode→focus_mode；
     hero_guard_mode→guard_mode＋guard_exposure（新-8）；fill_in_mode→fill_mode。對照見 LEGACY_KEY_MAP；
     舊值對應（on→live、TRUE→live、incoming_only／always 等）只在 config_repo 的邊界轉換，
     本檔所有 mode 鍵只認 off／dry／live，其他一律 off 並回報。
     舊 hero_transfer_mode 的 incoming_only／always 區分在新版沒有對應鍵，A6a2 需要時再開 transfer_exposure。
  3. focus_mode 不是 mode 鍵：值域只有 off／auto（§6.4：新值域待 A6a2，不直接套用 off／dry／live），
     merge_settings 目前固定回 modes['focus']='off'。
  4. 退役不登記：home_x、home_y（改由 VillageRef）、map_size（改 server_map_half；舊 401＝2×200＋1）、
     village_id（改 main_did／C8）。
  5. 布林嚴格（§6.1）：TRUE／FALSE／true／false／1／0；舊的 yes／是／否 等同義詞不帶進來（新 Sheet 重填）。
     enabled 看不懂＝視為 FALSE 並回報（舊版「看不懂＝啟用」，緊急停止開關不該在打錯字時繼續跑）。
     舊 is_capital 空白會變 TRUE（疑似 bug），新版空白＝FALSE。
  6. 安靜時段（舊 QUIET_UTC）不保留，沒有對應鍵。
  7. is_capital 暫放帳號級（單村），單村模式以 Config 為準（頁面目前讀不出首都）；多村時由 Villages 列取代（B2）。
  8. tribe 讀入接受已登記的別名（高盧→gaul，§6.1 讀入可寬鬆）；main_did 與 main_did_set_utc 要同時有或同時空；
     schema_version 比本程式新就拒絕讀取（error）。

問題嚴重度：error＝不能安全使用（必填缺值、strict 鍵不合法值設 None、enabled 看不懂、種族未知、超過資源田上限、
鎖村不完整、版本太新）；warn＝已用預設或已忽略（一般鍵不合法、mode 看不懂、未登記或舊鍵、非預設種族）。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import game_rules, serialize
from .models import (BuildSettings, HideContext, ServerProfile, VillageContext, VillageRef,
                     VillageSettingsRow, ValidationError)
from .modes import Mode, parse_mode_checked
from .server_profile import profile_from_dict
from .tribe_data import TRIBES, get_tribe, resolve_tribe

__all__ = ["SCHEMA_VERSION", "DEFAULT_TRIBE", "KeySpec", "CfgProblem", "KEYS", "DEFAULTS", "ORDER",
           "NOTES", "REQUIRED_KEYS", "MODE_KEYS", "MODE_TO_CTX", "LEGACY_KEY_MAP", "normalize_cfg", "validate_cfg",
           "profile_from_cfg", "merge_settings"]

SCHEMA_VERSION = 1
DEFAULT_TRIBE = "gaul"          # C11 預設；非此值啟用時警告「未驗證」
_HERO_ALLOWED = ("normal", "hard")
_EXPOSURE = ("incoming", "always")
_FOCUS = ("off", "auto")


@dataclass(frozen=True)
class KeySpec:
    key: str
    kind: str                       # bool／int／float／str／enum／mode／utc／tribe／csvset
    default: Any
    note: str
    allowed: Optional[Tuple[str, ...]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    max_len: Optional[int] = None
    required: bool = False          # 沒有預設、缺了就是錯誤
    nullable: bool = False          # 空白可為 None
    strict: bool = False            # 不合法時不用預設頂替（回報 error、值設 None）


@dataclass(frozen=True)
class CfgProblem:
    key: str
    severity: str                   # 'error'（不能安全使用）或 'warn'（已用預設／已忽略）
    rule: str
    message: str                    # 不含值（避免機密外洩）


def _k(key, kind, default, note, **kw) -> KeySpec:
    return KeySpec(key, kind, default, note, **kw)


_MODE_NOTE = "off／dry／live（看不懂一律當 off）"

KEYS: Tuple[KeySpec, ...] = (
    _k("schema_version", "int", SCHEMA_VERSION, "Config 格式版本（只增不減）", min=1),
    _k("enabled", "bool", True, "FALSE＝緊急停止；看不懂也視為 FALSE"),
    # ---- 伺服器（C11）----
    _k("tribe", "tribe", DEFAULT_TRIBE, "種族鍵（TRIBES 的鍵）；非預設種族啟用時警告「未驗證」", strict=True),
    _k("server_id", "str", None, "伺服器代號（必填）", max_len=80, required=True, strict=True),
    _k("server_base_url", "str", None, "https://主機，不含路徑與帳密（必填）", max_len=200, required=True, strict=True),
    _k("server_tz", "str", None, "IANA 時區，＝頁面 Travian.Game.timeZone（必填）", max_len=60, required=True, strict=True),
    _k("server_start_utc", "utc", None, "開服時間 UTC，例 2026-11-02T08:15:30Z（必填）", required=True, strict=True),
    _k("server_speed", "int", 1, "伺服器倍速（整數 ≥ 1）；本專案固定 1 倍速常規服", min=1, strict=True),
    _k("server_map_half", "int", 200, "地圖半邊長（座標 -N..N；△ 開服後核對）", min=1, strict=True),
    _k("server_protection_days", "int", None, "新手保護天數（△；空白＝未知）", min=0, nullable=True, strict=True),
    _k("server_locale", "str", "zh-TW", "介面語系（與頁面 <html lang> 不符時啟動警告）", max_len=20, strict=True),
    _k("main_did", "int", None, "主村 did（第一次執行自動記錄；之後只讀）", min=1, nullable=True),
    _k("main_did_set_utc", "utc", None, "main_did 記錄時間（自動）", nullable=True),
    # ---- 建城 ----
    _k("is_capital", "bool", False, "首都才填 TRUE（單村；多村改在 Villages）"),
    _k("target_level", "int", 10, "資源田升到幾級（沒設 build_order 時使用；非首都上限 10）", min=1),
    _k("queue_slots", "int", None, "建城佇列條數 1..3；留空＝依種族基準（Plus 另計）", min=1, max=3, nullable=True),
    _k("max_builds", "int", 2, "每輪最多送出幾個升級", min=0),
    _k("target_building_level", "int", 0, "倉庫／糧倉升到幾級，0＝停用", min=0),
    _k("build_order", "str", None, "建城順序（格式 A4b 定案；空白＝沒有）", max_len=2000, nullable=True),
    # ---- 寫入類 mode（off／dry／live）----
    _k("hide_mode", "mode", "off", "躲兵：" + _MODE_NOTE),
    _k("guard_mode", "mode", "off", "庫存防搶＋防溢出守衛：" + _MODE_NOTE),
    _k("guard_exposure", "enum", "incoming", "守衛何時算暴露：incoming（有來襲才算，溢出一律算）／always", allowed=_EXPOSURE),
    _k("fill_mode", "mode", "off", "插隊：" + _MODE_NOTE),
    _k("transfer_mode", "mode", "off", "英雄道具庫轉資源（△ 鍵名）：" + _MODE_NOTE),
    _k("focus_mode", "enum", "off", "英雄產量加成切換：off／auto（△ 值域待 A6a2；目前 merge_settings 一律當 off）",
       allowed=_FOCUS),
    _k("oasis_mode", "mode", "off", "綠洲掃描（△ 鍵名）：" + _MODE_NOTE),
    _k("hero_mode", "mode", "off", "英雄冒險（△ 鍵名）：" + _MODE_NOTE),
    _k("market_mode", "mode", "off", "市場調度：" + _MODE_NOTE),
    _k("troop_mode", "mode", "off", "運兵：" + _MODE_NOTE),
    # ---- 英雄 ----
    _k("hero_min_health", "int", 45, "英雄體力 ≤ 這個數字不出發（讀不到也不出發）", min=0, max=100),
    _k("hero_hard_min_health", "int", 60, "體力 > 此數字才可選困難冒險（hero_allowed 含 hard 才有作用）", min=0, max=100),
    _k("hero_allowed", "csvset", "normal", "允許的冒險難度：normal 或 normal,hard", allowed=_HERO_ALLOWED),
    _k("hero_skip_on_incoming", "bool", True, "TRUE＝村莊有來襲時不派英雄"),
    _k("hero_transfer_min", "int", 20000, "需要轉的每種資源，道具庫存量都要 ≥ 此值才轉", min=0),
    _k("hero_transfer_max_gap", "int", 1000, "各資源缺口加總 > 此值就不轉", min=0),
    _k("hero_transfer_eta_min", "int", 45, "最快來襲 ETA ≤ 此分鐘數才處理", min=0),
    _k("hero_focus_min_hours", "float", 1.0, "「加成」兩次切換至少間隔幾小時（防搶加成不看此值）", min=0),
    _k("hero_guard_hidden", "int", 2000, "山洞每種資源隱藏量（守衛與插隊的來襲放寬用）", min=0),
    # ---- 插隊／躲兵參數 ----
    _k("fill_in_slack_min", "int", 0, "插隊允許把主目標開工時間拖慢幾分鐘，0＝不准", min=0),
    _k("hide_min_attack", "int", 20, "躲兵派出兵力攻擊力合計必須「大於」此數；沒列攻擊力的兵種算 0", min=0),
    _k("hide_wait_max_s", "int", 180, "躲兵：自己的兵在幾秒內歸來且來得及，就等到歸來再派；0＝不等", min=0),
    # ---- 市場（C7）----
    _k("market_max_per_ship", "int", 0, "每趟商人最多送多少，0＝不限", min=0),
    _k("market_min_ship", "int", 200, "太小不送（✗ 草案）", min=0),
    _k("market_reserve_hours", "float", 2.0, "捐方至少保留幾小時產量（✗ 草案）", min=0),
    _k("market_target_fill_pct", "int", 80, "受方補到容量幾 %（✗ 草案）", min=0, max=100),
    _k("market_max_ships_per_run", "int", 3, "每輪最多送幾趟（✗ 草案）", min=1),
)

_BY_KEY: Dict[str, KeySpec] = {s.key: s for s in KEYS}
ORDER: Tuple[str, ...] = tuple(s.key for s in KEYS)
DEFAULTS: Dict[str, Any] = {s.key: s.default for s in KEYS}
NOTES: Dict[str, str] = {s.key: s.note for s in KEYS}
REQUIRED_KEYS: Tuple[str, ...] = tuple(s.key for s in KEYS if s.required)
MODE_KEYS: Tuple[str, ...] = tuple(s.key for s in KEYS if s.kind == "mode")

# Config 鍵 → C9 VillageContext.modes 的鍵
MODE_TO_CTX: Dict[str, str] = {
    "fill_mode": "fill_in", "guard_mode": "guard", "transfer_mode": "item_transfer",
    "hide_mode": "hide", "oasis_mode": "oasis", "hero_mode": "hero",
    "market_mode": "market", "troop_mode": "troops",
}   # focus 的值域未定（見檔頭 3），merge_settings 另外固定填 'off'

# 舊 Config 鍵 → 新鍵說明（None＝不再使用）。config_repo 在邊界轉換；這裡只用來給出明確的警告。
LEGACY_KEY_MAP: Dict[str, Optional[str]] = {
    "hero_adventure": "hero_mode（舊 TRUE 對應 live、FALSE 對應 off）",
    "hero_transfer_mode": "transfer_mode（舊 incoming_only／always 的區分待 A6a2）",
    "hero_focus_mode": "focus_mode",
    "hero_guard_mode": "guard_mode＋guard_exposure（舊 incoming／always 改放 guard_exposure）",
    "fill_in_mode": "fill_mode（舊 on 改 live）",
    "map_size": "server_map_half（(邊長−1)÷2）",
    "village_id": "main_did",
    "home_x": None,
    "home_y": None,
}

# Config 鍵 → ServerProfile 欄位
_PROFILE_MAP: Dict[str, str] = {
    "server_id": "server_id", "server_base_url": "base_url", "tribe": "tribe",
    "server_start_utc": "start_utc", "server_tz": "server_tz", "server_speed": "speed",
    "server_map_half": "map_half", "server_protection_days": "protection_days",
    "server_locale": "locale",
}
_PROFILE_FIELD_TO_KEY = {v: k for k, v in _PROFILE_MAP.items()}


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _short(key: Any) -> str:
    text = str(key)
    return text if len(text) <= 60 else text[:59] + "…"


def _coerce(spec: KeySpec, value: Any) -> Any:
    """依 spec 轉型並檢查；不合法丟 ValueError(rule)，rule 是 type／range／enum／mode。"""
    kind = spec.kind
    try:
        if kind == "bool":
            out = serialize.from_cell(value, "bool")
        elif kind == "int":
            out = serialize.from_cell(value, "int")
        elif kind == "float":
            out = serialize.from_cell(value, "float")
        elif kind == "utc":
            out = serialize.from_cell(value, "utc")
        elif kind in ("str", "tribe"):
            out = serialize.from_cell(value, "str")
            if kind == "tribe" and isinstance(out, str):
                out = resolve_tribe(out) or out.lower()      # 讀入接受已登記的別名（高盧→gaul）
        elif kind == "enum":
            out = serialize.from_cell(value, "str")
            out = out.lower() if isinstance(out, str) else out
        elif kind == "csvset":
            out = serialize.from_cell(value, "str")
        else:
            raise AssertionError(kind)
    except serialize.SerializeError:
        raise ValueError("type") from None
    if kind in ("int", "float"):
        if spec.min is not None and out < spec.min or spec.max is not None and out > spec.max:
            raise ValueError("range")
    if kind in ("str", "tribe") and spec.max_len is not None and len(out) > spec.max_len:
        raise ValueError("range")
    if kind == "enum" and out not in spec.allowed:
        raise ValueError("enum")
    if kind == "csvset":
        tokens = [t.strip().lower() for t in out.split(",") if t.strip()]
        if not tokens or any(t not in spec.allowed for t in tokens):
            raise ValueError("enum")
        out = ",".join(t for t in spec.allowed if t in tokens)
    return out


def normalize_cfg(raw: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[CfgProblem]]:
    """原始 Config（鍵→儲存格值或已轉型的值）→ (已轉型且補齊預設的 cfg, 問題清單)。

    - 鍵去空白、轉小寫；未登記的鍵只警告（不進 cfg）。
    - 空白＝預設；required 鍵空白＝error（值 None）。
    - 型別／範圍／列舉不合法＝改用預設並回報（warn）；strict 鍵（server_*、tribe）不用預設頂替：error、值 None。
    - mode 鍵不合法一律 off 並回報（warn）。enabled 不合法＝FALSE 並回報（error）。
    - 訊息不含值。
    """
    if not isinstance(raw, Mapping):
        raise ValidationError("Config", "", None, "type")
    problems: List[CfgProblem] = []
    seen: Dict[str, Any] = {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        if key not in _BY_KEY:
            if key in LEGACY_KEY_MAP:
                target = LEGACY_KEY_MAP[key]
                msg = "舊鍵，已忽略；請改用 " + target if target else "舊鍵，新版不再使用，已忽略"
                problems.append(CfgProblem(_short(key), "warn", "legacy_key", msg))
            else:
                problems.append(CfgProblem(_short(key), "warn", "unregistered", "未登記的鍵，已忽略"))
            continue
        seen[key] = v
    cfg: Dict[str, Any] = {}
    for spec in KEYS:
        key = spec.key
        value = seen.get(key)
        if _blank(value):
            if spec.required:
                problems.append(CfgProblem(key, "error", "required", "缺少必填鍵"))
            cfg[key] = spec.default
            continue
        if spec.kind == "mode":
            mode, issue = parse_mode_checked(value, Mode.OFF)
            if issue:
                problems.append(CfgProblem(key, "warn", "mode", "mode 值不合法，視為 off"))
            cfg[key] = mode.value
            continue
        try:
            cfg[key] = _coerce(spec, value)
        except ValueError as exc:
            rule = str(exc)
            if key == "enabled":
                problems.append(CfgProblem(key, "error", rule, "enabled 看不懂，視為 FALSE（停止）"))
                cfg[key] = False
            elif spec.strict:
                problems.append(CfgProblem(key, "error", rule, "值不合法，且此鍵不可用預設頂替"))
                cfg[key] = None
            else:
                problems.append(CfgProblem(key, "warn", rule, "值不合法，已改用預設"))
                cfg[key] = spec.default
    # 跨鍵檢查
    tribe = cfg.get("tribe")
    if isinstance(tribe, str):
        if tribe not in TRIBES:
            problems.append(CfgProblem("tribe", "error", "unknown_tribe", "種族不在 TRIBES"))
        elif tribe != DEFAULT_TRIBE:
            problems.append(CfgProblem("tribe", "warn", "unverified_tribe",
                                       "非預設種族，資料尚未用遊戲樣本核對"))
    if (cfg["main_did"] is None) != (cfg["main_did_set_utc"] is None):
        problems.append(CfgProblem("main_did_set_utc", "error", "lock_incomplete",
                                   "main_did 與 main_did_set_utc 要同時有或同時空"))
    if cfg["schema_version"] > SCHEMA_VERSION:
        problems.append(CfgProblem("schema_version", "error", "schema_too_new", "Config 版本比本程式新，拒絕讀取"))
    cap = game_rules.resource_field_cap(bool(cfg["is_capital"]))
    if cap is not None and cfg["target_level"] > cap:
        problems.append(CfgProblem("target_level", "error", "level_over_cap", "超過非首都資源田上限"))
    return cfg, problems


def _profile_dict(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for key, field in _PROFILE_MAP.items():
        v = cfg.get(key)
        if v is not None:
            d[field] = v
        elif field == "protection_days":
            d[field] = None
    return d


def validate_cfg(cfg: Mapping[str, Any]) -> List[CfgProblem]:
    """回傳全部問題（空＝正常）。除了逐鍵檢查，必填都在且沒有 server_* 錯誤時，另用 C11 規則檢查
    （例如 base_url 格式、server_tz 格式）。"""
    norm, problems = normalize_cfg(cfg)
    blocked = any(p.severity == "error" and p.key in _PROFILE_MAP for p in problems)
    if not blocked:
        try:
            profile_from_dict(_profile_dict(norm), tribes=set(TRIBES))
        except ValidationError as exc:
            for e in exc.all:
                key = _PROFILE_FIELD_TO_KEY.get(e.field, e.field or "server")
                problems.append(CfgProblem(key, "error", e.rule, "不符合 ServerProfile 規則"))
    return problems


def profile_from_cfg(cfg: Mapping[str, Any]) -> ServerProfile:
    """Config → ServerProfile（C11）。server_* 與 tribe 的任何問題都丟 ValidationError，不用預設頂替。"""
    norm, problems = normalize_cfg(cfg)
    for p in problems:
        if p.severity == "error" and (p.key in _PROFILE_MAP or p.key == "schema_version"):
            raise ValidationError("ServerProfile", _PROFILE_MAP.get(p.key, p.key), None, p.rule)
    return profile_from_dict(_profile_dict(norm), tribes=set(TRIBES))


# ---------------------------------------------------------------- 單村合併
_MERGE_KEYS = ("tribe", "target_level", "queue_slots", "is_capital", "main_did", "main_did_set_utc", "schema_version")


def _pick_village(refs: Sequence[VillageRef], main_did: Optional[int]) -> VillageRef:
    refs = list(refs)
    if not refs:
        raise ValidationError("VillageContext", "refs", None, "no_village")
    if main_did is not None:
        for r in refs:
            if r.did == main_did:
                return r
        raise ValidationError("VillageContext", "main_did", None, "main_did_not_found")
    if len(refs) == 1:
        return refs[0]
    active = [r for r in refs if r.active]
    if len(active) != 1:
        raise ValidationError("VillageContext", "refs", None, "ambiguous_village")
    return active[0]


def merge_settings(cfg: Mapping[str, Any], village_rows: Optional[Sequence[VillageSettingsRow]],
                   refs: Sequence[VillageRef]) -> List[VillageContext]:
    """Config＋頁面讀到的村莊 → VillageContext 清單。

    A1b 只做單村模式（沒有 Villages 列）：village_rows 必須為空或 None，否則 NotImplementedError（B2）。
    選村：main_did 有填就找該村；否則只有一村用該村；否則要剛好一個 active 的村，不然 ValidationError。
    queue_slots 留空＝tribe_data 的基準條數（Plus 有效再 +1 由 stage 處理，common 層不知道 Plus）。
    is_capital 以 Config 為準（頁面目前讀不出首都；ref.is_capital 不參與）。modes 的 focus 固定 'off'（見檔頭 3）。
    驗證失敗丟 ValidationError（不靜默用預設）。
    """
    if village_rows:
        raise NotImplementedError("多村模式（Villages 列）由 B2 實作")
    c, problems = normalize_cfg(cfg)
    for p in problems:
        if p.severity == "error" and p.key in _MERGE_KEYS:
            raise ValidationError("Config", p.key, None, p.rule)
    spec = get_tribe(c["tribe"])
    ref = _pick_village(refs, c["main_did"])
    is_capital = bool(c["is_capital"])
    slots = c["queue_slots"] if c["queue_slots"] is not None else spec.base_queue_slots
    settings = BuildSettings(target_level=c["target_level"], queue_slots=slots,
                             build_order=c["build_order"] or None)
    ctx = VillageContext(
        did=ref.did, name=ref.name, x=ref.x, y=ref.y, is_capital=is_capital,
        role="capital" if is_capital else "resource", enabled=bool(c["enabled"]), priority=100,
        build_settings=settings,
        modes={**{ctx_key: c[cfg_key] for cfg_key, ctx_key in MODE_TO_CTX.items()}, "focus": "off"},
        hide_context=HideContext(home_x=ref.x, home_y=ref.y, oases=(), blocked=(), tribe=c["tribe"]))
    vctx = {"tribe": c["tribe"], "tribes": set(TRIBES), "is_capital": is_capital,
            "max_non_capital_level": game_rules.MAX_NON_CAPITAL_FIELD_LEVEL}
    settings.ensure_valid(vctx)
    ctx.ensure_valid(vctx)
    return [ctx]
