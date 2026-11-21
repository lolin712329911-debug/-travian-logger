#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/actions/oasis_exec.py（ac-07）
版本：v0.1（A5b）
用途：fetch_block(gw, x, y, *, map_half) → dict；scan(gw, center, radius, *, map_half) → tuple[BlockOasis, …]；
      verify_oasis(gw, target, *, map_half) → TileSafety（派兵前即時驗證）。三者都是唯讀（不改變遊戲狀態），所以沒有 mode。
依賴：if-02（Gateway）、ps-08（parse_block_json）、ps-09（parse_tile_details）、cm-09（BlockOasis、TileSafety）、
      cm-07（geo.map_id；卡片原未列，v0.1 補）。
部署狀態：未部署（GA 前不 live）。

來源：舊 oasis_store.py 的 fetch_block、scan（✓ 已讀）、舊 hide_troops.py 的 _fetch_tile（✓ 已讀）。
判定：**重新規劃**（§5.1(b)(e) 不成立，需改簽名；與卡片差異如下，待你同意卡片）：
  1. scan 回傳型別 list[Oasis] → tuple[BlockOasis, …]：ps-08 輸出的是 BlockOasis（含 taken／bonuses／animals／owner），
     cm-01 的 Oasis 只有規劃用的 x／y／kind／safe，會丟資料。
  2. 全域 dispatch.HOME／MAP_SIZE／_half() → 參數 center、map_half；環境變數 OASIS_ENDPOINT／OASIS_ZOOM → 參數 zoom（預設 1）
     與模組常數 BLOCK_ENDPOINT；time.sleep → 注入的 sleep；page.request.post → Gateway.request（登入狀態由 session 帶）。
  3. 解析一律走 ps-08／ps-09；舊 oasis_check.is_safe／recent_occupy_warning 屬決策，不搬（歸 domain，A3c）。
  4. verify_oasis 回 TileSafety（事實＋保守的 safe），不在這裡做「附近剛有佔領事件」判斷；
     並以 geo.map_id 核對頁面座標與 map_id、與要求的座標一致（ps-09 檔頭交給呼叫端的核對在這裡做），不一致丟 OasisExecError。
錯誤：HTTP 非 2xx、回應不是 JSON 物件、區塊格子範圍太小、請求數超過上限、座標核對不符 → OasisExecError；
      連線失敗 GatewayError、解析失敗 ParseError 原樣往上丟（呼叫端自己接）。訊息不含頁面內容與帳號資料。
