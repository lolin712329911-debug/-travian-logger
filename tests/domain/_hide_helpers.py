"""hide_plan／hide_decide 測試共用：讀 golden、組 RallyOverview／HideContext。"""
import json
import os

from travian_bot.common import geo
from travian_bot.common.models import HideContext, Oasis
from travian_bot.common.parsed import RallyMovement, RallyOverview

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden", "domain", "hide_decide", "decide_cases.expected.json")
MAP_HALF = 200


def load_golden():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


def movement(kinds, arrive_ts, units=None):
    return RallyMovement(kinds=tuple(kinds), hostile=any(k in ("inRaid", "inAttack") for k in kinds), own_home=False,
                         arrive_ts=arrive_ts, units=dict(units or {}), role_did=None, head_did=None, link_did=None,
                         recall_id=None, section="", headline="")


def overview(now_ts, arrivals=(), units_home=None, extra=()):
    moves = tuple(movement(("inRaid",), a, {"u1": None}) for a in arrivals) + tuple(extra)
    return RallyOverview(server_ts=now_ts, movements=moves, units_home=units_home, units_away=None,
                         incoming_attacks=len(tuple(arrivals)))


def ctx_from_case(c):
    return HideContext(home_x=c["home"][0], home_y=c["home"][1],
                       oases=tuple(Oasis(x, y, kind, safe) for x, y, kind, safe in c["oases"]),
                       blocked=tuple(geo.map_id(x, y, MAP_HALF) for x, y in c["blocked_pos"]), tribe=c["tribe"])
