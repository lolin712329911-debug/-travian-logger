#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/notify.py（if-03）
版本：v0.1（A4a）
用途：通知。目前只印 log（Actions 的執行紀錄）；E1 再加 Email／Telegram。
依賴：cm-10（serialize.redact）。
部署狀態：未部署（GA 前不 live）。

與舊 notify.py（✓ 已讀，10 行）的差異
  1. 新增 level 參數（info／warn／error）。info 的輸出格式與舊版完全相同：`[HH:MM:SS] msg`。
  2. 訊息先過 serialize.redact 再輸出（舊版直接印，失敗訊息可能帶到 Cookie／token）。
  卡片原簽名 notify(level, msg) 改為 notify(msg, level="info")：舊呼叫點 notify(msg) 不用改。
"""
from datetime import datetime
from typing import Any

from ..common.serialize import redact

LEVELS = ("info", "warn", "error")
_TAGS = {"info": "", "warn": "[WARN] ", "error": "[ERROR] "}


def _clock() -> datetime:
    """本機時間（只用於 log 顯示，不持久化；測試可替換）。"""
    return datetime.now()


def notify(msg: Any, level: str = "info") -> None:
    """印一行 log。level 不在 LEVELS 內丟 ValueError（呼叫端打錯字不能靜默吞掉）。"""
    if level not in LEVELS:
        raise ValueError("notify level 只能是 info／warn／error")
    print(f"[{_clock():%H:%M:%S}] {_TAGS[level]}{redact(msg)}")
