"""版本：hero-v1.2（2026-10-13，加入真實 HUD 片段測試；版本歷史見 project-notes 的「版本對照」）
travian_hero 離線測試（不需網路、不需 pytest：python test_hero.py）。

fixtures：
- JSON 兩份是 International 11 的真實 viewData（P0 在家 ts1791799322、P1 去程 ts1791799378）。
- HUD 片段取自同兩頁的頂端列（體力 41%、經驗 97%、冒險數 17）。
- 「渲染後表格」是**依文件記載的結構程式產生的合成資料**（不是真實 T2），
  真實 T2 到手後應補一個以真實 HTML 為準的測試。
"""
import json
from travian_hero import (
    parse_hero_hud, parse_hero_json, parse_adventure_rows, rows_match_json, plan_adventure,
    HeroState, AdventureRow,
)

ADV_P0 = [
 (5,4.12311,"clay",0,1060),(7,4.12311,"grassland",2,1060),(8,9.48683,"hill",3,2439),
 (9,4.47214,"forest",0,1150),(10,5.65685,"grassland",1,1455),(11,5.83095,"grassland",2,1499),
 (12,9.21954,"hill",3,2371),(14,8.06226,"clay",1,2073),(31,11.40175,"natar_village",1,2932),
 (32,10,"forest",2,2571),(34,9.05539,"grassland",0,2329),(35,9.21954,"forest",1,2371),
 (36,8.544,"clay",2,2197),(38,8.94427,"grassland",0,2300),(40,9.21954,"grassland",2,2371),
 (44,8.48528,"hill",2,2182),(45,9.43398,"grassland",3,2426)]

def _json(status_block, advs, hero_extra=None):
    hero = {"isRegenerating": False, "regenerationTimeLeft": None,
            "homeVillage": {"mapId": 11233, "id": 65222, "name": "x"},
            "status": status_block, "adventureDurationBonus": None, "adventureDifficultyBonus": False,
            "adventures": [{"number": n, "mapId": None, "x": None, "y": None, "distance": d,
                            "place": p, "difficulty": df, "travelingDuration": t} for n, d, p, df, t in advs]}
    hero.update(hero_extra or {})
    data = {"data": {"ownPlayer": {"hero": hero, "villages": []}, "bootstrapData": {}}}
    return ('<script>window.Travian.React.HeroAdventure.render({gql: "q", viewData: %s, '
            'activePerspective: "perspectiveBuildings"}, ["a"]);</script>' % json.dumps(data))

HOME = {"status": 100, "inOasis": None, "inVillage": {"id": 65222, "mapId": 11233, "name": "x", "type": 1},
        "adventure": None, "arrivalAt": None, "arrivalIn": None, "onWayTo": None}
GOING = {"status": 50, "inOasis": None, "inVillage": None,
         "adventure": {"number": 7, "hasDifficultyBonusActive": False, "hasDurationBonusActive": False},
         "arrivalAt": 1791800404, "arrivalIn": 1026, "onWayTo": None}
RETURN = {"status": 9, "inOasis": None, "inVillage": None, "adventure": None,
          "arrivalAt": 1791801000, "arrivalIn": 575, "onWayTo": {"id": 65222, "x": -196, "y": 172, "type": 1,
                                                                  "village": {"mapId": 11233, "name": "x"}}}

HUD = ('<div id="topBarHero" class="heroV2">'
       '<svg class="health"><path class="title" d="M0"><title>體力: &#x202d;&#x202d;{h}&#x202c;&#37;&#x202c;</title></path></svg>'
       '<svg class="experience"><path class="title" d="M0"><title>經驗 &amp;#x202d;&amp;#x202d;97&amp;#x202c;&amp;#37;&amp;#x202c;||還需 10 經驗</title></path></svg>'
       '<div class="heroStatus"><a href="#"><i class="{icon}"></i></a></div>'
       '<a class="adventure"><div class="content">17</div></a></div>')

def hud(h=41, icon="heroHome"):
    return HUD.replace("{h}", str(h)).replace("{icon}", icon)

def table(advs, disabled=False, drop_hard=False):
    trs = []
    for n, d, p, df, t in advs:
        icon = "difficulty_hard" if df == 0 else "difficulty_normal"   # 文件記載：difficulty 0 ＝ hard 圖示
        ds = f"{float(f'{d:.3g}'):g}"
        dur = f"{t//3600}:{t%3600//60:02d}:{t%60:02d}"
        cls = "textButtonV2 buttonFramed rectangle green" + (" disabled" if disabled else "")
        trs.append(f'<tr><td class="place"><img class="{p}"></td>'
                   f'<td class="distance">\u202d{ds}\u202c 資源田</td>'
                   f'<td class="duration"><div class="duration">{dur}</div></td>'
                   f'<td class="difficulty"><i class="{icon}"></i></td>'
                   f'<td class="button"><button class="{cls}">探索</button></td></tr>')
    return '<table class="adventureList"><tbody>' + "".join(trs) + "</tbody></table>"

CFG = {"hero_min_health": 45, "hero_allowed": "normal", "hero_skip_on_incoming": True}

