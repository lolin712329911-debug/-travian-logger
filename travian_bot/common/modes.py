#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/modes.py（cm-04）
版本：v0.1（A1a-1）
用途：寫入類動作的模式（off／dry／live）。純函式，不讀環境變數（由 app/main 讀 DRY_RUN
      後以 bool 傳入，v0.22／A-8）。
依賴：無（只用標準庫）。
部署狀態：未部署（GA 前不 live）。

規則來源：§6.1「寫入類 mode 值不合法一律視為 off 並回報」、§6.4「空白＝用 Config／預設」、
          §4.1 規則 12／A-9「DRY_RUN=1 時 live 降為 dry」。
注意：卡片寫「沿用 runner.py `_guard_mode`／`_fill_mode` 判斷規則」，但本 WP 沒有收到
      runner.py，規則取自契約文字，尚未與舊函式輸出做 golden 比對（✗）。
"""
from enum import Enum
from typing import Optional, Tuple, Union


class Mode(str, Enum):
    OFF = "off"
    DRY = "dry"
    LIVE = "live"


ModeLike = Union[Mode, str, None]


def parse_mode_checked(value: ModeLike, default: Mode = Mode.OFF) -> Tuple[Mode, Optional[str]]:
    """解析 mode 字串，回傳 (Mode, 問題說明或 None)。

    - None 或空白字串 → default（「空白＝用預設」），不算問題。
    - 合法值（去前後空白、不分大小寫）→ 對應 Mode。
    - 其他（含非字串）→ Mode.OFF，並回傳問題說明（呼叫端負責回報）。
      問題說明不包含原始值，避免把誤貼的機密帶進 log。
    """
    if isinstance(value, Mode):
        return value, None
    if value is None:
        return Mode(default), None
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "":
            return Mode(default), None
        try:
            return Mode(text), None
        except ValueError:
            return Mode.OFF, "mode 值不合法，視為 off（允許值：off／dry／live）"
    return Mode.OFF, f"mode 型別不合法（{type(value).__name__}），視為 off"


def parse_mode(value: ModeLike, default: Mode = Mode.OFF) -> Mode:
    """同 parse_mode_checked，只回傳 Mode（要回報問題請用 parse_mode_checked）。"""
    return parse_mode_checked(value, default)[0]


def effective_mode(mode: Mode, is_dry_flag: bool) -> Mode:
    """DRY_RUN 旗標為真時 live 降為 dry；off／dry 不變。不讀環境變數。

    is_dry_flag 必須是 bool：字串 "0" 在 Python 是真值，傳字串會被擋下（TypeError），
    請先用 parse_dry_run_flag 轉換。
    """
    if not isinstance(is_dry_flag, bool):
        raise TypeError("is_dry_flag 必須是 bool（環境變數字串請先用 parse_dry_run_flag 轉換）")
    mode = Mode(mode)
    if is_dry_flag and mode is Mode.LIVE:
        return Mode.DRY
    return mode


_TRUE_TEXT = frozenset({"1", "true", "yes", "on"})
_FALSE_TEXT = frozenset({"0", "false", "no", "off"})


def parse_dry_run_flag(raw: Optional[str]) -> bool:
    """把 DRY_RUN 環境變數的文字轉成 bool（供 app/main 使用）。

    安全方向偏 dry：只有明確的 "0"／"false"／"no"／"off" 才回 False；
    未設定、空白、無法辨識一律回 True（A-8：預設不送出）。
    """
    if raw is None:
        return True
    text = raw.strip().lower()
    if text in _FALSE_TEXT:
        return False
    return True  # 含 _TRUE_TEXT、空白、未知值
