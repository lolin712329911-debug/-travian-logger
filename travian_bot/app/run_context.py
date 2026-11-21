#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/run_context.py（ap-02）
版本：v0.1.3（GA-fix1：加 dorf1_raw_if；get_page 對 dorf1.php 預設套用它，實機診斷發現 observe 前已有別處用無備援方式抓過 dorf1）｜v0.1.2（A6a2b：StageIO 加 oasis_centers）｜v0.1.1（A6a2：加 stage_notes；StageIO 加 read_state／upsert_state）｜v0.1（A6a1）
用途：帳號級執行環境。
      StageIO       ：stage 與 observe 對外的全部 IO（Sheet 讀寫、通知、等待、時鐘），欄位都是可替換的函式，
                      測試時整組注入假的；real_io(notify) 組出綁真實 repo 函式的版本。
      SessionLike   ：app 對 session 的最小需求（Protocol；不 import infra/session）。
      RunContext    ：帳號級可變狀態（cfg、profile、tribe、gateway、session、sh、io、dry_flag、hero、pages、warnings）。
依賴：if-02（gateway）、if-05（config_repo.disable）、if-07（action_repo）、if-08（state_repo）、
      if-09（snapshot_repo）、if-10（oasis_repo）、cm-01（models）、cm-06（tribe_data）、cm-09（parsed）、
      cm-10（serialize.redact；v0.69 卡片漏列，見交接區塊）、ps-01（dorf1_fields_lack_cost；v0.1.3，卡片與 arch_manifest 要補）。
部署狀態：未部署（GA 前不 live）。

設計重點
  1. 本檔不 import infra/notify、infra/session：notify 由 app/main 傳進 real_io，session 只用 Protocol。
  2. 時間一律 aware UTC datetime（io.now()）；字串化只經 serialize（本檔不格式化）。
  3. rc.warn 只收集、不印；訊息先過 serialize.redact（§6.1 機密規則）。
  4. rc.pages 是「本輪已抓頁面」：同一路徑本輪只抓一次（get_page）。
  5. 與卡片的差異（交接區塊有列）：RunContext 多一個 `modes`（帳號級 mode 值，account 級 stage 用；預設空＝全部 off）。
  6. v0.1.1（A6a2）：多一個 `stage_notes`（同一輪 stage 之間的旗標，例如 focus 這輪切了、守衛不跑；鍵 `{did}:{名稱}`，
     由 app/stages/_util 讀寫）。StageResult.snapshot_updates 的鍵必須是 C2 欄位名，放不下這種內部旗標，所以另開。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from ..common import serialize
from ..common.models import ActionRow, ServerProfile
from ..common.parsed import HeroState
from ..common.tribe_data import TribeSpec
from ..infra import gateway as _gateway
from ..parsers.village import dorf1_fields_lack_cost
from ..infra.store import action_repo, config_repo, oasis_repo, snapshot_repo, state_repo

__all__ = ["StageIO", "SessionLike", "RunContext", "real_io"]


