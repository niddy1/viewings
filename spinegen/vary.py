"""Give an older shelf the 2026 shelf's spread of placements (see CLAUDE.md, "Target mix").
    python3 vary.py 2017 [2018 ...]
Rewrites the std(...) specs of those shelves in spinegen/tapes.py in place:
  - pictures: about 13% moved under the title; shapes varied (ar) and crops enlarged, kept clear of the title boxes
  - lines under the title: cast lines kept on ~8% (oldest films first), director lines capped at ~28%
  - stickers: ~27% of tapes, dot/rewind/barcode/price ~ 38/25/25/12, about a third of the dots at the top,
    spread out so neighbours differ; format markers (2-TAPE SET, BOX SET) and stickers laid in `over` are kept
  - foot styles mixed; a little layout variety (gap/rule) on the plainest tapes
"""
import ast, json, re, sys, glob
import os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
F = R + 'spinegen/tapes.py'
DIR = re.compile(r"(^(A|AN) .+ (FILM|PICTURE|JOINT)$)|FILM BY|FILME DE|FILM DE|FILM AV|FILM VON|PELÍCULA DE|DIRECTED BY|DOCUMENTARY BY|\b(A|AN) [A-ZÀ-Ž'. -]+ (FILM|JOINT)\b")
GEN = re.compile(r"^(A|AN) (COMEDY|DOCUMENTARY|TV SPECIAL|NETFLIX DOCUMENTARY|TRUE-CRIME DOCUMENTARY|LIFETIME ORIGINAL MOVIE|KNIVES OUT MYSTERY)$")
OTHER = re.compile(r"COMPLETE|SERIE|DUBBED|ADULTS|PLAY BY|SAGA|STAND-UP")
FORMAT = re.compile(r"TWOST|BOX', 'SET|2-TAPE")
GWORD = {'Drama': 'DRAMA', 'Comedy': 'COMEDY', 'Horror': 'HORROR', 'Thriller': 'THRILLER', 'Crime': 'CRIME',
         'Action': 'ACTION', 'Documentary': 'DOCUMENTARY', 'Romance': 'ROMANCE', 'Science Fiction': 'SCI-FI',
         'Mystery': 'MYSTERY', 'Animation': 'ANIMATION', 'War': 'WAR', 'Western': 'WESTERN', 'Music': 'MUSIC',
         'Family': 'FAMILY', 'Fantasy': 'FANTASY', 'Adventure': 'ADVENTURE', 'History': 'DRAMA'}
FEET = ['a', 'b', 'e', 'a', 'b', 'c', 'b', 'a', 'd']
ARS = [1.4, .6, 1.1, .85, 1.6, .5, 1.2, 1.0, .75, 1.3, .9, .45, 1.15, 1.7, .65, 1.25, .8, 1.05]
EXTRA = ['LgPTF', 'LPgTF', 'L-PTF']
DOTC = [((200, 40, 40), WHT := (246, 243, 234)), ((40, 110, 150), WHT), ((250, 206, 40), (30, 30, 34)), ((30, 30, 34), WHT),
        ((220, 60, 100), WHT), ((60, 150, 80), WHT), ((236, 130, 40), (30, 20, 10))]
LBL = [((214, 200, 168), (52, 46, 40)), ((232, 228, 214), (40, 40, 44)), ((250, 214, 60), (30, 24, 20)),
       ((214, 230, 214), (30, 60, 40)), ((250, 214, 220), (120, 20, 50)), ((220, 236, 250), (20, 40, 80))]
RWDC = ["RWD()", "RWD(fill=(250, 226, 60))", "RWD(fill=(250, 200, 220), ink=(110, 20, 60))", "RWD(fill=(236, 122, 40), ink=(20, 16, 12))"]


def cls(lines):
    s = ' '.join(lines)
    if GEN.match(s): return 'generic'
    if DIR.search(s): return 'dir'
    if OTHER.search(s): return 'other'
    return 'cast'


def crop(cx, cy, w, ar):
    h = w * ar * 780 / 1170
    x0 = min(max(0, cx - w / 2), 1 - w); y0 = min(max(0, cy - h / 2), 1 - h)
    return x0, y0, x0 + w, y0 + h, h


def clear(b, boxes, m=.01):
    return all(b[2] <= t[0] - m or b[0] >= t[2] + m or b[3] <= t[1] - m or b[1] >= t[3] + m for t in boxes)


def new_photo(old, boxes, i):
    cx, cy, w = old[:3]; ar0 = old[3] if len(old) > 3 else 1.0
    for k in range(len(ARS)):
        ar = ARS[(i + k) % len(ARS)]
        for ww in (min(1.0, max(.5, w * 1.5)), min(1.0, max(.45, w * 1.2)), w):
            if ww * ar * 780 / 1170 > .95: continue
            for dy in (0, -.05, .05, -.1, .1, -.15, .15, -.2, .2):
                b = crop(cx, cy + dy, ww, ar)
                if clear(b, boxes): return (round(cx, 3), round(cy + dy, 3), round(ww, 3), ar)
    return tuple(old[:3]) + (ar0,)


