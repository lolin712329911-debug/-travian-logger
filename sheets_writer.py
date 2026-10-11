#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets 写入模块

通过 Google Service Account（服务账号）向指定表格追加一行数据。
在 GitHub Actions 里运行时，服务账号的 JSON 凭据通过环境变量
GOOGLE_SERVICE_ACCOUNT_JSON（整段 JSON 文本）传入。

首次设置步骤（一次性）：
1. 打开 https://console.cloud.google.com/ 新建一个项目（或用现有的）
2. 左侧菜单 "APIs & Services" -> "Library"，搜索并启用：
   - Google Sheets API
3. "APIs & Services" -> "Credentials" -> "Create Credentials" -> "Service account"
   随便起个名字，创建完成后点进去，"Keys" 标签 -> "Add Key" -> "Create new key"
   -> 选 JSON -> 下载。这个 JSON 文件里有个 client_email 字段，形如
   xxx@xxx.iam.gserviceaccount.com
4. 打开你要写入的 Google Sheet，点右上角"共享"，把上面那个 client_email
   添加为"编辑者"（这一步很关键，不然服务账号没权限写入）
5. 把下载的整个 JSON 文件内容，复制粘贴进 GitHub 仓库的
   Settings -> Secrets and variables -> Actions -> New repository secret，
   名字设为 GOOGLE_SERVICE_ACCOUNT_JSON
6. 表格的 ID 是网址里 /d/ 和 /edit 之间那一串字符，例如：
   https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^ 这段
   同样存成 secret，名字设为 GOOGLE_SHEET_ID
