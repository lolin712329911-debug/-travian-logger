#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/main.py（ap-01）
版本：v0.1.1（A6b：merge_settings 例外改為 hold＋通知；hard 啟動檢查 hold 也通知）
用途：GitHub Actions 入口（`python -m travian_bot.app.main`）。
      讀 Secrets→開 Sheet 讀 Config→建 Session／Gateway／RunContext→確認登入→讀村莊清單→
      啟動檢查（verify_against_page；hard＝本輪 hold）→merge_settings→orchestrator.run→存 session。
依賴：if-01、if-02、if-03、if-04、if-05、if-06、cm-01、cm-05、cm-06、cm-08、cm-10、cm-11、cm-13、ps-01、ps-02、ap-02、ap-08。
部署狀態：未部署（GA 前不 live）。

環境變數（Secrets 名稱 v0.57 已定）：
  TRAVIAN_SEED_COOKIE_S2、GOOGLE_SHEET_ID_S2、GOOGLE_SERVICE_ACCOUNT_JSON  必填
  DRY_RUN  預設 "1"：寫入類 mode 一律降 dry（A-8）；只有明確設 "0" 才是正式
不再讀：TRAVIAN_BASE_URL（改讀 Config 的 server_*）、QUIET_UTC（不保留）。
結束碼：0＝正常；1＝設定／登入／啟動檢查有問題，或本輪有 stage／村失敗（讓 GitHub 寄失敗信）。

處置：拆（舊 travian_ci_run.main；安靜時段 keep-alive 不保留；dispatch.configure 改由 HideContext）。

已對照原始碼 ✓：gsheets v0.2、Session v0.1、Gateway v0.2、RunContext／real_io v0.1.2、stage_base v0.1。
✗ 仍未核對：config_schema.MODE_TO_CTX 的方向、merge_settings 的參數與回傳、CfgProblem 的欄位名、
  notify 的 level 合法值（所以只呼叫 notify(msg)）。
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from ..common import clock, config_schema, serialize, tribe_data
from ..common.models import ValidationError
from ..common.schema import ParseError
from ..common.server_profile import verify_against_page
from ..infra.gateway import Gateway, GatewayLimits
from ..infra.notify import notify
from ..infra.session import Session, SessionLost
from ..infra.store import config_repo, gsheets, village_repo
from ..parsers.village import parse_page_facts
from ..parsers.village_list import parse_village_list
from . import orchestrator
from .run_context import RunContext, real_io

STATE_PATH = Path("travian_session.json")
DORF1 = "dorf1.php"


def _say(level: str, msg: str) -> None:
    print(f"{serialize.to_utc_str(clock.utc_now())} {level} main - {serialize.redact(msg)}")


def _open_sheet(sa_json: str, sheet_id: str) -> Any:
    return gsheets.open_sheet(gsheets.get_credentials(sa_json), sheet_id)      # ✓ gsheets.py v0.2


def _modes_from_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # ✗ MODE_TO_CTX 方向假設為 Config 鍵（如 hide_mode）→ C9 modes 鍵（如 hide）
    return {ctx: cfg[key] for key, ctx in config_schema.MODE_TO_CTX.items() if key in cfg}


def _fetch_dorf1(rc: RunContext) -> str:
    """確認登入：不是村莊頁就 recover 一次重抓；仍失效丟 SessionLost（寫進 rc.pages，observe 沿用）。"""
    not_village = lambda h: not rc.session.is_village_html(h)   # noqa: E731
    html = rc.get_page(DORF1, raw_if=not_village)
    if not rc.session.is_village_html(html) and rc.session.can_recover:
        rc.session.recover()
        html = rc.get_page(DORF1, raw_if=not_village, refresh=True)
    if not rc.session.is_village_html(html):
        rc.pages.pop(DORF1, None)
        raise SessionLost("dorf1 不是村莊頁，登入狀態失效")
    return html


def _build_contexts(cfg: Dict[str, Any], sh: Any, refs: Any) -> Any:
    """merge_settings 的包裝：不合法（main_did 不在頁面清單、無法選村、Villages 列尚未支援等）＝本輪 hold。

    成功回 list[VillageContext]；失敗 _say＋notify 後回 None（呼叫端 return 1）。
    """
    try:
        return config_schema.merge_settings(cfg, village_repo.load_villages(sh), refs)
    except (ValidationError, NotImplementedError) as exc:
        msg = f"村莊設定合併失敗，本輪 hold（{type(exc).__name__}）：{exc}"
        _say("ERROR", msg)
        notify(msg)
        return None


