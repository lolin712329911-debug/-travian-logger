#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scrub_sample.py v0.3（一次性工具，放在 repo 外；樣本脫敏）

用法：
  python scrub_sample.py SRC DST          脫敏 SRC 寫到 DST，並自動驗證（有問題 exit 1）
  python scrub_sample.py --verify FILE    只驗證已脫敏的檔案
  python scrub_sample.py --selftest       內建案例（含集結點概覽的 d=／他人村莊／俘虜）

v0.2 → v0.3 的變動（A2a-2b 前置；測試帳號 International 11 的樣本沒有寫死的名字可用）：
  1. 自動讀出自己的玩家名、村莊（id＋名稱）、玩家 uid、聯盟名：來源是頁內 viewData 的 ownPlayer／villageList、
     英雄頭像檔名的 uid、`allianceBanner` 旁的聯盟名；讀不到玩家名或村莊時退回 v0.2 寫死的舊服常數
     （所以 --selftest 與舊服樣本的輸出與 v0.2 相同，唯獨多替換聯盟名）。
  2. 村名連同 JSON 的 \\uXXXX 跳脫形式一併替換；聯盟名一律替換成 ALLIANCE。
  3. verify() 另外把頁面內容做 HTML 實體解碼與 \\uXXXX 解碼後再搜一次禁用字串（實體或跳脫形式的名字不會漏）。
  4. 自動讀到的名字在每次 scrub() 開始時重置禁用字串清單；--verify 單獨驗證時只能用 v0.2 的舊服常數，
     新樣本請以「脫敏當下」的輸出為準（或自行搜尋玩家名）。

v0.1 → v0.2 的變動（v0.1 對 S6 集結點頁會 KeyError，且 `karte.php?d=` 會洩漏真實座標）：
  1. 座標改為通用平移（每軸 SHIFT），在地圖範圍內環繞（寬 401），不再查表；平移與環繞都保持兩點距離。
     SHIFT 維持 (-100, -100)，所以對 v0.1 處理過的頁面輸出完全相同。
  2. `karte.php?d=N`：解出座標→平移→重新編碼，d 與座標在同一表格內仍互相吻合（d=0＝冒險，不動）。
     也處理 `karte.php?x=..&y=..`。
  3. 他人：`data-player-name` 的玩家名、`karte.php?d=` 連結文字的村名、`/profile/N` 的玩家 id、
     只在他人身上出現的 did（data-did／newdid／at／from／release）一律替換成編號代號。
  4. 新增 verify()：座標與 d 都在範圍內；每個 troop_details 表格的 d 與座標吻合；不含禁用字串。
