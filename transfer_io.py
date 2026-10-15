"""transfer_io.py v1.1（失敗時帶出回應內容；成功時回傳狀態碼）

v1.0  travian_transfer 需要的網路函式（send／read_state），用 Playwright 的 context.request。

△ 全部未實測：認證靠同一個 context 的 Cookie（graphql 請求標頭只有 Cookie 認證，use-item 推測相同）。
用法（在 travian_ci_run.py 有 context 的地方）：
    from transfer_io import make_io
    send, read_state = make_io(context, base_url)   # base_url 例：https://ts11.x1.international.travian.com
    DRY 時不要呼叫 send（用 make_dry_send 只印 log）。
"""
import json

import travian_transfer as TR


def make_io(context, base_url: str, referer: str = ""):
    base = base_url.rstrip("/")
    headers = {"content-type": "application/json; charset=UTF-8", "accept": "*/*", "origin": base}
    if referer:
        headers["referer"] = referer

    def send(payload: dict, method: str = "POST") -> str:
        fn = {"PUT": context.request.put, "POST": context.request.post}[method]
        r = fn(base + TR.USE_ITEM_PATH, data=json.dumps(payload), headers=headers)
        if not r.ok:                       # PUT 預期 204，POST 預期 200
            try:
                body = r.text()[:300]
            except Exception as e:  # noqa: BLE001
                body = f"(讀不到回應內容: {e!r})"
            raise RuntimeError(f"{method} use-item HTTP {r.status} 回應={body!r}")
        return f"{method} {r.status}"      # 讓呼叫端記錄成功的狀態碼（可驗證 PUT 是 204）

    def read_state() -> "TR.State":
        r = context.request.post(base + TR.GRAPHQL_PATH, data=json.dumps(TR.graphql_body()), headers=headers)
        if not r.ok:
            raise RuntimeError(f"graphql HTTP {r.status}")
        return TR.parse_state(r.json())

    return send, read_state


def make_dry_send(log=print):
    def send(payload: dict, method: str = "POST") -> None:
        log(f"[DRY] 不送出 {method} use-item {payload}")
    return send
