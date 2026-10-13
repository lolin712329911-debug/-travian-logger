"""Config 解析與 run_hero_cycle 的離線測試（python test_hero_cycle.py）。
專案其他模組（notify、travian_const、travian_pages）若不在路徑上，會用最小的 stub 取代，只為了能 import。"""
import contextlib, io, sys, types

def _stub(name, **attrs):
    try:
        __import__(name)
    except Exception:
        m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m

try:
    import gspread.exceptions  # noqa
except Exception:             # 測試環境沒裝 gspread：只需要 WorksheetNotFound 這個名字
    g = types.ModuleType("gspread"); ge = types.ModuleType("gspread.exceptions")
    ge.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {}); g.exceptions = ge
    sys.modules["gspread"] = g; sys.modules["gspread.exceptions"] = ge
_stub("notify", notify=lambda msg: None)
_stub("travian_const", BUILDING_GIDS={}, DEFAULT_TARGET_BUILDING_LEVEL=0, FREE_SLOT_RANGE=(19, 40),
      MAX_NON_CAPITAL_FIELD_LEVEL=10, RESOURCE_FIELD_PRODUCTION={}, ROMAN_TRIBE_ID=1, TRIBE_NAMES={},
      RES_NAMES=["木", "磚", "鐵", "糧"], gid_name=lambda g: str(g), BIDI=__import__("re").compile("[\u202a-\u202e\u200e\u200f]"))
from travian_models import State
_stub("travian_pages", fetch_build_options=None, parse_building_cost=None, parse_dorf2_slots=None,
      parse_dorf1=lambda html: State(stock=[0]*4, cap=[0]*4, prod=[0]*4, free_crop=0, attacks=0))

with contextlib.redirect_stdout(io.StringIO()):
    import test_hero as TH
import sheets_writer as SW
import runner as R

def check(name, got, want):
    assert got == want, f"{name}: got {got!r}, want {want!r}"
    print("ok", name)

# ------------------------------------------------ Config
class FakeWS:
    def __init__(self, rows): self.rows = rows; self.row_count = 100; self.col_count = 3; self.updated = None
    def get_all_values(self): return self.rows
    def add_rows(self, n): pass
    def add_cols(self, n): pass
    def update(self, range_name, values, raw=False): self.updated = values
class FakeSH:
    def __init__(self, ws): self.ws = ws
    def worksheet(self, name): return self.ws
SW.has_sheet = lambda: True

def cfg_of(rows):
    ws = FakeWS(rows); SW.open_sheet = lambda: FakeSH(ws)
    with contextlib.redirect_stdout(io.StringIO()):
        return SW.load_config(), ws

d = SW._default_cfg()
check("default hero keys", (d["hero_adventure"], d["hero_min_health"], d["hero_allowed"], d["hero_skip_on_incoming"]),
      (False, 45, "normal", True))
c, ws = cfg_of([["enabled", "TRUE"]])
check("missing rows appended", [r[0] for r in ws.updated], list(SW._CONFIG_ORDER[1:]))   # 不會 KeyError
check("appended hero_adventure FALSE", [r for r in ws.updated if r[0] == "hero_adventure"][0][1], "FALSE")
c, _ = cfg_of([["hero_adventure", ""]]);            check("blank hero_adventure = False", c["hero_adventure"], False)
c, _ = cfg_of([["hero_adventure", "maybe"]]);       check("garbage hero_adventure = False", c["hero_adventure"], False)
c, _ = cfg_of([["hero_adventure", "TRUE"]]);        check("TRUE hero_adventure", c["hero_adventure"], True)
c, _ = cfg_of([["enabled", ""]]);                   check("blank enabled still TRUE (舊行為不變)", c["enabled"], True)
c, _ = cfg_of([["hero_skip_on_incoming", ""]]);     check("blank skip_on_incoming = True", c["hero_skip_on_incoming"], True)
c, _ = cfg_of([["hero_skip_on_incoming", "FALSE"]]);check("FALSE skip_on_incoming", c["hero_skip_on_incoming"], False)
c, _ = cfg_of([["hero_min_health", "60"]]);         check("min_health 60", c["hero_min_health"], 60)
c, _ = cfg_of([["hero_min_health", "abc"]]);        check("min_health garbage keeps 45", c["hero_min_health"], 45)
c, _ = cfg_of([["hero_allowed", "normal,hard"]]);   check("allowed string", c["hero_allowed"], "normal,hard")
c, _ = cfg_of([["hero_allowed", ""]]);              check("allowed blank keeps normal", c["hero_allowed"], "normal")

# ------------------------------------------------ run_hero_cycle
logs, notes, clicks = [], [], []
R.log_action = lambda row: logs.append(row)
R.notify = lambda m: notes.append(m)
R.time.sleep = lambda s: None
STOCK = '<div id="stockBar"></div>'

def run(status, cfg=None, h=100, icon="heroHome", attacks=0, click=None, dry=False, advs=TH.ADV_P0,
        flag=True, get_raises=False, **kw):
    logs.clear(); notes.clear(); clicks.clear()
    R.P.parse_dorf1 = lambda html: State(stock=[0]*4, cap=[0]*4, prod=[0]*4, free_crop=0, attacks=attacks)
    d1 = STOCK + TH.hud(h, icon)
    adv = TH.hud(h, "heroHome") + TH._json(status, advs) + (TH.table(advs, **kw) if status["status"] != 50 else "")
    def get(p):
        if get_raises: raise RuntimeError("boom")
        return adv
    def default_click(n, i, row):
        clicks.append((n, i, row.icon)); return True, "已確認出發"
    cfg_full = {**TH.CFG, "hero_adventure": flag, **(cfg or {})}
    R.run_hero_cycle(cfg_full, get=get, get_dorf1=lambda: d1, click_adventure=click or default_click, dry=dry)

run(TH.HOME, flag=False);                check("flag off: nothing", (logs, notes, clicks), ([], [], []))
run(TH.HOME, dry=True);                  check("DRY: no click", clicks, [])
check("DRY: logged 未送出", (logs[0][1], logs[0][6], logs[0][7]), ("冒險", "DRY", "未送出"))
run(TH.HOME);                            check("LIVE: clicked #7 row index 1", clicks, [(7, 1, "normal")])
check("LIVE: logged 成功 + notified", (logs[0][7], len(notes)), ("成功", 1))
run(TH.HOME, click=lambda n, i, r: (False, "沒看到出發"))
check("click failed: logged, notified, no raise", (logs[0][7], len(notes)), ("沒看到變化", 1))
run(TH.HOME, h=40);                      check("low health: skip + log, no notify, no click", (logs[0][7], notes, clicks), ("未出發", [], []))
run(TH.HOME, attacks=3);                 check("incoming: skip", clicks, [])
run(TH.HOME, attacks=3, cfg={"hero_skip_on_incoming": False}); check("incoming allowed: click", len(clicks), 1)
run(TH.GOING);                           check("going: silent (no log, no click)", (logs, clicks), ([], []))
run(TH.RETURN, disabled=True);           check("returning: silent", (logs, clicks), ([], []))
run(TH.HOME, icon="heroRunning");        check("hud not at home: silent", (logs, clicks), ([], []))
run({**TH.HOME, "status": 30});          check("unknown status: log + notify", (len(logs), len(notes), clicks), (1, 1, []))
run(TH.HOME, get_raises=True);           check("exception: notified, not raised", (len(notes), clicks), (1, []))
R_ok = True
print("ALL PASSED")
