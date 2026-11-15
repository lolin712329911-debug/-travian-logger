#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stage_base.py（ap-03）
版本：v0.1（A6a1）
用途：Stage 定義與統一執行入口 run_stage。stage 只回 StageResult；例外一律接住並轉成 failed；
      Actions 由這裡經 rc.io.log_actions 一次寫入（寫入失敗只 rc.warn，不往上丟、不改 status）。
依賴：ap-02（RunContext）、cm-01（models）、cm-04（modes）、cm-10（serialize.redact／to_utc_str）。
部署狀態：未部署（GA 前不 live）。

run_stage 規則（卡片 v0.69）
  ① mode=off：不執行、不寫 Actions，回 skipped。
  ② precondition 為假：skipped，不寫 Actions（避免每輪洗版）。
  ③ 執行；例外（含 ParseError、GatewayError、SessionLost、ValidationError）→ status=failed，
     note ≤200（先 redact），記一列 Actions（result=failed，detail 含例外類別）。
  ④ requests_used、elapsed_s 取 gateway.request_count()／elapsed() 的前後差值。
  ⑤ Actions 統一在這裡寫入。account 級 stage 的 vc 為 None，did 用 rc.cfg["main_did"]（單村期間；B2 改）。

與卡片的差異（交接區塊有列）
  - stage_mode 多一個關鍵字參數 rc：卡片說「不合法視為 off 並寫入 rc.warnings」，但簽名沒有 rc；
    account 級 stage 的 vc 是 None，mode 來源改取 rc.modes。沒給 rc 時只回 Mode（問題不回報）。
  - 順手多收一條規則：stage 回 failed 卻沒有任何 result=failed 的列時，補一列，避免失敗沒有紀錄。
