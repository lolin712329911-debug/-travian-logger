"""check_contracts.py  v0.1  (A1a-3)

用途：契約檢查（slice §6.6 的自動化）。WP 驗收必跑。
檢查項（規則名稱 → 說明）：
  NO_CLASS / NO_SPEC      schema.CONTRACT_SPECS 與 models.CONTRACT_CLASSES 的契約名必須一一對應
                          （唯一例外：表格型契約 VillageSettingsTable，沒有 dataclass，改查 validate_village_table）
  SPEC_FIELDS             dataclass 欄位集合 ≠ spec 欄位集合
  SPEC_NULLABLE           spec 可為 null ↔ dataclass 型別是否 Optional 不一致
  SPEC_KIND               dataclass 型別與 spec 型別種類不相容（int／float／str／bool／資源×4／list／dict／struct）
  EXAMPLE_COVERAGE        每個契約至少一個合規與一個不合規範例
  VALID_REJECTED          合規範例被 schema.validate 擋下
  INVALID_PASSED          不合規範例沒有被擋、或錯誤清單不含預期的 (field, rule)
  ROUNDTRIP_DICT          合規範例 from_dict → to_dict 與原資料不一致（或建出來後驗證不過）
  INVALID_BUILT           不合規範例用 from_dict 竟然建得出來，或丟出的 ValidationError 不含預期 (field, rule)
  ROUNDTRIP_ROW           有 to_row／from_row 的結構：from_row(to_row(x)) ≠ x，或欄數 ≠ COLUMNS
  FILE_MISSING／FILE_STALE／FILE_EXTRA
                          tests/contracts/{契約名}.valid.json／.invalid.json 與 schema.contract_examples() 產生的內容不符
                          （這些檔案由本工具產生，不得手改；用 --write 重新產生）
檔名說明：卡片寫 `{CID}.valid.json`，本版 CID 取「契約名」（例 VillageRef.valid.json），
          因為 C9 底下有三個結構、C12 有子結構，用 C1～C12 編號會對不上。要改請回報。
檔案內容：dumps_stable 的 JSON，頂層 {schema_version, contract, kind, cases}；cases 的每項有 data、ctx
          （ctx 內的集合如 tribes／action_names 存成排序後的 list，讀回時由 load_cases 還原成 set）。

用法：python tools/check_contracts.py [--root DIR] [--write] [--json]
輸出：每行 `VIOLATION｜規則｜契約或路徑｜細節`；exit 0＝通過、1＝有違規、2＝用法或輸入錯誤。
依賴：標準庫＋ travian_bot.common（schema、models、serialize）。
部署狀態：僅開發／CI 用，不在 bot 執行路徑上。
"""
import argparse
import os
import sys
import typing

VERSION = "0.1"
SET_CTX_KEYS = ("tribes", "action_names")     # contract_examples 的 ctx 中型別為集合的鍵
FILE_SCHEMA_VERSION = 1
TABLE_CONTRACT = "VillageSettingsTable"


class Finding:
    def __init__(self, rule, where, detail):
        self.rule, self.where, self.detail = rule, where, detail

    def key(self):
        return (self.rule, self.where, self.detail)

    def text(self):
        return f"VIOLATION｜{self.rule}｜{self.where}｜{self.detail}"

    def as_dict(self):
        return {"rule": self.rule, "where": self.where, "detail": self.detail}


# --------------------------------------------------------------------------- 型別比對

def _unwrap_optional(hint):
    if typing.get_origin(hint) is typing.Union:
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        opt = len(args) != len(typing.get_args(hint))
        return (args[0] if len(args) == 1 else typing.Union[tuple(args)]), opt
    return hint, False


def _kind_problem(spec, hint, classes):
    """回傳不相容說明，相容回 None。hint 已去掉 Optional。"""
    t = spec["t"]
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if t == "any":
        return None
    if t == "int":
        return None if hint is int else f"spec=int，型別={hint}"
    if t == "float":
        return None if hint in (float, int) else f"spec=float，型別={hint}"
    if t in ("str", "enum", "utc"):
        return None if hint is str else f"spec={t}，型別={hint}"
    if t == "bool":
        return None if hint is bool else f"spec=bool，型別={hint}"
    if t == "res4":
        ok = origin is tuple and args == (int, int, int, int)
        return None if ok else f"spec=資源×4，型別={hint}（應為 Tuple[int,int,int,int]）"
    if t == "dict":
        return None if origin is dict or hint is dict else f"spec=dict，型別={hint}"
    if t == "struct":
        cls = classes.get(spec["name"])
        return None if cls is not None and hint is cls else f"spec=struct {spec['name']}，型別={hint}"
    if t == "list":
        if origin not in (tuple, list):
            return f"spec=list，型別={hint}"
        item = spec["item"]
        elem = args[0] if args else None
        if item["t"] == "struct":
            cls = classes.get(item["name"])
            return None if cls is not None and elem is cls else f"list 元素應為 {item['name']}，型別={hint}"
        if item["t"] == "int":
            return None if elem is int else f"list 元素應為 int，型別={hint}"
        return None
    return f"未知 spec 種類 {t}"


