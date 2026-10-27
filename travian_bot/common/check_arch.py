"""check_arch.py  v0.1  (A1a-3)

用途：架構檢查（slice §4.1／§4.2 的自動化）。WP 驗收必跑。
檢查項（規則名稱 → 說明）：
  MANIFEST         manifest 自身：ID／路徑不重複、層級與路徑一致、依賴對得到卡片且符合層級表、依賴圖無循環、張數
  UNREGISTERED     travian_bot/ 底下的 .py 沒登記在 manifest（__init__.py 除外）
  MISSING_FILE     --expect-wp 指定的 WP 應交付的檔案不存在
  LAYER_DEP        import 違反 §4.1 層級表（含同層限制：parsers／domain／actions 不可互相 import；
                   infra 只有 infra/store/* 內部可互依）
  CYCLE            模組 import 有循環
  PURE_LAYER_IO    common／parsers／domain 引入網路、Playwright 等 IO 套件
  ENV_IN_COMMON    common 讀環境變數（os.environ／os.getenv）
  OLD_ROOT_IMPORT  新程式 import repo 根目錄的舊模組（v0.22）
  TRIBE_STRING     種族名稱字串出現在 tribe_data／config_schema／schema 以外
  FORMAT_EXIT      strftime／isoformat／json.dumps 出現在 serialize 以外
  GSPREAD_EXIT     gspread 出現在 infra/store/gsheets 以外
  UNDECLARED_DEP   （預設為 WARN，--strict 才算違規）實際 import 的卡片不在該卡片「依賴」欄
未檢查（靜態看不出來，仍靠 code review）：只有 *_repo 讀寫 Sheet、只有 infra/session 讀寫 session 檔。

輸出：每行 `VIOLATION｜規則｜路徑｜細節`（警告行為 `WARN｜…`）；exit 0＝通過、1＝有違規、2＝用法或輸入錯誤。
      --json 時用 travian_bot.common.serialize.dumps_stable 輸出。
依賴：標準庫＋ tools/arch_manifest.py；--json 另需 travian_bot/common/serialize.py。
部署狀態：僅開發／CI 用，不在 bot 執行路徑上。
"""
import argparse
import ast
import importlib.util
import os
import re
import sys

VERSION = "0.1"
PACKAGE = "travian_bot"

LAYER_OF_PREFIX = {"cm": "common", "ps": "parsers", "dm": "domain",
                   "if": "infra", "ac": "actions", "ap": "app"}
LAYERS = tuple(LAYER_OF_PREFIX.values())

# 層級表（slice §4.1）：key 層可以 import 的層（含自己）
ALLOW = {
    "common": {"common"},
    "parsers": {"common"},
    "domain": {"common"},
    "infra": {"common", "infra"},
    "actions": {"common", "parsers", "infra"},
    "app": {"common", "parsers", "domain", "infra", "actions", "app"},
}
# 同層互相 import 一律禁止的層（common、app 可；infra 只有 store 內部可）
NO_SAME_LAYER = {"parsers", "domain", "actions"}

PURE_LAYERS = {"common", "parsers", "domain"}
IO_ROOTS = {"playwright", "requests", "httpx", "aiohttp", "urllib3", "socket",
            "selenium", "smtplib"}
IO_DOTTED = {"urllib.request", "http.client"}

TRIBE_RE = re.compile(r"\b(gaul|roman|teuton|egyptian|hun)s?\b")
TRIBE_ALLOWED_IDS = {"cm-06", "cm-08", "cm-11"}      # tribe_data、config_schema、schema
FORMAT_ALLOWED_ID = "cm-10"                          # serialize
GSPREAD_ALLOWED_ID = "if-04"                         # infra/store/gsheets
FORMAT_ATTRS = {"strftime", "isoformat"}


class Finding:
    def __init__(self, kind, rule, path, detail, line=None):
        self.kind, self.rule, self.path, self.detail, self.line = kind, rule, path, detail, line

    def key(self):
        return (self.path, self.rule, self.line or 0, self.detail)

    def text(self):
        loc = f"L{self.line}: " if self.line else ""
        return f"{self.kind}｜{self.rule}｜{self.path}｜{loc}{self.detail}"

    def as_dict(self):
        return {"rule": self.rule, "path": self.path, "line": self.line, "detail": self.detail}


# --------------------------------------------------------------------------- manifest

