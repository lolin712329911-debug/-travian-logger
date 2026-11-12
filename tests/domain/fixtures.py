"""tests/domain 共用的假資料（A3a）。不是測試檔。"""
from travian_bot.common import parsed as P
from travian_bot.common.models import VillageSnapshot


def fields(levels=None, costs=None, building=(), secs=1000):
    """18 塊資源田：aid 1..18，gid 依 1,2,3,4 輪流（和遊戲 4-4-4-6 的常見排法無關，只為測試）。
    levels／costs 是 {aid: 值}；沒給的預設等級 1、成本 (100,100,100,100)。"""
    out = []
    for aid in range(1, 19):
        gid = (aid - 1) % 4 + 1
        lv = (levels or {}).get(aid, 1)
        cost = (costs or {}).get(aid, (100, 100, 100, 100))
        out.append(P.ResField(aid, gid, lv, cost, secs, aid in building, None))
    return tuple(out)


def dorf1(stock=(1000, 1000, 1000, 1000), prod=(100, 100, 100, 100), cap_wh=3000, cap_gr=3000, free_crop=50,
          flds=None, queue=()):
    return P.Dorf1(tuple(stock), tuple(prod), cap_wh, cap_gr, free_crop, flds if flds is not None else fields(),
                   tuple(P.QueueItem(s, None) for s in queue), 0, None, (), None, None)


def dorf2(spec=None):
    """spec＝{aid: (gid, level, under_construction)}；其餘 aid 19..38 是空地、39／40 是集結點／城牆。"""
    spec = dict(spec or {})
    slots = []
    for aid in range(19, 41):
        if aid in spec:
            g, lv, b = (tuple(spec[aid]) + (False,))[:3]
            slots.append(P.BuildingSlot(aid, g, lv, None, bool(b)))
        elif aid == 39:
            slots.append(P.BuildingSlot(aid, 16, 1, None, False))
        elif aid == 40:
            slots.append(P.BuildingSlot(aid, 31, 0, None, False))
        else:
            slots.append(P.BuildingSlot(aid, None, 0, None, False))
    return P.Dorf2(tuple(slots))


def uc(cost, secs=2000):
    return P.UpgradeCost(tuple(cost), secs, False, None, None)


def option(gid, cost=(100, 100, 100, 100), secs=1500, buildable=True, conds=()):
    return P.BuildOption(gid, "b%d" % gid, tuple(cost), secs, buildable, "u" if buildable else None, False, None,
                         None, tuple(conds))


def cond(gid, level, met=False, forbidden=False):
    return P.BuildCondition(gid, "c%d" % gid, level, met, None, forbidden)


def snapshot(stock=(1000, 1000, 1000, 1000), prod=(100, 100, 100, 100), cap_wh=3000, cap_gr=3000,
             hidden=(0, 0, 0, 0), attacks=0, **kw):
    return VillageSnapshot(1, "2026-11-11T00:00:00Z", tuple(stock), tuple(prod), cap_wh, cap_gr, tuple(hidden), 0, 0,
                           None, None, (), (), attacks, None, None)
