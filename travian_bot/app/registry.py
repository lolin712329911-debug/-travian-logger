#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/registry.py（ap-04）
版本：v0.3（A6a2b：登記 oasis／hide）｜v0.2（A6a2：登記 build／item_transfer／fill_in／focus／guard／hero）｜v0.1（A6a1）
用途：stage 登記表。新增功能＝新增 stage 檔＋在 STAGES 登記一行，不改 orchestrator 迴圈。
      A6a1 為空表；A6a2 登記六個 stage（build、item_transfer、fill_in、focus、guard、hero）；A6a2b 再登記 oasis、hide。不用動態 import（check_arch 看不到）。
依賴：ap-03（Stage、SCOPES、STAGE_MODE_KEYS）。
部署狀態：未部署（GA 前不 live）。

檢查（違反丟 ValueError）：name 不重複；scope 合法（village／account）；
mode_key 必須是 None 或 C9 modes 的 9 個鍵；order 為 int（不含 bool）。
排序：order 由小到大、再依 name。
"""
from typing import Optional, Sequence, Tuple

from .stage_base import SCOPES, STAGE_MODE_KEYS, Stage
from .stages import build as _build
from .stages import fill_in as _fill_in
from .stages import focus as _focus
from .stages import guard as _guard
from .stages import hero as _hero
from .stages import hide as _hide
from .stages import item_transfer as _item_transfer
from .stages import oasis as _oasis

__all__ = ["STAGES", "validate_stages", "village_stages", "account_stages"]

# order：oasis 5 → hide 10（躲兵在建城前，舊 hide_observe 每輪建城前跑；oasis 先把綠洲清單放進 HideContext）→ item_transfer 20 → fill_in 25 → build 30
#        → focus 40 → guard 50；hero 60（帳號級）
STAGES: Tuple[Stage, ...] = (_oasis.STAGE, _hide.STAGE, _item_transfer.STAGE, _fill_in.STAGE, _build.STAGE, _focus.STAGE,
                             _guard.STAGE, _hero.STAGE)


def validate_stages(table: Sequence[Stage]) -> None:
    seen = set()
    for st in table:
        if not isinstance(st, Stage):
            raise ValueError("登記表只能放 Stage")
        if not isinstance(st.name, str) or not st.name.strip():
            raise ValueError("stage name 不可為空")
        if st.name in seen:
            raise ValueError(f"stage name 重複：{st.name}")
        seen.add(st.name)
        if st.scope not in SCOPES:
            raise ValueError(f"stage {st.name}：scope 只能是 {SCOPES}")
        if st.mode_key is not None and st.mode_key not in STAGE_MODE_KEYS:
            raise ValueError(f"stage {st.name}：mode_key 必須是 None 或 {STAGE_MODE_KEYS}")
        if isinstance(st.order, bool) or not isinstance(st.order, int):
            raise ValueError(f"stage {st.name}：order 需為 int")


def _pick(scope: str, table: Optional[Sequence[Stage]]) -> Tuple[Stage, ...]:
    tbl = STAGES if table is None else tuple(table)
    validate_stages(tbl)
    return tuple(sorted((s for s in tbl if s.scope == scope), key=lambda s: (s.order, s.name)))


def village_stages(table: Optional[Sequence[Stage]] = None) -> Tuple[Stage, ...]:
    """村級 stage，依 order、name 排序。table 供測試傳自己的表。"""
    return _pick("village", table)


def account_stages(table: Optional[Sequence[Stage]] = None) -> Tuple[Stage, ...]:
    """帳號級 stage，依 order、name 排序。"""
    return _pick("account", table)
