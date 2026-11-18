# Vault batch tools (run from the repo root).  python3 spinegen/vt.py <command> ...
#   sheet OUT id...                      contact sheet, posters with a 10% grid
#   measure id x0 y0 x1 y1 TEST [minf]   runs of rows where TEST passes: each lettering line's box
#   comps id x0 y0 x1 y1 TEST [minarea]  letter pieces: centre and box as poster fractions (for pick_cut/seq_cut)
#   zoom OUT id x0 y0 x1 y1              crop with a 5% grid
#   row OUT id...                        rendered spines side by side
#   audit [decade...]                    vault.py specs counted against the 2026 targets
# TEST is a Python expression on a (h, w, 3) 0-1 array `a`; _lum(a), _sat(a) are available.
import sys, json, glob, ast, collections
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

_sat = lambda a: a.max(2) - a.min(2)
_lum = lambda a: a @ np.array([.299, .587, .114], np.float32)
P = lambda i: f'posters/{i}.jpg'


def poster(i):
    return np.asarray(Image.open(P(i)).convert('RGB')).astype(np.float32) / 255


def sheet(out, *ids):
    W, H = 300, 450; cols = min(6, len(ids)); rows = (len(ids) + cols - 1) // cols
    sh = Image.new('RGB', (cols * (W + 10) + 10, rows * (H + 34) + 10), (40, 40, 40))
    for k, i in enumerate(ids):
        im = Image.open(P(i)).convert('RGB').resize((W, H)); d = ImageDraw.Draw(im)
        for g in range(1, 10):
            c = (255, 0, 255) if g == 5 else (0, 255, 255)
            d.line([(W * g / 10, 0), (W * g / 10, H)], fill=c); d.line([(0, H * g / 10), (W, H * g / 10)], fill=c)
            d.text((W * g / 10 + 2, 2), str(g), fill=(255, 255, 0)); d.text((2, H * g / 10 + 1), str(g), fill=(255, 255, 0))
        x, y = 10 + (k % cols) * (W + 10), 10 + (k // cols) * (H + 34)
        sh.paste(im, (x, y)); ImageDraw.Draw(sh).text((x, y + H + 4), i[:44], fill=(255, 255, 255))
    sh.save(out)


def measure(i, x0, y0, x1, y1, expr, mf=.03):
    x0, y0, x1, y1, mf = map(float, (x0, y0, x1, y1, mf)); A = poster(i); H, W = A.shape[:2]
    a = A[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)]
    m = eval(expr); rows = list(m.mean(1) > mf) + [False]; st = None
    for k, v in enumerate(rows):
        if v and st is None: st = k
        if not v and st is not None:
            if k - st >= 3:
                cols = np.where(m[st:k].mean(0) > .02)[0]
                print(f'rows {y0 + st / H:.3f}-{y0 + k / H:.3f}  cols {x0 + cols.min() / W:.3f}-{x0 + (cols.max() + 1) / W:.3f}')
            st = None


def comps(i, x0, y0, x1, y1, expr, mn=150):
    x0, y0, x1, y1 = map(float, (x0, y0, x1, y1)); A = poster(i); H, W = A.shape[:2]
    X0, Y0 = int(x0 * W), int(y0 * H); a = A[Y0:int(y1 * H), X0:int(x1 * W)]
    m = cv2.morphologyEx(eval(expr).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    for j in sorted(range(1, n), key=lambda j: cen[j][0]):
        if st[j, 4] < int(mn): continue
        x, y, w, h = st[j, :4]
        print(f'({(X0 + cen[j][0]) / W:.3f}, {(Y0 + cen[j][1]) / H:.3f})  area {st[j, 4]:5d}  box {(X0 + x) / W:.3f}-{(X0 + x + w) / W:.3f} x {(Y0 + y) / H:.3f}-{(Y0 + y + h) / H:.3f}')


def zoom(out, i, x0, y0, x1, y1):
    x0, y0, x1, y1 = map(float, (x0, y0, x1, y1)); im = Image.open(P(i)).convert('RGB'); W, H = im.size
    c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))); c = c.resize((800, int(c.height * 800 / c.width))); d = ImageDraw.Draw(c)
    for g in range(5, 100, 5):
        x = (g / 100 - x0) / (x1 - x0) * c.width; y = (g / 100 - y0) / (y1 - y0) * c.height; col = (255, 0, 255) if g % 10 else (0, 255, 255)
        if 0 < x < c.width: d.line([(x, 0), (x, c.height)], fill=col); d.text((x + 2, 2), str(g), fill=(255, 255, 0))
        if 0 < y < c.height: d.line([(0, y), (c.width, y)], fill=col); d.text((2, y + 2), str(g), fill=(255, 255, 0))
    c.save(out)


