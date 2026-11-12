#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/gsheets.py（if-04）
版本：v0.1（A4a）
用途：Google Sheet 的連線與批次寫入。全 repo 只有這裡 import gspread（§4.1 補充規則 7）。
      不認得任何分頁格式（那是 *_repo 的事）；憑證與 Sheet ID 一律由參數傳入，不讀環境變數
      （讀 Secrets 的 helper 放 app 層，A6b）。
依賴：cm-10（serialize；只用來解析憑證 JSON，不在這裡自行解析 JSON）。
部署狀態：未部署（GA 前不 live）。

與舊 sheets_writer.py（✓ 已讀連線部分）的差異（交接區塊有列）
  1. 舊 has_sheet() 是「有沒有設定 Sheet」，現名 is_configured(raw_json, sheet_id)；
     卡片的 has_sheet(name) 是另一件事（分頁存在與否），現名 has_worksheet(sh, title)。
  2. 憑證與 Sheet ID 由參數傳入（舊版讀 GOOGLE_SERVICE_ACCOUNT_JSON／GOOGLE_SHEET_ID）。
  3. 新增 batch_write：append_rows 合併追加，或 update 寫指定區塊；只在 429 配額錯誤時重試。
  4. gspread、google-auth 在函式內才 import（CI 的 import 步驟只裝 bs4，寫在檔案最上面會紅燈）。
  5. 預設 value_input="RAW"（舊版 USER_ENTERED）：新格式的 UTC 時間字串與 "TRUE"／"FALSE" 要原樣
     存進儲存格，USER_ENTERED 會被 Sheet 自作主張轉成日期或布林，讀回來就不是原字串。
"""
import re
import time
from typing import Any, Callable, Optional, Sequence

from ...common import serialize

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
VALUE_INPUT_OPTIONS = ("RAW", "USER_ENTERED")
DEFAULT_BACKOFF_S = (10.0, 30.0, 60.0)      # 429 時依序等待；長度＝最多重試次數
_A1_START = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
_QUOTA_CODE = 429


def get_credentials(raw_json: Optional[str]) -> Any:
    """服務帳號 JSON 文字 → gspread Client。缺值或格式錯誤丟 RuntimeError（訊息不含內容）。"""
    if not isinstance(raw_json, str) or not raw_json.strip():
        raise RuntimeError("缺少服務帳號憑證（GOOGLE_SERVICE_ACCOUNT_JSON）")
    try:
        info = serialize.from_cell(raw_json, "json")
    except serialize.SerializeError:
        raise RuntimeError("服務帳號憑證不是合法 JSON") from None
    if not isinstance(info, dict):
        raise RuntimeError("服務帳號憑證格式不合法（需為 JSON 物件）")
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(info, scopes=list(SCOPES))
    return gspread.authorize(creds)


def open_sheet(client: Any, sheet_id: Optional[str]) -> Any:
    """以 Sheet ID 開啟試算表。"""
    if not isinstance(sheet_id, str) or not sheet_id.strip():
        raise RuntimeError("缺少 Sheet ID（GOOGLE_SHEET_ID_S2）")
    return client.open_by_key(sheet_id.strip())


def is_configured(raw_json: Optional[str], sheet_id: Optional[str]) -> bool:
    """憑證與 Sheet ID 是否都有值（舊 has_sheet；不連線）。"""
    return (isinstance(raw_json, str) and bool(raw_json.strip())
            and isinstance(sheet_id, str) and bool(sheet_id.strip()))


def has_worksheet(sh: Any, title: str) -> bool:
    """試算表有沒有這個分頁。其他錯誤（權限、網路）照丟，不當成「沒有」。"""
    from gspread.exceptions import WorksheetNotFound

    try:
        sh.worksheet(title)
    except WorksheetNotFound:
        return False
    return True


def _is_quota_error(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code == _QUOTA_CODE


def batch_write(ws: Any, rows: Sequence[Sequence[Any]], *, start: Optional[str] = None,
                value_input: str = "RAW", backoff_s: Sequence[float] = DEFAULT_BACKOFF_S,
                sleep: Callable[[float], None] = time.sleep) -> int:
    """一次寫入多列，回傳寫入列數。

    start=None：append_rows 合併追加（一個 API 請求）；
    start="A5"：update 從該儲存格起寫入（覆蓋該區塊）。
    格值只收 int／float／str（bool、None 等請先過 serialize.to_cell）。
    只在 429 配額錯誤時依 backoff_s 重試（被拒絕的請求沒寫入，重送安全）；其他錯誤立刻丟出、不重送。
    """
    if value_input not in VALUE_INPUT_OPTIONS:
        raise ValueError("value_input 只能是 RAW 或 USER_ENTERED")
    if start is not None and (not isinstance(start, str) or not _A1_START.match(start)):
        raise ValueError("start 需為 A1 格式的起始儲存格（例：A5）")
    data = [list(r) for r in rows]
    for r in data:
        for v in r:
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(f"儲存格值型別不合法（{type(v).__name__}）；請先用 serialize.to_cell")
    if not data:
        return 0

    waits = list(backoff_s)
    attempt = 0
    while True:
        try:
            if start is None:
                ws.append_rows(data, value_input_option=value_input)
            else:
                ws.update(range_name=start, values=data, value_input_option=value_input)
            return len(data)
        except Exception as exc:  # noqa: BLE001
            if not _is_quota_error(exc) or attempt >= len(waits):
                raise
            sleep(waits[attempt])
            attempt += 1
