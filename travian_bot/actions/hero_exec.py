#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/hero_exec.py（ac-05）
版本：v0.2（difficulty bonus 防護改為依 allow_hard 決定）｜v0.1（A5a）
用途：read_hero(gw) → HeroState；click_adventure(gw, adventure, mode) → ExecResult（點擊前核對、點擊後重讀確認）。
依賴：if-02（Gateway，含 v0.2 的 click）、ps-05（parse_hero_status、parse_adventures）、cm-02、cm-04、cm-09（HeroState、Adventure）、cm-11（ParseError）（後兩者為 v0.1 補）。
部署狀態：未部署（GA 前不 live）。

來源 travian_ci_run.py 的 click_adventure（✓ 已讀，沿用）。舊安全規則原樣保留：
  點擊前重讀並核對（英雄在家、沒有 difficulty bonus、表格與 JSON 一致、清單沒變、該列內容與決策時相同、按鈕可按）；
  只點 `table.adventureList` 該列的按鈕（不碰「觀看影片」）；成功只看重讀結果、不看網路請求；不重試。
流程：off→skipped；渲染 hero/adventures → 核對 → dry 回 dry（不點）→ live 點擊 → 重讀（原始 HTML 即可）：
  status＝50（去程，✓ 樣本）且 adventure_no＝該冒險編號 → ok（verified=True）；否則 failed（verified=False）。
差異：
  1. 舊碼用 travian_hero 的解析與 H.STATUS_HOME；改用 ps-05。在家判斷＝HUD at_home 為真且沒有 adventure_no／arrival_in_s
     （在家時 status 碼沒有樣本，✗，所以不靠它）；表格與 JSON 不一致由 parse_adventures 丟 ParseError → 回 failed。
  2. 舊碼直接用 page.locator；改用 Gateway.click（v0.2）。選擇器 `…tr:nth-child(N) td.button button`，N＝該冒險在清單的位置。
  3. 比對決策時的 Adventure：編號、地點、距離、秒數、難度、icon（兩邊都有值才比）。
  4. 舊碼失敗不丟例外，只回 (False, 說明)；本層回 ExecResult，例外一律接住。
v0.2 修改：
  difficulty bonus 為真＝下一次普通冒險會被遊戲升成困難。v0.1 一律不點，和 domain 層 v0.1 一樣會形成死結。
  改成呼叫端傳 allow_hard（hard 在允許清單且體力夠）：allow_hard 為 True 時，bonus 為真也照點（被升成困難是可接受的）；
  allow_hard 為 False（預設，維持原本安全行為）時，bonus 為真仍不點。
"""
from typing import Optional

from ..common.decisions import ExecResult
from ..common.modes import Mode
from ..common.parsed import Adventure, HeroState
from ..common.schema import ParseError
from ..infra.gateway import Gateway, GatewayError
from ..parsers.hero import parse_adventures, parse_hero_status

__all__ = ["read_hero", "click_adventure"]

ADVENTURES_PATH = "hero/adventures"
_STATUS_GOING = 50      # ✓ 樣本 S18c（hero.py 檔頭）：冒險去程


def _mode_value(mode) -> str:
    v = str(getattr(mode, "value", mode)).strip().lower()
    return v if v in ("off", "dry", "live") else "off"


def _same(a: Adventure, b: Adventure) -> bool:
    if (a.number, a.place, a.difficulty, a.duration_s) != (b.number, b.place, b.difficulty, b.duration_s):
        return False
    if abs(a.distance - b.distance) > 1e-9:
        return False
    return a.icon is None or b.icon is None or a.icon == b.icon


def read_hero(gw: Gateway) -> HeroState:
    """唯讀：冒險頁原始 HTML（HUD＋viewData）。失敗丟 GatewayError／ParseError。"""
    return parse_hero_status(gw.get(ADVENTURES_PATH, raw=True))


def click_adventure(gw: Gateway, adventure: Adventure, mode: Mode, allow_hard: bool = False) -> ExecResult:
    m = _mode_value(mode)
    if m == "off":
        return ExecResult("skipped", "mode=off，不動作", 0, None)

    n0 = gw.request_count()
    what = f"冒險 #{adventure.number}（{adventure.place}，距離 {adventure.distance}，去程 {adventure.duration_s // 60} 分）"

    def res(result: str, detail: str, verified: Optional[bool] = None) -> ExecResult:
        return ExecResult(result, detail, gw.request_count() - n0, verified)

    # 1) 點擊前重讀並核對（渲染頁：要有 table.adventureList 才有 icon／clickable）
    try:
        html = gw.get(ADVENTURES_PATH)
        hero = parse_hero_status(html)
        advs = parse_adventures(html)
    except (GatewayError, ParseError) as e:
        return res("failed", f"{what}：點擊前重讀失敗，不點：{e}")
    if hero.at_home is not True or hero.adventure_no is not None or hero.arrival_in_s is not None:
        return res("skipped", f"{what}：英雄已不在家或讀不到在家狀態，不點")
    if hero.difficulty_bonus and not allow_hard:
        return res("skipped", f"{what}：difficulty bonus 為真，且不允許困難冒險，不點")
    idx = next((i for i, a in enumerate(advs) if a.number == adventure.number), None)
    if idx is None:
        return res("skipped", f"{what}：清單裡已沒有這個冒險（清單變了），不點")
    if not _same(advs[idx], adventure):
        return res("skipped", f"{what}：該列內容和決策時不同，不點")
    if advs[idx].clickable is not True:
        return res("skipped", f"{what}：頁面沒有可按的按鈕（沒有表格或按鈕 disabled），不點")

    if m == "dry":
        return res("dry", f"{what}：會點擊第 {idx + 1} 列（乾跑，沒有真的點擊）")

    # 2) 點擊（不重試）→ 重讀確認
    selector = f"table.adventureList tbody tr:nth-child({idx + 1}) td.button button"
    try:
        gw.click(selector)
    except GatewayError as e:
        return res("failed", f"{what}：點擊時出錯（可能已送達，不重試）：{e}")
    try:
        after = read_hero(gw)
    except (GatewayError, ParseError) as e:
        return res("failed", f"{what}：已點擊，但重讀失敗，無法確認（不重試）：{e}")
    if after.status == _STATUS_GOING and after.adventure_no == adventure.number:
        eta = f"，約 {after.arrival_in_s} 秒後抵達" if after.arrival_in_s is not None else ""
        return res("ok", f"{what}：已確認出發{eta}", True)
    return res("failed", f"{what}：點擊後重讀沒看到出發（狀態／編號 = {after.status}／{after.adventure_no}）", False)
