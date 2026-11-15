#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/common/decisions.py（cm-02）
版本：v0.3（A5a：ItemTransferDecision 改寫＋TransferLine；FOCUS_NAMES）｜v0.2（A3a：BuildDecision／GuardDecision／FillInDecision 定案；其餘仍為草案 ✗，待 A3b／A3c）｜v0.1（A1a-2）
用途：各 domain 決策的回傳結構（domain 回傳、actions 吃進去、app/stages 串接，§4.1 補充規則 1）：
      BuildTarget、BuildDecision、GuardDecision、FillInDecision、FocusDecision、
      ItemTransferDecision、AdventureDecision、HideCandidate、HideDecision、ExecResult。
依賴：cm-01（models；BuildTarget 直接沿用，不重複定義）、cm-09（parsed；BuildFacts 的欄位型別）。
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
from typing import Mapping, Optional, Tuple

from .models import BuildTarget
from .parsed import BuildOption, Dorf2, UpgradeCost

__all__ = [
    "BUILD_KINDS", "BuildTarget", "FactsNeed", "BuildFacts", "BuildDecision", "FillCandidate", "GuardDecision", "FillInDecision",
    "FocusDecision", "TransferLine", "ItemTransferDecision", "AdventureDecision", "HideCandidate",
    "HideDecision", "ExecResult",
]

BUILD_KINDS = ("build", "wait_resources", "wait_queue", "storage_too_small",
               "plan_stuck", "no_free_slot", "done")     # §6.7 的 7 個舊標籤（tests/common/test_decisions 釘住，不增減）

# v0.2（A3a）新增值，另放以免動到 BUILD_KINDS；這三個與 FACTS_KINDS 是 tuple，不放進 __all__
# （test_decisions 要求 __all__ 只有 frozen dataclass，BUILD_KINDS 例外），用 from … import 名稱取用。
BUILD_EXTRA_KINDS = ("no_affordable",   # plan(affordable_only=True) 沒有付得起的候選（舊 ("no_affordable",)）
                     "need_facts")      # 純函式缺頁面資料，要呼叫端抓完再呼叫（見 FactsNeed）
BUILD_DECISION_KINDS = BUILD_KINDS + BUILD_EXTRA_KINDS   # BuildDecision.kind 的完整值域（planner 實際回傳）
# v0.3（A5a）：FocusDecision.focus 的值域（actions 換成 hero.productionType：0～4；tuple 不進 __all__）
FOCUS_NAMES = ("balanced", "wood", "clay", "iron", "crop")
FACTS_KINDS = ("dorf2", "upgrade_cost", "build_options")  # FactsNeed.kind 的值域


@dataclass(frozen=True)
class FactsNeed:
    """build_planner／plan_validate 缺的頁面資料。kind：dorf2（村莊中心）、upgrade_cost（aid 的建築頁）、
    build_options（aid 空地的建造清單）。取代舊 plan_with_order 的 get(path)（domain 不碰網路）。"""
    kind: str
    aid: Optional[int] = None


@dataclass(frozen=True)
class BuildFacts:
    """呼叫端已抓到的頁面資料（唯讀）。upgrade_costs[aid]＝None 表示頁面讀過但沒有升級成本（例：已達最高等級）；
    沒有該鍵＝還沒抓。options[aid]＝該空地建造頁的清單（讀失敗給空 tuple）。"""
    dorf2: Optional[Dorf2] = None
    upgrade_costs: Optional[Mapping[int, Optional[UpgradeCost]]] = None
    options: Optional[Mapping[int, Tuple[BuildOption, ...]]] = None

    def __post_init__(self):
        object.__setattr__(self, "upgrade_costs", dict(self.upgrade_costs or {}))
        object.__setattr__(self, "options", dict(self.options or {}))


@dataclass(frozen=True)
class BuildDecision:
    kind: str                                   # BUILD_DECISION_KINDS 之一；只有 build 會有動作
    target: Optional[BuildTarget]
    reason: str
    wait_s: Optional[int] = None                # wait_* 時預計還要等幾秒（未知 None）
    build_time_s: Optional[int] = None          # v0.2：target 的工期（秒；插隊要用；BuildTarget 沒有此欄）
    need: Optional[FactsNeed] = None            # v0.2：kind＝need_facts 時要補什麼


@dataclass(frozen=True)
class FillCandidate:
    """v0.2：插隊候選（後面付得起的目標）。"""
    target: BuildTarget
    build_time_s: Optional[int]


@dataclass(frozen=True)
class GuardDecision:
    """防搶加成（stock_guard）。act＝True 時 focus 是要切到的英雄產量加成類型
    （hero.productionType：0 平均、1 木、2 磚、3 鐵、4 穀；v0.2）。"""
    act: bool
    reason: str
    exposure: Optional[str] = None              # incoming／always（承接 guard_exposure）
    focus: Optional[int] = None


@dataclass(frozen=True)
class FillInDecision:
    """插隊（fill_in）。"""
    act: bool
    target: Optional[BuildTarget]
    reason: str


@dataclass(frozen=True)
class FocusDecision:
    """hero_focus。v0.3：act＝True 時 focus 為 FOCUS_NAMES 之一（balanced／wood／clay／iron／crop，對應 productionType 0～4）。
    設定檔的 focus_mode 值域（off／auto）是另一回事，待 A6a2 定案。值域由 actions 檢查（不合法回 failed）。"""
    act: bool
    focus: Optional[str]
    reason: str


@dataclass(frozen=True)
class TransferLine:
    """轉移的一筆：resource 為資源索引（0 木、1 磚、2 鐵、3 穀，與 Res4 同序）；item_id＝道具庫物件 id；amount＝要轉的量。"""
    resource: int
    item_id: int
    amount: int


@dataclass(frozen=True)
class ItemTransferDecision:
    """英雄道具庫 → 村莊的資源轉移（travian_transfer）。v0.3 改寫（舊版只有單一 item／amount，放不下四種資源）。
    act＝True 時：lines 至少一筆（resource 不重複）、village_id＝收貨村、targets＝轉完後村莊每種資源至少要有的量（木磚鐵穀，驗證用）。
    合法性由 actions 檢查（不合法回 failed、不送出）。"""
    act: bool
    reason: str
    lines: Tuple[TransferLine, ...] = ()
    village_id: Optional[int] = None
    targets: Optional[Tuple[int, int, int, int]] = None


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
