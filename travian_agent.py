"""
Travian (ts11.x1.international) 資源田升級排程（純解析 + 決策，不含網路 / Sheet）
- parse_dorf1(): 解析 dorf1.php 原始碼（依你貼的頁面結構寫）
- plan():        純規則決策（不用 LLM）
- run():         Playwright 持久登入 + 迴圈；DRY_RUN=True 時只印出決定，不點擊

安裝: pip install playwright beautifulsoup4 requests && playwright install chromium
"""
import html as _html
import json
import os
import random
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup

from travian_const import (  # noqa: F401  重新匯出：runner / village_log 等仍用 T.xxx 存取
    BIDI, BUILD_CATEGORIES, BUILDING_GIDS, DEFAULT_TARGET_BUILDING_LEVEL, FREE_SLOT_RANGE,
    GID_NAMES, MAX_NON_CAPITAL_FIELD_LEVEL, RES_NAMES, RESOURCE_FIELD_PRODUCTION,
    ROMAN_TRIBE_ID, TRIBE_NAMES, gid_name,
)
from travian_models import Field, Slot, State  # noqa: F401

# ---------------- 設定 ----------------
BASE = "https://ts11.x1.international.travian.com"
DRY_RUN = True            # 確認決策正確後才改 False
TARGET_LEVEL = 2          # 資源田先升到這個等級
QUEUE_SLOTS = 2           # Plus 有效時 2；Plus 到期後請改 1（未驗證，請以遊戲內為準）
QUIET_HOURS = (2, 7)      # 這段伺服器時間不運作
UPGRADE_BUTTON = "button.textButtonV1.green.build"   # ← 未驗證，需用 build.php 頁面確認
PROFILE_DIR = "./travian_profile"

# 0 = 停用村莊中心建築自動升級（預設，因為只是剛驗證過解析，還沒實際跑過）。
# 要啟用時設一個 >0 的目標等級即可；Sheet 的 Config 分頁可用
# target_building_level 這個 key 覆蓋（見 runner.py 的 load_config()）。
TARGET_BUILDING_LEVEL = DEFAULT_TARGET_BUILDING_LEVEL


IS_CAPITAL = False   # Config 可用 is_capital 覆蓋（見 runner.py）；不確定就留 False


def _roi_key(f):
    """排序鍵：(每花費一單位資源能換到的每小時新增產量的倒數, 工期)，越小越優先。
    也就是「花費 ÷ 每小時新增產量」，比值越小代表 CP/資源投報率越好，愈早升愈划算。
    查不到這個等級的產量資料（超出上面那張表的範圍）時，退回舊規則（總花費、工期）,
    確保排序永遠有結果，不會因為缺資料而卡住或報錯。"""
    gain = RESOURCE_FIELD_PRODUCTION.get(f.level + 1)
    base = RESOURCE_FIELD_PRODUCTION.get(f.level)
    cost = sum(f.cost)
    if f.gid not in (1, 2, 3, 4) or gain is None or base is None or gain <= base or cost <= 0:
        return (2, cost, f.secs)        # 排在「有 ROI 資料」的後面，但仍是穩定排序
    return (1, cost / (gain - base), f.secs)


# ---------------- 解析 ----------------
def _js_dict(block: str, key: str) -> dict:
    m = re.search(key + r":\s*\{([^}]*)\}", block)
    return {k: int(v) for k, v in re.findall(r'"(l\d)":\s*(-?\d+)', m.group(1))} if m else {}


def _hms(s: str) -> int:
    h, m, sec = (int(x) for x in s.split(":"))
    return h * 3600 + m * 60 + sec


def _queue_label(li, secs: int) -> str:
    """施工佇列一項的文字：'農場 等級 1 剩0:01:46'。抓不到名稱時顯示 '（未知建築）'。"""
    n = li.select_one("div.name")
    name, lvl = "", ""
    if n is not None:
        lv = n.select_one("span.lvl")
        if lv is not None:
            lvl = BIDI.sub("", lv.get_text(" ", strip=True))
            lv.extract()
        name = BIDI.sub("", n.get_text(" ", strip=True))
    left = f"剩{secs // 3600}:{secs % 3600 // 60:02d}:{secs % 60:02d}"
    return " ".join(x for x in (name or "（未知建築）", lvl, left) if x)


