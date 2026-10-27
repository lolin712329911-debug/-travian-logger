#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/serialize.py（cm-10）
版本：v0.1（A1a-1）
用途：唯一的格式化出口（§4.1 補充規則 7、§6.1）。其他模組不得自行 strftime／isoformat／
      json.dumps／json.loads 做持久化格式（check_arch 檢查）。
依賴：無（只用標準庫；與 schema 互不依賴）。
部署狀態：未部署（GA 前不 live）。

與卡片簽名的差異（交接區塊有列，請確認）：
  1. loads_checked(text, schema_name, validator=None, max_version=1)：卡片寫 (text, schema_name)，
     但 serialize 不得依賴 schema（四模組互不依賴），所以驗證函式由呼叫端注入
     （validator(schema_name, data) → 錯誤清單，空清單＝通過）。
  2. 另增：dumps_compact（Sheet 儲存格用）、res_to_cost_str／cost_str_to_res（C5 Actions.cost）、
     SerializeError、RES_SUFFIXES。
舊 sheets_writer 格式尚未回填（△，A4b）；本檔只實作 §6.1 目標格式。
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

RES_SUFFIXES = ("_wood", "_clay", "_iron", "_crop")
CELL_MAX_CHARS = 40000          # §6.1：Sheet 儲存格內 JSON ≤ 40000 字元
TRUNC_MARK = "…"                # 截斷標記（只在這裡加）

_UTC_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")
_COST_RE = re.compile(r"^\d+,\d+,\d+,\d+$")


class SerializeError(ValueError):
    """格式化／解析失敗。訊息不含原始內容（避免機密外洩）。"""


