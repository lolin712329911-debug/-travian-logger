#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travian_bot/parsers/oasis.py（ps-08）
版本：v0.1（A2b）
用途：地圖區塊 JSON（`{"tiles": […]}`）中綠洲格的解析。純函式：資料進、資料出，不連遊戲、不連 Sheet。
依賴：cm-09（parsed）、cm-03（constants，BIDI）、cm-11（schema，ParseError）。
部署狀態：未部署（GA 前不 live）。

公開介面
  parse_block_json(data) → tuple[BlockOasis, ...]
      data 為 str／bytes（JSON 文字）或 dict；只回綠洲格（座標、已佔領與否、加成、動物、持有人名），頁面順序；
      村莊、Natars、地形格忽略。JSON 結構不符（不是物件、沒有 `tiles` 清單）→ ParseError。

來源：舊 oasis_scan.py（✓ 已讀）的 parse_tiles；§5.1 判定五條皆成立 → 套用（沿用＋修改）。
有意的修改（golden 以新行為為準）：
  1. 資源編號 1～4 → cm-03 的 0～3（RES_WOOD…）；加成為 (資源索引, 百分比)。
  2. bonus_label 的中文標籤不進 parser（顯示由呼叫端用 RES_NAMES）。
  3. free_candidates、blocked_set 依賴 dispatch 的距離與 HOME，屬篩選決策 → 歸 domain，不搬。
  4. 不依賴任何中文字面：只認翻譯鍵 `{k.fo}`（未佔領）、`{k.bt}`（已佔領）、`{a:rN}`（加成）、`{k.animals}`、`{k.spieler}`；
     地形格的標題一律忽略（v0.46 有損貼上的地形格標題是翻譯鍵 `{k.vt} {k.fN}`，S16 的地形格標題是中文字面「森林」「山」「泥地」）。
  5. 有「加成」但分不出未佔領／已佔領（沒有 `{k.fo}`、`{k.bt}`、uid）、加成或動物讀不出來 → ParseError（舊版會當未佔領，
     而「未佔領」是安全判斷的前提，不能猜）；動物欄位與清單沒有 `{k.animals}`＝空 tuple。
  6. 持有人名去 BIDI 與 HTML 跳脫。
樣本：S16（舊服 Asia 8 區塊 JSON，249 格：地形 138＋45、村莊 34、未佔領綠洲 25〔8 無動物、17 有動物〕、已佔領綠洲 7）。
      ✗ 樣本裡沒有明確的荒地格；`{a:rN}` 的 N 與資源對應（1 木、2 磚、3 鐵、4 穀）仍只是 Travian 慣例，樣本沒有直接證明（✗）。
ParseError 的訊息只放原因，不放資料內容。
"""
import html as _html
import json
import re
from typing import Any, Tuple

from ..common.constants import BIDI
from ..common.parsed import BlockOasis
from ..common.schema import ParseError

__all__ = ["parse_block_json"]

_PAGE = "oasis"
_BONUS_RE = re.compile(r"\{a:r(\d)\}\s*\{a\.r\d\}\s*(\d+)%")
_ANIMAL_RE = re.compile(r'class="unit u(\d+)"></i><span class="value\s*">(\d+)</span>')
_OWNER_RE = re.compile(r"\{k\.spieler\}\s*([^<]*)")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _load(data: Any) -> dict:
    if isinstance(data, (bytes, bytearray)):
        try:
            data = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            raise ParseError(_PAGE, "JSON 不是 UTF-8 文字")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            raise ParseError(_PAGE, "不是合法的 JSON")
    if not isinstance(data, dict) or not isinstance(data.get("tiles"), list):
        raise ParseError(_PAGE, "JSON 沒有 tiles 清單")
    return data


def parse_block_json(data: Any) -> Tuple[BlockOasis, ...]:
    out = []
    for i, t in enumerate(_load(data)["tiles"]):
        if not isinstance(t, dict):
            raise ParseError(_PAGE, f"第 {i + 1} 格不是物件")
        text = t.get("text", "")
        if not isinstance(text, str) or "{a:r" not in text:
            continue                                    # 只收綠洲（有加成）；村莊、Natars、地形格忽略
        title = t.get("title", "")
        title = title if isinstance(title, str) else ""
        pos = t.get("position")
        if not (isinstance(pos, dict) and _is_int(pos.get("x")) and _is_int(pos.get("y"))):
            raise ParseError(_PAGE, f"第 {i + 1} 格是綠洲但座標讀不到")

        taken = "{k.bt}" in title or "uid" in t
        if not taken and "{k.fo}" not in title:
            raise ParseError(_PAGE, f"第 {i + 1} 格是綠洲但分不出未佔領或已佔領")

        bonuses = []
        for n, pct in _BONUS_RE.findall(text):
            if not 1 <= int(n) <= 4:
                raise ParseError(_PAGE, f"第 {i + 1} 格的加成資源編號不在 1～4")
            bonuses.append((int(n) - 1, int(pct)))
        if not bonuses:
            raise ParseError(_PAGE, f"第 {i + 1} 格有加成標記但讀不出加成")

        animals = ()
        if "{k.animals}" in text:
            part = text.split("{k.animals}", 1)[1]
            animals = tuple((int(u), int(n)) for u, n in _ANIMAL_RE.findall(part))
            if not animals:
                raise ParseError(_PAGE, f"第 {i + 1} 格標示有動物但讀不出種類與數量")

        om = _OWNER_RE.search(text)
        owner = BIDI.sub("", _html.unescape(om.group(1))).strip() if om else None
        out.append(BlockOasis(x=pos["x"], y=pos["y"], taken=taken, bonuses=tuple(bonuses),
                              animals=animals, owner=owner or None))
    return tuple(out)