def page(status, advs=ADV_P0, h=100, icon="heroHome", **kw):
    return hud(h, icon) + _json(status, advs) + (table(advs, **kw) if status["status"] != 50 else "")

def plan(status, h=100, incoming=0, cfg=None, advs=ADV_P0, extra=None, **kw):
    html = hud(h, "heroHome") + _json(status, advs, extra) + (table(advs, **kw) if status["status"] != 50 else "")
    return plan_adventure(parse_hero_json(html), parse_adventure_rows(html),
                          parse_hero_hud(html).health, {**CFG, **(cfg or {})}, incoming)

def check(name, got, want):
    assert got == want, f"{name}: got {got!r}, want {want!r}"
    print("ok", name)

# ---- 解析
h = parse_hero_hud(hud(41, "heroHome"))
check("hud health", h.health, 41); check("hud exp", h.experience, 97)
check("hud adv count", h.adventures_count, 17); check("hud home", h.at_home, True)
check("hud running", parse_hero_hud(hud(41, "heroRunning")).at_home, False)
check("hud missing", parse_hero_hud("<html></html>").health, None)

s0 = parse_hero_json(page(HOME)); check("home status", (s0.status, s0.in_village, s0.adventure_number, s0.arrival_in), (100, True, None, None))
check("home 17 adventures", len(s0.adventures), 17)
s1 = parse_hero_json(page(GOING)); check("going", (s1.status, s1.in_village, s1.adventure_number, s1.arrival_in), (50, False, 7, 1026))
s9 = parse_hero_json(page(RETURN)); check("return", (s9.status, s9.adventure_number, s9.arrival_in), (9, None, 575))
check("json missing", parse_hero_json("<html></html>"), None)
check("distance 3sf", s0.adventures[0].distance, 4.12); check("distance 10", s0.adventures[9].distance, 10.0)

rows = parse_adventure_rows(page(HOME))
check("17 rows", len(rows), 17)
check("hard numbers", sorted(s0.adventures[i].number for i, r in enumerate(rows) if r.icon == "hard"), [5, 9, 34, 38])
check("rows match json", rows_match_json(s0, rows), None)
check("going has no rows", parse_adventure_rows(page(GOING)), [])
check("disabled button", parse_adventure_rows(page(RETURN, disabled=True))[0].disabled, True)
bad = list(rows); bad[3] = AdventureRow("hill", 4.47, 1150, "hard", False, True)
check("mismatch place detected", rows_match_json(s0, bad) is not None, True)

# ---- 決策（normal 圖示、最短去程）：normal 中 #7(1060s) 最短
check("send shortest normal", plan(HOME), ("send", 7, 1))
check("health 45 skip", plan(HOME, h=45)[0], "skip")
check("health 46 send", plan(HOME, h=46)[0], "send")
check("health unknown skip", plan_adventure(s0, rows, None, CFG, 0), ("skip", "讀不到體力"))
check("going skip", plan(GOING)[0], "skip")
check("returning skip", plan(RETURN, disabled=True)[0], "skip")
check("unknown status", plan({**HOME, "status": 30})[0], "skip")
check("incoming skip", plan(HOME, incoming=3)[0], "skip")
check("incoming off", plan(HOME, incoming=3, cfg={"hero_skip_on_incoming": False})[0], "send")
check("incoming unknown skip", plan(HOME, incoming=None)[0], "skip")
check("regenerating skip", plan(HOME, extra={"isRegenerating": True})[0], "skip")
check("difficulty bonus skip", plan(HOME, extra={"adventureDifficultyBonus": True})[0], "skip")
check("no adventures", plan(HOME, advs=[])[0], "skip")
check("allow hard picks #5", plan(HOME, cfg={"hero_allowed": "normal,hard"}), ("send", 5, 0))
check("disabled button skip", plan(HOME, disabled=True)[0], "skip")
only_hard = [a for a in ADV_P0 if a[3] == 0]
check("only hard & normal-only cfg", plan(HOME, advs=only_hard)[0], "skip")


# ---- BIDI 兩種型態（專案是正規表示式、備援是 list）
import re, travian_hero as _H
_orig = _H.BIDI
for b in (re.compile("[\u202a-\u202e\u200e\u200f]"), ["\u202c", "\u202d"]):
    _H.BIDI = b
    check("clean with " + type(b).__name__, _H._clean("\u202d41\u202c%"), "41%")
    check("hud with " + type(b).__name__, parse_hero_hud(hud(41)).health, 41)
_H.BIDI = _orig

# ---- 真實頁面片段（International 11，2026-10-13 報告頁頂端列，返回中）：fixture_hud_returning_real.html
# 內容取自使用者上傳的原始碼（體力／經驗／冒險數／heroStatus 逐字；英雄頭像與長提示做了縮短）
import os
_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture_hud_returning_real.html")
if os.path.exists(_p):
    _real = parse_hero_hud(open(_p, encoding="utf-8").read())
    check("real hud health", _real.health, 90)
    check("real hud exp", _real.experience, 21)
    check("real hud adv count", _real.adventures_count, 16)
    check("real hud returning = not at home", _real.at_home, False)
print("ALL PASSED")