# ---------------------------------------------------------------- 時間
def to_utc_str(dt: datetime) -> str:
    """aware datetime → 'YYYY-MM-DDTHH:MM:SSZ'（轉 UTC、秒精度，微秒直接捨去）。

    naive datetime 一律拒絕（不得猜時區）。
    """
    if not isinstance(dt, datetime):
        raise SerializeError("to_utc_str 需要 datetime")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise SerializeError("to_utc_str 不接受 naive datetime（缺時區）")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    """'YYYY-MM-DDTHH:MM:SSZ' → aware UTC datetime。讀入去前後空白，其餘嚴格。"""
    if not isinstance(text, str):
        raise SerializeError("parse_utc 需要字串")
    m = _UTC_RE.match(text.strip())
    if not m:
        raise SerializeError("時間格式不是 YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime(*(int(g) for g in m.groups()), tzinfo=timezone.utc)
    except ValueError as exc:
        raise SerializeError("時間數值不合法") from exc


# ---------------------------------------------------------------- JSON
def dumps_stable(obj: Any) -> str:
    """檔案用：鍵排序、UTF-8（不跳脫中文）、2 空白縮排、LF、結尾換行。"""
    try:
        text = json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SerializeError("無法序列化為 JSON（型別或 NaN／Infinity）") from exc
    return text + "\n"


def dumps_compact(obj: Any, max_chars: int = CELL_MAX_CHARS) -> str:
    """Sheet 儲存格用：鍵排序、緊湊、不換行、≤ max_chars。超長丟錯，不截斷（截斷會讓 JSON 壞掉）。"""
    try:
        text = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SerializeError("無法序列化為 JSON（型別或 NaN／Infinity）") from exc
    if len(text) > max_chars:
        raise SerializeError(f"儲存格 JSON 超過 {max_chars} 字元")
    return text


Validator = Callable[[str, Any], Sequence[Any]]


def loads_checked(text: str, schema_name: str,
                  validator: Optional[Validator] = None,
                  max_version: int = 1) -> Dict[str, Any]:
    """讀 JSON 檔：去 BOM／前後空白、頂層必須是物件且有 int `schema_version`。

    - schema_version 非 int（含 bool）、< 1 → 拒絕。
    - schema_version > max_version（比自己新的 major）→ 拒絕（§6.1 版本）。
    - validator 有給時呼叫 validator(schema_name, data)，回傳非空清單就拒絕。
      （serialize 不依賴 schema，驗證函式由呼叫端傳入，例如 `schema.validate` 的包裝。）
    """
    if not isinstance(text, str):
        raise SerializeError("loads_checked 需要字串")
    body = text.lstrip("﻿").strip()
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise SerializeError(f"{schema_name}：不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise SerializeError(f"{schema_name}：頂層必須是物件")
    ver = data.get("schema_version")
    if isinstance(ver, bool) or not isinstance(ver, int) or ver < 1:
        raise SerializeError(f"{schema_name}：缺少或不合法的 schema_version（需為 int ≥ 1）")
    if ver > max_version:
        raise SerializeError(f"{schema_name}：schema_version {ver} 比本程式支援的 {max_version} 新，拒絕讀取")
    if validator is not None:
        errors = list(validator(schema_name, data))
        if errors:
            raise SerializeError(f"{schema_name}：驗證失敗（{len(errors)} 項；第一項：{errors[0]}）")
    return data


# ---------------------------------------------------------------- 資源
def _check_res(res: Any) -> List[int]:
    if not isinstance(res, (list, tuple)) or len(res) != 4:
        raise SerializeError("資源需為長度 4 的陣列（木、磚、鐵、穀）")
    out = []
    for v in res:
        if isinstance(v, bool) or not isinstance(v, int):
            raise SerializeError("資源每項需為整數")
        out.append(v)
    return out


def res_to_cells(res: Sequence[int], prefix: Optional[str] = None) -> Union[List[int], Dict[str, int]]:
    """[木,磚,鐵,穀] → 4 個儲存格值。有給 prefix 時回 {prefix_wood: .., ...}（鍵序固定）。"""
    vals = _check_res(res)
    if prefix is None:
        return vals
    return {prefix + suf: v for suf, v in zip(RES_SUFFIXES, vals)}


def cells_to_res(cells: Union[Sequence[Any], Dict[str, Any]], prefix: Optional[str] = None) -> List[int]:
    """res_to_cells 的反向。每格走 from_cell("int")，空白／缺值＝錯誤（資源不可為空）。"""
    if isinstance(cells, dict):
        if prefix is None:
            raise SerializeError("以 dict 讀資源時必須給 prefix")
        try:
            raw = [cells[prefix + suf] for suf in RES_SUFFIXES]
        except KeyError as exc:
            raise SerializeError("資源欄位缺少") from exc
    else:
        raw = list(cells)
        if len(raw) != 4:
            raise SerializeError("資源需為 4 個儲存格")
    out = []
    for c in raw:
        v = from_cell(c, "int")
        if v is None:
            raise SerializeError("資源儲存格不可為空")
        out.append(v)
    return out


def res_to_cost_str(res: Sequence[int]) -> str:
    """Actions.cost 專用：'木,磚,鐵,穀'（逗號、無空白；各項需 ≥ 0）。"""
    vals = _check_res(res)
    if any(v < 0 for v in vals):
        raise SerializeError("cost 不可為負")
    return ",".join(str(v) for v in vals)


def cost_str_to_res(text: str) -> List[int]:
    if not isinstance(text, str) or not _COST_RE.match(text.strip()):
        raise SerializeError("cost 格式需為 木,磚,鐵,穀（四個非負整數）")
    return [int(p) for p in text.strip().split(",")]


# ---------------------------------------------------------------- Sheet 儲存格
CELL_TYPES = ("int", "float", "str", "bool", "utc", "json")


def to_cell(value: Any, type_: str, max_len: Optional[int] = None) -> Union[int, float, str]:
    """程式值 → Sheet 儲存格值（寫出一律嚴格）。None → ""（空白）。

    int→int（不帶小數點）；float→float；bool→"TRUE"/"FALSE"；utc→字串（需已是合法 UTC 字串）；
    str→去換行（換成空白）、超過 max_len（預設 CELL_MAX_CHARS）截斷並加「…」；
    json→dumps_compact。
    """
    if type_ not in CELL_TYPES:
        raise SerializeError(f"未知儲存格型別：{type_}")
    if value is None:
        return ""
    if type_ == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SerializeError("int 欄需為整數")
        return value
    if type_ == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SerializeError("float 欄需為數字")
        f = float(value)
        if f != f or f in (float("inf"), float("-inf")):
            raise SerializeError("float 欄不可為 NaN／Infinity")
        return f
    if type_ == "bool":
        if not isinstance(value, bool):
            raise SerializeError("bool 欄需為 bool")
        return "TRUE" if value else "FALSE"
    if type_ == "utc":
        if isinstance(value, datetime):
            return to_utc_str(value)
        parse_utc(value)  # 驗證格式；不合法會丟 SerializeError
        return value.strip()
    if type_ == "json":
        return dumps_compact(value)
    # str
    if not isinstance(value, str):
        raise SerializeError("str 欄需為字串")
    text = value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    limit = CELL_MAX_CHARS if max_len is None else max_len
    if limit < 1:
        raise SerializeError("max_len 需 ≥ 1")
    if len(text) > limit:
        text = text[: max(limit - len(TRUNC_MARK), 0)] + TRUNC_MARK
        text = text[:limit]
    return text


def from_cell(cell: Any, type_: str, nullable: bool = True) -> Any:
    """Sheet 儲存格值 → 程式值（讀入可寬鬆：去前後空白、接受已登記同義寫法）。

    空白（None／""／純空白）→ None；但 type_ 為 "str" 且 nullable=False 時回 ""。
    bool 接受 TRUE／FALSE／true／false／1／0（及真正的 bool／整數 1／0），其他＝錯誤。
    int 接受整數、整數值的 float（Sheet API 常回 12.0）、純數字字串；
    帶小數點或千分位的字串＝錯誤。
    """
    if type_ not in CELL_TYPES:
        raise SerializeError(f"未知儲存格型別：{type_}")
    blank = cell is None or (isinstance(cell, str) and cell.strip() == "")
    if blank:
        if type_ == "str" and not nullable:
            return ""
        return None
    if type_ == "str":
        if not isinstance(cell, str):
            return str(cell)  # Sheet 可能把純數字字串當數字回傳
        return cell.strip()
    if type_ == "bool":
        if isinstance(cell, bool):
            return cell
        if isinstance(cell, int) and cell in (0, 1):
            return bool(cell)
        if isinstance(cell, str) and cell.strip() in ("TRUE", "FALSE", "true", "false", "1", "0"):
            return cell.strip() in ("TRUE", "true", "1")
        raise SerializeError("bool 儲存格需為 TRUE／FALSE／true／false／1／0")
    if type_ == "int":
        if isinstance(cell, bool):
            raise SerializeError("int 儲存格不可為 bool")
        if isinstance(cell, int):
            return cell
        if isinstance(cell, float):
            if cell.is_integer():
                return int(cell)
            raise SerializeError("int 儲存格不可帶小數")
        if isinstance(cell, str) and re.fullmatch(r"-?\d+", cell.strip()):
            return int(cell.strip())
        raise SerializeError("int 儲存格格式不合法（不可帶小數點或千分位）")
    if type_ == "float":
        if isinstance(cell, bool):
            raise SerializeError("float 儲存格不可為 bool")
        if isinstance(cell, (int, float)):
            return float(cell)
        if isinstance(cell, str) and re.fullmatch(r"-?\d+(\.\d+)?", cell.strip()):
            return float(cell.strip())
        raise SerializeError("float 儲存格格式不合法")
    if type_ == "utc":
        if not isinstance(cell, str):
            raise SerializeError("utc 儲存格需為字串")
        parse_utc(cell)
        return cell.strip()
    # json
    if not isinstance(cell, str):
        raise SerializeError("json 儲存格需為字串")
    try:
        return json.loads(cell.strip())
    except ValueError as exc:
        raise SerializeError("json 儲存格不是合法 JSON") from exc


# ---------------------------------------------------------------- 機密遮蔽
_MASK = "[REDACTED]"
_SENSITIVE_KEY = (r"(?:set-cookie|cookie|authorization|access[_-]?token|refresh[_-]?token|id[_-]?token|"
                  r"token|password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|private[_-]?key|"
                  r"seed[_-]?cookie|sess(?:ion)?[_-]?id|phpsessid)")

_REDACT_PATTERNS = [
    # PEM 私鑰區塊（Google 服務帳號 JSON 內嵌）
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), _MASK),
    # JSON 形式的 cookie 物件：{"name": "x", "value": "y"}
    (re.compile(r'("name"\s*:\s*"[^"]*"\s*,\s*"value"\s*:\s*)"[^"]*"'), r'\1"' + _MASK + '"'),
    # Cookie: / Set-Cookie: 整行（含 key=value; key=value）
    (re.compile(r"(?im)(?<![A-Za-z0-9])((?:set-)?cookie)(\s*[:=]\s*)[^\r\n]*"), r"\1\2" + _MASK),
    # Authorization: Bearer xxx／Bearer xxx
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer " + _MASK),
    # JSON 風格 "key": "value"（key 為敏感詞）
    (re.compile(r'(?i)("' + _SENSITIVE_KEY + r'"\s*:\s*)"[^"]*"'), r'\1"' + _MASK + '"'),
    # key=value／key: value（key 為敏感詞）
    (re.compile(r"(?i)(?<![A-Za-z0-9])(" + _SENSITIVE_KEY + r")(\s*[:=]\s*)(?!\[REDACTED\])[^\s\"',;&}\]]+"),
     r"\1\2" + _MASK),
    # JWT
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*"), _MASK),
    # 沒有 Cookie 標頭的原始 cookie 字串：兩組以上 name=value; name=value
    (re.compile(r"(?:[\w.\-]+=[^\s;,]{4,};\s*){1,}[\w.\-]+=[^\s;,]{4,}"), _MASK),
]


def redact(text: Any) -> str:
    """遮蔽 Cookie、token、密碼、私鑰（冪等）。非字串先轉 str。輸出文字（log／Sheet／錯誤）前必過。

    這是啟發式遮蔽，不保證抓到所有格式；真正的防線是「機密不進入任何輸出路徑」。
    """
    out = text if isinstance(text, str) else str(text)
    for pat, repl in _REDACT_PATTERNS:
        out = pat.sub(repl, out)
    return out