# ---------------------------------------------------------------- StageIO
@dataclass(frozen=True)
class StageIO:
    """全部對外 IO。欄位簽名與對應的真實 repo 函式一致（見 real_io）；測試時以假函式取代。"""
    log_actions: Callable[[Any, Sequence[ActionRow]], int]
    write_state: Callable[[Any, int, Sequence[Tuple[str, Any, str]], str], int]
    append_snapshot: Callable[[Any, int, Any], int]
    write_structure: Callable[..., Any]
    buildable_due: Callable[..., bool]
    last_action_age_hours: Callable[..., Optional[float]]
    disable: Callable[[Any, str, Optional[int], str], bool]
    oasis_save: Callable[..., int]
    oasis_load: Callable[..., list]
    notify: Callable[[str], None]
    sleep: Callable[[float], None]
    now: Callable[[], datetime]          # aware UTC
    # v0.1.1（A6a2，ap-10 用）：有預設值，所以既有的假 StageIO（tests/app/fakes.py）不用改；None＝這個 IO 沒接
    read_state: Optional[Callable[..., dict]] = None
    upsert_state: Optional[Callable[..., int]] = None
    # v0.1.2（A6a2b，ap-16 用）：oasis_repo.list_centers(sh) → list[CenterInfo]；None＝這個 IO 沒接（oasis stage 會略過）
    oasis_centers: Optional[Callable[..., list]] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def real_io(notify: Callable[[str], None]) -> StageIO:
    """綁真實 repo 函式的 StageIO。notify 由 app/main 傳入（本檔不 import infra/notify）。"""
    import time
    return StageIO(
        log_actions=action_repo.log_actions,
        write_state=state_repo.write_state,
        append_snapshot=snapshot_repo.append_snapshot,
        write_structure=snapshot_repo.write_structure,
        buildable_due=snapshot_repo.buildable_due,
        last_action_age_hours=action_repo.last_action_age_hours,
        disable=config_repo.disable,
        oasis_save=oasis_repo.save,
        oasis_load=oasis_repo.load,
        notify=notify,
        sleep=time.sleep,
        now=_utc_now,
        read_state=state_repo.read_state,
        upsert_state=state_repo.upsert_state,
        oasis_centers=oasis_repo.list_centers,
    )


# ---------------------------------------------------------------- SessionLike
class SessionLike(Protocol):
    """app 需要的 session 介面（infra.session.Session 滿足）。
    is_village_html 在 Session 上是 staticmethod，經實例呼叫與一般方法相同。"""

    def is_village_html(self, html: Any) -> bool: ...

    @property
    def can_recover(self) -> bool: ...

    def recover(self) -> None: ...

    def save_state(self) -> None: ...


# ---------------------------------------------------------------- RunContext
@dataclass
class RunContext:
    """帳號級執行環境（可變）。每輪由 app/main 建立一次。"""
    cfg: Dict[str, Any]                      # 已 normalize_cfg
    profile: ServerProfile
    tribe: TribeSpec
    gateway: "_gateway.Gateway"
    session: SessionLike
    sh: Any                                  # 已開啟的試算表（gsheets 層物件）
    io: StageIO
    dry_flag: bool = True                    # app/main 讀 DRY_RUN 後傳入；預設 dry（A-8）
    hero: Optional[HeroState] = None         # observe 更新；讀不到維持原值
    pages: Dict[str, str] = field(default_factory=dict)      # 路徑 → html（本輪已抓）
    warnings: List[str] = field(default_factory=list)        # 已 redact
    modes: Dict[str, str] = field(default_factory=dict)      # 帳號級 mode（C9 鍵 → 原始值）；空＝全部 off
    stage_notes: Dict[str, Any] = field(default_factory=dict)   # v0.1.1：同一輪 stage 之間的旗標（每輪新建，不跨輪）

    def warn(self, msg: Any) -> None:
        """收集警告（不印）。訊息先 redact。"""
        self.warnings.append(serialize.redact(msg))

    def dorf1_raw_if(self, html: str) -> bool:
        """dorf1 專用的 gateway raw_if：不是村莊頁，或資源田成本被渲染後的頁面清空 → 改抓純 HTTP 原始 HTML
        （取代舊 need_cost 備援）。所有抓 dorf1 的地方都要傳它（含 refresh=True），否則升級後重讀會丟成本。"""
        return (not self.session.is_village_html(html)) or dorf1_fields_lack_cost(html)

    def get_page(self, path: str, *, raw_if: Optional[Callable[[str], bool]] = None, refresh: bool = False) -> str:
        """抓一頁並記在 pages；同一路徑本輪只抓一次（refresh=True 才重抓）。
        dorf1.php 呼叫端沒傳 raw_if 時自動套用 dorf1_raw_if：誰先抓都會拿到帶資源田成本的原始 HTML。"""
        if not refresh and path in self.pages:
            return self.pages[path]
        if raw_if is None and path.split("?", 1)[0].lstrip("/") == "dorf1.php":
            raw_if = self.dorf1_raw_if
        html = self.gateway.get(path, raw_if=raw_if)
        self.pages[path] = html
        return html