def row(out, *ids):
    ims = [Image.open(f'posters/{i}-spine-b.jpg').convert('RGB') for i in ids]; H = max(i.height for i in ims)
    o = Image.new('RGB', (sum(i.width + 4 for i in ims) + 4, H + 8), (70, 52, 40)); x = 4
    for im in ims: o.paste(im, (x, 4 + H - im.height)); x += im.width + 4
    o.save(out)


def audit(*want):
    dec = {}
    for p in glob.glob('vault-*.json'):
        for f in json.load(open(p))['films']: dec[f['poster'].split('/')[-1][:-4]] = p[6:11]
    rows = collections.defaultdict(list)
    for node in ast.walk(ast.parse(open('spinegen/vault.py').read())):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ('std', 'disney'):
            kw = {k.arg: k.value for k in node.keywords}
            o = kw['order'].value if 'order' in kw else ('CLAM' if node.func.id == 'disney' else 'LPTF')
            ph = kw.get('photo'); ar = w = None
            if isinstance(ph, ast.Call): w = ph.args[2].value; ar = ph.args[3].value if len(ph.args) > 3 else 1.0
            rows[dec.get(node.args[0].value, '?')].append(dict(order=o, ft=kw['ft'].value if 'ft' in kw else 'a', ar=ar, w=w,
                credit=ast.unparse(kw['credit']) if 'credit' in kw else '', st=('stick' in kw and 'S' in o) or 'dotst' in kw))
    for d in (want or sorted(rows)):
        R = rows[d]; n = len(R)
        if not n: continue
        after = lambda r, c: 'T' in r['order'] and c in r['order'][r['order'].index('T'):]
        dirw = ('FILM', 'BY', ' DE', ' DI', 'PICTURE', 'PRODUCTION', 'RÉALISATION', 'DIRECTED')
        dl = sum(1 for r in R if r['credit'] and any(x in r['credit'] for x in dirw)); cast = sum(1 for r in R if r['credit']) - dl
        ars = [r['ar'] for r in R if r['ar']]; ws = sorted(r['w'] for r in R if r['w'])
        print(f"{d}: {n} | stickers {sum(r['st'] for r in R) / n:.0%} | line under title {sum(after(r, 'C') for r in R) / n:.0%} | director {dl / n:.0%} | cast/other {cast / n:.0%} | picture below title {sum(after(r, 'P') for r in R) / n:.0%}")
        print(f"   aspect square {sum(.9 <= a <= 1.1 for a in ars)}, wide {sum(a < .8 for a in ars)}, tall {sum(a > 1.2 for a in ars)} of {len(ars)}; median width {ws[len(ws) // 2] if ws else '-'}")
        print(f"   feet {dict(collections.Counter(r['ft'] for r in R if r['order'] != 'CLAM'))} | orders {collections.Counter(r['order'] for r in R).most_common(4)}")




def lines(out, id_):
    """render the title lines of a spec on their own, stacked, on grey (to check a lift or cut)"""
    import os
    sys.argv = ['tapes.py', '--none']
    src = open('spinegen/tapes.py').read().replace("if __name__ == '__main__':", 'if False:')
    g = {'__file__': os.path.abspath('spinegen/tapes.py')}
    sys.path.insert(0, 'spinegen'); exec(compile(src, 'tapes.py', 'exec'), g)
    g['CUR']['cover'] = os.path.abspath(f'posters/{id_}.jpg')
    ims = []
    for it in g['SPECS'][id_]['items']:
        for l in getattr(it, 'lines', []): ims.append(l.render(1.0))
    W = max(i.width for i in ims); o = Image.new('RGBA', (W, sum(i.height + 6 for i in ims)), (120, 120, 120, 255)); y = 0
    for i in ims: o.alpha_composite(i, (0, y)); y += i.height + 6
    o.convert('RGB').save(out)


if __name__ == '__main__':
    globals()[sys.argv[1]](*sys.argv[2:])