def _session_lost(rc: RunContext, msg: str) -> int:
    """登入失效：正式模式才 disable 帳號（DRY 不動共用 Config，避免測試分支把正式排程停掉）。"""
    if rc.dry_flag:
        notify(msg + "（DRY 模式：不修改 Config 的 enabled）")
        return 1
    try:
        rc.io.disable(rc.sh, "account", None, msg)
    except Exception as exc:  # noqa: BLE001
        _say("ERROR", f"disable 失敗：{type(exc).__name__}")
    notify(msg)
    return 1


def main() -> int:
    dry_flag = os.getenv("DRY_RUN", "1") != "0"
    seed = os.getenv("TRAVIAN_SEED_COOKIE_S2", "")
    sheet_id = os.getenv("GOOGLE_SHEET_ID_S2", "")
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    missing = [n for n, v in (("TRAVIAN_SEED_COOKIE_S2", seed), ("GOOGLE_SHEET_ID_S2", sheet_id),
                              ("GOOGLE_SERVICE_ACCOUNT_JSON", sa_json)) if not v]
    if missing:
        _say("ERROR", "缺少環境變數：" + "、".join(missing))
        return 1
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _say("ERROR", "缺少 playwright，請確認 requirements.txt 與 workflow 有安裝")
        return 1

    sh = _open_sheet(sa_json, sheet_id)
    cfg, problems = config_repo.load_normalized(sh)
    for p in problems:
        _say("ERROR" if p.severity == "error" else "WARN", f"Config {p.key}：{p.message}")
    if any(p.severity == "error" for p in problems):
        _say("ERROR", "Config 有錯誤，本輪不動作")
        return 1
    if not cfg.get("enabled", False):
        _say("INFO", "Config 的 enabled 不是 TRUE，本輪不動作")
        return 0
    try:
        profile = config_schema.profile_from_cfg(cfg)
        tribe = tribe_data.get_tribe(profile.tribe)
    except ValidationError as exc:
        _say("ERROR", f"伺服器設定不合法：{exc}")
        return 1
    _say("INFO", f"DRY_RUN={'1' if dry_flag else '0'}（寫入類 mode 在 DRY_RUN=1 時一律降 dry）")

    with sync_playwright() as p:
        try:
            session = Session.launch(p, profile, STATE_PATH, seed)
        except SessionLost as exc:
            _say("ERROR", f"建立 session 失敗：{exc}")
            notify(f"建立 session 失敗：{exc}")
            return 1
        code = 1
        alive = False
        try:
            gateway = Gateway(session, profile, GatewayLimits())
            rc = RunContext(cfg=cfg, profile=profile, tribe=tribe, gateway=gateway, session=session, sh=sh,
                            io=real_io(notify), dry_flag=dry_flag, modes=_modes_from_cfg(cfg))
            try:
                html = _fetch_dorf1(rc)
                alive = True
            except SessionLost as exc:
                return _session_lost(rc, f"登入狀態失效，請更新 TRAVIAN_SEED_COOKIE_S2：{exc}")

            try:
                refs = parse_village_list(html, profile.map_half)
                facts = parse_page_facts(html)
            except ParseError as exc:
                _say("ERROR", f"讀不到村莊清單或頁面資訊，本輪 hold：{type(exc).__name__}")
                return 1
            hard: List[str] = []
            for pr in verify_against_page(profile, facts):
                _say("ERROR" if pr.severity == "hard" else "WARN",
                     f"啟動檢查 {pr.key}：預期 {pr.expected}、實際 {pr.actual}")
                if pr.severity == "hard":
                    hard.append(pr.key)
            if hard:
                msg = "啟動檢查有 hard 問題，本輪 hold（不動作）：" + "、".join(hard)
                _say("ERROR", msg)
                notify(msg)
                return 1

            vcs = _build_contexts(cfg, sh, refs)
            if vcs is None:
                return 1
            try:
                report = orchestrator.run(rc, refs, vcs)
            except SessionLost as exc:
                alive = False
                return _session_lost(rc, f"執行中登入狀態失效：{exc}")
            code = 1 if report.failed else 0
            return code
        finally:
            if alive:
                try:
                    session.save_state()
                except Exception as exc:  # noqa: BLE001
                    _say("WARN", f"存 session 失敗：{type(exc).__name__}")
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    sys.exit(main())
