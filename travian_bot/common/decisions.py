#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/decisions.py（cm-02）
版本：v0.1（A1a-2）｜草案（✗）：欄位待 A3a～A3c 讀現有函式回傳值後定案
用途：各 domain 決策的回傳結構（domain 回傳、actions 吃進去、app/stages 串接，§4.1 補充規則 1）：
      BuildTarget、BuildDecision、GuardDecision、FillInDecision、FocusDecision、
      ItemTransferDecision、AdventureDecision、HideCandidate、HideDecision、ExecResult。
依賴：cm-01（models；BuildTarget 直接沿用，不重複定義）。
部署狀態：未部署（GA 前不 live）。

來源（△ 都還沒讀，欄位是依 §6.7 舊動作與決策標籤做的最小猜想）：
  travian_agent.py、stock_guard.py、fill_in.py、hero_focus.py、travian_transfer.py、
  travian_hero.py、hide_troops.py 的回傳 dict。
  建城決策標籤取自 §6.7（✓ 已回填）：等待資源→wait_resources、等待佇列→wait_queue、
  倉容不足→storage_too_small、計畫卡住→plan_stuck、無空地→no_free_slot、已完成→done。
  中文標籤只留在 reason／detail，不進列舉值。
決策物件都是 frozen；reason 為給人看的短文字（寫入 Actions.detail 前先 models.clip_text）。
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from .models import BuildTarget

__all__ = [
    "BUILD_KINDS", "BuildTarget", "BuildDecision", "GuardDecision", "FillInDecision",
    "FocusDecision", "ItemTransferDecision", "AdventureDecision", "HideCandidate",
    "HideDecision", "ExecResult",
]

BUILD_KINDS = ("build", "wait_resources", "wait_queue", "storage_too_small",
               "plan_stuck", "no_free_slot", "done")


@dataclass(frozen=True)
class BuildDecision:
    kind: str                                   # BUILD_KINDS 之一；只有 build 會有動作
    target: Optional[BuildTarget]
    reason: str
    wait_s: Optional[int] = None                # wait_* 時預計還要等幾秒（未知 None）


@dataclass(frozen=True)
class GuardDecision:
    """防搶加成（stock_guard）。"""
    act: bool
    reason: str
    exposure: Optional[str] = None              # incoming／always（承接 guard_exposure）


@dataclass(frozen=True)
class FillInDecision:
    """插隊（fill_in）。"""
    act: bool
    target: Optional[BuildTarget]
    reason: str


@dataclass(frozen=True)
class FocusDecision:
    """hero_focus。舊值域只有 auto／off，新值域待 A6a2 定案。"""
    act: bool
    focus: Optional[str]
    reason: str


@dataclass(frozen=True)
class ItemTransferDecision:
    """轉移（travian_transfer）。"""
    act: bool
    item: Optional[str]
    amount: Optional[int]
    reason: str


@dataclass(frozen=True)
class AdventureDecision:
    """冒險（travian_hero）。"""
    act: bool
    adv_id: Optional[int]
    reason: str


@dataclass(frozen=True)
class HideCandidate:
    x: int
    y: int
    kind: Optional[str]
    distance: Optional[float]
    safe: Optional[bool]


@dataclass(frozen=True)
class HideDecision:
    act: bool
    chosen: Optional[HideCandidate]
    candidates: Tuple[HideCandidate, ...]
    reason: str


@dataclass(frozen=True)
class ExecResult:
    """actions 的回傳。result 取值同 C5（ok／dry／skipped／failed／deferred）。"""
    result: str
    detail: str
    requests_used: int = 0
    verified: Optional[bool] = None             # 送出後重讀驗證：None＝沒驗證（dry 或不可重讀）
