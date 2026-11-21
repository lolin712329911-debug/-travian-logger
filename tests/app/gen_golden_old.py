# -*- coding: utf-8 -*-
"""A6a1：由舊 runner.py（v2.36）離線產生 golden（不是測試檔，discover 不會收）。
用法：python tests/app/gen_golden_old.py <舊 repo 目錄（含 runner.py、travian_const.py）>
只抽出舊的純函式（_fname／_flv／_mins／describe／_with_queue／cp_summary／build_state_rows）在受控命名空間執行；
輸入是這裡寫死的案例，輸出寫到 tests/golden/app/。舊函式只在離線當對照（§5.1、A-6）。"""
import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

old = Path(sys.argv[1])
sys.path.insert(0, str(old))
import travian_const as C  # noqa: E402

src = (old / "runner.py").read_text(encoding="utf-8")
tree = ast.parse(src)
want = {"_fname", "_flv", "_mins", "describe", "_with_queue", "cp_summary", "build_state_rows"}
funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
assert {f.name for f in funcs} == want
T = SimpleNamespace(QUEUE_SLOTS=1)
ns = {"gid_name": C.gid_name, "RES_NAMES": C.RES_NAMES, "TRIBE_NAMES": C.TRIBE_NAMES, "T": T}
exec(compile(ast.Module(body=funcs, type_ignores=[]), "runner_old", "exec"), ns)

Field = SimpleNamespace


def F(aid, gid, level, cost, secs=0):
    return Field(aid=aid, gid=gid, level=level, cost=list(cost), secs=secs, building=False)


def ST(stock, cap, queue_info=()):
    return SimpleNamespace(stock=list(stock), cap=list(cap), queue=list(queue_info), queue_info=list(queue_info))


out = {"source": "runner.py v2.36（舊）離線輸出", "describe": [], "mins": [], "fname_flv": [], "state_rows": [], "cp_summary": []}

# ---- describe
cases = [
    ("wait_res_field", "wait_res", dict(f=F(3, 1, 4, (500, 400, 300, 200)), secs=5400), ST((100, 500, 300, 50), (800, 800, 800, 800)), 1),
    ("wait_res_new_building", "wait_res", dict(f=F(25, 10, 0, (90, 50, 70, 20)), secs=30), ST((500, 500, 500, 500), (800, 800, 800, 800)), 1),
    ("wait_res_short_crop_only", "wait_res", dict(f=F(7, 4, 2, (10, 10, 10, 900)), secs=7260), ST((50, 50, 50, 10), (800, 800, 800, 800)), 1),
    ("wait_queue_full", "wait_queue", dict(secs=125), ST((0, 0, 0, 0), (800,) * 4, ("某建築 等級 2",)), 1),
    ("wait_queue_not_full", "wait_queue", dict(secs=3600), ST((0, 0, 0, 0), (800,) * 4), 2),
    ("need_storage", "need_storage", dict(f=F(9, 2, 7, (1000, 300, 100, 900)), ), ST((0, 0, 0, 0), (800, 800, 800, 800)), 1),
    ("blocked", "blocked", dict(text="前置建築缺主建築 5 級"), ST((0, 0, 0, 0), (800,) * 4), 1),
    ("done", "done", dict(), ST((0, 0, 0, 0), (800,) * 4), 1),
]
for name, kind, p, st, slots in cases:
    T.QUEUE_SLOTS = slots
    if kind == "wait_res":
        act = ("wait_res", p["secs"], p["f"])
    elif kind == "wait_queue":
        act = ("wait_queue", p["secs"])
    elif kind == "need_storage":
        act = ("need_storage", p["f"])
    elif kind == "blocked":
        act = ("blocked", p["text"])
    else:
        act = ("done",)
    label, nf, desc = ns["describe"](act, st)
    rec = {"case": name, "kind": kind, "slots": slots, "stock": st.stock, "cap": st.cap, "queue_len": len(st.queue),
           "label": label, "detail": desc, "ref_aid": nf.aid if nf else None}
    if "f" in p:
        f = p["f"]
        rec["field"] = {"aid": f.aid, "gid": f.gid, "level": f.level, "cost": f.cost}
    if "secs" in p:
        rec["secs"] = p["secs"]
    if "text" in p:
        rec["text"] = p["text"]
    out["describe"].append(rec)

