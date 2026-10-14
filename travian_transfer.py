"""travian_transfer.py v1.0  英雄道具庫 → 村莊 資源轉移（決策為純函式，網路由呼叫端注入）

已驗證（見筆記 §3.6）：graphql 回應格式、use-item 的 Payload、typeId 145~148。
未驗證（✗）：use-item 的 HTTP 方法（PUT/204 與 POST/200 都出現過）、graphql 請求的 body 外層格式。
→ 本模組不替你決定方法：send 由呼叫端提供；轉完一定用 read_state 驗證，沒到位只回報、不重試。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

RES = ("lumber", "clay", "iron", "crop")
TYPE_ID = {"lumber": 145, "clay": 146, "iron": 147, "crop": 148}   # ✓ graphql 回應
USE_ITEM_PATH = "/api/v1/hero/v2/inventory/use-item"
GRAPHQL_PATH = "/api/v1/graphql"

# ✓ 使用者提供的實際 query（原樣）
STATE_QUERY = (
    "{lumber:item(typeId:145 rarity:none){...itemFields}clay:item(typeId:146 rarity:none){...itemFields}"
    "iron:item(typeId:147 rarity:none){...itemFields}crop:item(typeId:148 rarity:none){...itemFields}"
    "ownPlayer{hero{inventory{...heroInventoryItemFields}}village{id name resources{lumberStock clayStock "
    "ironStock cropStock maxStorageCapacity maxCropStorageCapacity}}}}"
    "fragment itemFields on Item{typeId name isConsumable isUsableIfDead attributes{description descriptionDetails}"
    "slot quality rarity possibleAmountsToSell}"
    "fragment heroInventoryItemFields on HeroInventoryItem{id amount placeId name typeId isConsumable "
    "isUsableIfDead attributes{description descriptionDetails}slot quality rarity possibleAmountsToSell}"
)


@dataclass(frozen=True)
class TransferConfig:
    mode: str = "off"            # off | incoming_only | always（看不懂＝off）
    min_inventory: int = 20000   # 每一種「需要轉」的資源，道具庫都要 >= 此值
    max_gap: int = 1000          # 各資源缺口加總 > 此值 → 不轉，改做付得起的項目
    eta_min: int = 45            # 最快來襲 ETA <= 此分鐘才處理


def _int(v, default):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def parse_config(d: dict) -> TransferConfig:
    mode = str(d.get("hero_transfer_mode", "") or "").strip().lower()
    if mode not in ("incoming_only", "always"):
        mode = "off"
    return TransferConfig(
        mode=mode,
        min_inventory=_int(d.get("hero_transfer_min"), 20000),
        max_gap=_int(d.get("hero_transfer_max_gap"), 1000),
        eta_min=_int(d.get("hero_transfer_eta_min"), 45),
    )


@dataclass
class State:
    village_id: int
    stock: dict                  # {"lumber":.., ...}
    capacity: dict               # {"lumber":4000,..,"crop":3100}
    inventory: dict              # {"lumber": {"id":879843,"amount":38279}, ...} 以 typeId 辨識，id 執行時讀


def parse_state(resp: dict) -> State:
    """吃 graphql 完整回應（含外層 data）或內層 data。缺欄位 → ValueError。"""
    data = resp.get("data", resp)
    try:
        village = data["ownPlayer"]["village"]
        res = village["resources"]
        inv_list = data["ownPlayer"]["hero"]["inventory"]
        stock = {"lumber": res["lumberStock"], "clay": res["clayStock"],
                 "iron": res["ironStock"], "crop": res["cropStock"]}
        cap = {"lumber": res["maxStorageCapacity"], "clay": res["maxStorageCapacity"],
               "iron": res["maxStorageCapacity"], "crop": res["maxCropStorageCapacity"]}
    except (KeyError, TypeError) as e:
        raise ValueError(f"graphql 回應缺欄位: {e}")
    by_type = {it.get("typeId"): it for it in inv_list if isinstance(it, dict)}
    inventory = {}
    for r, tid in TYPE_ID.items():
        it = by_type.get(tid)
        inventory[r] = {"id": it["id"], "amount": it["amount"]} if it else None
    return State(int(village["id"]), stock, cap, inventory)


_TARGET_RE = re.compile(
    r"targetResourceAmount:\s*\{\s*lumber:\s*(\d+),\s*clay:\s*(\d+),\s*iron:\s*(\d+),\s*crop:\s*(\d+)")


def parse_target_amounts(html: str):
    """建築頁 fillUp 圖示的 onclick：目標『總量』（不是缺口）。找不到 → None。"""
    m = _TARGET_RE.search(html or "")
    return dict(zip(RES, map(int, m.groups()))) if m else None


@dataclass
class Plan:
    decision: str                # 見 decide_transfer
    reason: str = ""
    gaps: dict = field(default_factory=dict)
    items: list = field(default_factory=list)   # [{"action","itemId","amount","villageId"}]


def decide_transfer(cfg, incoming_eta_s, queue_busy, target, state) -> Plan:
    """decision：
    mode_off / no_incoming / queue_busy / no_data -> 不動作
    affordable   -> 村莊付得起，直接開工，不動道具庫
    gap_too_big / inventory_low / over_capacity -> 不轉；呼叫端改選『現有資源付得起』的項目
    transfer     -> 只轉缺口（items），轉完立刻開工
    """
    if cfg.mode == "off":
        return Plan("mode_off")
    if cfg.mode == "incoming_only":
        if incoming_eta_s is None or incoming_eta_s > cfg.eta_min * 60:
            return Plan("no_incoming", "無來襲或最快 ETA 超過門檻")
    if queue_busy:
        return Plan("queue_busy", "施工佇列已占用，不轉（轉進來會留在村莊被搶）")
    if not target or state is None:
        return Plan("no_data", "讀不到目標成本或村莊／道具庫狀態")
    gaps = {r: max(0, target[r] - state.stock[r]) for r in RES}
    if sum(gaps.values()) == 0:
        return Plan("affordable", gaps=gaps)
    total = sum(gaps.values())
    if total > cfg.max_gap:
        return Plan("gap_too_big", f"缺口加總 {total} > {cfg.max_gap}", gaps)
    for r, g in gaps.items():
        if g and target[r] > state.capacity[r]:
            return Plan("over_capacity", f"{r} 目標 {target[r]} 超過倉容 {state.capacity[r]}", gaps)
    items = []
    for r, g in gaps.items():
        if not g:
            continue
        it = state.inventory.get(r)
        if not it:
            return Plan("inventory_low", f"道具庫沒有 {r}", gaps)
        if it["amount"] < cfg.min_inventory or it["amount"] < g:
            return Plan("inventory_low", f"{r} 庫存 {it['amount']} < 門檻 {cfg.min_inventory}", gaps)
        items.append({"action": "inventory", "itemId": it["id"], "amount": g, "villageId": state.village_id})
    return Plan("transfer", gaps=gaps, items=items)


@dataclass
class Result:
    ok: bool
    detail: str
    sent: list = field(default_factory=list)


def execute_transfer(plan: Plan, target: dict, send, read_state) -> Result:
    """send(payload)->None（失敗請 raise）；read_state()->State。
    每個缺的資源送一筆；中途失敗就停（不重試、不換方法）；最後讀村莊驗證。"""
    if plan.decision != "transfer":
        return Result(False, f"plan 不是 transfer: {plan.decision}")
    sent = []
    for payload in plan.items:
        try:
            send(payload)
        except Exception as e:  # noqa: BLE001
            return Result(False, f"送出失敗 {payload['itemId']}: {e}", sent)
        sent.append(payload)
    st = read_state()
    short = {r: (st.stock[r], target[r]) for r in RES if plan.gaps.get(r) and st.stock[r] < target[r]}
    if short:
        return Result(False, f"轉移後村莊仍不足 {short}（可能方法錯誤；不重試）", sent)
    return Result(True, "已轉移並驗證", sent)