✗ 區塊 POST 的 body 格式與 tile-details 的 data 以舊碼為準（舊服＋v2.84 新服 Actions 跑通，✓ 讀碼；本層未實機驗證）。
"""
import json
import math
import time
from typing import Any, Callable, Dict, Sequence, Tuple

from ..common.geo import map_id as geo_map_id
from ..common.parsed import BlockOasis, TileSafety
from ..infra.gateway import Gateway
from ..parsers.oasis import parse_block_json
from ..parsers.tile import parse_tile_details

__all__ = ["OasisExecError", "BLOCK_ENDPOINT", "TILE_ENDPOINT", "fetch_block", "scan", "verify_oasis"]

BLOCK_ENDPOINT = "/api/v1/map/position"          # ✓ 舊 oasis_store v2.84
TILE_ENDPOINT = "/api/v1/map/tile-details"       # ✓ 舊 hide_troops
DEFAULT_ZOOM = 1


class OasisExecError(RuntimeError):
    """綠洲請求的結果不能用（HTTP 非 2xx、格式不對、範圍太小、座標核對不符、請求數超上限）。"""


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_half(map_half: Any) -> int:
    if not _is_int(map_half) or map_half < 1:
        raise ValueError("map_half 需為 int ≥ 1")
    return map_half


def _wrap(v: int, map_half: int) -> int:
    """座標環繞到 -map_half..map_half。"""
    return (v + map_half) % (2 * map_half + 1) - map_half


# ---------------------------------------------------------------- 抓區塊
def fetch_block(gw: Gateway, x: int, y: int, *, map_half: int, zoom: int = DEFAULT_ZOOM) -> Dict[str, Any]:
    """POST 一次，回 {"tiles": […]}（dict）。座標先環繞。HTTP 非 2xx 或不是 JSON 物件丟 OasisExecError。"""
    if not (_is_int(x) and _is_int(y)):
        raise ValueError("x、y 需為 int")
    if not _is_int(zoom) or zoom < 1:
        raise ValueError("zoom 需為 int ≥ 1")
    half = _check_half(map_half)
    resp = gw.request(
        "POST", BLOCK_ENDPOINT,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{gw.base_url}/karte.php"},
        data={"data": {"x": _wrap(x, half), "y": _wrap(y, half), "zoomLevel": zoom, "ignorePositions": []}})
    if not resp.ok:
        raise OasisExecError(f"區塊請求失敗：HTTP {resp.status}")
    try:
        data = json.loads(resp.text)
    except ValueError:
        raise OasisExecError("區塊回應不是 JSON") from None
    if not isinstance(data, dict):
        raise OasisExecError("區塊回應不是 JSON 物件")
    return data


def _span(data: Dict[str, Any]) -> Tuple[int, int]:
    tiles = data.get("tiles")
    if not isinstance(tiles, list):
        raise OasisExecError("區塊回應沒有 tiles 清單")
    if not tiles:
        return 0, 0
    xs, ys = [], []
    for t in tiles:
        pos = t.get("position") if isinstance(t, dict) else None
        try:
            xs.append(int(pos["x"]))
            ys.append(int(pos["y"]))
        except (TypeError, KeyError, ValueError):
            raise OasisExecError("區塊格子缺座標") from None
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


# ---------------------------------------------------------------- 掃描
def scan(gw: Gateway, center: Sequence[int], radius: int = 15, *, map_half: int, max_requests: int = 30,
         pause_s: float = 0.5, sleep: Callable[[float], None] = time.sleep, zoom: int = DEFAULT_ZOOM,
         fetch: Callable[..., Dict[str, Any]] = fetch_block) -> Tuple[BlockOasis, ...]:
    """以 center 為中心掃 radius 格內的綠洲。第一次請求量出一次回傳涵蓋多大，再依此排格子（不寫死 11×9）。
    依座標去重（重疊格子取後來的），順序＝第一次出現的順序。超過 max_requests 丟 OasisExecError（在第一次之後才知道，沿用舊行為）。"""
    if len(center) != 2 or not (_is_int(center[0]) and _is_int(center[1])):
        raise ValueError("center 需為 (x, y) 兩個 int")
    if not _is_int(radius) or radius < 1:
        raise ValueError("radius 需為 int ≥ 1")
    if not _is_int(max_requests) or max_requests < 1:
        raise ValueError("max_requests 需為 int ≥ 1")
    half = _check_half(map_half)
    hx, hy = center

    first = fetch(gw, hx, hy, map_half=half, zoom=zoom)
    w, h = _span(first)
    if w < 3 or h < 3:
        raise OasisExecError(f"回傳格子範圍太小（{w}×{h}），請求參數可能不對")
    sx, sy = max(1, w - 1), max(1, h - 1)               # 步距＝涵蓋寬高 -1（留 1 格重疊）
    nx, ny = math.ceil(radius / sx), math.ceil(radius / sy)
    centers = [(hx + i * sx, hy + j * sy) for j in range(-ny, ny + 1) for i in range(-nx, nx + 1)]
    centers.sort(key=lambda c: abs(c[0] - hx) + abs(c[1] - hy))     # 穩定排序：中心點（距離 0）永遠第一個
    if len(centers) > max_requests:
        raise OasisExecError(f"radius={radius} 需要 {len(centers)} 次請求，超過上限 {max_requests}")

    seen: Dict[Tuple[int, int], BlockOasis] = {}
    for k, (cx, cy) in enumerate(centers):
        if k:
            sleep(pause_s)                              # 別連打
        data = first if k == 0 else fetch(gw, cx, cy, map_half=half, zoom=zoom)
        for o in parse_block_json(data):
            seen[(o.x, o.y)] = o
    return tuple(seen.values())


# ---------------------------------------------------------------- 即時驗證
def verify_oasis(gw: Gateway, target: Any, *, map_half: int, locale: str = "zh-TW") -> TileSafety:
    """派兵前即時驗證：tile-details → ps-09。target 要有 .x／.y（BlockOasis、cm-01 Oasis 都可）。
    座標必須與要求一致、且頁面的 map_id 必須等於 geo.map_id(x, y, map_half)，否則 OasisExecError（不回「安全」）。"""
    x, y = getattr(target, "x", None), getattr(target, "y", None)
    if not (_is_int(x) and _is_int(y)):
        raise ValueError("target 需有 int 的 x、y")
    half = _check_half(map_half)
    resp = gw.request("POST", TILE_ENDPOINT, data={"x": x, "y": y})
    if not resp.ok:
        raise OasisExecError(f"格子詳情請求失敗：HTTP {resp.status}")
    try:
        body = json.loads(resp.text)
        html = body["html"] if isinstance(body, dict) else None
    except (ValueError, KeyError):
        html = None
    if not isinstance(html, str):
        raise OasisExecError("格子詳情回應沒有 html 欄")
    info = parse_tile_details(html, locale)
    if (info.x, info.y) != (x, y):
        raise OasisExecError("格子詳情的座標與要求不符")
    if info.map_id != geo_map_id(x, y, half):
        raise OasisExecError("格子詳情的地圖格編號與座標不符")
    return info