def load_manifest(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch_manifest.py")
    spec = importlib.util.spec_from_file_location("arch_manifest", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.MANIFEST), getattr(mod, "EXPECTED_COUNT", None)


def pair_allowed(src_path, dst_path):
    """src 檔 import dst 檔是否符合 §4.1。path 為相對 travian_bot/ 的路徑。"""
    sl, dl = src_path.split("/")[0], dst_path.split("/")[0]
    if dl not in ALLOW.get(sl, set()):
        return False
    if sl == dl:
        if sl in NO_SAME_LAYER:
            return False
        if sl == "infra":
            return src_path.startswith("infra/store/") and dst_path.startswith("infra/store/")
    return True


def check_manifest(manifest, expected_count=None):
    out = []
    ids, paths = {}, {}
    for c in manifest:
        cid, p = c["id"], c["path"]
        if cid in ids:
            out.append(Finding("VIOLATION", "MANIFEST", p, f"ID 重複：{cid}"))
        ids[cid] = c
        if p in paths:
            out.append(Finding("VIOLATION", "MANIFEST", p, f"路徑重複（{paths[p]}、{cid}）"))
        paths[p] = cid
        layer = LAYER_OF_PREFIX.get(cid[:2])
        if layer is None:
            out.append(Finding("VIOLATION", "MANIFEST", p, f"{cid} 的前綴不是已知層"))
        elif layer != c["layer"] or p.split("/")[0] != layer:
            out.append(Finding("VIOLATION", "MANIFEST", p,
                               f"{cid} 層級不一致：前綴={layer}、layer 欄={c['layer']}、路徑={p.split('/')[0]}"))
    for c in manifest:
        for d in c["deps"]:
            if d not in ids:
                out.append(Finding("VIOLATION", "MANIFEST", c["path"], f"{c['id']} 依賴 {d}，但沒有這張卡片"))
            elif d == c["id"]:
                out.append(Finding("VIOLATION", "MANIFEST", c["path"], f"{c['id']} 依賴自己"))
            elif not pair_allowed(c["path"], ids[d]["path"]):
                out.append(Finding("VIOLATION", "MANIFEST", c["path"],
                                   f"{c['id']}→{d} 違反層級表（{c['path']}→{ids[d]['path']}）"))
    graph = {c["id"]: [d for d in c["deps"] if d in ids] for c in manifest}
    for comp in _sccs(graph):
        if len(comp) > 1:
            out.append(Finding("VIOLATION", "MANIFEST", ids[sorted(comp)[0]]["path"],
                               "卡片依賴循環：" + "、".join(sorted(comp))))
    if expected_count is not None and len(manifest) != expected_count:
        out.append(Finding("VIOLATION", "MANIFEST", "tools/arch_manifest.py",
                           f"卡片數 {len(manifest)} ≠ 預期 {expected_count}"))
    return out


def _sccs(graph):
    """Tarjan；graph: node→[node]。回傳 list[set]。"""
    index, low, on, stack, res, counter = {}, {}, set(), [], [], [0]

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, []):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = set()
            while True:
                w = stack.pop()
                on.discard(w)
                comp.add(w)
                if w == v:
                    break
            res.append(comp)

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return res


# --------------------------------------------------------------------------- tree scan

def list_package_files(root, package=PACKAGE):
    """回傳 {相對 package 的路徑: 絕對路徑}（不含 __init__.py）。"""
    base = os.path.join(root, package)
    found = {}
    for dp, dns, fns in os.walk(base):
        dns[:] = sorted(d for d in dns if d != "__pycache__" and not d.startswith("."))
        for fn in sorted(fns):
            if fn.endswith(".py") and fn != "__init__.py":
                full = os.path.join(dp, fn)
                found[os.path.relpath(full, base).replace(os.sep, "/")] = full
    return found


def list_old_root_modules(root, package=PACKAGE):
    skip = {package, "tools", "tests"}
    names = set()
    for e in os.listdir(root):
        if e.startswith(".") or e in skip or e == "__pycache__":
            continue
        full = os.path.join(root, e)
        if os.path.isfile(full) and e.endswith(".py"):
            names.add(e[:-3])
        elif os.path.isdir(full) and any(f.endswith(".py") for _, _, fs in os.walk(full) for f in fs):
            names.add(e)
    return names


def dotted_of(path, package=PACKAGE):
    return package + "." + path[:-3].replace("/", ".")


