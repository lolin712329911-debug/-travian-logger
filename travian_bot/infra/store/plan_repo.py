#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/infra/store/plan_repo.py（if-12）
版本：v0.1.1（A4b-1；v0.58 只改註解與依賴說明，程式碼與 v0.1 完全相同）
用途：讀 build_order（唯讀，Python 不寫；唯一寫入者是 Apps Script／人）。回傳原始文字，不解析、不驗證——
      解析與驗證在 domain/plan_validate（parse_build_order → validate_order）。
依賴：if-04（gsheets）、if-05（config_repo）。
部署狀態：未部署（GA 前不 live）。

與卡片的差異（A4b-1 交接區塊有列）
  1. 來源＝**Config 分頁的 build_order 字串**（例 `res:9,26:10,20:10`），不是 `build_order` 分頁：
     Apps Script 套用時寫的是 Config（Code.gs writeConfigOrder_），你手動改 Config 或開 ai_lock 時，
     分頁的 applied 批會和實際生效的不同。`build_order` 分頁只是 Gemini 的紀錄，Python 不讀。
  2. 字串空白、沒有這個鍵、或沒有 Config 分頁＝None＝**沒有計畫**（不是被拒，也不是 hold）。
     呼叫端（app/stages/build，A6a2）遇到 None 走舊流程 build_planner.plan（資源田依 target_level、
     倉庫糧倉依 target_building_level；與舊 runner.py 一致）；有內容才交給 plan_validate，被拒才 hold（主檔 §10 v0.58）。
     IO 失敗照丟，不當成 None（避免讀取暫時失敗時悄悄走舊流程）。預設行程由 domain 的 plan 負責，plan_repo 不產生任何預設。
  3. 每次呼叫都重新讀，不快取（v0.10）。呼叫端若本輪已讀過 Config，可傳 raw_config 省一次請求（那是同一輪剛讀的值，不是跨輪快取）。
  4. 多村（B6）改讀 Villages 的 build_order 欄；A4b 只有單村，did 只檢查型別。
  5. RawBuildOrder 放在這裡（不進 cm-01 契約）：infra 不能 import domain，所以 plan_repo 只交出文字，
     呼叫端用 plan_validate.parse_build_order(raw.text) 轉成 RawStep。
"""
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from . import config_repo, gsheets

BUILD_ORDER_KEY = "build_order"


@dataclass(frozen=True)
class RawBuildOrder:
    text: str       # Config 儲存格的原始字串（已去前後空白，非空）
    source: str     # 'config'（單村）；B6 會有 'villages'


def load_build_order(sh: Any, did: int, *, raw_config: Optional[Mapping[str, str]] = None) -> Optional[RawBuildOrder]:
    """讀目前生效的 build_order。沒有分頁、沒有這個鍵、或內容空白回 None（＝沒有計畫，呼叫端走舊流程）。IO 失敗照丟（不當成 None）。"""
    if isinstance(did, bool) or not isinstance(did, int) or did < 1:
        raise ValueError("did 需為 int ≥ 1")
    if raw_config is not None:
        value = str(raw_config.get(BUILD_ORDER_KEY, "") or "").strip()
    else:
        ws = gsheets.get_worksheet(sh, config_repo.CONFIG_TAB)
        if ws is None:
            return None
        value = config_repo.parse_rows(ws.get_all_values()).get(BUILD_ORDER_KEY, "").strip()
    return RawBuildOrder(value, "config") if value else None
