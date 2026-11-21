#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scrub_sample.py v0.4（一次性工具，放在 repo 外；樣本脫敏）

用法：
  python scrub_sample.py SRC DST          脫敏 SRC 寫到 DST，並自動驗證（有問題 exit 1）
  python scrub_sample.py --verify FILE    只驗證已脫敏的檔案
  python scrub_sample.py --tiles SRC DST  脫敏區塊 JSON（`{"tiles":[…]}`，S16）：自動辨識 UTF-8／UTF-8-BOM／Big5(cp950)，一律輸出 UTF-8
  python scrub_sample.py --verify-tiles FILE   只驗證已脫敏的區塊 JSON
  python scrub_sample.py --selftest       內建案例（含集結點概覽的 d=／他人村莊／俘虜／攻擊者標題／區塊 JSON）

v0.3 → v0.4 的變動（International 11、Asia 8 集結點樣本與 S16 區塊 JSON；v0.3 對攻擊者名字與短名字有漏洞）：
  1. 攻擊者／來襲者玩家名：`troopHeadline` 連結文字是「<名字> <動詞> <自己的村名>」（動詞語言相依，如「搶奪」「攻擊」），
     v0.3 只認 `data-player-name`，來襲表的名字全部漏掉而 verify 仍顯示 OK。現在以「<名字> <單一詞> <自己的村名>」辨識（名字可含空格），
     與 `data-player-name`、`/profile/N` 連結文字一併編成 OtherPlayerN。
  2. 攻擊標記 id：`markAttackSymbol(N)`／`markSymbol_N` 的 N 依出現順序換成 900000001…（同一個 N 全頁一致）。
  3. 玩家名替換與 verify 都改成「字詞邊界」比對（名字全是 ASCII 字母數字或底線時）：短名字（例如 rat）不再誤傷 `TownHallCelebration`
     這類字串，也不再誤報。含非 ASCII 字元的名字仍用子字串比對。
  4. 新增 `--tiles`：S16 區塊 JSON 的脫敏。逐格處理：`position` 平移（與頁面相同的 SHIFT 與環繞）、`text` 內嵌的座標 HTML 平移、
     `{k.dt} 村名` → `{k.dt} VillageN`（`{k.dt} Natars x|y` 只平移座標）、`{k.spieler} 名` → `PlayerN`、`{k.allianz} 名` → `AllianceN`、
     `uid`／`aid`／`did`（正數）→ 流水號；`did`=-1 等非正數不動。同一個名字或 id 全檔一致。輸出 UTF-8（`ensure_ascii=False`、縮排 4、LF）。
  5. 編碼：區塊 JSON 以 Big5 存檔時（Windows cp950 另存）會被轉成 UTF-8；Big5 無法表示的字元在存檔當時已變成 `?`，無法還原
     （都在玩家名／村名裡，會被替換，不影響 golden）。


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


def _name_re(name):
    """名字全是 ASCII 字母數字／底線 → 字詞邊界；否則（含中文等）→ 子字串。"""
    if re.fullmatch(r"[A-Za-z0-9_]+", name):
        return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
    return re.compile(re.escape(name))


def _has(text, name):
    return bool(_name_re(name).search(text))


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
    for _vid, vname, _l in own_villages:   # 來襲表標題「<名字> <動詞> <自己的村名>」（v0.4）
        for nm, _verb in re.findall(r'<a href="/karte\.php\?d=\d+">\s*([^<>]+?) (\S+) %s\s*</a>' % re.escape(vname), h):
            if nm != own_player and nm not in others_players:
                others_players.append(nm)
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
        h = _name_re(name).sub("OtherPlayer%d" % i, h)
    for old, new in own_uid.items():
        h = h.replace("/profile/%s" % old, "/profile/%s" % new)
    for i, u in enumerate(others_uids, 1):
        FORBIDDEN.append(u)
        h = h.replace("/profile/%s" % u, "/profile/%d" % (2000 + i))

    # ---- 攻擊標記 id（v0.4）----
    for i, a in enumerate(dict.fromkeys(re.findall(r"markAttackSymbol\((\d+)\)", h)), 1):
        FORBIDDEN.append(a)
        h = re.sub(r"(?<!\d)" + a + r"(?!\d)", str(900000000 + i), h)

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
        if s and _has(h, s):
            bad.append("殘留禁用字串：%s" % s)
        elif s and _has(decoded, s):
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



# ---------------------------------------------------------------------------
# 區塊 JSON（S16）
# ---------------------------------------------------------------------------
TILES_FORBIDDEN = []