def _docstring_nodes(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                ids.add(id(b[0].value))
    return ids


def _imports(tree, rel_path, package=PACKAGE):
    """回傳 list[(絕對 dotted 名稱 or None, 候選 list, lineno, 原始頂層名)]。
    每個 import 產生一個項目：(base_dotted, [候選子模組 dotted…], lineno)。"""
    out = []
    pkg_parts = (package + "/" + rel_path).split("/")[:-1]   # 檔案所在 package
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((a.name, [], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(pkg_parts) - (node.level - 1)
                if keep < 1:
                    out.append((None, [], node.lineno))
                    continue
                base_parts = pkg_parts[:keep]
                base = ".".join(base_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            cands = [f"{base}.{a.name}" for a in node.names if a.name != "*"]
            out.append((base, cands, node.lineno))
    return out


def scan_file(rel_path, full, card, id_by_path, files, old_root, root_pkg=PACKAGE):
    """檢查單一檔案；回傳 (findings, imported_paths(set), edges list)。"""
    findings = []
    path_disp = f"{root_pkg}/{rel_path}"
    try:
        with open(full, encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src, filename=path_disp)
    except (OSError, SyntaxError, UnicodeDecodeError) as e:
        return [Finding("VIOLATION", "PARSE", path_disp, f"無法解析：{e}")], set(), []
    layer = rel_path.split("/")[0]
    cid = card["id"] if card else None
    dotted_to_path = {dotted_of(p, root_pkg): p for p in files}
    imported = set()
    json_aliases, json_dumps_names = set(), set()

    for base, cands, lineno in _imports(tree, rel_path, root_pkg):
        if base is None:
            findings.append(Finding("VIOLATION", "LAYER_DEP", path_disp, "相對 import 超出套件範圍", lineno))
            continue
        top = base.split(".")[0]
        if top == root_pkg:
            targets = [dotted_to_path[c] for c in cands if c in dotted_to_path]
            if not targets and base in dotted_to_path:
                targets = [dotted_to_path[base]]
            for t in targets:
                imported.add((t, lineno))
            # 沒有對到檔案的 import（例如 package 本身）：只檢查層名是否合法
            parts = base.split(".")
            if len(parts) >= 2 and not targets and parts[1] not in LAYERS:
                findings.append(Finding("VIOLATION", "LAYER_DEP", path_disp,
                                        f"import {base}：不是已登記的層", lineno))
            continue
        # 非本套件
        if top in old_root:
            findings.append(Finding("VIOLATION", "OLD_ROOT_IMPORT", path_disp,
                                    f"import repo 根目錄舊模組 {top}（{base}）", lineno))
        if top == "gspread" and cid != GSPREAD_ALLOWED_ID:
            findings.append(Finding("VIOLATION", "GSPREAD_EXIT", path_disp,
                                    "gspread 只能在 infra/store/gsheets.py import", lineno))
        if layer in PURE_LAYERS:
            names = [base] + cands
            if top in IO_ROOTS or any(n == d or n.startswith(d + ".") for n in names for d in IO_DOTTED):
                findings.append(Finding("VIOLATION", "PURE_LAYER_IO", path_disp,
                                        f"{layer} 層不可 import {base}（有 IO）", lineno))

    # 其他 AST 規則
    doc_ids = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "json":
                    json_aliases.add(a.asname or "json")
        elif isinstance(node, ast.ImportFrom) and node.module == "json" and not node.level:
            for a in node.names:
                if a.name == "dumps":
                    json_dumps_names.add(a.asname or "dumps")
                    if cid != FORMAT_ALLOWED_ID:
                        findings.append(Finding("VIOLATION", "FORMAT_EXIT", path_disp,
                                                "from json import dumps：json.dumps 只能在 serialize", node.lineno))
        if layer == "common" and isinstance(node, ast.ImportFrom) and node.module == "os" and not node.level:
            for a in node.names:
                if a.name in ("environ", "getenv", "putenv"):
                    findings.append(Finding("VIOLATION", "ENV_IN_COMMON", path_disp,
                                            f"common 不可讀環境變數（from os import {a.name}）", node.lineno))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if layer == "common" and isinstance(node.value, ast.Name) and node.value.id == "os" \
                    and node.attr in ("environ", "getenv", "putenv"):
                findings.append(Finding("VIOLATION", "ENV_IN_COMMON", path_disp,
                                        f"common 不可讀環境變數（os.{node.attr}）", node.lineno))
            if cid != FORMAT_ALLOWED_ID:
                if node.attr in FORMAT_ATTRS:
                    findings.append(Finding("VIOLATION", "FORMAT_EXIT", path_disp,
                                            f".{node.attr}：格式化只能在 serialize", node.lineno))
                elif node.attr == "dumps" and isinstance(node.value, ast.Name) \
                        and node.value.id in json_aliases:
                    findings.append(Finding("VIOLATION", "FORMAT_EXIT", path_disp,
                                            "json.dumps 只能在 serialize", node.lineno))
        elif isinstance(node, ast.Call) and cid != FORMAT_ALLOWED_ID \
                and isinstance(node.func, ast.Name) and node.func.id in json_dumps_names:
            findings.append(Finding("VIOLATION", "FORMAT_EXIT", path_disp,
                                    "dumps()（來自 json）只能在 serialize", node.lineno))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in doc_ids and cid not in TRIBE_ALLOWED_IDS:
            m = TRIBE_RE.search(node.value.lower())
            if m:
                findings.append(Finding("VIOLATION", "TRIBE_STRING", path_disp,
                                        f"種族名稱字串 {m.group(0)!r}：種族資料只能經 tribe_data", node.lineno))
    return findings, imported, []


def run_checks(root, manifest, expected_count=None, expect_wp=(), strict=False, package=PACKAGE):
    findings = check_manifest(manifest, expected_count)
    by_path = {c["path"]: c for c in manifest}
    id_by_path = {c["path"]: c["id"] for c in manifest}
    base = os.path.join(root, package)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"找不到套件目錄 {base}")
    files = list_package_files(root, package)
    old_root = list_old_root_modules(root, package)

    for p in sorted(files):
        if p not in by_path:
            findings.append(Finding("VIOLATION", "UNREGISTERED", f"{package}/{p}",
                                    "檔案沒有登記在 tools/arch_manifest.py（§4.2 沒有這張卡片）"))
    for c in manifest:
        wps = {w.strip() for w in c["wp"].split("／")}
        if c["path"] not in files and any(w in wps for w in expect_wp):
            findings.append(Finding("VIOLATION", "MISSING_FILE", f"{package}/{c['path']}",
                                    f"{c['id']} 應由 {'／'.join(sorted(w for w in expect_wp if w in wps))} 交付但檔案不存在"))

    graph = {}
    for p, full in sorted(files.items()):
        card = by_path.get(p)
        f, imported, _ = scan_file(p, full, card, id_by_path, files, old_root, package)
        findings.extend(f)
        graph.setdefault(p, set())
        for t, lineno in sorted(imported):
            if t == p:
                continue
            graph[p].add(t)
            if not pair_allowed(p, t):
                sl, dl = p.split("/")[0], t.split("/")[0]
                why = "同層互相 import" if sl == dl else f"{sl} 不可 import {dl}"
                if sl == dl == "infra":
                    why = "infra 只有 infra/store/* 內部可互依"
                findings.append(Finding("VIOLATION", "LAYER_DEP", f"{package}/{p}",
                                        f"{why}：{p} → {t}", lineno))
            if card and t in id_by_path and id_by_path[t] not in card["deps"]:
                findings.append(Finding("VIOLATION" if strict else "WARN", "UNDECLARED_DEP",
                                        f"{package}/{p}",
                                        f"import {t}（{id_by_path[t]}）不在 {card['id']} 的「依賴」欄", lineno))
    for comp in _sccs({k: sorted(v) for k, v in graph.items()}):
        if len(comp) > 1:
            first = sorted(comp)[0]
            findings.append(Finding("VIOLATION", "CYCLE", f"{package}/{first}",
                                    "import 循環：" + " ↔ ".join(sorted(comp))))
    findings.sort(key=Finding.key)
    return findings, len(files)


# --------------------------------------------------------------------------- CLI

def _dumps_stable(root):
    sys.path.insert(0, root)
    try:
        from travian_bot.common.serialize import dumps_stable   # noqa: WPS433
    except Exception as e:   # 缺檔或介面不同：視為輸入錯誤
        raise RuntimeError(f"--json 需要 travian_bot.common.serialize.dumps_stable：{e}")
    return dumps_stable


def main(argv=None):
    ap = argparse.ArgumentParser(description="架構檢查（slice §4.1）")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="repo 根目錄（預設＝tools/ 的上一層）")
    ap.add_argument("--manifest", default=None, help="arch_manifest.py 路徑（預設同目錄）")
    ap.add_argument("--expect-wp", default="", help="逗號分隔；這些 WP 的檔案必須存在，例 A1a-1,A1a-2")
    ap.add_argument("--strict", action="store_true", help="UNDECLARED_DEP 也算違規")
    ap.add_argument("--json", action="store_true", help="以 dumps_stable 輸出 JSON")
    ap.add_argument("--version", action="version", version=f"check_arch {VERSION}")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    root = os.path.abspath(args.root)
    try:
        manifest, expected = load_manifest(args.manifest)
        expect_wp = [w.strip() for w in args.expect_wp.split(",") if w.strip()]
        findings, nfiles = run_checks(root, manifest, expected, expect_wp, args.strict)
        dumps = _dumps_stable(root) if args.json else None
    except (OSError, RuntimeError, SyntaxError, KeyError) as e:
        print(f"ERROR｜{e}", file=sys.stderr)
        return 2
    viol = [f for f in findings if f.kind == "VIOLATION"]
    warns = [f for f in findings if f.kind == "WARN"]
    if args.json:
        sys.stdout.write(dumps({"ok": not viol, "files_checked": nfiles, "manifest_cards": len(manifest),
                                "violations": [f.as_dict() for f in viol],
                                "warnings": [f.as_dict() for f in warns]}))
    else:
        for f in findings:
            print(f.text())
    print(f"check_arch {VERSION}：{'通過' if not viol else '失敗'}｜違規 {len(viol)}｜警告 {len(warns)}"
          f"｜檢查檔案 {nfiles}｜卡片 {len(manifest)}", file=sys.stderr)
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main())
