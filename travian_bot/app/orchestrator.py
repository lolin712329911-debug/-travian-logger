#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/orchestrator.py（ap-08）
版本：v0.1.1（A6b，單村版；B3 擴成多村；log 不重複 did）
用途：一輪的總指揮：排村莊順序→逐村 run_village_cycle→帳號級 stage→寫彙總。
      村級例外隔離（只記錄、不關帳號）；SessionLost 往上丟，由 app/main 處理（disable／通知）。
依賴：ap-02、ap-03、ap-04、ap-07、cm-01、cm-10、if-01。
部署狀態：未部署（GA 前不 live）。

單村版先不做的事（B3）：有來襲先、最久沒處理的次之（需要跨輪記錄與多村快照）、時間預算與 deferred。
  目前順序＝priority（小的先）、再 did；budget_s 與耗時只記錄在彙總 log，不中斷。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..common.models import StageResult, VillageContext, VillageRef, VillageSnapshot
from ..infra.session import SessionLost
from . import registry, village_cycle
from .run_context import RunContext
from .stage_base import run_stage

__all__ = ["RunReport", "order_villages", "run"]


@dataclass
class RunReport:
    runs: List[village_cycle.VillageRun] = field(default_factory=list)
    account_results: List[StageResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)       # 村級例外（已 redact）

    def all_results(self) -> List[StageResult]:
        out: List[StageResult] = []
        for r in self.runs:
            out.extend(r.results)
        return out + list(self.account_results)

    @property
    def failed(self) -> bool:
        return bool(self.errors) or any(r.status == "failed" for r in self.all_results())


def order_villages(vcs: Sequence[VillageContext]) -> List[VillageContext]:
    """只排 enabled 的村：priority 小的先、再 did。（B3 加來襲與最久沒處理）"""
    return sorted((v for v in vcs if v.enabled), key=lambda v: (v.priority, v.did))


def _counts(results: Sequence[StageResult]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def run(rc: RunContext, refs: Sequence[VillageRef], vcs: Sequence[VillageContext]) -> RunReport:
    report = RunReport()
    known = {r.did for r in refs}
    for vc in order_villages(vcs):
        if known and vc.did not in known:
            msg = f"Villages 的村 {vc.did} 不在頁面村莊清單，略過"
            rc.warn(msg)
            report.errors.append(msg)
            continue
        try:
            run_ = village_cycle.run_village_cycle(rc, vc)
        except SessionLost:
            raise
        except Exception as exc:  # noqa: BLE001  村級例外隔離：不關帳號、不影響其他村
            msg = f"村 {vc.did} 本輪失敗（{type(exc).__name__}）"
            report.errors.append(msg)
            village_cycle.log_line(rc, "ERROR", "village_cycle", vc.did, f"本輪失敗（{type(exc).__name__}）：{exc}")
            village_cycle.log_event(rc, vc, "village_cycle", "failed", f"{type(exc).__name__}：{exc}")
            continue
        report.runs.append(run_)

    # 帳號級 stage：單村期間 snapshot 給第一個有快照的村 ✗（帳號級 stage 是否要快照，A6a2 的 stage 實作確認）
    snap: Optional[VillageSnapshot] = next((r.snapshot for r in report.runs if r.snapshot is not None), None)
    for stage in registry.account_stages():
        report.account_results.append(run_stage(stage, rc, None, snap))

    results = report.all_results()
    village_cycle.log_line(
        rc, "INFO", "orchestrator", None,
        f"本輪結束：村 {len(report.runs)}／錯誤 {len(report.errors)}／stage {_counts(results)}"
        f"／請求 {rc.gateway.request_count()}／耗時 {rc.gateway.elapsed():.1f}s")
    for w in rc.warnings:
        village_cycle.log_line(rc, "WARN", "orchestrator", None, w)
    return report
