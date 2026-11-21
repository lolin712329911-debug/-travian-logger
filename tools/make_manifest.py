"""make_manifest.py  v0.1.1  (A1a-3 後續)

用途：從主檔（或切片檔）的 §4.2 檔案卡片表，轉出 tools/arch_manifest.py。§4.2 變動後重跑一次，
      不要手改 arch_manifest.py。與 compress_cards.py 同源（同一張卡片表）。
輸入：主檔 .md（7 欄：ID｜檔｜內容｜依賴｜舊源→處置｜WP｜測試）或切片檔 .md（6 欄：少「測試」）。
      「依賴」欄兩種寫法都吃：卡片 ID（cm-01）或檔案路徑（`common/models`，依 path→ID 對照轉成 ID）。
轉出前的檢查（任何一項不過就不寫檔、exit 1）：
  ①卡片 ID 不重複　②欄數正確　③依賴對得到卡片　④沿用 check_arch.check_manifest 的規則
  （層級與路徑一致、依賴方向符合 §4.1、依賴圖無循環）　⑤文中寫的「N 個模組」與解析到的張數相同
  （文中沒有這句才用解析張數當預期）。
用法：python tools/make_manifest.py SRC.md [-o tools/arch_manifest.py] [--check]
      --check：不寫檔，只比對現有 arch_manifest.py 是否與來源一致（不一致 exit 1）。
exit：0＝成功（或 --check 一致）、1＝來源有問題或 --check 不一致、2＝用法或檔案錯誤。
依賴：標準庫＋ tools/check_arch.py。
部署狀態：僅開發用，不在 bot 執行路徑上。
"""
import argparse
import importlib.util
import os
import re
import sys

VERSION = "0.1.1"
LAYER_OF_PREFIX = {"cm": "common", "ps": "parsers", "dm": "domain",
                   "if": "infra", "ac": "actions", "ap": "app"}
ROW_RE = re.compile(r"^\| ((?:cm|ps|dm|if|ac|ap)-\d+) \|")
ID_RE = re.compile(r"\b(?:cm|ps|dm|if|ac|ap)-\d+\b")
DISP_KEYWORDS = ("新寫", "改寫", "拆", "沿用")
SEC_START, SEC_END = "### 4.2 ", "#### tools/、tests/、其他"


class SourceError(ValueError):
    pass


def _load_check_arch():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_arch.py")
    spec = importlib.util.spec_from_file_location("check_arch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm_path(p):
    return re.sub(r"\.py$", "", p.strip().strip("`"))


def _disposition(old):
    m = re.search(r"\*\*(.+)\*\*[^*]*$", old)
    seg = m.group(1) if m else old
    hits = [(seg.find(k), k) for k in DISP_KEYWORDS if k in seg]
    return min(hits)[1] if hits else ""


def parse_cards(text):
    """回傳 (cards, 文中的預期張數 or None, 版本字串 or None)。"""
    if SEC_START in text:                       # 主檔：只取 §4.2，避免別處的表
        start = text.index(SEC_START)
        end = text.find(SEC_END, start)
        body = text[start:end if end != -1 else len(text)]
    else:
        body = text
    rows = {}
    order = []
    for line in body.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) not in (6, 7):
            raise SourceError(f"{m.group(1)}：欄數 {len(cells)}（應為 6 或 7）")
        if m.group(1) in rows:
            if rows[m.group(1)] != cells:
                raise SourceError(f"{m.group(1)}：出現兩次且內容不同")
            continue
        rows[m.group(1)] = cells
        order.append(m.group(1))
    if not rows:
        raise SourceError("找不到任何卡片列（| cm-01 | … |）")
    path_to_id = {_norm_path(rows[i][1]): i for i in order}
    cards = []
    for cid in order:
        cells = rows[cid]
        path = cells[1].strip("`")
        deps, seen = [], set()
        dep_cell = cells[3]
        tokens = ID_RE.findall(dep_cell)
        for tok in re.findall(r"`([^`]+)`", dep_cell):
            p = _norm_path(tok)
            if p in path_to_id:
                tokens.append(path_to_id[p])
            else:
                raise SourceError(f"{cid}：依賴 `{tok}` 對不到任何卡片的檔案路徑")
        # 依在文字中的出現順序輸出：ID 與路徑混用時以「ID 在前、路徑在後」為準，去重
        for t in tokens:
            if t not in seen:
                seen.add(t)
                deps.append(t)
        wp = re.sub(r"〔.*?〕", "", cells[5]).strip()
        cards.append({"id": cid, "path": path, "layer": LAYER_OF_PREFIX[cid[:2]],
                      "deps": deps, "wp": wp, "disp": _disposition(cells[4])})
    cards.sort(key=lambda c: c["id"])
    m = re.search(r"(\d+)\s*個模組", text)
    ver = re.search(r"\*\*本版：(v[\d.]+)", text)
    return cards, (int(m.group(1)) if m else None), (ver.group(1) if ver else None)


