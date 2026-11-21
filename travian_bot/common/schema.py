#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/schema.py（cm-11）
版本：v0.3（A6a1）｜對應契約 C-v0.7（全部 ✗ 草案，待 B1／B6 用真實樣本修正）
      v0.3 唯一變動：C2 VillageSnapshot 的 hidden 改為可為 null（D-32：山洞各級容量表沒有來源，未知＝null，不得用 0 充數）；
      v0.2（A2b）｜C-v0.6
      v0.2 唯一變動：C2 VillageSnapshot 的 units_home／units_away 鍵改為 u1～u10 或 hero（D-21②；與 TroopMovePlan.units 同一格式）；
      v0.1（A1a-1）｜C-v0.5
用途：機器可讀的契約規格（CONTRACT_SPECS，來源 §6.1／§6.2）與唯一的驗證入口。
依賴：無（只用標準庫；與 serialize 互不依賴，UTC 格式在此自行檢查）。
部署狀態：未部署（GA 前不 live）。

公開介面（卡片 cm-11）：
  CONTRACT_SPECS            契約名 → 欄位規格（涵蓋 C1～C12 與子結構）
  validate(name, data, ctx) → list[ValidationError]（空清單＝通過）
  ValidationError(contract, field, value, rule)、ParseError(page, reason)
  contract_examples()       → 合規／不合規範例（供 tools/check_contracts.py 與測試共用）
另增（交接區塊有列）：ensure_valid()（有錯就丟 ValidationError，並附 .all 全部錯誤）、
  CONTRACT_NAMES。

ctx（執行期情境，全部選填；沒給就略過對應檢查，不猜預設）：
  map_half               int   座標絕對值上限（C11 server_map_half）
  tribes                 集合  合法種族鍵（TRIBES 的鍵；由呼叫端從 tribe_data 取得，本檔不寫死）
  tribe                  str   ServerProfile.tribe（C9 檢查 hide_context.tribe 相符）
  capacity_each          int   商人單趟運量（C3 檢查 merchants_needed）
  max_non_capital_level  int   非首都資源田上限（BuildSettings）；與 is_capital 搭配
  is_capital             bool  該村是否首都（BuildSettings 用）
  action_names           集合  合法動作名稱（C5）
  strict                 bool  為真時，未登記欄位算錯誤（預設只忽略，容許未來追加欄位）