def run(year):
    src = open(F).read(); tree = ast.parse(src)
    p = R + ('films.json' if year == 2026 else f'films-{year}.json')
    films = [f for f in json.load(open(p))['films'] if f.get('poster')]
    meta = {f['poster'].split('/')[-1][:-4]: f for f in films}
    ids = list(meta)
    calls = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'std' and node.args \
                and isinstance(node.args[0], ast.Constant) and node.args[0].value in meta:
            calls[node.args[0].value] = node
    seq = [k for k in ids if k in calls]; n = len(ids)
    seg = lambda x: ast.get_source_segment(src, x)
    T = {}
    for k in seq:
        node = calls[k]
        kw = {}
        for a in node.keywords:
            kw[a.arg if a.arg else '**' + seg(a.value)] = seg(a.value)
        o = ast.literal_eval(kw.get('order', "'LPTF'"))
        title = seg(node.args[3]) if len(node.args) > 3 else ''
        boxes = [tuple(float(x) for x in m.groups()) for m in re.finditer(r'\(([01]?\.?\d*), ([01]?\.?\d*), ([01]?\.?\d*), ([01]?\.?\d*)\)', title)
                 if all(m.groups())]
        boxes = [b for b in boxes if all(0 <= v <= 1 for v in b) and b[2] > b[0] and b[3] > b[1]]
        cred = ast.literal_eval(kw['credit']) if kw.get('credit', 'None').startswith('[') else None
        st = kw.get('stick', '')
        T[k] = dict(node=node, kw=kw, o=o, boxes=boxes, cred=cred, ctype=cls(cred) if cred and 'C' in o else None,
                    fixed=bool(FORMAT.search(st)) or 'over' in kw, year=meta[k].get('year') or year,
                    genre=next((GWORD[g] for g in meta[k].get('genres', []) if g in GWORD), 'DRAMA'))
    m = len(seq)
    # ---- lines under the title
    casts = sorted([k for k in seq if T[k]['ctype'] == 'cast'], key=lambda k: T[k]['year'])
    keep_cast = set(casts[:round(.08 * n)])
    dirs = [k for k in seq if T[k]['ctype'] == 'dir']
    cap = round(.28 * n)
    keep_dir = set(dirs[::max(1, len(dirs) / cap)] if False else [dirs[round(i * len(dirs) / cap)] for i in range(min(cap, len(dirs)))])
    for k in seq:
        t = T[k]
        if t['ctype'] == 'cast' and k not in keep_cast or t['ctype'] == 'dir' and k not in keep_dir:
            t['o'] = t['o'].replace('C', ''); t['kw'].pop('credit', None); t['kw'].pop('ccol', None)
    # ---- pictures under the title: ~13%, spread out
    cand = [k for k in seq if 'P' in t_o(T, k) and 'T' in t_o(T, k) and 'p' not in t_o(T, k) and t_o(T, k).index('P') < t_o(T, k).index('T')
            and 'dotst' not in T[k]['kw']]
    nb = round(.13 * n); bottom = set()
    if cand and nb:
        step = len(cand) / nb
        bottom = {cand[int(step * i + step / 2)] for i in range(nb)}
    for k in bottom:
        o = T[k]['o'].replace('P', '', 1); i = o.index('T') + 1; T[k]['o'] = o[:i] + 'P' + o[i:]
    # ---- picture shapes
    for i, k in enumerate(seq):
        mm = re.match(r'ph\(([^)]*)\)$', T[k]['kw'].get('photo', '') or '')
        if mm:
            old = [float(x) for x in mm.group(1).split(',')]
            T[k]['kw']['photo'] = 'ph(%s)' % ', '.join(str(x) for x in new_photo(old, T[k]['boxes'], i * 7 + year))
    # ---- stickers
    for k in seq:  # clear the free stickers; format markers and `over` stickers stay
        t = T[k]
        if not t['fixed']:
            t['kw'].pop('stick', None); t['kw'].pop('dotst', None); t['o'] = t['o'].replace('S', '')
    fixed = [k for k in seq if T[k]['fixed']]
    target = max(0, round(.27 * n) - len(fixed))
    free = [k for k in seq if not T[k]['fixed']]
    picks = []
    if target:
        step = len(free) / target
        picks = [free[int(step * i + step / 2)] for i in range(target)]
    nd = round(.38 * target) - len(fixed); nr = round(.25 * target); nbar = round(.25 * target)
    npr = target - max(0, nd) - nr - nbar
    types = []
    pools = {'dot': max(0, nd), 'rewind': nr, 'barcode': nbar, 'price': max(0, npr)}
    order = ['dot', 'barcode', 'rewind', 'price', 'dot', 'rewind', 'barcode', 'dot']
    j = 0
    while len(types) < len(picks):
        tname = order[j % len(order)]; j += 1
        if pools[tname] > 0: types.append(tname); pools[tname] -= 1
        if j > 1000: types.append('dot')
    # older films get the labels and price tags where possible
    olds = sorted(range(len(picks)), key=lambda i: T[picks[i]]['year'])
    lab = sorted([i for i, x in enumerate(types) if x in ('barcode', 'price')])
    # swap label types onto the older picks while keeping the spacing pattern
    want = set(olds[:len(lab)])
    labtypes = [types[i] for i in lab]; others = [types[i] for i in range(len(types)) if i not in lab]
    types2 = []
    for i in range(len(picks)):
        types2.append(labtypes.pop(0) if i in want and labtypes else (others.pop(0) if others else labtypes.pop(0)))
    types = types2
    # no same type on neighbours (adjacent shelf slots)
    pos = {k: i for i, k in enumerate(ids)}
    for i in range(1, len(picks)):
        if types[i] == types[i - 1] and pos[picks[i]] - pos[picks[i - 1]] == 1 and i + 1 < len(picks):
            types[i], types[i + 1] = types[i + 1], types[i]
    ndot = 0
    for i, (k, ty) in enumerate(zip(picks, types)):
        t = T[k]; g = t['genre']; c = 10000 + (i * 7919 + year) % 89999
        if ty == 'dot':
            ndot += 1
            new = t['year'] >= year - 1
            text = ['NEW', 'RELEASE'] if new and ndot % 3 == 1 else (['STAFF', 'PICK'] if ndot % 3 == 2 else [g])
            fill, ink = DOTC[(i + year) % len(DOTC)]
            top = 'P' in t['o'] and 'T' in t['o'] and t['o'].index('P') < t['o'].index('T') and ndot % 2 == 1
            if top:
                t['kw']['dotst'] = repr((text, fill, ink))
                continue
            t['kw']['stick'] = f"flow(dot, 70, {text!r}, {fill}, {ink}, d=62)"
        elif ty == 'rewind':
            t['kw']['stick'] = RWDC[(i + year) % len(RWDC)]
        elif ty == 'barcode':
            fill, ink = LBL[(i + year) % len(LBL)]
            t['kw']['stick'] = f"BAR('{c // 1000} {c % 1000:03d}{i}', top='{g}', fill={fill}, ink={ink})"
        else:
            t['kw']['stick'] = f"PRC([{['$0.99', '$1.99', '$2.99', '$3.99'][(i + year) % 4]!r}, {g!r}])"
        t['o'] = t['o'].replace('F', 'SF') if 'F' in t['o'] else t['o'] + 'S'
    # ---- feet and a little layout variety
    plain = 0
    for i, k in enumerate(seq):
        t = T[k]
        if t['o'] == 'LPTF':
            plain += 1
            if plain % 3 == 0: t['o'] = EXTRA[(plain // 3) % 3]
        t['kw']['order'] = repr(t['o'])
        t['kw']['ft'] = repr(FEET[(i + year) % len(FEET)])
    # ---- write back (byte offsets)
    b = src.encode(); lines = b.splitlines(keepends=True); offs = [0]
    for l in lines: offs.append(offs[-1] + len(l))
    edits = []
    for k in seq:
        node = calls[k]; kw = T[k]['kw']
        head = ', '.join(seg(a) for a in node.args[:3]) + ','
        title = seg(node.args[3]) if len(node.args) > 3 else None
        parts = [(a if a.startswith('**') else f'{a}={v}') for a, v in kw.items()]
        out = 'std(' + head + '\n' + ('    ' + title + ',\n' if title else '')
        line = '    '
        for p_ in parts:
            if len(line) + len(p_) > 128 and line.strip(): out += line.rstrip() + '\n'; line = '    '
            line += p_ + ', '
        out += line.rstrip().rstrip(',') + ')'
        s = offs[node.lineno - 1] + node.col_offset; e = offs[node.end_lineno - 1] + node.end_col_offset
        edits.append((s, e, out))
    for s, e, out in sorted(edits, reverse=True): b = b[:s] + out.encode() + b[e:]
    open(F, 'wb').write(b)
    ast.parse(open(F).read())
    print(year, len(seq), 'specs rewritten; bottom pictures', len(bottom), 'stickers', len(picks) + len(fixed))


def t_o(T, k): return T[k]['o']


if __name__ == '__main__':
    for y in sys.argv[1:]: run(int(y))