def render(cards, expected, source_label):
    head = '''"""arch_manifest.py  v0.1  (A1a-3)

用途：{n} 張模組卡片的機器可讀登記表，與主檔 §4.2 同源。本檔由 tools/make_manifest.py 轉出，
      §4.2 有變動請改主檔後重新轉出，不要手改本檔。
依賴：無（純資料）。
部署狀態：僅供 tools/check_arch.py 與測試使用，不在 bot 執行路徑上。

每項鍵：
  id    卡片 ID（cm-/ps-/dm-/if-/ac-/ap-）
  path  相對 travian_bot/ 的檔案路徑
  layer common／parsers／domain／infra／actions／app
  deps  依賴的卡片 ID list
  wp    交付的 WP（含「／」者＝多個 WP 接力，第一個為首次交付）
  disp  處置：沿用／拆／改寫／新寫（依「舊源→處置」欄最後的粗體字分類；僅供參考，不參與檢查）
"""

SOURCE = {src!r}
EXPECTED_COUNT = {exp}

MANIFEST = [
'''.format(n=len(cards), src=source_label, exp=expected)
    lines = ["    {'id': %r, 'path': %r, 'layer': %r, 'deps': %r, 'wp': %r, 'disp': %r}," %
             (c["id"], c["path"], c["layer"], c["deps"], c["wp"], c["disp"]) for c in cards]
    return head + "\n".join(lines) + "\n]\n"


def build(text, source_name):
    cards, stated, ver = parse_cards(text)
    if stated is not None and stated != len(cards):
        raise SourceError(f"文中寫 {stated} 個模組，但解析到 {len(cards)} 張卡片")
    expected = stated if stated is not None else len(cards)
    problems = _load_check_arch().check_manifest(cards, expected)
    if problems:
        raise SourceError("卡片表未通過檢查：\n" + "\n".join(p.text() for p in problems))
    label = f"{source_name} {ver + ' ' if ver else ''}§4.2"
    return render(cards, expected, label), len(cards)


def main(argv=None):
    ap = argparse.ArgumentParser(description="由 §4.2 卡片表轉出 arch_manifest.py")
    ap.add_argument("source", help="主檔或切片檔（.md）")
    ap.add_argument("-o", "--output", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           "arch_manifest.py"))
    ap.add_argument("--check", action="store_true", help="只比對現有輸出檔是否與來源一致")
    ap.add_argument("--version", action="version", version=f"make_manifest {VERSION}")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        with open(args.source, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"ERROR｜{e}", file=sys.stderr)
        return 2
    try:
        out, n = build(text, os.path.basename(args.source))
    except SourceError as e:
        print(f"ERROR｜{e}", file=sys.stderr)
        return 1
    if args.check:
        try:
            with open(args.output, encoding="utf-8", newline="") as fh:
                have = fh.read()
        except OSError as e:
            print(f"ERROR｜{e}", file=sys.stderr)
            return 2
        # 來源檔名與版本只是標籤，不算內容差異；其餘必須逐字相同
        strip = lambda s: re.sub(r"^SOURCE = .*$", "SOURCE = <label>", s, flags=re.M)
        same = strip(have) == strip(out)
        print(f"make_manifest {VERSION}：{'一致' if same else '不一致（請重新轉出）'}｜{n} 張", file=sys.stderr)
        return 0 if same else 1
    with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print(f"make_manifest {VERSION}：已寫入 {args.output}｜{n} 張", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