# --------------------------------------------------------------------------- 範例檔

def _jsonable_ctx(ctx):
    return {k: (sorted(v) if isinstance(v, (set, frozenset)) else v) for k, v in (ctx or {}).items()}


def _restore_ctx(ctx):
    return {k: (set(v) if k in SET_CTX_KEYS and isinstance(v, list) else v) for k, v in (ctx or {}).items()}


def load_cases(doc):
    """把範例檔（已 json 解析）的 cases 還原成 [{data, ctx, field?, rule?}]，ctx 的集合還原成 set。"""
    out = []
    for c in doc["cases"]:
        c = dict(c)
        c["ctx"] = _restore_ctx(c.get("ctx"))
        out.append(c)
    return out


def build_example_files(examples):
    """{檔名: 文字內容}。檔名＝契約名＋.valid.json／.invalid.json；內容用 serialize.dumps_stable。"""
    from travian_bot.common.serialize import dumps_stable
    files = {}
    for name in sorted(examples):
        for kind in ("valid", "invalid"):
            cases = []
            for c in examples[name][kind]:
                item = {"data": c["data"], "ctx": _jsonable_ctx(c.get("ctx"))}
                if kind == "invalid":
                    item["field"], item["rule"] = c["field"], c["rule"]
                cases.append(item)
            files[f"{name}.{kind}.json"] = dumps_stable(
                {"schema_version": FILE_SCHEMA_VERSION, "contract": name, "kind": kind, "cases": cases})
    return files


# --------------------------------------------------------------------------- 檢查

def _errs(errors):
    return {(e.field, e.rule) for e in errors}


def check_specs_vs_classes(specs, classes):
    out = []
    for name in sorted(specs):
        if "table" in specs[name]:
            continue
        if name not in classes:
            out.append(Finding("NO_CLASS", name, "schema 有此契約，但 models 沒有對應的 dataclass"))
    for name in sorted(classes):
        if name not in specs:
            out.append(Finding("NO_SPEC", name, "models 有此 dataclass，但 schema.CONTRACT_SPECS 沒有規格"))
    for name in sorted(set(specs) & set(classes)):
        spec, cls = specs[name], classes[name]
        if "fields" not in spec:
            continue
        try:
            hints = typing.get_type_hints(cls)
        except Exception as e:                       # 型別解析失敗也是問題
            out.append(Finding("SPEC_KIND", name, f"無法解析型別註記：{type(e).__name__}"))
            continue
        import dataclasses
        names = [f.name for f in dataclasses.fields(cls)]
        miss = sorted(set(spec["fields"]) - set(names))
        extra = sorted(set(names) - set(spec["fields"]))
        if miss or extra:
            out.append(Finding("SPEC_FIELDS", name, f"spec 有但 dataclass 沒有：{miss}；dataclass 有但 spec 沒有：{extra}"))
        for fname in names:
            fs = spec["fields"].get(fname)
            if fs is None:
                continue
            base, opt = _unwrap_optional(hints[fname])
            if bool(fs.get("null")) != opt:
                out.append(Finding("SPEC_NULLABLE", f"{name}.{fname}",
                                   f"spec null={bool(fs.get('null'))}，型別 Optional={opt}"))
            prob = _kind_problem(fs, base, classes)
            if prob:
                out.append(Finding("SPEC_KIND", f"{name}.{fname}", prob))
    return out


def check_examples(specs, classes, examples, models_mod, validate):
    out = []
    for name in sorted(specs):
        ex = examples.get(name)
        if not ex or not ex.get("valid") or not ex.get("invalid"):
            out.append(Finding("EXAMPLE_COVERAGE", name, "缺合規或不合規範例"))
    for name in sorted(examples):
        if name not in specs:
            out.append(Finding("EXAMPLE_COVERAGE", name, "範例對應的契約不在 CONTRACT_SPECS"))
    for name in sorted(set(examples) & set(specs)):
        cls = classes.get(name)
        for i, c in enumerate(examples[name].get("valid", [])):
            where = f"{name}.valid[{i}]"
            errs = validate(name, c["data"], c.get("ctx") or None)
            if errs:
                out.append(Finding("VALID_REJECTED", where, "；".join(str(e) for e in errs[:3])))
                continue
            _roundtrip(name, cls, c, where, models_mod, out)
        for i, c in enumerate(examples[name].get("invalid", [])):
            where = f"{name}.invalid[{i}]"
            want = (c["field"], c["rule"])
            errs = validate(name, c["data"], c.get("ctx") or None)
            if want not in _errs(errs):
                out.append(Finding("INVALID_PASSED", where, f"預期 {want}，實際 {sorted(_errs(errs))}"))
            if cls is not None and isinstance(c["data"], dict):
                try:
                    cls.from_dict(c["data"], c.get("ctx") or None)
                except models_mod.ValidationError as e:
                    if want not in _errs(getattr(e, "all", [e])):
                        out.append(Finding("INVALID_BUILT", where, f"from_dict 的錯誤不含 {want}"))
                else:
                    out.append(Finding("INVALID_BUILT", where, "from_dict 竟然建得出物件"))
    return out