"""

from __future__ import annotations

import json
import os
from typing import Optional

from notify import notify
from travian_const import DEFAULT_TARGET_BUILDING_LEVEL


HEADER_ROW = [
    "抓取時間(UTC)", "伺服器時間", "村莊名", "人口", "忠誠度%",
    "金幣", "銀幣",
    "木材_存量", "木材_產量", "磚塊_存量", "磚塊_產量",
    "鋼鐵_存量", "鋼鐵_產量", "穀物_存量", "穀物_產量", "自由穀物",
    "英雄血量%", "英雄經驗%", "英雄可用冒險數",
    "施工佇列", "Plus剩餘(小時)", "新手保護剩餘(小時)",
    "來襲波數", "最快來襲剩餘(分)",
]


def _get_credentials(service_account_json: Optional[str] = None):
    """
    从环境变量或传入字符串获取服务账号凭据，返回 gspread 可用的 Client。
    service_account_json: 整段 JSON 文本；若为 None 则从环境变量
    GOOGLE_SERVICE_ACCOUNT_JSON 读取。
    """
    import gspread
    from google.oauth2.service_account import Credentials

    raw = service_account_json or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError(
            "缺少服务账号凭据：请设置环境变量 GOOGLE_SERVICE_ACCOUNT_JSON "
            "（整段 JSON 文本），或在调用时传入 service_account_json 参数。"
        )

    info = json.loads(raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def append_row(
    row: list,
    sheet_id: Optional[str] = None,
    worksheet_name: str = "Sheet1",
    service_account_json: Optional[str] = None,
    ensure_header: bool = True,
):
    """
    向指定 Google Sheet 的某个分页追加一行数据。
    如果分页是空的且 ensure_header=True，会先写入表头行。

    sheet_id: 表格 ID；若为 None 则从环境变量 GOOGLE_SHEET_ID 读取
    """
    client = _get_credentials(service_account_json)

    sid = sheet_id or os.environ.get("GOOGLE_SHEET_ID")
    if not sid:
        raise RuntimeError(
            "缺少表格 ID：请设置环境变量 GOOGLE_SHEET_ID，"
            "或在调用时传入 sheet_id 参数。"
        )

    spreadsheet = client.open_by_key(sid)

    try:
        ws = spreadsheet.worksheet(worksheet_name)
    except Exception:
        # 分页不存在则新建
        ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(HEADER_ROW) + 2)

    if ensure_header:
        first = ws.row_values(1)
        if not first:
            ws.append_row(HEADER_ROW, value_input_option="USER_ENTERED")
        elif first != HEADER_ROW:
            # 舊版表頭（欄位比較少）：補欄並把第 1 列更新成最新表頭，舊資料列不動
            if ws.col_count < len(HEADER_ROW):
                ws.add_cols(len(HEADER_ROW) - ws.col_count)
            ws.update(range_name="A1", values=[HEADER_ROW])

    ws.append_row(row, value_input_option="USER_ENTERED")
    return True


# ---------------- Config / Actions 分頁（原本在 runner.py）----------------
def has_sheet() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_SHEET_ID"))


def open_sheet():
    """開啟 GOOGLE_SHEET_ID 指定的試算表（原 runner._sheet）。"""
    return _get_credentials().open_by_key(os.environ["GOOGLE_SHEET_ID"])


_FALSE_WORDS = ("false", "0", "no", "off", "否", "停")


# Config 分頁的預設列（順序 = 補上去時的順序）。C 欄是給人看的說明，程式只讀 A、B 欄。
_CONFIG_ORDER = ("enabled", "target_level", "queue_slots", "is_capital",
                 "max_builds", "target_building_level", "build_order")
_CONFIG_NOTES = {
    "enabled": "FALSE = 緊急停止；session 失效時程式也會改成 FALSE",
    "target_level": "資源田升到幾級（沒設 build_order 時使用）",
    "queue_slots": "留空 = 自動偵測；填數字 = 手動指定",
    "is_capital": "首都才填 TRUE",
    "max_builds": "每輪最多送出幾個升級",
    "target_building_level": "倉庫／糧倉升到幾級，0 = 停用",
    "build_order": "建城順序，例如 res:2,10:3,15:5",
}


def _default_cfg() -> dict:
    return {"enabled": True, "target_level": 2, "queue_slots": None, "max_builds": 2,
            "target_building_level": DEFAULT_TARGET_BUILDING_LEVEL, "build_order": "", "is_capital": False}


def _cfg_cell(v) -> str:
    """預設值轉成要寫進儲存格的純文字。"""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def _ensure_config_rows(ws, existing_rows: list) -> None:
    """Config 缺哪一列就補哪一列（只補缺的，已有的列不覆蓋）。
    existing_rows 是 load_config() 本來就讀進來的資料，不多打請求；
    沒有缺列時完全不寫入。用 raw=True 寫純文字，避免 build_order 之類的值被 Sheets 誤判成時間。"""
    have = {r[0].strip().lower() for r in existing_rows if r}
    defaults = _default_cfg()
    missing = [[k, _cfg_cell(defaults[k]), _CONFIG_NOTES[k]] for k in _CONFIG_ORDER if k not in have]
    if not missing:
        return
    start = len(existing_rows) + 1                 # 寫在既有資料的最後一列之後
    need_rows = start + len(missing) - 1
    if ws.row_count < need_rows:
        ws.add_rows(need_rows - ws.row_count)
    if ws.col_count < 3:                           # disable() 建的 Config 只有 2 欄，C 欄要先補
        ws.add_cols(3 - ws.col_count)
    ws.update(range_name=f"A{start}", values=missing, raw=True)
    print(f"Config 補上缺少的 {len(missing)} 列：{', '.join(r[0] for r in missing)}")


def load_config() -> dict:
    """讀 Sheet 的 Config 分頁；沒有這個分頁就用預設值（不是錯誤），並順手建立分頁、補齊預設列。
    分頁存在但缺列時，只補缺的列，不覆蓋已填的值。補齊失敗（例如權限問題）只印 log，不影響本輪。
    真正的異常（憑證、網路等）會往外拋，讓呼叫端中止本輪。"""
    from gspread.exceptions import WorksheetNotFound

    cfg = _default_cfg()
    if not has_sheet():
        return cfg
    sh = open_sheet()
    try:
        ws = sh.worksheet("Config")
    except WorksheetNotFound:
        print("Sheet 裡沒有 Config 分頁，使用預設值，並建立分頁")
        try:
            _ensure_config_rows(sh.add_worksheet("Config", 20, 3), [])
        except Exception as e:
            print(f"建立 Config 分頁失敗（不影響本輪，使用預設值）: {e!r}")
        return cfg
    rows = ws.get_all_values()
    for row in rows:
        if len(row) < 2:
            continue
        k, v = row[0].strip().lower(), row[1].strip()
        if k in ("enabled", "is_capital"):
            cfg[k] = v.lower() not in _FALSE_WORDS
        elif k == "build_order":
            cfg[k] = v
        elif k in ("target_level", "queue_slots", "max_builds", "target_building_level") and v.isdigit():
            cfg[k] = int(v)
    try:
        _ensure_config_rows(ws, rows)
    except Exception as e:
        print(f"補齊 Config 預設列失敗（不影響本輪）: {e!r}")
    return cfg


ACTIONS_HEADER = ["時間(UTC)", "動作", "slot", "gid", "目前等級", "成本", "模式", "結果", "升級項目 / 說明"]
_actions_header_ok = False


def log_action(row: list):
    global _actions_header_ok
    if not has_sheet():
        return
    try:
        sh = open_sheet()
        try:
            ws = sh.worksheet("Actions")
        except Exception:
            ws = sh.add_worksheet("Actions", 1000, len(ACTIONS_HEADER) + 1)
            ws.append_row(ACTIONS_HEADER)
            _actions_header_ok = True
        if not _actions_header_ok:
            # 舊分頁只有 8 欄：補欄並更新表頭，舊資料列不動
            if ws.row_values(1) != ACTIONS_HEADER:
                if ws.col_count < len(ACTIONS_HEADER):
                    ws.add_cols(len(ACTIONS_HEADER) - ws.col_count)
                ws.update(range_name="A1", values=[ACTIONS_HEADER])
            _actions_header_ok = True
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"寫入 Actions 分頁失敗（不影響升級）: {e!r}")


STATE_HEADER = ["項目(key)", "值", "說明", "更新時間(UTC)"]


def write_state(rows: list, updated: str) -> bool:
    """把玩家／村莊狀態（文化點、倉庫容量…）整份覆蓋寫到「state」分頁，給 Apps Script / Gemini 讀。
    rows 是 [(key, 值, 說明), ...]；覆蓋式（不是追加），所以分頁永遠只有最新一份。
    用 raw 寫入純值，避免日期字串被 Sheets 轉型。失敗只印 log、不影響升級；回傳是否成功。"""
    if not has_sheet():
        return False
    try:
        from gspread.exceptions import WorksheetNotFound
        sh = open_sheet()
        try:
            ws = sh.worksheet("state")
        except WorksheetNotFound:
            ws = sh.add_worksheet("state", 60, len(STATE_HEADER))
        values = [STATE_HEADER] + [[k, v, note, updated] for k, v, note in rows]
        ws.clear()
        ws.update(range_name="A1", values=values, raw=True)
        return True
    except Exception as e:
        print(f"寫入 state 分頁失敗（不影響升級）: {e!r}")
        return False


def disable(reason: str):
    """偵測到 session / Cookie 失效等需要人工介入的狀況時呼叫：
    把 Config 的 enabled 設成 FALSE，讓之後每一輪一讀到 cfg 就直接跳過，
    不會再嘗試登入、也不會每 30 分鐘重複失敗。要恢復請手動把 enabled 改回 TRUE。
    沒有連 Sheet 時沒辦法持久化，下一輪還是會照樣重試。"""
    notify(reason)
    if not has_sheet():
        print("沒有連 Google Sheet，無法自動停用，下一輪還會再試一次")
        return
    from gspread.exceptions import WorksheetNotFound
    try:
        sh = open_sheet()
        try:
            ws = sh.worksheet("Config")
        except WorksheetNotFound:
            ws = sh.add_worksheet("Config", 10, 2)
        rows = ws.get_all_values()
        for i, row in enumerate(rows, start=1):
            if row and row[0].strip().lower() == "enabled":
                ws.update(range_name=f"B{i}", values=[["FALSE"]])
                break
        else:
            ws.append_row(["enabled", "FALSE"])
        print("已將 Config 的 enabled 設為 FALSE，排程會自動跳過，直到手動改回 TRUE")
    except Exception as e:
        print(f"嘗試寫入 Config 停用失敗（不影響本輪判定為失敗）: {e!r}")
