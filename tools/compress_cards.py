import re, sys, json
src = open('/mnt/user-data/uploads/multi-village-dev-v0_10.md', encoding='utf-8').read()
# isolate section 4.2 up to "#### tools/"
start = src.index('### 4.2 檔案卡片')
end = src.index('#### tools/、tests/、其他')
sec = src[start:end]

rows = []   # (layer_heading, cells)
heading = None
for line in sec.splitlines():
    if line.startswith('#### '):
        heading = line[5:].strip()
    elif re.match(r'\| (cm|ps|dm|if|ac|ap)-\d+ \|', line):
        cells = [c.strip() for c in line.strip().strip('|').split(' | ')]
        # cells may contain '|' escaped? check count
        rows.append((heading, cells))

bad = [(h, c[0], len(c)) for h, c in rows if len(c) != 7]
print('rows', len(rows), 'bad col counts', bad, file=sys.stderr)

# path -> id
def norm(p):
    return re.sub(r'\.py$', '', p.strip('`'))
pid = {}
for h, c in rows:
    path = norm(c[1])
    # layer prefix: file column omits layer for some? (e.g. `store/gsheets.py` inside infra)
    pid[path] = c[0]
# also allow layer-less lookup is not needed; report
unresolved = []
def conv_deps(idv, dep):
    out = []
    for tok in re.findall(r'`([^`]+)`', dep):
        t = norm(tok)
        if t in pid:
            out.append(pid[t])
        else:
            unresolved.append((idv, t))
            out.append('?' + t)
    return out

LAYER = {'cm':'common','ps':'parsers','dm':'domain','if':'infra','ac':'actions','ap':'app'}
ALLOW = {'common':{'common'}, 'parsers':{'common'}, 'domain':{'common'},
         'infra':{'common','infra'}, 'actions':{'common','parsers','infra'},
         'app':{'common','parsers','domain','infra','actions','app'}}
violations = []
cards = []
for h, c in rows:
    idv, f, content, dep, old, wp, test = c
    deps = conv_deps(idv, dep)
    for d in deps:
        if d.startswith('?'): continue
        if LAYER[d[:2]] not in ALLOW[LAYER[idv[:2]]]:
            violations.append((idv, d))
        if LAYER[d[:2]] == LAYER[idv[:2]] and LAYER[idv[:2]] not in ('common','infra','app') :
            violations.append((idv, d, 'same-layer'))
    cards.append(dict(h=h, id=idv, f=f, content=content, deps=deps, old=old, wp=wp, test=test))

# verify test column is derivable
nonderiv = []
for k in cards:
    layer = LAYER[k['id'][:2]]
    name = norm(k['f']).split('/')[-1]
    sub = norm(k['f']).split('/')[1:-1]
    exp_dir = 'tests/' + '/'.join(norm(k['f']).split('/')[:-1])
    exp = f"`{exp_dir}/test_{name}.py`"
    got = k['test'].split('（')[0].strip()
    if got != exp:
        nonderiv.append((k['id'], got, exp))
print('unresolved deps:', unresolved, file=sys.stderr)
print('layer violations:', violations, file=sys.stderr)
print('non-derivable tests:', nonderiv, file=sys.stderr)

# emit
out = []
cur = None
for k in cards:
    if k['h'] != cur:
        cur = k['h']
        out.append(f'\n**{cur}**\n')
        out.append('| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |')
        out.append('|---|---|---|---|---|---|')
    deps = '、'.join(k['deps']) if k['deps'] else '—'
    test = k['test']
    extra = ''
    m = re.search(r'（.+）$', test)
    if m and not test.startswith('`tests') is False and test.count('（'):
        extra = ' 〔測試備註：' + m.group(0).strip('（）') + '〕'
    out.append(f"| {k['id']} | {k['f']} | {k['content']} | {deps} | {k['old']} | {k['wp']}{extra} |")
open('/home/claude/cards_compressed.md','w',encoding='utf-8').write('\n'.join(out)+'\n')
print('cards', len(cards), file=sys.stderr)