# ---- mins / fname / flv
for s in (0, 1, 29, 30, 31, 59, 60, 89, 90, 119, 150, 3599, 3600, 3660, 5400, 7260, 86399):
    out["mins"].append({"secs": s, "text": ns["_mins"](s)})
for aid, gid, level in ((3, 1, 0), (3, 1, 4), (25, 10, 0), (25, 10, 3), (9, 4, 0), (30, 10, 9)):   # gid 11 不放：新表由「糧倉」改「穀倉」（v0.66，刻意）
    f = F(aid, gid, level, (1, 1, 1, 1))
    out["fname_flv"].append({"aid": aid, "gid": gid, "level": level, "fname": ns["_fname"](f), "flv": ns["_flv"](f)})

# ---- build_state_rows（舊 info 是 dict）
def cp(have, need, per_day, used, mx):
    return {"have": have, "need": need, "per_day": per_day, "used": used, "max": mx}


st_cap = ST((0, 0, 0, 0), (6300, 6300, 6300, 7800))
st_zero = ST((0, 0, 0, 0), (0, 0, 0, 0))
state_cases = [
    ("full", {"tribe_id": 3, "plus_active": True, "cp": cp(1536, 6000, 275, 2, 2)}, st_cap, 2),
    ("plus_false_cp_reached", {"tribe_id": 3, "plus_active": False, "cp": cp(6000, 6000, 275, 1, 2)}, st_cap, 1),
    ("per_day_zero", {"tribe_id": 7, "plus_active": True, "cp": cp(10, 6000, 0, 1, 1)}, st_cap, 1),
    ("unknown_tribe_no_cp", {"tribe_id": 99, "plus_active": None, "cp": None}, st_cap, 1),
    ("info_none_caps_zero", None, st_zero, 1),
    ("info_none_no_snapshot", None, None, 3),
]
for name, info, st, qs in state_cases:
    rows = ns["build_state_rows"](info, st, qs)
    out["state_rows"].append({"case": name, "info": info, "cap": st.cap if st else None, "queue_slots": qs,
                              "rows": [[k, v, n] for k, v, n in rows]})

# ---- cp_summary
for name, c in (("gap", cp(1536, 6000, 275, 2, 2)), ("reached", cp(6000, 6000, 275, 1, 2)), ("per_day_zero", cp(10, 6000, 0, 1, 1)),
                ("ceil", cp(5990, 6000, 275, 1, 2))):
    out["cp_summary"].append({"case": name, "cp": c, "text": ns["cp_summary"](c)})

# ---- Sheet1：舊 travian_parser＋scrape_and_log.build_row 對同一份樣本的輸出（只收新版也輸出的欄位）
import travian_parser as TP  # noqa: E402
import datetime as _dt  # noqa: E402
sys.modules.setdefault("sheets_writer", SimpleNamespace(append_row=None, HEADER_ROW=["c"] * 24))
import scrape_and_log as SL  # noqa: E402

samples = Path(__file__).resolve().parents[1] / "samples"
out["sheet1_old"] = []
for sid, date in (("S1a", "20261031"), ("S1b", "20261031")):
    html = (samples / f"{sid}_dorf1_{date}.html").read_text(encoding="utf-8")
    ov = TP.parse_village_page(html)
    r = ov.resources
    out["sheet1_old"].append({
        "sample": sid, "server_time_text": ov.server_time,
        "stock": [r[k].amount for k in ("l1", "l2", "l3", "l4")],
        "prod": [r[k].production for k in ("l1", "l2", "l3", "l4")],
        "free_crop": ov.free_crop,
        "hero_health_pct": ov.hero.health_percent, "hero_exp_pct": ov.hero.experience_percent,
        "hero_adventures": ov.hero.adventures_available,
        "population": ov.population, "loyalty": ov.loyalty_percent, "gold": ov.gold, "silver": ov.silver})

path = Path(__file__).resolve().parents[1] / "golden" / "app" / "formatting" / "old_runner.expected.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
print("wrote", path, len(out["describe"]), "describe cases")
