"""躲兵「只觀察」v0.1：有來襲時，只讀、只記錄，絕不派兵。

做什麼（每輪建城前跑一次；沒有來襲就只印一行、不多打任何請求）：
  1. 用已經載入的 dorf1（d1）數來襲：viewData 的 incomingAttacksAmount，和 travian_pages 的 attacks 交叉對照；
  2. 有來襲才開集結點概況（唯讀 GET），原始 HTML 存進 debug_html/（workflow 已上傳，保留 3 天）；
  3. 用 hide_troops 的 plan 模式算「如果要躲，會怎麼派」，並唯讀驗證前 2 個候選綠洲（tile-details，
     順便實測 page.request.post 這條路在 Actions 上通不通）；
  4. 寫一列到 Actions：動作＝「躲兵觀察」、模式＝PLAN，說明欄含來襲提前量、在家兵力、決策、候選、各 in* 表的 class 與標題。
任何例外都只印 log，不往外拋，不影響後面的建城。
開關：Sheet「Config」分頁的 hide_mode（off／observe；預設 observe，空白或看不懂一律當 off），由 travian_ci_run 傳進 mode。
不會做的事：不開派遣頁、不填表、不按任何確認。
"""
import os
from datetime import datetime, timezone

import hide_troops as HT
import oasis_check


def _utc():
    return datetime.now(timezone.utc).strftime("%F %T")


def _default_log(row):
    from sheets_writer import log_action
    log_action(row)


def _probe_tile(page, base, pos):
    """唯讀：tile-details。回傳一小段文字（含 HTTP 狀態），失敗也只是文字。"""
    tag = f"{pos[0]}|{pos[1]}"
    try:
        r = page.request.post(f"{base}/api/v1/map/tile-details", data={"x": pos[0], "y": pos[1]})
        if not r.ok:
            return f"{tag}=HTTP{getattr(r, 'status', '?')}"
        info = oasis_check.parse_tile_details(r.json()["html"])
        return f"{tag}=" + ("安全" if oasis_check.is_safe(info, pos) else "不安全")
    except Exception as e:                                      # noqa: BLE001
        return f"{tag}=例外{type(e).__name__}"


def observe(page, base, d1, *, mode="observe", log=None, save_dir="debug_html", probe=True, now_fn=_utc):
    """回傳 run_once 的結果 dict；沒有來襲或失敗回 None。永遠不拋例外。"""
    if str(mode or "").strip().lower() != "observe":
        print(f"[躲兵觀察] Config hide_mode={mode!r}，不是 observe，略過")
        return None
    try:
        n_sym = HT.incoming_symbols(d1)["amount"]
        n_pages = None
        try:
            import travian_pages as P
            n_pages = P.parse_dorf1(d1).attacks
        except Exception:                                       # noqa: BLE001
            pass
        if max(n_sym, n_pages or 0) == 0:
            print("[躲兵觀察] 沒有來襲")
            return None

        saved = {}

        def on_overview(html):
            os.makedirs(save_dir, exist_ok=True)
            name = os.path.join(save_dir, f"overview_{now_fn().replace(' ', '_').replace(':', '')}.html")
            with open(name, "w", encoding="utf-8") as f:
                f.write(html)
            saved["path"] = name

        res = HT.run_once(page, base, "plan", on_overview=on_overview)

        now_ts, arr = res.get("now_ts"), res.get("arrivals", [])
        leads = ",".join(f"{(a - now_ts) / 60:.1f}" for a in arr) if now_ts else ""
        top = res.get("top", [])
        probes = [_probe_tile(page, base, t["pos"]) for t in top[:2]] if probe else []
        desc = " ｜ ".join(x for x in [
            f"dorf1來襲={n_sym}/{n_pages}",
            f"概況敵方={len(arr)}波 提前(分)={leads}",
            f"在家={res.get('units')}",
            f"決策={res.get('action')}:{res.get('reason')}",
            "首選=" + ";".join(f"({t['pos'][0]}|{t['pos'][1]}) 單程{t['one_way']} 回{t['back']}"
                              f"{'' if t['ok'] else ' 缺波'}" for t in top) if top else "",
            "即時驗證=" + ",".join(probes) if probes else "",
            "in表=" + ";".join(res.get("in_moves", [])),
            f"未知class={res.get('unknown_in')}" if res.get("unknown_in") else "",
            f"now={now_ts} arr={arr}",
            f"存檔={saved.get('path', '無')}",
            f"錯誤={res['error']}" if res.get("error") else "",
        ] if x)
        (log or _default_log)([now_fn(), "躲兵觀察", "", "", "", "", "PLAN", res.get("action", "error"), desc])
        print(f"[躲兵觀察] {res.get('action')}：{res.get('reason')}；提前(分)={leads}；{', '.join(probes)}")
        return res
    except Exception as e:                                      # noqa: BLE001
        print(f"[躲兵觀察] 失敗（不影響建城）: {e!r}")
        return None