def parse_dorf1(html: str) -> State:
    # 1) 資源量/容量/產量：直接讀頁面內的 var resources（比讀畫面數字可靠）
    blk = re.search(r"var resources = \{(.*?)\};", html, re.S)
    blk = blk.group(1) if blk else ""
    prod, stock, cap = (_js_dict(blk, k) for k in ("production", "storage", "maxStorage"))
    st = State(
        stock=[stock.get(f"l{i}", 0) for i in range(1, 5)],
        cap=[cap.get(f"l{i}", 0) for i in range(1, 5)],
        prod=[prod.get(f"l{i}", 0) for i in range(1, 5)],
        free_crop=prod.get("l5", 0),
    )

    soup = BeautifulSoup(html, "html.parser")

    # 2) 資源田：等級在 class，升級成本/時間在 title（HTML 實體，bs4 會解碼）
    for a in soup.select("#resourceFieldContainer a.resourceField"):
        cls = " ".join(a.get("class", []))
        lvl = re.search(r"\blevel(\d+)\b", cls)
        tip = a.get("title", "")
        cost = [int(v) for _, v in sorted(re.findall(r'class="r(\d)Big"></i><span class="value ">(\d+)<', tip))]
        dur = re.search(r'clock_medium"></i><span class="value ">(\d+:\d+:\d+)<', tip)
        st.fields.append(Field(
            aid=int(a["data-aid"]), gid=int(a["data-gid"]),
            level=int(lvl.group(1)) if lvl else 0,
            cost=cost, secs=_hms(dur.group(1)) if dur else 0,
            building="underConstruction" in cls,
        ))

    # 3) 施工佇列（選擇器未驗證：需要一份「正在施工」的 dorf1 來確認）
    for li in soup.select("div.buildingList li"):
        t = li.select_one("span.timer")
        if t and t.get("value", "").isdigit():
            st.queue.append(int(t["value"]))
            st.queue_info.append(_queue_label(li, int(t["value"])))

    # 4) 來襲：注意 .incomingTroops 圖示在沒有來襲時也存在，不能用「元素存在」判斷
    st.attacks = sum(int(x) for x in re.findall(r'incomingAttacksAmount":(\d+)', html))
    st.movements = parse_movements(soup)
    etas = [m["seconds"] for m in st.movements if m["kind"] == "attack" and m["seconds"] is not None]
    st.attack_eta_s = min(etas) if etas else None

    # 5) 新手保護 / Plus 剩餘秒數（用中文文字比對）
    for li in soup.select("#sidebarBoxInfobox li"):
        txt = BIDI.sub("", li.get_text(" ", strip=True))
        t = li.select_one("span.timer")
        if not (t and t.get("value", "").isdigit()):
            continue
        if "新手保護" in txt:
            st.protection_s = int(t["value"])
        elif "Plus" in txt:
            st.plus_s = int(t["value"])
    return st


# ---------------- 來村部隊（dorf1 的 #movements 表格） ----------------
# 已用真實頁面確認：img.att1 = 即將抵達的敵人軍隊（攻擊）、img.def1 = 即將抵達的援軍。
# 其他 class（自己出發的部隊、掠奪等）還沒看過樣本，原樣保留在 kind 裡，不猜意思。
_MOVEMENT_KINDS = {"att1": "attack", "def1": "reinforcement"}


def parse_movements(soup) -> list:
    """回傳 [{"kind": "attack"|"reinforcement"|<原 class>, "count": int|None, "seconds": int|None, "label": str}]。
    soup 可以是 BeautifulSoup 物件或 HTML 字串。沒有 #movements 表格 = 空 list。"""
    if isinstance(soup, str):
        soup = BeautifulSoup(soup, "html.parser")
    tbl = soup.find(id="movements")
    out = []
    if tbl is None:
        return out
    for tr in tbl.find_all("tr"):
        img = tr.select_one("td.typ img")
        if img is None:
            continue
        cls = next((c for c in img.get("class", []) if re.fullmatch(r"(att|def|rai|rei)\d+", c)), "")
        label = BIDI.sub("", (tr.select_one("div.mov") or tr).get_text(" ", strip=True))
        n = re.match(r"\s*(\d+)", label)
        t = tr.select_one("span.timer")
        secs = int(t["value"]) if t is not None and t.get("value", "").isdigit() else None
        out.append({"kind": _MOVEMENT_KINDS.get(cls, cls or "unknown"),
                    "count": int(n.group(1)) if n else None, "seconds": secs, "label": label})
    return out


