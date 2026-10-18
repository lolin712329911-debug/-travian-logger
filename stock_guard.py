"""stock_guard.py v0.2（新、未接線、未部署）庫存防搶＋防溢出：預估下一輪結束時各資源的「溢出」與「超過山洞隱藏量的暴露」，挑加成設定讓兩者合計最小。

v0.2（相對 v0.1）：
  ① 新增溢出項：超過倉容的產量是 100% 浪費，v0.1 把它當成「不算暴露」，所以快滿倉時不會切走加成（已實測）。
     評分＝溢出 ＋ lambda_exposure × 暴露（預設 0.5，△ 未校準）。
  ② 不管施工佇列忙不忙都可以用（由呼叫端決定何時呼叫）；佇列忙時 gaps 可傳 None（只看溢出與暴露）或下一目標缺口。
  ③ slack 自動夾到 ≤ switch_ratio（和 hero_focus.decide_focus 的 1.3 對齊），避免守衛切走的加成又被 decide_focus 切回來。
  ④ min_gain 改以「評分」計：預設 150（＝無溢出時暴露少 300，和 v0.1 的門檻等價）。
  horizon 預設 1.25 小時（實測輪距中位 48 分、最長 73 分）。

原則（筆記 §5、§6.3）：來襲只拿倉庫／糧倉裡超過山洞隱藏量的部分；道具庫拿不走。
排程每 40 分鐘一輪，來襲 ETA 最短只有 257 秒，所以不能靠「看到來襲才處理」，要看「下一輪結束時的預估庫存」。
純函式、不連網路、不改既有檔案；參數順序與 hero_focus 的 production／types／current 相同。
穀產量請給 var resources 的 l4（含英雄加成；l5 不含，見筆記 §5 H1 ✓）。
"""
from typing import Optional
from hero_focus import hero_bonus, RES_NAME

DEFAULT_CAPACITY = {1: 4000, 2: 4000, 3: 4000, 4: 3100}


def exposure(stock: dict, production: dict, hours: float, hidden: float = 2000,
             capacity: Optional[dict] = None) -> dict:
    """{1..4: 預估 hours 小時後超過隱藏量的數量}。超過倉容的部分是溢出，不算暴露（溢出另用 overflow 算）。"""
    cap = capacity or DEFAULT_CAPACITY
    out = {}
    for r in (1, 2, 3, 4):
        proj = max(0.0, min(cap[r], stock[r] + production[r] * hours))
        out[r] = max(0.0, proj - hidden)
    return out


def overflow(stock: dict, production: dict, hours: float, capacity: Optional[dict] = None) -> dict:
    """{1..4: 預估 hours 小時內超過倉容而浪費掉的數量}。"""
    cap = capacity or DEFAULT_CAPACITY
    return {r: max(0.0, stock[r] + production[r] * hours - cap[r]) for r in (1, 2, 3, 4)}


def guard_focus(stock: dict, production: dict, current: Optional[int], types: Optional[list],
                hidden: float = 2000, capacity: Optional[dict] = None, horizon_h: float = 1.25,
                gaps: Optional[dict] = None, slack: float = 1.3, min_gain: float = 150,
                crop_floor: float = 0.0, lambda_exposure: float = 0.5, switch_ratio: float = 1.3):
    """回傳 ("keep", None, 原因) 或 ("switch", 類型, 原因)。
    評分(t)＝溢出(t) ＋ lambda_exposure × 暴露(t)，越小越好。
    候選須滿足：穀產量 > crop_floor；有缺口時補齊時間 ≤ 最快候選 × min(slack, switch_ratio)。
    要比目前少 min_gain（評分）以上才切。"""
    if current is None or not types:
        return ("keep", None, "讀不到目前加成，不動")
    slack = min(slack, switch_ratio)

    def after(t, r):
        return production[r] - hero_bonus(current, types, r) + hero_bonus(t, types, r)

    def prod_after(t):
        return {r: after(t, r) for r in (1, 2, 3, 4)}

    def expo(t):
        return sum(exposure(stock, prod_after(t), horizon_h, hidden, capacity).values())

    def waste(t):
        return sum(overflow(stock, prod_after(t), horizon_h, capacity).values())

    def score(t):
        return waste(t) + lambda_exposure * expo(t)

    def fill(t):
        worst = 0.0
        for r, g in (gaps or {}).items():
            p = after(t, r)
            if p <= 0:
                return float("inf")
            worst = max(worst, g / p)
        return worst

    now, w_now, e_now = score(current), waste(current), expo(current)
    if now <= 0:
        return ("keep", None, f"{horizon_h:.2f} 小時內不會溢出，也不會超過隱藏量 {hidden:.0f}")
    ok = [t for t in range(5) if after(t, 4) > crop_floor]
    if not ok:
        return ("keep", None, "所有選項穀產量都 ≤ 下限，不動")
    best_fill = min(fill(t) for t in ok)
    allowed = [t for t in ok if fill(t) <= best_fill * slack]
    best = min(allowed, key=lambda t: (score(t), t != current))
    sb = score(best)
    if best == current or sb > now - min_gain:
        return ("keep", None, f"目前評分 {now:.0f}（溢出 {w_now:.0f}、暴露 {e_now:.0f}），沒有能少 {min_gain:.0f} 以上的選項")
    tag = "溢出" if w_now > 0 else "暴露"
    return ("switch", best, f"改 {RES_NAME[best]}（{tag}）：評分 {now:.0f} → {sb:.0f}"
                            f"（溢出 {w_now:.0f}→{waste(best):.0f}、暴露 {e_now:.0f}→{expo(best):.0f}）"
                            + (f"，補齊缺口約 {fill(best):.1f}h" if gaps else "，無缺口：只是停放／避溢出"))