替換：玩家名、聯盟名、村名、did、checksum、取消建設 event id、英雄頭像雜湊、座標、d=。
不動：class／data-* 屬性名、數字（數量／時間）、viewData 結構。"""
import html as _html
import json as _json
import re
import sys

MAP_HALF = 200
SPAN = 2 * MAP_HALF + 1
SHIFT = (-100, -100)                       # (x, y)；與 v0.1 相同

OWN_PLAYER = "doga"
DID = {"29786": "10001", "34593": "10002"}     # 自己的兩個村
NAME = {"29786": "VillageA", "34593": "VillageB"}
OWN_UID = {"2713": "1000"}
FORBIDDEN = ["doga", "29786", "34593", "ROHIRRIM", "2713"]   # verify 時不得出現；他人名稱由 scrub 動態加入
LEGACY_FORBIDDEN = list(FORBIDDEN)
LEGACY_VILLAGES = [("29786", "doga的村莊", "VillageA"), ("34593", "doga2", "VillageB")]

POSITIVE_COORD_NOTE = []     # 平移後出現非負座標時記錄（HTML 格式未用樣本驗證）


def shift(v, axis):
    return (v + SHIFT[axis] + MAP_HALF) % SPAN - MAP_HALF


def d_to_xy(d):
    n = d - 1
    return n % SPAN - MAP_HALF, MAP_HALF - n // SPAN


def xy_to_d(x, y):
    return (MAP_HALF - y) * SPAN + (x + MAP_HALF) + 1


def _numstr(v):
    return str(v)


def detect_own(h):
    """從頁面讀自己的資訊；讀不到的項目回 None／空 list。"""
    out = {"player": None, "villages": [], "uid": None, "alliance": None}
    m = re.search(r'"ownPlayer":\{"name":"((?:[^"\\]|\\.)*)"', h)
    if m:
        try:
            out["player"] = _json.loads('"%s"' % m.group(1))
        except ValueError:
            pass
    m = re.search(r'"villageList":\[(.*?)\]\}', h, re.S)
    if m:
        for vid, vname in re.findall(r'\{"id":(\d+),"name":"((?:[^"\\]|\\.)*)"', m.group(1)):
            try:
                out["villages"].append((vid, _json.loads('"%s"' % vname)))
            except ValueError:
                pass
    m = re.search(r"/heroV2/head/[0-9a-f]+\.(\d+)\.\d+\.png", h)
    if m:
        out["uid"] = m.group(1)
    m = re.search(r'allianceBanner"\s*/>\s*<div class="name">([^<]+)</div>', h)
    if m:
        out["alliance"] = _html.unescape(m.group(1)).strip()
    return out


def scrub(h):
    # ---- 自己：自動偵測，失敗退回舊服常數 ----
    own = detect_own(h)
    if own["player"] and own["villages"]:
        own_player = own["player"]
        own_villages = [(vid, vname, "Village" + chr(65 + i)) for i, (vid, vname) in enumerate(own["villages"])]
        own_did = {vid: str(10001 + i) for i, (vid, _n, _l) in enumerate(own_villages)}
        own_uid = {own["uid"]: "1000"} if own["uid"] else {}
        forbidden = [own_player] + [vid for vid, _n, _l in own_villages] + [n for _v, n, _l in own_villages] \
            + list(own_uid) + ["ROHIRRIM"]
    else:
        own_player, own_villages, own_did, own_uid = OWN_PLAYER, LEGACY_VILLAGES, dict(DID), dict(OWN_UID)
        forbidden = list(LEGACY_FORBIDDEN)
    alliance = own["alliance"]
    if alliance:
        forbidden.append(alliance)
    FORBIDDEN[:] = forbidden

    # ---- 蒐集他人（先於任何替換，避免被自己的替換干擾）----
    others_players = [p for p in dict.fromkeys(re.findall(r'data-player-name="([^"]+)"', h)) if p != own_player]
    others_uids = [u for u in dict.fromkeys(re.findall(r"/profile/(\d+)", h)) if u not in own_uid]
    did_pat = [r'data-did="(\d+)"', r"newdid=(\d+)", r"[?&;]at=(\d+)", r"[?&;]from=(\d+)", r"release=(\d+)"]
    other_dids = []
    for pat in did_pat:
        for d in re.findall(pat, h):
            if d not in own_did and d not in other_dids:
                other_dids.append(d)
    other_villages = []
    for d, text in re.findall(r'karte\.php\?d=(\d+)">\s*([^<\s][^<]*?)\s*</a>', h):
        if d != "0" and text not in other_villages and text not in [n for _v, n, _l in own_villages]:
            other_villages.append(text)

    # ---- 自己：村名（含 JSON 跳脫形式，長的先換）、玩家名、聯盟 ----
    for _vid, vname, label in sorted(own_villages, key=lambda t: -len(t[1])):
        h = h.replace(_json.dumps(vname)[1:-1], label).replace(vname, label)
    h = re.sub(r"(?<!\w)" + re.escape(own_player) + r"(?!\w)", "PLAYER", h)
    if alliance:
        h = h.replace(alliance, "ALLIANCE")
    h = h.replace("ROHIRRIM" + "KNIGHTS", "ALLIANCE")
    h = re.sub(r"/alliance/banner/\d+/[0-9A-Za-z]+\.svg", "/alliance/banner/0/000000000000.svg", h)
    h = re.sub(r"/heroV2/head/[0-9a-f]+\.\d+\.\d+\.png",
               "/heroV2/head/0000000000000000000000000000000000000000.0.0.png", h)
    h = re.sub(r"checksum=[0-9a-fA-F]+", "checksum=000000", h)
    h = re.sub(r"(showCancelBuildingDialog\(\s*)\d+", r"\g<1>1000000", h)

    # ---- 他人：村名（只動 karte 連結文字）、玩家名、玩家 id ----
    for i, text in enumerate(other_villages, 1):
        h = h.replace('">%s</a>' % text, '">OtherVillage%d</a>' % i)
    for i, name in enumerate(others_players, 1):
        FORBIDDEN.append(name)
        h = h.replace(name, "OtherPlayer%d" % i)
    for old, new in own_uid.items():
        h = h.replace("/profile/%s" % old, "/profile/%s" % new)
    for i, u in enumerate(others_uids, 1):
        FORBIDDEN.append(u)
        h = h.replace("/profile/%s" % u, "/profile/%d" % (2000 + i))

    # ---- did（自己與他人）----
    mapping = dict(own_did)
    for i, d in enumerate(other_dids, 1):
        mapping[d] = str(20000 + i)
        FORBIDDEN.append(d)
    for old, new in mapping.items():
        h = re.sub(r"(?<!\d)" + old + r"(?!\d)", new, h)

    # ---- d= 重算（d=0 是冒險，不動）----
    def dlink(m):
        d = int(m.group(2))
        if d == 0:
            return m.group(0)
        x, y = d_to_xy(d)
        if not (-MAP_HALF <= x <= MAP_HALF and -MAP_HALF <= y <= MAP_HALF):
            sys.stderr.write("警告：d=%d 超出地圖範圍，原樣保留\n" % d)
            return m.group(0)
        return m.group(1) + str(xy_to_d(shift(x, 0), shift(y, 1)))
    h = re.sub(r"(karte\.php\?d=)(\d+)", dlink, h)

    def xylink(m):
        return "%sx=%d%sy=%d" % (m.group(1), shift(int(m.group(2)), 0), m.group(3), shift(int(m.group(4)), 1))
    h = re.sub(r"(karte\.php\?)x=(-?\d+)(&(?:amp;)?)y=(-?\d+)", xylink, h)

    # ---- 座標：JSON 成對 "x":..,"y":.. ----
    def jx(m):
        return '"x":%d,"y":%d' % (shift(int(m.group(1)), 0), shift(int(m.group(2)), 1))
    h = re.sub(r'"x":(-?\d+),"y":(-?\d+)', jx, h)

    # ---- 座標：HTML coordinateX／coordinateY ----
    # 格式（✓ 舊服與測試帳號樣本）：負數＝`&minus;&#x202d;數字&#x202c;&#x202c;`（兩個 PDF），
    # 正數＝`&#x202d;數字&#x202c;`（一個 PDF；Y 軸正數已在測試帳號樣本見到，X 軸正數依對稱推定、未見樣本）。
    # 平移可能讓正負號改變，所以負→正時少一個 PDF、正→負時補一個。
    def side(m):
        axis = 0 if m.group(2) == "X" else 1
        v = -int(m.group(4)) if m.group(3) else int(m.group(4))
        nv = shift(v, axis)
        if nv < 0:
            return m.group(1) + "&minus;&#x202d;%d&#x202c;&#x202c;" % -nv
        if m.group(3) or nv >= 0:
            POSITIVE_COORD_NOTE.append((m.group(2), nv))
        return m.group(1) + "%d&#x202c;" % nv
    h = re.sub(r'(class="coordinate([XY])">\(?&#x202d;)(&minus;&#x202d;)?(\d+)&#x202c;(?:&#x202c;)?', side, h)
    return h


def verify(h):
    """回傳問題清單；空＝通過。"""
    bad = []
    decoded = _html.unescape(re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), h))
    for s in FORBIDDEN:
        if s and s in h:
            bad.append("殘留禁用字串：%s" % s)
        elif s and s in decoded:
            bad.append("殘留禁用字串（實體或 \\u 跳脫形式）：%s" % s)
    for m in re.finditer(r'"x":(-?\d+),"y":(-?\d+)', h):
        x, y = int(m.group(1)), int(m.group(2))
        if abs(x) > MAP_HALF or abs(y) > MAP_HALF:
            bad.append("JSON 座標超出範圍：(%d,%d)" % (x, y))
    for m in re.finditer(r"karte\.php\?d=(\d+)", h):
        d = int(m.group(1))
        if d and not (1 <= d <= SPAN * SPAN):
            bad.append("d 超出範圍：%d" % d)
    for m in re.finditer(r'<table[^>]*class="troop_details[^>]*>(.*?)</table>', h, re.S):
        blk = m.group(1)
        dm = re.search(r"karte\.php\?d=(\d+)\">", blk)
        cx = re.search(r'coordinateX">\(?&#x202d;(&minus;&#x202d;)?(\d+)', blk)
        cy = re.search(r'coordinateY">&#x202d;(&minus;&#x202d;)?(\d+)', blk)
        if dm and cx and cy and int(dm.group(1)) != 0:
            x = -int(cx.group(2)) if cx.group(1) else int(cx.group(2))
            y = -int(cy.group(2)) if cy.group(1) else int(cy.group(2))
            if xy_to_d(x, y) != int(dm.group(1)):
                bad.append("表格內 d=%s 與座標 (%d,%d) 不吻合（應為 %d）" % (dm.group(1), x, y, xy_to_d(x, y)))
    return bad


def _coord_html(axis, v):
    s = "&minus;&#x202d;%d" % -v if v < 0 else "%d" % v
    pre = "(&#x202d;" if axis == "X" else "&#x202d;"
    post = "&#x202c;&#x202c;" + (")" if axis == "Y" else "")
    return '<span class="coordinate%s">%s%s%s</span>' % (axis, pre, s, post)


def selftest():
    def tbl(did, ort, role_d, role_name, x, y, player):
        return ('<table class="troop_details " data-vid="3" data-did="%s" data-ort="%s" data-player-name="%s">'
                '<thead><tr><td class="role"><a href="/karte.php?d=%d">%s</a></td>'
                '<td class="troopHeadline"><a href="/profile/%s">x</a></td></tr></thead>'
                '<tbody><tr><th class="coords">%s<span class="coordinatePipe">|</span>%s</th></tr></tbody></table>'
                % (did, ort, player, role_d, role_name, "2713" if player == "doga" else "3787",
                   _coord_html("X", x), _coord_html("Y", y)))
    src = (
        '<table class="troop_details outHero"><thead><tr><td class="role"><a href="/karte.php?d=114461">doga2</a></td>'
        '<td class="troopHeadline"><a href="/karte.php?d=0">冒險</a></td></tr></thead></table>'
        + tbl("34593", "34593", 114461, "doga2", -25, -85, "doga")
        + tbl("29786", "34593", 109245, "doga的村莊", -28, -72, "doga")
        + tbl("32007", "34593", 115264, "ShadowWolf`s village", -24, -87, "ShadowWolf")
        + '<a href="/build.php?gid=16&tt=2&amp;eventType=9&amp;at=34593&amp;from=29786">送回</a>'
        + '<a href="/build.php?gid=16&tt=1&amp;release=32007">釋放</a>'
        + '<a href="/karte.php?x=-24&amp;y=-87">tile</a>'
        + '"villageList":[{"id":29786,"x":-28,"y":-72},{"id":34593,"x":-25,"y":-85}]'
        + '<a href="/profile/3787">ShadowWolf 的俘虜</a>'
        # 會環繞的座標：(-150,-190) -> (151,-290→111)
        + '"x":-150,"y":-190'
    )
    FORBIDDEN[:] = ["doga", "29786", "34593", "ROHIRRIM", "2713"]
    out = scrub(src)
    problems = verify(out)
    checks = [
        ("d=114461 → (-125,-185) 的 d", "karte.php?d=%d" % xy_to_d(-125, -185) in out),
        ("d=109245 → (-128,-172) 的 d", "karte.php?d=%d" % xy_to_d(-128, -172) in out),
        ("d=115264 → (-124,-187) 的 d", "karte.php?d=%d" % xy_to_d(-124, -187) in out),
        ("d=0 保留", "karte.php?d=0" in out),
        ("他人玩家名已替換", "ShadowWolf" not in out and "OtherPlayer1" in out),
        ("他人村名已替換", "OtherVillage1" in out),
        ("他人 did 已替換", "release=20001" in out and "32007" not in out),
        ("他人 profile id 已替換", "/profile/2001" in out and "3787" not in out),
        ("自己的 profile id 已替換", "/profile/1000" in out and "2713" not in out),
        ("at／from 對應自己的 did", "at=10002" in out and "from=10001" in out),
        ("karte x/y 平移", "karte.php?x=-124&amp;y=-187" in out),
        ("環繞座標在範圍內", '"x":151,"y":111' in out),
        ("兩村距離不變", abs(shift(-28, 0) - shift(-25, 0)) == 3 and abs(shift(-72, 1) - shift(-85, 1)) == 13),
        ("verify 無問題", not problems),
    ]
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("✓ " if ok else "✗ ") + name)
    for p in problems:
        print("  verify：" + p)
    return not bad


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        sys.exit(0 if selftest() else 1)
    if len(sys.argv) == 3 and sys.argv[1] == "--verify":
        issues = verify(open(sys.argv[2], encoding="utf-8", newline="").read())
        print("\n".join(issues) if issues else "OK")
        sys.exit(1 if issues else 0)
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    out = scrub(open(src, encoding="utf-8", newline="").read())
    open(dst, "w", encoding="utf-8", newline="").write(out)
    issues = verify(out)
    if POSITIVE_COORD_NOTE:
        sys.stderr.write("注意：%d 個座標平移後為非負，X 軸正數的 HTML 格式依對稱推定（未見樣本）：%s\n"
                         % (len(POSITIVE_COORD_NOTE), POSITIVE_COORD_NOTE[:5]))
    if issues:
        sys.stderr.write("\n".join(issues) + "\n")
        sys.exit(1)
    print("OK：%s → %s" % (src, dst))