def read_text_auto(path):
    """UTF-8（含 BOM）優先；失敗再試 Big5(cp950)。回 (text, encoding)。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp950"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit("無法以 UTF-8 或 Big5 解碼：%s" % path)


def _shift_coord_html(h):
    def side(m):
        axis = 0 if m.group(2) == "X" else 1
        v = -int(m.group(4)) if m.group(3) else int(m.group(4))
        nv = shift(v, axis)
        if nv < 0:
            return m.group(1) + "&minus;&#x202d;%d&#x202c;&#x202c;" % -nv
        return m.group(1) + "%d&#x202c;" % nv
    return re.sub(r'(class="coordinate([XY])">\(?&#x202d;)(&minus;&#x202d;)?(\d+)&#x202c;(?:&#x202c;)?', side, h)


def scrub_tiles(data):
    """data：已解析的 {"tiles":[…]}（就地不改，回新物件）。回 (新資料, 對照表)。"""
    import copy
    out = copy.deepcopy(data)
    players, alliances, villages = {}, {}, {}
    uids, aids, dids = {}, {}, {}
    TILES_FORBIDDEN[:] = []

    def code(table, key, fmt, start=1):
        if key not in table:
            n = start + len(table)
            table[key] = fmt % n if "%" in fmt and "d" in fmt[-2:] and fmt != "%d" else (n if fmt == "%d" else fmt % n)
        return table[key]

    for t in out["tiles"]:
        pos = t.get("position") or {}
        if "x" in pos and "y" in pos:
            pos["x"], pos["y"] = shift(pos["x"], 0), shift(pos["y"], 1)
        title = t.get("title", "")
        if title.startswith("{k.dt} "):
            rest = title[len("{k.dt} "):]
            m = re.fullmatch(r"Natars (-?\d+)\|(-?\d+)", rest)
            if m:
                t["title"] = "{k.dt} Natars %d|%d" % (shift(int(m.group(1)), 0), shift(int(m.group(2)), 1))
            else:
                TILES_FORBIDDEN.append(rest)
                t["title"] = "{k.dt} " + code(villages, rest, "Village%d")
        text = t.get("text", "")

        def sp(m):
            if m.group(1) == "Natars":           # 遊戲內建帳號，不是個資；uid=1 也保留
                return m.group(0)
            TILES_FORBIDDEN.append(m.group(1))
            return "{k.spieler} " + code(players, m.group(1), "Player%d")

        def al(m):
            if not m.group(1):
                return m.group(0)
            TILES_FORBIDDEN.append(m.group(1))
            return "{k.allianz} " + code(alliances, m.group(1), "Alliance%d")
        text = re.sub(r"\{k\.spieler\} ([^<]*)", sp, text)
        text = re.sub(r"\{k\.allianz\} ([^<]*)", al, text)
        t["text"] = _shift_coord_html(text)
        if isinstance(t.get("uid"), int) and t["uid"] > 1:
            t["uid"] = code(uids, t["uid"], "%d", 2001)
        if isinstance(t.get("aid"), int) and t["aid"] > 0:
            t["aid"] = code(aids, t["aid"], "%d", 3001)
        if isinstance(t.get("did"), int) and t["did"] > 0:
            t["did"] = code(dids, t["did"], "%d", 20001)
    return out, {"players": len(players), "alliances": len(alliances), "villages": len(villages),
                 "uid": len(uids), "aid": len(aids), "did": len(dids)}


def verify_tiles(out_text, src_data=None):
    """回傳問題清單；空＝通過。src_data 給定時另檢查格數不變、禁用字串不殘留。"""
    bad = []
    try:
        d = _json.loads(out_text)
    except ValueError as e:
        return ["不是合法 JSON：%s" % e]
    tiles = d.get("tiles")
    if not isinstance(tiles, list):
        return ["缺少 tiles 陣列"]
    seen = set()
    for t in tiles:
        p = t.get("position", {})
        k = (p.get("x"), p.get("y"))
        if k in seen:
            bad.append("座標重複：%s" % (k,))
        seen.add(k)
        if abs(p.get("x", 0)) > MAP_HALF or abs(p.get("y", 0)) > MAP_HALF:
            bad.append("座標超出範圍：%s" % (k,))
    if src_data is not None and len(tiles) != len(src_data["tiles"]):
        bad.append("格數改變：%d → %d" % (len(src_data["tiles"]), len(tiles)))
    if src_data is not None:
        for i, (a, b) in enumerate(zip(src_data["tiles"], tiles)):
            for f in ("uid", "aid", "did"):
                if isinstance(a.get(f), int) and a[f] > 1 and a[f] == b.get(f):
                    bad.append("第 %d 格 %s 未替換：%s" % (i, f, a[f]))
    for s_ in TILES_FORBIDDEN:
        if s_ and _has(out_text, s_):
            bad.append("殘留禁用字串：%s" % s_)
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
    # v0.4：攻擊者標題、攻擊標記 id、短名字邊界
    src4 = (
        '<script>Travian.AttackSymbol.markAttackSymbol(194976507);</script><img id="markSymbol_194976507" />'
        '<table class="troop_details inRaid"><thead><tr><td class="role"><a href="/karte.php?d=3623">Hideout</a></td>'
        '<td class="troopHeadline"><a href="/karte.php?d=114461">rat 搶奪 doga2</a></td></tr></thead></table>'
        '<table class="troop_details inRaid"><thead><tr><td class="role"><a href="/karte.php?d=3624">Camp</a></td>'
        '<td class="troopHeadline"><a href="/karte.php?d=114461">Big Wolf 攻擊 doga2</a></td></tr></thead></table>'
        '{"type":"TownHallCelebration"}'
    )
    FORBIDDEN[:] = ["doga", "29786", "34593", "ROHIRRIM", "2713"]
    out4 = scrub(src4)
    p4 = verify(out4)
    checks += [
        ("攻擊者名字（短名）已替換", "rat 搶奪" not in out4 and "OtherPlayer1 搶奪" in out4),
        ("攻擊者名字（含空格）已替換", "Big Wolf" not in out4 and "OtherPlayer2 攻擊" in out4),
        ("短名字不誤傷 TownHallCelebration", "TownHallCelebration" in out4),
        ("攻擊標記 id 已替換且前後一致", "markAttackSymbol(900000001)" in out4 and "markSymbol_900000001" in out4 and "194976507" not in out4),
        ("verify（v0.4 樣本）無問題", not p4),
    ]
    # 區塊 JSON
    tiles_src = {"tiles": [
        {"position": {"x": -20, "y": -90}, "did": -1, "title": "{k.fo}", "text": "x"},
        {"position": {"x": -19, "y": -90}, "uid": 41, "aid": 17, "did": 777, "title": "{k.bt}",
         "text": "{k.spieler} Dodo<br />{k.allianz} Zeta<br />&#x202d;<span class=\"coordinates\"><span class=\"coordinateX\">(&#x202d;&minus;&#x202d;19&#x202c;&#x202c;</span><span class=\"coordinatePipe\">|</span><span class=\"coordinateY\">&#x202d;&minus;&#x202d;90&#x202c;&#x202c;)</span></span>"},
        {"position": {"x": -18, "y": -90}, "uid": 41, "aid": 0, "did": 778, "title": "{k.dt} Dodo`s village", "text": "{k.spieler} Dodo<br />{k.allianz} "},
        {"position": {"x": -17, "y": -81}, "uid": 1, "aid": 0, "did": 1, "title": "{k.dt} Natars -17|-81", "text": "{k.spieler} Natars"},
    ]}
    tout, cnt = scrub_tiles(tiles_src)
    ttext = _json.dumps(tout, ensure_ascii=False)
    checks += [
        ("區塊：座標平移", tout["tiles"][0]["position"] == {"x": -120, "y": -190}),
        ("區塊：玩家名／聯盟名編號", "Player1" in ttext and "Alliance1" in ttext and "Dodo" not in ttext and "Zeta" not in ttext),
        ("區塊：同一玩家同一代號", ttext.count("Player1") == 2 and cnt["players"] == 1 and "Natars" in ttext),
        ("區塊：uid／aid／did 換成流水號", tout["tiles"][1]["uid"] == 2001 and tout["tiles"][1]["aid"] == 3001 and tout["tiles"][1]["did"] == 20001),
        ("區塊：did=-1 與 aid=0 不動", tout["tiles"][0]["did"] == -1 and tout["tiles"][2]["aid"] == 0),
        ("區塊：Natars 標題座標平移", tout["tiles"][3]["title"] == "{k.dt} Natars -117|-181"),
        ("區塊：text 內座標平移", "&minus;&#x202d;119&#x202c;" in ttext and "&minus;&#x202d;190&#x202c;" in ttext),
        ("區塊：verify 無問題", not verify_tiles(ttext, tiles_src)),
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
    if len(sys.argv) == 4 and sys.argv[1] == "--tiles":
        text, enc = read_text_auto(sys.argv[2])
        data = _json.loads(text)
        out, cnt = scrub_tiles(data)
        out_text = _json.dumps(out, ensure_ascii=False, indent=4)
        open(sys.argv[3], "w", encoding="utf-8", newline="\n").write(out_text + "\n")
        issues = verify_tiles(out_text, data)
        print("來源編碼：%s｜%d 格｜%s" % (enc, len(out["tiles"]), cnt))
        if issues:
            sys.stderr.write("\n".join(issues) + "\n")
            sys.exit(1)
        print("OK：%s → %s" % (sys.argv[2], sys.argv[3]))
        sys.exit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--verify-tiles":
        text, _enc = read_text_auto(sys.argv[2])
        issues = verify_tiles(text)
        print("\n".join(issues) if issues else "OK（只檢查結構；名字殘留要在脫敏當下驗證）")
        sys.exit(1 if issues else 0)
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