def parse_dorf2(html: str) -> dict:
    """解析 dorf2.php（村莊中心），回傳 {gid: (aid, level)}，
    只保留 BUILDING_GIDS 裡關心的建築（目前是倉庫/糧倉）。
    尚未建造的位置沒有 a.level，level 視為 0（跳過，不會被當成候選，
    因為蓋新建築跟升級既有建築的按鈕/流程不一樣，尚未驗證）。"""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for slot in soup.select("#villageContent .buildingSlot"):
        try:
            aid, gid = int(slot["data-aid"]), int(slot["data-gid"])
        except (KeyError, ValueError):
            continue
        if gid not in BUILDING_GIDS:
            continue
        a = slot.select_one("a.level")
        if not a or not a.get("data-level", "").isdigit():
            continue
        out[gid] = (aid, int(a["data-level"]))
    return out


def parse_building_cost(html: str) -> tuple:
    """解析 build.php?id=<aid> 的村莊中心建築頁面（倉庫/糧倉），回傳 (cost, secs)。
    跟資源田的 tooltip 格式不同（debug_village_buildings.py 已驗證）：
      - 成本/時間直接寫在頁面正文，不是 <a> 的 title 屬性
      - 成本的 class 是 "value value"（資源田是單一個 "value "）
      - 數字外層包了雙向文字控制字元 \\u202d...\\u202c，跟 BIDI 常數要清的是同一種，
        用同一個 BIDI.sub 清掉即可（不影響 \\d+，只是保險起見先清乾淨）
      - 時間前面多一個 </div>："clock_medium"></i></div><span..."
    """
    clean = BIDI.sub("", html)
    cost = [int(v) for _, v in sorted(
        re.findall(r'class="r(\d)Big"></i><span class="value value">(\d+)<', clean))]
    # 工期欄位跟成本欄位的 class 不一樣：這裡其實是 "value "（單一個，跟資源田同格式），
    # 不是成本用的 "value value"（兩個）。原本兩個都用 "value value" 找，導致 secs 永遠是 0。
    dur = re.search(r'clock_medium"></i></div><span class="value ">(\d+:\d+:\d+)<', clean)
    return cost, (_hms(dur.group(1)) if dur else 0)


# ---------------- 玩家資訊：種族 / Plus / 文化點（頁面內嵌的 viewData JSON） ----------------
# dorf2 頁面（已用真實頁面確認）的側邊欄有一段 `viewData: {...}`，裡面的 ownPlayer 有
# tribeId、goldFeatures.travianPlus.isActive、culturalPointsOverview。dorf1 有沒有同一段
# 還沒確認，所以讀不到時呼叫端要改讀 dorf2，兩邊都沒有就退回保守值，不要猜。


