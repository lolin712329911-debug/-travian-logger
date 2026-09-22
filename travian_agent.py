"""
Travian (ts11.x1.international) 資源田升級排程 + 來襲通知
- parse_dorf1(): 解析 dorf1.php 原始碼（依你貼的頁面結構寫）
- plan():        純規則決策（不用 LLM）
- run():         Playwright 持久登入 + 迴圈；DRY_RUN=True 時只印出決定，不點擊

安裝: pip install playwright beautifulsoup4 requests && playwright install chromium
環境變數(選用，Telegram 通知): TG_TOKEN, TG_CHAT_ID
"""
import os
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup

# ---------------- 設定 ----------------
BASE = "https://ts11.x1.international.travian.com"
DRY_RUN = True            # 確認決策正確後才改 False
TARGET_LEVEL = 2          # 資源田先升到這個等級
QUEUE_SLOTS = 2           # Plus 有效時 2；Plus 到期後請改 1（未驗證，請以遊戲內為準）
QUIET_HOURS = (2, 7)      # 這段伺服器時間不運作
UPGRADE_BUTTON = "button.textButtonV1.green.build"   # ← 未驗證，需用 build.php 頁面確認
PROFILE_DIR = "./travian_profile"

BIDI = re.compile(r"[\u202a-\u202e\u2066-\u2069]")   # 頁面數字外面包的方向控制字元


# ---------------- 資料結構 ----------------
@dataclass
class Field:
    aid: int          # 田位編號 (build.php?id=aid)
    gid: int          # 1 木 2 磚 3 鐵 4 糧
    level: int
    cost: list        # [木, 磚, 鐵, 糧]，升到下一級
    secs: int         # 升級所需秒數
    building: bool    # 是否正在施工（class 名稱未驗證）


@dataclass
class State:
    stock: list
    cap: list
    prod: list
    free_crop: int
    fields: list = field(default_factory=list)
    queue: list = field(default_factory=list)   # 剩餘秒數列表（選擇器未驗證）
    attacks: int = 0
    protection_s: int = None
    plus_s: int = None


# ---------------- 解析 ----------------
def _js_dict(block: str, key: str) -> dict:
    m = re.search(key + r":\s*\{([^}]*)\}", block)
    return {k: int(v) for k, v in re.findall(r'"(l\d)":\s*(-?\d+)', m.group(1))} if m else {}


def _hms(s: str) -> int:
    h, m, sec = (int(x) for x in s.split(":"))
    return h * 3600 + m * 60 + sec


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

    # 4) 來襲：注意 .incomingTroops 圖示在沒有來襲時也存在，不能用「元素存在」判斷
    st.attacks = sum(int(x) for x in re.findall(r'incomingAttacksAmount":(\d+)', html))

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


# ---------------- 決策 ----------------
def plan(st: State):
    """回傳 (動作, 參數...)。動作: build / wait_res / wait_queue / need_storage / done"""
    if len(st.queue) >= QUEUE_SLOTS:
        return ("wait_queue", min(st.queue) + 5)

    cands = [f for f in st.fields if f.level < TARGET_LEVEL and f.cost and not f.building]
    if not cands:
        return ("done",)

    # 糧食淨產出太低時優先升農田
    pool = [f for f in cands if f.gid == 4] if st.free_crop < 5 else cands
    pool = pool or cands
    f = min(pool, key=lambda x: (sum(x.cost), x.secs))     # 最便宜、最快的先

    if any(c > m for c, m in zip(f.cost, st.cap)):
        return ("need_storage", f)                          # 成本超過倉庫容量，要先升倉庫/糧倉

    short = [max(0, c - s) for c, s in zip(f.cost, st.stock)]
    if any(short):
        secs = max(sh / max(p, 1) * 3600 for sh, p in zip(short, st.prod))
        return ("wait_res", int(secs) + 30, f)
    return ("build", f)


# ---------------- 通知 ----------------
def notify(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")
    token, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT_ID")
    if token and chat:
        import requests
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": f"[Travian] {msg}"}, timeout=10)


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
