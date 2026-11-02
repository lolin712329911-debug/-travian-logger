# -*- coding: utf-8 -*-
"""parsers 測試共用工具（不是測試檔，discover 不會收）。
golden 更新：UPDATE_GOLDEN=1 python -m unittest discover -s tests -t .  會改寫 golden 檔；
更新後要在交接區塊說明原因（主檔 §6.5）。"""
import json
import os
import re
from pathlib import Path

from travian_bot.common import serialize

TESTS = Path(__file__).resolve().parents[1]
SAMPLES = TESTS / "samples"
GOLDEN = TESTS / "golden" / "parsers"
SAMPLE_IDS = ("S1a", "S1b")
_VIEWDATA_RE = re.compile(r"viewData\s*:\s*")


def load_sample(sid, kind="dorf1", date="20261031"):
    return (SAMPLES / f"{sid}_{kind}_{date}.html").read_text(encoding="utf-8")


def load_meta(sid, kind="dorf1", date="20261031"):
    return json.loads((SAMPLES / f"{sid}_{kind}_{date}.meta.json").read_text(encoding="utf-8"))


def mutate_view(html, fn):
    """取出頁內 viewData 的 dict，交給 fn(obj) 就地修改，再放回頁面（其餘頁面內容不動）。"""
    m = _VIEWDATA_RE.search(html)
    obj, end = json.JSONDecoder().raw_decode(html, m.end())
    fn(obj)
    return html[:m.end()] + json.dumps(obj, ensure_ascii=False) + html[end:]


def view_page(obj):
    """只含 viewData 的最小頁面（用來測欄位缺漏）。"""
    return "<html><script>var cfg = {viewData: " + json.dumps(obj, ensure_ascii=False) + "};</script></html>"


def check_golden(case, module, name, actual):
    """actual 需是純資料（list／dict／數字／字串），頂層會補上 schema_version。"""
    path = GOLDEN / module / f"{name}.expected.json"
    data = dict(actual)
    data["schema_version"] = 1
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize.dumps_stable(data), encoding="utf-8", newline="")
    case.assertTrue(path.exists(), f"golden 缺檔：{path}")
    case.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)