"""
import dataclasses
from dataclasses import dataclass
from typing import Callable, List, Optional

from ..common import serialize
from ..common.models import ActionRow, StageResult, VillageContext, VillageSnapshot, clip_text
from ..common.modes import Mode, effective_mode, parse_mode_checked
from .run_context import RunContext

__all__ = ["SCOPES", "STAGE_MODE_KEYS", "NOTE_MAX", "Stage", "stage_mode", "run_stage"]

SCOPES = ("village", "account")
# C9 `modes` 的 9 個鍵（§6.2）；build 不受 mode 控制（mode_key=None）
STAGE_MODE_KEYS = ("fill_in", "guard", "item_transfer", "focus", "hide", "oasis", "hero", "market", "troops")
NOTE_MAX = 200
DETAIL_MAX = 300


@dataclass(frozen=True)
class Stage:
    name: str                                    # 唯一；也是失敗列的 Actions.action（≤40）
    scope: str                                   # village／account
    mode_key: Optional[str]                      # STAGE_MODE_KEYS 之一；None＝不受 mode 控制（例：build）
    order: int                                   # 越小越先
    precondition: Callable[[RunContext, Optional[VillageContext], Optional[VillageSnapshot]], bool]
    run: Callable[[RunContext, Optional[VillageContext], Optional[VillageSnapshot], Mode], StageResult]
    budget_s: float = 0.0                        # A6a1 只記錄、不中斷（B3 才做時間預算）


# ---------------------------------------------------------------- mode
def stage_mode(stage: Stage, vc: Optional[VillageContext], dry_flag: bool, *,
               rc: Optional[RunContext] = None) -> Mode:
    """stage 這一輪的有效 mode。
    mode_key=None：以 live 經 effective_mode（DRY_RUN 時降 dry）。
    否則取 vc.modes[mode_key]（account 級 vc 為 None → rc.modes）；不合法一律 off，並在有 rc 時寫入 rc.warnings；
    缺值＝off（不報問題）。最後一律經 effective_mode。"""
    if stage.mode_key is None:
        return effective_mode(Mode.LIVE, dry_flag)
    if vc is not None:
        raw = (vc.modes or {}).get(stage.mode_key)
    elif rc is not None:
        raw = (rc.modes or {}).get(stage.mode_key)
    else:
        raw = None
    mode, problem = parse_mode_checked(raw, Mode.OFF)
    if problem and rc is not None:
        rc.warn(f"stage {stage.name}：{problem}")
    return effective_mode(mode, dry_flag)


# ---------------------------------------------------------------- 失敗列
def _did_of(rc: RunContext, vc: Optional[VillageContext]) -> Optional[int]:
    if vc is not None:
        return vc.did
    did = (rc.cfg or {}).get("main_did")
    return did if isinstance(did, int) and not isinstance(did, bool) and did >= 1 else None


def _failed_row(rc: RunContext, stage: Stage, mode: Mode, did: int, detail: str) -> ActionRow:
    return ActionRow(ts_utc=serialize.to_utc_str(rc.io.now()), action=stage.name[:40], aid=None, gid=None,
                     level=None, cost=None, mode=mode.value, result="failed",
                     detail=clip_text(serialize.redact(detail), DETAIL_MAX), did=did)


def _exc_note(exc: BaseException) -> str:
    text = serialize.redact(f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)
    return clip_text(text, NOTE_MAX)


# ---------------------------------------------------------------- 執行
def run_stage(stage: Stage, rc: RunContext, vc: Optional[VillageContext],
              snap: Optional[VillageSnapshot]) -> StageResult:
    """執行一個 stage，永遠回 StageResult，不往上丟例外。"""
    mode = stage_mode(stage, vc, rc.dry_flag, rc=rc)
    if mode is Mode.OFF:
        return StageResult(status="skipped", note="mode=off")
    did = _did_of(rc, vc)
    gw = rc.gateway
    req0, t0 = gw.request_count(), gw.elapsed()
    result: StageResult
    try:
        if not stage.precondition(rc, vc, snap):
            return StageResult(status="skipped", note="precondition 不成立")
        result = stage.run(rc, vc, snap, mode)
        if not isinstance(result, StageResult):
            raise TypeError(f"stage {stage.name} 回傳型別不是 StageResult")
        result = dataclasses.replace(result, actions=list(result.actions))
        result.note = clip_text(serialize.redact(result.note), NOTE_MAX) if result.note else ""
        if result.status == "failed" and not result.note:
            result.note = "failed（stage 未說明原因）"
        result.requests_used = max(0, gw.request_count() - req0)
        result.elapsed_s = max(0.0, gw.elapsed() - t0)
        result.ensure_valid()
    except Exception as exc:  # noqa: BLE001 —— 一律接住，轉成 failed
        note = _exc_note(exc)
        rows: List[ActionRow] = []
        if did is not None:
            try:
                rows.append(_failed_row(rc, stage, mode, did, note))
            except Exception as row_exc:  # noqa: BLE001
                rc.warn(f"stage {stage.name}：失敗列建立失敗（{type(row_exc).__name__}）")
        result = StageResult(status="failed", actions=rows, note=note,
                             requests_used=max(0, gw.request_count() - req0),
                             elapsed_s=max(0.0, gw.elapsed() - t0))
        _write_actions(stage, rc, result, did)
        return result
    # stage 自己說失敗、卻沒有失敗列：補一列
    if result.status == "failed" and did is not None and not any(a.result == "failed" for a in result.actions):
        try:
            result.actions.append(_failed_row(rc, stage, mode, did, result.note))
        except Exception as row_exc:  # noqa: BLE001
            rc.warn(f"stage {stage.name}：失敗列建立失敗（{type(row_exc).__name__}）")
    _write_actions(stage, rc, result, did)
    return result


def _write_actions(stage: Stage, rc: RunContext, result: StageResult, did: Optional[int]) -> None:
    """一次寫入這個 stage 的全部 Actions。失敗只 warn，不改 status、不往上丟。"""
    if not result.actions:
        if result.status == "failed" and did is None:
            rc.warn(f"stage {stage.name}：failed 但沒有 did（尚未鎖村），Actions 未寫入")
        return
    try:
        rc.io.log_actions(rc.sh, result.actions)
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"stage {stage.name}：寫入 Actions 失敗（{type(exc).__name__}）")
