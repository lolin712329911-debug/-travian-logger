#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/village_cycle.py（ap-07）
版本：v0.1.2（GA 修正：record_main 要 UTC 字串，改傳 serialize.to_utc_str(rc.io.now())；v0.1.1：動作名稱改用 constants.ACTION_VILLAGE_SKIP）
用途：單一村莊一輪的流程：核對目前村莊→village_lock→observe→依 registry 順序跑村級 stage。
      寫入類 stage 執行前再核對一次目前村莊；不符則該村剩餘寫入 stage 全記 skipped、不 disable()。
依賴：ap-02、ap-03、ap-04、ap-05、dm-09、ac-01、cm-01、cm-03、cm-04、cm-10、if-01、if-05。
部署狀態：未部署（GA 前不 live）。

處置：拆（舊 runner.run_build_cycle 的串接段；決策與送出已在各 stage）。

行為
  run_village_cycle(rc, vc)→VillageRun（含最後的快照，orchestrator 要給帳號級 stage 用）；
  run_village(rc, vc)→list[StageResult]（卡片簽名，薄包裝）。
  ①switch_to（單村＝無操作）②assert_active（進村一次；不符＝村莊跳過）
  ③decide_lock：skip＝寫一列「村莊跳過」、不 disable()；record＝record_main 後寫 Config（set_keys）
  ④observe_village；observe_player＋write_player_state（best-effort，SessionLost 例外）
  ⑤每個村級 stage：mode_key 為 None（build）或 mode 為 dry／live 者先 assert_active；
    stage 的 snapshot_updates 套回快照（失敗只 rc.warn，不丟掉 stage 的結果）。
  ①～④ 的例外（ParseError／GatewayError／SessionLost／lock 寫入失敗）不吞，往上丟（orchestrator 做村級隔離）。
