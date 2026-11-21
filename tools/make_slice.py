#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_slice.py v0.2.1 — 從主檔 multi-village-dev-vX.md 產生單一 WP 的切片（只用標準庫）。
用法：python tools/make_slice.py MASTER WP [-o OUT] [--no-contracts] [--decisions] [--extra cm-05,cm-06]
      python tools/make_slice.py MASTER --check-all     （檢查主檔每個 WP 都能解析出交付卡片）
切片是唯讀產物，不手改、不保存；主檔才是唯一真相來源（§8.4）。
"""
import argparse
import re
import sys

CARD_ID = r"(?:cm|ps|dm|if|ac|ap)-\d{2}"


def heading_level(line):
    m = re.match(r"^(#{1,6}) ", line)
    return len(m.group(1)) if m else 0


def get_section(lines, prefix):
    for i, line in enumerate(lines):
        lv = heading_level(line)
        if lv and line.startswith(prefix):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                lj = heading_level(lines[j])
                if lj and lj <= lv:
                    end = j
                    break
            return lines[i:end]
    return None


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def parse_cards(lines):
    cards = {}
    for line in lines:
        m = re.match(r"^\| (%s) \|" % CARD_ID, line)
        if m:
            c = cells(line)
            if len(c) != 6:
                raise ValueError("卡片欄數不是 6：%s（%d 欄）" % (m.group(1), len(c)))
            cards[m.group(1)] = {"line": line, "deps": re.findall(CARD_ID, c[3])}
    return cards


def parse_ids(cell):
    ids = []
    for m in re.finditer(r"(?:([a-z]{2})-)?(\d{2})(?:～(\d{2}))?", cell):
        pref, a, b = m.group(1), m.group(2), m.group(3)
        if pref:
            parse_ids.prefix = pref
        if not getattr(parse_ids, "prefix", None):
            continue
        for n in range(int(a), int(b or a) + 1):
            ids.append("%s-%02d" % (parse_ids.prefix, n))
    parse_ids.prefix = None
    return ids


def wp_rows(sec7):
    rows = {}
    for i, line in enumerate(sec7):
        m = re.match(r"^\| \*\*([A-Za-z0-9\-]+)\*\*", line)
        if m:
            header = None
            for k in range(i - 1, -1, -1):
                if sec7[k].startswith("| WP |"):
                    header = [sec7[k], sec7[k + 1]]
                    break
            rows[m.group(1)] = (line, header)
    return rows


def tool_rows(sec42, wp):
    rows, header = [], None
    for line in sec42:
        if line.startswith("| 檔 | 內容 | WP |"):
            header = [line]
        if re.match(r"^\| `(tools|tests)/", line) and cells(line)[-1] == wp:
            rows.append(line)
    return header, rows


def wp_in_cell(text, wp, order):
    """text 內是否點名 wp（含 A3a～A3c 這類範圍）。"""
    if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(wp), text):
        return True
    for m in re.finditer(r"([A-Za-z][A-Za-z0-9\-]*)～([A-Za-z][A-Za-z0-9\-]*)", text):
        a, b = m.group(1), m.group(2)
        if a in order and b in order and wp in order:
            if order.index(a) <= order.index(wp) <= order.index(b):
                return True
    return False


def handoff_parts(s9, wp, order):
    """§9「交接紀錄」之後的區塊：最新 WP 的整段附上；舊 WP 的「留給後續 WP 的事項」只附點名本 WP 的列。"""
    start = next((i for i, l in enumerate(s9) if l.startswith("**交接紀錄")), None)
    if start is None:
        return []
    segs, cur = [], None
    for l in s9[start + 1:]:
        m = re.match(r"^\*\*(\S+?) (交接區塊|留給後續 WP 的事項)", l)
        if m:
            cur = {"wp": m.group(1), "kind": m.group(2), "lines": [l]}
            segs.append(cur)
        elif cur is not None:
            if l.strip() == "---":
                cur = None
            else:
                cur["lines"].append(l)
    if not segs:
        return []
    latest = segs[0]["wp"]
    for sg in segs:                      # 新的在上面：取檔案中第一個「交接區塊」（v0.2.1；v0.2 取到最後一個＝最舊的）
        if sg["kind"] == "交接區塊":
            latest = sg["wp"]
            break
    out = []
    for sg in segs:
        body = [l for l in sg["lines"][1:] if l.strip()]
        if sg["wp"] == latest:
            out += sg["lines"] + [""]
        elif sg["kind"] == "留給後續 WP 的事項":
            keep = []
            for l in body:
                if l.startswith("|"):
                    if wp_in_cell(cells(l)[-1], wp, order):
                        keep.append(l)
                elif wp_in_cell(l, wp, order):
                    keep.append(l)
            if keep:
                hdr = [l for l in body if l.startswith("|")][:2]
                out += [sg["lines"][0]] + [""] + (hdr if hdr and keep[0].startswith("|") else []) + keep + [""]
    return out


def build(md, wp, contracts=True, decisions=False, extra=(), all_cards=False):
    lines = md.split("\n")
    ver = re.search(r"本版：(v[\d.]+)", md).group(1)
    sec = lambda p: get_section(lines, p) or []
    sec7 = sec("## 7. ")
    rows = wp_rows(sec7)
    if wp not in rows:
        raise SystemExit("找不到 WP：%s（可用：%s）" % (wp, "、".join(rows)))
    wp_line, wp_header = rows[wp]
    sec42 = sec("### 4.2 ")
    cards = parse_cards(sec42)
    deliver = [i for i in parse_ids(cells(wp_line)[2]) if i in cards]
    deliver += [i for i in extra if i in cards and i not in deliver]
    if all_cards:
        deliver += [i for i in cards if i not in deliver]
    unknown = [i for i in parse_ids(cells(wp_line)[2]) if i not in cards]
    deps = []
    for i in deliver:
        for d in cards[i]["deps"]:
            if d not in deliver and d not in deps:
                deps.append(d)
    card_header = next((l for l in sec42 if l.startswith("| ID | 檔 |")), "")
    sep = "|---|---|---|---|---|---|"
    t_header, t_rows = tool_rows(sec42, wp)

    parts = {}
    head = [lines[0], "", "**本版：%s｜切片：%s**（由 `tools/make_slice.py` 自主檔產生，唯讀；有變動只改主檔）" % (ver, wp), ""]
    head += [l for l in lines if l.startswith("**一句話**") or l.startswith("**標記**")]
    parts["標頭"] = head
    parts["§0"] = sec("## 0. ")
    parts["§1"] = sec("## 1. ")
    parts["§4.1"] = sec("### 4.1 ")
    intro = []
    for l in sec42[1:]:
        if l.startswith("|") or l.startswith("**"):
            break
        if l.startswith(">"):
            intro.append(l)
    c = ["### 4.2 本 WP 卡片", ""] + intro + [""]
    if deliver:
        c += ["**本 WP 交付**", "", card_header, sep] + [cards[i]["line"] for i in deliver] + [""]
    if t_rows:
        c += ["**本 WP 的 tools／tests 項目**", ""] + (t_header or []) + ["|---|---|---|"] + t_rows + [""]
    if deps:
        c += ["**直接依賴的卡片（只讀，不在本 WP 交付）**", "", card_header, sep] + [cards[i]["line"] for i in deps] + [""]
    parts["§4.2 卡片"] = c
    parts["§5.1"] = sec("### 5.1 ")
    if contracts:
        parts["§6"] = sec("## 6. ")
    parts["§7 本 WP"] = ["## 7. 本 WP 在工作包表的那一列", ""] + (wp_header or []) + [wp_line]
    s9 = sec("## 9. ")
    status, recs = [], [l for l in s9 if l.startswith("- 20")]
    for l in s9:
        if l.startswith("**交接紀錄"):
            break
        status.append(l)
    parts["§8.2 交接區塊範本"] = sec("### 8.2 ")
    parts["§9"] = status + ["", "**最近交接（共 %d 筆，只列最後 3 筆）**" % len(recs)] + recs[-3:]
    parts["§9 交接區塊與後續事項"] = handoff_parts(s9, wp, list(rows))
    tail = ["## 10.（節錄）決策與風險", ""]
    tail += sec("### 待決")[0:] + [""] + sec("### 架構與遷移風險")
    if decisions:
        tail += [""] + sec("### 已定")
    parts["§10"] = tail
    text = "\n".join(l for p in parts.values() for l in p + [""])
    sizes = {k: len("\n".join(v).encode("utf-8")) for k, v in parts.items()}
    return text, sizes, deliver, deps, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("wp", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--no-contracts", action="store_true")
    ap.add_argument("--decisions", action="store_true")
    ap.add_argument("--extra", default="")
    ap.add_argument("--all-cards", action="store_true", help="附上全部卡片（A1a-3 產生 arch_manifest 需要）")
    ap.add_argument("--check-all", action="store_true")
    a = ap.parse_args()
    md = open(a.master, encoding="utf-8").read()
    if a.check_all:
        bad = 0
        for wp in wp_rows(get_section(md.split("\n"), "## 7. ")):
            try:
                _, _, d, dep, unk = build(md, wp)
            except SystemExit as e:
                print("ERROR", wp, e); bad += 1; continue
            flag = "  <-- 檢查" if unk else ""
            print("%-6s 交付 %2d 張｜依賴 %2d 張｜未對上 %s%s" % (wp, len(d), len(dep), unk or "-", flag))
            bad += bool(flag)
        sys.exit(1 if bad else 0)
    if not a.wp:
        ap.error("需要 WP")
    extra = [x for x in a.extra.split(",") if x]
    text, sizes, d, dep, unk = build(md, a.wp, not a.no_contracts, a.decisions, extra, a.all_cards)
    out = a.out or "slice_%s.md" % a.wp
    open(out, "w", encoding="utf-8").write(text)
    print("輸出 %s：%d bytes（主檔 %d bytes）" % (out, len(text.encode("utf-8")), len(md.encode("utf-8"))))
    print("交付卡片：%s｜依賴卡片：%s｜未對上：%s" % (d, dep, unk or "無"))
    for k, v in sizes.items():
        print("  %-10s %6d bytes" % (k, v))


if __name__ == "__main__":
    main()