def _roundtrip(name, cls, case, where, models_mod, out):
    data, ctx = case["data"], case.get("ctx") or None
    if name == TABLE_CONTRACT:
        try:
            rows = [models_mod.VillageSettingsRow.from_dict(r, ctx) for r in data]
            errs = models_mod.validate_village_table(rows, ctx)
        except models_mod.ValidationError as e:
            out.append(Finding("ROUNDTRIP_DICT", where, f"建構失敗：{e}"))
            return
        if errs:
            out.append(Finding("ROUNDTRIP_DICT", where, f"validate_village_table 擋下合規範例：{errs[0]}"))
        return
    if cls is None:
        return
    try:
        obj = cls.from_dict(data, ctx)
    except models_mod.ValidationError as e:
        out.append(Finding("ROUNDTRIP_DICT", where, f"from_dict 失敗：{e}"))
        return
    if obj.to_dict() != data:
        out.append(Finding("ROUNDTRIP_DICT", where, "from_dict→to_dict 與原資料不一致"))
    errs = obj.validate(ctx)
    if errs:
        out.append(Finding("ROUNDTRIP_DICT", where, f"建出的物件驗證不過：{errs[0]}"))
    if hasattr(cls, "to_row") and hasattr(cls, "from_row"):
        try:
            cells = obj.to_row(ctx)
            back = cls.from_row(cells, ctx)
        except models_mod.ValidationError as e:
            out.append(Finding("ROUNDTRIP_ROW", where, f"to_row／from_row 失敗：{e}"))
            return
        if len(cells) != len(cls.COLUMNS):
            out.append(Finding("ROUNDTRIP_ROW", where, f"欄數 {len(cells)} ≠ COLUMNS {len(cls.COLUMNS)}"))
        if back != obj:
            out.append(Finding("ROUNDTRIP_ROW", where, "from_row(to_row(x)) ≠ x"))


def check_files(root, examples, write=False):
    out = []
    folder = os.path.join(root, "tests", "contracts")
    want = build_example_files(examples)
    if write:
        os.makedirs(folder, exist_ok=True)
        for fn, text in want.items():
            with open(os.path.join(folder, fn), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        for fn in os.listdir(folder):
            if fn.endswith(".valid.json") or fn.endswith(".invalid.json"):
                if fn not in want:
                    os.remove(os.path.join(folder, fn))
    have = {}
    if os.path.isdir(folder):
        for fn in os.listdir(folder):
            if fn.endswith(".valid.json") or fn.endswith(".invalid.json"):
                with open(os.path.join(folder, fn, ), encoding="utf-8", newline="") as fh:
                    have[fn] = fh.read()
    for fn in sorted(want):
        path = f"tests/contracts/{fn}"
        if fn not in have:
            out.append(Finding("FILE_MISSING", path, "範例檔不存在（用 --write 產生）"))
        elif have[fn] != want[fn]:
            out.append(Finding("FILE_STALE", path, "內容與 schema.contract_examples() 不符（不得手改；用 --write 重新產生）"))
    for fn in sorted(set(have) - set(want)):
        out.append(Finding("FILE_EXTRA", f"tests/contracts/{fn}", "沒有對應的契約範例"))
    return out


def run_checks(root, write=False, mods=None):
    """mods＝(schema, models) 注入用（測試）；預設從 travian_bot.common 匯入。"""
    if mods is None:
        sys.path.insert(0, root)
        from travian_bot.common import models, schema   # noqa: WPS433
    else:
        schema, models = mods
    findings = check_specs_vs_classes(schema.CONTRACT_SPECS, models.CONTRACT_CLASSES)
    examples = schema.contract_examples()
    findings += check_examples(schema.CONTRACT_SPECS, models.CONTRACT_CLASSES, examples, models, schema.validate)
    findings += check_files(root, examples, write=write)
    findings.sort(key=Finding.key)
    return findings, len(schema.CONTRACT_SPECS), sum(len(v["valid"]) + len(v["invalid"]) for v in examples.values())


def main(argv=None):
    ap = argparse.ArgumentParser(description="契約檢查（slice §6.6）")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="repo 根目錄（預設＝tools/ 的上一層）")
    ap.add_argument("--write", action="store_true", help="重新產生 tests/contracts/*.json 後再檢查")
    ap.add_argument("--json", action="store_true", help="以 dumps_stable 輸出 JSON")
    ap.add_argument("--version", action="version", version=f"check_contracts {VERSION}")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    root = os.path.abspath(args.root)
    try:
        findings, ncontracts, ncases = run_checks(root, write=args.write)
    except (ImportError, OSError) as e:
        print(f"ERROR｜{e}", file=sys.stderr)
        return 2
    if args.json:
        from travian_bot.common.serialize import dumps_stable
        sys.stdout.write(dumps_stable({"ok": not findings, "contracts": ncontracts, "cases": ncases,
                                       "violations": [f.as_dict() for f in findings]}))
    else:
        for f in findings:
            print(f.text())
    print(f"check_contracts {VERSION}：{'通過' if not findings else '失敗'}｜違規 {len(findings)}"
          f"｜契約 {ncontracts}｜範例 {ncases}", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