def parse_player_info(html: str):
    """回傳 {"tribe_id": int|None, "plus_active": bool|None, "cp": dict|None}；整段找不到回傳 None。
    cp = {"have": 已累積, "need": 下一個村莊需要, "per_day": 每日產量, "used": 已用名額, "max": 名額上限}。"""
    m = re.search(r"viewData:\s*(\{)", html)
    if not m:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html, m.start(1))
        p = data["ownPlayer"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(p, dict):
        return None

    plus = ((p.get("goldFeatures") or {}).get("travianPlus") or {}).get("isActive")
    tribe = p.get("tribeId")
    cp = None
    c = p.get("culturalPointsOverview")
    if isinstance(c, dict):
        try:
            cp = {"have": int(c["cpProducedForNextSlot"]), "need": int(c["cpNeededForNextSlot"]),
                  "per_day": int(c["cpProductionTotal"]),
                  "used": int(c["usedSlots"]), "max": int(c["maxControllableVillages"])}
        except (KeyError, TypeError, ValueError):
            cp = None
    return {"tribe_id": tribe if isinstance(tribe, int) else None,
            "plus_active": plus if isinstance(plus, bool) else None,
            "cp": cp}


def queue_limit(tribe_id: int, plus_active: bool) -> int:
    """施工佇列長度的推估規則：羅馬族基本 2 條（資源田、建築各一）、其他種族 1 條；
    Plus 有效再多 1 格「等待佇列」（排隊等前一項完成，不是並行）。
    依據：官方說明只把同時施工兩項列為羅馬族的種族加成；Plus 的多排一格對非羅馬族的效果官方頁沒寫清楚，
    只有你這個帳號 Plus 有效時 dorf2 曾同時列出兩項施工可以佐證。所以這是推估，Config 的 queue_slots
    填數字就會蓋過它。羅馬族的兩條是「各自一條線」，這裡只算總數，沒有分線（見 README）。"""
    return (2 if tribe_id == ROMAN_TRIBE_ID else 1) + (1 if plus_active else 0)


def resolve_queue_slots(manual, info):
    """回傳 (佇列長度, 說明文字)。優先順序：Config 手動數字 > 自動偵測 > 保守值 1。"""
    if manual is not None:
        return manual, "Config 手動指定"
    if info and info.get("tribe_id") is not None and info.get("plus_active") is not None:
        tid, plus = info["tribe_id"], info["plus_active"]
        return queue_limit(tid, plus), f"自動偵測：{TRIBE_NAMES.get(tid, f'種族 {tid}')}、Plus {'有效' if plus else '未啟用'}"
    return 1, "偵測不到種族/Plus，保守用 1"


def cp_summary(cp: dict) -> str:
    """把文化點缺口整理成一行 log。"""
    have, need, per_day = cp["have"], cp["need"], cp["per_day"]
    slots = f"村莊名額 {cp['used']}/{cp['max']}"
    gap = need - have
    if gap <= 0:
        return f"[文化點] {have}/{need}，已達標；{slots}"
    if per_day > 0:
        eta = f"，照目前每日 +{per_day} 約 {-(-gap // per_day)} 天（不含慶典）"
    else:
        eta = "，目前每日產量是 0"
    return f"[文化點] {have}/{need}，缺 {gap}{eta}；{slots}"


def parse_dorf2_slots(html: str) -> list:
    """解析 dorf2.php，回傳村莊中心「所有」建築位（含空地）的 Slot 清單。
    選擇器（#villageContent .buildingSlot / data-aid / data-gid / a.level[data-level]）
    已用真實頁面驗證過（debug_village_buildings.py 抓到 22 個建築位）。
    「施工中」是看 class 有沒有 underConstruction（跟 dorf1 資源田同名），
    這點在 dorf2 上還沒用真實的「施工中」頁面驗證過。"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for slot in soup.select("#villageContent .buildingSlot"):
        try:
            aid, gid = int(slot["data-aid"]), int(slot["data-gid"])
        except (KeyError, ValueError):
            continue
        a = slot.select_one("a.level")
        lv = a.get("data-level", "") if a is not None else ""
        cls = " ".join(slot.get("class", [])) + " " + " ".join(a.get("class", []) if a is not None else [])
        out.append(Slot(aid=aid, gid=gid, level=int(lv) if lv.isdigit() else 0,
                        name=slot.get("data-name", ""), building="underConstruction" in cls))
    return out


# ---------------- 空地「建造新的建築物」頁面（gid=0） ----------------
def _clean_text(el) -> str:
    """取出元素文字，去掉雙向文字控制字元。"""
    return BIDI.sub("", el.get_text("", strip=True)) if el is not None else ""


def _to_int(s: str) -> int:
    """'2,880' -> 2880。頁面上的數字可能有千分位逗號。"""
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


# 「興建/擴建」按鈕的網址只認這一種格式（已在真實頁面看過的：
# /dorf1.php?id=7&gid=3&action=build&checksum=76c9cd、/dorf2.php?id=35&gid=17&action=build&checksum=89273d）。
# 多任何參數（例如金幣的 &buildmaster、看廣告的 &as=）一律不算，避免不小心花金幣。
_BUILD_URL_RE = re.compile(r"/dorf[12]\.php\?id=\d+&gid=\d+&action=build&checksum=[0-9a-fA-F]+")


_rejected_seen = set()   # 同一個被拒絕的網址在同一輪只警告一次，避免洗版


def _mask_checksum(u: str) -> str:
    """log 裡不要留下完整的 checksum，只留長度，方便判斷格式有沒有變。"""
    return re.sub(r"(checksum=)([^&]+)", lambda m: f"{m.group(1)}<{len(m.group(2))}字元>", u)


def _safe_build_url(url: str):
    u = _html.unescape(url or "")
    if _BUILD_URL_RE.fullmatch(u):
        return u
    # 被拒絕時留一行警告，這樣遊戲哪天多加參數、導致所有升級都變成「找不到按鈕」時，
    # 看 log 就知道是網址格式變了。金幣（buildmaster）、看廣告（&as=）是預期中要拒絕的，不記。
    if u and "buildmaster" not in u and not re.search(r"[?&]as=", u) and u not in _rejected_seen:
        _rejected_seen.add(u)
        print(f"[警告] 升級按鈕的網址不符合白名單格式，已忽略（遊戲改版了嗎？）：{_mask_checksum(u)}")
    return None


def find_upgrade_url(build_page_html: str):
    """只認綠色 build 按鈕，而且網址必須通過白名單；紫色的「建構25%更快」(看廣告加速)、
    金幣的按鈕一律不碰。"""
    soup = BeautifulSoup(build_page_html, "html.parser")
    for b in soup.select("button.green.build"):
        m = re.search(r"location\.href\s*=\s*'([^']+)'", b.get("onclick", ""))
        u = _safe_build_url(m.group(1)) if m else None
        if u:
            return u
    return None


def parse_build_options(html: str) -> list:
    """解析 build.php?id=<空地> 的「建造新的建築物」頁面（body 內 #build.gid0）。
    每個建築一個 dict：
      gid, name
      cost            [木, 磚, 鐵, 糧]
      secs            工期（秒）；不能蓋時頁面不顯示工期，為 0
      buildable       True = 頁面上有綠色「興建建築物」按鈕
      url             上述按鈕的網址（不含紫色看廣告加速、金幣的按鈕）；不能蓋時為 None
      resource_short  頁面出現「交換資源」按鈕 = 目前資源不足
      exceeds_storage 「交換資源」按鈕是 disabled = 成本超過倉庫/糧倉容量
      conditions      前置條件清單，每筆：
                        gid, name, level (要求的等級)
                        met      True = 已達成
                        current  目前等級（未達成時頁面才會給；達成時為 None）
                        forbidden True = 被劃掉的建築，代表「不能已經有這棟」（例如蓋行宮前不能有皇宮）
    注意：條件只會出現在「還不能蓋」的建築上；能蓋的建築沒有條件清單。
    """
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for w in soup.select('div.buildingWrapper[id^="contract_building"]'):
        m = re.search(r"contract_building(\d+)", w.get("id", ""))
        if not m:
            continue
        gid = int(m.group(1))

        # 成本：只認 r1Big~r4Big；cropConsumptionBig（穀物消耗）不算
        cost = {}
        for r in w.select("div.contractWrapper div.resource"):
            i = r.select_one("i")
            mm = re.search(r"\br([1-4])Big\b", " ".join(i.get("class", []))) if i is not None else None
            v = r.select_one("span.value")
            if mm and v is not None:
                cost[int(mm.group(1))] = _to_int(_clean_text(v))

        box = w.select_one("div.upgradeButtonsContainer")
        url, secs = None, 0
        if box is not None:
            for b in box.select("button.green"):
                mm = re.search(r"location\.href\s*=\s*'([^']+)'", b.get("onclick", ""))
                url = _safe_build_url(mm.group(1)) if mm else None
                if url:
                    break
            # section1 才是正常工期；section2（看廣告加速）的工期比較短，不能拿來用
            d = box.select_one("div.section1 .duration span.value")
            dm = re.search(r"\d+:\d+:\d+", _clean_text(d))
            if dm:
                secs = _hms(dm.group(0))

        conds = []
        if box is not None:
            for c in box.select("span.buildingCondition"):
                a = c.find("a")
                om = re.search(r"open\('building',\s*(\d+)\)", a.get("onclick", "")) if a else None
                lvl_el = next((s for s in c.find_all("span", recursive=False)), None)
                lm = re.search(r"等級\s*(\d+)", _clean_text(lvl_el))
                cur = re.search(r"目前等級:\s*(\d+)", BIDI.sub("", lvl_el.get("title", ""))) if lvl_el is not None else None
                conds.append({
                    "gid": int(om.group(1)) if om else 0,
                    "name": _clean_text(a),
                    "level": int(lm.group(1)) if lm else 0,
                    "met": "error" not in c.get("class", []),
                    "current": int(cur.group(1)) if cur else None,
                    "forbidden": bool(a and a.find("span", style=re.compile("line-through"))),
                })

        short = w.select_one("div.upgradeBlocked button.exchange")
        h2 = w.select_one("div.build_desc h2")
        out.append({
            "gid": gid, "name": _clean_text(h2),
            "cost": [cost.get(k, 0) for k in (1, 2, 3, 4)], "secs": secs,
            "buildable": url is not None, "url": url,
            "resource_short": short is not None,
            "exceeds_storage": short is not None and "disabled" in short.get("class", []),
            "conditions": conds,
        })
    return out


# ---------------- 決策 ----------------
def plan(st: State):
    """回傳 (動作, 參數...)。動作: build / wait_res / wait_queue / need_storage / done"""
    if len(st.queue) >= QUEUE_SLOTS:
        return ("wait_queue", min(st.queue) + 5)

    # 一般村莊資源田上限 10 級（首都無上限，見 MAX_NON_CAPITAL_FIELD_LEVEL 的說明）。
    eff_target = TARGET_LEVEL if IS_CAPITAL else min(TARGET_LEVEL, MAX_NON_CAPITAL_FIELD_LEVEL)
    # 村莊中心建築（gid 在 BUILDING_GIDS 裡）由呼叫端先用它們自己的
    # target_building_level 篩過等級，這裡不再套用資源田的 TARGET_LEVEL，
    # 只需要成本非空、沒有正在施工即可。
    cands = [f for f in st.fields if f.cost and not f.building
             and (f.gid in BUILDING_GIDS or f.level < eff_target)]
    if not cands:
        return ("done",)

    # 糧食淨產出太低時優先升農田
    pool = [f for f in cands if f.gid == 4] if st.free_crop < 5 else cands
    pool = pool or cands
    f = min(pool, key=_roi_key)     # ROI（花費÷每小時新增產量）最好的先；建築沒有產量表，退回花費排序

    if any(c > m for c, m in zip(f.cost, st.cap)):
        return ("need_storage", f)                          # 成本超過倉庫容量，要先升倉庫/糧倉

    short = [max(0, c - s) for c, s in zip(f.cost, st.stock)]
    if any(short):
        secs = max(sh / max(p, 1) * 3600 for sh, p in zip(short, st.prod))
        return ("wait_res", int(secs) + 30, f)
    return ("build", f)


# ---------------- 建城順序 ----------------


def fetch_build_options(get, aid: int) -> list:
    """抓空地 aid 的三個分頁並合併成一份完整可蓋清單（每筆多一個 "category" 欄位）。
    只抓預設分頁會漏掉軍事與資源兩類（英雄宅、研究院、盔甲廠、鋸木廠…），所以一律三頁都抓。"""
    out, seen = [], set()
    for cat, label in BUILD_CATEGORIES.items():
        for o in parse_build_options(get(f"build.php?id={aid}&category={cat}")):
            if o["gid"] in seen:
                continue
            seen.add(o["gid"])
            o["category"] = label
            out.append(o)
    return out


def parse_build_order(text: str) -> list:
    """把 'res:2,15:3,10:3,17:1' 轉成 [('res', 2), (15, 3), (10, 3), (17, 1)]。
      res:N   所有資源田都升到 N 級
      1~4:N   只有木/磚/鐵/糧其中一種的所有田升到 N 級
      其他數字:N  該 gid 的建築升到 N 級（沒有就蓋一棟）。gid 見 README：
              15 村莊大樓、10 倉庫、11 糧倉、17 市場、18 大使館、25 行宮、22 研究院 ...
    分隔符號可以是逗號、空白、換行。格式不對會丟 ValueError（呼叫端要接住、不要亂猜）。"""
    goals = []
    for tok in re.split(r"[,\s，;；]+", (text or "").strip()):
        if not tok:
            continue
        m = re.fullmatch(r"(res|資源田|\d+)\s*[:：]\s*(\d+)", tok, re.I)
        if not m:
            raise ValueError(f"看不懂 {tok!r}，格式應該像 res:2 或 15:3")
        k = m.group(1)
        goals.append((int(k) if k.isdigit() else "res", int(m.group(2))))
    return goals


def plan_with_order(st: State, order: list, get, touched=()):
    """依建城順序決定下一步。跟 plan() 回傳同樣的動作（但不會回傳 need_storage：
    成本超過容量時會自動改成先升倉庫/糧倉，補不了才回 blocked），另外多兩種：
      ("blocked", 說明)   計畫卡住了（例如被「不能已經有某棟」擋住），需要人看一下
      ("no_slot", gid)    要蓋新建築但村莊沒有空地了
    規則：由上到下，第一個「還沒達成」的目標就是現在要做的；它還在等資源/施工，
    後面的目標就不動（嚴格照順序）。要蓋的建築缺前置條件時，自動改成先補條件。
    get(path) -> html 由呼叫端提供（requests 或 Playwright），需要時才會呼叫：
    只有順序裡有「資源田以外」的目標才會多抓 dorf2 / build.php。"""
    touched = set(touched)
    if len(st.queue) >= QUEUE_SLOTS:
        return ("wait_queue", min(st.queue) + 5)
    cache = {}

    def q_wait():
        return ("wait_queue", (min(st.queue) + 5) if st.queue else 600)

    def slots():
        if "slots" not in cache:
            cache["slots"] = parse_dorf2_slots(get("dorf2.php"))
        return cache["slots"]

    def options():
        """抓一次空地的「建造新的建築物」頁面（每個空地看到的清單一樣）。"""
        if "opts" not in cache:
            lo, hi = FREE_SLOT_RANGE
            empty = sorted(s.aid for s in slots()
                           if s.gid == 0 and lo <= s.aid <= hi and s.aid not in touched)
            cache["empty"] = empty[0] if empty else None
            cache["opts"] = fetch_build_options(get, empty[0]) if empty else []
        return cache["opts"], cache["empty"]

    fixing = set()      # 正在補的儲存建築 gid，防止「補倉庫的成本又超過容量」無限遞迴

    def storage_fix(f):
        """成本超過容量：木/磚/鐵超過 → 先處理倉庫(gid 10)；只有穀物超過 → 先處理糧倉(gid 11)。
        做法是把該儲存建築升一級（沒有就蓋一棟），下一輪容量變大再重新評估。"""
        over_res = any(c > m for c, m in zip(f.cost[:3], st.cap[:3]))
        gid, name = (10, "倉庫") if over_res else (11, "糧倉")
        if gid in fixing:
            return ("blocked", f"{name}自己的升級成本就超過容量，無法自動補救")
        lvl = max((s.level for s in slots() if s.gid == gid), default=0)
        if lvl >= 20:
            return ("blocked", f"成本超過{name}容量，但{name}已滿級")
        fixing.add(gid)
        try:
            r = resolve(gid, lvl + 1)
        finally:
            fixing.discard(gid)
        return r if r is not None else ("blocked", f"成本超過{name}容量，但{name}已達目標等級（資料不一致）")

    def decide(f):
        if any(c > m for c, m in zip(f.cost, st.cap)):
            return storage_fix(f)
        short = [max(0, c - s) for c, s in zip(f.cost, st.stock)]
        if any(short):
            secs = max(sh / max(p, 1) * 3600 for sh, p in zip(short, st.prod))
            return ("wait_res", int(secs) + 30, f)
        return ("build", f)

    def fields_action(gids, level, need_all):
        # 資源田（gid 1~4）套用一般村莊 10 級上限；村莊中心建築（gid 不在 1~4）不受此限制。
        if gids == (1, 2, 3, 4) and not IS_CAPITAL:
            level = min(level, MAX_NON_CAPITAL_FIELD_LEVEL)
        fs = [f for f in st.fields if f.gid in gids]
        if not need_all and any(f.level >= level for f in fs):
            return None                       # 前置條件只要「有一塊」達標就算
        todo = [f for f in fs if f.level < level]
        if not todo:
            return None
        avail = [f for f in todo if f.cost and not f.building and f.aid not in touched]
        if not avail:
            if any(f.building or f.aid in touched for f in todo):
                return q_wait()
            return ("blocked", "資源田的升級成本讀不到（頁面 title 被前端 JS 清空？）")
        pool = [f for f in avail if f.gid == 4] if st.free_crop < 5 else avail
        pool = pool or avail
        if need_all:
            f = min(pool, key=_roi_key)   # res:N 這種「全部升到位」的目標：ROI 最好的先
        else:
            f = min(pool, key=lambda x: (-x.level, sum(x.cost), x.secs))   # 補條件：挑最接近的
        return decide(f)

    def resolve(gid, level, depth=0, need_all=False):
        """回傳 None = 這個目標已達成；否則回傳要做的動作。"""
        if depth > 3:
            return ("blocked", f"前置條件套了太多層（卡在 gid {gid}）")
        if gid in (1, 2, 3, 4):
            return fields_action((gid,), level, need_all)

        mine = [s for s in slots() if s.gid == gid]
        if mine:                                              # 已經有：升級
            best = max(mine, key=lambda s: s.level)
            if best.level >= level:
                return None
            if best.building or best.aid in touched:
                return q_wait()
            cost, secs = parse_building_cost(get(f"build.php?id={best.aid}"))
            if not cost:
                return q_wait() if st.queue else (
                    "blocked", f"{BUILDING_GIDS.get(gid, gid)} (aid={best.aid}) 讀不到升級成本（已達最高等級？）")
            return decide(Field(aid=best.aid, gid=gid, level=best.level, cost=cost, secs=secs, building=False))

        if any(s.aid in touched and s.gid == 0 for s in slots()):
            return q_wait()        # 本輪剛送出一個新建築、dorf2 還沒反映（乾跑模式就是這樣）：不要重複蓋
        opts, empty = options()                               # 還沒有：蓋新的
        if empty is None:
            return ("no_slot", gid)
        entry = next((o for o in opts if o["gid"] == gid), None)
        if entry is None:
            return ("blocked", f"gid {gid} 不在可蓋清單裡（種族不能蓋、已達數量上限，或空地頁面讀取失敗）")
        f = Field(aid=empty, gid=gid, level=0, cost=entry["cost"], secs=entry["secs"],
                  building=False, url=entry["url"] or "")
        if entry["buildable"]:
            return decide(f)
        unmet = [c for c in entry["conditions"] if not c["met"]]
        for c in unmet:
            if c["forbidden"]:
                return ("blocked", f"{entry['name']} 被 {c['name']} 擋住（村莊裡不能已經有它）")
        for c in unmet:                                       # 先補前置條件
            r = resolve(c["gid"], c["level"], depth + 1)
            if r is not None:
                return r
        if unmet:
            return q_wait() if st.queue else (
                "blocked", f"{entry['name']}：頁面說條件沒達成，但村莊資料看起來已達成")
        r = decide(f)                                         # 條件沒問題：可能只是資源不足
        if r[0] == "build":
            return ("blocked", f"{entry['name']} 沒有綠色按鈕、也沒有未達成的條件（原因不明）")
        return r

    for key, level in order:
        r = fields_action((1, 2, 3, 4), level, True) if key == "res" else resolve(key, level, need_all=True)
        if r is not None:
            return r
    return ("done",)


# ---------------- 通知 ----------------
def notify(msg: str):
    """目前只印 log（Actions 的執行紀錄）。來襲寄信尚未實作，見 README。"""
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


# ---------------- 執行 ----------------
def run():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE_DIR, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE}/dorf1.php")
        input("第一次請在瀏覽器手動登入，看到資源田畫面後按 Enter ... ")

        last_attacks = 0
        while True:
            if QUIET_HOURS[0] <= datetime.now().hour < QUIET_HOURS[1]:   # 注意：這是本機時間
                time.sleep(random.uniform(900, 1500))
                continue

            page.goto(f"{BASE}/dorf1.php")
            page.wait_for_load_state("networkidle")
            if page.locator("#stockBar").count() == 0:                    # 被登出/驗證碼/改版
                notify("找不到 #stockBar：可能被登出或出現驗證碼，已停止")
                return

            html = page.content()
            st = parse_dorf1(html)
            if not any(f.cost for f in st.fields):                        # title 被前端 JS 拿掉時的備案
                html = ctx.request.get(f"{BASE}/dorf1.php").text()
                st = parse_dorf1(html)

            if st.attacks and st.attacks != last_attacks:
                notify(f"偵測到來襲 {st.attacks} 波！請手動處理")
            last_attacks = st.attacks

            action = plan(st)
            sleep_s = 600
            if action[0] == "build":
                f = action[1]
                notify(f"{'[DRY] ' if DRY_RUN else ''}升級 slot {f.aid} (gid {f.gid}) L{f.level}->L{f.level + 1} 成本 {f.cost}")
                if not DRY_RUN:
                    page.goto(f"{BASE}/build.php?id={f.aid}")
                    page.locator(UPGRADE_BUTTON).first.click()
                    page.wait_for_load_state("networkidle")
                sleep_s = random.uniform(20, 60)
            elif action[0] in ("wait_res", "wait_queue"):
                sleep_s = action[1]
            elif action[0] == "need_storage":
                notify(f"slot {action[1].aid} 的成本超過倉庫容量 {st.cap}，請先升倉庫/糧倉")
                return
            elif action[0] == "done":
                notify("資源田都到目標等級了")
                return

            # 新手保護期間不需要密集查來襲；結束後改成最多 10 分鐘一輪
            cap = 1800 if (st.protection_s or 0) > 0 else 600
            sleep_s = min(max(sleep_s, 60), cap) * random.uniform(0.9, 1.3)
            print(f"下一輪約 {int(sleep_s)} 秒後")
            time.sleep(sleep_s)


if __name__ == "__main__":
    run()