錯誤訊息不含欄位值（避免機密外洩）；value 只放在 ValidationError.value 屬性供程式取用。
"""
import math
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------- 例外
class ValidationError(Exception):
    """契約驗證失敗。str() 只含契約、欄位、規則名，不含值。"""

    def __init__(self, contract: str, field: str, value: Any, rule: str):
        super().__init__(contract, field, rule)
        self.contract = contract
        self.field = field
        self.value = value
        self.rule = rule
        self.all: List["ValidationError"] = [self]

    def __str__(self) -> str:
        return f"{self.contract}.{self.field}: {self.rule}" if self.field else f"{self.contract}: {self.rule}"


class ParseError(Exception):
    """頁面解析失敗（parsers 用；不得靜默回傳預設值）。"""

    def __init__(self, page: str, reason: str):
        super().__init__(page, reason)
        self.page = page
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.page}: {self.reason}"


# ---------------------------------------------------------------- 規格建構
MODES = ("off", "dry", "live")
RESULTS = ("ok", "dry", "skipped", "failed", "deferred")
STATUSES = ("ok", "skipped", "failed", "deferred")
ROLES = ("capital", "resource", "military", "other")
VERDICTS = ("proceed", "hold")
REJECT_RULES = ("bad_format", "unknown_building", "level_over_cap", "prereq_unmet", "missing_order")
CTX_MODE_KEYS = ("fill_in", "guard", "item_transfer", "focus", "hide", "oasis", "hero", "market", "troops")

_UTC_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")
_SENTINELS = frozenset({"-", "none", "null", "n/a"})


def _int(min=None, max=None, null=False, coord=False):
    return {"t": "int", "min": min, "max": max, "null": null, "coord": coord}


def _float(min=None, null=False):
    return {"t": "float", "min": min, "null": null}


def _str(max=None, min=0, pattern=None, null=False):
    return {"t": "str", "max": max, "min": min, "pattern": pattern, "null": null}


def _bool(null=False):
    return {"t": "bool", "null": null}


def _enum(values, null=False):
    return {"t": "enum", "values": tuple(values), "null": null}


def _utc(null=False):
    return {"t": "utc", "null": null}


def _res4(min=0, null=False):
    return {"t": "res4", "min": min, "null": null}


def _list(item, null=False):
    return {"t": "list", "item": item, "null": null}


def _dict(value, key_pattern=None, key_enum=None, min_len=0, null=False):
    return {"t": "dict", "value": value, "key_pattern": key_pattern, "key_enum": key_enum,
            "min_len": min_len, "null": null}


def _struct(name, null=False):
    return {"t": "struct", "name": name, "null": null}


def _any():
    return {"t": "any", "null": False}


# ---------------------------------------------------------------- 規則（跨欄位）
# 每條規則：f(data, ctx) → [(欄位, 規則名), ...]；只在該結構所有欄位型別都通過後才執行。
def _r_merchants(d, ctx):
    return [("free", "free_le_total")] if d["free"] > d["total"] else []


def _r_build_settings(d, ctx):
    cap = ctx.get("max_non_capital_level")
    if cap is not None and ctx.get("is_capital") is False and d["target_level"] > cap:
        return [("target_level", "level_over_cap")]
    return []


def _r_hide_context(d, ctx):
    tribes = ctx.get("tribes")
    if tribes is not None and d["tribe"] not in tribes:
        return [("tribe", "unknown_tribe")]
    return []


def _r_village_ref(d, ctx):
    return []


def _plan_ids_match(d, prefix):
    m = re.match(r"^" + prefix + r"\d{12}-(\d+)-(\d+)$", d["plan_id"])
    if m and (int(m.group(1)) != d["from_did"] or int(m.group(2)) != d["to_did"]):
        return [("plan_id", "plan_id_mismatch")]
    return []


def _r_transfer(d, ctx):
    out = []
    if d["from_did"] == d["to_did"]:
        out.append(("to_did", "same_village"))
    total = sum(d["amount"])
    if total <= 0:
        out.append(("amount", "empty_amount"))
    cap = ctx.get("capacity_each")
    if cap is not None and cap >= 1 and total > 0 and d["merchants_needed"] != math.ceil(total / cap):
        out.append(("merchants_needed", "merchants_mismatch"))
    out += _plan_ids_match(d, "T")
    return out


def _r_troop(d, ctx):
    out = []
    if d["from_did"] == d["to_did"]:
        out.append(("to_did", "same_village"))
    out += _plan_ids_match(d, "M")
    return out


def _r_action(d, ctx):
    out = []
    if d["mode"] == "dry" and d["result"] == "ok":
        out.append(("result", "dry_result_ok"))
    names = ctx.get("action_names")
    if names is not None and d["action"] not in names:
        out.append(("action", "unknown_action"))
    return out


def _r_lock(d, ctx):
    if (d["main_did"] is None) != (d["main_did_set_utc"] is None):
        return [("main_did_set_utc", "lock_incomplete")]
    return []


def _r_context(d, ctx):
    tribe = ctx.get("tribe")
    if tribe is not None and d["hide_context"]["tribe"] != tribe:
        return [("hide_context.tribe", "tribe_mismatch")]
    return []


def _r_stage(d, ctx):
    out = []
    if d["status"] == "failed" and d["note"].strip() == "":
        out.append(("note", "note_required_when_failed"))
    allowed = CONTRACT_SPECS["VillageSnapshot"]["fields"]
    for k in d["snapshot_updates"]:
        if k not in allowed:
            out.append(("snapshot_updates", "unknown_snapshot_field"))
            break
    return out


def _r_server(d, ctx):
    out = []
    if "@" in d["base_url"]:
        out.append(("base_url", "credentials_in_url"))
    tribes = ctx.get("tribes")
    if tribes is not None and d["tribe"] not in tribes:
        out.append(("tribe", "unknown_tribe"))
    return out


def _r_verdict(d, ctx):
    out = []
    rules = [r["rule"] for r in d["rejected"]]
    missing = "missing_order" in rules
    nxt = d["next_seq"]
    if missing and nxt is not None:
        out.append(("next_seq", "next_seq_must_be_null_when_missing_order"))
    if nxt is None and not missing:
        out.append(("next_seq", "null_next_seq_requires_missing_order"))
    should_hold = missing or (nxt is not None and any(r["seq"] == nxt for r in d["rejected"]))
    if (d["verdict"] == "hold") != should_hold:
        out.append(("verdict", "hold_mismatch"))
    return out


def _r_village_table(rows, ctx):
    out = []
    seen = set()
    caps = 0
    for i, r in enumerate(rows):
        if r["did"] in seen:
            out.append((f"[{i}].did", "duplicate_did"))
        seen.add(r["did"])
        if r["is_capital"]:
            caps += 1
            if caps > 1:
                out.append((f"[{i}].is_capital", "multiple_capital"))
    return out


# ---------------------------------------------------------------- 契約規格
_RES_POS = _res4(0)
_COORD = _int(coord=True)

CONTRACT_SPECS: Dict[str, Dict[str, Any]] = {
    # ---- 子結構 ----
    "BuildTarget": {"fields": {
        "aid": _int(1, 40), "gid": _int(1), "name": _str(40, 1),
        "to_level": _int(1), "cost": _RES_POS, "ready_in_s": _int(0)}, "rules": []},
    "Merchants": {"fields": {
        "free": _int(0), "total": _int(0), "capacity_each": _int(1)}, "rules": [_r_merchants]},
    "Transit": {"fields": {
        "from_did": _int(1, null=True), "to_did": _int(1), "amount": _RES_POS, "arrive_utc": _utc()},
        "rules": []},
    "Oasis": {"fields": {
        "x": _int(), "y": _int(), "kind": _str(20, 1), "safe": _bool(null=True)}, "rules": []},
    "BuildSettings": {"fields": {
        "target_level": _int(1), "queue_slots": _int(1, 3), "build_order": _str(null=True)},
        "rules": [_r_build_settings]},
    "HideContext": {"fields": {
        "home_x": _COORD, "home_y": _COORD, "oases": _list(_struct("Oasis")),
        "blocked": _list(_int(0)), "tribe": _str(40, 1)}, "rules": [_r_hide_context]},
    "PlanRejection": {"fields": {
        "seq": _int(1), "rule": _enum(REJECT_RULES), "reason": _str(200)}, "rules": []},
    # ---- C1 ----
    "VillageRef": {"fields": {
        "did": _int(1), "name": _str(60, 1), "x": _COORD, "y": _COORD,
        "is_capital": _bool(null=True), "active": _bool()}, "rules": [_r_village_ref]},
    # ---- C2 ----
    "VillageSnapshot": {"fields": {
        "did": _int(1), "ts_utc": _utc(), "stock": _res4(0), "prod": _res4(None),
        "cap_wh": _int(0), "cap_gr": _int(0), "hidden": _res4(0, null=True),
        "queue_free_in_s": _int(0), "queue_slots_used": _int(0),
        "next_target": _struct("BuildTarget", null=True),
        "merchants": _struct("Merchants", null=True),
        "incoming_res": _list(_struct("Transit")), "outgoing_res": _list(_struct("Transit")),
        "incoming_attacks": _int(0, null=True),
        "units_home": _dict(_int(1), key_pattern=r"^(u([1-9]|10)|hero)$", null=True),   # C-v0.6：鍵 u1～u10／hero（D-21②）
        "units_away": _dict(_int(1), key_pattern=r"^(u([1-9]|10)|hero)$", null=True)}, "rules": []},
    # ---- C3 ----
    "TransferPlan": {"fields": {
        "plan_id": _str(pattern=r"^T\d{12}-\d+-\d+$"), "from_did": _int(1), "to_did": _int(1),
        "amount": _RES_POS, "merchants_needed": _int(1), "arrive_utc": _utc(),
        "reason": _str(200), "mode": _enum(MODES)}, "rules": [_r_transfer]},
    # ---- C4 ----
    "TroopMovePlan": {"fields": {
        "plan_id": _str(pattern=r"^M\d{12}-\d+-\d+$"), "from_did": _int(1), "to_did": _int(1),
        "units": _dict(_int(1), key_pattern=r"^(u([1-9]|10)|hero)$", min_len=1),   # 鍵定義待 D-21（✗）
        "kind": _enum(("reinforce", "recall")), "arrive_utc": _utc(null=True),
        "reason": _str(200), "mode": _enum(MODES)}, "rules": [_r_troop]},
    # ---- C5 ----
    "ActionRow": {"fields": {
        "ts_utc": _utc(), "action": _str(40, 1), "aid": _int(1, null=True), "gid": _int(1, null=True),
        "level": _int(0, null=True), "cost": _str(pattern=r"^\d+,\d+,\d+,\d+$", null=True),
        "mode": _enum(MODES), "result": _enum(RESULTS), "detail": _str(300), "did": _int(1)},
        "rules": [_r_action]},
    # ---- C6 ----
    "VillageSettingsRow": {"fields": {
        "did": _int(1), "name": _str(60, 1), "enabled": _bool(), "role": _enum(ROLES),
        "is_capital": _bool(), "queue_slots": _int(1, 3), "build_order": _str(null=True),
        "hide_mode": _enum(MODES, null=True), "guard_mode": _enum(MODES, null=True),
        "fill_mode": _enum(MODES, null=True), "priority": _int(1, 999), "note": _str(200, null=True)},
        "rules": []},
    "VillageSettingsTable": {"table": "VillageSettingsRow", "rules": [_r_village_table]},
    # ---- C7（Config 鍵，§6.4）----
    "MarketConfig": {"fields": {
        "market_max_per_ship": _int(0), "market_min_ship": _int(0),
        "market_reserve_hours": _float(0), "market_target_fill_pct": _int(0, 100),
        "market_max_ships_per_run": _int(1)}, "rules": []},
    # ---- C8 ----
    "VillageLock": {"fields": {
        "main_did": _int(1, null=True), "main_did_set_utc": _utc(null=True)}, "rules": [_r_lock]},
    # ---- C9 ----
    "VillageContext": {"fields": {
        "did": _int(1), "name": _str(60, 1), "x": _COORD, "y": _COORD, "is_capital": _bool(),
        "role": _enum(ROLES), "enabled": _bool(), "priority": _int(1, 999),
        "build_settings": _struct("BuildSettings"),
        "modes": _dict(_enum(MODES), key_enum=CTX_MODE_KEYS),
        "hide_context": _struct("HideContext")}, "rules": [_r_context]},
    # ---- C10 ----
    "StageResult": {"fields": {
        "status": _enum(STATUSES), "actions": _list(_struct("ActionRow")),
        "snapshot_updates": _dict(_any()), "note": _str(200),
        "requests_used": _int(0), "elapsed_s": _float(0)}, "rules": [_r_stage]},
    # ---- C11 ----
    "ServerProfile": {"fields": {
        "server_id": _str(80, 1), "base_url": _str(pattern=r"^https://[^/\s]+/?$"),
        "game": _str(40, 1), "speed": _int(1), "map_half": _int(1), "tribe": _str(40, 1),
        "start_utc": _utc(), "server_tz": _str(pattern=r"^(UTC|[A-Za-z_]+/[A-Za-z_+\-0-9]+)$"),
        "protection_days": _int(0, null=True), "version": _str(20, null=True),
        "locale": _str(20, 1)}, "rules": [_r_server]},
    # ---- C12 ----
    "PlanVerdict": {"fields": {
        "did": _int(1), "checked_utc": _utc(), "verdict": _enum(VERDICTS),
        "next_seq": _int(1, null=True), "rejected": _list(_struct("PlanRejection"))},
        "rules": [_r_verdict]},
}

CONTRACT_NAMES = tuple(CONTRACT_SPECS)


# ---------------------------------------------------------------- 驗證引擎
def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_utc(v) -> bool:
    if not isinstance(v, str):
        return False
    m = _UTC_RE.match(v)
    if not m:
        return False
    try:
        datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return False
    return True


def _check_value(contract, spec, v, path, ctx, errs):
    def bad(rule):
        errs.append(ValidationError(contract, path, v, rule))

    if v is None:
        if not spec.get("null"):
            bad("required")
        return
    t = spec["t"]
    if t == "any":
        return
    if t == "int":
        if not _is_int(v):
            return bad("type")
        if spec["min"] is not None and v < spec["min"]:
            return bad("min")
        if spec["max"] is not None and v > spec["max"]:
            return bad("max")
        half = ctx.get("map_half")
        if spec.get("coord") and half is not None and abs(v) > half:
            return bad("map_range")
    elif t == "float":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return bad("type")
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return bad("type")
        if spec["min"] is not None and v < spec["min"]:
            return bad("min")
    elif t == "bool":
        if not isinstance(v, bool):
            bad("type")
    elif t == "str":
        if not isinstance(v, str):
            return bad("type")
        if len(v) < spec["min"]:
            return bad("min_len")
        if spec["max"] is not None and len(v) > spec["max"]:
            return bad("max_len")
        if spec["pattern"] and not re.match(spec["pattern"], v):
            return bad("pattern")
        if spec["null"] and v.strip().lower() in _SENTINELS:
            bad("no_sentinel")
    elif t == "enum":
        if not isinstance(v, str) or v not in spec["values"]:
            bad("enum")
    elif t == "utc":
        if not _check_utc(v):
            bad("utc_format")
    elif t == "res4":
        if not isinstance(v, (list, tuple)) or len(v) != 4:
            return bad("res4_length")
        for i, x in enumerate(v):
            if not _is_int(x):
                errs.append(ValidationError(contract, f"{path}[{i}]", x, "type"))
            elif spec["min"] is not None and x < spec["min"]:
                errs.append(ValidationError(contract, f"{path}[{i}]", x, "min"))
    elif t == "list":
        if not isinstance(v, (list, tuple)):
            return bad("type")
        for i, item in enumerate(v):
            _check_value(contract, spec["item"], item, f"{path}[{i}]", ctx, errs)
    elif t == "dict":
        if not isinstance(v, dict):
            return bad("type")
        if len(v) < spec["min_len"]:
            return bad("min_len")
        for k, item in v.items():
            if not isinstance(k, str):
                errs.append(ValidationError(contract, path, k, "key_type"))
                continue
            if spec["key_enum"] is not None and k not in spec["key_enum"]:
                errs.append(ValidationError(contract, path, k, "key_enum"))
            elif spec["key_pattern"] and not re.match(spec["key_pattern"], k):
                errs.append(ValidationError(contract, path, k, "key_pattern"))
            _check_value(contract, spec["value"], item, f"{path}.{k}", ctx, errs)
    elif t == "struct":
        _validate_struct(contract, spec["name"], v, f"{path}.", ctx, errs)
    else:  # 規格本身寫錯，屬於程式錯誤
        raise AssertionError(f"未知規格型別 {t}")


def _validate_struct(contract, struct_name, data, prefix, ctx, errs):
    spec = CONTRACT_SPECS[struct_name]
    if not isinstance(data, dict):
        errs.append(ValidationError(contract, prefix.rstrip("."), None, "type"))
        return
    start = len(errs)
    for fname, fspec in spec["fields"].items():
        path = prefix + fname
        if fname not in data:
            if not fspec.get("null"):
                errs.append(ValidationError(contract, path, None, "required"))
            continue
        _check_value(contract, fspec, data[fname], path, ctx, errs)
    if ctx.get("strict"):
        for k in data:
            if k not in spec["fields"]:
                errs.append(ValidationError(contract, prefix + str(k), None, "unknown_field"))
    if len(errs) == start:
        for rule in spec["rules"]:
            for field, rule_name in rule(data, ctx):
                errs.append(ValidationError(contract, prefix + field, _lookup(data, field), rule_name))


def _lookup(data, dotted):
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def validate(name: str, data: Any, ctx: Optional[Dict[str, Any]] = None) -> List[ValidationError]:
    """依契約名驗證資料，回傳錯誤清單（空＝通過）。未知契約名丟 KeyError（程式錯誤）。"""
    if name not in CONTRACT_SPECS:
        raise KeyError(f"未知契約：{name}")
    ctx = ctx or {}
    spec = CONTRACT_SPECS[name]
    errs: List[ValidationError] = []
    if "table" in spec:
        if not isinstance(data, (list, tuple)):
            return [ValidationError(name, "", None, "type")]
        for i, row in enumerate(data):
            _validate_struct(name, spec["table"], row, f"[{i}].", ctx, errs)
        if not errs:
            for rule in spec["rules"]:
                for field, rule_name in rule(data, ctx):
                    errs.append(ValidationError(name, field, None, rule_name))
        return errs
    _validate_struct(name, name, data, "", ctx, errs)
    return errs


def ensure_valid(name: str, data: Any, ctx: Optional[Dict[str, Any]] = None) -> None:
    """有錯誤就丟第一個 ValidationError（.all 帶全部）；通過則回 None。"""
    errs = validate(name, data, ctx)
    if errs:
        first = errs[0]
        first.all = errs
        raise first


# ---------------------------------------------------------------- 範例（合規＋不合規）
def _copy(x):
    if isinstance(x, dict):
        return {k: _copy(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_copy(v) for v in x]
    return x


_MISSING = object()


def _mut(base, path, value=_MISSING):
    """複製 base，把 path（'a.b[0].c' 形式，只支援 dict 鍵與 [i]）設成 value；value=_MISSING 表示刪除。"""
    out = _copy(base)
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur = out
    for p in parts[:-1]:
        cur = cur[int(p[1:-1])] if p.startswith("[") else cur[p]
    last = parts[-1]
    key = int(last[1:-1]) if last.startswith("[") else last
    if value is _MISSING:
        del cur[key]
    else:
        cur[key] = value
    return out


def contract_examples() -> Dict[str, Dict[str, List[Any]]]:
    """每個契約的合規與不合規範例。

    回傳 {契約名: {"valid": [{"data":…, "ctx":…}], "invalid": [{"data":…, "ctx":…, "field":…, "rule":…}]}}。
    不合規範例保證「錯誤清單中含 (field, rule)」。供 tools/check_contracts.py 與測試共用。
    範例資料為示意用，不含任何真實伺服器、帳號或憑證。
    """
    U = "2026-11-02T08:15:30Z"
    bt = {"aid": 5, "gid": 1, "name": "伐木場", "to_level": 3, "cost": [100, 80, 60, 40], "ready_in_s": 0}
    mer = {"free": 2, "total": 3, "capacity_each": 500}
    tr = {"from_did": 101, "to_did": 102, "amount": [100, 0, 0, 0], "arrive_utc": U}
    oa = {"x": 3, "y": -4, "kind": "wood25", "safe": None}
    bs = {"target_level": 10, "queue_slots": 1, "build_order": None}
    hc = {"home_x": 0, "home_y": 0, "oases": [oa], "blocked": [0], "tribe": "gaul"}
    ref = {"did": 101, "name": "主村", "x": 0, "y": 0, "is_capital": None, "active": True}
    snap = {"did": 101, "ts_utc": U, "stock": [500, 500, 500, 500], "prod": [10, 10, 10, -2],
            "cap_wh": 800, "cap_gr": 800, "hidden": [0, 0, 0, 0], "queue_free_in_s": 0,
            "queue_slots_used": 0, "next_target": bt, "merchants": None, "incoming_res": [tr],
            "outgoing_res": [], "incoming_attacks": None, "units_home": None, "units_away": None}
    xfer = {"plan_id": "T202611020815-101-102", "from_did": 101, "to_did": 102,
            "amount": [600, 0, 0, 0], "merchants_needed": 2, "arrive_utc": U,
            "reason": "補糧", "mode": "dry"}
    troop = {"plan_id": "M202611020815-101-102", "from_did": 101, "to_did": 102,
             "units": {"u1": 10, "hero": 1}, "kind": "reinforce", "arrive_utc": None,
             "reason": "增援", "mode": "dry"}
    act = {"ts_utc": U, "action": "調度資源", "aid": None, "gid": None, "level": None, "cost": None,
           "mode": "dry", "result": "dry", "detail": "", "did": 101}
    vrow = {"did": 101, "name": "主村", "enabled": True, "role": "resource", "is_capital": False,
            "queue_slots": 1, "build_order": None, "hide_mode": None, "guard_mode": None,
            "fill_mode": None, "priority": 100, "note": None}
    vrow2 = dict(vrow, did=102, name="二村", is_capital=True, role="capital")
    market = {"market_max_per_ship": 0, "market_min_ship": 200, "market_reserve_hours": 2.0,
              "market_target_fill_pct": 80, "market_max_ships_per_run": 3}
    lock = {"main_did": 101, "main_did_set_utc": U}
    vctx = {"did": 101, "name": "主村", "x": 0, "y": 0, "is_capital": False, "role": "resource",
            "enabled": True, "priority": 100, "build_settings": bs,
            "modes": {"hide": "off", "guard": "dry"}, "hide_context": hc}
    stage = {"status": "ok", "actions": [act], "snapshot_updates": {"stock": [1, 2, 3, 4]},
             "note": "", "requests_used": 3, "elapsed_s": 1.25}
    prof = {"server_id": "example-s1", "base_url": "https://example.invalid", "game": "legends",
            "speed": 1, "map_half": 200, "tribe": "gaul", "start_utc": U, "server_tz": "Europe/London",
            "protection_days": None, "version": None, "locale": "zh-TW"}
    rej = {"seq": 3, "rule": "prereq_unmet", "reason": "主建築等級不足"}
    verdict_ok = {"did": 101, "checked_utc": U, "verdict": "proceed", "next_seq": 3, "rejected": []}
    verdict_hold = {"did": 101, "checked_utc": U, "verdict": "hold", "next_seq": 3, "rejected": [rej]}
    verdict_missing = {"did": 101, "checked_utc": U, "verdict": "hold", "next_seq": None,
                       "rejected": [{"seq": 1, "rule": "missing_order", "reason": "沒有 build_order"}]}

    def V(data, ctx=None):
        return {"data": data, "ctx": ctx or {}}

    def I(data, field, rule, ctx=None):
        return {"data": data, "ctx": ctx or {}, "field": field, "rule": rule}

    ex: Dict[str, Dict[str, List[Any]]] = {}
    ex["BuildTarget"] = {"valid": [V(bt)], "invalid": [
        I(_mut(bt, "aid", 41), "aid", "max"),
        I(_mut(bt, "cost", [1, 2, 3]), "cost", "res4_length"),
        I(_mut(bt, "cost", [1, -2, 3, 4]), "cost[1]", "min"),
        I(_mut(bt, "name", _MISSING), "name", "required")]}
    ex["Merchants"] = {"valid": [V(mer)], "invalid": [
        I(_mut(mer, "free", 4), "free", "free_le_total"),
        I(_mut(mer, "capacity_each", 0), "capacity_each", "min")]}
    ex["Transit"] = {"valid": [V(tr), V(_mut(tr, "from_did", None))], "invalid": [
        I(_mut(tr, "arrive_utc", "2026-11-02 08:15:30"), "arrive_utc", "utc_format"),
        I(_mut(tr, "to_did", _MISSING), "to_did", "required")]}
    ex["Oasis"] = {"valid": [V(oa)], "invalid": [
        I(_mut(oa, "kind", "x" * 21), "kind", "max_len"),
        I(_mut(oa, "x", "3"), "x", "type")]}
    ex["BuildSettings"] = {"valid": [V(bs)], "invalid": [
        I(_mut(bs, "queue_slots", 4), "queue_slots", "max"),
        I(_mut(bs, "target_level", 11), "target_level", "level_over_cap",
          {"is_capital": False, "max_non_capital_level": 10}),
        I(_mut(bs, "build_order", "none"), "build_order", "no_sentinel")]}
    ex["HideContext"] = {"valid": [V(hc)], "invalid": [
        I(_mut(hc, "blocked", [-1]), "blocked[0]", "min"),
        I(_mut(hc, "tribe", "nobody"), "tribe", "unknown_tribe", {"tribes": {"gaul"}}),
        I(_mut(hc, "home_x", 201), "home_x", "map_range", {"map_half": 200})]}
    ex["PlanRejection"] = {"valid": [V(rej)], "invalid": [
        I(_mut(rej, "rule", "BAD_FORMAT"), "rule", "enum"),
        I(_mut(rej, "reason", "x" * 201), "reason", "max_len")]}
    ex["VillageRef"] = {"valid": [V(ref), V(_mut(ref, "is_capital", True))], "invalid": [
        I(_mut(ref, "did", 0), "did", "min"),
        I(_mut(ref, "x", 250), "x", "map_range", {"map_half": 200}),
        I(_mut(ref, "active", 1), "active", "type")]}
    ex["VillageSnapshot"] = {"valid": [V(snap), V(_mut(snap, "merchants", mer)), V(_mut(snap, "hidden", None))], "invalid": [
        I(_mut(snap, "stock", [1, 2, 3, -4]), "stock[3]", "min"),
        I(_mut(snap, "ts_utc", "2026-13-40T00:00:00Z"), "ts_utc", "utc_format"),
        I(_mut(snap, "next_target.cost", [1, 2, 3]), "next_target.cost", "res4_length"),
        I(_mut(snap, "units_home", {"u1": 0}), "units_home.u1", "min"),
        I(_mut(snap, "queue_free_in_s", -1), "queue_free_in_s", "min"),
        I(_mut(snap, "hidden", [0, 0, 0, -1]), "hidden[3]", "min")]}
    ex["TransferPlan"] = {"valid": [V(xfer, {"capacity_each": 500})], "invalid": [
        I(_mut(xfer, "to_did", 101), "to_did", "same_village"),
        I(_mut(xfer, "amount", [0, 0, 0, 0]), "amount", "empty_amount"),
        I(_mut(xfer, "merchants_needed", 3), "merchants_needed", "merchants_mismatch", {"capacity_each": 500}),
        I(_mut(xfer, "plan_id", "T2026110208-101-102"), "plan_id", "pattern"),
        I(_mut(xfer, "plan_id", "T202611020815-101-103"), "plan_id", "plan_id_mismatch"),
        I(_mut(xfer, "mode", "LIVE"), "mode", "enum")]}
    ex["TroopMovePlan"] = {"valid": [V(troop)], "invalid": [
        I(_mut(troop, "units", {}), "units", "min_len"),
        I(_mut(troop, "units", {"u11": 1}), "units", "key_pattern"),
        I(_mut(troop, "kind", "attack"), "kind", "enum"),
        I(_mut(troop, "to_did", 101), "to_did", "same_village")]}
    ex["ActionRow"] = {"valid": [V(act), V(_mut(_mut(act, "mode", "live"), "result", "ok"))], "invalid": [
        I(_mut(act, "result", "ok"), "result", "dry_result_ok"),
        I(_mut(act, "cost", "1,2,3"), "cost", "pattern"),
        I(_mut(act, "detail", "x" * 301), "detail", "max_len"),
        I(_mut(act, "did", _MISSING), "did", "required"),
        I(_mut(act, "action", "亂寫"), "action", "unknown_action", {"action_names": {"調度資源"}})]}
    ex["VillageSettingsRow"] = {"valid": [V(vrow)], "invalid": [
        I(_mut(vrow, "priority", 0), "priority", "min"),
        I(_mut(vrow, "role", "boss"), "role", "enum"),
        I(_mut(vrow, "enabled", "TRUE"), "enabled", "type"),
        I(_mut(vrow, "guard_mode", "maybe"), "guard_mode", "enum")]}
    ex["VillageSettingsTable"] = {"valid": [V([vrow, vrow2])], "invalid": [
        I([vrow, _mut(vrow2, "did", 101)], "[1].did", "duplicate_did"),
        I([_mut(vrow, "is_capital", True), vrow2], "[1].is_capital", "multiple_capital"),
        I({"not": "a list"}, "", "type")]}
    ex["MarketConfig"] = {"valid": [V(market)], "invalid": [
        I(_mut(market, "market_target_fill_pct", 101), "market_target_fill_pct", "max"),
        I(_mut(market, "market_max_ships_per_run", 0), "market_max_ships_per_run", "min"),
        I(_mut(market, "market_reserve_hours", -0.5), "market_reserve_hours", "min")]}
    ex["VillageLock"] = {"valid": [V(lock), V({"main_did": None, "main_did_set_utc": None})], "invalid": [
        I(_mut(lock, "main_did_set_utc", None), "main_did_set_utc", "lock_incomplete"),
        I(_mut(lock, "main_did", 0), "main_did", "min")]}
    ex["VillageContext"] = {"valid": [V(vctx, {"tribe": "gaul"})], "invalid": [
        I(_mut(vctx, "modes", {"build": "live"}), "modes", "key_enum"),
        I(_mut(vctx, "modes", {"hide": "on"}), "modes.hide", "enum"),
        I(_mut(vctx, "hide_context.tribe", "other"), "hide_context.tribe", "tribe_mismatch", {"tribe": "gaul"}),
        I(_mut(vctx, "build_settings.queue_slots", 0), "build_settings.queue_slots", "min")]}
    ex["StageResult"] = {"valid": [V(stage)], "invalid": [
        I(_mut(_mut(stage, "status", "failed"), "note", ""), "note", "note_required_when_failed"),
        I(_mut(stage, "snapshot_updates", {"nope": 1}), "snapshot_updates", "unknown_snapshot_field"),
        I(_mut(stage, "elapsed_s", -1), "elapsed_s", "min"),
        I(_mut(stage, "actions[0].result", "weird"), "actions[0].result", "enum")]}
    ex["ServerProfile"] = {"valid": [V(prof, {"tribes": {"gaul"}})], "invalid": [
        I(_mut(prof, "base_url", "http://example.invalid"), "base_url", "pattern"),
        I(_mut(prof, "base_url", "https://example.invalid/path"), "base_url", "pattern"),
        I(_mut(prof, "base_url", "https://user:pw@example.invalid"), "base_url", "credentials_in_url"),
        I(_mut(prof, "server_tz", "Taipei"), "server_tz", "pattern"),
        I(_mut(prof, "speed", 0), "speed", "min"),
        I(_mut(prof, "tribe", "nobody"), "tribe", "unknown_tribe", {"tribes": {"gaul"}})]}
    ex["PlanVerdict"] = {"valid": [V(verdict_ok), V(verdict_hold), V(verdict_missing)], "invalid": [
        I(_mut(verdict_hold, "verdict", "proceed"), "verdict", "hold_mismatch"),
        I(_mut(verdict_ok, "verdict", "hold"), "verdict", "hold_mismatch"),
        I(_mut(verdict_ok, "next_seq", None), "next_seq", "null_next_seq_requires_missing_order"),
        I(_mut(verdict_missing, "next_seq", 1), "next_seq", "next_seq_must_be_null_when_missing_order"),
        I(_mut(verdict_ok, "verdict", "maybe"), "verdict", "enum")]}
    return ex
