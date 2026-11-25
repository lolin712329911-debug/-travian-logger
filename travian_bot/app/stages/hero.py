#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/app/stages/hero.py（ap-17）
版本：v0.2（hero_allowed 字串拆分修正）｜v0.1（A6a2）
用途：英雄冒險 stage（帳號級）：讀英雄 → domain.adventure 決策 → actions.hero_exec 點冒險 → 寫 Actions（動作「冒險」）。
依賴：ap-03、ap-06、dm-06、ac-05、if-07、cm-02。
部署狀態：未部署（GA 前不 live）。未實測。

來源：runner.py `run_hero_cycle`、`_hero_log`（✓）。卡片寫「沿用（純搬）」，實際要改的地方：
  1. 開關：舊 Config hero_adventure → hero_mode（off／dry／live，由 stage_base 處理）。
  2. 英雄狀態：ac-05 read_hero（冒險頁原始 HTML；HUD＋viewData）。舊版用 dorf1 HUD 的體力是因為渲染頁 title 常被清空，
     ac-05 取原始 HTML，不再有這個問題。讀到後更新 rc.hero。
  3. 冒險清單：不在家等一定 skip 的情況不抓；其餘才抓渲染頁（要 table.adventureList 的 icon／clickable）並用 ps-05 parse_adventures。
  4. 來襲數：dorf1（rc.get_page）的 incoming_attacks（目前村；舊版同）；dorf1 不是村莊頁（session 問題）→ 略過。
  5. 不再 sleep(2～6)：等待交給 GatewayLimits（ac-02 檔頭同）。
  6. skip 的寫法同舊版：status 50／9（去程／返回）安靜略過；其他 skip 寫一列 skipped（舊「未出發」）。
  7. 帳號級：did＝Config main_did；沒有就 skipped（寫不了 Actions）。
"""
from ...actions.hero_exec import ADVENTURES_PATH, click_adventure, read_hero
from ...common.models import StageResult
from ...common.modes import Mode
from ...common.schema import ParseError
from ...domain.adventure import AdventureSettings, decide_adventure
from ...infra.gateway import GatewayError
from ...parsers.hero import parse_adventures
from ...parsers.village import parse_dorf1
from ..run_context import RunContext
from ..stage_base import Stage
from . import _util as U

__all__ = ["STAGE", "precondition", "run"]

_STATUS_GOING, _STATUS_RETURNING, _STATUS_HOME = 50, 9, 100


def precondition(rc: RunContext, vc, snap) -> bool:
    return True


def _parse_allowed(raw) -> frozenset:
    """hero_allowed 可能是 list/tuple/set，也可能是設定表來的逗號字串（"normal,hard"）。
    字串直接丟 frozenset 會被拆成單一字元，所以先用逗號切開、去空白、轉小寫。"""
    if not raw:
        return frozenset({"normal"})
    if isinstance(raw, str):
        raw = raw.split(",")
    items = [str(x).strip().lower() for x in raw if str(x).strip()]
    return frozenset(items) or frozenset({"normal"})


def _settings(cfg) -> AdventureSettings:
    return AdventureSettings(min_health=int(cfg.get("hero_min_health", 45)),
                             hard_min_health=int(cfg.get("hero_hard_min_health", 60)),
                             allowed=_parse_allowed(cfg.get("hero_allowed")),
                             skip_on_incoming=bool(cfg.get("hero_skip_on_incoming", False)))


def run(rc: RunContext, vc, snap, mode: Mode) -> StageResult:
    did = (rc.cfg or {}).get("main_did")
    if not isinstance(did, int) or isinstance(did, bool) or did < 1:
        return StageResult(status="skipped", note="main_did 未鎖定，英雄冒險不跑")
    gw, settings = rc.gateway, _settings(rc.cfg)

    d1_html = rc.get_page("dorf1.php")
    if not rc.session.is_village_html(d1_html):
        return StageResult(status="skipped", note="dorf1 不是村莊頁（session 問題由建城流程處理）")
    incoming = parse_dorf1(d1_html).incoming_attacks

    try:
        hero = read_hero(gw)
    except (GatewayError, ParseError) as e:
        rc.io.notify(f"英雄流程出錯（不影響建城）: {e!r}")
        row = U.make_row(rc, did, U.ACTION_HERO, mode, "failed", f"讀取英雄狀態失敗｜{e!r}")
        return StageResult(status="failed", actions=[row], note=f"讀取英雄失敗：{type(e).__name__}")
    rc.hero = hero

    # 一定 skip 的情況不抓冒險頁（和 decide_adventure 的前幾條一致）
    quick_skip = (hero.status not in (None, _STATUS_HOME) or hero.at_home is not True
                  or hero.adventure_no is not None or hero.arrival_in_s is not None)
    if quick_skip:
        dec = decide_adventure(hero, (), settings, incoming)
        if hero.status in (_STATUS_GOING, _STATUS_RETURNING):
            return StageResult(status="ok", note=f"略過：{dec.reason}")      # 去程／返回中：正常等待，不寫列
        row = U.make_row(rc, did, U.ACTION_HERO, mode, "skipped", dec.reason)
        return StageResult(status="ok", actions=[row])

    try:
        advs = parse_adventures(rc.get_page(ADVENTURES_PATH))
    except (GatewayError, ParseError) as e:
        rc.io.notify(f"英雄冒險略過：{e!r}")
        row = U.make_row(rc, did, U.ACTION_HERO, mode, "failed", f"讀取冒險清單失敗｜{e!r}")
        return StageResult(status="failed", actions=[row], note=f"讀取冒險清單失敗：{type(e).__name__}")

    dec = decide_adventure(hero, advs, settings, incoming)
    if not dec.act:
        return StageResult(status="ok", actions=[U.make_row(rc, did, U.ACTION_HERO, mode, "skipped", dec.reason)])

    adv = next(a for a in advs if a.number == dec.adv_id)
    res = click_adventure(gw, adv, mode)
    what = f"{dec.reason}（體力 {hero.health_pct}%，來襲 {incoming}）"
    if res.result == "ok":
        rc.io.notify(f"英雄已出發：{what}")
    elif res.result == "failed":
        rc.io.notify(f"英雄冒險沒有確認成功（不重試）：{res.detail}")
    row = U.make_row(rc, did, U.ACTION_HERO, mode, res.result, f"{what}｜{res.detail}")
    return StageResult(status="failed" if res.result == "failed" else "ok", actions=[row],
                       note=res.detail if res.result == "failed" else "")


STAGE = Stage(name="hero", scope="account", mode_key="hero", order=60, precondition=precondition, run=run)