"""
from dataclasses import dataclass, field, fields, replace
from typing import Any, Callable, Dict, List, Optional

from ..actions import village_switch
from ..common import serialize
from ..common.constants import ACTION_VILLAGE_SKIP   # "村莊跳過"（cm-03，C5／C8）
from ..common.modes import Mode
from ..common.models import ActionRow, StageResult, VillageContext, VillageLock, VillageSnapshot
from ..domain import village_lock
from ..infra.session import SessionLost
from ..infra.store import config_repo
from . import observe, registry
from .run_context import RunContext
from .stage_base import run_stage, stage_mode

__all__ = ["VillageRun", "run_village", "run_village_cycle", "apply_updates", "log_line", "log_event"]

_FROZEN_KEYS = ("did",)


@dataclass
class VillageRun:
    did: int
    snapshot: Optional[VillageSnapshot] = None
    results: List[StageResult] = field(default_factory=list)
    skipped_reason: Optional[str] = None      # 非 None＝整村沒跑（村莊跳過）


# ---------------------------------------------------------------- 小工具
def log_line(rc: RunContext, level: str, stage: str, did: Optional[int], msg: str) -> None:
    """§6.5 log 格式：{ts_utc} {LEVEL} {stage} {did或-} {msg}；msg 先 redact。"""
    print(f"{serialize.to_utc_str(rc.io.now())} {level} {stage} {did if did else '-'} {serialize.redact(msg)}")


def log_event(rc: RunContext, vc: Optional[VillageContext], action: str, result: str, detail: str) -> None:
    """寫一列 Actions（best-effort；失敗只 rc.warn）。did 沒有就不寫。"""
    did = vc.did if vc is not None else rc.cfg.get("main_did")
    if not did:
        rc.warn("沒有 did，略過寫 Actions")
        return
    try:
        row = ActionRow(ts_utc=serialize.to_utc_str(rc.io.now()), action=action, aid=None, gid=None, level=None,
                        cost=None, mode="dry" if rc.dry_flag else "live", result=result,
                        detail=serialize.redact(detail)[:300], did=did)
        rc.io.log_actions(rc.sh, [row])
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"寫入 Actions 失敗：{type(exc).__name__}")


def _skip_result(note: str) -> StageResult:
    return StageResult(status="skipped", actions=[], snapshot_updates={}, note=serialize.redact(note)[:200],
                       requests_used=0, elapsed_s=0.0)


def _fail_result(note: str) -> StageResult:
    return StageResult(status="failed", actions=[], snapshot_updates={}, note=serialize.redact(note)[:200],
                       requests_used=0, elapsed_s=0.0)


def apply_updates(snap: VillageSnapshot, updates: Dict[str, Any]) -> VillageSnapshot:
    """把 StageResult.snapshot_updates 套回快照（C2 唯讀，回新物件）。鍵不是 C2 欄位、或想改 did、
    或套完 ensure_valid 不過＝丟例外（呼叫端只 rc.warn）。"""
    if not updates:
        return snap
    names = {f.name for f in fields(snap)}
    bad = [k for k in updates if k not in names or k in _FROZEN_KEYS]
    if bad:
        raise ValueError("snapshot_updates 含不可更新的鍵：" + "、".join(sorted(bad)))
    new = replace(snap, **updates)
    new.ensure_valid()
    return new


def _lock_from_cfg(cfg: Dict[str, Any]) -> VillageLock:
    # ✗ 空的村莊鎖怎麼建（main_did／main_did_set_utc 皆 None）要看 models／village_lock 實作
    return VillageLock(main_did=cfg.get("main_did"), main_did_set_utc=cfg.get("main_did_set_utc"))


def _record_lock(rc: RunContext, lock: VillageLock) -> None:
    """記錄村莊鎖：寫 Config 並同步 rc.cfg。寫入失敗丟出（村莊鎖寫不進去不該靜默）。"""
    stamp = lock.main_did_set_utc
    if not isinstance(stamp, str):
        stamp = serialize.to_utc_str(stamp)
    config_repo.set_keys(rc.sh, {"main_did": str(lock.main_did), "main_did_set_utc": stamp})
    rc.cfg["main_did"] = lock.main_did
    rc.cfg["main_did_set_utc"] = stamp


def _skipped(rc: RunContext, vc: VillageContext, reason: str) -> VillageRun:
    log_line(rc, "WARN", "village_cycle", vc.did, f"村莊跳過：{reason}")
    log_event(rc, vc, ACTION_VILLAGE_SKIP, "skipped", reason)
    return VillageRun(did=vc.did, snapshot=None, results=[_skip_result(f"村莊跳過：{reason}")],
                      skipped_reason=reason)


# ---------------------------------------------------------------- 主流程
def _record_player(rc: RunContext, vc: VillageContext, snap: VillageSnapshot) -> None:
    info = None
    try:
        info = observe.observe_player(rc)
    except SessionLost:
        raise
    except Exception as exc:  # noqa: BLE001
        rc.warn(f"讀不到玩家資訊（{type(exc).__name__}）")
    line = observe.cp_summary(info)
    if line:
        log_line(rc, "INFO", "observe", vc.did, line)
    observe.write_player_state(rc, vc, info, snap, vc.build_settings.queue_slots)


def run_village_cycle(rc: RunContext, vc: VillageContext, *,
                      record_lock: Callable[[RunContext, VillageLock], None] = _record_lock) -> VillageRun:
    gw = rc.gateway
    map_half = rc.profile.map_half
    village_switch.switch_to(gw, vc.did)
    if not village_switch.assert_active(gw, vc.did, map_half=map_half):
        return _skipped(rc, vc, f"目前村莊不是 {vc.did}")

    lock = _lock_from_cfg(rc.cfg)
    decision = village_lock.decide_lock(lock, vc.did)
    if decision.kind == "skip":
        return _skipped(rc, vc, decision.reason)
    if decision.record:
        new_lock = village_lock.record_main(vc.did, serialize.to_utc_str(rc.io.now()),
                                            existing=lock if lock.main_did else None)
        record_lock(rc, new_lock)
        log_line(rc, "INFO", "village_lock", vc.did, "第一次執行，已記錄 main_did")

    snap = observe.observe_village(rc, vc)
    _record_player(rc, vc, snap)

    results: List[StageResult] = []
    broken: Optional[str] = None
    for stage in registry.village_stages():
        mode = stage_mode(stage, vc, rc.dry_flag, rc=rc)
        is_write = stage.mode_key is None or mode is not Mode.OFF   # build（無 mode_key）與 dry／live
        if is_write:
            if broken is not None:
                results.append(_skip_result(f"村莊跳過：{broken}（{stage.name}）"))
                continue
            try:
                ok = village_switch.assert_active(gw, vc.did, map_half=map_half)
            except SessionLost:
                raise
            except Exception as exc:  # noqa: BLE001
                note = f"{stage.name}：寫入前核對目前村莊失敗（{type(exc).__name__}）"
                log_event(rc, vc, stage.name, "failed", note)
                results.append(_fail_result(note))
                continue
            if not ok:
                broken = f"寫入前目前村莊不是 {vc.did}"
                log_line(rc, "WARN", stage.name, vc.did, f"村莊跳過：{broken}")
                log_event(rc, vc, ACTION_VILLAGE_SKIP, "skipped", f"{broken}（{stage.name} 起）")
                results.append(_skip_result(f"村莊跳過：{broken}（{stage.name}）"))
                continue
        res = run_stage(stage, rc, vc, snap)
        results.append(res)
        if res.snapshot_updates:
            try:
                snap = apply_updates(snap, res.snapshot_updates)
            except Exception as exc:  # noqa: BLE001
                rc.warn(f"{stage.name} 的 snapshot_updates 套用失敗（{type(exc).__name__}），沿用原快照")
    return VillageRun(did=vc.did, snapshot=snap, results=results, skipped_reason=None)


def run_village(rc: RunContext, vc: VillageContext) -> List[StageResult]:
    """卡片簽名：只回 stage 結果。"""
    return run_village_cycle(rc, vc).results
