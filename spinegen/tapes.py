"""One hand-written spine design per tape.  Run from the repo root:

    python3 spinegen/tapes.py                 # everything
    python3 spinegen/tapes.py sinners-2025    # some (keys are the poster file names without .jpg)

Writes posters/<name>-spine-b.jpg (1100px tall; width follows the shelf's runtime rule).
Studio names are plain type only: no studio logos and no character art are drawn.
"""
import sys, json
from eng import *

# finishes: how the box has aged
SLIP = dict(kind='slip', wear=.45, gloss=.05)                                   # ordinary card slipcase
MINT = dict(kind='slip', wear=.2, gloss=.07)                                    # barely handled
RENTAL = dict(kind='slip', wear=.8, gloss=.03, dents=1, tears=1, fade=.04, warm=.012)  # ex-rental
OLD = dict(kind='slip', wear=.65, gloss=.02, dents=1, fade=.06, warm=.02, card=(232, 224, 205))
CLAM = dict(kind='clam', wear=.4, gloss=.06)                                    # plastic clamshell
WHT, BLK, CRM = (246, 243, 234), (20, 19, 19), (240, 233, 212)
VRED = (200, 32, 38)

import glob, os
# every shelf: films.json (newest year) and films-<year>.json (older ones)
FILMS = {f['poster'].split('/')[-1][:-4]: f
         for p in [REPO + 'films.json'] + sorted(glob.glob(REPO + 'films-*.json'))
         for f in json.load(open(p, encoding='utf8'))['films'] if f.get('poster')}
SPECS = {}


def add(id, bg, items, fin=SLIP, **kw):
    kw.setdefault('bot', 78)  # keep clear of the thumb notch
    SPECS[id] = dict(id=id, runtime=FILMS[id].get('runtime'), bg=bg, items=items, fin=fin, **kw)


def tb(id, i=0, pad=0.012):
    """the film's titleBox line i from films.json, padded a little (i may be a list -> list of boxes)"""
    if isinstance(i, (list, tuple)):
        return [tb(id, j, pad) for j in i]
    b = FILMS[id]['titleBox'][i]
    return (max(0, b[0] - pad), max(0, b[1] - pad), min(1, b[2] + pad), min(1, b[3] + pad))


def ph(cx, cy, w, ar=1.0):
    """a poster crop box centred on (cx, cy), w wide (fraction of poster width), ar = height/width of the picture"""
    h = w * ar * 780 / 1170
    x0 = min(max(0, cx - w / 2), 1 - w); y0 = min(max(0, cy - h / 2), 1 - h)
    return (x0, y0, x0 + w, y0 + h)


def logo(id, color=None, w=0.62, path=None, maxh=0.5):
    """the studio logo file from logos/ (as fetched from TMDB), placed as it is (color=None) or
    printed in one ink.  Never redrawn: this only scales the repo's own file."""
    im = Image.open(REPO + (path or FILMS[id]['logo'])).convert('RGBA')
    W = w_for(FILMS[id].get('runtime'))
    tw = W * w
    if im.height / im.width * tw > W * maxh: tw = W * maxh * im.width / im.height
    th = tw * im.height / im.width
    big = im.resize((int(tw * S), int(th * S)), Image.LANCZOS)
    if color is not None:
        a = np.asarray(big).astype(np.float32) / 255
        al, lum = a[..., 3], a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
        op = al > 0.5
        lo, hi = (np.percentile(lum[op], 2), np.percentile(lum[op], 98)) if op.any() else (0, 0)
        if hi - lo > 0.3:  # two-tone artwork: print the commoner tone, leave the other knocked out
            t = np.clip((lum - lo) / (hi - lo), 0, 1)
            m = al * ((1 - t) if (t[op] < 0.5).mean() > 0.5 else t)
        else:
            m = al
        m = np.clip((cv2.GaussianBlur(m, (0, 0), 0.6) - 0.5) * 3 + 0.5, 0, 1)
        big = colorize(Image.fromarray((m * 255).astype(np.uint8)), color)

    def fn(imm, W_, y0, rng):
        imm.alpha_composite(big, (int(W_ * S / 2 - big.width / 2), int(y0 * S)))
    return Fn(fn, th)


def catfor(id, pre=''):
    return pre + str(10000 + sum((i + 3) * ord(c) for i, c in enumerate(id)) * 7 % 89999)


def foot(style, col, box=None, boxink=WHT, cat=None, id=''):
    cat = cat or catfor(id)
    if style == 'a': return [vhs(boxink if box else col, box), Gap(8), hifi(col), Gap(9), catno(cat, col)]
    if style == 'b': return [tiny(['VHS   ' + cat], col, font='intsb', size=22, track=.02)]
    if style == 'c': return [tiny(['Hi-Fi Stereo'], col, font='intm', size=21, track=0), Gap(10), vhs(boxink if box else col, box, size=36), Gap(10),
                             catno(cat, col, size=23), Gap(8), tiny(['CLOSED', 'CAPTIONED'], col, font='intxb', size=15, track=.04)]
    if style == 'd': return [catno(cat, col, size=20), Gap(6), tiny(['HI-FI'], col, font='intsb', size=18, track=.06), Gap(12), vhs(boxink if box else col, box, size=40)]
    if style == 'e': return [vhs(boxink if box else col, box, size=38), Gap(8), tiny(['STEREO'], col, font='intsb', size=15, track=.3), Gap(8), catno(cat, col, size=17)]


def std(id, bg, ink, title, order='LPTF', photo=None, pb=WHT, pin=14, lg=None, lw=.62, lpath=None, studio=None, scol=None,
        credit=None, ccol=None, ft='a', fcol=None, vbox=None, vink=WHT, cat=None, stick=None, dotst=None, photo2=None,
        tgap=14, fin=SLIP, barcols=None, **kw):
    """the usual tape: order is a string of parts, top to bottom:
    L logo  l studio name in type  P framed picture  p second picture  T title down the spine  t title block across
    C credit lines  S sticker  F format mark and numbers  - rule  g small gap"""
    fcol = fcol or ink; ccol = ccol or ink; scol = scol or ink
    it = []
    for ch in order:
        if ch == 'L': it += [logo(id, lg, lw, lpath), Gap(18)]
        elif ch == 'l': it += [tiny(studio, scol, font='intxb', size=16), Gap(16)]
        elif ch in 'Pp':
            it += [Crop(photo if ch == 'P' else photo2, inset=pin, border=pb)]
            if dotst and ch == 'P':
                it += [Fn(lambda im, W, y0, rng, d=dotst: dot(y0 - 6, d[0], d[1], d[2] if len(d) > 2 else WHT, x=.74, d=d[3] if len(d) > 3 else 64)(im, W, rng), 0)]
            it += [Gap(22)]
        elif ch == 'T': it += [Flex(.5), V(title if isinstance(title, list) else [title], gap=tgap), Flex(1), Gap(8)]
        elif ch == 't': it += [Hh(title if isinstance(title, list) else [title], gap=8, margin=14), Gap(22)]
        elif ch == 'C': it += [tiny(credit, ccol, size=16), Gap(22)]
        elif ch == 'S': it += [stick, Gap(18)]
        elif ch == 'F': it += ([] if 'T' in order else [Flex(1)]) + foot(ft, fcol, vbox, vink, cat, id)
        elif ch == '-': it += [Rule(scol, 2, 16), Gap(16)]
        elif ch == 'g': it += [Gap(14)]
        elif ch == 'b': it += [bars(barcols), Gap(20)]
    kw.setdefault('top', 26)
    add(id, bg, it, fin=fin, **kw)


def bars(cols, h=70, inset=14):
    """horizontal colour bars (a TV test-card stripe)"""
    def fn(im, W, y0, rng):
        d = ImageDraw.Draw(im); n = len(cols); bh = h / n
        for i, c in enumerate(cols):
            d.rectangle([inset * S, (y0 + i * bh) * S, (W - inset) * S, (y0 + (i + 1) * bh - 2) * S], fill=tuple(c) + (255,))
    return Fn(fn, h)


WORN = dict(SLIP, wear=.65, dents=1)
RWD = lambda **k: flow(rewind, 124, **k)
BAR = lambda code, **k: flow(barcode, 220, code, h=214, **k)
PRC = lambda lines: flow(price, 26 * len(lines) + 18, lines)




# ---------- spine furniture (all plain type)
def tiny(lines, color, font='intsb', size=17, track=0.14, gap=5):
    lines = lines if isinstance(lines, list) else [lines]
    return Hh([T(t, font, size, color, track=track) for t in lines], gap=gap)


def vhs(color, box=None, size=34):
    """the format mark: bold italic letters, optionally reversed out of a box"""
    return Hh([T('VHS', 'intbki', size, color, track=-0.03, box=(box, 7, 5) if box else None)], margin=30)


def hifi(color, text='hi-fi', size=20):
    return Hh([T(text, 'intxb', size, color, track=0.02)], margin=40)


def catno(text, color, size=19):
    return Hh([T(text, 'intm', size, color, track=0.06)])


def frame(color, inset=8, th=1.2):
    """a thin printed keyline round the spine"""
    def fn(im, W, rng):
        ImageDraw.Draw(im).rectangle([inset * S, inset * S, (W - inset) * S, (H - inset) * S], outline=tuple(color) + (255,), width=max(1, int(th * S)))
    return fn


def disc(stops, r=0.44, glow=(255, 120, 20), h=170):
    """a grainy glowing sun: colour only"""
    def fn(im, W, y0, rng):
        hh, ww = im.height, im.width
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        cx, cy, R = W / 2 * S, (y0 + h / 2) * S, W * r * S
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R
        n = fbm(hh, ww, 2.2 * S, rng, 2) * 0.10 + fbm(hh, ww, 30 * S, rng, 3) * 0.08
        a = np.asarray(im).astype(np.float32)
        g = np.clip(1.25 - d * 0.62 + n, 0, 1) ** 2.4 * 0.75
        a[..., :3] = a[..., :3] * (1 - g[..., None]) + np.array(glow, np.float32) * g[..., None]
        k = np.clip((1 - d + n * 0.5) * 9, 0, 1)
        t = np.clip((yy - (cy - R)) / (2 * R) + n, 0, 1)
        col = np.stack([np.interp(t, [s[0] for s in stops], [s[1][c] for s in stops]) for c in range(3)], -1)
        a[..., :3] = a[..., :3] * (1 - k[..., None]) + col * k[..., None]
        im.paste(Image.fromarray(a.astype(np.uint8), 'RGBA'))
    return Fn(fn, h)


# ---------- stickers (laid over the print; the finish then wears them with everything else)
def _stick(im, cx, cy, w, h, fill, ang, draw, rng, round_=5, circle=False):
    st = Image.new('RGBA', (int(w * S), int(h * S)), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    if circle: d.ellipse([0, 0, st.width - 1, st.height - 1], fill=tuple(fill) + (255,))
    else: d.rounded_rectangle([0, 0, st.width - 1, st.height - 1], radius=round_ * S, fill=tuple(fill) + (255,))
    draw(st, d)
    n = fbm(st.height, st.width, 14 * S, rng, 3)  # a little grime and uneven yellowing
    a = np.asarray(st).astype(np.float32); a[..., :3] *= (1 + 0.05 * n)[..., None]
    st = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA').rotate(ang, expand=True, resample=Image.BICUBIC)
    sh = Image.new('RGBA', st.size, (0, 0, 0, 0)); sh.putalpha(st.getchannel('A').point(lambda v: int(v * 0.45)))
    sh = sh.filter(ImageFilter.GaussianBlur(1.6 * S))
    x, y = int(cx * S - st.width / 2), int(cy * S - st.height / 2)
    im.alpha_composite(sh, (x + S, y + int(1.5 * S)))
    im.alpha_composite(st, (x, y))


def _lines(st, lines, font, size, color, gap=3, top=None, track=0.0):
    ims = [T(t, font, size, color, track=track).render(1.0) for t in lines]
    pads = [int((10 + size * 0.12) * S) for _ in ims]
    maxw = st.width - 8 * S
    out = []
    for i_, p in zip(ims, pads):
        i_ = i_.crop((p, p, i_.width - p, i_.height - p))
        if i_.width > maxw: i_ = i_.resize((maxw, int(i_.height * maxw / i_.width)), Image.LANCZOS)
        out.append(i_)
    tot = sum(i.height for i in out) + gap * S * (len(out) - 1)
    y = (st.height - tot) // 2 if top is None else int(top * S)
    for i_ in out:
        st.alpha_composite(i_, ((st.width - i_.width) // 2, y)); y += i_.height + gap * S
    return y / S


def rewind(y, fill=(244, 240, 226), ink=(28, 28, 30), ang=None, x=0.5):
    def fn(im, W, rng):
        _stick(im, W * x, y, W * 0.74, 112, fill, rng.uniform(-9, 9) if ang is None else ang,
               lambda st, d: _lines(st, ['BE', 'KIND', 'PLEASE', 'REWIND'], 'hcnb', 27, ink, gap=3), rng, round_=9)
    return fn


def barcode(y, code, top='(R)', fill=(214, 200, 168), ink=(52, 46, 40), h=250):
    """a video-shop inventory label running down the spine"""
    def fn(im, W, rng):
        def draw(st, d):
            yb = _lines(st, [top] + code.split(), 'mono', 22, ink, gap=4, top=12, track=0.04) + 12
            x0, x1 = 12 * S, st.width - 12 * S
            yy = yb * S
            while yy < st.height - 14 * S:
                t = int(rng.choice([1, 1, 2, 3])) * S
                d.rectangle([x0, yy, x1, yy + t - 1], fill=tuple(ink) + (255,))
                yy += t + int(rng.choice([1, 2, 2, 3])) * S
        _stick(im, W * 0.5 + rng.uniform(-3, 3), y, W * 0.56, h, fill, rng.uniform(-2.5, 2.5), draw, rng, round_=6)
    return fn


def dot(y, text, fill, ink=WHT, x=0.5, d=62):
    """a round shelf-category sticker"""
    def fn(im, W, rng):
        _stick(im, W * x, y, d, d, fill, rng.uniform(-18, 18), lambda st, dd: _lines(st, text if isinstance(text, list) else [text], 'hcnb', 19, ink, gap=2), rng, circle=True)
    return fn


def flow(maker, hh, *a, **kw):
    """put a sticker in the layout (it takes up h) instead of laying it over the print"""
    return Fn(lambda im, W, y0, rng: maker(y0 + hh / 2, *a, **kw)(im, W, rng), hh)


def price(y, lines, fill=(246, 244, 236), ink=(60, 60, 110), x=0.5):
    def fn(im, W, rng):
        _stick(im, W * x, y, W * 0.58, 26 * len(lines) + 18, fill, rng.uniform(-6, 6), lambda st, d: _lines(st, lines, 'mono', 21, ink, gap=4), rng, round_=3)
    return fn


# =====================================================================================
# first five
# =====================================================================================

# Sinners: black box, the poster's burning sun at the head, title in its own chalky lettering
add('sinners-2025',
    ('grad', [(0, (58, 8, 4)), (.10, (150, 22, 4)), (.24, (120, 12, 4)), (.42, (30, 6, 6)), (1, (8, 9, 12))]),
    [logo('sinners-2025', None, .4), Gap(10),
     disc([(0, (250, 200, 30)), (.45, (240, 120, 12)), (1, (236, 44, 6))]), Gap(26),
     Flex(.5),
     V([L(tb('sinners-2025'), 112, (243, 232, 208), mode='key', key=(240, 228, 196), t=(60, 125))]),
     Flex(1), tiny(['A RYAN COOGLER', 'FILM'], (226, 60, 30), size=17), Gap(26),
     vhs(WHT, VRED), Gap(8), hifi((200, 196, 188)), Gap(10), catno('S 38517', (150, 146, 140))],
    fin=dict(SLIP, gloss=.07), top=26)

# Bad Apples: the poster's flat yellow, red title, the apple framed up top
add('bad-apples-2025',
    ('solid', (231, 208, 62)),
    [logo('bad-apples-2025', BLK, .6), Gap(14), Rule(BLK, 2, 16), Gap(16),
     Crop((0.16, 0.215, 0.84, 0.625), inset=15, border=(250, 248, 240)), Gap(30),
     V([L(tb('bad-apples-2025'), 84, (190, 24, 20), mode='key', key=(194, 23, 18), t=(70, 140))], ),
     Flex(1), tiny(['Hi-Fi Stereo'], BLK, font='intm', size=21, track=0), Gap(10),
     vhs(WHT, (190, 24, 20), size=36), Gap(10), catno('8752', BLK, size=24), Gap(8),
     tiny(['CLOSED', 'CAPTIONED'], BLK, font='intxb', size=16, track=.04)],
    fin=dict(MINT, wear=.3), top=26,
    over=[dot(262, ['DARK', 'COMEDY'], (30, 30, 34), x=.74, d=66)])

# The Negotiator: a real 1998 rental. Black, the red stand-off framed at the head
add('the-negotiator-1998',
    ('solid', (16, 15, 15)),
    [Gap(2), Crop((0.0, 0.0, 1.0, 0.47), inset=13, border=(232, 228, 216)), Gap(20),
     tiny(['THE'], WHT, font='hcnb', size=30, track=.5), Gap(14),
     V([TT([('NEGOT', WHT), ('IA', (214, 44, 22)), ('TOR', WHT)], 'hcnb', 92, track=.13),
        T('SAMUEL L. JACKSON    KEVIN SPACEY', 'hcnb', 27, (214, 44, 22), track=.06)], gap=18),
     Gap(14), flow(barcode, 236, '22 15009', h=230), Flex(1),
     tiny(['VHS   14217'], (168, 164, 158), font='intsb', size=22, track=.02), Gap(14),
     logo('the-negotiator-1998', (226, 222, 212), .8)],
    fin=RENTAL, top=24,
    seed=1998)

# Do Revenge: the poster's sherbet fade, its neon signature down the spine, the two leads in a snapshot
add('do-revenge-2022',
    ('grad', [(0, (255, 199, 246)), (.3, (254, 222, 200)), (.55, (252, 226, 164)), (.8, (220, 238, 172)), (1, (192, 236, 204))]),
    [logo('do-revenge-2022', (206, 32, 84), .66), Gap(16),
     Crop((0.19, 0.085, 0.83, 0.43), inset=15, border=(255, 255, 255)), Gap(18),
     Flex(.4),
     V([L(tb('do-revenge-2022', pad=.02), 150, (208, 30, 84), mode='key', key=(240, 26, 95), t=(55, 105), grow=.12, shadow=((255, 255, 255), 1.5, 1.5))]),
     Flex(.6), flow(rewind, 124, fill=(250, 247, 238)), Flex(.6),
     vhs((206, 32, 84), size=38), Gap(8), hifi((60, 60, 80)), Gap(8), catno('NO 30402', (60, 60, 80), size=17)],
    fin=dict(SLIP, wear=.35, gloss=.08), top=26)

# Barcelona: 1994, cream laid-paper box with the engraved title and the pen-and-wash pair
add('barcelona-1994',
    ('solid', (243, 240, 226)),
    [Gap(6), logo('barcelona-1994', (92, 30, 30), .74), Gap(14),
     Crop((0.33, 0.33, 0.985, 0.80), inset=17, border=(70, 66, 58)), Gap(8),
     Flex(.5),
     V([L(tb('barcelona-1994'), 84, (46, 43, 38), mode='dark', grow=.10, close=2, cut=(.2, .5))]),
     Flex(1), tiny(['A FILM BY', 'WHIT STILLMAN'], (92, 30, 30), font='terb', size=17, track=.1), Gap(8), Rule((92, 30, 30), 1.2, 30), Gap(22),
     vhs((46, 43, 38), size=34), Gap(6), hifi((46, 43, 38), 'HI-FI STEREO', 14), Gap(10), catno('M 600194', (46, 43, 38), size=16)],
    fin=OLD, top=24, under=[frame((92, 30, 30), 9, 1.2)],
    over=[dot(246, ['STAFF', 'PICK'], (28, 92, 150), x=.73, d=64)])



# =====================================================================================
# the rest of the shelf
# =====================================================================================
GOLD = (206, 168, 84)

# Creed: black-and-white ring photo, big white block title
std('creed-2015', ('solid', (15, 15, 16)), WHT, L(tb('creed-2015'), 120, WHT),
    photo=ph(.42, .58, .84, 1.15), pb=(210, 210, 206), lg=None, lw=.5, credit=['A RYAN COOGLER', 'FILM'], ccol=GOLD,
    order='LPTCF', ft='a', vbox=VRED, fcol=(190, 188, 182), fin=SLIP)

# No Other Choice: the blue of the sky behind the pine, thin geometric capitals
std('no-other-choice-2025', ('grad', [(0, (26, 84, 170)), (.6, (18, 52, 120)), (1, (10, 26, 50))]), WHT,
    T('NO OTHER CHOICE', 'adv', 84, WHT, track=.07, bold=.5),
    photo=ph(.64, .87, .7, .8), lg=WHT, lw=.8, order='LTPF', credit=None, ft='e', fcol=(214, 226, 244), fin=MINT)

# Devil in Disguise: a boxed TV series, crawl-space dark
std('devil-in-disguise-john-wayne-gacy-2025', ('solid', (17, 14, 11)), (236, 228, 208),
    [L(tb('devil-in-disguise-john-wayne-gacy-2025', [0, 1, 2], pad=.004), 96, (236, 228, 208), speck=.03, valign='mid'),
     T('JOHN WAYNE GACY', 'hcnb', 26, (214, 178, 96), track=.3)],
    photo=ph(.5, .88, .8, .55), pb=(214, 178, 96), lg=(236, 228, 208), lw=.4, order='LPTCF', tgap=16,
    credit=['THE COMPLETE', 'LIMITED SERIES'], ccol=(214, 178, 96), ft='b', fcol=(170, 164, 150), fin=SLIP)

# The Rip: stencilled, battered white on black with a sodium-orange accent
std('the-rip-2026', ('solid', (14, 13, 12)), (238, 232, 220),
    L(tb('the-rip-2026', [0, 1], pad=.004), 128, (238, 232, 220), speck=.002),
    photo=ph(.5, .2, 1.0, .9), pb=(232, 122, 34), lg=(232, 122, 34), lw=.8, order='LPTSF', stick=RWD(fill=(236, 122, 40), ink=(20, 16, 12)),
    ft='a', vbox=(232, 122, 34), vink=(14, 13, 12), fcol=(190, 186, 178), fin=WORN)

# F1: storm-grey box, the poster's own wordmark in silver
std('f1-2025', ('grad', [(0, (84, 96, 98)), (.5, (52, 62, 66)), (1, (22, 26, 30))]), (224, 228, 226),
    [T('F1', 'intbki', 150, (232, 234, 232), track=-.04), T('THE MOVIE', 'intbki', 30, (226, 60, 44), track=.3)],
    photo=ph(.5, .42, .56, 1.6), pb=(226, 230, 228), lg=WHT, lw=.5, order='LPTCF', credit=['A JOSEPH KOSINSKI', 'FILM'],
    ccol=(226, 60, 44), ft='c', vbox=(226, 60, 44), fcol=(214, 218, 216), fin=dict(SLIP, gloss=.09))

# Marty Supreme: sweat-and-sepia black, stacked condensed whites
std('marty-supreme-2025', ('solid', (20, 15, 13)), (240, 234, 222),
    T('MARTY SUPREME', 'hcnb', 124, (240, 234, 222), squeeze=.8, rough=.35),
    photo=ph(.5, .2, .8, .9), pb=(240, 234, 222), lg=(240, 234, 222), lw=.56, order='LPTCF', credit=['A JOSH SAFDIE', 'PICTURE'],
    ccol=(226, 128, 52), ft='b', fcol=(180, 172, 160), fin=SLIP, dotst=(['NEW', 'RELEASE'], (226, 128, 52), (20, 15, 13)))

# The Housemaid: midnight blue, acid-yellow title, keyhole glow
std('the-housemaid-2025', ('grad', [(0, (14, 22, 70)), (.5, (12, 16, 46)), (1, (8, 9, 20))]), (220, 232, 40),
    L(tb('the-housemaid-2025', [0, 1], pad=.003), 104, (220, 232, 40)),
    photo=ph(.5, .22, 1.0, .95), pb=(226, 180, 70), lg=WHT, lw=.8, order='LPTF', ft='a', vbox=(220, 232, 40), vink=(12, 16, 46),
    fcol=(200, 206, 230), fin=SLIP)

# Bugonia: honey and ox-blood, the poster's cut-out capitals
std('bugonia-2025', ('solid', (146, 30, 32)), (246, 232, 208),
    L(tb('bugonia-2025'), 116, (246, 232, 208)),
    photo=ph(.5, .5, .9, 1.25), pb=(246, 232, 208), lg=(246, 232, 208), lw=.42, order='LTPCF', credit=['A YORGOS', 'LANTHIMOS FILM'],
    ccol=(244, 190, 60), ft='e', fcol=(246, 232, 208), fin=SLIP)

# The Perfect Neighbor: night street, police-light red and blue
std('the-perfect-neighbor-2025', ('grad', [(0, (8, 12, 30)), (.6, (14, 26, 70)), (1, (6, 8, 16))]), (226, 230, 240),
    [T('THE PERFECT', 'herb', 62, (226, 230, 240)), T('NEIGHBOR', 'herb', 62, (226, 230, 240))],
    photo=ph(.5, .36, 1.0, .45), pb=(210, 40, 50), lg=None, lw=.36, order='LPTCF', credit=['A DOCUMENTARY BY', 'GEETA GANDBHIR'],
    ccol=(140, 170, 240), ft='b', fcol=(170, 178, 200), fin=MINT, tgap=10)

# Dead Man's Wire: 1977 newsprint cream and alarm red
std('dead-man-s-wire-2025', ('solid', (234, 228, 210)), (206, 36, 44),
    T("DEAD MAN'S WIRE", 'hcnb', 112, (206, 36, 44), track=.02, rough=.5),
    photo=ph(.5, .27, .8, 1.15), pb=(30, 28, 26), lg=(30, 28, 26), lw=.74, order='LPTCF', credit=['A GUS VAN SANT', 'FILM'],
    ccol=(30, 28, 26), ft='c', vbox=(206, 36, 44), fcol=(30, 28, 26), fin=dict(WORN, warm=.015))

# Girl in the Box: TV movie, thin cream Roman capitals down a black spine
std('girl-in-the-box-2016', ('solid', (13, 11, 10)), (226, 214, 180),
    T('GIRL IN THE BOX', 'ter', 100, (226, 214, 180), track=.06, bold=.5),
    photo=ph(.55, .36, .62, 1.3), pb=(190, 150, 70), lg=None, lw=.7, order='LPTCF', credit=['A LIFETIME', 'ORIGINAL MOVIE'],
    ccol=(232, 40, 110), ft='a', vbox=(232, 40, 110), fcol=(196, 186, 160), fin=SLIP)

# Heel: cold teal room, tall blood-red condensed letters
std('heel-2025', ('grad', [(0, (16, 52, 60)), (1, (8, 24, 30))]), (206, 44, 34),
    T('HEEL', 'hcnb', 150, (206, 44, 34), track=.22, squeeze=.8),
    photo=ph(.5, .8, 1.0, .62), pb=(214, 226, 222), lg=(214, 226, 222), lw=.5, order='LTPF', ft='b', fcol=(170, 196, 196), fin=SLIP)

# High School (1968): a library copy of a 16mm documentary
std('high-school-1968', ('solid', (18, 18, 18)), (240, 238, 230),
    [L(tb('high-school-1968', 0, pad=.003), 84, (240, 238, 230), mode='light', cut=(.45, .75), speck=.03),
     L(tb('high-school-1968', 1, pad=.003), 84, (240, 238, 230), mode='light', cut=(.45, .75), speck=.03)],
    photo=ph(.4, .87, .8, .5), pb=(240, 238, 230), studio=['ZIPPORAH', 'FILMS'], order='lPTSF', tgap=10,
    stick=BAR('791.43 WIS', top='PUBLIC LIBRARY', fill=(236, 234, 224)), credit=None, ft='b', fcol=(170, 170, 166), fin=OLD, seed=1968)

# The Secret Agent: Recife 1977, telephone red with a cream italic slab
std('the-secret-agent-2025', ('solid', (188, 44, 30)), (250, 236, 200),
    [T('THE', 'bonbi', 40, (250, 236, 200)), L(tb('the-secret-agent-2025', 1, pad=.004), 150, (250, 236, 200), shadow=((70, 16, 10), 3, 3), speck=.01)],
    photo=ph(.47, .3, .7, 1.2), pb=(250, 236, 200), lg=(250, 236, 200), lw=.5, order='LPTCF', tgap=12,
    credit=['UM FILME DE', 'KLEBER MENDONÇA FILHO'], ccol=(250, 206, 90), ft='d', fcol=(250, 236, 200), fin=dict(WORN, warm=.02))

# Zodiac Killer Project: hazy California sky, plain grotesque
std('zodiac-killer-project-2025', ('grad', [(0, (188, 204, 212)), (.7, (218, 220, 214)), (1, (226, 214, 190))]), (24, 26, 30),
    L(tb('zodiac-killer-project-2025'), 76, (24, 26, 30)),
    photo=ph(.5, .8, 1.0, .6), pb=(24, 26, 30), photo2=ph(.24, .1, .44, 1.2), lg=(24, 26, 30), lw=.72, order='LpTPF',
    ft='b', fcol=(40, 44, 50), fin=MINT)

# The Sweet East: skin-warm cream, a copperplate signature
std('the-sweet-east-2023', ('solid', (240, 226, 206)), (150, 52, 40),
    T('The Sweet East', 'cho', 122, (150, 52, 40)),
    photo=ph(.5, .2, .9, .8), pb=(150, 52, 40), studio=['UTOPIA'], scol=(150, 52, 40), order='lPTCF',
    credit=['A FILM BY', 'SEAN PRICE WILLIAMS'], ft='e', fcol=(70, 40, 34), fin=dict(SLIP, warm=.01))

# Crime 101: bone white, fat black slab numerals
std('crime-101-2026', ('solid', (236, 228, 208)), (16, 15, 14),
    T('CRIME 101', 'bonb', 112, (16, 15, 14), bold=1.2, track=-.02),
    photo=ph(.74, .24, .5, 1.7), pb=(16, 15, 14), lg=None, lw=.8, order='LTPF', ft='c', vbox=(16, 15, 14), fcol=(16, 15, 14), fin=SLIP)

# How to Make a Killing: old-money white and banker's green
std('how-to-make-a-killing-2026', ('solid', (247, 246, 240)), (18, 92, 62),
    [T('HOW TO MAKE', 'terb', 66, (18, 92, 62), track=.02), T('A KILLING', 'terb', 66, (18, 92, 62), track=.02)],
    photo=ph(.5, .52, .56, 1.5), pb=(18, 92, 62), lg=(18, 92, 62), lw=.74, order='L-TPF', scol=(18, 92, 62), tgap=10,
    ft='a', vbox=(18, 92, 62), fcol=(18, 92, 62), fin=MINT)

# The Drama: wedding-photo navy, script "The" over a heavy white DRAMA
std('the-drama-2026', ('solid', (17, 19, 30)), WHT,
    [L(tb('the-drama-2026', 1, pad=.004), 112, WHT, speck=.03)],
    photo=ph(.5, .36, 1.0, 1.15), pb=WHT, lg=WHT, lw=.56, order='LPgTF', ft='b', fcol=(180, 184, 200), fin=SLIP,
    dotst=(['DATE', 'NIGHT'], (214, 60, 90)))

# Over Your Dead Body: forest green, hand-cut yellow letters
std('over-your-dead-body-2026', ('grad', [(0, (20, 70, 46)), (1, (8, 26, 18))]), (250, 230, 30),
    [L(tb('over-your-dead-body-2026', 0, pad=.003), 74, (250, 230, 30), speck=.02), L(tb('over-your-dead-body-2026', 1, pad=.003), 74, (250, 230, 30), speck=.02)],
    photo=ph(.5, .22, .74, 1.1), pb=(250, 230, 30), lg=WHT, lw=.6, order='LPTF', ft='a', vbox=(250, 230, 30), vink=(10, 30, 20),
    fcol=(220, 232, 214), fin=SLIP, tgap=10)

# Psycho Therapy: torn-paper orange
std('psycho-therapy-the-shallow-tale-of-a-writer-who-decided-to-write-about-a-serial-killer-2024', ('solid', (222, 64, 26)), WHT,
    [T('PSYCHO THERAPY', 'hcnb', 104, WHT, track=.01),
     T('THE SHALLOW TALE OF A WRITER WHO DECIDED TO WRITE ABOUT A SERIAL KILLER', 'hcnb', 21, (40, 14, 8), track=.03)],
    photo=ph(.74, .3, .5, 1.6), pb=WHT, lg=(40, 14, 8), lw=.46, order='LPTF', ft='d', fcol=(40, 14, 8), fin=SLIP, tgap=14)

# Maternal Instinct: institutional teal, swash script
std('maternal-instinct-2026', ('grad', [(0, (16, 64, 72)), (1, (8, 30, 36))]), WHT,
    L(tb('maternal-instinct-2026'), 164, WHT, grow=.06),
    photo=ph(.5, .34, .8, 1.0), pb=(200, 226, 226), lg=WHT, lw=.8, order='LPTCF', credit=['A TRUE-CRIME', 'DOCUMENTARY'],
    ccol=(236, 90, 80), ft='b', fcol=(180, 212, 212), fin=MINT)

# The Threesome: flushed red, rounded lower-case
std('the-threesome-2025', ('grad', [(0, (150, 40, 30)), (1, (70, 14, 14))]), WHT,
    L(tb('the-threesome-2025'), 150, WHT),
    photo=ph(.42, .3, 1.0, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTSF', stick=RWD(fill=(250, 240, 230)), ft='a', fcol=WHT, fin=SLIP)

# In the Grey: sun-bleached teal, three-colour stacked title
std('in-the-grey-2026', ('solid', (58, 138, 148)), (246, 206, 84),
    TT([('IN', (246, 206, 84)), ('THE', (246, 206, 84)), ('GREY', (188, 220, 220))], 'intbk', 104, track=-.01, sp=.2),
    photo=ph(.5, .62, 1.0, .75), pb=(246, 206, 84), lg=WHT, lw=.72, order='LPTCF', credit=['A GUY RITCHIE', 'FILM'], ccol=WHT,
    ft='c', vbox=(246, 206, 84), vink=(20, 60, 66), fcol=WHT, fin=SLIP)

# I Love Boosters: shoplifted-couture pink
std('i-love-boosters-2026', ('grad', [(0, (236, 60, 150)), (.6, (150, 40, 170)), (1, (60, 20, 110))]), WHT,
    L(tb('i-love-boosters-2026', [0, 1], pad=.003), 110, WHT, shadow=((60, 10, 80), 3, 3), speck=.01),
    photo=ph(.5, .14, 1.0, .55), pb=(250, 220, 60), lg=WHT, lw=.7, order='LPTF', ft='a', vbox=(250, 220, 60), vink=(60, 20, 110),
    fcol=WHT, fin=dict(SLIP, gloss=.09), dotst=(['STAFF', 'PICK'], (250, 220, 60), (60, 20, 110)))

# Project Hail Mary: deep-space teal, wide tracked capitals
std('project-hail-mary-2026', ('grad', [(0, (8, 22, 32)), (.5, (14, 52, 66)), (1, (6, 14, 22))]), WHT,
    [T('HAIL MARY', 'advb', 92, WHT, track=.3), T('PROJECT', 'advb', 22, (150, 214, 226), track=.9)],
    photo=ph(.6, .74, .74, 1.1), pb=(150, 214, 226), lg=(150, 214, 226), lw=.34, order='LTPF', tgap=16,
    ft='e', fcol=(190, 226, 234), fin=dict(MINT, gloss=.1))

# Sentimental Value: garden green, tight bold grotesque
std('sentimental-value-2025', ('grad', [(0, (30, 60, 38)), (1, (14, 30, 20))]), WHT,
    T('Sentimental Value', 'intbk', 84, WHT, track=-.03),
    photo=ph(.5, .74, 1.0, .7), pb=WHT, lg=WHT, lw=.6, order='LTPCF', credit=['EN FILM AV', 'JOACHIM TRIER'], ccol=(236, 214, 150),
    ft='b', fcol=(200, 214, 200), fin=MINT)

# Louis C.K.: Ridiculous: a comedy-club special, slate and spotlight
std('louis-c-k-ridiculous-2026', ('grad', [(0, (30, 42, 54)), (1, (10, 14, 20))]), WHT,
    TT([('LOUIS C.K.', (150, 190, 206)), ('RIDICULOUS', WHT)], 'her', 70, track=.02, sp=.22),
    photo=ph(.5, .68, .9, 1.0), pb=(150, 190, 206), studio=['STAND-UP', 'SPECIAL'], scol=(150, 190, 206), order='lPTF',
    ft='b', fcol=(170, 186, 196), fin=SLIP)

# The Devil Wears Prada 2: couture red, white Roman capitals and a script 2
std('the-devil-wears-prada-2-2026', ('solid', (172, 22, 36)), WHT,
    T('THE DEVIL WEARS PRADA 2', 'ter', 92, WHT, track=.05, bold=.5),
    photo=ph(.38, .18, .5, 1.0), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(16, 14, 14),
    fcol=WHT, fin=dict(MINT, gloss=.1))

# Jeff Arcuri: Nice to Meet You: marquee bulbs and heavy white
std('jeff-arcuri-nice-to-meet-you-2026', ('solid', (12, 12, 14)), WHT,
    [T('JEFF ARCURI', 'intbk', 80, WHT, track=-.02), T('NICE TO MEET YOU', 'intbk', 40, (246, 190, 70), track=0)],
    photo=ph(.5, .3, .84, 1.0), pb=(246, 190, 70), studio=['STAND-UP', 'COMEDY'], scol=(246, 190, 70), order='lPTF', tgap=12,
    ft='a', vbox=(246, 190, 70), vink=(12, 12, 14), fcol=(200, 200, 200), fin=SLIP)

# Pretty Maids All in a Row (1971): MGM black with the poster's long illustration
std('pretty-maids-all-in-a-row-1971', ('solid', (14, 14, 15)), WHT,
    L(tb('pretty-maids-all-in-a-row-1971'), 70, WHT, speck=.002, grow=.05),
    photo=ph(.5, .56, 1.0, .62), pb=WHT, lg=None, lw=.56, order='LPTCSF', credit=['ROCK HUDSON', 'ANGIE DICKINSON'], ccol=(214, 60, 50),
    stick=PRC(['PREVIOUSLY', 'VIEWED', '$4.99']), ft='b', fcol=(180, 176, 170), fin=OLD)

# Con Air (1997): fireball black, brushed-steel slab
std('con-air-1997', ('grad', [(0, (60, 20, 6)), (.2, (16, 12, 10)), (1, (10, 10, 12))]), (200, 210, 224),
    T('CON AIR', 'bonb', 124, (200, 210, 224), track=.06, grad=[(0, (236, 240, 248)), (.5, (140, 156, 180)), (.55, (90, 104, 130)), (1, (214, 222, 236))]),
    photo=ph(.5, .46, 1.0, .9), pb=(240, 140, 30), lg=None, lw=.8, order='LPTCSF', credit=['NICOLAS CAGE', 'JOHN CUSACK', 'JOHN MALKOVICH'],
    ccol=(240, 140, 30), stick=BAR('35 09711', top='ACTION'), ft='b', fcol=(170, 172, 180), fin=RENTAL, seed=1997)

# The Crash: tail-light pink on wet teal
std('the-crash-2026', ('grad', [(0, (18, 92, 86)), (1, (8, 40, 40))]), (236, 152, 164),
    L(tb('the-crash-2026'), 112, (236, 152, 164)),
    photo=ph(.42, .33, .84, .7), pb=(236, 152, 164), lg=WHT, lw=.5, order='LPTCF', credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=WHT,
    ft='e', fcol=WHT, fin=MINT)

# Face/Off (1997): black with a cold blue glow
std('face-off-1997', ('grad', [(0, (8, 8, 10)), (.75, (8, 10, 22)), (1, (16, 30, 80))]), (150, 190, 255),
    T('FACE/OFF', 'adv', 104, (190, 216, 255), track=.08, bold=.6, soft=((60, 120, 255), 7, .9)),
    photo=ph(.5, .38, 1.0, .85), pb=(120, 160, 240), studio=['A JOHN WOO', 'FILM'], scol=(150, 190, 255), order='lPTCSF',
    credit=['JOHN TRAVOLTA', 'NICOLAS CAGE'], ccol=WHT, stick=RWD(fill=(240, 236, 220)), ft='b', fcol=(160, 170, 196), fin=RENTAL, seed=1997)

# Obsession: one lit window in the dark
std('obsession-2025', ('grad', [(0, (10, 10, 12)), (.6, (20, 14, 10)), (1, (70, 36, 12))]), WHT,
    L(tb('obsession-2025'), 112, WHT, mode='light', cut=(.5, .8)),
    photo=ph(.5, .52, .9, 1.1), pb=(236, 150, 60), lg=WHT, lw=.6, order='LPTF', ft='a', vbox=(236, 150, 60), vink=(14, 10, 8),
    fcol=(214, 206, 196), fin=SLIP)

# LifeHack: phone-screen black and terminal green
std('lifehack-2025', ('solid', (9, 12, 12)), (128, 240, 50),
    L(tb('lifehack-2025'), 104, (128, 240, 50)),
    photo=ph(.5, .42, .56, 1.9), pb=(128, 240, 50), lg=WHT, lw=.7, order='LPTF', ft='e', fcol=(128, 240, 50), fin=SLIP)

# Tuner: piano-wire circles of slate blue, warm yellow slab
std('tuner-2025', ('grad', [(0, (54, 62, 100)), (1, (22, 26, 48))]), (242, 204, 76),
    L(tb('tuner-2025'), 132, (242, 204, 76)),
    photo=ph(.56, .4, .88, 1.1), pb=(242, 204, 76), lg=WHT, lw=.76, order='LPTF', ft='a', fcol=(226, 228, 240), fin=MINT)

# Talladega Nights (2006): stars, stripes and sponsor decals
std('talladega-nights-the-ballad-of-ricky-bobby-2006', ('bands', [(0, .34, (246, 244, 238)), (.34, 1, (22, 44, 130))]), WHT,
    [T('TALLADEGA NIGHTS', 'herbi', 70, WHT, box=((204, 24, 34), 12, 9)), T('THE BALLAD OF RICKY BOBBY', 'herbi', 27, WHT, track=.04)],
    photo=ph(.42, .2, .8, 1.25), pb=(204, 24, 34), lg=(22, 44, 130), lw=.44, order='LPTSF', tgap=16,
    stick=flow(dot, 70, ['#1', 'COMEDY'], (250, 206, 40), (22, 44, 130), d=70), ft='a', vbox=(204, 24, 34), fcol=WHT, fin=WORN)

# My Man Godfrey (1936): powder lavender, Deco hairline capitals
std('my-man-godfrey-1936', ('solid', (234, 234, 244)), (40, 60, 150),
    [L(tb('my-man-godfrey-1936', 0, pad=.002), 80, (40, 60, 150), grow=.24, speck=.03),
     L(tb('my-man-godfrey-1936', 1, pad=.002), 80, (120, 50, 130), grow=.24, speck=.03)],
    photo=ph(.5, .62, 1.0, 1.0), pb=(40, 60, 150), lg=None, lw=.56, order='LPTCF', tgap=10,
    credit=['WILLIAM POWELL', 'CAROLE LOMBARD'], ccol=(120, 50, 130), ft='d', fcol=(40, 60, 150), fin=dict(OLD, card=(238, 232, 218)))

# Body of Lies: surveillance teal-black, wide red capitals
std('body-of-lies-2008', ('grad', [(0, (12, 34, 40)), (1, (6, 10, 12))]), (232, 62, 34),
    L(tb('body-of-lies-2008'), 76, (232, 62, 34), speck=.03),
    photo=ph(.45, .3, .9, 1.1), pb=(170, 200, 204), lg=WHT, lw=.76, order='LPTCF', credit=['A RIDLEY SCOTT', 'FILM'], ccol=(170, 200, 204),
    ft='c', vbox=(232, 62, 34), fcol=(190, 206, 208), fin=WORN)

# Monster: black with the running field, red condensed title
std('monster-2023', ('solid', (12, 12, 12)), (224, 24, 34),
    L(tb('monster-2023'), 124, (224, 24, 34)),
    photo=ph(.5, .38, 1.0, .72), pb=None, pin=0, lg=WHT, lw=.3, order='LPTCF', credit=['A FILM BY', 'KORE-EDA HIROKAZU'], ccol=WHT,
    ft='b', fcol=(180, 180, 176), fin=SLIP, top=22)

# The Invite: dinner-party white, a sharp black serif
std('the-invite-2026', ('solid', (247, 245, 238)), (18, 17, 16),
    L(tb('the-invite-2026'), 104, (18, 17, 16)),
    photo=ph(.5, .32, .92, 1.0), pb=(18, 17, 16), lg=(18, 17, 16), lw=.4, order='LPTF', ft='d', fcol=(18, 17, 16), fin=MINT,
    dotst=(['COMEDY'], (196, 50, 40)))

# Motor City: pulp-paperback yellow, burnt-orange stencil
std('motor-city-2025', ('solid', (246, 172, 30)), (176, 44, 16),
    L(tb('motor-city-2025'), 112, (176, 44, 16)),
    photo=ph(.5, .42, .84, 1.5), pb=(40, 20, 10), lg=(40, 20, 10), lw=.8, order='LPTF', ft='c', vbox=(40, 20, 10), fcol=(40, 20, 10),
    fin=dict(WORN, warm=.015))

# A Deadly American Marriage: family-portrait black
std('a-deadly-american-marriage-2025', ('solid', (12, 12, 12)), WHT,
    [T('A DEADLY AMERICAN', 'popb', 56, WHT, track=.04), T('MARRIAGE', 'popb', 56, WHT, track=.2)],
    photo=ph(.5, .34, 1.0, 1.1), pb=WHT, lg=WHT, lw=.84, order='LPTCF', tgap=10, credit=['A NETFLIX', 'DOCUMENTARY'], ccol=(214, 40, 50),
    ft='b', fcol=(180, 180, 180), fin=SLIP)

# Stavros Halkias: Uncle Stav: stage blue, neon pink signature
std('stavros-halkias-uncle-stav-2026', ('grad', [(0, (26, 52, 170)), (1, (10, 16, 70))]), WHT,
    [L(tb('stavros-halkias-uncle-stav-2026', [0, 1], pad=.003), 84, WHT, speck=.02), T('Uncle Stav', 'cho', 62, (250, 90, 180))],
    photo=ph(.5, .17, .84, .8), pb=(250, 90, 180), lg=WHT, lw=.76, order='LPTF', tgap=8, ft='a', vbox=(250, 90, 180), fcol=WHT, fin=SLIP)

# Pacific Heights (1990): keyhole black, pale-blue Deco condensed
std('pacific-heights-1990', ('solid', (11, 11, 13)), (156, 204, 234),
    L(tb('pacific-heights-1990'), 124, (156, 204, 234)),
    photo=ph(.5, .36, .6, 1.9), pb=(156, 204, 234), lg=WHT, lw=.3, order='LPTSF', stick=BAR('17 02290', top='THRILLER', fill=(230, 226, 212)),
    ft='b', fcol=(160, 176, 190), fin=RENTAL, seed=1990)

# The Rivals of Amziah King: grey engraving, wood-type slab
std('the-rivals-of-amziah-king-2025', ('solid', (230, 230, 226)), (30, 30, 32),
    L(tb('the-rivals-of-amziah-king-2025'), 84, (30, 30, 32), speck=.001),
    photo=ph(.47, .38, .9, 1.1), pb=(30, 30, 32), lg=(30, 30, 32), lw=.8, order='LPTF', ft='d', fcol=(30, 30, 32), fin=SLIP)

# Molly's Game: casino navy, hairline neon running cyan to pink
std('molly-s-game-2017', ('grad', [(0, (12, 20, 40)), (1, (6, 8, 16))]), (80, 210, 226),
    L(tb('molly-s-game-2017'), 96, (80, 210, 226), grow=.2, hgrad=[(0, (70, 214, 230)), (.55, (120, 170, 230)), (1, (240, 96, 176))]),
    photo=ph(.5, .42, 1.0, .85), pb=(240, 96, 176), lg=WHT, lw=.56, order='LPTCF', credit=['WRITTEN & DIRECTED BY', 'AARON SORKIN'], ccol=WHT,
    ft='a', vbox=(240, 96, 176), fcol=(200, 210, 230), fin=SLIP)

# Beverly Hills Cop II (1987): palm-tree sky blue, lipstick-red script
std('beverly-hills-cop-ii-1987', ('grad', [(0, (40, 130, 220)), (1, (120, 196, 240))]), WHT,
    L(tb('beverly-hills-cop-ii-1987', [0, 1], pad=.002), 120, [WHT, (226, 30, 40)], shadow=((14, 50, 110), 2.5, 2.5), speck=.01),
    photo=ph(.5, .6, .74, 1.2), pb=WHT, lg=WHT, lw=.46, order='LPTSF', stick=PRC(['RENTAL', '$1.99']), ft='a', vbox=(226, 30, 40),
    fcol=WHT, fin=dict(RENTAL, sun=.25), seed=1987)

# Lethal Weapon (1987): black-and-white faces, red italic
std('lethal-weapon-1987', ('solid', (13, 13, 14)), (222, 28, 34),
    L(tb('lethal-weapon-1987'), 78, (222, 28, 34)),
    photo=ph(.45, .4, 1.0, 1.05), pb=(232, 230, 224), lg=WHT, lw=.4, order='LPTCSF', credit=['MEL GIBSON', 'DANNY GLOVER'], ccol=WHT,
    stick=RWD(fill=(250, 226, 60)), ft='b', fcol=(176, 174, 170), fin=RENTAL, seed=1987)

# Our Hero, Balthazar: night-vision green-black, orange lower-case
std('our-hero-balthazar-2025', ('solid', (15, 28, 24)), (242, 76, 44),
    T('our hero, balthazar', 'herb', 84, (242, 76, 44), track=-.02),
    photo=ph(.5, .5, 1.0, .3), pb=None, pin=0, lg=(242, 76, 44), lw=.84, order='LgPTF', ft='e', fcol=(242, 76, 44), fin=SLIP)

# Spider-Man: Brand New Day: red and midnight blue
std('spider-man-brand-new-day-2026', ('grad', [(0, (150, 14, 24)), (.3, (60, 10, 30)), (1, (8, 12, 44))]), (226, 34, 40),
    [T('SPIDER-MAN', 'intbki', 96, (236, 40, 44), outline=((8, 10, 40), 2.5), track=-.01), T('BRAND NEW DAY', 'advb', 26, (240, 190, 70), track=.34)],
    photo=ph(.5, .3, .9, 1.2), pb=(236, 40, 44), lg=None, lw=.8, order='LPTF', tgap=16, ft='a', vbox=(236, 40, 44), fcol=WHT,
    fin=dict(SLIP, gloss=.09))

# Coyote vs. Acme: desert sunset, mail-order red
std('coyote-vs-acme-2026', ('grad', [(0, (252, 190, 80)), (.5, (232, 120, 40)), (1, (96, 40, 20))]), WHT,
    TT([('COYOTE', WHT), ('VS.', (50, 22, 12)), ('ACME', (214, 34, 28))], 'intbk', 92, track=-.01, sp=.2),
    photo=ph(.42, .3, .72, 1.1), pb=(50, 22, 12), lg=(50, 22, 12), lw=.66, order='LPTF', ft='a', vbox=(214, 34, 28), fcol=WHT, fin=SLIP)

# By Any Means: Blue Note yellow and black
std('by-any-means-2026', ('bands', [(0, .075, (250, 182, 34)), (.075, 1, (13, 13, 13))]), (250, 182, 34),
    T('BY ANY MEANS', 'intbk', 100, (250, 182, 34), track=-.02),
    photo=ph(.48, .3, 1.0, .9), pb=(250, 182, 34), lg=(13, 13, 13), lw=.76, order='LPTF', ft='c', vbox=(250, 182, 34), vink=(13, 13, 13),
    fcol=(250, 182, 34), fin=SLIP)

# Deep Water: fogged-glass grey, towering black condensed
std('deep-water-2022', ('grad', [(0, (226, 228, 232)), (1, (176, 182, 190))]), (16, 16, 18),
    T('DEEP WATER', 'hcnb', 130, (16, 16, 18), track=0, squeeze=.86),
    photo=ph(.5, .45, .9, 1.0), pb=(16, 16, 18), lg=(16, 16, 18), lw=.84, order='LPTCF', credit=['AN ADRIAN LYNE', 'FILM'], ccol=(16, 16, 18),
    ft='d', fcol=(16, 16, 18), fin=SLIP)

# Primetime: broadcast blue, squeezed white headline
std('primetime-2026', ('grad', [(0, (30, 80, 170)), (.5, (16, 36, 90)), (1, (8, 12, 30))]), WHT,
    T('PRIMETIME', 'hcnb', 132, WHT, squeeze=.78, track=-.01, grad=[(0, WHT), (1, (170, 206, 250))]),
    photo=ph(.5, .38, 1.0, 1.1), pb=WHT, lg=WHT, lw=.56, order='LPTF', ft='b', fcol=(180, 200, 236), fin=MINT)

# Christine: a wall of 1974 studio monitors, test-card stripes
std('christine-2016', ('solid', (13, 13, 14)), WHT,
    L(tb('christine-2016'), 104, WHT),
    photo=ph(.5, .68, .62, 1.1), pb=(120, 170, 200), lg=None, lw=.7, order='LgPbTF', ft='a', vbox=(226, 110, 50), fcol=(200, 200, 200), fin=SLIP,
    barcols=[(226, 110, 50), (236, 190, 60), (110, 190, 110), (90, 170, 210), (150, 110, 190)])

# Your Mother Your Mother Your Mother: dark teal, the title said three times
std('your-mother-your-mother-your-mother-2026', ('solid', (26, 56, 56)), (242, 92, 42),
    L(tb('your-mother-your-mother-your-mother-2026'), 172, (242, 92, 42), speck=.002),
    photo=ph(.5, .7, .8, .95), pb=(242, 92, 42), lg=WHT, lw=.7, order='LPTF', ft='e', fcol=(242, 92, 42), fin=SLIP)

# The Odyssey: embers over a wine-dark sea, wide-spaced capitals
std('the-odyssey-2026', ('grad', [(0, (120, 60, 30)), (.25, (40, 30, 40)), (.6, (14, 20, 36)), (1, (8, 10, 18))]), (206, 216, 232),
    L(tb('the-odyssey-2026'), 62, (214, 222, 236), grow=.1),
    photo=ph(.5, .42, .84, 1.5), pb=(214, 170, 110), lg=(206, 216, 232), lw=.6, order='LPTCF', credit=['A FILM BY', 'CHRISTOPHER NOLAN'], ccol=(214, 170, 110),
    ft='a', vbox=(214, 170, 110), vink=(14, 20, 36), fcol=(206, 216, 232), fin=dict(MINT, gloss=.1))

# Heart of the Beast: wilderness green, colossal condensed letters
std('heart-of-the-beast-2026', ('grad', [(0, (24, 74, 44)), (1, (8, 26, 18))]), (150, 206, 130),
    T('HEART OF THE BEAST', 'hcnb', 112, (150, 206, 130), track=.01, squeeze=.9),
    photo=ph(.62, .36, .66, 1.3), pb=(150, 206, 130), lg=WHT, lw=.46, order='LPTF', ft='a', vbox=(150, 206, 130), vink=(10, 30, 20),
    fcol=WHT, fin=SLIP)

# Malice (1993): black with blood-red Roman capitals.  (films.json has the wrong studio for this one,
# so the Castle Rock logo file is used: it was a Castle Rock picture.)
std('malice-1993', ('solid', (11, 10, 10)), (206, 30, 36),
    L(tb('malice-1993'), 124, (214, 30, 36), grow=.2),
    photo=ph(.5, .3, 1.0, 1.0), pb=(206, 30, 36), lg=WHT, lw=.74, lpath='logos/97.png', order='LPTSF',
    stick=BAR('17 04418', top='(R)'), ft='b', fcol=(176, 170, 168),
    fin=RENTAL, seed=1993)

# The Widower: evidence-photo dark, blunt white headline
std('the-widower-til-death-do-us-part-2026', ('solid', (18, 18, 24)), WHT,
    [L(tb('the-widower-til-death-do-us-part-2026'), 86, WHT, speck=.03), T("'TIL DEATH DO US PART", 'her', 27, (226, 190, 96), track=.08)],
    photo=ph(.5, .36, 1.0, .9), pb=(226, 190, 96), lg=WHT, lw=.84, order='LPTF', tgap=14, ft='b', fcol=(180, 180, 190), fin=SLIP)

# Deep Web (2015): CRT violet-blue, scan-line capitals
std('deep-web-2015', ('grad', [(0, (12, 12, 20)), (.5, (40, 40, 120)), (1, (14, 14, 40))]), (206, 232, 240),
    L(tb('deep-web-2015'), 104, (206, 232, 240), speck=.004),
    photo=ph(.5, .62, .9, .85), pb=(206, 232, 240), lg=WHT, lw=.7, order='LPTCF', credit=['THE CRIME SAGA OF', 'THE DIGITAL AGE'], ccol=(150, 160, 250),
    ft='e', fcol=(206, 232, 240), fin=WORN)



# =====================================================================================
# the 2025 shelf (films-2025.json).  These posters have no titleBox in the data, so the
# lettering boxes are given here directly.
# =====================================================================================

# Flow: flood-water sky running down to green water, the poster's white brush lettering, the cat up top
std('flow-2024', ('grad', [(0, (118, 196, 230)), (.45, (70, 160, 186)), (1, (16, 70, 72))]), WHT,
    L((0.18, 0.095, 0.80, 0.295), 120, WHT, mode='key', key=(250, 250, 250), t=(40, 110), speck=.01),
    photo=ph(.57, .45, .42, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'GINTS ZILBALODIS'], ccol=(236, 246, 240),
    ft='e', fcol=(226, 242, 240), fin=MINT, dotst=(['ANIMATED'], (236, 120, 40)))

# You're Cordially Invited: wedding-invitation white, navy serif over the fat INVITED (lifted; the thin
# serif line above it is typeset, as it would not lift cleanly off the poster)
std('you-re-cordially-invited-2025', ('solid', (247, 245, 240)), (30, 38, 70),
    [T("You’re Cordially", 'ter', 54, (30, 38, 70), track=-.01),
     L((0.09, 0.183, 0.92, 0.255), 104, (30, 38, 70), mode='key', key=(30, 38, 70), t=(60, 140))],
    photo=ph(.67, .55, .62, 1.3), pb=(30, 38, 70), lg=(176, 140, 70), lw=.74, order='LPTF', tgap=10,
    ft='d', fcol=(30, 38, 70), fin=MINT, dotst=(['COMEDY'], (200, 60, 70)))

# Little Children: black, the thin white Roman title, the sleeping pair at the foot of the poster
std('little-children-2006', ('solid', (10, 10, 11)), WHT,
    L((0.01, 0.345, 0.99, 0.44), 80, WHT, mode='light', speck=.01),
    photo=ph(.55, .85, 1.0, .55), pb=(214, 200, 170), lg=WHT, lw=.8, order='LPTCF', credit=['A TODD FIELD', 'FILM'], ccol=(214, 200, 170),
    ft='b', fcol=(176, 172, 166), fin=SLIP)

# One of Them Days: brick-red rowhouse, the stacked white grunge capitals, the two of them on the orange couch
std('one-of-them-days-2025', ('grad', [(0, (140, 44, 36)), (.6, (96, 28, 24)), (1, (44, 14, 12))]), WHT,
    L([(0.322, 0.15, 0.672, 0.26), (0.322, 0.272, 0.672, 0.387), (0.322, 0.398, 0.672, 0.522)], 120, WHT, mode='light', speck=.002, gapf=.18),
    photo=ph(.5, .79, 1.0, .5), pb=(246, 150, 40), lg=WHT, lw=.7, order='LPTSF', tgap=8,
    stick=RWD(fill=(246, 150, 40), ink=(40, 14, 10)), ft='a', vbox=(246, 150, 40), vink=(44, 14, 12), fcol=WHT, fin=WORN)

# Babygirl: the poster's sea-glass teal and bubblegum serif
std('babygirl-2024', ('grad', [(0, (46, 120, 118)), (.6, (26, 80, 80)), (1, (10, 36, 38))]), (232, 140, 204),
    L((0.18, 0.36, 0.81, 0.475), 112, (238, 146, 208), mode='key', key=(232, 140, 204), t=(50, 110)),
    photo=ph(.58, .76, .8, 1.0), pb=(238, 146, 208), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(200, 226, 222), fin=MINT)

# Hard Truths: near-black brown, the poster's chunky lemon-yellow grotesque
std('hard-truths-2024', ('solid', (24, 20, 17)), (238, 226, 96),
    [L((0.07, 0.355, 0.63, 0.467), 96, (240, 228, 98), mode='key', key=(240, 228, 100), t=(55, 115)),
     L((0.19, 0.472, 0.93, 0.572), 96, (240, 228, 98), mode='key', key=(240, 228, 100), t=(55, 115))],
    photo=ph(.66, .17, .5, 1.0), pb=(240, 228, 98), lg=WHT, lw=.7, order='LPTCF', tgap=8, credit=['A MIKE LEIGH', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 228, 98), vink=(24, 20, 17), fcol=(200, 196, 186), fin=SLIP)

# Nickel Boys: Florida dirt and floorboards, the cream Roman capitals, the two boys seen from above
std('nickel-boys-2024', ('grad', [(0, (118, 96, 62)), (.5, (78, 62, 40)), (1, (32, 26, 18))]), (240, 232, 214),
    L((0.07, 0.815, 0.95, 0.885), 70, (242, 234, 214), mode='light', speck=.01),
    photo=ph(.55, .4, .66, 1.3), pb=(240, 232, 214), lg=(240, 232, 214), lw=.6, order='LPTCF', credit=['A RAMELL ROSS', 'FILM'],
    ccol=(226, 190, 120), ft='c', vbox=(240, 232, 214), vink=(40, 32, 22), fcol=(240, 232, 214), fin=SLIP)

# Anora: Brighton Beach night, the pink neon signature
std('anora-2024', ('grad', [(0, (52, 12, 40)), (.5, (28, 8, 26)), (1, (10, 6, 12))]), (255, 120, 150),
    L((0.07, 0.655, 0.915, 0.895), 140, (255, 236, 240), mode='key', key=(255, 244, 244), t=(28, 80), speck=.03, grow=.08,
      outline=((255, 60, 110), 2.4)),
    photo=ph(.6, .3, .64, 1.15), pb=(255, 140, 166), lg=WHT, lw=.7, order='LPTCF', credit=['A SEAN BAKER', 'FILM'], ccol=(255, 200, 120),
    ft='a', vbox=(230, 40, 90), fcol=(220, 200, 214), fin=dict(SLIP, gloss=.09), dotst=(['STAFF', 'PICK'], (255, 200, 60), (40, 10, 30)))

# The Brutalist: a 2-tape set for a 215-minute film, so the box is two tapes wide (W = twice an average
# slipcase; app.js shows a picture this wide at its own width).  The poster's pale sky, the heavy
# black condensed capitals, Liberty upside down.
std('the-brutalist-2024', ('grad', [(0, (222, 232, 238)), (1, (186, 204, 214))]), (16, 16, 18),
    [T('THE', 'hcnb', 70, (16, 16, 18), track=.12), T('BRUTALIST', 'hcnb', 230, (16, 16, 18), squeeze=.86, track=-.01)],
    photo=ph(.42, .17, .7, .42), pb=(16, 16, 18), pin=22, lg=(16, 16, 18), lw=.24, order='LPTCSF', tgap=10,
    credit=['A BRADY CORBET FILM', 'ADRIEN BRODY  FELICITY JONES  GUY PEARCE'], ccol=(16, 16, 18),
    stick=flow(dot, 112, ['2-TAPE', 'SET'], (200, 40, 36), WHT, d=104), ft='c', vbox=(16, 16, 18), fcol=(16, 16, 18), fin=SLIP,
    W=2 * w_for(115), notch_w=1.5 * w_for(115))  # twice an average tape (about 43px on the shelf), notch 1.5x a normal one

# Gaucho Gaucho: old circus-poster parchment, red western capitals with a cream keyline
std('gaucho-gaucho-2024', ('grad', [(0, (238, 218, 172)), (.6, (222, 190, 128)), (1, (168, 120, 70))]), (206, 64, 34),
    [T('"GAUCHO', 'bonb', 76, (206, 64, 34), outline=((250, 238, 206), 2.2), shadow=((80, 34, 16), 3, 3), track=.02),
     T('GAUCHO"', 'bonb', 76, (206, 64, 34), outline=((250, 238, 206), 2.2), shadow=((80, 34, 16), 3, 3), track=.02)],
    photo=ph(.27, .12, .5, 1.2), pb=(80, 34, 16), lg=(70, 34, 18), lw=.8, order='LPTCF', tgap=10,
    credit=['A DOCUMENTARY BY', 'MICHAEL DWECK', '& GREGORY KERSHAW'], ccol=(80, 34, 16), ft='e', fcol=(70, 34, 18), fin=OLD)

# The Wild Robot: night forest, the poster's chalky yellow lettering, Roz's glowing eyes up top
std('the-wild-robot-2024', ('grad', [(0, (26, 50, 40)), (.6, (14, 30, 24)), (1, (6, 14, 10))]), (232, 204, 52),
    L([(0.40, 0.075, 0.62, 0.135), (0.24, 0.13, 0.75, 0.225), (0.19, 0.228, 0.80, 0.33)], 120, (236, 208, 56), mode='key', key=(226, 200, 46), t=(60, 125), speck=.01, gapf=.2),
    photo=ph(.45, .6, .5, 1.0), pb=(236, 208, 56), lg=WHT, lw=.6, order='LPTF', ft='a', vbox=(236, 208, 56), vink=(14, 30, 24),
    fcol=(214, 222, 210), fin=SLIP, dotst=(['FAMILY'], (232, 112, 40)))

# Flight Risk: glacier blue-grey, orange condensed capitals (typeset: the poster's fade over snow won't lift), Wahlberg's battered face
std('flight-risk-2025', ('grad', [(0, (70, 92, 112)), (.5, (36, 50, 64)), (1, (14, 18, 24))]), (238, 84, 36),
    T('FLIGHT RISK', 'hcnb', 116, (240, 86, 38), squeeze=.8, bold=.8, track=-.01),
    photo=ph(.5, .13, .5, .75), pb=(226, 232, 238), lg=WHT, lw=.5, order='LPTCF', credit=['A MEL GIBSON', 'FILM'], ccol=(238, 84, 36),
    ft='a', vbox=(238, 84, 36), fcol=(200, 210, 220), fin=WORN)

# Adolescence: the boy's grey sweatshirt and the police-station green, thin tracked capitals
std('adolescence-2025', ('grad', [(0, (78, 86, 74)), (.6, (46, 52, 46)), (1, (18, 20, 18))]), WHT,
    L((0.11, 0.84, 0.89, 0.9), 64, WHT, mode='key', key=(248, 248, 248), t=(30, 100), speck=.01),
    photo=ph(.3, .33, .58, 1.1), pb=(226, 226, 220), lg=WHT, lw=.7, order='LPTCF', credit=['THE COMPLETE', 'LIMITED SERIES'],
    ccol=(226, 92, 70), ft='b', fcol=(196, 200, 190), fin=MINT)

# Carnal Knowledge (1971): the poster's pale grey and huge black condensed capitals (typeset: the poster's
# lettering bleeds off its edges), the halftone faces
std('carnal-knowledge-1971', ('solid', (222, 222, 218)), (18, 18, 18),
    T('CARNAL KNOWLEDGE', 'hcnb', 100, (18, 18, 18), squeeze=.74, bold=.8, track=-.02),
    photo=ph(.5, .3, 1.0, .42), pb=(18, 18, 18), lg=(18, 18, 18), lw=.6, order='LPTCF', tgap=10,
    credit=['JACK NICHOLSON', 'ART GARFUNKEL'], ccol=(150, 30, 30), ft='d', fcol=(18, 18, 18), fin=OLD, seed=1971)

# Rich Flu: storm-teal sky full of falling money, the chunky white title
std('rich-flu-2024', ('grad', [(0, (52, 86, 104)), (.6, (26, 42, 54)), (1, (10, 14, 20))]), WHT,
    L((0.05, 0.365, 0.95, 0.525), 112, WHT, mode='key', key=(248, 248, 246), t=(40, 110), speck=.01),
    photo=ph(.5, .72, .5, 1.25), pb=(214, 176, 90), lg=WHT, lw=.7, order='LPTF', ft='a', vbox=(214, 176, 90), vink=(10, 14, 20),
    fcol=(200, 214, 222), fin=SLIP)

# Riff Raff: the poster's 70s orange frame, heavy white stencil-ish capitals, the cast crammed in
std('riff-raff-2025', ('grad', [(0, (246, 160, 40)), (.5, (234, 110, 30)), (1, (176, 60, 20))]), WHT,
    L([(0.10, 0.605, 0.49, 0.695), (0.36, 0.67, 0.87, 0.765)], 116, WHT, mode='key', key=(250, 250, 248), t=(40, 110), speck=.01, gapf=.22),
    photo=ph(.5, .32, .9, .8), pb=WHT, lg=WHT, lw=.8, order='LPTCF', credit=['A DITO MONTIEL', 'FILM'], ccol=(60, 22, 8),
    ft='a', vbox=(60, 22, 8), fcol=(60, 22, 8), fin=WORN)

# Not a Pretty Picture (1976): grainy black-and-white, the title set in round lower-case with a black keyline
# (the poster's outlined 70s lettering won't lift off the photo)
std('not-a-pretty-picture-1976', ('grad', [(0, (60, 60, 58)), (1, (16, 16, 16))]), WHT,
    T('not a pretty picture', 'popb', 92, WHT, track=-.02, outline=((10, 10, 10), 3)),
    photo=ph(.5, .15, 1.0, .45), pb=(232, 230, 222), studio=['A FILM BY', 'MARTHA COOLIDGE'], scol=(214, 210, 200), order='lPTF',
    ft='b', fcol=(176, 172, 166), fin=OLD, seed=1976)

# Frantic (1988): Paris at night, black with bold white capitals, Harrison Ford mid-panic
std('frantic-1988', ('solid', (12, 12, 13)), WHT,
    L((0.10, 0.80, 0.90, 0.9), 104, WHT, mode='light', speck=.01),
    photo=ph(.33, .42, .62, .9), pb=(196, 40, 40), lg=None, lw=.36, order='LPTCSF', credit=['A ROMAN POLANSKI', 'FILM'], ccol=(196, 40, 40),
    stick=BAR('11 07762', top='THRILLER'), ft='b', fcol=(176, 174, 170), fin=RENTAL, seed=1988)

# Sacramento: road-trip blue sky, the poster's sunny yellow capitals
std('sacramento-2025', ('grad', [(0, (70, 186, 222)), (.6, (40, 130, 180)), (1, (18, 60, 96))]), (250, 212, 30),
    L((0.03, 0.195, 0.97, 0.28), 100, (252, 214, 32), mode='key', key=(250, 212, 30), t=(80, 160), speck=.01),
    photo=ph(.5, .63, 1.0, .65), pb=(252, 214, 32), studio=['A MICHAEL ANGARANO', 'FILM'], scol=WHT, order='lPTF',
    ft='e', fcol=WHT, fin=MINT, dotst=(['ROAD', 'TRIP'], (234, 80, 50)))

# The Assessment: a cold modernist house, Mondrian blocks at the head, hairline white capitals
std('the-assessment-2025', ('bands', [(0, .025, (200, 40, 36)), (.025, .05, (232, 190, 40)), (.05, .075, (40, 70, 160)), (.075, 1, (20, 22, 28))]), WHT,
    L([(0.44, 0.152, 0.56, 0.197), (0.13, 0.203, 0.87, 0.255)], 60, WHT, mode='light', speck=.01, grow=.1, gapf=.7),
    photo=ph(.5, .42, .45, 1.0), pb=WHT, lg=WHT, lw=.4, order='gLPTF', ft='b', fcol=(190, 194, 204), fin=MINT, top=40)

# Tombstone (1993): sun-bleached parchment, a dark spine for its white, red-shadowed title logo (Ian's image), the four of them walking out
std('tombstone-1993', ('grad', [(0, (60, 30, 22)), (.6, (26, 14, 10)), (1, (8, 5, 4))]), (236, 226, 210),
    Pic('logos/tombstone-1993-title.png', 110),
    photo=ph(.5, .4, .84, .7), pb=(200, 70, 50), lg=(236, 226, 210), lw=.6, order='LPTCSF', credit=['KURT RUSSELL', 'VAL KILMER'], ccol=(140, 30, 20),
    stick=BAR('27 06135', top='WESTERN', fill=(244, 236, 214)), ft='b', fcol=(220, 206, 186), fin=RENTAL, seed=1993)

# Hot Summer Nights: synthwave sunset, a hot-pink italic title with a neon glow (typeset: the poster's gradient lettering won't lift)
std('hot-summer-nights-2018', ('grad', [(0, (30, 22, 70)), (.5, (110, 30, 100)), (1, (40, 10, 40))]), (250, 120, 200),
    T('HOT SUMMER NIGHTS', 'herbi', 84, (255, 130, 206), outline=((70, 10, 70), 2.5), soft=((255, 80, 190), 8, .7), track=-.01),
    photo=ph(.5, .2, .6, .95), pb=(110, 220, 255), lg=WHT, lw=.8, order='LPTF', ft='a', vbox=(250, 120, 200), fcol=(220, 200, 240), fin=SLIP)

# Mountainhead: a glass lodge in the snow, tall white condensed capitals (typeset: the M melts into the snow behind it), the tech bros
std('mountainhead-2025', ('grad', [(0, (70, 84, 100)), (.5, (34, 42, 54)), (1, (12, 14, 20))]), WHT,
    T('MOUNTAINHEAD', 'hcnb', 116, WHT, squeeze=.78, track=.02),
    photo=ph(.5, .55, .8, 1.0), pb=(214, 222, 232), lg=WHT, lw=.6, order='LPTCF', credit=['A JESSE ARMSTRONG', 'FILM'], ccol=(150, 190, 230),
    ft='b', fcol=(190, 200, 214), fin=MINT)

# Black Bag: spy-thriller teal, the poster's hairline outlined capitals, Blanchett and Fassbender in shades
std('black-bag-2025', ('grad', [(0, (40, 98, 118)), (.6, (24, 64, 80)), (1, (8, 24, 32))]), WHT,
    T('BLACK BAG', 'adv', 92, (26, 74, 92), outline=(WHT, 1.6), track=.06),
    photo=ph(.6, .2, .7, .85), pb=(230, 200, 150), lg=WHT, lw=.8, order='LPTCF', credit=['A STEVEN SODERBERGH', 'FILM'], ccol=(230, 200, 150),
    ft='e', fcol=(214, 230, 236), fin=dict(MINT, gloss=.09))

# Ghost in the Shell (1995): a 90s anime rental, circuit teal, the white serif title (typeset: the poster's "IN THE" sits in a
# triangle that doesn't lift)
std('ghost-in-the-shell-1995', ('grad', [(0, (24, 70, 74)), (.6, (12, 36, 40)), (1, (4, 12, 14))]), WHT,
    T('GHOST IN THE SHELL', 'terb', 84, WHT, track=.02),
    photo=ph(.5, .42, .6, .9), pb=(236, 70, 60), lg=None, lw=.42, order='LPTCSF', credit=['ENGLISH', 'DUBBED'], ccol=(236, 70, 60),
    stick=BAR('ANI 0995', top='ANIME', fill=(236, 234, 224)), ft='a', vbox=(236, 70, 60), fcol=(190, 214, 214), fin=RENTAL, seed=1995)

# The Accountant: jigsaw-puzzle white, red condensed capitals (typeset: the poster's are on a slant), Affleck up top
std('the-accountant-2016', ('solid', (232, 232, 228)), (200, 26, 30),
    T('THE ACCOUNTANT', 'hcnb', 104, (200, 26, 30), squeeze=.84, bold=.6, track=-.01),
    photo=ph(.4, .15, .6, .85), pb=(30, 30, 32), lg=None, lw=.4, order='LPTCF', credit=['BEN AFFLECK', 'ANNA KENDRICK'], ccol=(30, 30, 32),
    ft='d', fcol=(30, 30, 32), fin=SLIP)

# Kneecap: acid-yellow faces on black, the hot-pink title with its butterfly
std('kneecap-2024', ('solid', (12, 12, 10)), (240, 60, 150),
    L((0.16, 0.44, 0.87, 0.62), 120, (246, 70, 160), mode='key', key=(238, 60, 150), t=(70, 150), speck=.01),
    photo=ph(.3, .14, .5, .9), pb=(236, 240, 40), lg=None, lw=.42, order='LPTSF', stick=RWD(fill=(236, 240, 40), ink=(12, 12, 10)),
    ft='a', vbox=(240, 60, 150), fcol=(236, 240, 40), fin=WORN)

# Y Tu Mamá También (2001): the lime green of the poster on black, condensed capitals (typeset: the poster's
# fade into the photo), the kiss at the head
std('y-tu-mama-tambien-2001', ('solid', (14, 16, 12)), (160, 210, 50),
    [T('Y TU MAMÁ', 'hcnb', 104, (160, 210, 50), squeeze=.84, bold=.5), T('TAMBIÉN', 'hcnb', 104, (160, 210, 50), squeeze=.84, bold=.5)],
    photo=ph(.62, .12, .6, .6), pb=(160, 210, 50), studio=['UNA PELÍCULA DE', 'ALFONSO CUARÓN'], scol=(214, 220, 200), order='lPTSF', tgap=10,
    stick=PRC(['SUBTITLED', '$2.99']), ft='b', fcol=(180, 186, 170), fin=RENTAL, seed=2001)

# Materialists: wedding-reception white, the tall blue serif
std('materialists-2025', ('solid', (247, 246, 241)), (40, 104, 170),
    L((0.18, 0.745, 0.82, 0.885), 112, (40, 104, 170), mode='key', key=(44, 110, 176), t=(60, 140), speck=.01),
    photo=ph(.5, .4, .8, .9), pb=(40, 104, 170), lg=(20, 20, 20), lw=.5, order='LPTCF', credit=['A CELINE SONG', 'FILM'], ccol=(40, 104, 170),
    ft='b', fcol=(30, 30, 34), fin=MINT, dotst=(['ROMANCE'], (210, 50, 60)))

# Crumb (1995): newsprint cream, the poster's fat red cartoon lettering in its black outline, Crumb in red engraving
std('crumb-1995', ('solid', (238, 230, 212)), (204, 62, 40),
    L((0.13, 0.105, 0.85, 0.285), 118, (206, 64, 42), mode='key', key=(204, 64, 44), t=(60, 130), speck=.01, outline=((24, 20, 18), 3)),
    photo=ph(.55, .52, .6, 1.0), pb=(24, 20, 18), studio=['A TERRY ZWIGOFF', 'FILM'], scol=(24, 20, 18), order='lPTCF',
    credit=['A DOCUMENTARY'], ccol=(204, 62, 40), ft='d', fcol=(24, 20, 18), fin=OLD, seed=1995)

# The Thursday Murder Club: the retirement village's dark wood-panelled games room, script and a red MURDER
std('the-thursday-murder-club-2025', ('grad', [(0, (44, 52, 40)), (.6, (24, 28, 22)), (1, (8, 10, 8))]), WHT,
    [T('The Thursday', 'cho', 66, WHT), TT([('MURDER', (214, 30, 36)), ('CLUB', WHT)], 'hcnb', 84, sp=.2)],
    photo=ph(.5, .3, .9, .7), pb=(214, 30, 36), lg=WHT, lw=.7, order='LPTCF', tgap=8, credit=['A CHRIS COLUMBUS', 'FILM'], ccol=(214, 190, 130),
    ft='a', vbox=(214, 30, 36), fcol=(210, 206, 196), fin=SLIP)

# Havoc: a city on fire at night, the poster's smashed white capitals
std('havoc-2025', ('grad', [(0, (40, 26, 18)), (.5, (90, 40, 16)), (1, (16, 10, 8))]), WHT,
    L((0.16, 0.585, 0.83, 0.785), 132, WHT, mode='light', cut=(.45, .75), speck=.002),
    photo=ph(.5, .15, .5, .8), pb=(240, 140, 50), lg=WHT, lw=.6, order='LPTCF', credit=['A GARETH EVANS', 'FILM'], ccol=(240, 140, 50),
    ft='a', vbox=(240, 140, 50), vink=(16, 10, 8), fcol=(214, 200, 186), fin=WORN)

# Play Dirty: blood-red brick, the poster's cream condensed capitals stepping down
std('play-dirty-2025', ('grad', [(0, (150, 30, 26)), (.6, (90, 18, 16)), (1, (30, 8, 6))]), (238, 228, 186),
    L([(0.16, 0.375, 0.50, 0.58), (0.47, 0.425, 0.86, 0.645)], 128, (240, 230, 190), mode='key', key=(236, 226, 180), t=(60, 140), speck=.01, gapf=.18),
    photo=ph(.25, .18, .5, .9), pb=(240, 230, 190), lg=None, lw=.3, order='LPTCF', credit=['A SHANE BLACK', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 230, 190), vink=(90, 18, 16), fcol=(240, 230, 190), fin=WORN)

# Relay: newsprint cream, the poster's navy condensed capitals, the two of them over the city
std('relay-2025', ('solid', (242, 234, 216)), (40, 50, 90),
    L((0.06, 0.755, 0.49, 0.89), 132, (40, 50, 90), mode='key', key=(44, 54, 92), t=(60, 140), speck=.01),
    photo=ph(.5, .35, .9, .7), pb=(40, 50, 90), lg=(40, 50, 90), lw=.84, order='LPTCF', credit=['A DAVID MACKENZIE', 'FILM'], ccol=(196, 70, 60),
    ft='d', fcol=(40, 50, 90), fin=SLIP)

# Caught Stealing: nicotine-mustard wall with bullet holes, yellow condensed capitals on a black plate
std('caught-stealing-2025', ('grad', [(0, (222, 168, 76)), (.6, (190, 132, 56)), (1, (90, 60, 26))]), (246, 206, 72),
    T('CAUGHT STEALING', 'hcnb', 92, (246, 206, 72), squeeze=.84, bold=.6, box=((20, 18, 16), 12, 10)),
    photo=ph(.5, .13, .5, .8), pb=(20, 18, 16), lg=(20, 18, 16), lw=.8, order='LPTCF', credit=['A DARREN ARONOFSKY', 'FILM'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), vink=(246, 206, 72), fcol=(20, 18, 16), fin=WORN)

# Honey Don't!: cream poster stock in a turquoise frame, the poster's hollow neon capitals
std('honey-don-t-2025', ('solid', (246, 234, 214)), (60, 186, 206),
    T("HONEY DON'T!", 'adv', 92, (246, 234, 214), outline=((40, 172, 198), 2.8), track=.04),
    photo=ph(.25, .3, .35, 1.3), pb=(60, 186, 206), lg=(40, 40, 44), lw=.7, order='LPTCF', credit=['AN ETHAN COEN', 'FILM'], ccol=(196, 60, 50),
    ft='e', fcol=(40, 40, 44), fin=MINT, under=[frame((60, 186, 206), 7, 2.4)])

# Friendship: pale winter sky, the poster's acid-yellow condensed capitals
std('friendship-2025', ('grad', [(0, (170, 200, 230)), (.6, (140, 172, 210)), (1, (90, 110, 150))]), (226, 250, 40),
    L((0.02, 0.11, 0.98, 0.275), 116, (230, 252, 44), mode='key', key=(226, 250, 40), t=(70, 150), speck=.01, outline=((30, 34, 60), 1.6)),
    photo=ph(.5, .55, .6, 1.0), pb=WHT, lg=(20, 22, 30), lw=.7, order='LPTF', ft='a', vbox=(20, 22, 30), vink=(226, 250, 40),
    fcol=(20, 22, 30), fin=MINT, dotst=(['COMEDY'], (234, 70, 60)))

# Perfect Days: Tokyo park shade, the poster's white condensed capitals, Hirayama looking up at the trees
std('perfect-days-2023', ('grad', [(0, (40, 54, 36)), (.6, (22, 30, 20)), (1, (8, 10, 8))]), WHT,
    L((0.14, 0.16, 0.86, 0.24), 96, WHT, mode='light', speck=.01),
    photo=ph(.5, .5, .6, .9), pb=(70, 100, 180), studio=['A WIM WENDERS', 'FILM'], scol=(214, 220, 206), order='lPTCF',
    credit=['KOJI YAKUSHO'], ccol=(150, 180, 230), ft='b', fcol=(190, 196, 184), fin=SLIP, dotst=(['STAFF', 'PICK'], (70, 100, 180)))

# Dìdi: 2008 bedroom green, the poster's orange title with its 弟弟
std('didi-2024', ('grad', [(0, (112, 128, 96)), (.6, (66, 78, 56)), (1, (24, 28, 20))]), (232, 150, 40),
    L((0.24, 0.12, 0.76, 0.235), 110, (238, 156, 44), mode='key', key=(230, 150, 44), t=(70, 150), speck=.01),
    photo=ph(.35, .7, .5, 1.0), pb=(238, 156, 44), lg=WHT, lw=.7, order='LPTCF', credit=['A SEAN WANG', 'FILM'], ccol=WHT,
    ft='e', fcol=(220, 226, 210), fin=SLIP)

# The Teachers' Lounge: classroom-wall teal, the white serif title
std('the-teachers-lounge-2023', ('grad', [(0, (34, 92, 118)), (.6, (18, 52, 70)), (1, (6, 18, 26))]), WHT,
    L([(0.11, 0.145, 0.27, 0.205), (0.11, 0.2, 0.91, 0.28)], 66, WHT, mode='light', speck=.01, gapf=.3),
    photo=ph(.5, .52, .5, 1.0), pb=(226, 190, 150), lg=WHT, lw=.5, order='LPTCF', credit=['EIN FILM VON', 'İLKER ÇATAK'], ccol=(226, 190, 150),
    ft='b', fcol=(200, 214, 220), fin=MINT)

# Snake Eyes (1998): casino purple, the scratched white SNAKE EYES title logo (Ian's image), Cage staring out
std('snake-eyes-1998', ('grad', [(0, (120, 70, 190)), (.5, (70, 40, 120)), (1, (20, 12, 36))]), WHT,
    Pic('logos/snake-eyes-1998-title.png', 116),
    photo=ph(.5, .12, .5, .8), pb=(90, 220, 70), lg=WHT, lw=.5, order='LPTCSF', credit=['NICOLAS CAGE', 'GARY SINISE'], ccol=(90, 220, 70),
    stick=BAR('32 08688', top='THRILLER'), ft='b', fcol=(200, 190, 220), fin=RENTAL, seed=1998)

# One Battle After Another: desert-highway sunset, white condensed capitals, DiCaprio and Willa up top
std('one-battle-after-another-2025', ('grad', [(0, (210, 100, 36)), (.5, (120, 40, 16)), (1, (30, 10, 6))]), WHT,
    [L((0.06, 0.79, 0.76, 0.86), 76, WHT, mode='light', speck=.01), L((0.12, 0.855, 0.95, 0.93), 76, WHT, mode='light', speck=.01)],
    photo=ph(.45, .35, .7, .9), pb=(250, 200, 120), lg=None, lw=.36, order='LPTCF', tgap=8,
    credit=['A PAUL THOMAS ANDERSON', 'FILM'], ccol=(250, 200, 120), ft='a', vbox=(250, 200, 120), vink=(30, 10, 6), fcol=(240, 214, 196),
    fin=SLIP, dotst=(['NEW', 'RELEASE'], (250, 200, 120), (30, 10, 6)))

# Companion: dusty rose, the poster's white script, Sophie Thatcher's one cold eye
std('companion-2025', ('grad', [(0, (200, 132, 140)), (.6, (140, 70, 84)), (1, (50, 20, 28))]), WHT,
    L((0.35, 0.435, 0.98, 0.56), 120, WHT, mode='light', cut=(.45, .75), speck=.01),
    photo=ph(.24, .405, .44, .55), pb=(250, 196, 206), lg=WHT, lw=.7, order='LPTCSF', credit=['A DREW HANCOCK', 'FILM'], ccol=(250, 214, 220),
    ft='a', vbox=(250, 196, 206), vink=(50, 20, 28), fcol=WHT, fin=dict(SLIP, gloss=.09), stick=flow(dot, 70, ['HORROR'], (30, 30, 34), d=64))

# Roofman: sunny yellow, the poster's royal-blue capitals, Tatum and the teddy bear
std('roofman-2025', ('solid', (250, 202, 44)), (30, 82, 200),
    L((0.14, 0.66, 0.86, 0.805), 124, (30, 82, 200), mode='key', key=(32, 84, 204), t=(70, 150), speck=.01),
    photo=ph(.5, .2, .6, .8), pb=(30, 82, 200), lg=None, lw=.3, order='LPTCF', credit=['A DEREK CIANFRANCE', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(30, 82, 200), fcol=(30, 30, 34), fin=SLIP)

# Night Stalker: a boxed docuseries, black with one red stripe, the poster's red brush lettering
std('night-stalker-the-hunt-for-a-serial-killer-2021', ('solid', (10, 10, 12)), (200, 40, 40),
    [L([(0.3, 0.695, 0.68, 0.775), (0.26, 0.77, 0.79, 0.865)], 104, (210, 40, 40), mode='key', key=(196, 40, 40), t=(70, 150), speck=.01, gapf=.25),
     T('THE HUNT FOR A SERIAL KILLER', 'hcnb', 26, (210, 40, 40), track=.12)],
    photo=ph(.45, .3, .6, 1.0), pb=(200, 40, 40), lg=WHT, lw=.8, order='LPTCF', tgap=12, credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(200, 196, 190),
    ft='b', fcol=(170, 170, 170), fin=SLIP)

# Spider-Man: Across the Spider-Verse: comic-book magenta and violet, the film's own title logo (Ian's image), Miles up top
std('spider-man-across-the-spider-verse-2023', ('grad', [(0, (240, 80, 150)), (.4, (120, 40, 150)), (1, (20, 12, 50))]), (232, 30, 40),
    Pic('logos/spider-man-across-the-spider-verse-2023-title.png', 130),
    photo=ph(.4, .35, .5, 1.0), pb=(250, 220, 60), lg=WHT, lw=.7, order='LPTF', tgap=14, ft='a', vbox=(232, 30, 40), fcol=WHT,
    fin=dict(SLIP, gloss=.09), dotst=(['ANIMATED'], (250, 220, 60), (20, 12, 50)))

# Gone Girls: The Long Island Serial Killer: a boxed docuseries, Gilgo Beach at night, police lights in the fog
std('gone-girls-the-long-island-serial-killer-2025', ('grad', [(0, (34, 66, 76)), (.5, (14, 28, 34)), (1, (4, 6, 8))]), WHT,
    [L((0.02, 0.67, 0.97, 0.755), 76, WHT, mode='light', speck=.01), L((0.02, 0.755, 0.97, 0.805), 34, WHT, mode='light', speck=.01)],
    photo=ph(.6, .32, .8, .8), pb=(220, 50, 50), lg=None, lw=.8, order='LPTCF', tgap=10, credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(220, 60, 60),
    ft='b', fcol=(170, 186, 190), fin=MINT)

# Who Took Johnny (2014): a library copy of a true-crime documentary, concrete grey, the poster's distressed red capitals
std('who-took-johnny-2014', ('grad', [(0, (90, 84, 78)), (.6, (52, 48, 44)), (1, (20, 18, 16))]), (220, 50, 40),
    L([(0.02, 0.33, 0.54, 0.52), (0.02, 0.52, 0.62, 0.735), (0.02, 0.735, 0.98, 0.94)], 124, (224, 54, 44), mode='key', key=(214, 50, 44), t=(70, 150), speck=.01, gapf=.18),
    photo=ph(.7, .38, .36, 1.2), pb=(236, 232, 222), studio=['A DOCUMENTARY BY', 'BEILINSON, GALINSKY', '& HAWLEY'], scol=(220, 214, 204), order='lPTSF',
    stick=BAR('364.15 WHO', top='PUBLIC LIBRARY', fill=(236, 234, 224)), ft='b', fcol=(190, 184, 176), fin=OLD, seed=2014)

# The Disappearance of Madeleine McCann: a boxed docuseries, the Algarve sand and the shadow on it (title typeset in
# a geometric sans like the poster's, which breaks up over the surf when lifted)
std('the-disappearance-of-madeleine-mccann-2019', ('grad', [(0, (182, 156, 114)), (.6, (122, 102, 72)), (1, (40, 34, 24))]), WHT,
    [T('THE DISAPPEARANCE OF', 'advb', 26, WHT, track=.08), T('MADELEINE McCANN', 'adv', 66, WHT, track=.04, bold=.4)],
    photo=ph(.3, .62, .45, 1.1), pb=WHT, lg=WHT, lw=.7, order='LPTCF', tgap=10, credit=['THE COMPLETE', 'DOCUSERIES'], ccol=WHT,
    ft='b', fcol=(250, 244, 230), fin=MINT)

# The Carman Family Deaths: night sea, wide white capitals, the boat from above
std('the-carman-family-deaths-2025', ('grad', [(0, (12, 26, 40)), (.6, (6, 14, 22)), (1, (2, 4, 8))]), WHT,
    [L((0.1, 0.695, 0.92, 0.77), 58, WHT, mode='light', speck=.01), L((0.02, 0.77, 0.99, 0.84), 58, WHT, mode='light', speck=.01)],
    photo=ph(.45, .25, .5, 1.2), pb=(150, 200, 230), lg=None, lw=.7, order='LPTCF', tgap=10, credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=(150, 200, 230),
    ft='b', fcol=(170, 186, 200), fin=MINT)

# Bad Timing (1980): the poster's yellow-ochre Klimt-ish painting, oxblood condensed capitals
std('bad-timing-1980', ('solid', (240, 232, 214)), (110, 28, 28),
    L((0.19, 0.895, 0.81, 0.995), 116, (112, 28, 28), mode='key', key=(110, 30, 30), t=(70, 150), speck=.01),
    photo=ph(.5, .4, .8, 1.0), pb=(110, 28, 28), lg=(110, 28, 28), lw=.3, order='LPTCSF', credit=['A NICOLAS ROEG', 'FILM'], ccol=(110, 28, 28),
    stick=PRC(['ADULTS', 'ONLY']), ft='d', fcol=(110, 28, 28), fin=OLD, seed=1980)

# Carmel: Who Killed María Marta?: a boxed docuseries, faded-photo grey, wide-spaced white capitals
std('carmel-who-killed-maria-marta-2020', ('grad', [(0, (100, 94, 86)), (.6, (56, 52, 48)), (1, (20, 18, 16))]), WHT,
    [L((0.02, 0.67, 0.98, 0.765), 70, WHT, mode='light', speck=.01), T('¿QUIÉN MATÓ A MARÍA MARTA?', 'hcnb', 28, (230, 220, 200), track=.1)],
    photo=ph(.5, .33, .6, 1.0), pb=(236, 230, 214), lg=WHT, lw=.8, order='LPTCF', tgap=12, credit=['LA SERIE', 'COMPLETA'], ccol=(230, 220, 200),
    ft='b', fcol=(190, 184, 176), fin=SLIP)

# Sophie: A Murder in West Cork: a boxed docuseries, Atlantic cliff green and storm grey, white serif capitals
std('sophie-a-murder-in-west-cork-2021', ('grad', [(0, (96, 116, 116)), (.5, (58, 74, 64)), (1, (20, 28, 22))]), WHT,
    [L((0.26, 0.1, 0.74, 0.17), 84, WHT, mode='light', speck=.01), T('A MURDER IN WEST CORK', 'ter', 28, WHT, track=.2)],
    photo=ph(.5, .55, .5, 1.2), pb=(236, 232, 220), lg=WHT, lw=.8, order='LPTCF', tgap=12, credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(214, 224, 214),
    ft='b', fcol=(200, 210, 204), fin=MINT)

# Love Liza (2002): headlight streaks and petrol-green night, white condensed capitals
std('love-liza-2002', ('grad', [(0, (40, 46, 20)), (.4, (70, 80, 30)), (1, (10, 12, 6))]), WHT,
    L((0.29, 0.43, 0.99, 0.535), 116, WHT, mode='light', speck=.01),
    photo=ph(.15, .48, .3, 1.0), pb=(236, 214, 70), lg=WHT, lw=.7, order='LPTCSF', credit=['PHILIP SEYMOUR', 'HOFFMAN'], ccol=(236, 214, 70),
    stick=RWD(fill=(236, 214, 70)), ft='b', fcol=(196, 200, 180), fin=RENTAL, seed=2002)

# I'm Still Here: Rio summer sky, wide geometric white capitals like the poster's stacked ones, the Paiva family on the beach
std('i-m-still-here-2024', ('grad', [(0, (116, 168, 210)), (.6, (70, 110, 140)), (1, (30, 40, 46))]), WHT,
    T('I’M STILL HERE', 'advb', 80, WHT, track=.16),
    photo=ph(.5, .68, 1.0, .6), pb=WHT, lg=WHT, lw=.8, order='LPTCF', credit=['UM FILME DE', 'WALTER SALLES'], ccol=(250, 230, 190),
    ft='e', fcol=WHT, fin=MINT, dotst=(['STAFF', 'PICK'], (230, 190, 50), (30, 40, 46)))

# Sorry, Baby: pale summer sky, the navy serif, Eva Victor and the kitten
std('sorry-baby-2025', ('grad', [(0, (204, 224, 242)), (.6, (170, 196, 222)), (1, (110, 136, 166))]), (30, 40, 90),
    L((0.08, 0.5, 0.89, 0.61), 112, (30, 40, 90), mode='key', key=(32, 42, 92), t=(70, 150), speck=.01),
    photo=ph(.45, .82, .8, .6), pb=(30, 40, 90), lg=(30, 40, 90), lw=.6, order='LPTCF', credit=['AN EVA VICTOR', 'FILM'], ccol=(30, 40, 90),
    ft='e', fcol=(30, 40, 90), fin=MINT)

# Wake Up Dead Man: a candlelit church, the white blackletter, the suspects lined up
std('wake-up-dead-man-a-knives-out-mystery-2025', ('grad', [(0, (40, 32, 26)), (.6, (20, 16, 14)), (1, (6, 4, 4))]), WHT,
    [L([(0.26, 0.18, 0.74, 0.27), (0.26, 0.265, 0.74, 0.355)], 104, WHT, mode='light', speck=.01, gapf=.3),
     T('A KNIVES OUT MYSTERY', 'ter', 26, (214, 180, 110), track=.24)],
    photo=ph(.5, .62, 1.0, .6), pb=(214, 180, 110), lg=WHT, lw=.8, order='LPTCF', tgap=12, credit=['A RIAN JOHNSON', 'FILM'], ccol=(214, 180, 110),
    ft='a', vbox=(214, 180, 110), vink=(20, 16, 14), fcol=(214, 206, 196), fin=SLIP, dotst=(['NEW', 'RELEASE'], (180, 30, 30)))

# The Mastermind: 1970 newsprint cream, heavy black stencil capitals with the poster's green shadow,
# the drawn J.B. up top
std('the-mastermind-2025', ('solid', (240, 230, 210)), (24, 24, 22),
    T('THE MASTERMIND', 'intbk', 84, (24, 24, 22), shadow=((50, 140, 80), 3, 3), track=-.02),
    photo=ph(.75, .18, .45, 1.0), pb=(24, 24, 22), lg=(24, 24, 22), lw=.8, order='LPTCF', credit=['A KELLY REICHARDT', 'FILM'], ccol=(50, 140, 80),
    ft='d', fcol=(24, 24, 22), fin=SLIP)

# Predators: a small-town street at night in green-teal murk, the small white serif title
std('predators-2025', ('grad', [(0, (26, 56, 56)), (.6, (12, 26, 26)), (1, (4, 8, 8))]), WHT,
    L((0.27, 0.705, 0.73, 0.765), 76, WHT, mode='light', speck=.01),
    photo=ph(.4, .45, .8, .8), pb=(236, 190, 90), studio=['A DAVID OSIT', 'FILM'], scol=(200, 214, 210), order='lPTCF',
    credit=['A DOCUMENTARY'], ccol=(236, 190, 90), ft='b', fcol=(170, 186, 182), fin=MINT)

# Murder in Monaco: the burning penthouse, white condensed capitals (typeset: the flames behind them won't key out)
std('murder-in-monaco-2025', ('grad', [(0, (60, 40, 20)), (.5, (150, 70, 16)), (1, (20, 10, 6))]), WHT,
    TT([('MURDER', WHT), ('in', (240, 190, 80)), ('MONACO', WHT)], 'hcnb', 104, sp=.18, squeeze=.78),
    photo=ph(.5, .3, .5, 1.0), pb=(240, 190, 80), lg=WHT, lw=.4, order='LPTCF', credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=(240, 190, 80),
    ft='b', fcol=(220, 206, 190), fin=MINT)

# One False Move (1992): Arkansas dusk in purple and pink, the poster's towering condensed capitals
std('one-false-move-1992', ('grad', [(0, (140, 80, 150)), (.5, (90, 50, 110)), (1, (20, 14, 30))]), (236, 190, 216),
    T('ONE FALSE MOVE', 'hcnb', 120, (236, 190, 216), squeeze=.8, bold=.6),
    photo=ph(.55, .86, .7, .35), pb=(236, 190, 216), studio=['A CARL FRANKLIN', 'FILM'], scol=(236, 214, 226), order='lPTCSF',
    credit=['BILL PAXTON', 'BILLY BOB THORNTON'], ccol=WHT, stick=BAR('19 21128', top='THRILLER'), ft='b', fcol=(210, 190, 214), fin=RENTAL, seed=1992)

# Dave Chappelle: The Unstoppable...: a comedy special, black stage and one spotlight, white and red condensed capitals
std('dave-chappelle-the-unstoppable-2025', ('grad', [(0, (40, 40, 44)), (.3, (14, 14, 16)), (1, (6, 6, 6))]), WHT,
    [T('DAVE CHAPPELLE', 'hcnb', 92, WHT, squeeze=.84, bold=.5), T('THE UNSTOPPABLE...', 'hcnb', 44, (220, 24, 30), squeeze=.84, bold=.5)],
    photo=ph(.5, .46, .32, 1.5), pb=(220, 24, 30), studio=['STAND-UP', 'SPECIAL'], scol=(220, 24, 30), order='lPTF', tgap=10,
    ft='b', fcol=(180, 180, 180), fin=SLIP)

# Eternity: the afterlife's blue sky and clouds, the poster's fat yellow serif
std('eternity-2025', ('grad', [(0, (130, 186, 232)), (.6, (90, 140, 196)), (1, (40, 66, 110))]), (252, 204, 20),
    L((0.07, 0.715, 0.94, 0.9), 124, (252, 206, 24), mode='key', key=(250, 200, 20), t=(70, 150), speck=.01, outline=((40, 50, 90), 1.6)),
    photo=ph(.5, .42, .9, .7), pb=WHT, lg=(20, 20, 20), lw=.5, order='LPTCF', credit=['A DAVID FREYNE', 'FILM'], ccol=WHT,
    ft='e', fcol=WHT, fin=MINT, dotst=(['ROMANCE'], (230, 70, 90)))

# Ricky Gervais: Mortality: a comedy special, studio slate blue, white condensed capitals, Ricky in his black wings
std('ricky-gervais-mortality-2025', ('grad', [(0, (110, 140, 170)), (.5, (60, 82, 104)), (1, (16, 22, 30))]), WHT,
    [L((0.04, 0.035, 0.96, 0.155), 84, WHT, mode='light', speck=.01), L((0.24, 0.805, 0.79, 0.915), 84, WHT, mode='light', speck=.01)],
    photo=ph(.5, .47, .7, 1.0), pb=WHT, studio=['STAND-UP', 'SPECIAL'], scol=WHT, order='lPTF', tgap=10, ft='b', fcol=(200, 214, 226), fin=SLIP)


# =====================================================================================
# the 2024 shelf (films-2024.json).  Same approach as 2025: lettering boxes given directly
# (checked with check_boxes.py), typeset where the lettering won't lift.
# =====================================================================================

# Four Daughters: Tunisian teal, the white serif title, the mother and her daughters
std('four-daughters-2023', ('grad', [(0, (30, 86, 104)), (.6, (16, 48, 60)), (1, (6, 16, 20))]), WHT,
    [L((0.17, 0.115, 0.48, 0.21), 84, WHT, mode='light', speck=.01), L((0.17, 0.225, 0.82, 0.33), 84, WHT, mode='light', speck=.01)],
    photo=ph(.5, .76, 1.0, .55), pb=(226, 214, 190), lg=WHT, lw=.4, order='LPTCF', tgap=8, credit=['A FILM BY', 'KAOUTHER BEN HANIA'], ccol=(226, 214, 190),
    ft='b', fcol=(190, 206, 210), fin=MINT)

# Past Lives: subway-car teal, hairline tracked capitals (typeset: too thin to lift off the photo)
std('past-lives-2023', ('grad', [(0, (70, 100, 106)), (.6, (36, 52, 56)), (1, (12, 16, 18))]), WHT,
    T('PAST LIVES', 'adv', 76, WHT, track=.32),
    photo=ph(.84, .45, .3, 1.0), pb=(236, 230, 214), lg=WHT, lw=.5, order='LPTCF', credit=['A CELINE SONG', 'FILM'], ccol=(236, 214, 170),
    ft='b', fcol=(200, 210, 212), fin=MINT, dotst=(['STAFF', 'PICK'], (236, 190, 60), (20, 26, 28)))

# Saltburn: oxblood and decadence, the poster's yellow blackletter
std('saltburn-2023', ('grad', [(0, (120, 22, 26)), (.6, (64, 10, 14)), (1, (18, 4, 6))]), (244, 224, 40),
    L((0.13, 0.765, 0.87, 0.895), 108, (246, 228, 44), mode='key', key=(240, 222, 40), t=(70, 150), speck=.01),
    photo=ph(.5, .32, .9, .8), pb=(244, 224, 40), lg=WHT, lw=.8, order='LPTCF', credit=['AN EMERALD FENNELL', 'FILM'], ccol=(244, 224, 40),
    ft='a', vbox=(244, 224, 40), vink=(64, 10, 14), fcol=(230, 210, 200), fin=dict(SLIP, gloss=.09))

# Wonka: chocolate-shop plum, the gold Wonka script logo (Ian's image)
std('wonka-2023', ('grad', [(0, (130, 24, 64)), (.6, (70, 12, 40)), (1, (24, 6, 16))]), (244, 196, 70),
    Pic('logos/wonka-2023-title.png', 170),
    photo=ph(.6, .2, .5, 1.0), pb=(244, 196, 70), lg=None, lw=.36, order='LPTCF', credit=['TIMOTHÉE', 'CHALAMET'], ccol=(250, 220, 160),
    ft='a', vbox=(244, 196, 70), vink=(70, 12, 40), fcol=(240, 214, 200), fin=SLIP, dotst=(['FAMILY'], (244, 196, 70), (70, 12, 40)))

# Sanctuary: hotel-room red, gold tracked Roman capitals (typeset: thin, over the photo)
std('sanctuary-2023', ('grad', [(0, (196, 36, 36)), (.6, (120, 18, 20)), (1, (36, 6, 6))]), (226, 190, 90),
    T('SANCTUARY', 'ter', 76, (230, 196, 96), track=.3, bold=.5),
    photo=ph(.5, .35, .9, .8), pb=(230, 196, 96), lg=WHT, lw=.7, order='LPTCF', credit=['MARGARET QUALLEY', 'CHRISTOPHER ABBOTT'], ccol=WHT,
    ft='e', fcol=(240, 214, 200), fin=SLIP)

# Anyone But You: Sydney Harbour blue, white condensed capitals (typeset: the sky behind is nearly white)
std('anyone-but-you-2023', ('grad', [(0, (110, 176, 224)), (.6, (50, 110, 170)), (1, (16, 40, 70))]), WHT,
    T('ANYONE BUT YOU', 'hcnb', 110, WHT, squeeze=.82, bold=.6),
    photo=ph(.5, .45, .8, .8), pb=WHT, lg=WHT, lw=.7, order='LPTF', ft='a', vbox=(230, 70, 80), fcol=WHT, fin=MINT,
    dotst=(['ROMANCE'], (230, 70, 80)))

# The Killing of Two Lovers: winter Utah grey, condensed bold serif capitals (typeset: stacked with a small THE and OF)
std('the-killing-of-two-lovers-2021', ('grad', [(0, (110, 114, 118)), (.6, (60, 62, 66)), (1, (18, 18, 20))]), WHT,
    [T('THE KILLING OF', 'dsc', 64, WHT, squeeze=.86), T('TWO LOVERS', 'dsc', 64, WHT, squeeze=.86)],
    photo=ph(.5, .85, 1.0, .5), pb=(230, 226, 218), studio=['A ROBERT MACHOIAN', 'FILM'], scol=WHT, order='lPTF', tgap=8,
    ft='b', fcol=(200, 200, 200), fin=SLIP)

# Lover, Stalker, Killer: cold green-black, a knife through a phone, the white three-word title
std('lover-stalker-killer-2024', ('grad', [(0, (30, 70, 64)), (.5, (12, 28, 26)), (1, (4, 6, 6))]), WHT,
    L((0.03, 0.775, 0.97, 0.865), 72, WHT, mode='light', speck=.01),
    photo=ph(.5, .42, .6, 1.0), pb=(214, 50, 60), lg=WHT, lw=.8, order='LPTCF', credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=(214, 50, 60),
    ft='b', fcol=(180, 196, 192), fin=MINT)

# Poor Things: watercolour sky, the hand-drawn black capitals, Bella in her puffed sleeves
std('poor-things-2023', ('grad', [(0, (214, 224, 236)), (.6, (190, 204, 220)), (1, (130, 140, 160))]), (26, 26, 30),
    L((0.03, 0.04, 0.46, 0.205), 150, (26, 26, 30), mode='dark', speck=.01, grow=.3),
    photo=ph(.5, .42, .4, 1.0), pb=(26, 26, 30), lg=(26, 26, 30), lw=.8, order='LPTCF', credit=['A YORGOS LANTHIMOS', 'FILM'], ccol=(150, 40, 60),
    ft='d', fcol=(26, 26, 30), fin=MINT, dotst=(['STAFF', 'PICK'], (150, 40, 60)))

# American Fiction: slate navy, the poster's pale-pink capitals, Monk in his gold-outlined "costume"
std('american-fiction-2023', ('grad', [(0, (52, 66, 96)), (.6, (30, 38, 60)), (1, (10, 12, 22))]), (244, 176, 176),
    L((0.05, 0.865, 0.95, 0.95), 72, (246, 180, 178), mode='key', key=(240, 172, 172), t=(60, 140), speck=.01),
    photo=ph(.5, .3, .6, 1.0), pb=(226, 190, 90), lg=WHT, lw=.6, order='LPTCF', credit=['A CORD JEFFERSON', 'FILM'], ccol=(226, 190, 90),
    ft='a', vbox=(244, 176, 176), vink=(30, 38, 60), fcol=(210, 214, 226), fin=SLIP)

# The Zone of Interest: black above, the Höss garden's green below, white condensed capitals
std('the-zone-of-interest-2023', ('grad', [(0, (8, 8, 8)), (.6, (10, 12, 10)), (1, (34, 60, 30))]), WHT,
    L((0.06, 0.285, 0.94, 0.365), 76, WHT, mode='light', speck=.01),
    photo=ph(.5, .86, 1.0, .4), pb=(200, 200, 196), lg=WHT, lw=.5, order='LPTCF', credit=['A JONATHAN GLAZER', 'FILM'], ccol=(200, 200, 196),
    ft='b', fcol=(170, 170, 166), fin=MINT)

# Ricky Stanicky: studio-comedy white, the poster's tall orange capitals
std('ricky-stanicky-2024', ('solid', (246, 244, 240)), (246, 130, 30),
    L([(0.29, 0.085, 0.69, 0.2), (0.2, 0.195, 0.77, 0.32)], 120, (246, 132, 32), mode='key', key=(246, 130, 30), t=(70, 150), speck=.01, gapf=.2),
    photo=ph(.5, .62, 1.0, .5), pb=(246, 132, 32), lg=(30, 30, 34), lw=.7, order='LPTCF', credit=['A PETER FARRELLY', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(246, 132, 32), fcol=(30, 30, 34), fin=MINT, dotst=(['COMEDY'], (40, 120, 200)))

# Road House: a Keys bar after dark, the neon Road House script logo (Ian's image)
std('road-house-2024', ('grad', [(0, (30, 44, 50)), (.6, (16, 22, 26)), (1, (6, 8, 10))]), (120, 236, 246),
    Pic('logos/road-house-title.png', 150),
    photo=ph(.5, .42, .5, 1.0), pb=(120, 236, 246), lg=WHT, lw=.4, order='LPTCF', credit=['JAKE GYLLENHAAL'], ccol=(120, 236, 246),
    ft='a', vbox=(120, 236, 246), vink=(16, 22, 26), fcol=(196, 210, 214), fin=SLIP)

# Argylle: navy argyle, the poster's gold dotted capitals
std('argylle-2024', ('grad', [(0, (40, 52, 120)), (.6, (22, 28, 70)), (1, (8, 10, 24))]), (226, 186, 96),
    L((0.14, 0.81, 0.86, 0.895), 76, (230, 192, 100), mode='key', key=(220, 180, 92), t=(70, 160), speck=.005),
    photo=ph(.5, .42, 1.0, .6), pb=(226, 186, 96), lg=WHT, lw=.5, order='LPTCF', credit=['A MATTHEW VAUGHN', 'FILM'], ccol=(226, 186, 96),
    ft='a', vbox=(226, 186, 96), vink=(22, 28, 70), fcol=(200, 206, 230), fin=SLIP, under=[frame((226, 186, 96), 8, 1.2)])

# Snack Shack: summer-pool blue, the yellow-and-red title logo (Ian's image)
std('snack-shack-2024', ('grad', [(0, (70, 180, 214)), (.6, (34, 120, 160)), (1, (14, 50, 70))]), (252, 220, 50),
    Pic('logos/snack-shack-2024-title.png', 100),
    photo=ph(.5, .12, 1.0, .45), pb=WHT, lg=WHT, lw=.8, order='LPTCSF', credit=['AN ADAM REHMEIER', 'FILM'], ccol=WHT,
    stick=RWD(fill=(252, 222, 54)), ft='a', vbox=(200, 30, 30), fcol=WHT, fin=WORN)

# Asphalt City: ambulance white and siren red, condensed red capitals
std('asphalt-city-2024', ('solid', (230, 228, 226)), (204, 40, 32),
    L((0.06, 0.835, 0.58, 0.905), 104, (206, 42, 34), mode='key', key=(200, 40, 32), t=(70, 150), speck=.01),
    photo=ph(.47, .17, .4, 1.0), pb=(204, 40, 32), lg=None, lw=.36, order='LPTCF', credit=['SEAN PENN', 'TYE SHERIDAN'], ccol=(30, 30, 34),
    ft='a', vbox=(204, 40, 32), fcol=(30, 30, 34), fin=SLIP)

# Love Lies Bleeding: 1989 gym-motel dark, the hot-red italic capitals (typeset: the poster's step down at an angle)
std('love-lies-bleeding-2024', ('grad', [(0, (60, 12, 40)), (.5, (28, 6, 20)), (1, (8, 2, 6))]), (250, 40, 80),
    T('LOVE LIES BLEEDING', 'herbi', 84, (250, 44, 84), track=-.01),
    photo=ph(.5, .3, .6, 1.0), pb=(250, 44, 84), lg=WHT, lw=.7, order='LPTCF', credit=['A ROSE GLASS', 'FILM'], ccol=(250, 180, 200),
    ft='a', vbox=(250, 44, 84), fcol=(220, 200, 210), fin=SLIP)

# Challengers: violet like her sunglasses, wide Roman capitals (typeset: the poster's are striped)
std('challengers-2024', ('grad', [(0, (140, 70, 170)), (.6, (80, 36, 110)), (1, (24, 10, 36))]), WHT,
    T('CHALLENGERS', 'terb', 80, WHT, track=.16),
    photo=ph(.5, .32, .8, .6), pb=(250, 230, 120), lg=WHT, lw=.8, order='LPTCF', credit=['A LUCA GUADAGNINO', 'FILM'], ccol=(250, 230, 120),
    ft='e', fcol=WHT, fin=dict(MINT, gloss=.09))

# Red Rooms: a dark-web screen glow, the poster's red condensed capitals
std('red-rooms-2023', ('grad', [(0, (60, 24, 18)), (.6, (30, 12, 10)), (1, (8, 4, 4))]), (214, 70, 50),
    L((0.21, 0.715, 0.79, 0.835), 112, (220, 76, 54), mode='key', key=(196, 70, 50), t=(70, 150), speck=.01),
    photo=ph(.5, .42, .6, 1.0), pb=(214, 70, 50), lg=WHT, lw=.8, order='LPTCF', credit=['UN FILM DE', 'PASCAL PLANTE'], ccol=(214, 160, 140),
    ft='b', fcol=(190, 170, 160), fin=SLIP)

# Reunion: police-tape red, the white heavy capitals, the class of whatever behind the tape
std('reunion-2024', ('grad', [(0, (220, 34, 34)), (.6, (150, 16, 18)), (1, (60, 6, 8))]), WHT,
    L((0.09, 0.705, 0.91, 0.795), 92, WHT, mode='key', key=(250, 250, 250), t=(40, 110), speck=.01),
    photo=ph(.5, .33, 1.0, .4), pb=(250, 220, 40), lg=WHT, lw=.8, order='LPTSF', stick=BAR('47 15338', top='COMEDY', fill=(250, 220, 40)),
    ft='a', vbox=(250, 220, 40), vink=(150, 16, 18), fcol=WHT, fin=SLIP)

# South Park: The End of Obesity: a TV-movie special, the show's construction-paper cream, black slab and a red OBESITY
std('south-park-the-end-of-obesity-2024', ('solid', (250, 244, 204)), (20, 20, 20),
    [T('SOUTH PARK', 'bonb', 64, (20, 20, 20), bold=.6), TT([('THE END OF', (20, 20, 20)), ('OBESITY', (220, 30, 30))], 'hcnb', 64, sp=.25)],
    photo=ph(.4, .72, .6, 1.0), pb=(20, 20, 20), lg=None, lw=.6, order='LPTCF', tgap=8, credit=['A TV SPECIAL'], ccol=(220, 30, 30),
    ft='d', fcol=(20, 20, 20), fin=SLIP)

# Pizza, Beer, and Cigarettes (1998): sun-faded Buenos Aires, orange condensed capitals on black plates (typeset)
std('pizza-beer-and-cigarettes-1998', ('grad', [(0, (210, 170, 96)), (.6, (150, 110, 56)), (1, (60, 40, 20))]), (244, 150, 30),
    T('PIZZA, BIRRA, FASO', 'hcnb', 92, (246, 156, 34), squeeze=.84, bold=.6, box=((18, 16, 14), 12, 9)),
    photo=ph(.5, .77, .8, .6), pb=(18, 16, 14), lg=(18, 16, 14), lw=.4, order='LPTCSF', credit=['UNA PELÍCULA DE', 'CAETANO Y STAGNARO'], ccol=(18, 16, 14),
    stick=PRC(['ESTRENO', '$3']), ft='b', fcol=(30, 22, 14), fin=RENTAL, seed=1998)

# Red Rocket: a Texas-motel cream, the red script, Mikey in the doughnut float
std('red-rocket-2021', ('solid', (246, 242, 234)), (214, 32, 44),
    L((0.14, 0.715, 0.91, 0.855), 124, (216, 34, 46), mode='key', key=(210, 30, 40), t=(70, 150), speck=.01),
    photo=ph(.5, .42, .6, 1.0), pb=(214, 32, 44), lg=(30, 30, 34), lw=.8, order='LPTCF', credit=['A SEAN BAKER', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(214, 32, 44), fcol=(30, 30, 34), fin=SLIP, dotst=(['STAFF', 'PICK'], (240, 120, 170)))

# Purple Noon (1960): old Titanus cream, navy-violet capitals, Delon in profile over the forged signature
std('purple-noon-1960', ('solid', (240, 236, 226)), (52, 60, 110),
    L((0.07, 0.16, 0.93, 0.24), 80, (52, 60, 110), mode='key', key=(50, 60, 110), t=(70, 150), speck=.01),
    photo=ph(.35, .45, .6, 1.0), pb=(52, 60, 110), lg=(52, 60, 110), lw=.4, order='LPTCSF', credit=['ALAIN DELON', 'A FILM BY RENÉ CLÉMENT'], ccol=(120, 60, 120),
    stick=PRC(['CLASSIC', '$1.99']), ft='d', fcol=(52, 60, 110), fin=OLD, seed=1960)

# Faults: midnight navy, the poster's acid-yellow condensed capitals (typeset: they're stacked on the split face)
std('faults-2014', ('grad', [(0, (24, 34, 80)), (.6, (14, 20, 50)), (1, (4, 6, 16))]), (226, 230, 44),
    T('FAULTS', 'hcnb', 150, (226, 230, 44), squeeze=.78, bold=.6, track=.06),
    photo=ph(.25, .3, .4, 1.0), pb=(226, 230, 44), lg=WHT, lw=.6, order='LPTCF', credit=['A RILEY STEARNS', 'FILM'], ccol=(226, 230, 44),
    ft='b', fcol=(180, 190, 220), fin=WORN)

# Searching: laptop-screen dark, the poster's red lower-case
std('searching-2018', ('grad', [(0, (24, 32, 44)), (.6, (14, 18, 26)), (1, (4, 6, 8))]), (232, 34, 34),
    L((0.07, 0.075, 0.91, 0.175), 112, (234, 38, 38), mode='key', key=(230, 30, 30), t=(70, 150), speck=.01),
    photo=ph(.5, .45, .6, 1.0), pb=(200, 214, 230), lg=WHT, lw=.8, order='LPTCF', credit=['JOHN CHO'], ccol=(200, 214, 230),
    ft='b', fcol=(170, 180, 196), fin=SLIP)

# Wyrm: desert sky over a bus stop, fat capitals graded violet to pink like the poster's
std('wyrm-2019', ('grad', [(0, (150, 196, 226)), (.6, (210, 200, 170)), (1, (200, 170, 120))]), (120, 60, 170),
    T('WYRM', 'intbk', 150, (120, 60, 170), grad=[(0, (110, 60, 180)), (1, (226, 80, 150))], track=-.04),
    photo=ph(.5, .78, .7, .6), pb=(120, 60, 170), studio=['A CHRISTOPHER', 'WINTERBAUER FILM'], scol=(60, 40, 80), order='lPTCF',
    credit=['A COMEDY'], ccol=(200, 60, 120), ft='e', fcol=(60, 40, 80), fin=MINT)

# Puss in Boots: The Last Wish: a fairy-tale night, the poster's gold storybook capitals
std('puss-in-boots-the-last-wish-2022', ('grad', [(0, (40, 30, 70)), (.5, (90, 40, 30)), (1, (20, 10, 10))]), (240, 186, 60),
    [L((0.03, 0.8, 0.97, 0.9), 84, (244, 192, 66), mode='key', key=(232, 176, 60), t=(70, 160), speck=.01),
     T('THE LAST WISH', 'terb', 26, WHT, track=.3)],
    photo=ph(.38, .35, .5, 1.0), pb=(240, 186, 60), lg=WHT, lw=.7, order='LPTF', tgap=10, ft='a', vbox=(240, 186, 60), vink=(40, 30, 70),
    fcol=(230, 214, 200), fin=SLIP, dotst=(['FAMILY'], (240, 186, 60), (40, 30, 70)))

# All of Us Strangers: London-at-night blue, the poster's pale-pink condensed capitals
std('all-of-us-strangers-2023', ('grad', [(0, (24, 46, 76)), (.6, (12, 24, 42)), (1, (4, 8, 14))]), (244, 204, 226),
    [L((0.2, 0.705, 0.8, 0.785), 56, (246, 208, 228), mode='key', key=(240, 200, 222), t=(60, 140), speck=.01),
     L((0.09, 0.785, 0.91, 0.905), 76, (246, 208, 228), mode='key', key=(240, 200, 222), t=(60, 140), speck=.01)],
    photo=ph(.6, .3, .7, .7), pb=(244, 204, 226), lg=WHT, lw=.7, order='LPTCF', tgap=8, credit=['AN ANDREW HAIGH', 'FILM'], ccol=(244, 204, 226),
    ft='b', fcol=(190, 200, 220), fin=MINT)

# Changeling (2008): white, small black condensed capitals, Jolie under her cloche hat
std('changeling-2008', ('solid', (246, 246, 244)), (24, 24, 26),
    L((0.34, 0.715, 0.83, 0.78), 100, (24, 24, 26), mode='dark', speck=.01, grow=.05),
    photo=ph(.45, .3, .7, .9), pb=(24, 24, 26), lg=(24, 24, 26), lw=.6, order='LPTCF', credit=['A CLINT EASTWOOD', 'FILM'], ccol=(150, 30, 30),
    ft='d', fcol=(24, 24, 26), fin=SLIP)

# King of New York (1990): black and steel-teal, tall condensed capitals in the poster's gradient (typeset: too dark to lift)
std('king-of-new-york-1990', ('solid', (10, 12, 14)), (120, 186, 196),
    T('KING OF NEW YORK', 'hcnb', 104, (130, 196, 206), squeeze=.8, track=.06, grad=[(0, (190, 236, 240)), (.5, (100, 170, 186)), (1, (40, 90, 110))]),
    photo=ph(.6, .18, .6, .8), pb=(130, 196, 206), lg=WHT, lw=.7, order='LPTCSF', tgap=8, credit=['CHRISTOPHER WALKEN'], ccol=WHT,
    stick=BAR('16 09558', top='CRIME'), ft='b', fcol=(160, 176, 180), fin=RENTAL, seed=1990)

# Blades of Glory (2007): rink-ice blue, white italic capitals with a blue keyline (typeset: the poster's are skewed)
std('blades-of-glory-2007', ('grad', [(0, (120, 180, 236)), (.6, (40, 100, 190)), (1, (10, 30, 80))]), WHT,
    T('BLADES OF GLORY', 'herbi', 88, WHT, outline=((20, 50, 140), 2.5), track=-.01),
    photo=ph(.7, .2, .5, 1.0), pb=(240, 80, 40), lg=WHT, lw=.8, order='LPTCSF', credit=['WILL FERRELL', 'JON HEDER'], ccol=WHT,
    stick=RWD(fill=(240, 236, 220)), ft='a', vbox=(240, 80, 40), fcol=WHT, fin=WORN)

# The Hunt (2020): hunting-season orange, the poster's black stencil-heavy capitals
std('the-hunt-2020', ('grad', [(0, (236, 110, 36)), (.6, (190, 70, 20)), (1, (80, 26, 8))]), (20, 16, 14),
    L((0.05, 0.075, 0.95, 0.2), 120, (20, 16, 14), mode='key', key=(28, 20, 16), t=(70, 150), speck=.01),
    photo=ph(.5, .52, .6, 1.0), pb=(20, 16, 14), lg=(20, 16, 14), lw=.8, order='LPTCF', credit=['BETTY GILPIN', 'HILARY SWANK'], ccol=(20, 16, 14),
    ft='a', vbox=(20, 16, 14), vink=(236, 110, 36), fcol=(20, 16, 14), fin=WORN)

# Eileen: 1964 blood-red and black, the poster's spaced yellow capitals
std('eileen-2023', ('grad', [(0, (100, 14, 18)), (.6, (40, 6, 8)), (1, (10, 4, 4))]), (234, 196, 56),
    L((0.12, 0.815, 0.91, 0.93), 90, (238, 200, 60), mode='key', key=(230, 190, 52), t=(70, 150), speck=.01),
    photo=ph(.5, .12, .3, 1.0), pb=(234, 196, 56), lg=WHT, lw=.7, order='LPTCF', credit=['ANNE HATHAWAY', 'THOMASIN McKENZIE'], ccol=(234, 196, 56),
    ft='b', fcol=(200, 180, 170), fin=SLIP)

# Hit Man: sunshine yellow, the poster's orange italic capitals with a dark keyline (typeset: over the red dress)
std('hit-man-2024', ('grad', [(0, (244, 196, 50)), (.6, (210, 150, 30)), (1, (80, 50, 14))]), (240, 110, 30),
    T('HIT MAN', 'intbki', 132, (244, 114, 34), outline=((50, 24, 10), 2.4), track=-.02),
    photo=ph(.5, .25, .9, .6), pb=(50, 24, 10), lg=(50, 24, 10), lw=.5, order='LPTCF', credit=['A RICHARD LINKLATER', 'FILM'], ccol=(50, 24, 10),
    ft='a', vbox=(50, 24, 10), vink=(244, 196, 50), fcol=(50, 24, 10), fin=SLIP)

# Strays: fire-engine red brick, the poster's white blackletter, the Boston terrier with its CENSORED bone
std('strays-2023', ('grad', [(0, (220, 30, 30)), (.6, (150, 14, 16)), (1, (50, 6, 6))]), WHT,
    L((0.11, 0.135, 0.88, 0.345), 116, WHT, mode='key', key=(248, 244, 240), t=(50, 120), speck=.01),
    photo=ph(.7, .6, .45, 1.0), pb=WHT, lg=WHT, lw=.8, order='LPTCSF', credit=['WILL FERRELL', 'JAMIE FOXX'], ccol=WHT,
    stick=flow(dot, 70, ['RATED', 'R'], (20, 20, 20), d=64), ft='a', vbox=WHT, vink=(150, 14, 16), fcol=WHT, fin=SLIP)

# Miller's Girl: a dim study, thin white serif capitals (typeset: the poster's hairline Deco ones break up when lifted)
std('miller-s-girl-2024', ('grad', [(0, (40, 34, 30)), (.6, (20, 18, 16)), (1, (6, 6, 6))]), WHT,
    T("MILLER'S GIRL", 'ter', 92, WHT, track=.06, bold=.4),
    photo=ph(.5, .38, .8, .8), pb=(214, 196, 160), lg=WHT, lw=.7, order='LPTCF', credit=['JENNA ORTEGA', 'MARTIN FREEMAN'], ccol=(214, 196, 160),
    ft='b', fcol=(190, 186, 180), fin=SLIP)

# Sleeping Dogs: cracked-glass slate, wide white geometric capitals like the poster's (typeset: a crack runs through them), Crowe in his beanie
std('sleeping-dogs-2024', ('grad', [(0, (60, 72, 80)), (.6, (30, 36, 42)), (1, (8, 10, 12))]), WHT,
    T('SLEEPING DOGS', 'advb', 76, WHT, track=.2),
    photo=ph(.5, .32, .7, 1.0), pb=(200, 210, 214), lg=WHT, lw=.8, order='LPTCF', tgap=8, credit=['RUSSELL CROWE'], ccol=(200, 210, 214),
    ft='b', fcol=(180, 190, 196), fin=SLIP)

# I Used to Be Funny: a misty Niagara pale blue, the poster's lower-case serif
std('i-used-to-be-funny-2024', ('grad', [(0, (220, 234, 238)), (.6, (190, 210, 214)), (1, (120, 140, 140))]), (30, 34, 40),
    L((0.07, 0.055, 0.93, 0.135), 88, (30, 34, 40), mode='dark', speck=.01, grow=.08),
    photo=ph(.55, .6, .7, .8), pb=(236, 214, 40), lg=(30, 34, 40), lw=.8, order='LPTCF', credit=['RACHEL SENNOTT'], ccol=(30, 34, 40),
    ft='e', fcol=(30, 34, 40), fin=MINT)

# Hell or High Water: West Texas dust, the poster's stacked white condensed capitals (typeset: stacked in mixed sizes)
std('hell-or-high-water-2016', ('grad', [(0, (200, 176, 120)), (.6, (140, 116, 70)), (1, (50, 40, 24))]), WHT,
    TT([('HELL', WHT), ('OR', (60, 40, 20)), ('HIGH WATER', WHT)], 'hcnb', 110, sp=.16, squeeze=.78),
    photo=ph(.65, .55, .6, 1.0), pb=(60, 40, 20), lg=(60, 40, 20), lw=.8, order='LPTCF', credit=['JEFF BRIDGES', 'CHRIS PINE', 'BEN FOSTER'], ccol=(60, 40, 20),
    ft='a', vbox=(60, 40, 20), vink=(200, 176, 120), fcol=(40, 30, 20), fin=WORN)

# Sexy Beast (2001): Spanish-villa poolside white and blue, the poster's hot-pink capitals, Winstone baking
std('sexy-beast-2001', ('bands', [(0, .06, (40, 170, 210)), (.06, 1, (246, 246, 244))]), (220, 20, 130),
    L((0.13, 0.52, 0.88, 0.6), 96, (222, 22, 132), mode='key', key=(216, 20, 128), t=(70, 150), speck=.01),
    photo=ph(.5, .88, .6, .5), pb=(40, 170, 210), lg=(40, 40, 44), lw=.4, order='LPTCSF', credit=['RAY WINSTONE', 'BEN KINGSLEY'], ccol=(40, 40, 44),
    stick=PRC(['NEW', 'RELEASE', '$3.99']), ft='b', fcol=(40, 40, 44), fin=RENTAL, seed=2001)

# Hot Fuzz (2007): an explosion behind black, the chrome HOT FUZZ badge logo (Ian's image)
std('hot-fuzz-2007', ('grad', [(0, (240, 140, 40)), (.3, (120, 40, 10)), (1, (12, 8, 6))]), (214, 218, 226),
    Pic('logos/hot-fuzz-2007-title.png', 170),
    photo=ph(.6, .2, .7, .8), pb=(240, 140, 40), lg=WHT, lw=.6, order='LPTCSF', credit=['SIMON PEGG', 'NICK FROST'], ccol=(240, 180, 90),
    stick=BAR('48 04638', top='COMEDY'), ft='a', vbox=(240, 140, 40), vink=(12, 8, 6), fcol=(200, 196, 190), fin=RENTAL, seed=2007)

# The Disruptors: a cartoon map's sunny white, the poster's red italic capitals
std('the-disruptors-2024', ('solid', (250, 248, 240)), (226, 40, 40),
    L((0.08, 0.865, 0.93, 0.935), 76, (228, 42, 42), mode='key', key=(224, 40, 40), t=(70, 150), speck=.01),
    photo=ph(.5, .4, .9, .8), pb=(226, 40, 40), studio=['AN ADAM FRUCCI', 'FILM'], scol=(30, 30, 34), order='lPTCF',
    credit=['A COMEDY'], ccol=(30, 140, 220), ft='a', vbox=(226, 40, 40), fcol=(30, 30, 34), fin=MINT)

# Babes: bubblegum pink, the poster's hot-pink heavy capitals
std('babes-2024', ('solid', (250, 214, 228)), (236, 20, 140),
    L((0.05, 0.035, 0.94, 0.21), 136, (236, 22, 142), mode='key', key=(234, 20, 140), t=(70, 150), speck=.01),
    photo=ph(.5, .6, 1.0, .6), pb=(236, 20, 140), lg=(30, 30, 34), lw=.7, order='LPTCF', credit=['ILANA GLAZER', 'MICHELLE BUTEAU'], ccol=(30, 30, 34),
    ft='a', vbox=(236, 20, 140), fcol=(30, 30, 34), fin=MINT)

# Beverly Hills Cop: Axel F: palm-tree sky blue (like the 1987 tape next door a year on), the film's title logo (Ian's image)
std('beverly-hills-cop-axel-f-2024', ('grad', [(0, (60, 160, 230)), (.6, (40, 110, 190)), (1, (14, 40, 80))]), WHT,
    Pic('logos/beverly-hills-cop-axel-f-2024-title.png', 150),
    photo=ph(.6, .5, .6, 1.0), pb=WHT, lg=WHT, lw=.5, order='LPTCF', tgap=10, credit=['EDDIE MURPHY'], ccol=WHT,
    ft='a', vbox=(226, 30, 40), fcol=WHT, fin=SLIP)

# The Bikeriders: 1965 photo-book cream, red slab capitals like the poster's (typeset: the poster's are inline-striped)
std('the-bikeriders-2024', ('solid', (238, 232, 216)), (196, 40, 36),
    [T('THE', 'bonb', 40, (196, 40, 36)), T('BIKERIDERS', 'bonb', 92, (196, 40, 36), bold=.8, track=.02)],
    photo=ph(.5, .42, .9, .8), pb=(30, 30, 34), lg=(30, 30, 34), lw=.7, order='LPTCF', tgap=8, credit=['AUSTIN BUTLER', 'JODIE COMER', 'TOM HARDY'], ccol=(30, 30, 34),
    ft='d', fcol=(30, 30, 34), fin=dict(SLIP, warm=.012))

# Jackpot!: a game-show sky blue and orange, the poster's red outlined capitals
std('jackpot-2024', ('grad', [(0, (40, 150, 220)), (.5, (230, 120, 40)), (1, (120, 40, 10))]), (226, 34, 34),
    L((0.06, 0.575, 0.96, 0.69), 112, (230, 38, 38), mode='key', key=(222, 40, 36), t=(70, 150), speck=.01, outline=((250, 220, 60), 2.4)),
    photo=ph(.6, .33, .8, .7), pb=(250, 220, 60), lg=WHT, lw=.6, order='LPTCF', credit=['AWKWAFINA', 'JOHN CENA'], ccol=WHT,
    ft='a', vbox=(250, 220, 60), vink=(120, 40, 10), fcol=WHT, fin=SLIP)

# The Instigators: Boston-harbour blue, acid-yellow italic capitals (typeset: the poster stacks them in two lines)
std('the-instigators-2024', ('grad', [(0, (70, 140, 180)), (.6, (30, 60, 84)), (1, (10, 18, 26))]), (220, 240, 40),
    T('THE INSTIGATORS', 'intbki', 92, (222, 242, 44), track=-.02),
    photo=ph(.5, .2, .9, .7), pb=(220, 240, 40), lg=WHT, lw=.8, order='LPTCF', credit=['MATT DAMON', 'CASEY AFFLECK'], ccol=WHT,
    ft='a', vbox=(220, 240, 40), vink=(10, 18, 26), fcol=(200, 214, 222), fin=SLIP)

# Telemarketers: a boxed docuseries, call-centre cream with dollar bills, black capitals on an orange bar
std('telemarketers-2023', ('solid', (246, 226, 190)), (24, 20, 18),
    T('TELEMARKETERS', 'hcnb', 84, (24, 20, 18), bold=.6, box=((240, 120, 40), 12, 10)),
    photo=ph(.5, .35, .7, .9), pb=(24, 20, 18), lg=(24, 20, 18), lw=.7, order='LPTCF', credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(24, 20, 18),
    ft='b', fcol=(24, 20, 18), fin=MINT)

# LaRoy, Texas: a stormy teal sky, a motel-sign script and slab in neon (typeset: the sign won't lift off the sky)
std('laroy-texas-2024', ('grad', [(0, (30, 80, 100)), (.6, (14, 40, 52)), (1, (40, 30, 16))]), (250, 160, 100),
    [T('LaRoy', 'cho', 110, (250, 210, 180), soft=((250, 120, 80), 8, .8), outline=((180, 60, 40), 1.4)), T('TEXAS', 'bonb', 56, (250, 170, 110), soft=((250, 100, 60), 7, .7), track=.1)],
    photo=ph(.6, .8, .7, .6), pb=(150, 230, 230), lg=WHT, lw=.8, order='LPTCF', tgap=10, credit=['JOHN MAGARO', 'STEVE ZAHN'], ccol=(150, 230, 230),
    ft='a', vbox=(250, 160, 100), vink=(14, 40, 52), fcol=(200, 214, 220), fin=SLIP)

# The Fugitive (1993): black with a white diagonal streak, tall white condensed capitals, Ford on the run
std('the-fugitive-1993', ('solid', (10, 10, 12)), WHT,
    T('THE FUGITIVE', 'hcnb', 112, WHT, squeeze=.8, bold=.6),
    photo=ph(.25, .25, .5, 1.0), pb=(200, 30, 30), lg=None, lw=.36, order='LPTCSF', credit=['HARRISON FORD', 'TOMMY LEE JONES'], ccol=(200, 30, 30),
    stick=BAR('16 12880', top='ACTION'), ft='b', fcol=(176, 176, 176), fin=RENTAL, seed=1993)

# Ol' Dirty Bastard: A Tale of Two Dirtys: denim navy, the poster's huge yellow condensed slab
std('ol-dirty-bastard-a-tale-of-two-dirtys-2024', ('grad', [(0, (40, 54, 90)), (.6, (20, 28, 50)), (1, (8, 10, 18))]), (246, 220, 30),
    [T("OL' DIRTY BASTARD", 'hcnb', 104, (246, 222, 34), squeeze=.84, bold=.6), T('A TALE OF TWO DIRTYS', 'hcnb', 30, WHT, track=.08)],
    photo=ph(.5, .8, .7, .8), pb=(246, 222, 34), lg=WHT, lw=.8, order='LPTCF', tgap=10, credit=['A DOCUMENTARY'], ccol=(246, 222, 34),
    ft='b', fcol=(200, 206, 220), fin=SLIP)

# Adventures in Babysitting (1987): Chicago skyline at night, the gold italic title with "in Babysitting" in a sash
std('adventures-in-babysitting-1987', ('grad', [(0, (14, 18, 50)), (.6, (8, 10, 30)), (1, (4, 4, 10))]), (240, 196, 70),
    [T('ADVENTURES', 'herbi', 84, (244, 200, 76), outline=((90, 40, 10), 2)), T('IN BABYSITTING', 'herbi', 40, WHT, box=((40, 70, 160), 8, 6))],
    photo=ph(.6, .45, .6, 1.0), pb=(240, 196, 70), lg=WHT, lw=.8, order='LPTCSF', tgap=10, credit=['ELISABETH SHUE'], ccol=(240, 196, 70),
    stick=PRC(['FAMILY', 'RENTAL', '$1.99']), ft='a', vbox=(240, 196, 70), vink=(8, 10, 30), fcol=(200, 200, 220), fin=RENTAL, seed=1987)

# Greedy People: small-town sheriff's-office green, a white slab like the poster's (typeset: stacked on the poster)
std('greedy-people-2024', ('grad', [(0, (90, 110, 80)), (.6, (50, 62, 44)), (1, (16, 20, 14))]), WHT,
    T('GREEDY PEOPLE', 'bonb', 92, WHT, bold=.6),
    photo=ph(.5, .55, .9, .7), pb=(220, 200, 150), lg=WHT, lw=.5, order='LPTCF', credit=['JOSEPH GORDON-LEVITT', 'HIMESH PATEL'], ccol=(220, 200, 150),
    ft='a', vbox=(220, 200, 150), vink=(16, 20, 14), fcol=(210, 214, 200), fin=SLIP)

# The Grifters (1990): black, the poster's yellow brush capitals with a red streak (typeset: they're slanted)
std('the-grifters-1990', ('solid', (10, 10, 10)), (246, 222, 30),
    T('THE GRIFTERS', 'herbi', 96, (246, 222, 34), shadow=((200, 30, 30), 3, 3), track=-.01),
    photo=ph(.5, .3, 1.0, .6), pb=(246, 222, 34), studio=['A STEPHEN FREARS', 'FILM'], scol=(246, 222, 34), order='lPTCSF',
    credit=['ANJELICA HUSTON', 'JOHN CUSACK', 'ANNETTE BENING'], ccol=WHT, stick=BAR('15 31337', top='CRIME'), ft='b', fcol=(176, 176, 176), fin=RENTAL, seed=1990)

# Rebel Ridge: dust-cream poster stock, heavy dark-brown capitals like the poster's (typeset: a rule runs through them)
std('rebel-ridge-2024', ('solid', (232, 216, 192)), (44, 30, 22),
    T('REBEL RIDGE', 'intbk', 92, (44, 30, 22), track=-.03),
    photo=ph(.35, .38, .6, 1.0), pb=(44, 30, 22), lg=(44, 30, 22), lw=.8, order='LPTCF', credit=['A JEREMY SAULNIER', 'FILM'], ccol=(196, 70, 30),
    ft='d', fcol=(44, 30, 22), fin=SLIP)

# Blink Twice: black, the poster's chunky yellow capitals, Tatum behind the Polaroid
std('blink-twice-2024', ('solid', (12, 12, 12)), (246, 200, 30),
    L((0.04, 0.8, 0.96, 0.875), 104, (246, 202, 34), mode='key', key=(240, 196, 30), t=(70, 150), speck=.01),
    photo=ph(.6, .35, .6, 1.0), pb=(246, 200, 30), lg=WHT, lw=.7, order='LPTCF', credit=['A ZOË KRAVITZ', 'FILM'], ccol=(246, 200, 30),
    ft='a', vbox=(246, 200, 30), vink=(12, 12, 12), fcol=(190, 190, 190), fin=SLIP)

# What You Wish For: a Colombian villa at dusk, wide-spaced white capitals like the poster's
std('what-you-wish-for-2024', ('grad', [(0, (60, 90, 110)), (.6, (24, 36, 40)), (1, (8, 12, 12))]), WHT,
    T('WHAT YOU WISH FOR', 'adv', 64, WHT, track=.3, bold=.4),
    photo=ph(.5, .5, .6, 1.0), pb=(214, 190, 150), lg=WHT, lw=.8, order='LPTCF', credit=['NICK STAHL'], ccol=(214, 190, 150),
    ft='b', fcol=(190, 200, 204), fin=SLIP)

# Enter the Void (2010): Tokyo neon, the poster's glowing capitals (typeset with the same red-to-yellow neon)
std('enter-the-void-2010', ('grad', [(0, (160, 20, 120)), (.5, (60, 10, 90)), (1, (10, 4, 20))]), (250, 220, 60),
    T('ENTER THE VOID', 'intbk', 92, (250, 220, 60), grad=[(0, (250, 240, 120)), (1, (250, 60, 60))], soft=((250, 60, 160), 9, .9), track=.02),
    photo=ph(.5, .85, .6, .5), pb=(250, 220, 60), studio=['A GASPAR NOÉ', 'FILM'], scol=(250, 220, 60), order='lPTCF',
    credit=['ADULTS ONLY'], ccol=(250, 120, 200), ft='a', vbox=(250, 220, 60), vink=(60, 10, 90), fcol=(230, 200, 230), fin=WORN)

# Wolfs: winter-diner white, the poster's magenta condensed capitals
std('wolfs-2024', ('solid', (244, 244, 242)), (204, 20, 100),
    L((0.2, 0.155, 0.8, 0.36), 120, (206, 22, 104), mode='key', key=(200, 20, 100), t=(70, 150), speck=.01),
    photo=ph(.5, .68, 1.0, .5), pb=(30, 30, 34), lg=(30, 30, 34), lw=.8, order='LPTCF', credit=['GEORGE CLOONEY', 'BRAD PITT'], ccol=(30, 30, 34),
    ft='a', vbox=(204, 20, 100), fcol=(30, 30, 34), fin=MINT)

# In the Company of Men (1997): grey office sky, the poster's mustard lower-case slab, Eckhart in shades
std('in-the-company-of-men-1997', ('grad', [(0, (190, 196, 202)), (.6, (140, 146, 152)), (1, (60, 62, 66))]), (206, 150, 40),
    T('in the company of men', 'bonb', 84, (206, 150, 40), bold=.6),
    photo=ph(.55, .25, .7, .8), pb=(30, 30, 34), studio=['A NEIL LABUTE', 'FILM'], scol=(30, 30, 34), order='lPTCSF', tgap=8,
    credit=['AARON ECKHART'], ccol=(30, 30, 34), stick=PRC(['STAFF', 'FAVORITE']), ft='b', fcol=(30, 30, 34), fin=RENTAL, seed=1997)

# Deadpool & Wolverine: Deadpool red into Wolverine yellow, the comic-book stencil capitals (typeset: over the costumes)
std('deadpool-wolverine-2024', ('grad', [(0, (180, 20, 24)), (.55, (110, 10, 14)), (.56, (230, 190, 30)), (1, (150, 110, 10))]), (226, 30, 34),
    [T('DEADPOOL', 'hcnb', 92, (232, 36, 40), outline=((20, 10, 10), 2.4), bold=.6), T('& WOLVERINE', 'hcnb', 92, (250, 210, 40), outline=((20, 10, 10), 2.4), bold=.6)],
    photo=ph(.5, .3, 1.0, .6), pb=(250, 210, 40), lg=WHT, lw=.8, order='LPTF', tgap=8, ft='a', vbox=(20, 10, 10), vink=(250, 210, 40), fcol=WHT,
    fin=dict(SLIP, gloss=.09))

# The Wasp: black with a single red streak, a white italic serif like the poster's (typeset: the lift lost the small "The")
std('the-wasp-2024', ('solid', (10, 10, 10)), WHT,
    T('The Wasp', 'teri', 120, WHT),
    photo=ph(.4, .2, .6, .8), pb=(200, 30, 30), lg=WHT, lw=.6, order='LPTCF', credit=['NAOMIE HARRIS', 'NATALIE DORMER'], ccol=(200, 30, 30),
    ft='b', fcol=(180, 180, 180), fin=SLIP)

# The 4:30 Movie: 1980s multiplex blue, gold slab "4:30" with "the" and "movie" (typeset: over the cast collage)
std('the-4-30-movie-2024', ('grad', [(0, (90, 160, 210)), (.6, (40, 90, 150)), (1, (14, 30, 60))]), (246, 196, 60),
    TT([('THE', WHT), ('4:30', (246, 200, 66)), ('MOVIE', WHT)], 'bonb', 100, sp=.18),
    photo=ph(.6, .2, .7, .8), pb=(246, 200, 66), lg=WHT, lw=.4, order='LPTCSF', credit=['A KEVIN SMITH', 'FILM'], ccol=(246, 200, 66),
    stick=flow(dot, 70, ['NOW', 'PLAYING'], (220, 40, 50), d=64), ft='a', vbox=(246, 200, 66), vink=(14, 30, 60), fcol=WHT, fin=WORN)

# Dune: Part Two: the poster's burnt-orange sun, wide hairline glyph-capitals (typeset like the poster's, which are too thin to lift)
std('dune-part-two-2024', ('grad', [(0, (120, 40, 20)), (.3, (230, 130, 40)), (.6, (190, 90, 30)), (1, (60, 24, 10))]), WHT,
    [T('DUNE', 'adv', 110, WHT, track=.6), T('PART TWO', 'adv', 26, WHT, track=.5)],
    photo=ph(.5, .85, .6, .6), pb=WHT, lg=WHT, lw=.8, order='LPTCF', tgap=14, credit=['A DENIS VILLENEUVE', 'FILM'], ccol=WHT,
    ft='e', fcol=WHT, fin=dict(MINT, gloss=.1), dotst=(['STAFF', 'PICK'], (30, 14, 8)))

# It's What's Inside: party-house dark, chrome italic capitals (typeset: the poster's are chrome-on-photo)
std('it-s-what-s-inside-2024', ('grad', [(0, (50, 36, 30)), (.6, (26, 18, 16)), (1, (8, 6, 6))]), WHT,
    T("IT'S WHAT'S INSIDE", 'herbi', 80, WHT, grad=[(0, (250, 250, 252)), (.5, (180, 186, 196)), (1, (230, 234, 240))], outline=((30, 20, 20), 2)),
    photo=ph(.5, .62, 1.0, .6), pb=(236, 120, 60), lg=WHT, lw=.6, order='LPTCF', credit=['A GREG JARDIN', 'FILM'], ccol=(236, 120, 60),
    ft='a', vbox=(236, 120, 60), vink=(8, 6, 6), fcol=(200, 196, 190), fin=SLIP)

# The Last Stop in Yuma County: desert-diner teal, the poster's red wood-type capitals (typeset: they're set on a wave)
std('the-last-stop-in-yuma-county-2024', ('grad', [(0, (150, 196, 186)), (.6, (200, 196, 160)), (1, (140, 110, 70))]), (190, 40, 30),
    [T('THE LAST STOP IN', 'bonb', 40, (190, 40, 30), track=.04), T('YUMA COUNTY', 'bonb', 76, (190, 40, 30), bold=.6)],
    photo=ph(.5, .3, .8, .8), pb=(190, 40, 30), lg=(40, 30, 24), lw=.8, order='LPTCF', tgap=8, credit=['A FRANCIS GALLUPPI', 'FILM'], ccol=(40, 30, 24),
    ft='a', vbox=(190, 40, 30), fcol=(40, 30, 24), fin=WORN)

# Rillington Place: a boxed BBC miniseries, sepia mugshots, tall white condensed capitals
std('rillington-place-2016', ('grad', [(0, (70, 60, 50)), (.6, (40, 34, 28)), (1, (14, 12, 10))]), WHT,
    L((0.06, 0.43, 0.95, 0.51), 64, WHT, mode='light', speck=.01),
    photo=ph(.5, .18, 1.0, .45), pb=(220, 210, 190), lg=WHT, lw=.6, order='LPTCF', credit=['THE COMPLETE', 'MINISERIES'], ccol=(220, 210, 190),
    ft='b', fcol=(190, 180, 170), fin=SLIP)

# The Last Duel: parchment white, the slate-blue Roman capitals, the three of them in ink-black smoke
std('the-last-duel-2021', ('solid', (240, 238, 232)), (40, 60, 80),
    L([(0.43, 0.81, 0.57, 0.845), (0.15, 0.845, 0.85, 0.925)], 84, (40, 60, 80), mode='dark', speck=.01, gapf=.3),
    photo=ph(.5, .25, .9, .7), pb=(40, 60, 80), lg=(40, 60, 80), lw=.6, order='LPTCF', credit=['A RIDLEY SCOTT', 'FILM'], ccol=(150, 30, 30),
    ft='d', fcol=(40, 60, 80), fin=SLIP)

# Into the Fire: The Lost Daughter: a boxed docuseries, Colorado-prairie grey, wide white capitals
std('into-the-fire-the-lost-daughter-2024', ('grad', [(0, (120, 126, 120)), (.6, (64, 66, 58)), (1, (20, 20, 18))]), WHT,
    [T('INTO THE FIRE', 'adv', 70, WHT, track=.12, bold=.4), T('THE LOST DAUGHTER', 'adv', 30, WHT, track=.2)],
    photo=ph(.4, .35, .6, 1.0), pb=(200, 40, 40), lg=WHT, lw=.6, order='LPTCF', tgap=10, credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(214, 200, 180),
    ft='b', fcol=(200, 200, 194), fin=MINT)

# Jailbreak: Love on the Run: two mugshot halves, white rounded capitals (typeset: over the faces)
std('jailbreak-love-on-the-run-2024', ('grad', [(0, (140, 124, 110)), (.6, (80, 68, 58)), (1, (24, 20, 16))]), WHT,
    [T('JAILBREAK', 'advb', 40, WHT, track=.2), T('LOVE ON THE RUN', 'advb', 76, WHT, track=.02)],
    photo=ph(.5, .2, 1.0, .5), pb=WHT, lg=(214, 40, 40), lw=.7, order='LPTCF', tgap=10, credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=(240, 214, 200),
    ft='b', fcol=(220, 210, 200), fin=MINT)

# Into the Night (1985): LA at night under a violet sky, a scrawled white script (typeset)
std('into-the-night-1985', ('grad', [(0, (90, 60, 160)), (.4, (30, 26, 70)), (1, (6, 6, 14))]), WHT,
    T('into the night', 'cho', 120, WHT),
    photo=ph(.5, .5, .7, .9), pb=(200, 40, 60), lg=WHT, lw=.6, order='LPTCSF', credit=['JEFF GOLDBLUM', 'MICHELLE PFEIFFER'], ccol=(200, 180, 240),
    stick=BAR('17 01985', top='THRILLER'), ft='b', fcol=(180, 176, 200), fin=RENTAL, seed=1985)

# The Killer (2024): Paris-grey, the poster's blood-red italic capitals with the small stacked THE (typeset)
std('the-killer-2024', ('grad', [(0, (210, 210, 210)), (.6, (150, 150, 152)), (1, (40, 40, 44))]), (196, 20, 24),
    [T('THE', 'herbi', 40, (196, 20, 24)), T('KILLER', 'intbki', 130, (196, 20, 24), track=-.02)],
    photo=ph(.6, .6, .8, .8), pb=(196, 20, 24), lg=(30, 30, 34), lw=.7, order='LPTCF', tgap=8, credit=['A JOHN WOO', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(196, 20, 24), fcol=(30, 30, 34), fin=SLIP)

# Killer Heat: Greek-island teal, huge cream serif capitals like the poster's (typeset: they fade into the sky)
std('killer-heat-2024', ('grad', [(0, (60, 160, 160)), (.6, (40, 110, 110)), (1, (14, 40, 40))]), (244, 236, 214),
    T('KILLER HEAT', 'dsc', 100, (244, 236, 214)),
    photo=ph(.5, .75, 1.0, .5), pb=(244, 236, 214), lg=WHT, lw=.8, order='LPTCF', credit=['JOSEPH GORDON-LEVITT', 'SHAILENE WOODLEY'], ccol=(244, 236, 214),
    ft='e', fcol=(220, 236, 232), fin=SLIP)

# Brothers: road-trip orange, the poster's battered yellow capitals on black
std('brothers-2024', ('grad', [(0, (234, 150, 30)), (.6, (190, 110, 20)), (1, (80, 40, 8))]), (246, 230, 40),
    T('BROTHERS', 'hcnb', 140, (246, 232, 44), squeeze=.84, rough=.3, box=((20, 18, 14), 12, 10)),
    photo=ph(.6, .25, .6, .9), pb=(20, 18, 14), lg=(20, 18, 14), lw=.7, order='LPTCF', credit=['JOSH BROLIN', 'PETER DINKLAGE'], ccol=(20, 18, 14),
    ft='a', vbox=(20, 18, 14), vink=(246, 232, 44), fcol=(20, 18, 14), fin=WORN)

# A Woman Under the Influence (1974): the dusty-rose still, black heavy capitals like the poster's (typeset: the lift broke up)
std('a-woman-under-the-influence-1974', ('grad', [(0, (200, 140, 140)), (.6, (150, 96, 96)), (1, (60, 34, 34))]), (20, 18, 18),
    [T('A WOMAN', 'intbk', 100, (20, 18, 18), track=-.03), T('UNDER THE INFLUENCE', 'dsc', 40, WHT)],
    photo=ph(.5, .55, 1.0, .6), pb=(20, 18, 18), studio=['A JOHN CASSAVETES', 'FILM'], scol=(20, 18, 18), order='lPTCSF', tgap=10,
    credit=['GENA ROWLANDS', 'PETER FALK'], ccol=WHT, stick=PRC(['CRITERION', 'PICK']), ft='b', fcol=(30, 20, 20), fin=OLD, seed=1974)

# Joker: Folie à Deux: teal and clown-red, tall white condensed capitals (typeset: small on the poster)
std('joker-folie-a-deux-2024', ('grad', [(0, (40, 110, 116)), (.6, (20, 56, 60)), (1, (6, 16, 18))]), WHT,
    [T('JOKER', 'hcnb', 140, WHT, squeeze=.78, bold=.5), T('FOLIE À DEUX', 'hcnb', 36, (220, 40, 50), track=.2)],
    photo=ph(.5, .45, 1.0, .6), pb=(220, 40, 50), lg=WHT, lw=.6, order='LPTCF', tgap=10, credit=['JOAQUIN PHOENIX', 'LADY GAGA'], ccol=WHT,
    ft='a', vbox=(220, 40, 50), fcol=(200, 214, 214), fin=SLIP)

# Woman of the Hour: 1970s game-show orange in the dark, a cream swash serif (typeset like the poster's)
std('woman-of-the-hour-2024', ('grad', [(0, (30, 20, 14)), (.5, (110, 50, 20)), (1, (14, 8, 6))]), (246, 226, 190),
    T('Woman of the Hour', 'terbi', 80, (246, 226, 190)),
    photo=ph(.5, .5, .6, 1.0), pb=(240, 140, 40), lg=WHT, lw=.8, order='LPTCF', credit=['AN ANNA KENDRICK', 'FILM'], ccol=(240, 140, 40),
    ft='a', vbox=(240, 140, 40), vink=(14, 8, 6), fcol=(220, 200, 180), fin=SLIP)

# A Different Man: black stage, a red condensed serif like the poster's (typeset: the lift broke up)
std('a-different-man-2024', ('solid', (10, 10, 10)), (200, 40, 30),
    T('A DIFFERENT MAN', 'dsc', 92, (206, 44, 34), squeeze=.8),
    photo=ph(.5, .45, .8, .8), pb=(200, 40, 30), lg=WHT, lw=.6, order='LPTCF', credit=['SEBASTIAN STAN', 'ADAM PEARSON'], ccol=(200, 40, 30),
    ft='b', fcol=(180, 180, 180), fin=SLIP)

# Magpie: dark teal close-up, yellow serif capitals like the poster's (typeset: the lift broke up)
std('magpie-2024', ('grad', [(0, (40, 90, 90)), (.6, (18, 40, 40)), (1, (6, 12, 12))]), (240, 200, 60),
    T('MAGPIE', 'terb', 120, (244, 206, 66), track=.08),
    photo=ph(.4, .55, .8, .7), pb=(240, 200, 60), lg=WHT, lw=.8, order='LPTCF', credit=['DAISY RIDLEY'], ccol=(240, 200, 60),
    ft='b', fcol=(190, 206, 206), fin=SLIP)

# My Old Ass: lakeside-cabin flannel blue, chunky yellow condensed capitals (typeset: stacked word by word on the poster)
std('my-old-ass-2024', ('grad', [(0, (50, 90, 170)), (.6, (30, 50, 100)), (1, (10, 16, 36))]), (250, 228, 30),
    T('MY OLD ASS', 'hcnb', 140, (250, 228, 30), squeeze=.8, bold=.6),
    photo=ph(.2, .3, .4, 1.0), pb=(250, 228, 30), lg=WHT, lw=.8, order='LPTCF', credit=['A MEGAN PARK', 'FILM'], ccol=(250, 228, 30),
    ft='a', vbox=(250, 228, 30), vink=(30, 50, 100), fcol=WHT, fin=SLIP)

# The Servant (1963): black, a hand-mirror holding two faces, the poster's cream condensed capitals
std('the-servant-1963', ('solid', (10, 10, 10)), (236, 210, 180),
    L((0.08, 0.8, 0.93, 0.92), 100, (238, 212, 182), mode='key', key=(232, 204, 176), t=(70, 150), speck=.01),
    photo=ph(.5, .35, .8, .8), pb=(236, 210, 180), studio=['A JOSEPH LOSEY', 'FILM'], scol=(236, 210, 180), order='lPTCSF',
    credit=['DIRK BOGARDE', 'JAMES FOX'], ccol=WHT, stick=PRC(['CLASSIC', '$1.99']), ft='b', fcol=(180, 170, 160), fin=OLD, seed=1963)

# Topkapi (1964): Istanbul sky blue, a tall black hand-drawn title (typeset: it runs into the art)
std('topkapi-1964', ('grad', [(0, (70, 170, 230)), (.6, (230, 220, 200)), (1, (200, 120, 90))]), (20, 20, 20),
    T('Topkapi', 'dsc', 140, (20, 20, 20), squeeze=.8),
    photo=ph(.5, .45, .7, .6), pb=(20, 20, 20), lg=(20, 20, 20), lw=.8, order='LPTCSF', credit=['MELINA MERCOURI', 'PETER USTINOV'], ccol=(200, 40, 40),
    stick=PRC(['CLASSIC', '$1.99']), ft='b', fcol=(20, 20, 20), fin=OLD, seed=1964)

# The Critic: theatre-programme cream, wide black condensed capitals like the poster's (typeset: the lift broke up), McKellen under the marquee
std('the-critic-2024', ('solid', (240, 228, 206)), (20, 18, 16),
    T('THE CRITIC', 'hcnb', 104, (20, 18, 16), track=.3, bold=.5),
    photo=ph(.5, .15, .6, .7), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['IAN McKELLEN', 'GEMMA ARTERTON'], ccol=(150, 30, 30),
    ft='d', fcol=(20, 18, 16), fin=SLIP)

# What Jennifer Did: a true-crime documentary, a face split in shadow and red, wide white capitals
std('what-jennifer-did-2024', ('grad', [(0, (60, 14, 14)), (.6, (24, 6, 6)), (1, (6, 2, 2))]), WHT,
    T('WHAT JENNIFER DID', 'advb', 64, WHT, track=.12),
    photo=ph(.4, .3, .8, .8), pb=(220, 40, 40), lg=WHT, lw=.7, order='LPTCF', credit=['A TRUE-CRIME', 'DOCUMENTARY'], ccol=(220, 40, 40),
    ft='b', fcol=(190, 176, 176), fin=MINT)

# Trainwreck (2015): grey studio backdrop, the poster's yellow condensed capitals
std('trainwreck-2015', ('grad', [(0, (200, 200, 200)), (.6, (140, 140, 144)), (1, (50, 50, 54))]), (248, 220, 30),
    L((0.08, 0.04, 0.92, 0.155), 112, (250, 222, 34), mode='key', key=(240, 214, 40), t=(70, 160), speck=.01, outline=((40, 40, 44), 1.8)),
    photo=ph(.5, .4, .9, .8), pb=(248, 220, 30), lg=(30, 30, 34), lw=.6, order='LPTCSF', credit=['AMY SCHUMER', 'BILL HADER'], ccol=(30, 30, 34),
    stick=RWD(fill=(248, 220, 30)), ft='a', vbox=(248, 220, 30), vink=(30, 30, 34), fcol=(30, 30, 34), fin=WORN)

# An Inspector Calls (1954): black with a painted yellow glow, a yellow brush script (typeset: it's on a slant)
std('an-inspector-calls-1954', ('grad', [(0, (230, 200, 60)), (.25, (60, 50, 30)), (1, (10, 10, 10))]), (246, 222, 40),
    T('An Inspector Calls', 'curbi', 76, (246, 222, 40), outline=((20, 16, 10), 2)),
    photo=ph(.5, .25, .6, .9), pb=(246, 222, 40), studio=['ALASTAIR SIM'], scol=(20, 16, 10), order='lPTCSF',
    credit=['FROM THE PLAY BY', 'J. B. PRIESTLEY'], ccol=(246, 222, 40), stick=PRC(['CLASSIC', '$1.99']), ft='b', fcol=(180, 176, 160), fin=OLD, seed=1954)

# The Hitcher (1986): a highway under storm-blue sky, the slashed white capitals (typeset with a slant)
std('the-hitcher-1986', ('grad', [(0, (40, 70, 130)), (.5, (20, 34, 66)), (1, (6, 8, 14))]), WHT,
    [T('THE', 'herbi', 40, WHT), T('HITCHER', 'intbki', 120, WHT, rough=.4, track=-.02)],
    photo=ph(.5, .15, .8, .5), pb=WHT, studio=['A ROBERT HARMON', 'FILM'], scol=(200, 60, 60), order='lPTCSF', tgap=8, credit=['RUTGER HAUER', 'C. THOMAS HOWELL'], ccol=(200, 60, 60),
    stick=BAR('20 01986', top='HORROR'), ft='b', fcol=(170, 180, 200), fin=RENTAL, seed=1986)

# Juror #2: courthouse black and lamp-gold, the poster's gold serif
std('juror-2-2024', ('grad', [(0, (50, 36, 22)), (.6, (22, 16, 10)), (1, (6, 4, 2))]), (236, 206, 150),
    L((0.11, 0.29, 0.89, 0.4), 100, (238, 210, 156), mode='key', key=(232, 204, 150), t=(70, 160), speck=.01),
    photo=ph(.5, .62, .6, .9), pb=(236, 206, 150), lg=WHT, lw=.6, order='LPTCF', credit=['A CLINT EASTWOOD', 'FILM'], ccol=(236, 206, 150),
    ft='a', vbox=(236, 206, 150), vink=(22, 16, 10), fcol=(210, 200, 186), fin=SLIP)

# Venom: The Last Dance: black symbiote tendrils, chrome capitals and a scrawled subtitle (typeset)
std('venom-the-last-dance-2024', ('grad', [(0, (60, 50, 60)), (.5, (24, 20, 26)), (1, (60, 10, 10))]), WHT,
    [T('VENOM', 'intbk', 120, WHT, grad=[(0, (250, 250, 252)), (.5, (150, 156, 170)), (1, (220, 224, 232))], outline=((10, 10, 12), 2)),
     T('THE LAST DANCE', 'herbi', 40, WHT, track=.06)],
    photo=ph(.5, .4, .9, .8), pb=(200, 30, 30), lg=WHT, lw=.8, order='LPTF', tgap=10, ft='a', vbox=(200, 30, 30), fcol=(200, 196, 200), fin=SLIP)

# Carry-On: airport-uniform blue, red spaced capitals like the poster's (typeset: the lift broke up)
std('carry-on-2024', ('grad', [(0, (80, 120, 150)), (.6, (36, 60, 80)), (1, (10, 18, 26))]), (220, 30, 30),
    T('CARRY-ON', 'hcnb', 96, (226, 34, 34), track=.3, bold=.5),
    photo=ph(.5, .35, .7, .9), pb=(220, 30, 30), lg=WHT, lw=.8, order='LPTCF', credit=['TARON EGERTON', 'JASON BATEMAN'], ccol=WHT,
    ft='a', vbox=(220, 30, 30), fcol=(200, 214, 224), fin=SLIP)

# The Order: white with the torn flag, the poster's blood-red condensed capitals
std('the-order-2024', ('solid', (246, 244, 240)), (170, 20, 24),
    L((0.09, 0.835, 0.91, 0.955), 116, (176, 22, 26), mode='key', key=(170, 20, 24), t=(70, 150), speck=.01),
    photo=ph(.5, .35, .7, .9), pb=(170, 20, 24), lg=(30, 30, 34), lw=.7, order='LPTCF', credit=['JUDE LAW', 'NICHOLAS HOULT'], ccol=(30, 30, 34),
    ft='a', vbox=(170, 20, 24), fcol=(30, 30, 34), fin=SLIP)

# Gladiator II: arena embers, white Roman capitals with a gold II (typeset: they sit over the arena)
std('gladiator-ii-2024', ('grad', [(0, (60, 50, 40)), (.5, (100, 40, 16)), (1, (20, 8, 4))]), WHT,
    TT([('GLADIATOR', WHT), ('II', (226, 186, 90))], 'ter', 96, sp=.2, track=.08),
    photo=ph(.5, .28, .8, .7), pb=(226, 186, 90), lg=WHT, lw=.6, order='LPTCF', credit=['A RIDLEY SCOTT', 'FILM'], ccol=(226, 186, 90),
    ft='a', vbox=(226, 186, 90), vink=(20, 8, 4), fcol=(220, 206, 190), fin=dict(SLIP, gloss=.09))

# Misery (1990): snowbound night blue, red serif capitals like the poster's (typeset: the speckled snow broke the lift), the farmhouse lit in the snow
std('misery-1990', ('grad', [(0, (40, 80, 120)), (.5, (12, 26, 46)), (1, (4, 8, 14))]), (210, 30, 34),
    T('MISERY', 'dsc', 112, (216, 34, 38), squeeze=.9),
    photo=ph(.5, .8, .6, .6), pb=(210, 30, 34), lg=WHT, lw=.7, order='LPTCSF', credit=['JAMES CAAN', 'KATHY BATES'], ccol=WHT,
    stick=BAR('15 01990', top='THRILLER'), ft='b', fcol=(170, 186, 206), fin=RENTAL, seed=1990)



# =====================================================================================
# Disney and Pixar: the white clamshell.  Ian's rule (16 Nov 2026): every Disney or Pixar film gets
# this box, laid out the way the 1990s Disney clamshell spines were: artwork running the full length,
# a black diamond at the head, the studio logo reading down, the title in the film's own logo lettering,
# a character portrait in a red diamond near the foot, then CC, VHS and the number.  The case itself
# (white caps, sleeve, extra height and thickness) is added by finish_vhs(kind='clam').
# =====================================================================================
def head_diamond(lines, h=150):
    """a tall black diamond with a silver sheen and keyline, holding plain type that reads down the spine"""
    def fn(im, W, y0, rng):
        cx, cy, rx, ry = W / 2 * S, (y0 + h / 2) * S, W * 0.27 * S, h / 2 * S
        m = Image.new('L', im.size, 0)
        pts = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
        ImageDraw.Draw(m).polygon(pts, fill=255)
        yy, xx = np.mgrid[0:im.height, 0:im.width].astype(np.float32)
        t = (xx - cx + (yy - cy) * 0.55) / (rx * 0.9)  # slanted bands of sheen, as on foil
        sheen = 14 + 70 * np.exp(-((t + 0.25) / 0.22) ** 2) + 40 * np.exp(-((t - 0.55) / 0.16) ** 2)
        fill = Image.fromarray(np.dstack([sheen, sheen, sheen * 1.04, np.full_like(sheen, 255)]).clip(0, 255).astype(np.uint8), 'RGBA')
        fill.putalpha(m); im.alpha_composite(fill)
        d = ImageDraw.Draw(im)
        d.line(pts + [pts[0]], fill=(226, 228, 232, 255), width=int(1.8 * S), joint='curve')
        ims = []
        for t_, sz in lines:
            i_ = T(t_, 'terb', sz, (246, 246, 242), track=.03).render(1.0); p = int((10 + sz * 0.12) * S)
            ims.append(rot(i_.crop((p, p, i_.width - p, i_.height - p))))
        tot = sum(i.width for i in ims) + 3 * S * (len(ims) - 1)
        x = cx + tot / 2
        for i_ in ims:
            x -= i_.width; im.alpha_composite(i_, (int(x), int(cy - i_.height / 2))); x -= 3 * S
    return Fn(fn, h)


def head_emblem(path, h):
    """the head emblem placed from an image file in logos/ (Ian's photo of it, squared up); never redrawn"""
    src = Image.open(REPO + path).convert('RGBA')

    def fn(im, W, y0, rng):
        e = src.resize((int(h * S * src.width / src.height), int(h * S)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(4, 90, 2))
        im.alpha_composite(e, (int(W * S / 2 - e.width / 2), int(y0 * S)))
    return Fn(fn, h)


def vlogo(id, color, length, path=None):
    """the studio's logo file from logos/, in one ink, turned to read down the spine"""
    src = Image.open(REPO + (path or FILMS[id]['logo'])).convert('RGBA')
    big = src.resize((int(length * S), int(length * S * src.height / src.width)), Image.LANCZOS)
    a = np.asarray(big).astype(np.float32) / 255
    m = np.clip((cv2.GaussianBlur(a[..., 3], (0, 0), 0.6) - 0.5) * 3 + 0.5, 0, 1)
    big = rot(colorize(Image.fromarray((m * 255).astype(np.uint8)), color))

    def fn(im, W, y0, rng):
        sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sh.putalpha(big.getchannel('A').point(lambda v: int(v * .55)))
        x, y = int(W * S / 2 - big.width / 2), int(y0 * S)
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(1.2 * S)), (x + S, y + S))
        im.alpha_composite(big, (x, y))
    return Fn(fn, length)


def portrait(box, h, border=(214, 30, 40), inner=(250, 214, 60)):
    """a crop of the poster in a red diamond frame"""
    def fn(im, W, y0, rng):
        cov = Image.open(CUR['cover']).convert('RGB'); cw, ch = cov.size
        w_ = W * 0.80  # a true diamond: clearly taller than it is wide, not a square on its corner
        c = cov.crop((int(box[0] * cw), int(box[1] * ch), int(box[2] * cw), int(box[3] * ch))).resize((int(w_ * S), int(h * S)), Image.LANCZOS)
        c = c.filter(ImageFilter.UnsharpMask(3, 60, 2)).convert('RGBA')
        m = Image.new('L', c.size, 0); d = ImageDraw.Draw(m)
        pts = [(c.width / 2, 0), (c.width, c.height / 2), (c.width / 2, c.height), (0, c.height / 2)]
        d.polygon(pts, fill=255); c.putalpha(m)
        d2 = ImageDraw.Draw(c)
        d2.line(pts + [pts[0]], fill=tuple(border) + (255,), width=int(4.5 * S), joint='curve')
        k = 0.93; q = [(c.width / 2 + (x - c.width / 2) * k, c.height / 2 + (y - c.height / 2) * k) for x, y in pts]
        d2.line(q + [q[0]], fill=tuple(inner) + (255,), width=int(1.2 * S))
        c.putalpha(m)
        im.alpha_composite(c, (int((W - w_) / 2 * S), int(y0 * S)))
    return Fn(fn, h)


def ccbox(col, w=30, h=20):
    def fn(im, W, y0, rng):
        d = ImageDraw.Draw(im)
        x0 = (W - w) / 2 * S
        d.rounded_rectangle([x0, y0 * S, x0 + w * S, (y0 + h) * S], radius=4 * S, fill=tuple(col) + (255,))
        t = T('CC', 'intxb', 13, (20, 20, 24) if sum(col) > 380 else (240, 240, 236)).render(1.0)
        p = int((10 + 13 * 0.12) * S); t = t.crop((p, p, t.width - p, t.height - p))
        im.alpha_composite(t, (int(W * S / 2 - t.width / 2), int((y0 + h / 2) * S - t.height / 2)))
    return Fn(fn, h)


EMBLEM = 'logos/classics-diamond.png'  # Ian's own photo of the clamshell head emblem; without the file a plain diamond is drawn


def disney(id, bg, title, face, lcol=(250, 214, 80), head=(('VHS', 30), ('2026', 21)), ink=WHT, cat=None, lpath=None, fin=None, studio=True, **kw):
    W = int(round(w_for(FILMS[id].get('runtime')) * 1.15))  # a clamshell is a thicker box (1.26 was tried; Ian wanted it a tad slimmer)
    items = [Gap(4), Gap(10), (head_emblem(EMBLEM, int(W * .84)) if os.path.exists(REPO + EMBLEM) else head_diamond(head, int(W * .78))), Gap(22)] + ([vlogo(id, lcol, int(W * .62), lpath), Gap(22)] if studio else []) + [  # studio=False when the title logo already carries the studio's name
             Flex(.5), V(title if isinstance(title, list) else [title], gap=10), Flex(.7),
             portrait(face, int(W * 1.12)), Gap(16), ccbox(ink), Gap(12),
             tiny(['VHS'], ink, font='intsb', size=22, track=.04), Gap(8), catno(cat or catfor(id)[:4], ink, size=20)]
    kw.setdefault('side', 22)
    add(id, bg, items, fin=fin or dict(CLAM), W=W, notch=False, top=16, bot=26, **kw)


# Toy Story 5: bedroom-wall blue; the poster's own logo taken apart and laid along the spine the way the
# Toy Story tapes did it: TOY, then the red STORY plate, then the number.
def _soft(m, r=1.4):
    return np.clip((cv2.GaussianBlur(m.astype(np.float32), (0, 0), r) - 0.5) * 4 + 0.5, 0, 1)


def _biggest(m):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    return lab == (1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))) if n > 1 else m


def ts_letters(rgb):
    """yellow letters with their blue edge, off the sky and off the red plate"""
    r, g, b = [rgb[..., i].astype(np.int32) for i in range(3)]
    yel = (r > 170) & (g > 130) & (b < 130) & (r - b > 90)
    blu = (b > 110) & (r < 100) & (b - r > 70)
    m = cv2.morphologyEx((yel | blu).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = _biggest(m)
    filled = np.zeros_like(m, np.uint8)
    cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(filled, cs, -1, 1, -1)
    hole = (filled == 1) & ~(yel | blu) & (r > 95)  # the sky showing through the O stays a hole
    return rgb, _soft(filled.astype(bool) & ~cv2.erode(hole.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool))


def ts_plate(y0f, y1f):
    """the red plate with STORY on it; the bits of TOY and the 5 that overlap it are painted back to red"""
    def fn(rgb):
        r, g, b = [rgb[..., i].astype(np.int32) for i in range(3)]
        red = (r > 130) & (g < 80) & (b < 90)
        hull = np.zeros(red.shape, np.uint8)
        pts = cv2.findNonZero(_biggest(cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))).astype(np.uint8))
        cv2.fillConvexPoly(hull, cv2.convexHull(pts), 1)
        h = rgb.shape[0]
        band = np.zeros(red.shape, bool); band[int(y0f * h):int(y1f * h)] = True  # the rows holding STORY
        keep = red | (band & (hull == 1))
        out = rgb.copy(); out[(hull == 1) & ~keep] = np.median(rgb[red], axis=0).astype(np.uint8)
        return out, _soft(hull)
    return fn


disney('toy-story-5-2026', ('strip', dict(x0=.0, blur=14, wash=((36, 124, 242), .6))), fin=dict(CLAM, vivid=.3),
       title=LC([(0.375, 0.064, 0.625, 0.146), (0.380, 0.126, 0.610, 0.190), (0.450, 0.168, 0.550, 0.250)], 170, gapf=.05,
          cuts=[ts_letters, ts_plate(.30, .68), ts_letters]),
       face=ph(.335, .305, .19, 1.4))

# Hoppers: the poster's yellow all the way down, its glitchy black lettering
disney('hoppers-2026', ('grad', [(0, (255, 214, 28)), (.6, (255, 202, 18)), (1, (252, 178, 10))]), fin=dict(CLAM, vivid=.22),
       title=L(tb('hoppers-2026'), 120, (20, 18, 16), speck=.001), face=ph(.5, .305, .22, 1.4), lcol=(20, 18, 16), ink=(20, 18, 16))

# Zootopia 2: the film's own title logo (Ian supplied the image: logos/zootopia-2-title.png, kept on its
# night-blue field and feathered at the edges), on a spine graded to the same blues
disney('zootopia-2-2025', ('grad', [(0, (8, 8, 34)), (.5, (12, 12, 50)), (1, (10, 16, 46))]),
       Pic('logos/zootopia-2-title.png', 226), ph(.47, .705, .2, 1.4), lcol=WHT, side=4, studio=False)

# ----- 2024 Pixar clamshells -----
def key_cut(test, soft=1.4):
    """an LC cut: keep the pixels where test(rgb float 0..1 array) is true, in their own colours"""
    def fn(rgb):
        a = rgb.astype(np.float32) / 255
        m = test(a).astype(np.float32)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats((m > .5).astype(np.uint8))
        if n > 1:
            big = st[1:, cv2.CC_STAT_AREA].max(); keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] > big * .02
            m = m * keep[lab]
        return rgb, _soft(m, soft)
    return fn


def fill_cut(ground=(0, 0, 0), tol=40, soft=1.2):
    """an LC cut for outlined lettering filled with pictures on a flat ground (The Bad Kids): keeps everything
    an outline encloses, in its own colours, and opens the counters that show the ground through them"""
    def fn(rgb):
        a = rgb.astype(np.float32)
        gnd = np.sqrt(((a - np.array(ground, np.float32)) ** 2).sum(axis=2)) < tol
        pad = cv2.copyMakeBorder(gnd.astype(np.uint8), 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=1)
        cv2.floodFill(pad, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 2)
        m = (pad[2:-2, 2:-2] != 2).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats((gnd & (m > 0)).astype(np.uint8), connectivity=4)
        hole = np.zeros(n, bool); hole[1:] = st[1:, cv2.CC_STAT_AREA] > 0.002 * m.size
        m[hole[lab]] = 0
        return rgb, _soft(m.astype(np.float32), soft)
    return fn

_sat = lambda a: a.max(2) - a.min(2)
_lum = lambda a: a @ np.array([.299, .587, .114], np.float32)

# Elemental: Element City night blue, ELEMENTAL typeset letter by letter in the poster logo's colours (its translucent
# letters over the busy art won't cut out cleanly; Ian can supply the logo), Ember in the diamond
disney('elemental-2023', ('grad', [(0, (40, 60, 140)), (.5, (24, 30, 90)), (1, (10, 12, 40))]), fin=dict(CLAM, vivid=.2),
       title=TT([('E', (150, 120, 230)), ('L', (196, 90, 226)), ('E', (244, 106, 30)), ('M', (246, 44, 100)), ('E', (200, 176, 60)), ('N', (90, 180, 96)), ('T', (30, 206, 186)), ('A', (60, 200, 250)), ('L', (80, 234, 214))], 'advb', 110, sp=-.02),
       face=ph(.59, .385, .2, 1.4), lcol=WHT)

# Inside Out 2: the emotions' blue-violet, the poster's white tilted logo, Joy in the diamond
disney('inside-out-2-2024', ('grad', [(0, (110, 90, 200)), (.5, (60, 60, 160)), (1, (24, 24, 70))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.27, 0.745, 0.76, 0.915)], 150, cuts=[key_cut(lambda a: (_lum(a) > .86) & (_sat(a) < .2))]),
       face=ph(.515, .43, .24, 1.4), lcol=WHT)

# Kitbull (a short): sketchbook white, the hand-lettered Kit / Bull cut off the poster, the kitten in the diamond
disney('kitbull-2019', ('grad', [(0, (250, 248, 240)), (.6, (240, 232, 214)), (1, (226, 214, 190))]), fin=dict(CLAM),
       title=LC([(0.77, 0.065, 0.97, 0.175), (0.77, 0.18, 0.97, 0.265)], 120, gapf=.12, cuts=[key_cut(lambda a: _lum(a) < .5), key_cut(lambda a: (_lum(a) < .9) & (_sat(a) > .05))]),
       face=ph(.46, .63, .26, 1.4), lcol=(30, 30, 34), ink=(30, 30, 34))

# Purl (a short): open-plan office grey, the pink yarn script cut off the poster, Purl herself in the diamond
disney('purl-2019', ('grad', [(0, (196, 204, 214)), (.6, (150, 158, 170)), (1, (90, 96, 106))]), fin=dict(CLAM, vivid=.15),
       title=LC([(0.32, 0.795, 0.69, 0.935)], 130, cuts=[key_cut(lambda a: (a[..., 0] > a[..., 1] + .12) & (_lum(a) > .45))]),
       face=ph(.53, .44, .26, 1.4), lcol=(30, 30, 40), ink=(30, 30, 40))


# =====================================================================================
# the 2023 shelf (films-2023.json).  Same approach as 2025 and 2024: lettering boxes given
# directly (checked with check_boxes.py), typeset where the lettering won't lift.
# =====================================================================================

# The Menu: the island restaurant's black, the white "the MENU", the chef over his guests
std('the-menu-2022', ('grad', [(0, (24, 22, 20)), (.6, (12, 11, 10)), (1, (4, 4, 4))]), WHT,
    [L((0.40, 0.035, 0.60, 0.10), 44, WHT, mode='light', speck=.01), L((0.22, 0.105, 0.78, 0.20), 110, WHT, mode='light', speck=.01)],
    tgap=6, photo=ph(.5, .36, .45, 1.0), pb=(226, 214, 190), lg=WHT, lw=.8, order='LPTCF', credit=['A MARK MYLOD', 'FILM'], ccol=(226, 214, 190),
    ft='b', fcol=(180, 176, 170), fin=MINT)

# Double Jeopardy (1999): a real rental, midnight blue, the knife between the two faces, white serif capitals
std('double-jeopardy-1999', ('grad', [(0, (40, 40, 120)), (.5, (16, 16, 54)), (1, (4, 4, 14))]), WHT,
    L((0.07, 0.865, 0.93, 0.94), 66, WHT, mode='light', speck=.01),
    photo=ph(.45, .3, .8, .9), pb=(200, 206, 240), lg=WHT, lw=.5, order='LPTSF', stick=BAR('15 01999', top='THRILLER'),
    ft='a', vbox=(200, 206, 240), vink=(16, 16, 54), fcol=(190, 196, 230), fin=RENTAL, seed=1999)

# The Banshees of Inisherin: Achill sky, the poster's olive-gold serif, the two men on the strand
std('the-banshees-of-inisherin-2022', ('grad', [(0, (226, 224, 196)), (.6, (196, 194, 160)), (1, (120, 118, 96))]), (110, 116, 40),
    L([(0.42, 0.125, 0.58, 0.19), (0.11, 0.185, 0.89, 0.27), (0.2, 0.265, 0.8, 0.33)], 92, (104, 112, 34), mode='key', key=(118, 124, 44), t=(60, 140), speck=.01, gapf=.18),
    photo=ph(.5, .66, 1.0, .5), pb=(104, 112, 34), lg=(60, 62, 30), lw=.8, order='LPTCF', credit=['COLIN FARRELL', 'BRENDAN GLEESON'], ccol=(60, 62, 30),
    ft='a', vbox=(104, 112, 34), vink=(226, 224, 196), fcol=(60, 62, 30), fin=MINT)

# Louis C.K.: Back to the Garden: a Garden show-bill, red card, white and black wood type
std('louis-c-k-back-to-the-garden-2023', ('solid', (196, 60, 42)), WHT,
    [L((0.03, 0.08, 0.97, 0.18), 70, WHT, mode='light', speck=.01), L((0.06, 0.185, 0.94, 0.28), 52, (34, 16, 14), mode='dark', speck=.01)],
    photo=ph(.5, .53, .55, 1.0), pb=(240, 226, 200), studio=['STAND-UP', 'SPECIAL'], scol=(240, 226, 200), order='lPTF', tgap=10,
    ft='b', fcol=(250, 226, 210), fin=SLIP)

# Black Panther: Wakanda Forever: Talokan blue-black, silver capitals (typeset: thin, over the crowd), Shuri at the head
std('black-panther-wakanda-forever-2022', ('grad', [(0, (40, 50, 70)), (.6, (16, 22, 34)), (1, (4, 6, 10))]), WHT,
    [T('BLACK PANTHER', 'hcnb', 28, (210, 214, 224), track=.14),
     T('WAKANDA FOREVER', 'ter', 76, WHT, track=.04, bold=.4, grad=[(0, (252, 252, 254)), (.5, (170, 176, 196)), (1, (232, 234, 242))])],
    photo=ph(.5, .15, .4, 1.0), pb=(150, 120, 220), lg=None, lw=.8, order='LPTF', tgap=10,
    ft='a', vbox=(150, 120, 220), vink=(16, 22, 34), fcol=(190, 196, 214), fin=SLIP)

# Nothing Lasts Forever: jeweller's skin tones, the diamond in the tweezers, white serif capitals
std('nothing-lasts-forever-2022', ('grad', [(0, (150, 110, 90)), (.6, (90, 62, 50)), (1, (30, 20, 16))]), WHT,
    [L((0.11, 0.69, 0.89, 0.765), 56, WHT, mode='light', speck=.01), L((0.1, 0.765, 0.9, 0.85), 56, WHT, mode='light', speck=.01)],
    photo=ph(.5, .38, .6, 1.0), pb=(236, 230, 220), lg=WHT, lw=.8, order='LPTCF', tgap=8, credit=['A JASON KOHN', 'FILM'], ccol=(236, 220, 200),
    ft='b', fcol=(220, 200, 186), fin=MINT)

# The Whale: the apartment's lamp-lit dark, the poster's pale sea-green serif
std('the-whale-2022', ('grad', [(0, (40, 60, 62)), (.6, (20, 30, 32)), (1, (6, 10, 10))]), (174, 218, 206),
    L((0.11, 0.815, 0.87, 0.895), 76, (176, 220, 208), mode='key', key=(170, 214, 202), t=(60, 140), speck=.01),
    photo=ph(.4, .42, .7, .9), pb=(174, 218, 206), lg=WHT, lw=.5, order='LPTCF', credit=['A DARREN ARONOFSKY', 'FILM'], ccol=(174, 218, 206),
    ft='b', fcol=(170, 196, 192), fin=MINT)

# Identity (2003): storm-night cyan, white serif capitals, the faces in the rain
std('identity-2003', ('grad', [(0, (30, 90, 130)), (.5, (10, 34, 56)), (1, (4, 10, 18))]), WHT,
    L((0.09, 0.075, 0.93, 0.16), 76, WHT, mode='light', speck=.01),
    photo=ph(.5, .45, .9, .7), pb=(170, 220, 240), lg=WHT, lw=.7, order='LPTF',
    ft='a', vbox=(170, 220, 240), vink=(10, 34, 56), fcol=(180, 210, 226), fin=WORN, seed=2003)

# Gully: LA haze, the big chiselled white serif, the four of them
std('gully-2021', ('grad', [(0, (96, 110, 120)), (.6, (40, 44, 48)), (1, (10, 10, 12))]), WHT,
    L((0.03, 0.68, 0.97, 0.84), 100, WHT, mode='light', speck=.01),
    photo=ph(.5, .32, 1.0, .6), pb=(236, 232, 226), lg=WHT, lw=.6, order='LPTCF', credit=['JACOB LATIMORE', 'CHARLIE PLUMMER'], ccol=(236, 232, 226),
    ft='a', vbox=(236, 232, 226), vink=(40, 44, 48), fcol=(196, 196, 196), fin=SLIP)

# The Black Phone: basement brown-black, the Grabber's grin, red condensed capitals (typeset: the poster's are scratched and broke up)
std('the-black-phone-2022', ('grad', [(0, (70, 52, 40)), (.5, (30, 22, 16)), (1, (8, 6, 4))]), (214, 62, 44),
    [T('THE', 'hcnb', 30, (216, 64, 46), track=.1), T('BLACK PHONE', 'hcnb', 96, (216, 64, 46), squeeze=.86, bold=.6, rough=.5)], tgap=8,
    photo=ph(.5, .32, .6, 1.0), pb=(214, 62, 44), lg=WHT, lw=.8, order='LPTCF', credit=['ETHAN HAWKE'], ccol=(214, 62, 44),
    ft='a', vbox=(214, 62, 44), vink=(30, 22, 16), fcol=(200, 186, 176), fin=SLIP, dotst=(['HORROR'], (214, 62, 44)))

# Missing: laptop-screen blue, the hot-pink glitch lettering
std('missing-2023', ('grad', [(0, (40, 90, 150)), (.6, (16, 40, 76)), (1, (6, 12, 24))]), (240, 60, 100),
    L((0.08, 0.05, 0.92, 0.195), 104, (242, 64, 104), mode='key', key=(236, 56, 96), t=(70, 160), speck=.0005),
    photo=ph(.5, .38, .5, 1.0), pb=(240, 60, 100), lg=WHT, lw=.8, order='LPTCF', credit=['STORM REID'], ccol=WHT,
    ft='a', vbox=(240, 60, 100), fcol=(190, 206, 226), fin=MINT)

# Triangle of Sadness: Mediterranean sky, cream serif capitals (typeset: they sit on the white sky), the yacht below
std('triangle-of-sadness-2022', ('grad', [(0, (150, 196, 226)), (.6, (60, 120, 170)), (1, (20, 44, 70))]), (250, 244, 226),
    T('TRIANGLE OF SADNESS', 'ter', 74, (250, 244, 226), squeeze=.8, bold=.5, shadow=((20, 44, 70), 2, 2)),
    photo=ph(.5, .62, 1.0, .6), pb=(250, 244, 226), lg=WHT, lw=.8, order='LPTCF', credit=['A RUBEN ÖSTLUND', 'FILM'], ccol=(250, 244, 226),
    ft='a', vbox=(250, 244, 226), vink=(20, 44, 70), fcol=(220, 230, 240), fin=MINT, dotst=(['STAFF', 'PICK'], (230, 70, 60)))

# Tár: concert-hall black, the poster's grey block capitals
std('tar-2022', ('grad', [(0, (30, 30, 30)), (.6, (14, 14, 14)), (1, (4, 4, 4))]), (196, 196, 192),
    L((0.13, 0.49, 0.87, 0.685), 110, (200, 200, 196), mode='light', speck=.01),
    photo=ph(.5, .24, 1.0, .66), pb=(200, 200, 196), lg=WHT, lw=.8, order='LPTCF', credit=['CATE BLANCHETT'], ccol=(200, 200, 196),
    ft='b', fcol=(170, 170, 166), fin=MINT)

# Chris Rock: Selective Outrage: the marquee-bulb red, cream condensed capitals (typeset: SELECTIVE is too small to lift)
std('chris-rock-selective-outrage-2023', ('grad', [(0, (150, 30, 24)), (.6, (80, 14, 12)), (1, (20, 4, 4))]), (244, 232, 180),
    [T('CHRIS ROCK', 'hcnb', 70, (246, 234, 184), bold=.6, shadow=((40, 6, 4), 3, 3)), T('SELECTIVE OUTRAGE', 'hcnb', 70, (246, 234, 184), bold=.6, shadow=((40, 6, 4), 3, 3))],
    photo=ph(.55, .3, .6, 1.0), pb=(244, 232, 180), studio=['LIVE STAND-UP', 'SPECIAL'], scol=(244, 232, 180), order='lPTF', tgap=10,
    ft='b', fcol=(230, 200, 180), fin=MINT)

# The Fabelmans: a strip of home movies at the head, white Roman capitals on the dark
std('the-fabelmans-2022', ('grad', [(0, (60, 52, 40)), (.6, (26, 22, 18)), (1, (6, 6, 4))]), WHT,
    L((0.05, 0.84, 0.95, 0.925), 70, WHT, mode='light', speck=.01),
    photo=ph(.5, .25, .9, .9), pb=(236, 226, 200), lg=None, lw=.6, order='LPTCF', credit=['A STEVEN SPIELBERG', 'FILM'], ccol=(236, 226, 200),
    ft='a', vbox=(236, 226, 200), vink=(26, 22, 18), fcol=(206, 196, 180), fin=MINT)

# Reality: interrogation-room blush, the poster's hot-pink block capitals
std('reality-2023', ('grad', [(0, (250, 236, 240)), (.6, (236, 214, 222)), (1, (190, 170, 180))]), (236, 110, 226),
    L((0.1, 0.12, 0.9, 0.305), 108, (232, 100, 224), mode='key', key=(240, 120, 236), t=(60, 120), speck=.01),
    photo=ph(.5, .67, .4, 1.0), pb=(236, 110, 226), studio=['FIT VIA VI'], scol=(40, 40, 46), order='lPTCF', credit=['SYDNEY SWEENEY'], ccol=(40, 40, 46),
    ft='a', vbox=(236, 110, 226), fcol=(40, 40, 46), fin=MINT)

# John Wick: Chapter 4: Paris at sunrise, blazing orange, the red brush capitals (typeset: they sit on the sky's own orange)
std('john-wick-chapter-4-2023', ('grad', [(0, (220, 140, 50)), (.5, (130, 60, 20)), (1, (30, 10, 4))]), (230, 40, 30),
    [T('JOHN WICK', 'hcnb', 100, (232, 44, 32), squeeze=.8, bold=.6, rough=.4, outline=((40, 10, 4), 1.6)), T('CHAPTER 4', 'herbi', 34, WHT, track=.3)],
    photo=ph(.5, .15, .4, 1.0), pb=(232, 44, 32), lg=WHT, lw=.8, order='LPTCF', tgap=10, credit=['KEANU REEVES'], ccol=WHT,
    ft='a', vbox=(232, 44, 32), fcol=(250, 220, 190), fin=SLIP)

# I Like Movies: a video store's beige carpet, the red signwriter's script
std('i-like-movies-2023', ('grad', [(0, (226, 214, 190)), (.6, (200, 186, 160)), (1, (130, 116, 96))]), (180, 34, 44),
    L((0.05, 0.04, 0.95, 0.215), 120, (186, 36, 46), mode='key', key=(180, 40, 50), t=(70, 150), speck=.01),
    photo=ph(.47, .6, .5, 1.0), pb=(186, 36, 46), studio=['DIRECTED BY', 'CHANDLER LEVACK'], scol=(60, 40, 34), order='lPTSF',
    stick=RWD(), ft='a', vbox=(186, 36, 46), fcol=(60, 40, 34), fin=WORN, dotst=(['STAFF', 'PICK'], (30, 90, 170)))

# Tom Segura: Sledgehammer: stage black, red and cream heavy capitals (typeset: the lift lost the T's bar)
std('tom-segura-sledgehammer-2023', ('grad', [(0, (40, 36, 34)), (.6, (18, 16, 16)), (1, (6, 6, 6))]), (226, 40, 30),
    [T('TOM SEGURA', 'intbk', 70, (228, 44, 34), squeeze=.9), T('SLEDGEHAMMER', 'intbk', 50, (240, 228, 196), squeeze=.9)],
    photo=ph(.48, .3, .6, 1.0), pb=(240, 228, 196), studio=['STAND-UP', 'SPECIAL'], scol=(240, 228, 196), order='lPTF', tgap=10,
    ft='b', fcol=(200, 196, 190), fin=MINT)

# Guardians of the Galaxy Vol. 3: the poster's cosmic pink-to-violet, white capitals keylined in black (typeset: the logo's outlines won't lift off white)
std('guardians-of-the-galaxy-vol-3-2023', ('grad', [(0, (60, 30, 110)), (.5, (180, 60, 120)), (1, (40, 16, 60))]), WHT,
    [T('GUARDIANS OF THE GALAXY', 'intbk', 70, WHT, squeeze=.86, outline=((20, 20, 24), 2.4), shadow=((20, 20, 24), 3, 3)),
     T('VOLUME 3', 'intbk', 30, (20, 20, 24), track=.2, box=(WHT, 8, 3))],
    photo=ph(.5, .45, 1.0, .7), pb=WHT, lg=None, lw=.8, order='LPTF', tgap=10,
    ft='a', vbox=WHT, vink=(60, 30, 110), fcol=(230, 220, 236), fin=SLIP, dotst=(['NEW', 'RELEASE'], (240, 200, 40), (20, 20, 24)))

# Reptile: wire-mesh grey, the big white block capitals, Benicio behind the screen
std('reptile-2023', ('grad', [(0, (130, 130, 128)), (.6, (70, 70, 68)), (1, (20, 20, 20))]), WHT,
    L((0.06, 0.115, 0.94, 0.215), 104, WHT, mode='light', speck=.01),
    photo=ph(.66, .47, .5, 1.0), pb=(236, 234, 228), lg=WHT, lw=.4, order='LPTCF', credit=['BENICIO DEL TORO', 'JUSTIN TIMBERLAKE'], ccol=(236, 234, 228),
    ft='b', fcol=(200, 200, 196), fin=MINT)

# Falling Down (1993): a real rental, LA smog white, the poster's red capitals in their white box (typeset: thin, the lift broke), D-Fens with his briefcase
std('falling-down-1993', ('grad', [(0, (236, 232, 236)), (.6, (210, 204, 210)), (1, (150, 140, 140))]), (200, 30, 32),
    T('FALLING DOWN', 'intbk', 60, (204, 32, 34), squeeze=.9, box=(WHT, 8, 5, (204, 32, 34))),
    photo=ph(.5, .4, .5, 1.2), pb=(200, 30, 32), lg=None, lw=.6, order='LPTSF', stick=PRC(['2 NIGHTS', '$2.49']),
    ft='a', vbox=(200, 30, 32), fcol=(40, 36, 36), fin=RENTAL, seed=1993)

# The Equalizer 3: Amalfi gold and the red slash, white heavy capitals (typeset: they run diagonally on the poster)
std('the-equalizer-3-2023', ('grad', [(0, (180, 130, 60)), (.5, (100, 50, 24)), (1, (20, 10, 4))]), WHT,
    [T('THE', 'intbk', 30, WHT, track=.1), TT([('EQUALIZER', WHT), ('3', (220, 36, 36))], 'intbk', 90, sp=.25, squeeze=.86)],
    photo=ph(.17, .37, .3, 1.0), pb=(220, 36, 36), lg=WHT, lw=.7, order='LPTCF', tgap=8, credit=['DENZEL WASHINGTON'], ccol=WHT,
    ft='a', vbox=(220, 36, 36), fcol=(240, 214, 190), fin=SLIP)

# Heist 88: Chicago 1988, a payphone at night, gold spaced capitals and white numerals (typeset: spaced too wide to lift)
std('heist-88-2023', ('grad', [(0, (50, 46, 30)), (.6, (22, 20, 14)), (1, (6, 6, 4))]), (236, 196, 50),
    TT([('HEIST', (238, 198, 52)), ('88', WHT)], 'hcnb', 84, sp=.4, track=.35),
    photo=ph(.6, .32, .4, 1.0), pb=(236, 196, 50), lg=None, lw=.5, order='LPTCF', credit=['COURTNEY B. VANCE'], ccol=(236, 196, 50),
    ft='a', vbox=(236, 196, 50), vink=(22, 20, 14), fcol=(200, 196, 180), fin=SLIP)

# Retribution: Berlin rush hour, steel teal, white heavy italic capitals (typeset: they run uphill on the poster)
std('retribution-2023', ('grad', [(0, (60, 90, 100)), (.6, (24, 38, 44)), (1, (6, 10, 12))]), WHT,
    T('RETRIBUTION', 'intbki', 84, WHT, squeeze=.9, shadow=((6, 10, 12), 3, 3)),
    photo=ph(.45, .13, .5, 1.0), pb=(236, 140, 50), studio=['THE PICTURE COMPANY'], scol=WHT, order='lPTCF', credit=['LIAM NEESON'], ccol=(236, 140, 50),
    ft='a', vbox=(236, 140, 50), vink=(24, 38, 44), fcol=(190, 206, 210), fin=SLIP)

# Fair Play: trading-floor night, thin white capitals spaced wide (typeset: hairline, over the faces)
std('fair-play-2023', ('grad', [(0, (40, 50, 56)), (.6, (18, 22, 26)), (1, (6, 6, 8))]), WHT,
    T('FAIR PLAY', 'her', 70, WHT, track=.5, bold=.3),
    photo=ph(.5, .25, .9, .8), pb=(236, 232, 226), lg=WHT, lw=.8, order='LPTCF', credit=['PHOEBE DYNEVOR', 'ALDEN EHRENREICH'], ccol=(236, 232, 226),
    ft='b', fcol=(180, 186, 190), fin=MINT)

# Sound of Freedom: bright white, the heavy black FREEDOM (typeset: the figures stand on it)
std('sound-of-freedom-2023', ('grad', [(0, (252, 248, 240)), (.6, (236, 230, 220)), (1, (170, 164, 156))]), (16, 16, 16),
    [T('SOUND OF', 'her', 30, (16, 16, 16), track=.5), T('FREEDOM', 'intbk', 100, (16, 16, 16), squeeze=.8)],
    photo=ph(.5, .25, .6, 1.0), pb=(16, 16, 16), studio=['ANGEL STUDIOS'], scol=(16, 16, 16), order='lPTCF', tgap=10, credit=['JIM CAVIEZEL'], ccol=(16, 16, 16),
    ft='a', vbox=(16, 16, 16), fcol=(16, 16, 16), fin=MINT)

# Old Dads: whitewashed brick, the poster's royal-blue fat capitals, the three dads
std('old-dads-2023', ('grad', [(0, (240, 238, 234)), (.6, (220, 216, 210)), (1, (160, 154, 146))]), (30, 70, 190),
    L([(0.2, 0.1, 0.82, 0.215), (0.08, 0.215, 0.92, 0.33)], 110, (32, 72, 192), mode='key', key=(30, 70, 190), t=(70, 150), speck=.01, gapf=.22),
    photo=ph(.5, .68, 1.0, .55), pb=(32, 72, 192), lg=None, lw=.8, order='LPTCF', credit=['A BILL BURR', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(32, 72, 192), fcol=(30, 30, 34), fin=MINT, dotst=(['COMEDY'], (220, 40, 40)))

# Oppenheimer: the Trinity fireball, burnt orange, thin capitals spaced wide (typeset: hairline over the flames)
std('oppenheimer-2023', ('grad', [(0, (200, 90, 20)), (.5, (100, 34, 8)), (1, (20, 6, 2))]), (246, 120, 50),
    T('OPPENHEIMER', 'her', 66, (248, 124, 52), track=.4, bold=.5),
    photo=ph(.5, .4, .5, 1.0), pb=(248, 124, 52), lg=WHT, lw=.8, order='LPTCF', credit=['A CHRISTOPHER NOLAN', 'FILM'], ccol=(248, 200, 160),
    ft='a', vbox=(248, 124, 52), vink=(20, 6, 2), fcol=(240, 200, 170), fin=dict(SLIP, gloss=.09))

# Quiz Lady: game-show sky blue, puffy cream capitals stacked on red and violet (typeset: the poster's are 3-D)
std('quiz-lady-2023', ('grad', [(0, (120, 176, 220)), (.6, (60, 110, 170)), (1, (20, 40, 70))]), (252, 240, 210),
    T('QUIZ LADY', 'popb', 92, (252, 240, 210), outline=((236, 70, 70), 2.5), shadow=((110, 70, 190), 6, 6)),
    photo=ph(.25, .55, .45, 1.0), pb=(252, 240, 210), lg=WHT, lw=.5, order='LPTCF', credit=['AWKWAFINA', 'SANDRA OH'], ccol=(252, 240, 210),
    ft='a', vbox=(236, 70, 70), fcol=(230, 236, 246), fin=MINT)

# The Foot Fist Way (2008): a strip-mall dojo's red, white and blue sunburst, fat cream lettering keylined in black (typeset)
std('the-foot-fist-way-2008', ('grad', [(0, (200, 40, 40)), (.5, (130, 24, 30)), (1, (30, 50, 110))]), (250, 244, 226),
    [T('THE', 'bonb', 30, (250, 244, 226), outline=((20, 20, 22), 1.6)), T('Foot Fist Way', 'bonb', 92, (250, 244, 226), outline=((20, 20, 22), 2.6), shadow=((20, 20, 22), 3, 3))],
    photo=ph(.62, .2, .35, 1.0), pb=WHT, studio=['PARAMOUNT VANTAGE'], scol=WHT, order='lPTCSF', tgap=8, credit=['DANNY McBRIDE'], ccol=WHT,
    stick=PRC(['$2.99', '2-DAY']), ft='a', vbox=WHT, vink=(130, 24, 30), fcol=(250, 230, 220), fin=WORN, seed=2008)

# The Mechanic (2011): rain-soaked street black, brushed-gold capitals like the poster's (typeset: the lift broke up)
std('the-mechanic-2011', ('grad', [(0, (60, 54, 40)), (.6, (24, 22, 16)), (1, (6, 6, 4))]), (214, 184, 100),
    [T('THE', 'hcnb', 28, (216, 186, 104), track=.2), T('MECHANIC', 'hcnb', 84, (216, 186, 104), bold=.6, track=.04, grad=[(0, (240, 214, 140)), (.6, (196, 160, 80)), (1, (150, 116, 50))])], tgap=6,
    photo=ph(.5, .2, .6, 1.0), pb=(214, 184, 100), lg=WHT, lw=.8, order='LPTCF', credit=['JASON STATHAM'], ccol=(214, 184, 100),
    ft='a', vbox=(214, 184, 100), vink=(24, 22, 16), fcol=(200, 196, 180), fin=WORN, seed=2011)

# The Killer: the painted Paris night, teal and flare, the poster's white "THE K...ller"
std('the-killer-2023', ('grad', [(0, (40, 70, 70)), (.6, (16, 28, 30)), (1, (4, 8, 8))]), WHT,
    L((0.17, 0.805, 0.82, 0.915), 92, WHT, mode='light', speck=.005),
    photo=ph(.5, .3, .6, 1.0), pb=(236, 230, 210), lg=None, lw=.6, order='LPTCF', credit=['A DAVID FINCHER', 'FILM'], ccol=(236, 230, 210),
    ft='b', fcol=(180, 196, 196), fin=MINT)

# Your Lucky Day: the painted face behind the lottery ticket, yellow heavy italic capitals
std('your-lucky-day-2023', ('grad', [(0, (60, 90, 120)), (.6, (26, 36, 52)), (1, (8, 10, 16))]), (246, 214, 60),
    [L((0.2, 0.815, 0.8, 0.85), 26, (246, 214, 60), mode='light', speck=.01), L((0.02, 0.85, 0.98, 0.945), 64, WHT, mode='light', speck=.01)],
    photo=ph(.5, .3, .7, .8), pb=(246, 214, 60), lg=None, lw=.6, order='LPTF', tgap=8,
    ft='a', vbox=(246, 214, 60), vink=(26, 36, 52), fcol=(196, 206, 220), fin=SLIP)

# The Art of Self-Defense (2019): the poster's karate-belt yellow, deep teal heavy capitals (typeset: the lift broke the D)
std('the-art-of-self-defense-2019', ('solid', (240, 200, 30)), (30, 84, 96),
    T('THE ART OF SELF-DEFENSE', 'intbk', 60, (28, 82, 94), squeeze=.86),
    photo=ph(.72, .77, .45, 1.0), pb=(30, 84, 96), lg=None, lw=.5, order='LPTCSF', credit=['JESSE EISENBERG'], ccol=(30, 84, 96),
    stick=RWD(), ft='a', vbox=(30, 84, 96), vink=(240, 200, 30), fcol=(30, 84, 96), fin=WORN)

# Shaun of the Dead (2004): zombie-blood red, the cricket bat, the white horror-comic capitals
std('shaun-of-the-dead-2004', ('grad', [(0, (176, 30, 30)), (.6, (110, 14, 16)), (1, (30, 4, 4))]), WHT,
    L([(0.22, 0.67, 0.78, 0.765), (0.36, 0.76, 0.64, 0.81), (0.3, 0.805, 0.72, 0.905)], 84, WHT, mode='light', speck=.01, gapf=.2, valign='mid'),
    photo=ph(.5, .3, .8, .8), pb=WHT, lg=None, lw=.5, order='LPTCSF', credit=['SIMON PEGG', 'NICK FROST'], ccol=WHT,
    stick=flow(dot, 70, ['CULT', 'PICK'], (40, 120, 60), d=64), ft='a', vbox=WHT, vink=(110, 14, 16), fcol=(240, 210, 206), fin=WORN, seed=2004)

# Kingpin (1996): a bowling-alley rental, white with the red-and-orange cartoon capitals keylined in black (typeset: the poster's has a pin for the I)
std('kingpin-1996', ('grad', [(0, (246, 244, 238)), (.6, (226, 222, 214)), (1, (170, 164, 156))]), (226, 70, 40),
    T('KINGPIN', 'bonb', 100, (230, 78, 44), outline=((20, 20, 22), 2.6), shadow=((20, 20, 22), 3, 3), grad=[(0, (246, 150, 50)), (1, (214, 40, 36))]),
    photo=ph(.5, .38, .9, .7), pb=(214, 40, 36), lg=(20, 20, 22), lw=.6, order='LPTCSF', credit=['RANDY QUAID', 'BILL MURRAY'], ccol=(20, 20, 22),
    stick=RWD(fill=(250, 226, 70)), ft='a', vbox=(214, 40, 36), fcol=(20, 20, 22), fin=RENTAL, seed=1996)

# The Last Seduction (1994): smoke-brown black, the poster's red slab capitals
std('the-last-seduction-1994', ('grad', [(0, (60, 44, 36)), (.6, (24, 18, 14)), (1, (6, 4, 4))]), (220, 30, 36),
    L((0.04, 0.85, 0.96, 0.92), 76, (222, 34, 40), mode='key', key=(214, 34, 40), t=(70, 150), speck=.01),
    photo=ph(.45, .22, .6, 1.0), pb=(222, 34, 40), lg=WHT, lw=.6, order='LPTCF', credit=['A JOHN DAHL', 'FILM'], ccol=(222, 34, 40),
    ft='a', vbox=(222, 34, 40), vink=(24, 18, 14), fcol=(200, 186, 176), fin=RENTAL, seed=1994)

# Badlands (1973): an old library copy, white card, the oxblood brush script, Kit with his rifle against the sunset
std('badlands-1973', ('grad', [(0, (244, 240, 230)), (.6, (226, 218, 200)), (1, (170, 158, 136))]), (160, 26, 40),
    L((0.08, 0.025, 0.92, 0.21), 130, (164, 28, 42), mode='key', key=(160, 30, 44), t=(70, 150), speck=.01),
    photo=ph(.5, .55, .8, .8), pb=(164, 28, 42), studio=['WARNER BROS.'], scol=(40, 34, 30), order='lPTCSF', credit=['A TERRENCE MALICK', 'FILM'], ccol=(40, 34, 30),
    stick=PRC(['$1.99', 'CLASSIC']), ft='e', fcol=(40, 34, 30), fin=OLD, seed=1973)

# Midnight Run (1988): a real rental, desert-highway sky blue, navy spaced MIDNIGHT and the red brush RUN (typeset)
std('midnight-run-1988', ('grad', [(0, (180, 204, 226)), (.6, (120, 150, 180)), (1, (60, 66, 76))]), (30, 40, 110),
    [T('MIDNIGHT', 'terb', 40, (30, 40, 110), track=.4), T('RUN', 'intbki', 110, (220, 36, 30), rough=.6, skew=-.1)],
    photo=ph(.5, .55, .9, .8), pb=(220, 36, 30), lg=(30, 40, 110), lw=.6, order='LPTCSF', tgap=8, credit=['ROBERT DE NIRO', 'CHARLES GRODIN'], ccol=(30, 40, 110),
    stick=BAR('15 01988', top='COMEDY', fill=(240, 238, 230), ink=(30, 34, 60)), ft='a', vbox=(220, 36, 30), fcol=(30, 34, 50), fin=RENTAL, seed=1988)

# Things to Do in Denver When You're Dead (1995): black, the orange typewriter serif and the small red "when you're dead"
std('things-to-do-in-denver-when-you-re-dead-1995', ('grad', [(0, (50, 30, 14)), (.6, (20, 12, 6)), (1, (4, 2, 2))]), (236, 150, 40),
    [L((0.07, 0.8, 0.93, 0.86), 54, (238, 154, 44), mode='key', key=(232, 150, 44), t=(70, 150), speck=.01),
     L((0.3, 0.858, 0.78, 0.895), 30, (220, 50, 40), mode='key', key=(214, 50, 40), t=(70, 150), speck=.01)],
    photo=ph(.5, .3, .6, 1.0), pb=(236, 150, 40), lg=WHT, lw=.7, order='LPTF', tgap=8,
    ft='a', vbox=(236, 150, 40), vink=(20, 12, 6), fcol=(200, 180, 160), fin=RENTAL, seed=1995)

# Sleuth (1972): ink-blue fingerprint whorls, the cream heavy capitals in quotes (typeset: the U is a fingerprint)
std('sleuth-1972', ('grad', [(0, (40, 50, 130)), (.6, (20, 24, 70)), (1, (6, 8, 20))]), (240, 226, 190),
    T('"SLEUTH"', 'intbk', 96, (242, 228, 192), shadow=((6, 8, 20), 3, 3)),
    photo=ph(.27, .6, .5, 1.0), pb=(242, 228, 192), studio=['20TH CENTURY', 'FOX'], scol=(242, 228, 192), order='lPTCSF', credit=['LAURENCE OLIVIER', 'MICHAEL CAINE'], ccol=(242, 228, 192),
    stick=PRC(['$1.99', 'CLASSIC']), ft='e', fcol=(200, 204, 230), fin=OLD, seed=1972)

# Barbie: Malibu sky blue, the logo cut off the poster whole (pale letters on the hot-pink plate), Barbie in the Corvette
std('barbie-2023', ('grad', [(0, (60, 190, 240)), (.6, (40, 150, 220)), (1, (240, 150, 200))]), (236, 60, 160),
    LC([(0.07, 0.085, 0.93, 0.305)], 175, cuts=[key_cut(lambda a: a[..., 0] > a[..., 2] * .8 + .05)]),
    photo=ph(.5, .73, .8, .8), pb=(236, 60, 160), lg=WHT, lw=.8, order='LPTCF', credit=['A GRETA GERWIG', 'FILM'], ccol=WHT,
    ft='a', vbox=(236, 60, 160), fcol=WHT, fin=MINT, dotst=(['NEW', 'RELEASE'], (236, 60, 160)))

# Bye Bye Barry: Lions Honolulu blue, the white script and slab, Barry Sanders mid-cut
std('bye-bye-barry-2023', ('grad', [(0, (40, 100, 150)), (.6, (16, 44, 70)), (1, (4, 12, 20))]), WHT,
    L((0.13, 0.58, 0.87, 0.87), 140, WHT, mode='light', speck=.01),
    photo=ph(.6, .28, .6, 1.0), pb=(180, 200, 214), lg=None, lw=.8, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(180, 200, 214),
    ft='b', fcol=(170, 190, 206), fin=MINT)

# Unknown (2011): Berlin night teal, the ice-and-white italic capitals (typeset: the lift lost the pale UN), Liam Neeson in the snow
std('unknown-2011', ('grad', [(0, (30, 80, 90)), (.6, (12, 30, 36)), (1, (4, 8, 10))]), WHT,
    TT([('UN', (120, 180, 190)), ('KNOWN', WHT)], 'intbki', 80, sp=-.05, squeeze=.9),
    photo=ph(.55, .18, .5, 1.0), pb=(160, 210, 220), lg=WHT, lw=.6, order='LPTCF', credit=['LIAM NEESON'], ccol=(160, 210, 220),
    ft='a', vbox=(160, 210, 220), vink=(12, 30, 36), fcol=(180, 200, 206), fin=WORN, seed=2011)

# American Movie (1999): Wisconsin winter-sky blue, the black condensed capitals, Mark and Mike
std('american-movie-1999', ('grad', [(0, (200, 226, 246)), (.6, (150, 190, 226)), (1, (70, 100, 140))]), (20, 20, 24),
    L((0.07, 0.075, 0.93, 0.155), 76, (20, 20, 24), mode='dark', speck=.01),
    photo=ph(.5, .55, 1.0, .6), pb=(20, 20, 24), lg=(20, 20, 24), lw=.7, order='LPTCSF', credit=['A CHRIS SMITH', 'FILM'], ccol=(20, 20, 24),
    stick=PRC(['$2.99', 'DOCUMENTARY']), ft='a', fcol=(20, 20, 24), fin=RENTAL, seed=1999)

# Sick of Myself: Oslo garden green, the fat white capitals, Signe in her bandages
std('sick-of-myself-2022', ('grad', [(0, (90, 120, 50)), (.6, (40, 56, 24)), (1, (10, 14, 6))]), WHT,
    L((0.13, 0.06, 0.87, 0.26), 110, WHT, mode='light', speck=.01),
    photo=ph(.55, .55, .6, 1.0), pb=(220, 60, 70), lg=None, lw=.3, order='LPTCF', credit=['A KRISTOFFER BORGLI', 'FILM'], ccol=WHT,
    ft='a', vbox=(220, 60, 70), fcol=(220, 226, 206), fin=MINT, dotst=(['STAFF', 'PICK'], (220, 60, 70)))

# Carlito's Way (1993): a real rental, black, tall gold capitals (typeset: the poster's are stacked in two lines), Carlito in his leather coat
std('carlito-s-way-1993', ('grad', [(0, (30, 28, 34)), (.6, (12, 12, 16)), (1, (4, 4, 4))]), (176, 126, 50),
    T("CARLITO'S WAY", 'dsc', 100, (186, 136, 56), squeeze=.62, grad=[(0, (214, 170, 80)), (1, (150, 100, 36))]),
    photo=ph(.6, .22, .45, 1.0), pb=(186, 136, 56), lg=WHT, lw=.6, order='LPTCSF', credit=['AL PACINO', 'SEAN PENN'], ccol=(186, 136, 56),
    stick=BAR('18 01993', top='CRIME', fill=(236, 210, 110), ink=(40, 30, 10)), ft='a', vbox=(186, 136, 56), vink=(12, 12, 16), fcol=(190, 180, 166), fin=RENTAL, seed=1993)

# A Bronx Tale (1993): a real rental, Fordham Road night, the two faces at the head, the poster's red slab capitals
std('a-bronx-tale-1993', ('grad', [(0, (30, 28, 30)), (.6, (14, 12, 14)), (1, (4, 4, 4))]), (222, 44, 30),
    L((0.05, 0.885, 0.95, 0.955), 70, (224, 46, 32), mode='key', key=(220, 44, 30), t=(70, 150), speck=.01),
    photo=ph(.5, .3, 1.0, .6), pb=(224, 46, 32), lg=WHT, lw=.7, order='LPTCSF', credit=['ROBERT DE NIRO'], ccol=WHT,
    stick=flow(dot, 70, ['DRAMA'], (226, 190, 70), (30, 20, 10), d=60), ft='a', vbox=(224, 46, 32), fcol=(200, 196, 190), fin=RENTAL, seed=1993)

# Dogtooth (2009): the poster's plain cream, its red and blue wave framed at the head, black serif capitals
std('dogtooth-2009', ('solid', (242, 236, 220)), (34, 30, 30),
    L((0.18, 0.815, 0.82, 0.885), 70, (34, 30, 30), mode='dark', speck=.01),
    photo=ph(.5, .4, .7, .8), pb=(34, 30, 30), lg=None, lw=.6, order='LPTCF', credit=['A YORGOS LANTHIMOS', 'FILM'], ccol=(170, 40, 50),
    ft='e', fcol=(34, 30, 30), fin=WORN, seed=2009)

# In the Land of Saints and Sinners: Donegal dusk, the cream stacked capitals, Liam with his shotgun
std('in-the-land-of-saints-and-sinners-2023', ('grad', [(0, (70, 74, 60)), (.6, (30, 32, 26)), (1, (8, 8, 6))]), (240, 228, 196),
    L((0.205, 0.755, 0.8, 0.925), 140, (242, 230, 198), mode='light', speck=.002),
    photo=ph(.75, .17, .5, 1.0), pb=(242, 230, 198), lg=None, lw=.4, order='LPTCF', credit=['LIAM NEESON', 'KERRY CONDON'], ccol=(242, 230, 198),
    ft='a', vbox=(242, 230, 198), vink=(30, 32, 26), fcol=(200, 196, 180), fin=SLIP)

# Killers of the Flower Moon (206 min): a 2-tape set, Osage-red dust, white condensed capitals (typeset: they sit on the splattered red)
std('killers-of-the-flower-moon-2023', ('grad', [(0, (180, 60, 30)), (.5, (100, 30, 16)), (1, (24, 8, 4))]), (246, 236, 220),
    [T('KILLERS OF THE', 'hcnb', 44, (246, 236, 220), squeeze=.8, track=.06), T('FLOWER MOON', 'hcnb', 104, (246, 236, 220), squeeze=.72, bold=.4)],
    photo=ph(.4, .35, .8, .8), pb=(246, 236, 220), lg=WHT, lw=.5, order='LPTCSF', tgap=10, credit=['A MARTIN SCORSESE', 'PICTURE'], ccol=(246, 236, 220),
    stick=flow(dot, 112, ['2-TAPE', 'SET'], (246, 236, 220), (100, 30, 16), d=104), ft='c', vbox=(246, 236, 220), vink=(100, 30, 16), fcol=(240, 220, 200), fin=SLIP,
    W=2 * w_for(115), notch_w=1.5 * w_for(115))  # 2-tape box like The Brutalist's

# Cat Person: the kiss in close-up, flesh pink, the poster's yellow lower-case
std('cat-person-2023', ('grad', [(0, (200, 140, 130)), (.6, (130, 80, 76)), (1, (40, 22, 20))]), (244, 234, 40),
    L((0.02, 0.16, 0.98, 0.28), 96, (246, 236, 44), mode='key', key=(240, 230, 40), t=(70, 150), speck=.01),
    photo=ph(.5, .62, .8, 1.0), pb=(246, 236, 44), lg=WHT, lw=.8, order='LPTCF', credit=['EMILIA JONES', 'NICHOLAS BRAUN'], ccol=(246, 236, 44),
    ft='a', vbox=(246, 236, 44), vink=(130, 80, 76), fcol=(240, 220, 214), fin=MINT)

# Anatomy of a Fall: snow white, tall navy condensed capitals (typeset: the poster's are stacked four lines high), the body in the snow
std('anatomy-of-a-fall-2023', ('grad', [(0, (238, 238, 236)), (.6, (220, 220, 220)), (1, (160, 160, 166))]), (52, 60, 120),
    T('ANATOMY OF A FALL', 'hcnb', 104, (52, 60, 120), squeeze=.6, bold=.4),
    photo=ph(.17, .53, .3, .7), pb=(52, 60, 120), lg=None, lw=.3, order='LPTCF', credit=['A JUSTINE TRIET', 'FILM'], ccol=(52, 60, 120),
    ft='a', vbox=(52, 60, 120), fcol=(52, 60, 120), fin=MINT, dotst=(['STAFF', 'PICK'], (200, 40, 40)))

# Leave the World Behind: Long Island forest green, red spaced capitals (typeset: they sit on the road in the dark)
std('leave-the-world-behind-2023', ('grad', [(0, (70, 100, 90)), (.6, (24, 38, 34)), (1, (6, 10, 8))]), (210, 30, 30),
    T('LEAVE THE WORLD BEHIND', 'hcnb', 64, (236, 50, 40), track=.24, bold=.5),
    photo=ph(.5, .42, 1.0, .6), pb=(214, 32, 32), lg=WHT, lw=.8, order='LPTCF', credit=['JULIA ROBERTS', 'MAHERSHALA ALI'], ccol=WHT,
    ft='a', vbox=(214, 32, 32), fcol=(190, 206, 200), fin=MINT)

# Fast Charlie: Gulf Coast teal, the worn white capitals, Pierce Brosnan by the car
std('fast-charlie-2023', ('grad', [(0, (60, 150, 150)), (.6, (24, 70, 72)), (1, (6, 20, 22))]), WHT,
    L((0.17, 0.19, 0.83, 0.305), 96, WHT, mode='light', speck=.01),
    photo=ph(.42, .55, .5, 1.0), pb=(240, 200, 120), lg=WHT, lw=.4, order='LPTCF', credit=['PIERCE BROSNAN'], ccol=(240, 200, 120),
    ft='a', vbox=(240, 200, 120), vink=(24, 70, 72), fcol=(200, 220, 220), fin=SLIP)

# Alcarràs: Catalan summer, peach-orchard gold, the family in the evening field
std('alcarras-2022', ('grad', [(0, (220, 170, 100)), (.6, (150, 90, 40)), (1, (50, 26, 10))]), (248, 232, 170),
    L((0.19, 0.745, 0.81, 0.855), 96, (250, 234, 176), mode='light', speck=.003),
    photo=ph(.5, .45, 1.0, .6), pb=(250, 234, 176), lg=None, lw=.3, order='LPTCF', credit=['A CARLA SIMÓN', 'FILM'], ccol=(250, 234, 176),
    ft='a', vbox=(250, 234, 176), vink=(150, 90, 40), fcol=(250, 230, 200), fin=MINT, dotst=(['STAFF', 'PICK'], (40, 110, 60)))

# The Holdovers: Barton Academy snow white, the poster's red seventies serif
std('the-holdovers-2023', ('grad', [(0, (246, 244, 238)), (.6, (230, 226, 216)), (1, (170, 162, 150))]), (196, 34, 30),
    L((0.05, 0.105, 0.93, 0.285), 140, (200, 36, 32), mode='key', key=(196, 36, 32), t=(70, 150), speck=.01),
    photo=ph(.5, .55, .7, .8), pb=(200, 36, 32), lg=(30, 30, 34), lw=.7, order='LPTCSF', credit=['PAUL GIAMATTI'], ccol=(30, 30, 34),
    stick=RWD(), ft='a', vbox=(200, 36, 32), fcol=(30, 30, 34), fin=SLIP, dotst=(['STAFF', 'PICK'], (30, 90, 60)))

# Killer Joe (2012): black, KILLER in thin glowing orange and JOE in white-hot (typeset with a glow), Joe in his hat
std('killer-joe-2012', ('grad', [(0, (40, 26, 16)), (.6, (14, 10, 6)), (1, (4, 2, 2))]), (246, 150, 50),
    TT([('KILLER', (250, 170, 70)), ('JOE', (255, 240, 210))], 'hcn', 110, sp=-.02, squeeze=.7, soft=((240, 120, 30), 9, .9)),
    photo=ph(.45, .5, .7, .9), pb=(246, 150, 50), lg=None, lw=.7, order='LPTCF', credit=['MATTHEW', 'McCONAUGHEY'], ccol=(246, 150, 50),
    ft='a', vbox=(246, 150, 50), vink=(14, 10, 6), fcol=(200, 186, 170), fin=WORN, seed=2012)

# Ricky Gervais: Armageddon: stage-curtain red-black, white condensed name and the boxed ARMAGEDDON
std('ricky-gervais-armageddon-2023', ('grad', [(0, (80, 20, 20)), (.6, (30, 8, 8)), (1, (8, 2, 2))]), WHT,
    [L((0.21, 0.115, 0.79, 0.19), 70, WHT, mode='light', speck=.01), T('ARMAGEDDON', 'hcnb', 44, (20, 20, 20), squeeze=.8, box=(WHT, 8, 4))],
    photo=ph(.63, .55, .6, 1.0), pb=WHT, studio=['STAND-UP', 'SPECIAL'], scol=WHT, order='lPTF', tgap=12,
    ft='b', fcol=(210, 196, 190), fin=MINT)

# How to Have Sex: Malia sunburn pink, the white heavy capitals stacked on the poster (typeset), Tara looking up
std('how-to-have-sex-2023', ('grad', [(0, (226, 150, 140)), (.6, (160, 90, 90)), (1, (50, 24, 30))]), WHT,
    T('HOW TO HAVE SEX', 'intbk', 80, WHT, squeeze=.86),
    photo=ph(.62, .1, .5, .9), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A MOLLY MANNING', 'WALKER FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(160, 90, 90), fcol=(250, 230, 226), fin=MINT, dotst=(['STAFF', 'PICK'], (60, 160, 200)))

# Heavenly Creatures (1994): a real rental, Christchurch blue-black, the white serif capitals, Juliet at the head
std('heavenly-creatures-1994', ('grad', [(0, (40, 46, 70)), (.6, (18, 20, 32)), (1, (4, 4, 8))]), WHT,
    L((0.06, 0.07, 0.94, 0.25), 120, WHT, mode='light', speck=.01),
    photo=ph(.3, .55, .5, 1.0), pb=(214, 220, 236), lg=None, lw=.3, order='LPTCSF', credit=['A PETER JACKSON', 'FILM'], ccol=(214, 220, 236),
    stick=BAR('18 01994', top='DRAMA'), ft='a', vbox=(214, 220, 236), vink=(18, 20, 32), fcol=(190, 196, 214), fin=RENTAL, seed=1994)

# Sleeping with the Enemy (1991): a real rental, black, the condensed white lower-case and the red "enemy"
std('sleeping-with-the-enemy-1991', ('grad', [(0, (40, 30, 30)), (.6, (16, 12, 12)), (1, (4, 4, 4))]), WHT,
    L([(0.06, 0.085, 0.675, 0.17), (0.675, 0.085, 0.93, 0.17)], 84, [WHT, (220, 40, 40)], mode='light', speck=.01, gapf=.22),
    photo=ph(.45, .45, .7, .9), pb=(220, 40, 40), lg=WHT, lw=.5, order='LPTCF', credit=['JULIA ROBERTS'], ccol=WHT,
    ft='a', vbox=(220, 40, 40), fcol=(200, 190, 186), fin=RENTAL, seed=1991)

# The Chaser (2008): Seoul night black, the hand over the face, the poster's red heavy italic capitals
std('the-chaser-2008', ('grad', [(0, (40, 36, 34)), (.6, (14, 12, 12)), (1, (4, 4, 4))]), (214, 30, 36),
    L((0.03, 0.09, 0.97, 0.22), 96, (216, 32, 38), mode='key', key=(210, 30, 36), t=(70, 150), speck=.01),
    photo=ph(.5, .55, .8, .9), pb=(216, 32, 38), studio=['SHOWBOX'], scol=WHT, order='lPTCF', credit=['A NA HONG-JIN', 'FILM'], ccol=WHT,
    ft='a', vbox=(216, 32, 38), fcol=(200, 196, 190), fin=WORN, seed=2008)

# To Catch a Killer: Baltimore night blue, the white heavy capitals stacked on the poster (typeset), Eleanor at the head
std('to-catch-a-killer-2023', ('grad', [(0, (40, 50, 100)), (.6, (16, 20, 44)), (1, (4, 6, 14))]), WHT,
    T('TO CATCH A KILLER', 'intbk', 80, WHT, squeeze=.86),
    photo=ph(.33, .27, .5, 1.0), pb=(220, 60, 70), lg=WHT, lw=.8, order='LPTCF', credit=['SHAILENE WOODLEY', 'BEN MENDELSOHN'], ccol=WHT,
    ft='a', vbox=(220, 60, 70), fcol=(190, 196, 220), fin=SLIP)

# Dave Chappelle: The Dreamer: indigo stage dark, thin spaced capitals (typeset: hairline)
std('dave-chappelle-the-dreamer-2023', ('grad', [(0, (40, 34, 70)), (.6, (16, 14, 30)), (1, (4, 4, 8))]), WHT,
    [T('DAVE CHAPPELLE', 'her', 30, (200, 196, 220), track=.4), T('THE DREAMER', 'her', 70, WHT, track=.3, bold=.4)],
    photo=ph(.75, .6, .5, 1.0), pb=WHT, studio=['STAND-UP', 'SPECIAL'], scol=WHT, order='lPTF', tgap=10,
    ft='b', fcol=(190, 186, 210), fin=MINT)


# =====================================================================================
# the 2022 shelf (films-2022.json).  Same approach again.  The Disney and Pixar films on it
# (Turning Red, Lightyear, Pinocchio, Hocus Pocus 2) are clamshells, made with disney().
# =====================================================================================

# Don't Look Up: the poster's cream, the black condensed capitals (typeset: the UP is filled with the cast), the cast
std('don-t-look-up-2021', ('grad', [(0, (248, 244, 234)), (.6, (234, 228, 214)), (1, (170, 162, 150))]), (24, 22, 22),
    T("DON'T LOOK UP", 'hcnb', 100, (24, 22, 22), squeeze=.8, bold=.6),
    photo=ph(.5, .65, .9, .8), pb=(24, 22, 22), lg=(24, 22, 22), lw=.8, order='LPTCF', credit=['AN ADAM McKAY', 'FILM'], ccol=(24, 22, 22),
    ft='a', vbox=(24, 22, 22), fcol=(24, 22, 22), fin=MINT)

# The Batman: Gotham burning orange and black, the red stencil capitals (typeset: too small on the poster)
std('the-batman-2022', ('grad', [(0, (200, 100, 30)), (.5, (100, 40, 12)), (1, (12, 6, 4))]), (220, 30, 30),
    T('THE BATMAN', 'hcnb', 90, (226, 34, 32), squeeze=.8, bold=.6, rough=.4),
    photo=ph(.45, .2, .6, 1.0), pb=(226, 34, 32), studio=['WARNER BROS.'], scol=(20, 10, 6), order='lPTCF', credit=['A MATT REEVES', 'FILM'], ccol=(250, 230, 210),
    ft='a', vbox=(226, 34, 32), fcol=(240, 210, 190), fin=dict(SLIP, gloss=.09))

# Ambulance: siren red, AMBU-LA-NCE in black with the red L and A (typeset), the two brothers
std('ambulance-2022', ('grad', [(0, (210, 30, 30)), (.6, (130, 14, 16)), (1, (30, 4, 4))]), WHT,
    TT([('AMBU', WHT), ('LA', (20, 20, 22)), ('NCE', WHT)], 'intbk', 80, sp=-.05, track=.06),
    photo=ph(.5, .13, .7, .6), pb=WHT, lg=WHT, lw=.8, order='LPTCF', credit=['A MICHAEL BAY', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(130, 14, 16), fcol=(250, 220, 220), fin=SLIP)

# The Alpinist: Patagonian ice white and blue, thin spaced capitals (typeset), Marc-André on the face
std('the-alpinist-2021', ('grad', [(0, (210, 222, 232)), (.6, (150, 170, 190)), (1, (50, 66, 84))]), (24, 40, 60),
    [T('THE', 'her', 30, (24, 40, 60), track=.4), T('ALPINIST', 'her', 70, (24, 40, 60), track=.3, bold=.5)],
    photo=ph(.6, .25, .7, .8), pb=(24, 40, 60), lg=None, lw=.5, order='LPTCF', tgap=8, credit=['A DOCUMENTARY'], ccol=(24, 40, 60),
    ft='a', vbox=(24, 40, 60), fcol=(24, 40, 60), fin=MINT)

# Perfume: The Story of a Murderer (2006): black, the white Roman capitals, the petals
std('perfume-the-story-of-a-murderer-2006', ('grad', [(0, (40, 20, 24)), (.6, (14, 8, 10)), (1, (4, 2, 2))]), WHT,
    [L((0.09, 0.64, 0.91, 0.735), 76, WHT, mode='light', speck=.01), L((0.09, 0.735, 0.91, 0.765), 22, WHT, mode='light', speck=.002)],
    photo=ph(.5, .28, .6, 1.0), pb=(190, 30, 40), lg=WHT, lw=.8, order='LPTCF', tgap=10, credit=['A TOM TYKWER', 'FILM'], ccol=(220, 180, 180),
    ft='a', vbox=(190, 30, 40), fcol=(200, 190, 190), fin=WORN, seed=2006)

# Spider-Man: No Way Home: the mirror-dimension swirl, red and blue capitals with the script subtitle (typeset)
std('spider-man-no-way-home-2021', ('grad', [(0, (50, 60, 110)), (.5, (24, 26, 60)), (1, (120, 30, 30))]), (226, 40, 40),
    [T('SPIDER-MAN', 'intbk', 80, (226, 40, 40), squeeze=.86, outline=((30, 60, 160), 2.4), shadow=((10, 10, 30), 3, 3)), T('No Way Home', 'cho', 44, WHT)],
    photo=ph(.5, .22, .4, 1.0), pb=(226, 40, 40), lg=None, lw=.8, order='LPTF', tgap=10,
    ft='a', vbox=(226, 40, 40), fcol=(200, 206, 230), fin=SLIP)

# The Outfit: Savile Row lamp-light, amber and black, gold wide capitals like the poster's (typeset: the lift broke up on the haze)
std('the-outfit-2022', ('grad', [(0, (120, 70, 30)), (.5, (50, 26, 10)), (1, (10, 6, 2))]), (206, 176, 104),
    [T('THE', 'adv', 26, (210, 180, 110), track=.3), T('OUTFIT', 'advb', 84, (210, 180, 110), track=.18, grad=[(0, (236, 210, 140)), (.6, (196, 160, 90)), (1, (150, 116, 60))])],
    photo=ph(.42, .42, .5, 1.0), pb=(206, 176, 104), lg=WHT, lw=.8, order='LPTCF', tgap=6, credit=['MARK RYLANCE'], ccol=(206, 176, 104),
    ft='a', vbox=(206, 176, 104), vink=(50, 26, 10), fcol=(220, 196, 170), fin=MINT)

# Mikey and Nicky (1976): an old library copy, the illustration's wash-paper beige, the hand-drawn black title
std('mikey-and-nicky-1976', ('grad', [(0, (226, 214, 196)), (.6, (210, 194, 170)), (1, (150, 134, 110))]), (24, 22, 20),
    L((0.07, 0.825, 0.93, 0.92), 76, (24, 22, 20), mode='dark', speck=.01),
    photo=ph(.5, .35, 1.0, .6), pb=(24, 22, 20), lg=(24, 22, 20), lw=.4, order='LPTCSF', credit=['PETER FALK', 'JOHN CASSAVETES'], ccol=(24, 22, 20),
    stick=PRC(['$1.99', 'CLASSIC']), ft='e', fcol=(24, 22, 20), fin=OLD, seed=1976)

# All About My Mother (1999): the poster's flat Madrid blue and red, stacked black capitals with MOTHER in red (typeset)
std('all-about-my-mother-1999', ('solid', (70, 160, 226)), (16, 16, 18),
    TT([('ALL ABOUT MY', (16, 16, 18)), ('MOTHER', (210, 30, 34))], 'hcnb', 80, sp=.25, squeeze=.8, bold=.5),
    photo=ph(.65, .2, .6, 1.0), pb=(16, 16, 18), lg=None, lw=.6, order='LPTCSF', credit=['A FILM BY', 'ALMODÓVAR'], ccol=(16, 16, 18),
    stick=PRC(['2 NIGHTS', '$2.49']), ft='a', vbox=(210, 30, 34), fcol=(16, 16, 18), fin=RENTAL, seed=1999)

# Hustle: a Philly gym's wood and blue seats, the big brushed-white capitals
std('hustle-2022', ('grad', [(0, (60, 70, 110)), (.6, (30, 30, 46)), (1, (90, 60, 30))]), WHT,
    L((0.02, 0.15, 0.975, 0.272), 104, (236, 236, 236), mode='light', speck=.01),
    photo=ph(.5, .55, .6, 1.0), pb=(214, 40, 40), lg=None, lw=.4, order='LPTCF', credit=['ADAM SANDLER'], ccol=WHT,
    ft='a', vbox=(214, 40, 40), fcol=(210, 210, 220), fin=MINT)

# Doctor Strange in the Multiverse of Madness: shattered-mirror red-black, white Strange and the red MADNESS (typeset: small and over the glass)
std('doctor-strange-in-the-multiverse-of-madness-2022', ('grad', [(0, (60, 50, 60)), (.5, (24, 14, 18)), (1, (70, 10, 14))]), WHT,
    [T('DOCTOR STRANGE', 'ter', 64, WHT, bold=.5), T('IN THE MULTIVERSE OF MADNESS', 'hcnb', 40, (226, 36, 36), squeeze=.8)],
    photo=ph(.65, .35, .5, 1.0), pb=(226, 36, 36), lg=None, lw=.8, order='LPTF', tgap=10,
    ft='a', vbox=(226, 36, 36), fcol=(220, 206, 210), fin=SLIP)

# The Worst Person in the World: Oslo summer grey-green, the white serif in roman and italic (typeset: it sits on the trees)
std('the-worst-person-in-the-world-2021', ('grad', [(0, (150, 160, 150)), (.6, (80, 90, 80)), (1, (24, 28, 26))]), WHT,
    [T('THE WORST PERSON', 'teri', 56, WHT), T('IN THE WORLD', 'teri', 56, WHT)],
    photo=ph(.45, .5, .5, 1.0), pb=WHT, lg=None, lw=.3, order='LPTCF', tgap=8, credit=['A JOACHIM TRIER', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 90, 80), fcol=(226, 230, 226), fin=MINT, dotst=(['STAFF', 'PICK'], (220, 70, 60)))

# Volver (2006): Almodóvar's poster red with the flowers, black wood-type capitals (typeset: the lift broke on the print texture), Raimunda
std('volver-2006', ('solid', (220, 34, 34)), (16, 14, 14),
    T('VOLVER', 'bonb', 110, (16, 14, 14), track=.12, rough=.4),
    photo=ph(.5, .5, .6, 1.0), pb=(16, 14, 14), lg=None, lw=.6, order='LPTCF', credit=['PENÉLOPE CRUZ'], ccol=(16, 14, 14),
    ft='a', vbox=(16, 14, 14), fcol=(16, 14, 14), fin=WORN, seed=2006)

# The Heist of the Century: the tunnel's sewer green, the white condensed capitals (typeset: the lift lost the small THE and OF THE), the gang against the light
std('the-heist-of-the-century-2020', ('grad', [(0, (60, 90, 80)), (.6, (20, 34, 30)), (1, (4, 8, 6))]), WHT,
    TT([('THE', WHT), ('HEIST', WHT), ('OF THE', WHT), ('CENTURY', WHT)], 'hcnb', 84, sp=.3, squeeze=.7, bold=.6),
    photo=ph(.5, .33, .8, .8), pb=(240, 220, 150), lg=None, lw=.6, order='LPTCF', credit=['DIEGO PERETTI', 'GUILLERMO FRANCELLA'], ccol=(240, 220, 150),
    ft='a', vbox=(240, 220, 150), vink=(20, 34, 30), fcol=(200, 210, 206), fin=SLIP)

# Everything Everywhere All at Once: the poster's crowded colours behind navy stacked capitals (typeset: they sit on the pattern)
std('everything-everywhere-all-at-once-2022', ('grad', [(0, (236, 170, 60)), (.4, (220, 90, 70)), (.75, (60, 140, 160)), (1, (20, 40, 80))]), (20, 36, 100),
    T('EVERYTHING EVERYWHERE ALL AT ONCE', 'hcnb', 70, (20, 36, 100), squeeze=.8, bold=.5, outline=((250, 240, 220), 1.8)),
    photo=ph(.5, .8, .4, 1.0), pb=(20, 36, 100), lg=None, lw=.6, order='LPTCF', credit=['MICHELLE YEOH'], ccol=(20, 36, 100),
    ft='a', vbox=(20, 36, 100), fcol=(20, 36, 100), fin=MINT, dotst=(['STAFF', 'PICK'], (20, 36, 100)))

# We Were Once Kids: Washington Square 1995, sun-washed brick, the white heavy capitals (typeset: they sit on the crowd)
std('we-were-once-kids-2021', ('grad', [(0, (170, 130, 100)), (.6, (90, 66, 50)), (1, (26, 18, 14))]), WHT,
    [T('WE WERE ONCE', 'intbk', 36, WHT), T('KIDS', 'intbk', 100, WHT)],
    photo=ph(.5, .25, 1.0, .6), pb=WHT, lg=None, lw=.7, order='LPTCF', tgap=8, credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(90, 66, 50), fcol=(236, 220, 206), fin=SLIP)

# Turning Red: a Disney clamshell.  Panda red, the poster's white TURNING RED cut off it, Mei's panda face in the diamond
disney('turning-red-2022', ('grad', [(0, (236, 80, 50)), (.5, (200, 50, 36)), (1, (120, 24, 20))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.62, 0.78, 0.9, 0.925)], 150, cuts=[key_cut(lambda a: _lum(a) > .8)]),
       face=ph(.52, .27, .45, 1.4), lcol=WHT)

# Lightyear: a Disney clamshell.  Deep-space blue, the poster's silver-and-blue logo cut off it, Buzz in the diamond
disney('lightyear-2022', ('grad', [(0, (40, 60, 150)), (.5, (20, 26, 80)), (1, (6, 8, 30))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.05, 0.875, 0.95, 0.95)], 120, cuts=[key_cut(lambda a: _lum(a) > .5)]),
       face=ph(.485, .235, .18, 1.4), lcol=WHT)

# Val: the torn-strip portrait, grey and skin, the yellow brush VAL
std('val-2021', ('grad', [(0, (176, 176, 172)), (.6, (100, 96, 90)), (1, (30, 28, 26))]), (246, 226, 30),
    L((0.26, 0.12, 0.74, 0.34), 120, (248, 228, 34), mode='key', key=(240, 220, 30), t=(70, 150), speck=.01),
    photo=ph(.5, .47, .7, .85), pb=(248, 228, 34), lg=WHT, lw=.5, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(248, 228, 34),
    ft='a', vbox=(248, 228, 34), vink=(30, 28, 26), fcol=(230, 226, 220), fin=MINT)

# Open Your Eyes (1997): a real rental, Madrid sky white, black geometric capitals (typeset: stacked three high), Sofía
std('open-your-eyes-1997', ('grad', [(0, (236, 238, 240)), (.6, (214, 214, 216)), (1, (150, 150, 156))]), (16, 16, 18),
    T('OPEN YOUR EYES', 'advb', 80, (16, 16, 18), track=.06),
    photo=ph(.55, .2, .5, 1.0), pb=(16, 16, 18), lg=(16, 16, 18), lw=.3, order='LPTCSF', credit=['AN ALEJANDRO', 'AMENÁBAR FILM'], ccol=(16, 16, 18),
    stick=BAR('15 01997', top='THRILLER'), ft='a', vbox=(16, 16, 18), fcol=(16, 16, 18), fin=RENTAL, seed=1997)

# Thor: Love and Thunder: the poster's 80s rainbow sky, a chrome THOR and the pink script (typeset: busy behind)
std('thor-love-and-thunder-2022', ('grad', [(0, (60, 60, 160)), (.5, (200, 70, 150)), (1, (240, 150, 60))]), WHT,
    [T('THOR', 'intbk', 100, WHT, grad=[(0, (250, 250, 255)), (.5, (150, 170, 220)), (1, (230, 236, 250))], outline=((30, 20, 60), 2.4)),
     T('LOVE AND THUNDER', 'herbi', 38, (255, 120, 200), outline=((30, 20, 60), 1.6))],
    photo=ph(.38, .22, .35, 1.0), pb=WHT, lg=None, lw=.8, order='LPTF', tgap=10,
    ft='a', vbox=WHT, vink=(60, 60, 160), fcol=(250, 230, 240), fin=SLIP)

# Perfect Blue (1998): a real rental, Mima's night-blue, the white spaced serif capitals
std('perfect-blue-1998', ('grad', [(0, (60, 70, 130)), (.6, (24, 28, 60)), (1, (6, 8, 18))]), WHT,
    L((0.07, 0.815, 0.93, 0.885), 64, WHT, mode='light', speck=.01),
    photo=ph(.4, .25, .6, 1.0), pb=(200, 210, 240), lg=WHT, lw=.7, order='LPTCSF', credit=['A SATOSHI KON', 'FILM'], ccol=(200, 210, 240),
    stick=flow(dot, 70, ['ANIME'], (220, 40, 60), d=60), ft='a', vbox=(200, 210, 240), vink=(24, 28, 60), fcol=(180, 190, 220), fin=RENTAL, seed=1998)

# Kiki's Delivery Service (1989): Koriko's sea-blue sky, a white script like the poster's (typeset: the lift broke on the sky), Kiki on her broom (a Ghibli film, so a slipcase)
std('kiki-s-delivery-service-1989', ('grad', [(0, (60, 150, 220)), (.6, (30, 100, 180)), (1, (14, 46, 90))]), WHT,
    [T("KIKI'S", 'cho', 96, WHT), T('Delivery Service', 'cho', 50, WHT)], tgap=6,
    photo=ph(.6, .6, .6, 1.0), pb=WHT, lg=None, lw=.6, order='LPTCSF', credit=['A HAYAO MIYAZAKI', 'FILM'], ccol=WHT,
    stick=PRC(['$2.99', 'FAMILY']), ft='a', vbox=WHT, vink=(30, 100, 180), fcol=(220, 230, 244), fin=WORN, seed=1989)

# Vengeance: West Texas dust, a red diner script like the poster's (typeset: the lift broke up), Ben in his headphones
std('vengeance-2022', ('grad', [(0, (236, 222, 196)), (.6, (210, 190, 156)), (1, (150, 120, 90))]), (196, 30, 40),
    T('Vengeance', 'cho', 120, (204, 34, 44), outline=(WHT, 2.2), shadow=((90, 20, 20), 3, 3)),
    photo=ph(.3, .2, .6, 1.0), pb=(200, 32, 44), lg=(30, 30, 34), lw=.7, order='LPTCF', credit=['A B.J. NOVAK', 'FILM'], ccol=(30, 30, 34),
    ft='a', vbox=(200, 32, 44), fcol=(30, 30, 34), fin=SLIP)

# Emily the Criminal: LA dusk teal, white stencilled capitals (typeset: stacked on her shoulder), Emily at the head
std('emily-the-criminal-2022', ('grad', [(0, (40, 110, 120)), (.6, (16, 46, 52)), (1, (4, 12, 14))]), WHT,
    [T('EMILY THE', 'hcnb', 44, WHT, track=.08), T('CRIMINAL', 'hcnb', 92, WHT, track=.06, bold=.4)],
    photo=ph(.6, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.4, order='LPTCF', tgap=8, credit=['AUBREY PLAZA'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 46, 52), fcol=(196, 214, 216), fin=SLIP)

# Legend of the Guardians (2010): Ga'Hoole sunset bronze, silver serif capitals (typeset: small on the poster), Soren the barn owl
std('legend-of-the-guardians-the-owls-of-ga-hoole-2010', ('grad', [(0, (160, 120, 60)), (.6, (70, 50, 26)), (1, (16, 12, 6))]), (220, 216, 206),
    [T('LEGEND OF THE GUARDIANS', 'ter', 54, (226, 222, 212), track=.06, bold=.4), T("THE OWLS OF GA'HOOLE", 'ter', 26, (226, 222, 212), track=.3)],
    photo=ph(.45, .6, .6, 1.0), pb=(226, 222, 212), lg=None, lw=.4, order='LPTCSF', tgap=8, credit=['A ZACK SNYDER', 'FILM'], ccol=(226, 222, 212),
    stick=PRC(['$2.99', 'FAMILY']), ft='a', vbox=(226, 222, 212), vink=(70, 50, 26), fcol=(220, 206, 186), fin=WORN, seed=2010)

# The Skin I Live In (2011): the mask's flesh pink, hollow red capitals (typeset with a red outline), the eye in the mask
std('the-skin-i-live-in-2011', ('grad', [(0, (206, 160, 150)), (.6, (150, 100, 94)), (1, (60, 36, 34))]), (200, 30, 40),
    T('THE SKIN I LIVE IN', 'hcnb', 76, (250, 236, 230), track=.1, outline=((200, 30, 40), 2.4)),
    photo=ph(.6, .33, .6, 1.0), pb=(200, 30, 40), lg=None, lw=.6, order='LPTCF', credit=['A FILM BY', 'ALMODÓVAR'], ccol=(250, 236, 230),
    ft='a', vbox=(200, 30, 40), fcol=(250, 236, 230), fin=WORN, seed=2011)

# Boiling Point: the kitchen's steel and flame, fat white capitals
std('boiling-point-2021', ('grad', [(0, (60, 56, 54)), (.6, (26, 24, 22)), (1, (60, 20, 8))]), WHT,
    L((0.05, 0.06, 0.95, 0.325), 130, WHT, mode='light', speck=.01),
    photo=ph(.5, .62, .5, 1.0), pb=(240, 140, 40), lg=None, lw=.4, order='LPTCF', credit=['STEPHEN GRAHAM'], ccol=(240, 140, 40),
    ft='a', vbox=(240, 140, 40), vink=(26, 24, 22), fcol=(214, 206, 200), fin=MINT, dotst=(['STAFF', 'PICK'], (240, 140, 40), (26, 24, 22)))

# Funny Pages: the comic's red, the yellow hand-lettered title, Robert in the ink pot
std('funny-pages-2022', ('solid', (206, 30, 36)), (246, 214, 60),
    L((0.03, 0.03, 0.39, 0.2), 120, (248, 216, 64), mode='key', key=(240, 206, 60), t=(70, 150), speck=.01),
    photo=ph(.5, .72, .5, 1.0), pb=(20, 18, 18), lg=WHT, lw=.5, order='LPTCF', credit=['AN OWEN KLINE', 'FILM'], ccol=(20, 18, 18),
    ft='a', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=SLIP)

# Pinocchio (2022): a Disney clamshell.  Geppetto's workshop amber, the poster's gold storybook logo cut off it, Pinocchio in the diamond
disney('pinocchio-2022', ('grad', [(0, (120, 80, 40)), (.5, (70, 44, 22)), (1, (30, 18, 10))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.1, 0.07, 0.9, 0.2)], 120, cuts=[key_cut(lambda a: _lum(a) > .45)]),
       face=ph(.8, .44, .2, 1.4), lcol=WHT)

# Bully (2001): Florida-swamp brown-black, the cream heavy capitals
std('bully-2001', ('grad', [(0, (70, 44, 20)), (.6, (34, 20, 8)), (1, (8, 4, 2))]), (240, 226, 190),
    L((0.34, 0.45, 0.98, 0.55), 96, (242, 228, 194), mode='light', speck=.01),
    photo=ph(.25, .3, .5, 1.0), pb=(242, 228, 194), lg=WHT, lw=.7, order='LPTCF', credit=['A LARRY CLARK', 'FILM'], ccol=(242, 228, 194),
    ft='a', vbox=(242, 228, 194), vink=(34, 20, 8), fcol=(210, 196, 176), fin=WORN, seed=2001)

# Nine Queens (2000): the forged stamp sheet's sage green on charcoal, pale heavy capitals
std('nine-queens-2000', ('grad', [(0, (60, 62, 58)), (.6, (30, 30, 28)), (1, (8, 8, 8))]), (214, 222, 196),
    L((0.06, 0.815, 0.94, 0.895), 70, (216, 224, 198), mode='light', speck=.01),
    photo=ph(.5, .4, .7, .8), pb=(216, 224, 198), lg=WHT, lw=.6, order='LPTCSF', credit=['RICARDO DARÍN'], ccol=(216, 224, 198),
    stick=BAR('15 02000', top='THRILLER', fill=(242, 240, 232), ink=(30, 30, 30)), ft='a', vbox=(216, 224, 198), vink=(30, 30, 28), fcol=(190, 196, 180), fin=RENTAL, seed=2000)

# The Voyeurs: Montreal window-light blue, the blush art-deco capitals
std('the-voyeurs-2021', ('grad', [(0, (50, 60, 130)), (.6, (20, 24, 60)), (1, (6, 6, 18))]), (250, 220, 214),
    L((0.14, 0.625, 0.86, 0.92), 150, (252, 224, 218), mode='light', speck=.01),
    photo=ph(.65, .22, .5, 1.0), pb=(252, 224, 218), lg=WHT, lw=.5, order='LPTCF', credit=['SYDNEY SWEENEY'], ccol=(252, 224, 218),
    ft='a', vbox=(252, 224, 218), vink=(20, 24, 60), fcol=(196, 200, 226), fin=MINT)

# A Perfect Murder (1998): a real rental, lamplit Manhattan red-black, white serif and the red MURDER (typeset: stepped across the poster)
std('a-perfect-murder-1998', ('grad', [(0, (90, 30, 14)), (.6, (36, 12, 6)), (1, (6, 2, 2))]), WHT,
    TT([('A PERFECT', WHT), ('MURDER', (220, 40, 30))], 'ter', 80, sp=.3, squeeze=.86, bold=.4),
    photo=ph(.35, .3, .5, 1.0), pb=(220, 40, 30), lg=None, lw=.4, order='LPTCSF', credit=['MICHAEL DOUGLAS', 'GWYNETH PALTROW'], ccol=WHT,
    stick=RWD(), ft='a', vbox=(220, 40, 30), fcol=(220, 200, 190), fin=RENTAL, seed=1998)

# To Die For (1995): a real rental, TV-news blue, hot-pink thin capitals like the poster's (typeset: the lift broke up), Suzanne in the spotlight
std('to-die-for-1995', ('grad', [(0, (40, 90, 140)), (.6, (16, 40, 66)), (1, (4, 10, 18))]), (236, 40, 160),
    T('TO DIE FOR', 'adv', 76, (240, 50, 170), track=.04, bold=.5),
    photo=ph(.5, .2, .6, 1.0), pb=(240, 50, 170), lg=WHT, lw=.6, order='LPTCF', credit=['NICOLE KIDMAN'], ccol=WHT,
    ft='a', vbox=(240, 50, 170), fcol=(190, 210, 230), fin=RENTAL, seed=1995)

# Bodies Bodies Bodies: hurricane-party black, glow-stick cyan, violet and green capitals (typeset)
std('bodies-bodies-bodies-2022', ('grad', [(0, (30, 30, 50)), (.6, (12, 12, 20)), (1, (4, 4, 6))]), (60, 220, 240),
    TT([('BODIES', (60, 220, 240)), ('BODIES', (190, 80, 240)), ('BODIES', (110, 240, 60))], 'intbk', 70, sp=.2, soft=((120, 120, 240), 6, .5)),
    photo=ph(.5, .35, .8, .8), pb=(110, 240, 60), lg=WHT, lw=.5, order='LPTCF', credit=['A HALINA REIJN', 'FILM'], ccol=(60, 220, 240),
    ft='a', vbox=(190, 80, 240), fcol=(190, 190, 210), fin=MINT)

# Watcher: Bucharest night, wide-spaced white capitals like the poster's (typeset: her face shows through them), Julia at the window
std('watcher-2022', ('grad', [(0, (40, 46, 50)), (.6, (16, 18, 20)), (1, (60, 10, 14))]), WHT,
    T('WATCHER', 'adv', 66, WHT, track=.4, bold=.4),
    photo=ph(.5, .27, .5, 1.0), pb=(200, 30, 36), lg=None, lw=.6, order='LPTCF', credit=['MAIKA MONROE'], ccol=WHT,
    ft='a', vbox=(200, 30, 36), fcol=(190, 190, 194), fin=MINT)

# Presumed Innocent (1990): a real rental, courthouse white, spaced black serif capitals (typeset: small on the poster), Rusty at the head
std('presumed-innocent-1990', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 216)), (1, (160, 156, 150))]), (20, 20, 22),
    [T('PRESUMED', 'ter', 50, (20, 20, 22), track=.3), T('INNOCENT', 'ter', 72, (20, 20, 22), track=.06, bold=.4)],
    photo=ph(.25, .45, .5, 1.0), pb=(20, 20, 22), lg=(20, 20, 22), lw=.6, order='LPTCSF', tgap=8, credit=['HARRISON FORD'], ccol=(20, 20, 22),
    stick=BAR('15 01990', top='THRILLER', fill=(238, 214, 120), ink=(40, 30, 10)), ft='a', vbox=(20, 20, 22), fcol=(20, 20, 22), fin=RENTAL, seed=1990)

# Dressed to Kill (1980): a worn old rental, black, the white wedge-serif capitals, the shower-room door
std('dressed-to-kill-1980', ('grad', [(0, (40, 30, 30)), (.6, (14, 10, 10)), (1, (4, 2, 2))]), WHT,
    L((0.05, 0.04, 0.95, 0.26), 120, WHT, mode='light', speck=.01),
    photo=ph(.5, .62, .8, .9), pb=(200, 30, 34), lg=WHT, lw=.5, order='LPTCSF', credit=['A BRIAN DE PALMA', 'FILM'], ccol=WHT,
    stick=PRC(['$1.99', 'THRILLER']), ft='e', fcol=(200, 190, 190), fin=OLD, seed=1980)

# Luckiest Girl Alive: watercolour grey, pale serif lower-case (typeset: it melts into the face), the eye
std('luckiest-girl-alive-2022', ('grad', [(0, (200, 200, 198)), (.6, (130, 130, 130)), (1, (40, 40, 42))]), WHT,
    T('Luckiest Girl Alive', 'terb', 84, WHT, shadow=((40, 40, 42), 2, 2)),
    photo=ph(.5, .28, .5, 1.0), pb=WHT, lg=WHT, lw=.8, order='LPTCF', credit=['MILA KUNIS'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 40, 42), fcol=(236, 236, 236), fin=MINT)

# Bullet Train: Tokyo neon, red italic capitals keylined in white (typeset: they glow on the poster), Ladybug at the head
std('bullet-train-2022', ('grad', [(0, (40, 30, 90)), (.5, (150, 30, 90)), (1, (20, 10, 30))]), (236, 40, 50),
    [T('BULLET', 'intbki', 76, (238, 44, 54), outline=(WHT, 2), soft=((240, 60, 120), 8, .6)), T('TRAIN', 'intbki', 76, WHT, outline=((238, 44, 54), 2))],
    photo=ph(.45, .45, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', tgap=8, credit=['BRAD PITT'], ccol=WHT,
    ft='a', vbox=(238, 44, 54), fcol=(230, 210, 230), fin=SLIP)

# Clerks III: Quick Stop yellow, the ransom-note black capitals (typeset), Dante and Randal at the counter
std('clerks-iii-2022', ('solid', (240, 210, 30)), (20, 20, 22),
    T('CLERKS III', 'intbk', 96, (20, 20, 22)),
    photo=ph(.55, .55, .9, .8), pb=(20, 20, 22), lg=None, lw=.3, order='LPTCSF', credit=['A KEVIN SMITH', 'FILM'], ccol=(20, 20, 22),
    stick=RWD(), ft='a', vbox=(20, 20, 22), vink=(240, 210, 30), fcol=(20, 20, 22), fin=WORN)

# The Piano Teacher (2001): Vienna conservatory white, the black serif, the embrace on the tiled floor
std('the-piano-teacher-2001', ('grad', [(0, (244, 242, 238)), (.6, (226, 222, 216)), (1, (160, 156, 150))]), (20, 20, 22),
    L((0.22, 0.095, 0.78, 0.225), 104, (20, 20, 22), mode='dark', speck=.001),
    photo=ph(.4, .55, .7, .8), pb=(20, 20, 22), lg=None, lw=.4, order='LPTCF', credit=['A MICHAEL HANEKE', 'FILM'], ccol=(20, 20, 22),
    ft='a', vbox=(20, 20, 22), fcol=(20, 20, 22), fin=WORN, seed=2001)

# Top Gun: Maverick: Miramar sunset gold, the black winged logo, Maverick at the head
std('top-gun-maverick-2022', ('grad', [(0, (236, 196, 120)), (.6, (200, 150, 80)), (1, (90, 60, 30))]), (20, 20, 22),
    L((0.22, 0.785, 0.78, 0.895), 84, (20, 20, 22), mode='dark', speck=.001),
    photo=ph(.55, .25, .5, 1.0), pb=(20, 20, 22), lg=(20, 20, 22), lw=.8, order='LPTCF', credit=['TOM CRUISE'], ccol=(20, 20, 22),
    ft='a', vbox=(20, 20, 22), vink=(236, 196, 120), fcol=(20, 20, 22), fin=SLIP)

# Hocus Pocus 2: a Disney clamshell.  Salem-night violet, the poster's gold logo (with its Disney mark, so no separate studio line) cut off it, Winifred in the diamond
disney('hocus-pocus-2-2022', ('grad', [(0, (90, 50, 140)), (.5, (50, 26, 90)), (1, (20, 10, 40))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.08, 0.6, 0.97, 0.88)], 150, cuts=[key_cut(lambda a: (a[..., 0] > a[..., 2] + .2) & (_lum(a) > .4))]),
       face=ph(.5, .235, .2, 1.4), lcol=WHT, studio=False)

# Poker Face: the card table's black and white, the white condensed capitals, the cards falling past the face
std('poker-face-2022', ('grad', [(0, (40, 40, 40)), (.6, (16, 16, 16)), (1, (120, 20, 24))]), WHT,
    L((0.61, 0.75, 0.91, 0.895), 110, WHT, mode='light', speck=.01),
    photo=ph(.65, .25, .5, 1.0), pb=(200, 30, 36), lg=WHT, lw=.8, order='LPTCF', credit=['RUSSELL CROWE'], ccol=WHT,
    ft='a', vbox=(200, 30, 36), fcol=(200, 200, 200), fin=SLIP)

# A Christmas Story Christmas: Cleveland snow cream inside the green frame, red and green tumbling script (typeset), Ralphie with his bags
std('a-christmas-story-christmas-2022', ('grad', [(0, (246, 240, 226)), (.6, (232, 224, 204)), (1, (40, 110, 60))]), (196, 30, 36),
    [T('A CHRISTMAS STORY', 'bonbi', 50, (196, 30, 36), outline=(WHT, 1.4)), T('CHRISTMAS', 'bonbi', 64, (40, 120, 60), outline=(WHT, 1.4))],
    photo=ph(.68, .45, .35, 1.0), pb=(40, 120, 60), lg=(30, 30, 34), lw=.5, order='LPTCF', tgap=8, credit=['PETER BILLINGSLEY'], ccol=(30, 30, 34),
    ft='a', vbox=(196, 30, 36), fcol=(30, 30, 34), fin=SLIP, under=[frame((40, 120, 60), 8, 1.6)])

# Bandit: newsprint white and the red stripe, the poster's heavy red capitals
std('bandit-2022', ('grad', [(0, (240, 238, 234)), (.6, (220, 216, 210)), (1, (160, 150, 146))]), (226, 30, 40),
    L((0.12, 0.76, 0.89, 0.895), 104, (228, 32, 42), mode='key', key=(226, 30, 40), t=(70, 150), speck=.01),
    photo=ph(.7, .15, .5, 1.0), pb=(228, 32, 42), lg=(30, 30, 34), lw=.4, order='LPTCF', credit=['JOSH DUHAMEL', 'MEL GIBSON'], ccol=(30, 30, 34),
    ft='a', vbox=(228, 32, 42), fcol=(30, 30, 34), fin=SLIP)

# Glass Onion: Greek-island blue, the poster's golden blackletter, the guests at the pool
std('glass-onion-a-knives-out-mystery-2022', ('grad', [(0, (40, 110, 200)), (.6, (20, 60, 120)), (1, (6, 20, 44))]), (246, 206, 40),
    L((0.09, 0.115, 0.91, 0.28), 120, (248, 210, 44), mode='key', key=(240, 204, 40), t=(70, 150), speck=.01),
    photo=ph(.5, .62, 1.0, .6), pb=(248, 210, 44), lg=WHT, lw=.6, order='LPTCF', credit=['A KNIVES OUT', 'MYSTERY'], ccol=(248, 210, 44),
    ft='a', vbox=(248, 210, 44), vink=(20, 60, 120), fcol=(200, 214, 236), fin=MINT)


# =====================================================================================
# the 2021 shelf (films-2021.json).  Same approach as 2022-2025: lettering boxes given here,
# checked over the posters first; typeset where the lift wouldn't come clean (comments say so).
# Credits and typed labels checked on IMDb (17 Nov 2026).  Soul (Pixar) and Cruella (Disney) are clamshells.
# =====================================================================================

# The Kid Detective: the poster's crime-scene yellow, the red condensed capitals, Abe at the head
std('the-kid-detective-2020', ('grad', [(0, (250, 200, 40)), (.55, (240, 160, 30)), (1, (150, 70, 20))]), (190, 24, 24),
    TT([('THE', (196, 26, 26)), ('KID DETECTIVE', (196, 26, 26))], 'hcnb', 92, sp=.25, squeeze=.74, bold=1.6, rough=.3),  # typeset: the lift kept losing the E's bars
    photo=ph(.62, .2, .55, 1.0), pb=(196, 26, 26), lg=(30, 26, 22), lw=.6, order='LPTCF', credit=['ADAM BRODY'], ccol=(30, 26, 22),
    ft='a', vbox=(196, 26, 26), fcol=(30, 26, 22), fin=SLIP)

# The Little Things: night-time teal, the white lower-case serif, Rami Malek in the middle frame
std('the-little-things-2021', ('grad', [(0, (30, 70, 80)), (.6, (10, 26, 32)), (1, (60, 10, 14))]), WHT,
    L((0.05, 0.885, 0.97, 0.965), 66, WHT, mode='light', speck=.005),
    photo=ph(.55, .45, .6, 1.0), pb=(214, 40, 40), lg=WHT, lw=.7, order='LPTCF', credit=['DENZEL WASHINGTON', 'RAMI MALEK'], ccol=(214, 220, 222),
    ft='a', vbox=(214, 40, 40), fcol=(190, 200, 204), fin=MINT)

# Black Bear: the kaleidoscope's teal and red, the white spaced capitals, Aubrey Plaza at the centre
std('black-bear-2020', ('grad', [(0, (40, 80, 84)), (.6, (16, 30, 32)), (1, (110, 20, 24))]), WHT,
    L((0.12, 0.81, 0.89, 0.915), 84, WHT, mode='light', speck=.01),
    photo=ph(.5, .55, .45, 1.0), pb=(200, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['AUBREY PLAZA'], ccol=WHT,
    ft='a', vbox=(200, 40, 40), fcol=(200, 210, 210), fin=MINT)

# Never Rarely Sometimes Always: the poster's putty panel, the grey condensed capitals, Autumn's face
std('never-rarely-sometimes-always-2020', ('solid', (232, 228, 214)), (90, 86, 80),
    [T('NEVER RARELY', 'hcn', 64, (92, 88, 82), squeeze=.72), T('SOMETIMES ALWAYS', 'hcn', 64, (92, 88, 82), squeeze=.72)], tgap=10,  # typeset: the thin condensed letters broke up
    photo=ph(.62, .55, .55, 1.0), pb=(92, 88, 82), lg=(92, 88, 82), lw=.7, order='LPTCF', credit=['AN ELIZA HITTMAN', 'FILM'], ccol=(92, 88, 82),
    ft='a', vbox=(92, 88, 82), fcol=(92, 88, 82), fin=MINT)

# Promising Young Woman: white with the hot-pink condensed capitals, Cassie at the head
std('promising-young-woman-2020', ('grad', [(0, (250, 250, 248)), (.6, (240, 238, 236)), (1, (214, 206, 208))]), (222, 40, 96),
    L([(0.11, 0.47, 0.89, 0.58), (0.11, 0.575, 0.89, 0.66)], 84, (224, 42, 98), mode='key', key=(220, 40, 90), t=(70, 150), speck=.01),
    photo=ph(.5, .19, .24, 1.0), pb=(224, 42, 98), lg=(30, 30, 34), lw=.7, order='LPTCF', credit=['CAREY MULLIGAN'], ccol=(30, 30, 34),
    ft='a', vbox=(224, 42, 98), fcol=(30, 30, 34), fin=MINT)

# Nomadland: the Badlands at dusk, the orange heavy capitals off the sky, Fern in her camp chair (no logo file: the label in type)
std('nomadland-2021', ('grad', [(0, (226, 186, 150)), (.4, (180, 150, 120)), (.75, (110, 100, 70)), (1, (50, 44, 30))]), (236, 110, 30),
    L((0.05, 0.075, 0.95, 0.16), 96, (236, 112, 32), mode='key', key=(240, 120, 30), t=(70, 150), speck=.01, grow=.04),
    photo=ph(.55, .55, .5, 1.0), pb=(236, 112, 32), studio=['SEARCHLIGHT', 'PICTURES'], scol=(40, 34, 26), order='lPTCF', credit=['FRANCES', 'McDORMAND'], ccol=(40, 34, 26),
    ft='a', vbox=(236, 112, 32), fcol=(40, 34, 26), fin=MINT)

# Judas and the Black Messiah: protest-poster red, the white condensed capitals, Kaluuya at the head
std('judas-and-the-black-messiah-2021', ('grad', [(0, (200, 36, 30)), (.6, (120, 16, 14)), (1, (30, 6, 6))]), WHT,
    TT([('JUDAS', WHT), ('AND THE', WHT), ('BLACK MESSIAH', WHT)], 'hcnb', 84, sp=.25, squeeze=.82, bold=.6),  # typeset: the lift broke on the photo behind
    photo=ph(.62, .22, .55, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['DANIEL KALUUYA', 'LAKEITH STANFIELD'], ccol=WHT,
    ft='a', vbox=WHT, vink=(120, 16, 14), fcol=(240, 210, 206), fin=MINT)

# Shiva Baby: midnight violet, the pink neon script (typeset: the glow wouldn't lift), Danielle with her bagel
std('shiva-baby-2021', ('grad', [(0, (60, 40, 90)), (.6, (26, 18, 44)), (1, (10, 6, 16))]), (250, 150, 220),
    T('Shiva Baby', 'cho', 120, (252, 170, 230), soft=((240, 80, 200), 7, .7)),
    photo=ph(.46, .34, .34, 1.0), pb=(252, 170, 230), lg=WHT, lw=.6, order='LPTCF', credit=['RACHEL SENNOTT'], ccol=(252, 170, 230),
    ft='a', vbox=(252, 170, 230), vink=(26, 18, 44), fcol=(210, 200, 226), fin=MINT)

# Sound of Metal: black, the fat white capitals, Ruben behind the kit
std('sound-of-metal-2020', ('grad', [(0, (60, 30, 28)), (.6, (22, 12, 12)), (1, (6, 4, 4))]), WHT,
    L([(0.18, 0.09, 0.8, 0.17), (0.06, 0.175, 0.95, 0.265)], 88, WHT, mode='light', speck=.01),
    photo=ph(.53, .45, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['RIZ AHMED'], ccol=WHT,
    ft='a', vbox=WHT, vink=(22, 12, 12), fcol=(210, 200, 198), fin=MINT, dotst=(['STAFF', 'PICK'], (200, 40, 40)))

# Another Round: Copenhagen sky blue, the white ANOTHER over the heavy ROUND, Martin and the bottle
std('another-round-2020', ('grad', [(0, (90, 150, 196)), (.6, (40, 80, 120)), (1, (14, 24, 36))]), WHT,
    [T('ANOTHER', 'adv', 40, WHT, track=.08), L((0.14, 0.135, 0.86, 0.24), 96, WHT, mode='light', speck=.01)], tgap=8,
    photo=ph(.4, .5, .5, 1.0), pb=WHT, lg=WHT, lw=.7, order='LPTCF', credit=['MADS MIKKELSEN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 80, 120), fcol=(210, 222, 234), fin=MINT)

# Mank: black and white, the white brush script (typeset: it runs over the crowd), Mank in the middle (no logo file: the label in type)
std('mank-2020', ('grad', [(0, (120, 120, 120)), (.5, (50, 50, 50)), (1, (10, 10, 10))]), WHT,
    T('Mank', 'cho', 150, WHT, shadow=((0, 0, 0), 3, 3)),
    photo=ph(.48, .2, .5, 1.0), pb=WHT, studio=['NETFLIX'], scol=WHT, order='lPTCF', credit=['A DAVID FINCHER', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(50, 50, 50), fcol=(200, 200, 200), fin=MINT)

# I Care a Lot: the poster's flat teal, the cream italic capitals (typeset: they overlap her hair), Marla in her shades
std('i-care-a-lot-2021', ('solid', (98, 146, 146)), (250, 222, 196),
    T('I CARE A LOT.', 'intbki', 92, (250, 222, 196), squeeze=.86),
    photo=ph(.7, .5, .3, 1.0), pb=(226, 52, 44), lg=WHT, lw=.6, order='LPTCF', credit=['ROSAMUND PIKE'], ccol=(250, 222, 196),
    ft='a', vbox=(226, 52, 44), fcol=(250, 222, 196), fin=MINT)

# The Father: the flat's lamplight brown, the white spaced capitals, Anthony at the head
std('the-father-2020', ('grad', [(0, (120, 84, 50)), (.6, (50, 34, 20)), (1, (14, 10, 6))]), WHT,
    [L((0.44, 0.045, 0.56, 0.075), 22, WHT, mode='light', speck=.002), L((0.06, 0.08, 0.94, 0.155), 70, WHT, mode='light', speck=.005)], tgap=8,
    photo=ph(.77, .42, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['ANTHONY HOPKINS', 'OLIVIA COLMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(50, 34, 20), fcol=(220, 206, 190), fin=MINT)

# Nobody: black with the bloody knuckles, the grungy white stencil (typeset: the lift came off as scratches), Hutch at the head
std('nobody-2021', ('grad', [(0, (50, 46, 44)), (.6, (18, 16, 16)), (1, (60, 10, 10))]), WHT,
    T('NOBODY', 'intbki', 120, (240, 238, 234), squeeze=.8, rough=.8),
    photo=ph(.45, .26, .5, 1.0), pb=(190, 30, 30), lg=WHT, lw=.7, order='LPTCF', credit=['BOB ODENKIRK'], ccol=WHT,
    ft='a', vbox=(190, 30, 30), fcol=(200, 196, 194), fin=SLIP)

# Minari: Arkansas sky and grass, the olive serif capitals, the family in the field
std('minari-2020', ('grad', [(0, (200, 226, 222)), (.45, (230, 220, 180)), (.75, (150, 170, 80)), (1, (60, 80, 30))]), (110, 96, 40),
    L((0.1, 0.14, 0.9, 0.28), 96, (112, 98, 40), mode='dark', speck=.01),
    photo=ph(.5, .66, .9, .6), pb=(112, 98, 40), lg=(60, 56, 30), lw=.6, order='LPTCF', credit=['A LEE ISAAC CHUNG', 'FILM'], ccol=(60, 56, 30),
    ft='a', vbox=(112, 98, 40), fcol=(40, 40, 20), fin=MINT)

# Three Daughters (1961): an old art-house tape, the poster's magenta, its white hand-drawn title, one of the three faces (no logo file: Ray's company in type)
std('three-daughters-1961', ('solid', (196, 30, 150)), WHT,
    L([(0.04, 0.59, 0.62, 0.72), (0.03, 0.72, 0.97, 0.86)], 76, (248, 244, 246), mode='light', speck=.01, gapf=.35),
    photo=ph(.78, .46, .34, 1.0), pb=WHT, studio=['SATYAJIT RAY', 'PRODUCTIONS'], scol=WHT, order='lPTCSF', credit=['A SATYAJIT RAY', 'FILM'], ccol=WHT,
    stick=PRC(['$3.99', 'CLASSIC']), ft='e', fcol=WHT, fin=OLD, seed=1961)

# Soul: a Pixar clamshell.  Night-city blue, the poster's blue SOUL cut off it, Joe in his hat on the stair
disney('soul-2020', ('grad', [(0, (40, 90, 190)), (.5, (24, 50, 120)), (1, (10, 20, 56))]), fin=dict(CLAM, vivid=.25),
       title=TT([('S', (60, 150, 245)), ('O', (250, 206, 70)), ('UL', (60, 150, 245))], 'popb', 150, sp=0, shadow=((10, 20, 60), 3, 3)),  # typeset: the logo's blues run into the sky; Ian could supply it
       face=ph(.37, .2, .2, 1.4), lcol=WHT)

# Friends: The Reunion: Central Perk's dark brick, F.R.I.E.N.D.S with its coloured dots and the yellow-brush THE REUNION (typeset), the six on the stoop
std('friends-the-reunion-2021', ('grad', [(0, (60, 54, 44)), (.6, (26, 22, 18)), (1, (8, 6, 6))]), WHT,
    [TT([('F', WHT), ('.', (220, 40, 40)), ('R', WHT), ('.', (40, 140, 220)), ('I', WHT), ('.', (250, 210, 40)), ('E', WHT), ('.', (220, 40, 40)),
         ('N', WHT), ('.', (250, 210, 40)), ('D', WHT), ('.', (40, 140, 220)), ('S', WHT)], 'ter', 92, sp=.02),
     T('THE REUNION', 'herbi', 34, (30, 26, 20), box=((250, 220, 50), 8, 4), track=.25)], tgap=10,
    photo=ph(.5, .42, .8, .6), pb=(250, 220, 50), lg=WHT, lw=.7, order='LPTF',
    ft='a', vbox=(250, 220, 50), vink=(26, 22, 18), fcol=(210, 204, 196), fin=MINT)

# Wrath of Man: tailor's charcoal, the pale grey serif capitals, H at the head
std('wrath-of-man-2021', ('grad', [(0, (70, 70, 70)), (.6, (30, 30, 30)), (1, (8, 8, 8))]), (210, 206, 198),
    L([(0.09, 0.74, 0.76, 0.82), (0.76, 0.765, 0.92, 0.805), (0.28, 0.82, 0.92, 0.89)], 76, (214, 210, 202), mode='light', speck=.01),
    photo=ph(.48, .18, .4, 1.0), pb=(214, 210, 202), lg=WHT, lw=.6, order='LPTCF', credit=['JASON STATHAM'], ccol=(214, 210, 202),
    ft='a', vbox=(214, 210, 202), vink=(30, 30, 30), fcol=(180, 178, 174), fin=SLIP)

# Cruella: a Disney clamshell.  Black and white, the poster's red brush CRUELLA cut off it, Estella in the diamond
disney('cruella-2021', ('grad', [(0, (60, 60, 62)), (.5, (24, 24, 26)), (1, (8, 8, 8))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.09, 0.49, 0.93, 0.84)], 150, cuts=[key_cut(lambda a: (a[..., 0] > .42) & (a[..., 0] > a[..., 1] + .25) & (a[..., 0] > a[..., 2] + .2), soft=1.0)]),
       face=ph(.52, .2, .2, 1.4), lcol=WHT)

# False Positive: hospital black, the thin white condensed capitals with the red I (typeset), Lucy at the centre
std('false-positive-2021', ('grad', [(0, (50, 50, 54)), (.6, (18, 18, 20)), (1, (6, 6, 6))]), WHT,
    TT([('FALSE POS', WHT), ('I', (220, 40, 40)), ('T', WHT), ('I', (220, 40, 40)), ('VE', WHT)], 'hcn', 84, squeeze=.6, sp=0),
    photo=ph(.42, .37, .4, 1.0), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['ILANA GLAZER', 'JUSTIN THEROUX'], ccol=WHT,
    ft='a', vbox=(220, 40, 40), fcol=(200, 200, 204), fin=MINT)

# Point Break (1991): a real rental, the big-wave blue, the white heavy capitals, Johnny and Bodhi
std('point-break-1991', ('grad', [(0, (40, 110, 160)), (.6, (14, 44, 70)), (1, (4, 14, 24))]), WHT,
    L((0.08, 0.585, 0.94, 0.69), 92, WHT, mode='light', speck=.01),
    photo=ph(.47, .2, .94, .6), pb=WHT, lg=WHT, lw=.7, order='LPTCSF', credit=['PATRICK SWAYZE', 'KEANU REEVES'], ccol=WHT,
    stick=BAR('15 01991', top='ACTION', fill=(232, 236, 240), ink=(30, 40, 60)), ft='a', vbox=WHT, vink=(14, 44, 70), fcol=(190, 210, 224), fin=RENTAL, seed=1991)

# Zola: the poster's peach-and-pink haze, the lilac @zola (typeset: a gradient), Zola at the head
std('zola-2021', ('grad', [(0, (250, 200, 190)), (.5, (236, 150, 170)), (1, (150, 80, 150))]), (130, 90, 200),
    T('@zola', 'popb', 120, (140, 100, 210), grad=[(0, (180, 160, 240)), (1, (110, 70, 190))]),
    photo=ph(.3, .35, .4, 1.0), pb=(140, 100, 210), lg=(60, 30, 70), lw=.6, order='LPTCF', credit=['TAYLOUR PAIGE', 'RILEY KEOUGH'], ccol=(60, 30, 70),
    ft='a', vbox=(140, 100, 210), fcol=(60, 30, 70), fin=MINT)

# Space Jam: A New Legacy: the poster's orange-to-violet, a chrome-blue SPACE JAM (typeset: it sits behind the Tunes), LeBron at the head
std('space-jam-a-new-legacy-2021', ('grad', [(0, (250, 140, 30)), (.5, (226, 60, 90)), (1, (110, 40, 190))]), (40, 90, 220),
    [T('SPACE JAM', 'intbk', 92, (60, 110, 230), squeeze=.84, grad=[(0, (130, 190, 255)), (.5, (40, 90, 220)), (1, (20, 40, 140))], outline=((14, 20, 60), 2.2)),
     T('A NEW LEGACY', 'intbk', 36, (250, 160, 30), track=.08, outline=((60, 20, 40), 1.4))], tgap=8,
    photo=ph(.53, .3, .22, 1.0), pb=WHT, lg=WHT, lw=.7, order='LPTCF', credit=['LeBRON JAMES'], ccol=WHT,
    ft='a', vbox=WHT, vink=(226, 60, 90), fcol=WHT, fin=MINT)

# Woodstock 99: Peace, Love, and Rage: the poster's burnt orange, the white heavy capitals and subtitle (typeset: they sit in a ruled box), the stage and the crowd
std('woodstock-99-peace-love-and-rage-2021', ('grad', [(0, (226, 100, 40)), (.6, (170, 80, 40)), (1, (60, 40, 20))]), WHT,
    [T('WOODSTOCK 99', 'intbk', 70, WHT, squeeze=.86), T('PEACE, LOVE, AND RAGE', 'herb', 28, WHT, track=.1)], tgap=8,
    photo=ph(.5, .55, .9, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(170, 80, 40), fcol=(250, 230, 210), fin=MINT)

# Those Who Wish Me Dead: wildfire orange and black, the yellow condensed capitals (typeset: stacked five high), Hannah at the head
std('those-who-wish-me-dead-2021', ('grad', [(0, (180, 70, 20)), (.5, (80, 24, 10)), (1, (12, 6, 4))]), (240, 196, 40),
    T('THOSE WHO WISH ME DEAD', 'hcnb', 80, (242, 198, 44), squeeze=.78, bold=.8),
    photo=ph(.86, .09, .28, 1.0), pb=(242, 198, 44), lg=WHT, lw=.6, order='LPTCF', credit=['ANGELINA JOLIE'], ccol=(242, 198, 44),
    ft='a', vbox=(242, 198, 44), vink=(80, 24, 10), fcol=(230, 210, 190), fin=MINT)

# The Suicide Squad: the poster's cream, red and black comic capitals (typeset), the whole squad at the head
std('the-suicide-squad-2021', ('grad', [(0, (238, 230, 214)), (.6, (226, 214, 190)), (1, (170, 150, 120))]), (210, 30, 30),
    [T('THE', 'intbk', 40, (214, 32, 32), outline=((20, 18, 18), 1.6)), T('SUICIDE SQUAD', 'intbk', 84, (214, 32, 32), squeeze=.82, outline=((20, 18, 18), 2.4), shadow=((20, 18, 18), 3, 3))], tgap=8,
    photo=ph(.5, .33, .8, .8), pb=(20, 18, 18), lg=(20, 18, 18), lw=.5, order='LPTCF', credit=['A JAMES GUNN', 'FILM'], ccol=(20, 18, 18),
    ft='a', vbox=(214, 32, 32), fcol=(20, 18, 18), fin=SLIP)

# Pig: near-black and plum, the thin spaced serif P I G, Rob's eye
std('pig-2021', ('grad', [(0, (60, 40, 44)), (.6, (24, 16, 18)), (1, (6, 4, 4))]), (220, 210, 206),
    L((0.25, 0.81, 0.76, 0.91), 90, (226, 216, 212), mode='light', speck=.003),
    photo=ph(.6, .33, .5, 1.0), pb=(226, 216, 212), lg=WHT, lw=.6, order='LPTCF', credit=['NICOLAS CAGE'], ccol=(226, 216, 212),
    ft='a', vbox=(226, 216, 212), vink=(24, 16, 18), fcol=(190, 180, 180), fin=MINT, dotst=(['STAFF', 'PICK'], (150, 40, 60)))

# Black Widow: the poster's red hourglass on black, white italic capitals (typeset: brushed and small), Natasha at the head
std('black-widow-2021', ('grad', [(0, (180, 20, 24)), (.5, (70, 8, 10)), (1, (8, 4, 4))]), WHT,
    TT([('BLACK', WHT), ('WIDOW', WHT)], 'intbki', 84, sp=.3, squeeze=.84, rough=.3),
    photo=ph(.5, .12, .3, 1.0), pb=(214, 30, 34), lg=WHT, lw=.7, order='LPTCF', credit=['SCARLETT JOHANSSON'], ccol=WHT,
    ft='a', vbox=(214, 30, 34), fcol=(220, 200, 200), fin=SLIP)

# Kate: Tokyo neon, a hollow cyan KATE like the sign (typeset), Kate at the head
std('kate-2021', ('grad', [(0, (40, 30, 70)), (.5, (100, 20, 70)), (1, (20, 6, 20))]), (60, 230, 240),
    T('KATE', 'adv', 130, (40, 30, 70), track=.08, outline=((80, 240, 250), 2.6), soft=((60, 220, 240), 8, .6)),
    photo=ph(.63, .1, .35, 1.0), pb=(80, 240, 250), lg=WHT, lw=.6, order='LPTCF', credit=['MARY ELIZABETH', 'WINSTEAD'], ccol=(250, 120, 200),
    ft='a', vbox=(250, 80, 180), fcol=(210, 200, 230), fin=MINT)

# Free Guy: Free City's sky, white FREE and blue GUY (typeset: over the explosions), Guy and his coffee
std('free-guy-2021', ('grad', [(0, (120, 170, 220)), (.5, (60, 100, 160)), (1, (20, 30, 60))]), WHT,
    TT([('FREE', WHT), ('GUY', (40, 170, 240))], 'intbk', 100, sp=.25, squeeze=.9),
    photo=ph(.45, .3, .3, 1.0), pb=(40, 170, 240), lg=WHT, lw=.7, order='LPTCF', credit=['RYAN REYNOLDS'], ccol=WHT,
    ft='a', vbox=(40, 170, 240), fcol=(210, 226, 240), fin=MINT)

# Road House (1989): a real rental, the Double Deuce's dark, the neon script logo (Ian's image, shared with the 2024 remake), Dalton at the head
std('road-house-1989', ('grad', [(0, (70, 74, 90)), (.5, (24, 26, 34)), (1, (60, 14, 16))]), (90, 230, 250),
    Pic('logos/road-house-title.png', 140),
    photo=ph(.42, .15, .4, 1.0), pb=(150, 246, 255), lg=WHT, lw=.6, order='LPTCSF', credit=['PATRICK SWAYZE'], ccol=(150, 246, 255),
    stick=PRC(['2 NIGHTS', '$1.99']), ft='a', vbox=(150, 246, 255), vink=(24, 26, 34), fcol=(200, 206, 214), fin=RENTAL, seed=1989)

# Man Push Cart (2006): a Manhattan night, the white wide-spaced capitals (typeset: three stepped lines), Ahmad's cart
std('man-push-cart-2006', ('grad', [(0, (40, 54, 60)), (.6, (14, 20, 24)), (1, (4, 6, 8))]), WHT,
    T('MAN PUSH CART', 'her', 64, WHT, track=.35),
    photo=ph(.5, .55, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A RAMIN BAHRANI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 20, 24), fcol=(190, 200, 204), fin=WORN, seed=2006)

# Deep Cover (1992): a real rental, the poster's blood red and black, the white condensed capitals (typeset), John's face
std('deep-cover-1992', ('grad', [(0, (160, 20, 20)), (.5, (70, 8, 8)), (1, (8, 2, 2))]), WHT,
    T('DEEP COVER', 'hcnb', 96, WHT, squeeze=.74, bold=1.2),  # typeset: the lift broke on the red
    photo=ph(.62, .25, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['LAURENCE FISHBURNE', 'JEFF GOLDBLUM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(70, 8, 8), fcol=(220, 196, 196), fin=RENTAL, seed=1992, over=[dot(262, ['NEW', 'JACK'], (250, 210, 40), (30, 20, 10), x=.72, d=62)])

# The Card Counter: casino-card white and red, the thin spaced capitals (typeset), William at the head
std('the-card-counter-2021', ('grad', [(0, (240, 234, 226)), (.6, (210, 200, 190)), (1, (90, 70, 60))]), (40, 36, 34),
    [T('THE', 'her', 28, (40, 36, 34), track=.6), T('CARD COUNTER', 'her', 56, (40, 36, 34), track=.4)], tgap=8,
    photo=ph(.5, .22, .35, 1.0), pb=(200, 40, 40), lg=(40, 36, 34), lw=.6, order='LPTCF', credit=['OSCAR ISAAC'], ccol=(200, 40, 40),
    ft='a', vbox=(200, 40, 40), fcol=(40, 36, 34), fin=MINT)

# The Guilty: the dispatch room's black, the red condensed capitals, the face made of 911 calls
std('the-guilty-2021', ('grad', [(0, (60, 30, 26)), (.6, (22, 12, 10)), (1, (6, 4, 4))]), (210, 30, 30),
    L((0.24, 0.825, 0.77, 0.915), 100, (214, 32, 32), mode='key', key=(200, 30, 30), t=(70, 150), speck=.01),
    photo=ph(.5, .4, .6, 1.0), pb=(214, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['JAKE GYLLENHAAL'], ccol=(214, 32, 32),
    ft='a', vbox=(214, 32, 32), fcol=(200, 190, 186), fin=MINT)

# Venom: Let There Be Carnage: symbiote blue-black, silver VENOM and the scratchy subtitle (typeset), Venom at the head
std('venom-let-there-be-carnage-2021', ('grad', [(0, (30, 70, 130)), (.5, (12, 26, 50)), (1, (4, 6, 12))]), (220, 224, 230),
    [T('VENOM', 'ter', 100, (226, 230, 236), track=.04, grad=[(0, (250, 250, 255)), (.5, (160, 170, 186)), (1, (230, 234, 240))], outline=((10, 10, 16), 1.6)),
     T('LET THERE BE CARNAGE', 'herbi', 30, (220, 40, 40), track=.12)], tgap=8,
    photo=ph(.72, .23, .3, 1.0), pb=(220, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['TOM HARDY'], ccol=WHT,
    ft='a', vbox=(220, 40, 40), fcol=(190, 200, 214), fin=SLIP)

# Dune: Arrakis haze, the poster's spaced glyph lettering set in wide capitals (typeset), Paul at the head
std('dune-2021', ('grad', [(0, (150, 186, 190)), (.5, (110, 130, 130)), (.8, (190, 140, 90)), (1, (90, 60, 34))]), (30, 28, 26),
    T('DUNE', 'adv', 110, (34, 32, 30), track=.7),
    photo=ph(.52, .1, .3, 1.0), pb=(34, 32, 30), lg=(34, 32, 30), lw=.6, order='LPTCF', credit=['A DENIS VILLENEUVE', 'FILM'], ccol=(34, 32, 30),
    ft='a', vbox=(34, 32, 30), fcol=(34, 32, 30), fin=MINT)

# No Time to Die: the gun-barrel black and white, the gold stencil capitals (typeset: stacked), Bond at the head
std('no-time-to-die-2021', ('grad', [(0, (236, 236, 236)), (.35, (40, 40, 40)), (1, (6, 6, 6))]), (200, 160, 70),
    [T('NO TIME TO DIE', 'hcnb', 80, (204, 164, 74), squeeze=.8, grad=[(0, (226, 190, 100)), (1, (170, 130, 50))]), T('007', 'herbi', 30, (220, 220, 220))], tgap=8,
    photo=ph(.4, .16, .35, 1.0), pb=(204, 164, 74), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['DANIEL CRAIG'], ccol=(204, 164, 74),
    ft='a', vbox=(204, 164, 74), vink=(20, 20, 20), fcol=(200, 196, 190), fin=SLIP)

# The Unforgivable: prison grey-green, the white heavy capitals (typeset), Ruth's face
std('the-unforgivable-2021', ('grad', [(0, (90, 96, 90)), (.6, (40, 42, 40)), (1, (12, 12, 12))]), WHT,
    TT([('THE', WHT), ('UNFORGIVABLE', WHT)], 'hcnb', 84, sp=.25, squeeze=.74, bold=1.2),  # typeset: the lift broke on her shoulder
    photo=ph(.55, .4, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['SANDRA BULLOCK'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 42, 40), fcol=(200, 204, 200), fin=MINT)


# =====================================================================================
# the 2019 shelf (films-2019.json).  Same approach as 2021-2025.  Credits and typed labels
# checked on IMDb (17 Nov 2026).  Toy Story 4 (Pixar) is a clamshell.
# =====================================================================================

# Boy Erased: the poster's warm lamplight gold, the white serif capitals (typeset: they sit on the coat), Jared between his parents
std('boy-erased-2018', ('grad', [(0, (190, 150, 70)), (.6, (100, 76, 36)), (1, (30, 22, 10))]), WHT,
    [T('BOY', 'ter', 60, WHT, track=.12), T('ERASED', 'ter', 60, WHT, track=.12)], tgap=8,
    photo=ph(.51, .38, .32, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['LUCAS HEDGES', 'NICOLE KIDMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(100, 76, 36), fcol=(236, 222, 196), fin=MINT)

# The Favourite: the poster's cream, the brown engraved capitals, the three of them in the frame
std('the-favourite-2018', ('solid', (236, 228, 212)), (90, 74, 50),
    [T('THE', 'ter', 26, (92, 76, 52), track=.6), L((0.1, 0.11, 0.92, 0.23), 80, (92, 76, 52), mode='dark', speck=.01)], tgap=8,
    photo=ph(.6, .55, .5, 1.0), pb=(92, 76, 52), lg=(92, 76, 52), lw=.6, order='LPTCF', credit=['OLIVIA COLMAN', 'EMMA STONE'], ccol=(92, 76, 52),
    ft='a', vbox=(92, 76, 52), fcol=(92, 76, 52), fin=MINT)

# Cold War: black and white, the white condensed capitals, Wiktor and Zula
std('cold-war-2018', ('grad', [(0, (60, 60, 60)), (.5, (20, 20, 20)), (1, (6, 6, 6))]), WHT,
    L((0.16, 0.69, 0.84, 0.84), 100, WHT, mode='light', speck=.01),
    photo=ph(.52, .27, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A PAWEŁ PAWLIKOWSKI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 20, 20), fcol=(200, 200, 200), fin=MINT)

# Green Book: the car's turquoise, thin white capitals (typeset: too thin to lift), Tony and Don in the car
std('green-book-2018', ('grad', [(0, (40, 140, 160)), (.6, (20, 110, 130)), (1, (8, 50, 60))]), WHT,
    T('GREEN BOOK', 'her', 70, WHT, track=.04),
    photo=ph(.5, .58, .9, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['VIGGO MORTENSEN', 'MAHERSHALA ALI'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 110, 130), fcol=(210, 236, 240), fin=MINT)

# Shoplifters: the woodblock-print sand and indigo, a white italic like the poster's (typeset: it runs over the waves), the family at the shore
std('shoplifters-2018', ('grad', [(0, (222, 210, 184)), (.6, (200, 186, 160)), (1, (160, 150, 130))]), (40, 50, 96),
    T('Shoplifters', 'teri', 92, (36, 46, 92)),
    photo=ph(.42, .42, .6, 1.0), pb=(36, 46, 92), lg=(36, 46, 92), lw=.6, order='LPTCF', credit=['A HIROKAZU KOREEDA', 'FILM'], ccol=(36, 46, 92),
    ft='a', vbox=(36, 46, 92), fcol=(36, 46, 92), fin=MINT)

# Border: the Swedish forest's dark green, the yellow geometric capitals, Tina in her uniform
std('border-2018', ('grad', [(0, (30, 50, 30)), (.6, (12, 22, 12)), (1, (4, 8, 4))]), (240, 220, 40),
    L((0.08, 0.11, 0.92, 0.25), 90, (242, 222, 44), mode='key', key=(240, 220, 40), t=(70, 150), speck=.01),
    photo=ph(.43, .35, .3, 1.0), pb=(242, 222, 44), lg=WHT, lw=.6, order='LPTCF', credit=['AN ALI ABBASI', 'FILM'], ccol=(242, 222, 44),
    ft='a', vbox=(242, 222, 44), vink=(12, 22, 12), fcol=(200, 210, 196), fin=MINT)

# The Ballad of Buster Scruggs: the poster's red tooled leather, the cream western script (typeset: it twines through the guns)
std('the-ballad-of-buster-scruggs-2018', ('grad', [(0, (170, 40, 30)), (.6, (110, 24, 18)), (1, (50, 10, 8))]), (240, 220, 180),
    [T('The Ballad of', 'cho', 50, (242, 222, 184)), T('Buster Scruggs', 'cho', 90, (242, 222, 184))], tgap=4,
    lg=(242, 222, 184), lw=.6, order='LTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(242, 222, 184),
    ft='a', vbox=(242, 222, 184), vink=(110, 24, 18), fcol=(230, 200, 180), fin=SLIP)

# Minding the Gap: black torn tape, the white hand lettering (typeset: the torn paper round it is white too), Zack skating
std('minding-the-gap-2018', ('grad', [(0, (40, 40, 44)), (.6, (16, 16, 18)), (1, (6, 6, 6))]), WHT,
    T('Minding the Gap', 'cho', 90, WHT),
    photo=ph(.5, .13, .9, .6), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A BING LIU', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 16, 18), fcol=(200, 200, 204), fin=MINT)

# A Star Is Born: stage-light black, the gold serif capitals (typeset: stepped down the poster), Jack and Ally
std('a-star-is-born-2018', ('grad', [(0, (70, 70, 70)), (.6, (30, 30, 30)), (1, (10, 10, 10))]), (196, 150, 50),
    T('A STAR IS BORN', 'ter', 76, (200, 156, 56), track=.06, grad=[(0, (226, 186, 90)), (1, (170, 124, 36))]),
    photo=ph(.42, .72, .6, 1.0), pb=(200, 156, 56), lg=WHT, lw=.6, order='LPTCF', credit=['BRADLEY COOPER', 'LADY GAGA'], ccol=WHT,
    ft='a', vbox=(200, 156, 56), vink=(30, 30, 30), fcol=(210, 210, 210), fin=MINT)

# Free Solo: El Capitan's granite and the forest far below, white spaced capitals (typeset), Alex on the wall
std('free-solo-2018', ('grad', [(0, (150, 130, 110)), (.5, (70, 80, 60)), (1, (20, 30, 20))]), WHT,
    T('FREE SOLO', 'herb', 70, WHT, track=.4),
    photo=ph(.48, .3, .55, 1.0), pb=WHT, lg=WHT, lw=.7, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(70, 80, 60), fcol=(220, 220, 210), fin=MINT)

# Roma: black and white, the big yellow serif capitals, the family on the beach
std('roma-2018', ('grad', [(0, (226, 226, 224)), (.6, (190, 190, 188)), (1, (130, 130, 128))]), (232, 190, 40),
    L((0.13, 0.67, 0.88, 0.9), 110, (234, 192, 44), mode='key', key=(232, 190, 40), t=(70, 150), speck=.01),
    photo=ph(.55, .38, .6, 1.0), pb=(234, 192, 44), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['AN ALFONSO CUARÓN', 'FILM'], ccol=(20, 20, 20),
    ft='a', vbox=(234, 192, 44), vink=(20, 20, 20), fcol=(220, 220, 220), fin=MINT, dotst=(['STAFF', 'PICK'], (30, 30, 30), (234, 192, 44)))

# Spider-Man: Into the Spider-Verse: the upside-down city blue, the red comic capitals (typeset), Miles falling
std('spider-man-into-the-spider-verse-2018', ('grad', [(0, (30, 40, 90)), (.5, (60, 110, 180)), (1, (200, 220, 240))]), (226, 30, 40),
    [T('SPIDER-MAN', 'intbk', 84, (228, 32, 42), squeeze=.84, outline=((14, 14, 20), 2.4), shadow=((14, 14, 20), 3, 3)),
     T('INTO THE SPIDER-VERSE', 'herb', 28, (226, 30, 40), track=.1, outline=(WHT, 1.2))], tgap=8,
    photo=ph(.45, .4, .5, 1.0), pb=(228, 32, 42), lg=(14, 14, 20), lw=.6, order='LPTF',
    ft='a', vbox=(228, 32, 42), fcol=(20, 30, 60), fin=MINT)

# Can You Ever Forgive Me?: the poster's typing-paper cream, the typewriter lettering (typeset: it runs over Lee), the typewriter at the head
std('can-you-ever-forgive-me-2018', ('grad', [(0, (236, 228, 210)), (.6, (210, 200, 180)), (1, (120, 110, 96))]), (30, 28, 26),
    T('Can You Ever Forgive Me?', 'monob', 54, (30, 28, 26), track=.02, rough=.3),
    photo=ph(.5, .62, .8, .6), pb=(30, 28, 26), lg=(30, 28, 26), lw=.6, order='LPTCF', credit=['MELISSA McCARTHY', 'RICHARD E. GRANT'], ccol=(30, 28, 26),
    ft='a', vbox=(30, 28, 26), fcol=(30, 28, 26), fin=MINT)

# mid90s: LA sky blue, the big white serif lower case (typeset: it sits on his T-shirt), Stevie at the head
std('mid90s-2018', ('grad', [(0, (150, 180, 210)), (.5, (120, 100, 80)), (1, (50, 36, 26))]), WHT,
    T('mid90s', 'ter', 120, WHT),
    photo=ph(.5, .38, .4, 1.0), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A JONAH HILL', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(120, 100, 80), fcol=(230, 220, 210), fin=MINT)

# Bohemian Rhapsody: the poster's violet-to-gold Live Aid sky, its yellow BOHEMIAN and the thin gold RHAPSODY (typeset), Freddie on stage
std('bohemian-rhapsody-2018', ('grad', [(0, (140, 50, 200)), (.45, (200, 70, 150)), (.75, (240, 160, 40)), (1, (120, 60, 10))]), (246, 214, 50),
    [L((0.13, 0.17, 0.87, 0.255), 70, (248, 216, 54), mode='key', key=(246, 210, 50), t=(70, 150), speck=.01), T('RHAPSODY', 'ter', 50, (248, 216, 54), track=.08)], tgap=8,
    photo=ph(.5, .68, .55, 1.0), pb=(248, 216, 54), lg=WHT, lw=.6, order='LPTCF', credit=['RAMI MALEK'], ccol=WHT,
    ft='a', vbox=(248, 216, 54), vink=(120, 60, 10), fcol=WHT, fin=SLIP)

# Triple Frontier: the poster's torn-paper white, the dark distressed capitals (typeset), the five of them
std('triple-frontier-2019', ('grad', [(0, (230, 230, 226)), (.6, (200, 200, 196)), (1, (110, 110, 104))]), (34, 36, 34),
    T('TRIPLE FRONTIER', 'intbk', 74, (34, 36, 34), squeeze=.84, rough=.6),  # typeset: the distressed letters fell apart
    photo=ph(.5, .22, .9, .6), pb=(34, 36, 34), lg=(34, 36, 34), lw=.6, order='LPTCF', credit=['BEN AFFLECK', 'OSCAR ISAAC'], ccol=(34, 36, 34),
    ft='a', vbox=(34, 36, 34), fcol=(34, 36, 34), fin=MINT)

# Guava Island: black with the poster's teal leaves, red hand-cut capitals (typeset: they lean and tumble), the island's face
std('guava-island-2019', ('grad', [(0, (20, 50, 46)), (.6, (8, 16, 16)), (1, (4, 6, 6))]), (214, 70, 60),
    T('GUAVA ISLAND', 'bonb', 80, (216, 72, 62), track=.04, rough=.5),
    photo=ph(.45, .62, .5, 1.0), pb=(40, 140, 120), lg=WHT, lw=.6, order='LPTCF', credit=['DONALD GLOVER', 'RIHANNA'], ccol=(216, 72, 62),
    ft='a', vbox=(216, 72, 62), vink=(8, 16, 16), fcol=(170, 200, 190), fin=MINT)

# The Boy Band Con: the poster's flat orange, hollow outlined capitals (typeset), Lou at his desk under the spotlight
std('the-boy-band-con-the-lou-pearlman-story-2019', ('solid', (240, 90, 20)), (250, 236, 220),
    [T('THE BOY BAND CON', 'hcn', 70, (240, 90, 20), squeeze=.8, outline=((252, 238, 222), 2.2)), T('THE LOU PEARLMAN STORY', 'herb', 22, (252, 238, 222), track=.3)], tgap=8,
    photo=ph(.75, .68, .45, 1.0), pb=(252, 238, 222), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=MINT)

# Extremely Wicked, Shockingly Evil and Vile: line-up navy, the yellow heavy capitals (typeset), Ted in his yellow sweater
std('extremely-wicked-shockingly-evil-and-vile-2019', ('grad', [(0, (30, 40, 60)), (.6, (14, 18, 28)), (1, (4, 6, 10))]), (248, 210, 40),
    [T('EXTREMELY WICKED', 'intbk', 66, (248, 212, 44), squeeze=.8), T('SHOCKINGLY EVIL AND VILE', 'herb', 26, (248, 212, 44), track=.08)], tgap=8,
    photo=ph(.52, .6, .4, 1.0), pb=(248, 212, 44), lg=WHT, lw=.6, order='LPTCF', credit=['ZAC EFRON', 'LILY COLLINS'], ccol=(248, 212, 44),
    ft='a', vbox=(248, 212, 44), vink=(14, 18, 28), fcol=(190, 196, 210), fin=MINT)

# Unicorn Store: lawn green, the rainbow capitals (typeset with the poster's pastel run), Kit in the grass
std('unicorn-store-2017', ('grad', [(0, (60, 110, 50)), (.6, (26, 50, 22)), (1, (8, 16, 6))]), (200, 170, 240),
    T('UNICORN STORE', 'popb', 72, WHT, grad=[(0, (190, 150, 240)), (.35, (130, 200, 250)), (.7, (150, 236, 190)), (1, (250, 200, 150))]),
    photo=ph(.5, .66, .5, 1.0), pb=(250, 200, 230), lg=WHT, lw=.6, order='LPTCF', credit=['BRIE LARSON'], ccol=(250, 200, 230),
    ft='a', vbox=(250, 200, 230), vink=(26, 50, 22), fcol=(200, 220, 190), fin=MINT)

# Dolemite Is My Name: the poster's cream and seventies orange-teal stripes, the black slab capitals (typeset), Rudy in his white suit
std('dolemite-is-my-name-2019', ('grad', [(0, (240, 232, 216)), (.35, (40, 140, 140)), (.7, (210, 90, 30)), (1, (90, 36, 14))]), (20, 18, 16),
    T('DOLEMITE IS MY NAME', 'intbk', 72, (20, 18, 16), squeeze=.84, outline=((244, 236, 220), 2.0)),
    photo=ph(.52, .13, .3, 1.0), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['EDDIE MURPHY'], ccol=WHT,
    ft='a', vbox=(20, 18, 16), fcol=WHT, fin=MINT)

# Greenberg (2010): white, the small green heavy capitals (typeset: too small to lift), Roger looking up
std('greenberg-2010', ('solid', (244, 244, 240)), (30, 110, 60),
    T('GREENBERG', 'hcnb', 84, (30, 112, 62), squeeze=.86, bold=.6),
    photo=ph(.5, .85, .4, 1.0), pb=(30, 112, 62), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['BEN STILLER'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 112, 62), fcol=(30, 30, 30), fin=SLIP, seed=2010)

# Good Boys: the poster's flat red, the fat white GOOD BOYS with the devil horns, the three of them looking up
std('good-boys-2019', ('solid', (214, 40, 30)), WHT,
    L([(0.14, 0.17, 0.86, 0.305), (0.14, 0.305, 0.86, 0.43)], 100, WHT, mode='light', speck=.01),
    photo=ph(.5, .88, .9, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JACOB TREMBLAY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(214, 40, 30), fcol=WHT, fin=MINT)

# Twinsters: soft morning grey, the navy thin capitals (typeset), the twins asleep (no logo file: its company in type)
std('twinsters-2015', ('grad', [(0, (236, 238, 240)), (.6, (200, 204, 208)), (1, (150, 154, 160))]), (40, 54, 80),
    T('TWINSTERS', 'her', 76, (42, 56, 82), track=.02),
    photo=ph(.5, .82, .9, .6), pb=(42, 56, 82), studio=['SMALL PACKAGE', 'FILMS'], scol=(42, 56, 82), order='lPTCF', credit=['A DOCUMENTARY'], ccol=(42, 56, 82),
    ft='a', vbox=(42, 56, 82), fcol=(42, 56, 82), fin=SLIP)

# Booksmart: the poster's school-day blue, the yellow chunky lower case (typeset: it runs over their arms), Amy and Molly
std('booksmart-2019', ('grad', [(0, (230, 226, 220)), (.35, (40, 70, 130)), (1, (14, 24, 50))]), (248, 220, 40),
    T('booksmart', 'bonb', 100, (250, 222, 44)),
    photo=ph(.5, .2, .9, .6), pb=(250, 222, 44), lg=(30, 30, 34), lw=.6, order='LPTCF', credit=['KAITLYN DEVER', 'BEANIE FELDSTEIN'], ccol=(250, 222, 44),
    ft='a', vbox=(250, 222, 44), vink=(14, 24, 50), fcol=(200, 210, 230), fin=MINT)

# Three Identical Strangers: the poster's flat yellow, the black jigsaw capitals (typeset), the three boys
std('three-identical-strangers-2018', ('solid', (246, 214, 30)), (20, 18, 14),
    T('THREE IDENTICAL STRANGERS', 'intbk', 62, (20, 18, 14), squeeze=.8, rough=.5),  # typeset: the jigsaw letters broke up
    photo=ph(.5, .88, .9, .6), pb=(20, 18, 14), lg=(20, 18, 14), lw=.5, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(20, 18, 14),
    ft='a', vbox=(20, 18, 14), vink=(246, 214, 30), fcol=(20, 18, 14), fin=MINT)

# Stop Making Sense (1984): a well-played music tape, black, the thin red capitals (typeset), David's big suit (no logo file: the band's company in type)
std('stop-making-sense-1984', ('grad', [(0, (40, 36, 34)), (.6, (14, 12, 12)), (1, (4, 4, 4))]), (220, 40, 30),
    T('STOP MAKING SENSE', 'hcn', 76, (224, 44, 34), squeeze=.7),
    photo=ph(.4, .35, .6, 1.0), pb=(224, 44, 34), studio=['TALKING HEADS'], scol=(220, 214, 200), order='lPTCSF', credit=['A JONATHAN DEMME', 'FILM'], ccol=(220, 214, 200),
    stick=flow(dot, 70, ['MUSIC'], (40, 110, 200), d=60), ft='e', fcol=(220, 214, 200), fin=OLD, seed=1984)

# Over the Garden Wall: the Unknown's autumn wood, the gold storybook capitals (typeset: ornamented), Wirt and Greg in the clearing
std('over-the-garden-wall-2014', ('grad', [(0, (120, 110, 60)), (.5, (60, 50, 26)), (1, (20, 16, 8))]), (210, 160, 70),
    [T('OVER THE', 'ter', 40, (214, 166, 76), track=.12), T('GARDEN WALL', 'ter', 66, (214, 166, 76), track=.06, bold=.4)], tgap=8,
    photo=ph(.5, .5, .4, 1.0), pb=(214, 166, 76), lg=WHT, lw=.6, order='LPTCF', credit=['ELIJAH WOOD'], ccol=(214, 166, 76),
    ft='a', vbox=(214, 166, 76), vink=(60, 50, 26), fcol=(210, 200, 180), fin=SLIP)

# I Love You, Now Die: cold blue, the white heavy capitals and the spaced subtitle (typeset), Michelle's face
std('i-love-you-now-die-the-commonwealth-v-michelle-carter-2019', ('grad', [(0, (80, 90, 120)), (.6, (30, 34, 50)), (1, (8, 10, 16))]), WHT,
    [T('I LOVE YOU, NOW DIE', 'intbk', 60, WHT, squeeze=.86), T('THE COMMONWEALTH V. MICHELLE CARTER', 'herb', 18, (220, 70, 70), track=.12)], tgap=8,
    photo=ph(.45, .25, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(30, 34, 50), fcol=(190, 196, 210), fin=MINT)

# The Lunchbox: the poster's warm cream, the red script Lunch and dark BOX (typeset), Saajan and his tiffin
std('the-lunchbox-2013', ('grad', [(0, (240, 228, 200)), (.6, (220, 200, 160)), (1, (150, 110, 70))]), (190, 30, 30),
    TT([('the', (190, 30, 30)), ('Lunch', (190, 30, 30)), ('BOX', (40, 30, 24))], 'cho', 100, sp=.12),
    photo=ph(.45, .45, .4, 1.0), pb=(190, 30, 30), lg=(40, 30, 24), lw=.6, order='LPTCF', credit=['IRRFAN KHAN'], ccol=(40, 30, 24),
    ft='a', vbox=(190, 30, 30), fcol=(40, 30, 24), fin=SLIP)

# Mommy Dead and Dearest: the poster's cream wallpaper, black capitals on the yellow crime-scene tape (typeset), mother and daughter
std('mommy-dead-and-dearest-2017', ('grad', [(0, (240, 234, 220)), (.6, (220, 210, 190)), (1, (160, 150, 130))]), (20, 18, 16),
    T('MOMMY DEAD AND DEAREST', 'hcnb', 60, (20, 18, 16), squeeze=.8, box=((246, 222, 40), 10, 6)),
    photo=ph(.5, .25, .9, .6), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=MINT)

# Titus (1999): a real rental, the poster's electric blue, the spaced white Roman capitals (typeset), Titus in his helmet (no logo file: its company in type)
std('titus-1999', ('grad', [(0, (40, 150, 230)), (.5, (20, 80, 160)), (1, (6, 20, 50))]), WHT,
    T('TITUS', 'ter', 90, WHT, track=.5),
    photo=ph(.5, .45, .55, 1.0), pb=WHT, studio=['CLEAR BLUE SKY', 'PRODUCTIONS'], scol=WHT, order='lPTCSF', credit=['ANTHONY HOPKINS', 'JESSICA LANGE'], ccol=WHT,
    stick=PRC(['$2.49', 'DRAMA']), ft='a', vbox=WHT, vink=(20, 80, 160), fcol=(200, 220, 240), fin=RENTAL, seed=1999)

# Leaving Neverland: the old photo's dark, the white heavy capitals (typeset: on the photo), the boy in the hat
std('leaving-neverland-2019', ('grad', [(0, (90, 40, 40)), (.6, (30, 16, 16)), (1, (8, 4, 4))]), WHT,
    T('LEAVING NEVERLAND', 'intbk', 66, WHT, squeeze=.86),
    photo=ph(.6, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(30, 16, 16), fcol=(210, 196, 196), fin=MINT)

# The Big Sick: Chicago sky, the yellow fat lower case (typeset: on the family), Kumail and Emily
std('the-big-sick-2017', ('grad', [(0, (190, 210, 226)), (.5, (120, 140, 160)), (1, (40, 50, 60))]), (246, 230, 30),
    TT([('the', (246, 230, 30)), ('big sick', (246, 230, 30))], 'popb', 100, sp=.15, outline=((40, 40, 40), 1.4)),
    photo=ph(.5, .38, .6, 1.0), pb=(246, 230, 30), lg=WHT, lw=.6, order='LPTCF', credit=['KUMAIL NANJIANI', 'ZOE KAZAN'], ccol=WHT,
    ft='a', vbox=(246, 230, 30), vink=(40, 50, 60), fcol=WHT, fin=MINT)

# Sleepers (1996): a real rental, black, the spaced gold serif capitals (typeset), the four of them
std('sleepers-1996', ('grad', [(0, (40, 36, 30)), (.6, (14, 12, 10)), (1, (4, 4, 4))]), (210, 170, 90),
    T('SLEEPERS', 'ter', 76, (214, 174, 96), track=.35),
    photo=ph(.5, .72, .9, .6), pb=(214, 174, 96), lg=WHT, lw=.6, order='LPTCSF', credit=['ROBERT DE NIRO', 'BRAD PITT'], ccol=(214, 174, 96),
    stick=BAR('15 01996', top='DRAMA', fill=(236, 230, 214), ink=(40, 34, 28)), ft='a', vbox=(214, 174, 96), vink=(14, 12, 10), fcol=(190, 180, 160), fin=RENTAL, seed=1996)

# English Vinglish: the poster's yellow-green, black heavy capitals with its red letters (typeset; the Devanagari letters set as Latin), Shashi with her arms out
std('english-vinglish-2012', ('grad', [(0, (236, 230, 120)), (.6, (190, 190, 80)), (1, (100, 100, 40))]), (20, 18, 16),
    TT([('EN', (20, 18, 16)), ('G', (200, 30, 30)), ('LISH VINGLI', (20, 18, 16)), ('SH', (200, 30, 30))], 'intbk', 70, sp=0, squeeze=.86),
    photo=ph(.5, .45, .45, 1.0), pb=(200, 30, 30), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['SRIDEVI'], ccol=(20, 18, 16),
    ft='a', vbox=(200, 30, 30), fcol=(20, 18, 16), fin=SLIP)

# Living Dolls: the poster's white, the grey heavy capitals and red subtitle (typeset), the painted nesting dolls
std('living-dolls-2013', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 216)), (1, (170, 160, 156))]), (70, 70, 74),
    [T('LIVING DOLLS', 'intbk', 70, (72, 72, 76), squeeze=.86), T('THE SUBCULTURE OF DOLL COLLECTING', 'herb', 18, (210, 40, 70), track=.08)], tgap=8,
    photo=ph(.5, .6, .9, .6), pb=(210, 40, 70), lg=(72, 72, 76), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(72, 72, 76),
    ft='a', vbox=(210, 40, 70), fcol=(72, 72, 76), fin=MINT)

# All the Money in the World: Rome by flashbulb, the cream engraved capitals (typeset), Gail in the press scrum
std('all-the-money-in-the-world-2017', ('grad', [(0, (60, 70, 50)), (.6, (20, 24, 18)), (1, (6, 6, 4))]), (236, 228, 206),
    [T('ALL THE MONEY', 'ter', 62, (238, 230, 208), track=.08), T('IN THE WORLD', 'ter', 62, (238, 230, 208), track=.08)], tgap=8,
    photo=ph(.45, .3, .4, 1.0), pb=(238, 230, 208), lg=WHT, lw=.6, order='LPTCF', credit=['MICHELLE WILLIAMS', 'CHRISTOPHER PLUMMER'], ccol=(238, 230, 208),
    ft='a', vbox=(238, 230, 208), vink=(20, 24, 18), fcol=(200, 196, 180), fin=MINT)

# Shot Caller: prison-yard black, the grey distressed capitals (typeset), Money's face
std('shot-caller-2017', ('grad', [(0, (60, 60, 60)), (.6, (22, 22, 22)), (1, (6, 6, 6))]), (200, 200, 200),
    T('SHOT CALLER', 'hcnb', 92, (206, 206, 206), squeeze=.76, bold=1.0, rough=.6),
    photo=ph(.5, .17, .35, 1.0), pb=(206, 206, 206), lg=WHT, lw=.6, order='LPTCF', credit=['A RIC ROMAN WAUGH', 'FILM'], ccol=(206, 206, 206),
    ft='a', vbox=(206, 206, 206), vink=(22, 22, 22), fcol=(180, 180, 180), fin=SLIP)

# The Problem with Apu: Springfield yellow, the red The Problem with and the black APU (typeset), Hari in his glasses
std('the-problem-with-apu-2017', ('solid', (250, 210, 30)), (20, 18, 16),
    [T('The Problem with', 'her', 36, (200, 40, 30)), T('APU', 'intbk', 110, (20, 18, 16))], tgap=8,
    photo=ph(.55, .9, .4, 1.0), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['HARI KONDABOLU'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), vink=(250, 210, 30), fcol=(20, 18, 16), fin=MINT)

# Police Story (1985): an import rental, black capitals on the yellow police tape (typeset), Jackie with his gun
std('police-story-1985', ('grad', [(0, (90, 96, 90)), (.6, (40, 44, 40)), (1, (14, 14, 12))]), (20, 18, 16),
    T('POLICE STORY', 'hcnb', 76, (20, 18, 16), squeeze=.8, bold=.8, box=((246, 222, 40), 10, 6)),
    photo=ph(.4, .15, .45, 1.0), pb=(246, 222, 40), lg=WHT, lw=.6, order='LPTCSF', credit=['JACKIE CHAN'], ccol=(246, 222, 40),
    stick=PRC(['$1.49', 'ACTION']), ft='a', vbox=(246, 222, 40), vink=(20, 18, 16), fcol=(200, 200, 190), fin=RENTAL, seed=1985)

# The Wife: Stockholm night and pink blossom, thin spaced white capitals (typeset), Joan
std('the-wife-2017', ('grad', [(0, (60, 50, 70)), (.6, (22, 18, 26)), (1, (60, 20, 40))]), WHT,
    [T('THE', 'ter', 26, WHT, track=.4), T('WIFE', 'ter', 90, WHT, track=.5)], tgap=8,
    photo=ph(.3, .3, .4, 1.0), pb=(220, 120, 160), lg=WHT, lw=.6, order='LPTCF', credit=['GLENN CLOSE', 'JONATHAN PRYCE'], ccol=WHT,
    ft='a', vbox=(220, 120, 160), fcol=(220, 210, 220), fin=MINT)

# The Old Man & the Gun: the poster's cream, the red serif capitals (typeset: stacked), Forrest tipping his hat
std('the-old-man-the-gun-2018', ('solid', (240, 232, 214)), (180, 50, 40),
    TT([('the', (182, 52, 42)), ('OLD MAN', (182, 52, 42)), ('& the', (182, 52, 42)), ('GUN', (182, 52, 42))], 'schb', 76, sp=.2),
    photo=ph(.65, .28, .4, 1.0), pb=(182, 52, 42), lg=(40, 50, 70), lw=.6, order='LPTCF', credit=['ROBERT REDFORD', 'CASEY AFFLECK'], ccol=(40, 50, 70),
    ft='a', vbox=(182, 52, 42), fcol=(40, 50, 70), fin=MINT)

# A Serious Man (2009): Minnesota sky, the white and bronze serif capitals (typeset), Larry on the roof
std('a-serious-man-2009', ('grad', [(0, (120, 150, 170)), (.6, (170, 190, 200)), (1, (90, 90, 90))]), WHT,
    TT([('A', (150, 100, 40)), ('SERIOUS', WHT), ('MAN', (150, 100, 40))], 'ter', 80, sp=.25),
    photo=ph(.75, .65, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(90, 90, 90), fcol=WHT, fin=SLIP, seed=2009)

# Taking Lives (2004): murky green-black, the scratchy cream serif (typeset), Illeana's face
std('taking-lives-2004', ('grad', [(0, (60, 70, 50)), (.6, (20, 24, 16)), (1, (6, 6, 4))]), (230, 220, 190),
    T('TAKING LIVES', 'ter', 74, (232, 222, 192), track=.12, rough=.7),
    photo=ph(.6, .4, .45, 1.0), pb=(232, 222, 192), lg=WHT, lw=.6, order='LPTCF', credit=['ANGELINA JOLIE', 'ETHAN HAWKE'], ccol=(232, 222, 192),
    ft='a', vbox=(232, 222, 192), vink=(20, 24, 16), fcol=(190, 190, 170), fin=WORN, seed=2004)

# One Hour Photo (2002): a real rental, the photo lab's white, the navy rounded capitals (typeset), Sy and the negatives
std('one-hour-photo-2002', ('grad', [(0, (246, 246, 246)), (.6, (222, 222, 224)), (1, (160, 160, 170))]), (30, 50, 100),
    T('One Hour Photo', 'popm', 70, (30, 52, 104)),
    photo=ph(.58, .65, .4, 1.0), pb=(30, 52, 104), lg=(30, 52, 104), lw=.6, order='LPTCSF', credit=['ROBIN WILLIAMS'], ccol=(30, 52, 104),
    stick=RWD(), ft='a', vbox=(30, 52, 104), fcol=(30, 52, 104), fin=RENTAL, seed=2002)

# We Live in Public: black, the white rounded capitals (typeset), the wall of pods
std('we-live-in-public-2009', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), WHT,
    T('WE LIVE IN PUBLIC', 'popb', 60, WHT, track=.04),
    photo=ph(.5, .55, .8, .8), pb=(240, 130, 40), lg=WHT, lw=.6, order='LPTCF', credit=['AN ONDI TIMONER', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 130, 40), fcol=(200, 200, 204), fin=SLIP, seed=2009)

# Mike Tyson: Undisputed Truth: black, the white and red heavy capitals (typeset), the tattooed head
std('mike-tyson-undisputed-truth-2013', ('grad', [(0, (40, 40, 40)), (.6, (14, 14, 14)), (1, (4, 4, 4))]), WHT,
    TT([('MIKE TYSON', WHT), ('UNDISPUTED TRUTH', (214, 30, 30))], 'intbk', 60, sp=.25, squeeze=.84),
    photo=ph(.65, .25, .5, 1.0), pb=(214, 30, 30), lg=WHT, lw=.6, order='LPTCF', credit=['MIKE TYSON'], ccol=WHT,
    ft='a', vbox=(214, 30, 30), fcol=(200, 200, 200), fin=SLIP)

# Perfect Bid: the game show's navy, the yellow blocky capitals (typeset), Ted at his podium (no logo file: its company in type)
std('perfect-bid-the-contestant-who-knew-too-much-2017', ('grad', [(0, (30, 40, 120)), (.6, (14, 18, 60)), (1, (6, 8, 26))]), (250, 220, 40),
    [T('PERFECT BID', 'intbk', 80, (250, 222, 44), squeeze=.86), T('THE CONTESTANT WHO KNEW TOO MUCH', 'herb', 18, (250, 222, 44), track=.08)], tgap=8,
    photo=ph(.35, .33, .35, 1.0), pb=(250, 222, 44), studio=['FORTYFPS', 'PRODUCTIONS'], scol=(250, 222, 44), order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(250, 222, 44), vink=(14, 18, 60), fcol=(200, 206, 230), fin=MINT)

# McCabe & Mrs. Miller (1971): an old tape, Presbyterian Church mud and rain, cream circus-poster serif (typeset), McCabe in his fur coat
std('mccabe-mrs-miller-1971', ('grad', [(0, (150, 140, 120)), (.6, (90, 76, 60)), (1, (30, 24, 18))]), (240, 230, 210),
    T('McCABE & MRS. MILLER', 'ter', 66, (242, 232, 212), track=.04, outline=((60, 40, 30), 1.8)),
    photo=ph(.45, .2, .4, 1.0), pb=(242, 232, 212), lg=WHT, lw=.6, order='LPTCSF', credit=['WARREN BEATTY', 'JULIE CHRISTIE'], ccol=(242, 232, 212),
    stick=PRC(['$2.99', 'WESTERN']), ft='e', fcol=(230, 220, 200), fin=OLD, seed=1971)

# Miami Vice (2006): ocean-night blue, the white capitals reversed out of the blue box (typeset), Crockett in his shades
std('miami-vice-2006', ('grad', [(0, (40, 60, 110)), (.6, (16, 24, 50)), (1, (4, 6, 14))]), WHT,
    T('MIAMI VICE', 'her', 70, WHT, box=((40, 70, 170), 10, 6)),
    photo=ph(.3, .48, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['COLIN FARRELL', 'JAMIE FOXX'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 24, 50), fcol=(190, 200, 220), fin=WORN, seed=2006)

# Small Town Crime: the poster's off-white, red and blue stacked capitals (typeset), Mike in his suit
std('small-town-crime-2018', ('grad', [(0, (238, 236, 230)), (.6, (214, 210, 204)), (1, (150, 146, 140))]), (180, 40, 40),
    TT([('SMALL', (182, 42, 42)), ('TOWN', (182, 42, 42)), ('CRIME', (40, 80, 130))], 'hcnb', 84, sp=.25, squeeze=.8),
    photo=ph(.55, .12, .3, 1.0), pb=(182, 42, 42), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['JOHN HAWKES'], ccol=(30, 30, 30),
    ft='a', vbox=(182, 42, 42), fcol=(30, 30, 30), fin=MINT)

# Den of Thieves: LA steel blue, the red heavy capitals off the white band, Big Nick in his vest
std('den-of-thieves-2018', ('grad', [(0, (90, 110, 130)), (.6, (34, 42, 50)), (1, (10, 12, 14))]), (220, 30, 30),
    T('DEN OF THIEVES', 'hcnb', 84, (220, 30, 30), squeeze=.76, bold=1.0, box=(WHT, 10, 6)),  # typeset on its white band
    photo=ph(.6, .75, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['GERARD BUTLER'], ccol=WHT,
    ft='a', vbox=(220, 30, 30), fcol=(200, 206, 214), fin=MINT)

# The Bits of Yesterday: the retro-game neon on green, the magenta and pink capitals (typeset) (no logo file: its company in type)
std('the-bits-of-yesterday-2018', ('grad', [(0, (40, 160, 90)), (.5, (30, 60, 80)), (1, (20, 10, 40))]), (250, 60, 200),
    [T('THE BITS OF', 'intbki', 36, (250, 120, 220)), T('YESTERDAY', 'intbki', 84, (250, 60, 200), outline=((30, 10, 40), 1.8))], tgap=8,
    photo=ph(.5, .45, .5, 1.0), pb=(250, 60, 200), studio=['DREAM CASE', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(250, 60, 200), fcol=WHT, fin=MINT)

# The Equalizer 2: explosion amber and smoke, the yellow heavy capitals (typeset), McCall with his gun
std('the-equalizer-2-2018', ('grad', [(0, (230, 140, 40)), (.5, (110, 60, 20)), (1, (20, 14, 10))]), (250, 210, 40),
    TT([('THE', (250, 212, 44)), ('EQUALIZER 2', (250, 212, 44))], 'intbk', 80, sp=.25, squeeze=.84, outline=((40, 20, 10), 1.6)),
    photo=ph(.25, .14, .4, 1.0), pb=(250, 212, 44), lg=WHT, lw=.6, order='LPTCF', credit=['DENZEL', 'WASHINGTON'], ccol=(250, 212, 44),
    ft='a', vbox=(250, 212, 44), vink=(20, 14, 10), fcol=(230, 210, 190), fin=MINT)

# The Magnificent Seven (2016): the poster's blood-red splash, white heavy capitals (typeset), the seven walking
std('the-magnificent-seven-2016', ('grad', [(0, (200, 30, 30)), (.5, (120, 16, 16)), (1, (30, 6, 6))]), WHT,
    TT([('THE', WHT), ('MAGNIFICENT SEVEN', WHT)], 'intbk', 70, sp=.25, squeeze=.84),
    photo=ph(.5, .68, .9, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['DENZEL WASHINGTON', 'CHRIS PRATT'], ccol=WHT,
    ft='a', vbox=WHT, vink=(120, 16, 16), fcol=(236, 210, 206), fin=SLIP, seed=2016)

# Bound by Honor (1993): a 2-tape rental set, East LA red and black, the red slab BLOOD IN BLOOD OUT lettering for its US title (typeset), the three cousins
std('bound-by-honor-1993', ('grad', [(0, (160, 20, 20)), (.5, (60, 8, 8)), (1, (6, 2, 2))]), (226, 30, 30),
    [T('BOUND BY HONOR', 'bonb', 110, (244, 236, 220), track=.04, outline=((200, 30, 30), 2.4)), T('BLOOD IN BLOOD OUT', 'herb', 40, (244, 236, 220), track=.2)],
    photo=ph(.5, .15, .9, .6), pb=(230, 34, 34), lg=WHT, lw=.5, order='LPTCSF', tgap=10, credit=['A TAYLOR HACKFORD', 'FILM'], ccol=WHT,
    stick=flow(dot, 112, ['2-TAPE', 'SET'], (240, 230, 210), (60, 8, 8), d=104), ft='c', vbox=WHT, vink=(60, 8, 8), fcol=(220, 196, 196), fin=RENTAL, seed=1993,
    W=2 * w_for(115), notch_w=1.5 * w_for(115))  # 190 minutes: a 2-tape box

# The Act of Killing: the poster's magenta, the white heavy capitals, the giant fish and the dancers
std('the-act-of-killing-2012', ('grad', [(0, (180, 40, 120)), (.6, (110, 20, 80)), (1, (40, 8, 30))]), WHT,
    L([(0.04, 0.22, 0.98, 0.32), (0.3, 0.32, 0.98, 0.42)], 80, WHT, mode='light', speck=.01),
    photo=ph(.5, .8, .9, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 20, 80), fcol=(236, 210, 226), fin=SLIP)

# At the Heart of Gold: white, black and gold condensed capitals (typeset), the gymnast mid-air
std('at-the-heart-of-gold-inside-the-usa-gymnastics-scandal-2019', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (170, 160, 140))]), (20, 18, 16),
    [TT([('AT THE', (20, 18, 16)), ('HEART OF GOLD', (190, 160, 90))], 'hcnb', 70, sp=.25, squeeze=.8), T('INSIDE THE USA GYMNASTICS SCANDAL', 'hcnb', 22, (20, 18, 16), track=.1)], tgap=8,
    photo=ph(.4, .15, .5, 1.0), pb=(190, 160, 90), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(20, 18, 16),
    ft='a', vbox=(190, 160, 90), fcol=(20, 18, 16), fin=MINT)

# Camp Hollywood (2004): LA sky blue, the red heavy capitals (typeset), the motel pool (no logo file: its company in type)
std('camp-hollywood-2004', ('grad', [(0, (180, 214, 230)), (.6, (120, 170, 190)), (1, (40, 70, 60))]), (180, 30, 30),
    T('CAMP HOLLYWOOD', 'hcnb', 76, (182, 32, 32), squeeze=.8, bold=.8),
    photo=ph(.5, .82, .9, .6), pb=(182, 32, 32), studio=['INTERLOPER FILMS'], scol=(30, 40, 50), order='lPTCF', credit=['A DOCUMENTARY'], ccol=(30, 40, 50),
    ft='a', vbox=(182, 32, 32), fcol=(230, 236, 236), fin=SLIP, seed=2004)

# Parasite: the Parks' lawn green, white wide serif capitals (typeset: they run over the lawn), the house and the family
std('parasite-2019', ('grad', [(0, (60, 80, 70)), (.5, (70, 120, 50)), (1, (20, 40, 14))]), WHT,
    T('PARASITE', 'schb', 84, WHT, track=.06),
    photo=ph(.5, .3, .8, .8), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A BONG JOON HO', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(70, 120, 50), fcol=(220, 230, 214), fin=MINT, dotst=(['STAFF', 'PICK'], (230, 60, 40)))

# Once Upon a Time in America (1984): an old tape, the Manhattan Bridge in amber haze, black condensed capitals (typeset), the boys under the bridge
std('once-upon-a-time-in-america-1984', ('grad', [(0, (240, 220, 180)), (.5, (180, 130, 70)), (1, (50, 30, 14))]), (20, 16, 12),
    [T('ONCE UPON A TIME', 'hcnb', 44, (20, 16, 12), squeeze=.76), T('IN AMERICA', 'hcnb', 90, (20, 16, 12), squeeze=.74, bold=.6)], tgap=8,
    photo=ph(.5, .75, .6, 1.0), pb=(20, 16, 12), lg=(20, 16, 12), lw=.6, order='LPTCSF', credit=['ROBERT DE NIRO', 'JAMES WOODS'], ccol=(240, 220, 190),
    stick=BAR('15 01984', top='DRAMA', fill=(220, 214, 230), ink=(40, 30, 60)), ft='a', vbox=(240, 220, 190), vink=(50, 30, 14), fcol=(240, 220, 190), fin=OLD, seed=1984)

# Under the Skin: starfield black, teal spaced capitals (typeset), her face in the dark
std('under-the-skin-2014', ('grad', [(0, (20, 30, 50)), (.6, (6, 10, 18)), (1, (2, 2, 4))]), (90, 170, 190),
    T('UNDER THE SKIN', 'her', 56, (96, 176, 196), track=.2),
    photo=ph(.5, .25, .45, 1.0), pb=(96, 176, 196), lg=WHT, lw=.6, order='LPTCF', credit=['SCARLETT JOHANSSON'], ccol=(96, 176, 196),
    ft='a', vbox=(96, 176, 196), vink=(6, 10, 18), fcol=(160, 180, 196), fin=SLIP)

# A Separation (2011): Tehran dust brown, white heavy capitals (typeset), Simin
std('a-separation-2011', ('grad', [(0, (150, 120, 90)), (.6, (80, 60, 44)), (1, (26, 20, 14))]), WHT,
    T('A SEPARATION', 'herb', 70, WHT, track=.02),
    photo=ph(.4, .5, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AN ASGHAR FARHADI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 60, 44), fcol=(226, 216, 204), fin=SLIP)

# Marriage Story: the poster's cream, the black serif lower case, Charlie and Nicole
std('marriage-story-2019', ('solid', (240, 232, 216)), (20, 18, 16),
    L((0.03, 0.81, 0.97, 0.945), 80, (20, 18, 16), mode='dark', speck=.01),
    photo=ph(.5, .35, .6, 1.0), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['SCARLETT JOHANSSON', 'ADAM DRIVER'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=MINT)

# Dheepan: the estate's brick red, white heavy capitals (typeset), Dheepan on the roof's edge
std('dheepan-2015', ('grad', [(0, (210, 90, 80)), (.6, (150, 50, 44)), (1, (50, 16, 14))]), WHT,
    T('DHEEPAN', 'intbk', 100, WHT, squeeze=.86),
    photo=ph(.55, .65, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A JACQUES AUDIARD', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(150, 50, 44), fcol=(240, 220, 214), fin=SLIP)

# Apollo 11: launch-pad dusk, thin white capitals (typeset), the Saturn V on the pad
std('apollo-11-2019', ('grad', [(0, (60, 40, 60)), (.5, (130, 90, 110)), (1, (30, 20, 26))]), WHT,
    T('APOLLO 11', 'her', 90, WHT, track=.04),
    photo=ph(.45, .55, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 40, 60), fcol=(220, 210, 220), fin=MINT)

# Eyes Wide Shut (1999): a real rental, the poster's deep violet, the mint slab capitals, the kiss in the mirror
std('eyes-wide-shut-1999', ('grad', [(0, (80, 40, 90)), (.6, (44, 20, 50)), (1, (14, 6, 16))]), (160, 220, 190),
    L((0.03, 0.835, 0.97, 0.925), 84, (164, 222, 194), mode='key', key=(150, 210, 180), t=(70, 150), speck=.01),
    photo=ph(.5, .4, .5, 1.0), pb=(164, 222, 194), lg=WHT, lw=.6, order='LPTCSF', credit=['TOM CRUISE', 'NICOLE KIDMAN'], ccol=(164, 222, 194),
    stick=RWD(fill=(250, 240, 210)), ft='a', vbox=(164, 222, 194), vink=(44, 20, 50), fcol=(210, 200, 214), fin=RENTAL, seed=1999)

# Love Actually (2003): the poster's white and the red ribbon, red love and black actually (typeset), the faces
std('love-actually-2003', ('grad', [(0, (250, 248, 246)), (.6, (236, 232, 228)), (1, (190, 180, 176))]), (210, 30, 30),
    TT([('love', (214, 30, 30)), ('actually', (30, 28, 28))], 'popb', 92, sp=0),
    photo=ph(.3, .12, .5, 1.0), pb=(214, 30, 30), lg=(30, 28, 28), lw=.6, order='LPTCF', credit=['HUGH GRANT', 'LIAM NEESON'], ccol=(30, 28, 28),
    ft='a', vbox=(214, 30, 30), fcol=(30, 28, 28), fin=WORN, seed=2003, over=[dot(262, ['HOLIDAY'], (40, 120, 60), x=.72, d=62)])

# The Celebration (1998): a Dogme tape, white, the black spaced serif capitals, the family at the party
std('the-celebration-1998', ('solid', (244, 242, 238)), (20, 18, 16),
    [T('THE', 'ter', 26, (20, 18, 16), track=.3), L((0.07, 0.12, 0.93, 0.195), 70, (20, 18, 16), mode='dark', speck=.01)], tgap=8,
    photo=ph(.5, .55, .8, .8), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['A THOMAS VINTERBERG', 'FILM'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=WORN, seed=1998)

# Klaus: Smeerensburg's snowy night blue, an orange script like the poster's (typeset: small on the poster), Klaus himself
std('klaus-2019', ('grad', [(0, (40, 60, 90)), (.6, (20, 30, 50)), (1, (8, 12, 20))]), (240, 140, 50),
    T('Klaus', 'cho', 130, (244, 146, 56), shadow=((10, 14, 24), 3, 3)),
    photo=ph(.4, .78, .4, 1.0), pb=(244, 146, 56), lg=WHT, lw=.6, order='LPTCF', credit=['JASON SCHWARTZMAN', 'J.K. SIMMONS'], ccol=WHT,
    ft='a', vbox=(244, 146, 56), vink=(20, 30, 50), fcol=(200, 210, 224), fin=MINT)

# 48 Hrs. (1982): a real rental, San Francisco night, the red digital-clock capitals (typeset), Reggie and Jack
std('48-hrs-1982', ('grad', [(0, (30, 30, 60)), (.6, (12, 12, 26)), (1, (4, 4, 8))]), (240, 40, 50),
    T('48 HRS.', 'intbki', 110, (244, 44, 54), soft=((240, 40, 60), 6, .6)),
    photo=ph(.5, .45, .8, .8), pb=(244, 44, 54), lg=WHT, lw=.6, order='LPTCSF', credit=['NICK NOLTE', 'EDDIE MURPHY'], ccol=WHT,
    stick=PRC(['$0.99', 'ACTION']), ft='a', vbox=(244, 44, 54), vink=(12, 12, 26), fcol=(190, 196, 220), fin=RENTAL, seed=1982)

# Hustlers: club-light violet, the pink neon capitals (typeset), Destiny at the head
std('hustlers-2019', ('grad', [(0, (60, 30, 110)), (.6, (26, 12, 50)), (1, (8, 4, 16))]), (250, 120, 220),
    T('HUSTLERS', 'adv', 96, (252, 160, 236), track=.1, soft=((240, 60, 200), 8, .8)),
    photo=ph(.17, .09, .3, 1.0), pb=(252, 160, 236), lg=WHT, lw=.6, order='LPTCF', credit=['CONSTANCE WU', 'JENNIFER LOPEZ'], ccol=(252, 160, 236),
    ft='a', vbox=(252, 160, 236), vink=(26, 12, 50), fcol=(210, 196, 230), fin=MINT)

# Joker: the Bronx stairs' dun and shadow, the white distressed capitals, Arthur dancing
std('joker-2019', ('grad', [(0, (150, 140, 110)), (.5, (70, 60, 44)), (1, (20, 16, 12))]), WHT,
    L((0.31, 0.79, 0.69, 0.93), 110, WHT, mode='light', speck=.01),
    photo=ph(.45, .5, .5, 1.0), pb=(210, 40, 30), lg=WHT, lw=.6, order='LPTCF', credit=['JOAQUIN PHOENIX'], ccol=WHT,
    ft='a', vbox=(210, 40, 30), fcol=(220, 210, 196), fin=SLIP)

# Shirkers: the poster's pink-to-violet sky, the white stencil capitals (typeset), Sandi on the scooter
std('shirkers-2018', ('grad', [(0, (240, 110, 210)), (.5, (150, 100, 230)), (1, (40, 50, 160))]), WHT,
    T('SHIRKERS', 'adv', 92, WHT, track=.1, outline=((60, 30, 90), 1.6)),
    photo=ph(.5, .42, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A SANDI TAN', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 50, 160), fcol=WHT, fin=MINT)

# True Grit (2010): weathered barn-board brown, the white outlined slab capitals (typeset), Rooster with his eye patch
std('true-grit-2010', ('grad', [(0, (110, 90, 70)), (.6, (50, 40, 30)), (1, (14, 10, 8))]), WHT,
    T('TRUE GRIT', 'schb', 92, WHT, track=.04, outline=((30, 24, 18), 2.2), shadow=((10, 8, 6), 3, 3)),
    photo=ph(.3, .17, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JEFF BRIDGES', 'MATT DAMON'], ccol=WHT,
    ft='a', vbox=WHT, vink=(50, 40, 30), fcol=(220, 210, 196), fin=SLIP, seed=2010)

# Inside Llewyn Davis: Greenwich Village winter grey, the teal condensed capitals (typeset), Llewyn with the cat
std('inside-llewyn-davis-2013', ('grad', [(0, (220, 220, 214)), (.6, (180, 180, 174)), (1, (110, 110, 104))]), (40, 100, 110),
    [T('INSIDE', 'hcnb', 44, (40, 102, 112), squeeze=.8, track=.06), T('LLEWYN DAVIS', 'hcnb', 80, (40, 102, 112), squeeze=.76, bold=.4)], tgap=8,
    photo=ph(.5, .5, .4, 1.0), pb=(40, 102, 112), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(30, 30, 30),
    ft='a', vbox=(40, 102, 112), fcol=(30, 30, 30), fin=SLIP, dotst=(['FOLK'], (40, 102, 112)))

# Toy Story 4: a Pixar clamshell.  Carnival-night blue; the poster's logo taken apart and laid along the spine (TOY, the red STORY plate, the 4) like Toy Story 5's; Woody in the diamond
disney('toy-story-4-2019', ('strip', dict(x0=.0, blur=14, wash=((36, 90, 200), .6))), fin=dict(CLAM, vivid=.3),
       title=LC([(0.3, 0.11, 0.68, 0.225), (0.32, 0.21, 0.66, 0.29), (0.37, 0.28, 0.58, 0.39)], 170, gapf=.05,
          cuts=[ts_letters, ts_plate(.30, .68), ts_letters]),
       face=ph(.5, .47, .19, 1.4))

# Cinemania (2003): black, the red neon cine and yellow MANIA (typeset), Jack outside Film Forum
std('cinemania-2003', ('grad', [(0, (40, 36, 34)), (.6, (14, 12, 12)), (1, (4, 4, 4))]), (230, 60, 40),
    TT([('cine', (232, 64, 44)), ('MANIA', (246, 230, 60))], 'popb', 100, sp=0),
    photo=ph(.5, .3, .6, 1.0), pb=(246, 230, 60), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(232, 64, 44), fcol=(200, 196, 190), fin=WORN, seed=2003)


# =====================================================================================
# the 2020 shelf (films-2020.json).  Same approach as 2019 and 2021; most titles typeset this time
# (each comment says where a title was lifted off the poster instead).  Credits and typed labels
# checked on IMDb (17 Nov 2026).  Six long films are 2-tape boxes (185 minutes and over).
# =====================================================================================
TWO = dict(W=2 * w_for(115), notch_w=1.5 * w_for(115))
TWOST = lambda fill, ink: flow(dot, 112, ['2-TAPE', 'SET'], fill, ink, d=104)

# Last Year at Marienbad (1961): an old art-house tape, the hotel's silvered greys, the black engraved capitals on their white panel (typeset), the garden
std('last-year-at-marienbad-1961', ('grad', [(0, (160, 160, 158)), (.6, (80, 80, 78)), (1, (20, 20, 20))]), (20, 20, 20),
    T('LAST YEAR AT MARIENBAD', 'schb', 54, (20, 20, 20), track=.04, box=((244, 242, 236), 10, 6)),
    photo=ph(.5, .6, .5, 1.0), pb=(244, 242, 236), lg=WHT, lw=.6, order='LPTCF', credit=['AN ALAIN RESNAIS', 'FILM'], ccol=WHT,
    ft='e', fcol=(230, 230, 226), fin=OLD, seed=1961)

# Pain and Glory: Almodóvar's red, white condensed capitals (typeset), Salvador in profile
std('pain-and-glory-2019', ('grad', [(0, (214, 30, 30)), (.6, (150, 16, 18)), (1, (50, 6, 6))]), WHT,
    T('PAIN & GLORY', 'hcnb', 92, WHT, squeeze=.74, bold=.6),
    photo=ph(.3, .6, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['ANTONIO BANDERAS'], ccol=WHT,
    ft='a', vbox=WHT, vink=(150, 16, 18), fcol=(250, 220, 220), fin=MINT)

# Blue Collar (1978): an old tape, factory white, the navy heavy serif (typeset), the three of them in the car-press
std('blue-collar-1978', ('grad', [(0, (244, 242, 238)), (.6, (222, 220, 214)), (1, (160, 156, 150))]), (30, 40, 140),
    T('BLUE COLLAR', 'schb', 80, (30, 40, 140), track=.02),
    photo=ph(.5, .3, .45, 1.0), pb=(30, 40, 140), lg=(30, 40, 140), lw=.6, order='LPTCSF', credit=['RICHARD PRYOR', 'HARVEY KEITEL'], ccol=(30, 40, 140),
    stick=BAR('15 01978', top='DRAMA', fill=(250, 230, 200), ink=(80, 40, 20)), ft='e', fcol=(30, 40, 140), fin=OLD, seed=1978)

# The Bridge on the River Kwai (1957): an old tape, jungle green, the khaki heavy capitals (typeset), Nicholson and Shears (no logo file: the studio in type)
std('the-bridge-on-the-river-kwai-1957', ('grad', [(0, (60, 70, 50)), (.6, (26, 30, 20)), (1, (8, 10, 6))]), (200, 180, 110),
    [T('THE BRIDGE ON THE', 'intbk', 36, (214, 194, 124), squeeze=.86), T('RIVER KWAI', 'intbk', 84, (214, 194, 124), squeeze=.84)], tgap=8,
    photo=ph(.5, .6, .45, 1.0), pb=(214, 194, 124), studio=['COLUMBIA PICTURES'], scol=(220, 210, 180), order='lPTCF', credit=['WILLIAM HOLDEN', 'ALEC GUINNESS'], ccol=(220, 210, 180),
    ft='e', fcol=(220, 210, 180), fin=OLD, seed=1957)

# Bad Lieutenant (1992): a real rental, the poster's mustard yellow, the red heavy BAD and the small LIEUTENANT (typeset), the gun at you
std('bad-lieutenant-1992', ('grad', [(0, (230, 190, 60)), (.6, (190, 140, 30)), (1, (80, 50, 10))]), (180, 30, 30),
    TT([('BAD', (182, 30, 30)), ('LIEUTENANT', (182, 30, 30))], 'intbk', 84, sp=.25, squeeze=.86),
    photo=ph(.6, .55, .45, 1.0), pb=(182, 30, 30), lg=(30, 20, 10), lw=.6, order='LPTCSF', credit=['HARVEY KEITEL'], ccol=(30, 20, 10),
    stick=PRC(['$1.99', 'CRIME']), ft='a', vbox=(182, 30, 30), fcol=(30, 20, 10), fin=RENTAL, seed=1992)

# Once Upon a Time in Hollywood: the painted poster's orange sunset, yellow and white capitals (typeset), Cliff, Rick and Sharon
std('once-upon-a-time-in-hollywood-2019', ('grad', [(0, (240, 140, 50)), (.5, (200, 70, 30)), (1, (60, 20, 10))]), (250, 220, 60),
    TT([('ONCE UPON A TIME IN...', (250, 222, 64)), ('HOLLYWOOD', WHT)], 'hcnb', 70, sp=.25, squeeze=.8, outline=((60, 20, 10), 1.6)),
    photo=ph(.5, .15, .8, .6), pb=(250, 222, 64), lg=WHT, lw=.6, order='LPTCF', credit=['LEONARDO DiCAPRIO', 'BRAD PITT'], ccol=WHT,
    ft='a', vbox=(250, 222, 64), vink=(60, 20, 10), fcol=(250, 220, 200), fin=SLIP)

# Harlem Nights (1989): a real rental, the club's red, the red and white art-deco capitals (typeset), Quick in his hat
std('harlem-nights-1989', ('grad', [(0, (120, 20, 26)), (.6, (50, 8, 10)), (1, (10, 4, 4))]), WHT,
    TT([('HARLEM', (230, 60, 60)), ('NIGHTS', WHT)], 'adv', 84, sp=.25, track=.04, bold=.5),
    photo=ph(.6, .55, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['EDDIE MURPHY', 'RICHARD PRYOR'], ccol=WHT,
    stick=RWD(), ft='a', vbox=WHT, vink=(50, 8, 10), fcol=(230, 200, 200), fin=RENTAL, seed=1989)

# The Two Popes: the Vatican garden's green, the white condensed capitals, the two at their table
std('the-two-popes-2019', ('grad', [(0, (120, 130, 90)), (.6, (60, 70, 40)), (1, (20, 24, 12))]), WHT,
    L((0.1, 0.42, 0.9, 0.5), 90, WHT, mode='light', speck=.01),
    photo=ph(.5, .8, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['ANTHONY HOPKINS', 'JONATHAN PRYCE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 70, 40), fcol=(220, 226, 210), fin=MINT)

# The Asphalt Jungle (1950): an old tape, black, the yellow brush capitals (typeset), Angela on the sofa
std('the-asphalt-jungle-1950', ('grad', [(0, (40, 36, 30)), (.6, (14, 12, 10)), (1, (4, 4, 4))]), (246, 220, 40),
    T('THE ASPHALT JUNGLE', 'bonb', 70, (248, 222, 44), rough=.6),
    photo=ph(.3, .7, .4, 1.0), pb=(220, 40, 120), lg=WHT, lw=.6, order='LPTCF', credit=['A JOHN HUSTON', 'PICTURE'], ccol=(248, 222, 44),
    ft='e', fcol=(220, 214, 200), fin=OLD, seed=1950)

# To Catch a Thief (1955): an old tape, the Riviera teal, white capitals (typeset), John and Frances
std('to-catch-a-thief-1955', ('grad', [(0, (40, 120, 130)), (.6, (16, 60, 66)), (1, (4, 20, 22))]), WHT,
    [T("ALFRED HITCHCOCK'S", 'herb', 22, (250, 220, 60), track=.12), T('TO CATCH A THIEF', 'herb', 64, WHT, track=.02)], tgap=8,
    photo=ph(.25, .3, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['CARY GRANT', 'GRACE KELLY'], ccol=WHT,
    stick=PRC(['$2.99', 'CLASSIC']), ft='e', fcol=(220, 230, 230), fin=OLD, seed=1955)

# The Bank Job (2008): London-vault blue, the white condensed capitals (typeset), Terry at the head
std('the-bank-job-2008', ('grad', [(0, (80, 110, 140)), (.6, (30, 40, 56)), (1, (8, 12, 16))]), WHT,
    T('THE BANK JOB', 'hcnb', 92, WHT, squeeze=.7, bold=.6),
    photo=ph(.25, .15, .35, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JASON STATHAM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(30, 40, 56), fcol=(200, 210, 220), fin=SLIP, seed=2008)

# Dunkirk: the beach's steel grey and smoke, white spaced capitals (typeset), the soldier on the mole
std('dunkirk-2017', ('grad', [(0, (140, 150, 156)), (.6, (60, 66, 72)), (1, (16, 18, 20))]), WHT,
    T('DUNKIRK', 'her', 80, WHT, track=.45),
    photo=ph(.6, .45, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A CHRISTOPHER NOLAN', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 66, 72), fcol=(210, 214, 218), fin=SLIP)

# Alanis: the room's red light, white condensed capitals (typeset), Alanis on the bed
std('alanis-2017', ('grad', [(0, (200, 70, 80)), (.6, (120, 30, 40)), (1, (30, 8, 10))]), WHT,
    T('ALANIS', 'hcnb', 110, WHT, squeeze=.7, bold=.4),
    photo=ph(.45, .15, .35, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AN ANAHÍ BERNERI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(120, 30, 40), fcol=(240, 210, 214), fin=MINT)

# Notting Hill (1999): a real rental, the poster's white, navy and blue serif (typeset), Anna's face
std('notting-hill-1999', ('grad', [(0, (246, 246, 248)), (.6, (226, 228, 234)), (1, (170, 174, 186))]), (30, 40, 110),
    TT([('Notting', (30, 40, 110)), ('Hill', (40, 90, 190))], 'schb', 84, sp=.2),
    photo=ph(.45, .4, .5, 1.0), pb=(30, 40, 110), lg=(30, 40, 110), lw=.6, order='LPTCF', credit=['JULIA ROBERTS', 'HUGH GRANT'], ccol=(30, 40, 110),
    ft='a', vbox=(30, 40, 110), fcol=(30, 40, 110), fin=RENTAL, seed=1999, over=[dot(262, ['ROM', 'COM'], (220, 60, 90), x=.72, d=62)])

# Hearts and Minds (1974): an old tape, the poster's paper white, red HEARTS and black & MINDS (typeset), the woodcut (no logo file: its company in type)
std('hearts-and-minds-1974', ('grad', [(0, (238, 232, 222)), (.6, (220, 212, 198)), (1, (150, 140, 124))]), (20, 18, 16),
    TT([('HEARTS', (200, 40, 34)), ('& MINDS', (20, 18, 16))], 'ter', 80, sp=.2),
    photo=ph(.5, .55, .6, 1.0), pb=(20, 18, 16), studio=['BBS PRODUCTIONS'], scol=(20, 18, 16), order='lPTCF', credit=['A DOCUMENTARY'], ccol=(20, 18, 16),
    ft='e', fcol=(20, 18, 16), fin=OLD, seed=1974)

# The Barkley Marathons: forest dark with the poster's yellow border, the yellow heavy capitals (typeset), Laz at the gate (no company to name: left off)
std('the-barkley-marathons-the-race-that-eats-its-young-2014', ('grad', [(0, (60, 70, 40)), (.6, (24, 28, 16)), (1, (8, 10, 6))]), (240, 220, 40),
    [T('THE BARKLEY MARATHONS', 'intbk', 54, (242, 222, 44), squeeze=.84), T('THE RACE THAT EATS ITS YOUNG', 'herb', 20, (242, 222, 44), track=.08)], tgap=8,
    photo=ph(.8, .5, .3, 1.0), pb=(242, 222, 44), order='PTCF', credit=['A DOCUMENTARY'], ccol=(242, 222, 44),
    ft='a', vbox=(242, 222, 44), vink=(24, 28, 16), fcol=(200, 206, 190), fin=SLIP, under=[frame((242, 222, 44), 8, 1.6)])

# The Lighthouse: storm grey, white serif spaced capitals (typeset), Ephraim at the head
std('the-lighthouse-2019', ('grad', [(0, (120, 120, 120)), (.6, (50, 50, 50)), (1, (10, 10, 10))]), WHT,
    [T('THE', 'ter', 30, WHT, track=.3), T('LIGHTHOUSE', 'ter', 80, WHT, track=.12)], tgap=8,
    photo=ph(.84, .45, .3, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['ROBERT PATTINSON', 'WILLEM DAFOE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(50, 50, 50), fcol=(200, 200, 200), fin=MINT)

# Abducted in Plain Sight: the poster's red halftone, black slab capitals (typeset), Jan as a girl (no logo file: the label in type)
std('abducted-in-plain-sight-2017', ('grad', [(0, (230, 60, 50)), (.6, (190, 30, 30)), (1, (80, 10, 10))]), (20, 16, 16),
    [T('ABDUCTED', 'bonb', 90, (20, 16, 16)), T('IN PLAIN SIGHT', 'bonb', 40, (20, 16, 16), track=.06)], tgap=8,
    photo=ph(.5, .55, .6, 1.0), pb=WHT, studio=['NETFLIX'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(190, 30, 30), fcol=WHT, fin=MINT)

# The Good Liar: the poster's black and white, the red condensed capitals (typeset), Betty and Roy
std('the-good-liar-2019', ('grad', [(0, (60, 60, 60)), (.6, (22, 22, 22)), (1, (6, 6, 6))]), (180, 30, 34),
    T('THE GOOD LIAR', 'hcnb', 94, (190, 34, 38), squeeze=.72, bold=.8),
    photo=ph(.62, .22, .45, 1.0), pb=(190, 34, 38), lg=WHT, lw=.6, order='LPTCF', credit=['HELEN MIRREN', 'IAN McKELLEN'], ccol=WHT,
    ft='a', vbox=(190, 34, 38), fcol=(200, 200, 200), fin=MINT)

# Uncut Gems: black, the white condensed capitals (typeset), Howard with his rings
std('uncut-gems-2019', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), WHT,
    T('Uncut Gems', 'hcnb', 100, WHT, squeeze=.8, bold=.6),
    photo=ph(.5, .66, .35, 1.0), pb=(90, 200, 170), lg=WHT, lw=.6, order='LPTCF', credit=['ADAM SANDLER'], ccol=WHT,
    ft='a', vbox=(90, 200, 170), vink=(14, 14, 16), fcol=(190, 190, 196), fin=MINT, dotst=(['STAFF', 'PICK'], (90, 200, 170), (14, 14, 16)))

# Ford v Ferrari: Le Mans morning grey, blue FORD and red FERRARI (typeset), the GT40
std('ford-v-ferrari-2019', ('grad', [(0, (226, 228, 230)), (.6, (190, 194, 200)), (1, (90, 96, 106))]), (30, 30, 34),
    TT([('FORD', (60, 120, 210)), ('v', (30, 30, 34)), ('FERRARI', (210, 40, 40))], 'hcnb', 92, sp=.2, squeeze=.8, bold=.6),
    photo=ph(.5, .85, .8, .6), pb=(30, 30, 34), lg=(30, 30, 34), lw=.6, order='LPTCF', credit=['MATT DAMON', 'CHRISTIAN BALE'], ccol=(30, 30, 34),
    ft='a', vbox=(210, 40, 40), fcol=(30, 30, 34), fin=MINT)

# Jojo Rabbit: the poster's red, the white condensed capitals on the black band (typeset), Jojo in his cap
std('jojo-rabbit-2019', ('grad', [(0, (220, 40, 40)), (.6, (160, 20, 24)), (1, (50, 8, 8))]), WHT,
    T('JOJO RABBIT', 'hcnb', 90, WHT, squeeze=.74, bold=.6, box=((20, 18, 18), 10, 6)),
    photo=ph(.51, .26, .3, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A TAIKA WAITITI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(160, 20, 24), fcol=(250, 220, 220), fin=MINT)

# Won't You Be My Neighbor?: the poster's sky blue, white rounded capitals (typeset), Fred in his red cardigan
std('won-t-you-be-my-neighbor-2018', ('grad', [(0, (40, 110, 210)), (.6, (20, 60, 150)), (1, (8, 20, 60))]), WHT,
    [T("WON'T YOU BE MY", 'popb', 40, WHT), T('NEIGHBOR?', 'popb', 80, WHT)], tgap=8,
    photo=ph(.72, .33, .35, 1.0), pb=(220, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(220, 40, 40), fcol=(210, 220, 240), fin=MINT)

# A Rainy Day in New York: the umbrella's red on grey, white serif (typeset), the kiss under the umbrella (no logo file: its company in type)
std('a-rainy-day-in-new-york-2019', ('grad', [(0, (210, 50, 50)), (.6, (150, 30, 30)), (1, (60, 60, 64))]), WHT,
    T('A Rainy Day in New York', 'ter', 66, WHT),
    photo=ph(.65, .25, .5, 1.0), pb=WHT, studio=['GRAVIER', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['TIMOTHÉE CHALAMET', 'ELLE FANNING'], ccol=WHT,
    ft='a', vbox=WHT, vink=(150, 30, 30), fcol=(230, 220, 220), fin=MINT)

# Little Women: Concord's dusk green, white spaced capitals (typeset), the March sisters at the window
std('little-women-2019', ('grad', [(0, (60, 90, 80)), (.6, (24, 36, 32)), (1, (8, 12, 10))]), WHT,
    T('LITTLE WOMEN', 'her', 70, WHT, track=.2),
    photo=ph(.5, .15, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['SAOIRSE RONAN', 'EMMA WATSON'], ccol=WHT,
    ft='a', vbox=WHT, vink=(24, 36, 32), fcol=(210, 220, 214), fin=MINT)

# Richard Jewell: the press scrum's grey, the black serif capitals (typeset), Richard in the crowd
std('richard-jewell-2019', ('grad', [(0, (226, 226, 224)), (.6, (170, 170, 168)), (1, (60, 60, 58))]), (20, 20, 20),
    T('RICHARD JEWELL', 'ter', 76, (20, 20, 20), track=.04),  # typeset: the lift clipped the letters
    photo=ph(.35, .55, .45, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['A CLINT EASTWOOD', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 20, 20), fcol=WHT, fin=MINT)

# Sincerely Louis C.K.: the club's black, white chalk handwriting (typeset), Louis on the stage (a stand-up special, said in type)
std('sincerely-louis-c-k-2020', ('grad', [(0, (40, 40, 40)), (.6, (14, 14, 14)), (1, (4, 4, 4))]), WHT,
    T('Sincerely Louis C.K.', 'cho', 84, (236, 236, 232)),
    photo=ph(.5, .6, .5, 1.0), pb=WHT, studio=['STAND-UP SPECIAL'], scol=WHT, order='lPTF',
    ft='a', vbox=WHT, vink=(14, 14, 14), fcol=(190, 190, 190), fin=MINT)

# Murmur of the Heart (1971): an old art-house tape, aubergine black, cream serif capitals (typeset), Laurent with the cigar (no logo file: its company in type)
std('murmur-of-the-heart-1971', ('grad', [(0, (60, 30, 40)), (.6, (30, 14, 20)), (1, (10, 4, 6))]), (232, 214, 160),
    T('MURMUR OF THE HEART', 'ter', 62, (234, 216, 164), track=.06),
    photo=ph(.5, .18, .45, 1.0), pb=(234, 216, 164), studio=['NOUVELLES ÉDITIONS', 'DE FILMS'], scol=(234, 216, 164), order='lPTCSF', credit=['A LOUIS MALLE', 'FILM'], ccol=(234, 216, 164),
    stick=flow(dot, 70, ['FOREIGN'], (60, 120, 70), d=60), ft='e', fcol=(220, 206, 170), fin=OLD, seed=1971)

# Knives Out: Harlan's library brown, the yellow serif lettering (typeset), the family round the chair
std('knives-out-2019', ('grad', [(0, (90, 60, 40)), (.6, (40, 24, 16)), (1, (12, 6, 4))]), (246, 210, 30),
    T('Knives Out', 'pagb', 110, (248, 212, 34)),  # typeset: the lift broke on the bookshelves
    photo=ph(.5, .62, .9, .6), pb=(248, 212, 34), lg=WHT, lw=.6, order='LPTCF', credit=['A RIAN JOHNSON', 'FILM'], ccol=(248, 212, 34),
    ft='a', vbox=(248, 212, 34), vink=(40, 24, 16), fcol=(220, 200, 180), fin=MINT)

# Bad Boys for Life: Miami sunset and the Porsche, chrome-white capitals (typeset), Mike and Marcus
std('bad-boys-for-life-2020', ('grad', [(0, (240, 150, 60)), (.5, (130, 60, 70)), (1, (30, 20, 40))]), WHT,
    [T('BAD BOYS', 'intbk', 86, WHT, squeeze=.82, grad=[(0, (255, 255, 255)), (.5, (180, 186, 200)), (1, (240, 240, 246))], outline=((20, 20, 30), 1.8)), T('FOR LIFE', 'intbk', 34, WHT, track=.12)], tgap=8,
    photo=ph(.5, .1, .8, .6), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['WILL SMITH', 'MARTIN LAWRENCE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(130, 60, 70), fcol=WHT, fin=MINT)

# Waking Ned (1998): a real rental, the poster's sunny cream and green, the green serif lower case of its Waking Ned Devine (typeset), the old men on the hill
std('waking-ned-1998', ('grad', [(0, (240, 226, 180)), (.6, (210, 200, 150)), (1, (90, 110, 50))]), (60, 110, 40),
    T('waking Ned Devine', 'ter', 74, (60, 110, 40)),
    photo=ph(.5, .8, .8, .6), pb=(60, 110, 40), lg=(40, 50, 30), lw=.6, order='LPTCSF', credit=['IAN BANNEN', 'DAVID KELLY'], ccol=(40, 50, 30),
    stick=PRC(['$1.99', 'COMEDY']), ft='a', vbox=(60, 110, 40), fcol=(240, 236, 220), fin=RENTAL, seed=1998)

# The Gentlemen: white, the gold spaced serif capitals (typeset), the gang
std('the-gentlemen-2020', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (150, 140, 120))]), (150, 120, 40),
    [T('THE', 'ter', 30, (152, 122, 42), track=.4), T('GENTLEMEN', 'terb', 70, (152, 122, 42), track=.2)], tgap=8,
    photo=ph(.5, .6, .8, .8), pb=(152, 122, 42), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A GUY RITCHIE', 'FILM'], ccol=(30, 30, 30),
    ft='a', vbox=(152, 122, 42), fcol=(30, 30, 30), fin=MINT)

# The Last Dance: arena-floor white, the black spaced condensed capitals with the red rule (typeset), the Bulls walking out
std('the-last-dance-2020', ('grad', [(0, (244, 244, 244)), (.6, (210, 210, 210)), (1, (120, 120, 120))]), (20, 20, 20),
    T('THE LAST DANCE', 'hcnb', 70, (20, 20, 20), squeeze=.86, track=.14),
    photo=ph(.5, .62, .8, .6), pb=(206, 30, 40), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(206, 30, 40),
    ft='a', vbox=(206, 30, 40), fcol=WHT, fin=MINT)

# Jasper Mall: mall-ceiling white, the teal serif with the pink stripes (typeset), the walkers by the flag
std('jasper-mall-2020', ('grad', [(0, (240, 240, 236)), (.6, (210, 214, 214)), (1, (120, 130, 130))]), (30, 150, 170),
    T('Jasper Mall', 'schb', 80, (30, 152, 172)),
    photo=ph(.5, .75, .8, .6), pb=(220, 100, 180), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 152, 172), fcol=WHT, fin=MINT)

# Palm Springs: the pool's turquoise and desert sky, the pink neon script (typeset), Nyles and Sarah on their floats
std('palm-springs-2020', ('grad', [(0, (120, 200, 230)), (.5, (40, 190, 200)), (1, (10, 90, 110))]), (250, 120, 210),
    T('Palm Springs', 'cho', 100, (252, 150, 226), soft=((240, 60, 200), 7, .7)),
    photo=ph(.5, .72, .8, .6), pb=(252, 150, 226), lg=WHT, lw=.6, order='LPTCF', credit=['ANDY SAMBERG', 'CRISTIN MILIOTI'], ccol=WHT,
    ft='a', vbox=(252, 150, 226), vink=(10, 90, 110), fcol=WHT, fin=MINT)

# sex, lies, and videotape (1989): a real rental, black, the white rounded lower case (typeset), Graham's eyes
std('sex-lies-and-videotape-1989', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), WHT,
    T('sex, lies, and videotape', 'popb', 60, WHT),
    photo=ph(.5, .36, .9, .35), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A STEVEN SODERBERGH', 'FILM'], ccol=WHT,
    stick=BAR('15 01989', top='DRAMA', fill=(200, 230, 200), ink=(30, 60, 30)), ft='a', vbox=WHT, vink=(14, 14, 16), fcol=(190, 190, 196), fin=RENTAL, seed=1989)

# The Weight of Gold: black, white heavy stacked capitals (typeset), Michael's face
std('the-weight-of-gold-2020', ('grad', [(0, (50, 50, 50)), (.6, (18, 18, 18)), (1, (4, 4, 4))]), WHT,
    T('THE WEIGHT OF GOLD', 'hcnb', 76, WHT, squeeze=.76, bold=1.0),
    photo=ph(.65, .3, .45, 1.0), pb=(214, 180, 90), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(214, 180, 90),
    ft='a', vbox=(214, 180, 90), vink=(18, 18, 18), fcol=(190, 190, 190), fin=MINT)

# The Count of Monte Cristo (2002): Château d'If torch-red, the white script and caps (typeset), Edmond and Mercédès
std('the-count-of-monte-cristo-2002', ('grad', [(0, (170, 50, 20)), (.6, (70, 20, 8)), (1, (10, 4, 2))]), WHT,
    [T('The Count of', 'ter', 32, WHT, track=.1), T('Monte Cristo', 'cho', 96, WHT)], tgap=6,
    photo=ph(.55, .45, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JIM CAVIEZEL', 'GUY PEARCE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(70, 20, 8), fcol=(230, 200, 190), fin=WORN, seed=2002)

# Unbelievable: the poster's mist teal, white spaced condensed capitals (typeset), Marie in her red jacket
std('unbelievable-2019', ('grad', [(0, (150, 180, 180)), (.6, (90, 110, 110)), (1, (40, 30, 26))]), WHT,
    T('UNBELIEVABLE', 'hcnb', 70, WHT, squeeze=.8, track=.3),
    photo=ph(.4, .6, .45, 1.0), pb=(200, 60, 40), lg=WHT, lw=.6, order='LPTCF', credit=['KAITLYN DEVER', 'TONI COLLETTE'], ccol=WHT,
    ft='a', vbox=(200, 60, 40), fcol=WHT, fin=MINT)

# Defending Jacob: dim kitchen green-black, white spaced capitals with the bold JACOB (typeset), Jacob between his parents
std('defending-jacob-2020', ('grad', [(0, (60, 70, 60)), (.6, (22, 26, 22)), (1, (6, 8, 6))]), WHT,
    TT([('DEFENDING', (220, 220, 214)), ('JACOB', WHT)], 'her', 62, sp=.3, track=.25),
    photo=ph(.6, .35, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS EVANS', 'MICHELLE DOCKERY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(22, 26, 22), fcol=(190, 196, 190), fin=MINT)

# The Irishman: a 2-tape box (209 minutes), slate blue-grey, the red serif capitals (typeset), Frank, Russell and Jimmy
std('the-irishman-2019', ('grad', [(0, (70, 80, 90)), (.6, (30, 34, 40)), (1, (8, 10, 12))]), (200, 30, 30),
    [T('THE', 'terb', 50, (214, 40, 40), track=.2), T('IRISHMAN', 'terb', 150, (214, 40, 40), track=.04)],
    photo=ph(.55, .42, .6, .5), pb=(204, 34, 34), lg=WHT, lw=.5, order='LPTCSF', tgap=10, credit=['A MARTIN SCORSESE', 'PICTURE'], ccol=WHT,
    stick=TWOST((204, 34, 34), WHT), ft='c', vbox=WHT, vink=(30, 34, 40), fcol=(200, 206, 214), fin=MINT, **TWO)

# El Camino: A Breaking Bad Movie: the poster's red, white condensed capitals in the keyline box (typeset), Jesse
std('el-camino-a-breaking-bad-movie-2019', ('grad', [(0, (180, 30, 24)), (.6, (100, 14, 10)), (1, (24, 4, 2))]), WHT,
    [T('EL CAMINO', 'hcnb', 92, WHT, squeeze=.78, bold=.6), T('A BREAKING BAD MOVIE', 'herb', 22, WHT, track=.3)], tgap=8,
    photo=ph(.52, .2, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AARON PAUL'], ccol=WHT,
    ft='a', vbox=WHT, vink=(100, 14, 10), fcol=(240, 210, 206), fin=MINT)

# Class Action Park: storm grey, the sign's rainbow capitals (typeset), the park's sign (no logo file: the label in type)
std('class-action-park-2020', ('grad', [(0, (110, 116, 120)), (.6, (60, 66, 70)), (1, (30, 40, 30))]), WHT,
    TT([('CLASS', (240, 70, 140)), ('ACTION', (250, 200, 40)), ('PARK', (60, 180, 240))], 'popb', 76, sp=.2, outline=((20, 20, 30), 1.8)),
    photo=ph(.4, .32, .5, 1.0), pb=WHT, studio=['HBO MAX'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 66, 70), fcol=WHT, fin=MINT)

# Basic Instinct (1992): a real rental, the poster's blue-white, red BASIC and black INSTINCT (typeset), Nick and Catherine
std('basic-instinct-1992', ('grad', [(0, (200, 214, 230)), (.6, (150, 170, 196)), (1, (40, 54, 80))]), (200, 30, 30),
    TT([('BASIC', (204, 30, 30)), ('INSTINCT', (20, 20, 24))], 'hcnb', 92, sp=.2, squeeze=.72, bold=.8),
    photo=ph(.5, .4, .6, 1.0), pb=(204, 30, 30), lg=(20, 20, 24), lw=.6, order='LPTCSF', credit=['MICHAEL DOUGLAS', 'SHARON STONE'], ccol=WHT,
    stick=PRC(['$2.49', 'THRILLER']), ft='a', vbox=(204, 30, 30), fcol=WHT, fin=RENTAL, seed=1992)

# A Simple Favor: the poster's pink and teal blocks, thin grey capitals (typeset), Emily with her martini
std('a-simple-favor-2018', ('grad', [(0, (244, 190, 190)), (.5, (200, 214, 214)), (1, (40, 180, 190))]), (70, 70, 74),
    T('A Simple Favor', 'her', 70, (72, 72, 76)),
    photo=ph(.55, .2, .35, 1.0), pb=(72, 72, 76), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['ANNA KENDRICK', 'BLAKE LIVELY'], ccol=(30, 30, 30),
    ft='a', vbox=(72, 72, 76), fcol=(30, 30, 30), fin=MINT)

# Don't F**k with Cats: screen black, the yellow block capitals (typeset), the cat on the video
std('don-t-f-k-with-cats-hunting-an-internet-killer-2019', ('grad', [(0, (30, 40, 50)), (.6, (12, 16, 20)), (1, (4, 4, 6))]), (246, 214, 40),
    [T("DON'T F**K WITH CATS", 'hcnb', 70, (248, 216, 44), squeeze=.84, bold=.6), T('HUNTING AN INTERNET KILLER', 'hcnb', 26, (248, 216, 44), track=.12)], tgap=8,
    photo=ph(.6, .4, .5, 1.0), pb=(248, 216, 44), lg=WHT, lw=.6, order='LPTCF', credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(248, 216, 44),
    ft='a', vbox=(248, 216, 44), vink=(12, 16, 20), fcol=(190, 196, 206), fin=MINT)

# Fatal Attraction (1987): a real rental, black and the torn red, the red script and white capitals (typeset), Dan and Alex
std('fatal-attraction-1987', ('grad', [(0, (40, 40, 60)), (.6, (14, 14, 22)), (1, (4, 4, 6))]), WHT,
    [T('Fatal', 'cho', 100, (226, 30, 40)), T('ATTRACTION', 'ter', 52, WHT, track=.06)], tgap=6,
    photo=ph(.4, .3, .6, 1.0), pb=(226, 30, 40), lg=WHT, lw=.6, order='LPTCSF', credit=['MICHAEL DOUGLAS', 'GLENN CLOSE'], ccol=WHT,
    stick=flow(dot, 70, ['THRILLER'], (226, 30, 40), d=62), ft='a', vbox=(226, 30, 40), fcol=(200, 200, 210), fin=RENTAL, seed=1987)

# A Time to Kill (1996): a real rental, Canton night black, the red condensed capitals (typeset), Ellen at the head
std('a-time-to-kill-1996', ('grad', [(0, (40, 30, 30)), (.6, (14, 10, 10)), (1, (4, 4, 4))]), (210, 30, 30),
    T('A TIME TO KILL', 'hcnb', 94, (214, 32, 32), squeeze=.7, bold=.6),
    photo=ph(.6, .2, .35, 1.0), pb=(214, 32, 32), lg=WHT, lw=.6, order='LPTCSF', credit=['MATTHEW McCONAUGHEY', 'SANDRA BULLOCK'], ccol=WHT,
    stick=PRC(['3 NIGHTS', '$2.99']), ft='a', vbox=(214, 32, 32), fcol=(200, 196, 196), fin=RENTAL, seed=1996)

# Sorry, Wrong Number (1948): an old tape, the poster's lemon yellow, the red slab capitals (typeset), Leona at the telephone
std('sorry-wrong-number-1948', ('grad', [(0, (246, 226, 70)), (.6, (230, 200, 50)), (1, (140, 110, 20))]), (200, 40, 40),
    T('SORRY, WRONG NUMBER', 'bonb', 64, (204, 42, 42)),
    photo=ph(.2, .72, .4, 1.0), pb=(204, 42, 42), lg=(30, 26, 20), lw=.6, order='LPTCF', credit=['BARBARA STANWYCK', 'BURT LANCASTER'], ccol=(30, 26, 20),
    ft='e', fcol=(30, 26, 20), fin=OLD, seed=1948)

# The Dreamers (2003): the poster's Paris pink, white rough capitals (typeset), Isabelle at the head
std('the-dreamers-2003', ('grad', [(0, (200, 80, 130)), (.6, (120, 40, 80)), (1, (30, 10, 20))]), WHT,
    T('THE DREAMERS', 'herb', 70, WHT, rough=.6),
    photo=ph(.5, .45, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A BERNARDO BERTOLUCCI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(120, 40, 80), fcol=(240, 210, 226), fin=WORN, seed=2003)

# Runaway Jury (2003): the courthouse black and sepia, white serif capitals (typeset), Nick at the head
std('runaway-jury-2003', ('grad', [(0, (70, 56, 40)), (.6, (26, 20, 14)), (1, (6, 4, 4))]), WHT,
    [T('RUNAWAY', 'ter', 44, WHT, track=.08), T('JURY', 'ter', 100, WHT, track=.04)], tgap=6,
    photo=ph(.4, .45, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JOHN CUSACK', 'GENE HACKMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(26, 20, 14), fcol=(220, 206, 190), fin=WORN, seed=2003)

# The Pelican Brief (1993): a real rental, sepia gold, white serif capitals (typeset), Darby at the screen
std('the-pelican-brief-1993', ('grad', [(0, (170, 110, 50)), (.6, (80, 50, 20)), (1, (20, 12, 6))]), WHT,
    [T('THE', 'ter', 26, WHT, track=.3), T('PELICAN BRIEF', 'ter', 72, WHT, track=.02)], tgap=6,
    photo=ph(.55, .4, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['JULIA ROBERTS', 'DENZEL WASHINGTON'], ccol=WHT,
    stick=RWD(fill=(250, 246, 200)), ft='a', vbox=WHT, vink=(80, 50, 20), fcol=(230, 210, 190), fin=RENTAL, seed=1993)

# Icarus: the poster's flat red, yellow capitals with the white R (typeset; the poster's R is backwards), the puppet-master's hand
std('icarus-2017', ('solid', (226, 30, 30)), (250, 210, 40),
    TT([('ICA', (250, 212, 44)), ('R', WHT), ('US', (250, 212, 44))], 'hcnb', 110, sp=0, squeeze=.8, bold=.6),
    photo=ph(.5, .12, .5, 1.0), pb=(20, 18, 18), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(20, 18, 18), fcol=WHT, fin=MINT)

# Blow Out (1981): an old tape, black, the white heavy capitals, Jack and the microphone (no logo file: its company in type)
std('blow-out-1981', ('grad', [(0, (40, 40, 50)), (.6, (14, 14, 18)), (1, (4, 4, 6))]), WHT,
    L((0.09, 0.83, 0.91, 0.935), 96, WHT, mode='light', speck=.01),
    photo=ph(.75, .35, .45, 1.0), pb=WHT, studio=['FILMWAYS PICTURES'], scol=WHT, order='lPTCSF', credit=['JOHN TRAVOLTA'], ccol=WHT,
    stick=flow(dot, 70, ['CULT'], (240, 140, 30), d=60), ft='e', fcol=(200, 200, 206), fin=OLD, seed=1981)

# X-Men: First Class: Cuban-crisis teal, the silver capitals (typeset), the class on the beach
std('x-men-first-class-2011', ('grad', [(0, (50, 90, 100)), (.6, (16, 30, 36)), (1, (4, 8, 10))]), (220, 224, 230),
    [T('X-MEN', 'intbk', 90, WHT, grad=[(0, (250, 250, 255)), (.5, (150, 160, 176)), (1, (230, 234, 240))]), T('FIRST CLASS', 'intbk', 40, (200, 206, 214), track=.1)], tgap=8,
    photo=ph(.5, .35, .8, .8), pb=(230, 190, 60), lg=WHT, lw=.6, order='LPTCF', credit=['JAMES McAVOY', 'MICHAEL FASSBENDER'], ccol=WHT,
    ft='a', vbox=(230, 190, 60), vink=(16, 30, 36), fcol=(190, 200, 206), fin=SLIP, seed=2011)

# Exit Through the Gift Shop: gallery white, the red dripping spray capitals (typeset), the rat with the paint can
std('exit-through-the-gift-shop-2010', ('solid', (244, 242, 238)), (200, 30, 30),
    T('EXIT THROUGH THE GIFT SHOP', 'intbk', 60, (204, 32, 32), squeeze=.82, rough=.5),
    photo=ph(.8, .85, .35, 1.0), pb=(20, 18, 18), lg=(20, 18, 18), lw=.6, order='LPTCF', credit=['A BANKSY FILM'], ccol=(20, 18, 18),
    ft='a', vbox=(204, 32, 32), fcol=(20, 18, 18), fin=SLIP, seed=2010)

# The Body (2012): the morgue's dark teal, white heavy capitals (typeset), Mayka between the two men
std('the-body-2012', ('grad', [(0, (40, 60, 60)), (.6, (14, 20, 20)), (1, (4, 6, 6))]), WHT,
    T('THE BODY', 'intbk', 100, WHT),
    photo=ph(.48, .2, .35, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AN ORIOL PAULO', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 20, 20), fcol=(190, 200, 200), fin=SLIP)

# Logan: the dust-orange sun, white heavy capitals (typeset), Logan and Laura
std('logan-2017', ('grad', [(0, (210, 110, 40)), (.5, (110, 50, 20)), (1, (20, 10, 6))]), WHT,
    T('LOGAN', 'intbk', 120, WHT),
    photo=ph(.5, .2, .35, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['HUGH JACKMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 50, 20), fcol=(240, 220, 200), fin=SLIP)

# The Death of Stalin: the white plate, the red heavy capitals (typeset), the committee
std('the-death-of-stalin-2017', ('grad', [(0, (246, 244, 240)), (.6, (230, 226, 220)), (1, (170, 160, 150))]), (210, 30, 30),
    TT([('THE DEATH OF', (214, 32, 32)), ('STALIN', (214, 32, 32))], 'intbk', 66, sp=.25, squeeze=.86),
    photo=ph(.55, .35, .8, .6), pb=(214, 32, 32), lg=(30, 26, 24), lw=.6, order='LPTCF', credit=['AN ARMANDO IANNUCCI', 'FILM'], ccol=(30, 26, 24),
    ft='a', vbox=(214, 32, 32), fcol=(30, 26, 24), fin=SLIP)

# Captain Marvel: cosmic red and blue, the gold-and-red capitals (typeset), Carol at the head
std('captain-marvel-2019', ('grad', [(0, (40, 50, 120)), (.5, (150, 30, 50)), (1, (30, 10, 20))]), (250, 200, 80),
    [T('CAPTAIN', 'intbk', 40, (250, 204, 90), track=.12), T('MARVEL', 'intbk', 100, (220, 40, 40), outline=((250, 204, 90), 2.0))], tgap=8,
    photo=ph(.5, .12, .35, 1.0), pb=(250, 204, 90), lg=WHT, lw=.6, order='LPTCF', credit=['BRIE LARSON'], ccol=(250, 204, 90),
    ft='a', vbox=(250, 204, 90), vink=(150, 30, 50), fcol=WHT, fin=SLIP)

# ----- the 2020 Marvel run (Marvel Studios: slipcases, like Deadpool & Wolverine) -----

# Captain America: The First Avenger (2011): the poster's war-smoke grey, silver capitals (typeset), Steve at the head
std('captain-america-the-first-avenger-2011', ('grad', [(0, (150, 150, 150)), (.6, (60, 60, 62)), (1, (16, 16, 18))]), (220, 224, 230),
    [T('CAPTAIN AMERICA', 'intbk', 66, WHT, squeeze=.86, grad=[(0, (250, 250, 255)), (.5, (150, 156, 170)), (1, (230, 232, 240))], outline=((20, 24, 40), 1.6)), T('THE FIRST AVENGER', 'herb', 24, (200, 40, 40), track=.3)], tgap=8,
    photo=ph(.45, .12, .3, 1.0), pb=(200, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS EVANS'], ccol=WHT,
    ft='a', vbox=(200, 40, 40), fcol=(210, 210, 214), fin=SLIP, seed=2011)

# Thor (2011): Asgard night, the red Roman capitals (typeset), Thor with the hammer
std('thor-2011', ('grad', [(0, (30, 40, 70)), (.6, (12, 16, 30)), (1, (4, 6, 10))]), (200, 30, 30),
    T('THOR', 'ter', 120, (210, 34, 34), track=.3),
    photo=ph(.5, .47, .35, 1.0), pb=(210, 34, 34), lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS HEMSWORTH', 'NATALIE PORTMAN'], ccol=WHT,
    ft='a', vbox=(210, 34, 34), fcol=(190, 196, 210), fin=SLIP, seed=2011)

# Thor: The Dark World: Svartalfheim teal-grey, the steel capitals (typeset), Thor at the head
std('thor-the-dark-world-2013', ('grad', [(0, (90, 120, 120)), (.6, (30, 42, 44)), (1, (8, 12, 12))]), (210, 214, 220),
    [T('THOR', 'intbk', 100, WHT, grad=[(0, (240, 242, 246)), (.5, (130, 140, 150)), (1, (220, 224, 230))], outline=((20, 24, 30), 1.6)), T('THE DARK WORLD', 'herb', 26, (200, 206, 214), track=.3)], tgap=8,
    photo=ph(.52, .27, .3, 1.0), pb=(200, 206, 214), lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS HEMSWORTH'], ccol=WHT,
    ft='a', vbox=(200, 206, 214), vink=(30, 42, 44), fcol=(190, 200, 200), fin=SLIP)

# Thor: Ragnarok: Sakaar's eighties blue and green, orange THOR and the rainbow RAGNAROK (typeset), Thor at the head
std('thor-ragnarok-2017', ('grad', [(0, (40, 80, 180)), (.5, (30, 50, 110)), (1, (20, 60, 40))]), (250, 150, 40),
    [T('THOR', 'intbk', 70, (250, 160, 40)), T('RAGNAROK', 'intbk', 70, WHT, grad=[(0, (240, 80, 160)), (.5, (250, 200, 80)), (1, (80, 200, 240))], outline=((20, 20, 40), 1.6))], tgap=8,
    photo=ph(.47, .45, .3, 1.0), pb=(250, 160, 40), lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS HEMSWORTH', 'TOM HIDDLESTON'], ccol=WHT,
    ft='a', vbox=(250, 160, 40), vink=(30, 50, 110), fcol=WHT, fin=SLIP)

# The Intouchables (2011): the poster's warm black and green, the cream lower case (typeset), Philippe and Driss
std('the-intouchables-2011', ('grad', [(0, (60, 70, 50)), (.6, (24, 26, 20)), (1, (6, 6, 4))]), (240, 226, 190),
    [T('The', 'her', 36, (242, 228, 192)), T('Intouchables', 'her', 76, (242, 228, 192))], tgap=6,
    photo=ph(.74, .2, .45, 1.0), pb=(242, 228, 192), lg=WHT, lw=.6, order='LPTCF', credit=['FRANÇOIS CLUZET', 'OMAR SY'], ccol=(242, 228, 192),
    ft='a', vbox=(242, 228, 192), vink=(24, 26, 20), fcol=(210, 206, 190), fin=SLIP, seed=2011, dotst=(['STAFF', 'PICK'], (60, 120, 70)))

# Doctor Strange (2016): the mirror city's sky, the gold engraved capitals (typeset), Strange in the portal
std('doctor-strange-2016', ('grad', [(0, (120, 160, 200)), (.5, (50, 70, 110)), (1, (14, 18, 30))]), (230, 180, 70),
    [T('DOCTOR', 'ter', 44, (234, 186, 76), track=.1), T('STRANGE', 'ter', 90, (234, 186, 76), track=.04, grad=[(0, (250, 220, 120)), (1, (200, 140, 40))])], tgap=6,
    photo=ph(.5, .3, .5, 1.0), pb=(234, 186, 76), lg=WHT, lw=.6, order='LPTCF', credit=['BENEDICT CUMBERBATCH'], ccol=(234, 186, 76),
    ft='a', vbox=(234, 186, 76), vink=(50, 70, 110), fcol=(200, 210, 224), fin=SLIP)

# Avengers: Infinity War: Titan's fire red and orange, gold AVENGERS (typeset), the whole line-up
std('avengers-infinity-war-2018', ('grad', [(0, (220, 100, 40)), (.5, (130, 30, 30)), (1, (30, 8, 10))]), (240, 190, 80),
    [T('AVENGERS', 'intbki', 84, (244, 196, 86), grad=[(0, (250, 226, 140)), (1, (210, 140, 40))], outline=((60, 20, 10), 1.6)), T('INFINITY WAR', 'ter', 32, (244, 196, 86), track=.2)], tgap=8,
    photo=ph(.5, .4, .8, .6), pb=(244, 196, 86), lg=WHT, lw=.6, order='LPTCF', credit=['ROBERT DOWNEY JR.', 'CHRIS HEMSWORTH'], ccol=WHT,
    ft='a', vbox=(244, 196, 86), vink=(130, 30, 30), fcol=(240, 210, 190), fin=SLIP)

# Guardians of the Galaxy Vol. 2: the cosmic purple and orange, the blue-gold capitals and the pink VOL. 2 (typeset), Peter at the head
std('guardians-of-the-galaxy-vol-2-2017', ('grad', [(0, (60, 40, 120)), (.5, (180, 70, 90)), (1, (40, 20, 60))]), (100, 180, 240),
    [T('GUARDIANS OF THE GALAXY', 'intbk', 54, (110, 190, 250), squeeze=.86, outline=((20, 20, 50), 1.6)), T('VOL. 2', 'cho', 50, (250, 100, 160))], tgap=8,
    photo=ph(.5, .25, .4, 1.0), pb=(250, 200, 80), lg=WHT, lw=.6, order='LPTCF', credit=['A JAMES GUNN', 'FILM'], ccol=WHT,
    ft='a', vbox=(250, 200, 80), vink=(60, 40, 120), fcol=WHT, fin=SLIP)

# Avengers: Age of Ultron: Sokovia's ash grey and blue, the red AVENGERS (typeset), the team charging
std('avengers-age-of-ultron-2015', ('grad', [(0, (180, 186, 190)), (.5, (70, 80, 100)), (1, (14, 18, 26))]), (200, 30, 30),
    [T('AVENGERS', 'intbki', 84, (206, 32, 32), outline=((30, 10, 10), 1.6)), T('AGE OF ULTRON', 'herbi', 30, WHT, track=.12)], tgap=8,
    photo=ph(.5, .45, .8, .6), pb=(206, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['A JOSS WHEDON', 'FILM'], ccol=WHT,
    ft='a', vbox=(206, 32, 32), fcol=(200, 206, 214), fin=SLIP, seed=2015)

# Avengers: Endgame (181 minutes, one tape like Oppenheimer): the poster's violet, silver-blue AVENGERS (typeset), the survivors
std('avengers-endgame-2019', ('grad', [(0, (80, 60, 160)), (.5, (40, 30, 90)), (1, (10, 8, 26))]), (180, 190, 230),
    [T('AVENGERS', 'intbki', 84, (190, 200, 240), grad=[(0, (220, 226, 250)), (1, (110, 120, 200))], outline=((20, 16, 50), 1.6)), T('ENDGAME', 'her', 32, (200, 206, 240), track=.4)], tgap=8,
    photo=ph(.5, .25, .6, 1.0), pb=(190, 200, 240), lg=WHT, lw=.6, order='LPTCF', credit=['ROBERT DOWNEY JR.', 'CHRIS EVANS'], ccol=WHT,
    ft='a', vbox=(190, 200, 240), vink=(40, 30, 90), fcol=(200, 200, 226), fin=SLIP)

# Iron Man 2 (2010): Stark red and gold on black, the red stencil capitals (typeset), the helmet
std('iron-man-2-2010', ('grad', [(0, (60, 60, 64)), (.6, (20, 20, 22)), (1, (6, 6, 6))]), (210, 30, 30),
    T('IRON MAN 2', 'hcnb', 96, (214, 34, 34), squeeze=.76, bold=.8, outline=((230, 180, 60), 1.4)),
    photo=ph(.6, .15, .35, 1.0), pb=(230, 180, 60), lg=WHT, lw=.6, order='LPTCF', credit=['ROBERT DOWNEY JR.'], ccol=(230, 180, 60),
    ft='a', vbox=(214, 34, 34), fcol=(200, 200, 204), fin=SLIP, seed=2010)

# Captain America: Civil War: the shield's steel and red, the red-and-silver capitals (typeset), Steve and Tony face to face
std('captain-america-civil-war-2016', ('grad', [(0, (150, 160, 176)), (.5, (70, 80, 100)), (1, (16, 18, 26))]), (200, 30, 30),
    [T('CAPTAIN AMERICA', 'herb', 28, (206, 34, 34), track=.2), T('CIVIL WAR', 'intbk', 96, WHT, grad=[(0, (250, 250, 255)), (.5, (150, 160, 176)), (1, (230, 232, 240))], outline=((180, 30, 30), 2.0))], tgap=8,
    photo=ph(.5, .2, .9, .6), pb=(206, 34, 34), lg=WHT, lw=.6, order='LPTCF', credit=['CHRIS EVANS', 'ROBERT DOWNEY JR.'], ccol=WHT,
    ft='a', vbox=(206, 34, 34), fcol=(210, 214, 220), fin=SLIP, seed=2016)

# Ant-Man and the Wasp: the poster's red-and-gold slash on white, red ANT-MAN and gold WASP (typeset), Hope at the head
std('ant-man-and-the-wasp-2018', ('grad', [(0, (244, 240, 236)), (.4, (230, 120, 60)), (1, (130, 20, 20))]), (200, 30, 30),
    TT([('ANT-MAN', (206, 32, 32)), ('AND THE', (40, 30, 30)), ('WASP', (240, 180, 40))], 'intbki', 72, sp=.2, squeeze=.84, outline=((40, 20, 20), 1.2)),
    photo=ph(.5, .15, .3, 1.0), pb=(206, 32, 32), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['PAUL RUDD', 'EVANGELINE LILLY'], ccol=WHT,
    ft='a', vbox=(206, 32, 32), fcol=WHT, fin=SLIP)

# Manhattan Murder Mystery (1993): a real rental, the poster's royal blue night, yellow condensed capitals (typeset), the four in their frames
std('manhattan-murder-mystery-1993', ('grad', [(0, (40, 60, 180)), (.6, (20, 30, 110)), (1, (6, 10, 30))]), (246, 230, 50),
    T('MANHATTAN MURDER MYSTERY', 'hcnb', 70, (248, 232, 54), squeeze=.76),
    photo=ph(.5, .25, .9, .6), pb=(248, 232, 54), lg=WHT, lw=.6, order='LPTCSF', credit=['WOODY ALLEN', 'DIANE KEATON'], ccol=WHT,
    stick=PRC(['$1.99', 'COMEDY']), ft='a', vbox=(248, 232, 54), vink=(20, 30, 110), fcol=(210, 214, 240), fin=RENTAL, seed=1993)

# Wild Tales: the poster's white panels, the red brush capitals (typeset), the bride at her wedding
std('wild-tales-2014', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 216)), (1, (60, 56, 52))]), (210, 30, 30),
    T('WILD TALES', 'bonb', 92, (214, 32, 32), rough=.6),
    photo=ph(.6, .65, .5, 1.0), pb=(214, 32, 32), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A DAMIÁN SZIFRON', 'FILM'], ccol=WHT,
    ft='a', vbox=(214, 32, 32), fcol=WHT, fin=SLIP, dotst=(['STAFF', 'PICK'], (30, 30, 30)))

# Incendies (2010): the poster's red, the white wide capitals, Nawal's face
std('incendies-2010', ('grad', [(0, (220, 30, 30)), (.6, (160, 16, 18)), (1, (50, 6, 6))]), WHT,
    L((0.08, 0.79, 0.92, 0.885), 76, WHT, mode='light', speck=.01),
    photo=ph(.5, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DENIS VILLENEUVE', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(160, 16, 18), fcol=(250, 220, 220), fin=SLIP, seed=2010)

# Tangerines: the orchard dusk, the orange capitals (typeset: they lean), Ivo
std('tangerines-2013', ('grad', [(0, (70, 70, 50)), (.6, (26, 26, 18)), (1, (6, 6, 4))]), (240, 140, 30),
    T('TANGERINES', 'hcnb', 92, (242, 146, 36), squeeze=.78, bold=.6),
    photo=ph(.6, .35, .45, 1.0), pb=(242, 146, 36), lg=WHT, lw=.6, order='LPTCF', credit=['LEMBIT ULFSAK'], ccol=(242, 146, 36),
    ft='a', vbox=(242, 146, 36), vink=(26, 26, 18), fcol=(200, 200, 184), fin=SLIP)

# Mary and Max (2009): New York black and grey, the white hand-drawn lettering (typeset), Max at his table
std('mary-and-max-2009', ('grad', [(0, (70, 70, 70)), (.6, (24, 24, 24)), (1, (6, 6, 6))]), WHT,
    T('Mary and Max.', 'cho', 100, WHT),
    photo=ph(.5, .55, .6, 1.0), pb=(200, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['TONI COLLETTE', 'PHILIP SEYMOUR HOFFMAN'], ccol=WHT,
    ft='a', vbox=(200, 40, 40), fcol=(200, 200, 200), fin=SLIP, seed=2009)

# Barry Lyndon (1975): an old 2-tape box (188 minutes), the poster's cream with the engraved border, black serif capitals (typeset), the border's figures
std('barry-lyndon-1975', ('grad', [(0, (244, 238, 222)), (.6, (226, 216, 194)), (1, (160, 146, 120))]), (20, 18, 16),
    T('BARRY LYNDON', 'terb', 110, (20, 18, 16), track=.06),
    photo=ph(.2, .2, .4, .5), pb=(20, 18, 16), lg=(20, 18, 16), lw=.5, order='LPTCSF', tgap=10, credit=['A STANLEY KUBRICK', 'FILM'], ccol=(20, 18, 16),
    stick=TWOST((20, 18, 16), (244, 238, 222)), ft='c', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=OLD, seed=1975, **TWO)

# Three Colours: White (1994): the poster's white, the grey-blue heavy capitals (typeset), Dominique
std('three-colors-white-1994', ('solid', (246, 246, 244)), (110, 150, 160),
    [T('THREE COLOURS', 'herb', 24, (110, 150, 160), track=.2), T('WHITE', 'hcnb', 110, (110, 152, 162), squeeze=.8, bold=.6)], tgap=8,
    photo=ph(.4, .72, .45, 1.0), pb=(110, 152, 162), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A FILM BY', 'KIEŚLOWSKI'], ccol=(30, 30, 30),
    ft='a', vbox=(110, 152, 162), fcol=(30, 30, 30), fin=WORN, seed=1994)

# Three Colours: Red (1994): the poster's red, the pale heavy capitals (typeset), Valentine and the judge
std('three-colors-red-1994', ('grad', [(0, (210, 40, 50)), (.6, (150, 20, 30)), (1, (50, 6, 10))]), (244, 210, 210),
    [T('THREE COLOURS', 'herb', 24, (246, 214, 214), track=.2), T('RED', 'hcnb', 120, (246, 214, 214), squeeze=.8, bold=.6)], tgap=8,
    photo=ph(.6, .6, .45, 1.0), pb=(246, 214, 214), lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'KIEŚLOWSKI'], ccol=(246, 214, 214),
    ft='a', vbox=(246, 214, 214), vink=(150, 20, 30), fcol=(246, 214, 214), fin=WORN, seed=1994)

# My Father and My Son (2005): the poster's plaster cream, the cream heavy capitals (typeset), father and son at the table
std('my-father-and-my-son-2005', ('grad', [(0, (180, 150, 100)), (.6, (110, 90, 60)), (1, (30, 24, 16))]), (246, 230, 190),
    T('My Father and My Son', 'popb', 62, (248, 232, 194)),
    photo=ph(.25, .66, .4, 1.0), pb=(248, 232, 194), lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'ÇAĞAN IRMAK'], ccol=(248, 232, 194),
    ft='a', vbox=(248, 232, 194), vink=(110, 90, 60), fcol=(230, 220, 200), fin=WORN, seed=2005)

# Andhadhun: the poster's white and the piano's cyan, the cyan brush capitals (typeset), Akash and Sophie on the keys
std('andhadhun-2018', ('grad', [(0, (246, 246, 244)), (.5, (120, 210, 236)), (1, (20, 120, 170))]), (30, 170, 220),
    T('ANDHADHUN', 'intbk', 92, (30, 172, 222), squeeze=.86, rough=.5, outline=((20, 40, 60), 1.4)),
    photo=ph(.6, .15, .45, 1.0), pb=(30, 172, 222), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['AYUSHMANN KHURRANA', 'TABU'], ccol=WHT,
    ft='a', vbox=(30, 172, 222), fcol=WHT, fin=SLIP)

# Hotel Rwanda (2004): the poster's dusk peach, black heavy capitals (typeset), Paul at the head
std('hotel-rwanda-2004', ('grad', [(0, (240, 210, 170)), (.6, (210, 160, 110)), (1, (110, 70, 40))]), (20, 18, 16),
    T('HOTEL RWANDA', 'hcnb', 92, (20, 18, 16), squeeze=.76, bold=.8),
    photo=ph(.5, .15, .45, 1.0), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['DON CHEADLE'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=WORN, seed=2004)

# Three Colours: Blue (1993): the pool's deep blue, the pale blue heavy capitals (typeset), Julie
std('three-colors-blue-1993', ('grad', [(0, (30, 70, 140)), (.6, (12, 30, 70)), (1, (4, 10, 24))]), (90, 180, 230),
    [T('THREE COLOURS', 'herb', 24, (220, 230, 240), track=.2), T('BLUE', 'hcnb', 120, (96, 186, 236), squeeze=.8, bold=.6)], tgap=8,
    photo=ph(.5, .55, .45, 1.0), pb=(96, 186, 236), lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'KIEŚLOWSKI'], ccol=(220, 230, 240),
    ft='a', vbox=(96, 186, 236), vink=(12, 30, 70), fcol=(200, 210, 226), fin=WORN, seed=1993)

# Amadeus (1984): an old tape, black, the white engraved capitals (typeset), the masked figure
std('amadeus-1984', ('grad', [(0, (120, 50, 70)), (.4, (40, 16, 24)), (1, (6, 4, 4))]), WHT,
    T('AMADEUS', 'ter', 100, WHT, track=.04),
    photo=ph(.5, .25, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A MILOŠ FORMAN', 'FILM'], ccol=WHT,
    stick=PRC(['$2.99', 'DRAMA']), ft='e', fcol=(220, 210, 210), fin=OLD, seed=1984)

# Children of Heaven (1997): the poster's sky blue with the goldfish, orange serif capitals (typeset), the fish
std('children-of-heaven-1997', ('grad', [(0, (60, 150, 230)), (.6, (30, 100, 190)), (1, (10, 30, 50))]), (240, 130, 40),
    T('CHILDREN OF HEAVEN', 'ter', 66, (244, 136, 44), track=.04, outline=((60, 30, 10), 1.2)),
    photo=ph(.6, .3, .5, 1.0), pb=(244, 136, 44), lg=WHT, lw=.6, order='LPTCF', credit=['A MAJID MAJIDI', 'FILM'], ccol=WHT,
    ft='a', vbox=(244, 136, 44), vink=(30, 100, 190), fcol=WHT, fin=WORN, seed=1997)

# Alone in the Wilderness: Part II: Twin Lakes green, the white serif lettering (typeset), Dick by the water (no logo file: its company in type)
std('alone-in-the-wilderness-part-ii-2011', ('grad', [(0, (90, 140, 150)), (.5, (60, 90, 50)), (1, (20, 30, 14))]), WHT,
    [T('Alone in the Wilderness', 'ter', 56, WHT), T('PART II', 'ter', 26, WHT, track=.2)], tgap=6,
    photo=ph(.6, .62, .45, 1.0), pb=WHT, studio=['BOB SWERER', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 90, 50), fcol=(220, 230, 214), fin=SLIP)

# Gangs of Wasseypur - Part 1: dusty teal and rickshaw paint, the red slab capitals (typeset), the fight (no logo file: its company in type)
std('gangs-of-wasseypur-part-1-2012', ('grad', [(0, (180, 170, 140)), (.5, (70, 90, 90)), (1, (20, 24, 24))]), (190, 30, 30),
    [T('GANGS OF WASSEYPUR', 'bonb', 62, (196, 34, 34), outline=((250, 240, 220), 1.4)), T('PART 1', 'herb', 26, WHT, track=.2)], tgap=8,
    photo=ph(.4, .45, .5, 1.0), pb=(196, 34, 34), studio=['JAR PICTURES'], scol=(30, 30, 30), order='lPTCF', credit=['AN ANURAG KASHYAP', 'FILM'], ccol=WHT,
    ft='a', vbox=(196, 34, 34), fcol=WHT, fin=SLIP)

# X-Men: Days of Future Past: the burning future's amber, silver capitals (typeset), Logan
std('x-men-days-of-future-past-2014', ('grad', [(0, (170, 130, 80)), (.5, (70, 50, 40)), (1, (14, 10, 8))]), (220, 224, 230),
    [T('X-MEN', 'intbk', 92, WHT, grad=[(0, (250, 250, 255)), (.5, (150, 160, 176)), (1, (230, 234, 240))]), T('DAYS OF FUTURE PAST', 'herb', 24, (220, 224, 230), track=.2)], tgap=8,
    photo=ph(.68, .14, .3, 1.0), pb=(220, 224, 230), lg=WHT, lw=.6, order='LPTCF', credit=['PATRICK STEWART', 'HUGH JACKMAN'], ccol=WHT,
    ft='a', vbox=(220, 224, 230), vink=(70, 50, 40), fcol=(220, 210, 200), fin=SLIP)

# Your Name. (2016): the comet sky's blue, the white handwritten title (typeset), Mitsuha on the hill
std('your-name-2016', ('grad', [(0, (80, 150, 230)), (.6, (40, 100, 200)), (1, (20, 50, 100))]), WHT,
    T('your name.', 'cho', 110, WHT),
    photo=ph(.75, .75, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A MAKOTO SHINKAI', 'FILM'], ccol=WHT,
    stick=flow(dot, 70, ['ANIME'], (220, 60, 100), d=60), ft='a', vbox=WHT, vink=(40, 100, 200), fcol=WHT, fin=SLIP)

# Capernaum: Beirut sky blue, white spaced capitals (typeset), Zain on the road
std('capernaum-2018', ('grad', [(0, (60, 160, 200)), (.6, (40, 90, 110)), (1, (30, 24, 20))]), WHT,
    T('CAPERNAUM', 'her', 72, WHT, track=.3),
    photo=ph(.45, .55, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A NADINE LABAKI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 90, 110), fcol=(220, 226, 230), fin=MINT)

# Metropolis (1927): an old tape, silver-black, the yellow art-deco capitals (typeset), Maria the machine
std('metropolis-1927', ('grad', [(0, (70, 70, 72)), (.6, (24, 24, 26)), (1, (6, 6, 6))]), (230, 220, 60),
    T('METROPOLIS', 'adv', 84, (232, 222, 64), track=.1, bold=.4),
    photo=ph(.45, .35, .5, 1.0), pb=(232, 222, 64), lg=WHT, lw=.6, order='LPTCSF', credit=['A FRITZ LANG', 'FILM'], ccol=(232, 222, 64),
    stick=PRC(['$1.99', 'SILENT']), ft='e', fcol=(210, 210, 200), fin=OLD, seed=1927)

# Drishyam (2015): Goa monsoon green, white stencil capitals (typeset), Vijay at the head
std('drishyam-2015', ('grad', [(0, (70, 90, 60)), (.6, (28, 36, 24)), (1, (8, 10, 6))]), WHT,
    T('DRISHYAM', 'intbk', 92, WHT, rough=.5),
    photo=ph(.5, .12, .4, 1.0), pb=(220, 180, 60), lg=WHT, lw=.6, order='LPTCF', credit=['AJAY DEVGN', 'TABU'], ccol=WHT,
    ft='a', vbox=(220, 180, 60), vink=(28, 36, 24), fcol=(210, 216, 200), fin=SLIP)

# Elite Squad (2007): the poster's red, white heavy capitals (typeset), the BOPE squad
std('elite-squad-2007', ('grad', [(0, (200, 30, 30)), (.6, (130, 16, 16)), (1, (30, 6, 6))]), WHT,
    T('ELITE SQUAD', 'intbk', 84, WHT, squeeze=.86),
    photo=ph(.27, .75, .35, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['WAGNER MOURA'], ccol=WHT,
    ft='a', vbox=WHT, vink=(130, 16, 16), fcol=(240, 210, 206), fin=WORN, seed=2007)

# M (1931): an old tape, black, the red chalked M (typeset), the marked hand
std('m-1931', ('grad', [(0, (40, 36, 34)), (.6, (14, 12, 12)), (1, (4, 4, 4))]), (200, 40, 40),
    T('M', 'bonb', 200, (204, 44, 44), rough=.6),
    photo=ph(.5, .5, .6, 1.0), pb=(204, 44, 44), lg=WHT, lw=.6, order='LPTCF', credit=['PETER LORRE', 'A FRITZ LANG FILM'], ccol=(220, 214, 204),
    ft='e', fcol=(220, 214, 204), fin=OLD, seed=1931)

# Talk to Her (2002): the poster's blue-and-red split, red talk, white to and blue her (typeset), Alicia and Lydia
std('talk-to-her-2002', ('grad', [(0, (120, 150, 180)), (.5, (180, 40, 40)), (1, (40, 8, 8))]), WHT,
    TT([('talk', (220, 40, 40)), ('to', WHT), ('her', (60, 170, 230))], 'schb', 100, sp=.15, outline=((20, 20, 30), 1.4)),
    photo=ph(.3, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A FILM BY', 'ALMODÓVAR'], ccol=WHT,
    ft='a', vbox=WHT, vink=(180, 40, 40), fcol=(230, 220, 220), fin=WORN, seed=2002)

# Ray (2004): stage black and spotlight blue, the white script (typeset), Ray at the piano
std('ray-2004', ('grad', [(0, (60, 80, 110)), (.6, (16, 22, 32)), (1, (4, 6, 8))]), WHT,
    T('Ray', 'cho', 180, WHT),
    photo=ph(.4, .4, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JAMIE FOXX'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 22, 32), fcol=(190, 200, 214), fin=WORN, seed=2004)

# Shutter Island (2010): storm black and the match's glow, the red stencil capitals (typeset), Teddy's eyes
std('shutter-island-2010', ('grad', [(0, (50, 56, 60)), (.6, (16, 18, 20)), (1, (4, 4, 4))]), (210, 30, 30),
    T('SHUTTER ISLAND', 'hcnb', 84, (214, 32, 32), squeeze=.76, bold=.8, rough=.4),
    photo=ph(.5, .15, .5, 1.0), pb=(214, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['LEONARDO DiCAPRIO'], ccol=WHT,
    ft='a', vbox=(214, 32, 32), fcol=(200, 200, 204), fin=SLIP, seed=2010)

# Portrait of a Lady on Fire: Brittany night, the white handwriting (typeset), Héloïse with her dress alight
std('portrait-of-a-lady-on-fire-2019', ('grad', [(0, (40, 34, 30)), (.6, (14, 12, 10)), (1, (40, 16, 6))]), WHT,
    T('Portrait of a Lady on Fire', 'cho', 76, WHT),
    photo=ph(.5, .75, .45, 1.0), pb=(240, 160, 60), lg=WHT, lw=.6, order='LPTCF', credit=['A CÉLINE SCIAMMA', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 160, 60), vink=(14, 12, 10), fcol=(210, 200, 190), fin=MINT, dotst=(['STAFF', 'PICK'], (200, 60, 30)))

# The Great Dictator (1940): an old tape, the poster's lemon yellow, the red script Great and DICTATOR (typeset), Hynkel and the globe (no logo file: Chaplin's company in type)
std('the-great-dictator-1940', ('grad', [(0, (246, 236, 140)), (.6, (236, 220, 110)), (1, (160, 140, 60))]), (200, 30, 40),
    TT([('THE', (200, 30, 40)), ('Great', (200, 30, 40)), ('DICTATOR', (200, 30, 40))], 'hcnb', 80, sp=.2, squeeze=.8, bold=.6),
    photo=ph(.6, .2, .45, 1.0), pb=(200, 30, 40), studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=(40, 30, 20), order='lPTCSF', credit=['CHARLES CHAPLIN'], ccol=(40, 30, 20),
    stick=PRC(['$2.99', 'CLASSIC']), ft='e', fcol=(40, 30, 20), fin=OLD, seed=1940)

# Warriors of the Wind (1984): the US cut of Nausicaä, but the poster is Nausicaä's, so the spine is too: Ghibli sky blue, the white serif capitals (typeset), Nausicaä by the Ohmu
std('warriors-of-the-wind-1984', ('grad', [(0, (60, 140, 220)), (.5, (150, 200, 230)), (1, (190, 170, 130))]), WHT,
    [T('NAUSICAÄ', 'ter', 84, WHT, track=.06, outline=((30, 60, 120), 1.4)), T('OF THE VALLEY OF THE WIND', 'ter', 26, WHT, track=.08, outline=((30, 60, 120), 1.0))], tgap=8,
    photo=ph(.6, .38, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A HAYAO MIYAZAKI', 'FILM'], ccol=(30, 50, 90),
    stick=flow(dot, 70, ['ANIME'], (220, 60, 100), d=60), ft='a', vbox=(30, 50, 90), fcol=(30, 50, 90), fin=WORN, seed=1984)

# The Last Samurai (2003): the poster's ember orange, the copper serif capitals (typeset), Algren in armour
std('the-last-samurai-2003', ('grad', [(0, (220, 120, 70)), (.5, (130, 50, 30)), (1, (20, 8, 6))]), (240, 180, 130),
    [T('THE', 'ter', 30, (244, 186, 136), track=.4), T('LAST SAMURAI', 'ter', 76, (244, 186, 136), track=.1)], tgap=6,
    photo=ph(.4, .18, .4, 1.0), pb=(244, 186, 136), lg=WHT, lw=.6, order='LPTCF', credit=['TOM CRUISE', 'KEN WATANABE'], ccol=WHT,
    ft='a', vbox=(244, 186, 136), vink=(130, 50, 30), fcol=(240, 210, 190), fin=WORN, seed=2003)

# Das Boot (1981): an old tape, the North Atlantic blue, the white weathered capitals (typeset), the captain
std('das-boot-1981', ('grad', [(0, (40, 100, 160)), (.6, (16, 44, 76)), (1, (4, 12, 22))]), WHT,
    [T('DAS BOOT', 'bonb', 96, WHT, rough=.8), T('A WOLFGANG PETERSEN FILM', 'herb', 20, WHT, track=.2)], tgap=8,
    photo=ph(.5, .4, .55, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['JÜRGEN PROCHNOW'], ccol=WHT,
    stick=BAR('15 01981', top='WAR', fill=(236, 232, 214), ink=(30, 40, 60)), ft='e', fcol=(200, 210, 224), fin=OLD, seed=1981)

# City Lights (1931): an old tape, the poster's teal, the green brush lettering (typeset), the Tramp in the ring (no logo file: Chaplin's company in type)
std('city-lights-1931', ('grad', [(0, (60, 140, 160)), (.6, (30, 80, 100)), (1, (10, 26, 30))]), (60, 140, 60),
    T('City Lights', 'cho', 110, (90, 170, 80), outline=((240, 230, 140), 2.0)),
    photo=ph(.5, .25, .4, 1.0), pb=(240, 230, 140), studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['CHARLES CHAPLIN'], ccol=WHT,
    ft='e', fcol=(220, 230, 230), fin=OLD, seed=1931)

# Judgment at Nuremberg (1961): an old 2-tape box (191 minutes), black, white condensed capitals (typeset), the faces (no logo file: its distributor in type)
std('judgment-at-nuremberg-1961', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (4, 4, 4))]), WHT,
    [T('JUDGMENT AT', 'hcnb', 70, WHT, squeeze=.74, bold=.4), T('NUREMBERG', 'hcnb', 150, WHT, squeeze=.74, bold=.6)],
    photo=ph(.5, .35, .5, .5), pb=WHT, studio=['UNITED ARTISTS'], scol=WHT, order='lPTCSF', tgap=10, credit=['SPENCER TRACY', 'BURT LANCASTER'], ccol=WHT,
    stick=TWOST(WHT, (16, 16, 16)), ft='c', vbox=WHT, vink=(16, 16, 16), fcol=(200, 200, 200), fin=OLD, seed=1961, **TWO)

# To Be or Not to Be (1942): an old tape, the poster's yellow, the navy heavy capitals (typeset), Maria and Joseph (no logo file: its distributor in type)
std('to-be-or-not-to-be-1942', ('grad', [(0, (246, 236, 150)), (.6, (236, 222, 120)), (1, (160, 140, 70))]), (30, 40, 140),
    TT([('TO BE', (30, 40, 140)), ('or', (200, 30, 30)), ('NOT', (30, 40, 140)), ('to', (200, 30, 30)), ('BE', (30, 40, 140))], 'intbk', 74, sp=.18, squeeze=.84),
    photo=ph(.5, .3, .6, 1.0), pb=(30, 40, 140), studio=['UNITED ARTISTS'], scol=(30, 40, 140), order='lPTCF', credit=['CAROLE LOMBARD', 'JACK BENNY'], ccol=(30, 40, 140),
    ft='e', fcol=(30, 40, 140), fin=OLD, seed=1942)

# My Neighbor Totoro (1988): a Ghibli tape (a slipcase), the rainy forest green, the white serif capitals (typeset), Totoro at the bus stop
std('my-neighbor-totoro-1988', ('grad', [(0, (60, 90, 70)), (.6, (24, 40, 30)), (1, (8, 14, 10))]), WHT,
    [T('My Neighbor', 'ter', 40, WHT), T('TOTORO', 'terb', 100, WHT, track=.02)], tgap=6,
    photo=ph(.62, .55, .55, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A HAYAO MIYAZAKI', 'FILM'], ccol=WHT,
    stick=PRC(['$2.99', 'FAMILY']), ft='a', vbox=WHT, vink=(24, 40, 30), fcol=(210, 220, 214), fin=WORN, seed=1988)

# Deliverance (1972): an old tape, the river's pale blue, the navy heavy lettering (typeset), the hand and the rifle
std('deliverance-1972', ('grad', [(0, (210, 226, 236)), (.6, (170, 196, 214)), (1, (90, 110, 130))]), (30, 50, 130),
    T('Deliverance', 'intbk', 84, (30, 52, 134), squeeze=.86),
    photo=ph(.5, .5, .45, 1.0), pb=(30, 52, 134), lg=(30, 52, 134), lw=.6, order='LPTCSF', credit=['JON VOIGHT', 'BURT REYNOLDS'], ccol=(30, 52, 134),
    stick=PRC(['$1.99', 'THRILLER']), ft='e', fcol=(30, 52, 134), fin=OLD, seed=1972)

# Life of Brian (1979): an old tape, space black, the orange stone block capitals (typeset), the camels on the horizon
std('life-of-brian-1979', ('grad', [(0, (30, 30, 60)), (.6, (10, 10, 24)), (1, (4, 4, 8))]), (246, 160, 40),
    TT([('LIFE', (248, 170, 50)), ('of', (248, 210, 60)), ('BRIAN', (248, 170, 50))], 'bonb', 96, sp=.15, outline=((120, 40, 10), 1.8), shadow=((90, 30, 10), 4, 4)),
    photo=ph(.25, .7, .4, 1.0), pb=(248, 170, 50), lg=WHT, lw=.6, order='LPTCSF', credit=['GRAHAM CHAPMAN', 'JOHN CLEESE'], ccol=WHT,
    stick=flow(dot, 70, ['CULT'], (40, 120, 200), d=60), ft='e', fcol=(200, 200, 214), fin=OLD, seed=1979)

# Downfall (2004): Berlin smoke black, the red condensed capitals (typeset), Hitler in his cap
std('downfall-2004', ('grad', [(0, (60, 60, 60)), (.6, (20, 20, 20)), (1, (4, 4, 4))]), (220, 30, 30),
    T('DOWNFALL', 'hcnb', 104, (224, 32, 32), squeeze=.76, bold=.6),
    photo=ph(.5, .2, .45, 1.0), pb=(224, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['BRUNO GANZ'], ccol=WHT,
    ft='a', vbox=(224, 32, 32), fcol=(200, 200, 200), fin=WORN, seed=2004)

# The King of Kong: A Fistful of Quarters: the poster's arcade navy, orange curved capitals (typeset), Steve and Billy in their medallions
std('the-king-of-kong-a-fistful-of-quarters-2007', ('grad', [(0, (30, 70, 160)), (.6, (16, 34, 80)), (1, (6, 12, 30))]), (246, 160, 40),
    [T('THE KING OF KONG', 'intbk', 66, (248, 166, 46), squeeze=.86), T('A FISTFUL OF QUARTERS', 'herb', 24, (248, 166, 46), track=.1)], tgap=8,
    photo=ph(.5, .32, .7, .6), pb=(248, 166, 46), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(248, 166, 46), vink=(16, 34, 80), fcol=(200, 210, 230), fin=WORN, seed=2007)

# Cinema Paradiso (1988): the projection booth's black and gold, the gold art-deco lettering, Totò's smile
std('cinema-paradiso-1988', ('grad', [(0, (60, 40, 20)), (.6, (20, 14, 8)), (1, (4, 4, 2))]), (240, 214, 130),
    [T('cinema', 'cho', 50, (244, 218, 134)), T('PARADISO', 'adv', 84, (244, 218, 134), track=.08, bold=.4)], tgap=6,
    photo=ph(.6, .22, .5, 1.0), pb=(244, 218, 134), lg=WHT, lw=.6, order='LPTCSF', credit=['A GIUSEPPE TORNATORE', 'FILM'], ccol=(244, 218, 134),
    stick=RWD(fill=(250, 240, 220)), ft='a', vbox=(244, 218, 134), vink=(20, 14, 8), fcol=(210, 200, 180), fin=RENTAL, seed=1988)

# Sherlock Jr. (1924): an old tape, the sepia-white, dark condensed capitals (typeset), Buster with his book
std('sherlock-jr-1924', ('grad', [(0, (226, 222, 214)), (.6, (190, 184, 172)), (1, (100, 94, 84))]), (40, 40, 40),
    T('SHERLOCK, JR.', 'hcnb', 80, (40, 40, 40), squeeze=.8, bold=.4),
    photo=ph(.5, .45, .5, 1.0), pb=(40, 40, 40), lg=(40, 40, 40), lw=.6, order='LPTCF', credit=['BUSTER KEATON'], ccol=(40, 40, 40),
    ft='e', fcol=(40, 40, 40), fin=OLD, seed=1924)

# Andrei Rublev (1966): an old tape, the poster's white, thin spaced capitals (typeset), Rublev with his halo
std('andrei-rublev-1966', ('grad', [(0, (240, 238, 232)), (.6, (216, 212, 204)), (1, (140, 134, 124))]), (30, 30, 30),
    T('ANDREI RUBLEV', 'her', 60, (30, 30, 30), track=.4),
    photo=ph(.48, .2, .4, 1.0), pb=(30, 30, 30), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['AN ANDREI TARKOVSKY', 'FILM'], ccol=(30, 30, 30),
    ft='e', fcol=(30, 30, 30), fin=OLD, seed=1966)

# Cinderella Man (2005): the fight-night green, the cream serif (typeset), Jim and Mae
std('cinderella-man-2005', ('grad', [(0, (40, 70, 60)), (.6, (14, 26, 22)), (1, (4, 8, 6))]), (240, 230, 210),
    T('Cinderella Man', 'ter', 84, (242, 232, 212)),
    photo=ph(.4, .2, .5, 1.0), pb=(242, 232, 212), lg=WHT, lw=.6, order='LPTCF', credit=['RUSSELL CROWE', 'RENÉE ZELLWEGER'], ccol=(242, 232, 212),
    ft='a', vbox=(242, 232, 212), vink=(14, 26, 22), fcol=(200, 210, 204), fin=WORN, seed=2005)

# The Invisible Guest: the lake's grey-blue, thin spaced capitals (typeset), Adrián on the water
std('the-invisible-guest-2017', ('grad', [(0, (200, 212, 222)), (.6, (160, 176, 190)), (1, (90, 104, 118))]), (40, 50, 60),
    T('THE INVISIBLE GUEST', 'her', 56, (40, 50, 60), track=.25),
    photo=ph(.5, .32, .4, 1.0), pb=(40, 50, 60), lg=(40, 50, 60), lw=.6, order='LPTCF', credit=['AN ORIOL PAULO', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 50, 60), fcol=WHT, fin=SLIP)

# The Elephant Man (1980): an old tape, black, the white Victorian wood-type (typeset), John in his hood
std('the-elephant-man-1980', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (4, 4, 4))]), WHT,
    T('THE ELEPHANT MAN', 'bonb', 76, WHT, rough=.4),
    photo=ph(.4, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A DAVID LYNCH', 'FILM'], ccol=WHT,
    stick=BAR('15 01980', top='DRAMA', fill=(226, 220, 240), ink=(40, 30, 70)), ft='e', fcol=(200, 200, 200), fin=OLD, seed=1980)

# Midnight Cowboy (1969): an old tape, the poster's sunrise circles, the gold slab capitals (typeset), Ratso and Joe
std('midnight-cowboy-1969', ('grad', [(0, (240, 80, 120)), (.4, (200, 60, 140)), (.75, (60, 180, 160)), (1, (20, 40, 40))]), (250, 220, 120),
    T('MIDNIGHT COWBOY', 'bonb', 70, (252, 224, 124), outline=((60, 20, 30), 1.6)),
    photo=ph(.5, .65, .6, 1.0), pb=(252, 224, 124), lg=WHT, lw=.6, order='LPTCSF', credit=['DUSTIN HOFFMAN', 'JON VOIGHT'], ccol=WHT,
    stick=PRC(['$2.49', 'DRAMA']), ft='e', fcol=WHT, fin=OLD, seed=1969)

# Bound (1996): a real rental, black and white, the black heavy capitals (typeset), Violet and Corky
std('bound-1996', ('grad', [(0, (246, 244, 240)), (.6, (220, 216, 210)), (1, (140, 136, 130))]), (20, 18, 18),
    T('BOUND', 'intbk', 120, (20, 18, 18)),
    photo=ph(.5, .3, .6, 1.0), pb=(20, 18, 18), lg=(20, 18, 18), lw=.6, order='LPTCF', credit=['JENNIFER TILLY', 'GINA GERSHON'], ccol=(20, 18, 18),
    ft='a', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=RENTAL, seed=1996)

# Stalker (1979): an old tape, the Zone's sick green-grey, white heavy capitals (typeset), the three in the room
std('stalker-1979', ('grad', [(0, (150, 170, 150)), (.6, (80, 96, 80)), (1, (20, 26, 20))]), WHT,
    T('STALKER', 'intbk', 100, WHT),
    photo=ph(.45, .4, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AN ANDREI TARKOVSKY', 'FILM'], ccol=WHT,
    ft='e', fcol=(220, 226, 220), fin=OLD, seed=1979)

# The Gold Rush (1925): an old tape, the cabin's sepia, the yellow slab capitals (typeset), the Tramp (no logo file: Chaplin's company in type)
std('the-gold-rush-1925', ('grad', [(0, (130, 100, 50)), (.6, (70, 50, 24)), (1, (20, 14, 6))]), (246, 206, 60),
    T('THE GOLD RUSH', 'bonb', 80, (248, 210, 64)),
    photo=ph(.25, .35, .4, 1.0), pb=(248, 210, 64), studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=(248, 210, 64), order='lPTCF', credit=['CHARLES CHAPLIN'], ccol=WHT,
    ft='e', fcol=(230, 210, 180), fin=OLD, seed=1925)

# Modern Times (1936): an old tape, white, the black art-deco capitals (typeset), the Tramp's cogwheel eyes
std('modern-times-1936', ('grad', [(0, (246, 246, 244)), (.6, (222, 220, 216)), (1, (150, 146, 140))]), (20, 18, 18),
    T('MODERN TIMES', 'adv', 76, (20, 18, 18), track=.12, bold=.6),
    photo=ph(.5, .5, .55, 1.0), pb=(20, 18, 18), studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=(20, 18, 18), order='lPTCSF', credit=['CHARLES CHAPLIN'], ccol=(20, 18, 18),
    stick=PRC(['$1.99', 'COMEDY']), ft='e', fcol=(20, 18, 18), fin=OLD, seed=1936)

# The Passion of Joan of Arc (1928): an old tape, black, the pale stencil capitals (typeset), Joan's upturned face (no logo file: its company in type)
std('the-passion-of-joan-of-arc-1928', ('grad', [(0, (60, 60, 60)), (.6, (20, 20, 20)), (1, (4, 4, 4))]), (220, 216, 206),
    [T('THE PASSION OF', 'monob', 36, (222, 218, 208), track=.2), T('JOAN OF ARC', 'monob', 70, (222, 218, 208), track=.12)], tgap=8,
    photo=ph(.55, .3, .5, 1.0), pb=(222, 218, 208), studio=['SOCIÉTÉ GÉNÉRALE', 'DES FILMS'], scol=(222, 218, 208), order='lPTCF', credit=['A CARL TH. DREYER', 'FILM'], ccol=(222, 218, 208),
    ft='e', fcol=(200, 196, 190), fin=OLD, seed=1928)

# The Kid (1921): an old tape, the brick-wall grey, the white painted capitals (typeset), the Tramp and the Kid (no logo file: Chaplin's company in type)
std('the-kid-1921', ('grad', [(0, (110, 110, 108)), (.6, (50, 50, 48)), (1, (14, 14, 14))]), WHT,
    T('THE KID', 'bonb', 120, WHT, rough=.8),
    photo=ph(.25, .45, .4, 1.0), pb=WHT, studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['CHARLES CHAPLIN', 'JACKIE COOGAN'], ccol=WHT,
    ft='e', fcol=(210, 210, 206), fin=OLD, seed=1921)

# The Circus (1928): an old tape, the poster's circus orange, the red and navy capitals (typeset), the Tramp and the lion (no logo file: Chaplin's company in type)
std('the-circus-1928', ('grad', [(0, (240, 180, 60)), (.6, (210, 110, 40)), (1, (110, 40, 20))]), (190, 30, 30),
    TT([('THE', (30, 40, 120)), ('CIRCUS', (196, 32, 32))], 'bonb', 92, sp=.2),
    photo=ph(.6, .55, .5, 1.0), pb=(30, 40, 120), studio=['CHARLES CHAPLIN', 'PRODUCTIONS'], scol=(30, 40, 120), order='lPTCSF', credit=['CHARLES CHAPLIN'], ccol=(30, 40, 120),
    stick=flow(dot, 70, ['SILENT'], (30, 40, 120), d=62), ft='e', fcol=(40, 20, 10), fin=OLD, seed=1928)

# The General (1926): an old tape, the poster's sky blue, the red art-deco capitals (typeset), Buster on his engine (no logo file: Keaton's company in type)
std('the-general-1926', ('grad', [(0, (190, 214, 220)), (.6, (150, 180, 190)), (1, (70, 90, 100))]), (210, 40, 50),
    [T('The', 'cho', 50, (20, 20, 30)), T('GENERAL', 'adv', 92, (214, 42, 52), track=.06, bold=.5)], tgap=4,
    photo=ph(.4, .3, .5, 1.0), pb=(214, 42, 52), studio=['BUSTER KEATON', 'PRODUCTIONS'], scol=(20, 20, 30), order='lPTCF', credit=['BUSTER KEATON'], ccol=(20, 20, 30),
    ft='e', fcol=(20, 20, 30), fin=OLD, seed=1926)

# Rang De Basanti (2006): monsoon sky, the white-and-saffron script (typeset), the friends leaping
std('rang-de-basanti-2006', ('grad', [(0, (150, 180, 210)), (.6, (90, 110, 120)), (1, (20, 30, 20))]), WHT,
    TT([('Rang De', WHT), ('Basanti', (246, 170, 40))], 'cho', 92, sp=.15, outline=((40, 40, 60), 1.4)),
    photo=ph(.5, .65, .7, .7), pb=(246, 170, 40), lg=WHT, lw=.6, order='LPTCF', credit=['AAMIR KHAN'], ccol=WHT,
    ft='a', vbox=(246, 170, 40), vink=(90, 110, 120), fcol=WHT, fin=WORN, seed=2006)

# Hamilton: the poster's gold, black wide serif capitals (typeset), Hamilton on the star
std('hamilton-2025', ('grad', [(0, (236, 180, 60)), (.6, (210, 150, 40)), (1, (120, 80, 20))]), (20, 18, 16),
    T('HAMILTON', 'ter', 80, (20, 18, 16), track=.25),
    photo=ph(.5, .27, .3, 1.0), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCF', credit=['LIN-MANUEL MIRANDA'], ccol=(20, 18, 16),
    ft='a', vbox=(20, 18, 16), fcol=(20, 18, 16), fin=MINT)

# Ben-Hur (1959): an old 2-tape box (212 minutes), the poster's gold, the stone block capitals (typeset), the chariots
std('ben-hur-1959', ('grad', [(0, (240, 190, 70)), (.6, (210, 150, 40)), (1, (110, 70, 20))]), (60, 56, 56),
    T('BEN-HUR', 'bonb', 160, (230, 226, 220), outline=((50, 40, 30), 2.4), shadow=((60, 40, 20), 5, 5)),
    photo=ph(.5, .72, .8, .4), pb=(50, 40, 30), lg=(50, 40, 30), lw=.5, order='LPTCSF', tgap=10, credit=['CHARLTON HESTON'], ccol=(50, 40, 30),
    stick=TWOST((50, 40, 30), (240, 190, 70)), ft='c', vbox=(50, 40, 30), fcol=(50, 40, 30), fin=OLD, seed=1959, **TWO)

# Dangal: the Haryana lane's dust, white heavy capitals (typeset), Mahavir and his daughters
std('dangal-2016', ('grad', [(0, (190, 160, 120)), (.6, (110, 80, 50)), (1, (30, 20, 12))]), WHT,
    T('DANGAL', 'intbk', 110, WHT, rough=.4),
    photo=ph(.5, .35, .8, .8), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AAMIR KHAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 80, 50), fcol=(240, 226, 210), fin=SLIP)

# Grindhouse (2007): a 2-tape double bill (191 minutes), the poster's torn red and cream, the red stencil capitals (typeset), the two features
std('grindhouse-2007', ('grad', [(0, (230, 220, 190)), (.6, (200, 180, 150)), (1, (120, 90, 60))]), (190, 30, 30),
    [T('GRINDHOUSE', 'hcnb', 150, (196, 32, 32), squeeze=.76, bold=.8, rough=.6), T('PLANET TERROR  ·  DEATH PROOF', 'hcnb', 40, (20, 18, 16), track=.08)],
    photo=ph(.5, .5, .9, .4), pb=(196, 32, 32), lg=(20, 18, 16), lw=.5, order='LPTCSF', tgap=10, credit=['QUENTIN TARANTINO', 'ROBERT RODRIGUEZ'], ccol=(20, 18, 16),
    stick=TWOST((196, 32, 32), WHT), ft='c', vbox=(196, 32, 32), fcol=(20, 18, 16), fin=RENTAL, seed=2007, **TWO)

# Witness (1985): a real rental, black, the red heavy capitals (typeset), John Book
std('witness-1985', ('grad', [(0, (60, 40, 30)), (.6, (20, 14, 10)), (1, (4, 4, 4))]), (220, 50, 30),
    T('WITNESS', 'intbk', 100, (224, 54, 32)),
    photo=ph(.5, .2, .45, 1.0), pb=(224, 54, 32), lg=WHT, lw=.6, order='LPTCF', credit=['HARRISON FORD'], ccol=WHT,
    ft='a', vbox=(224, 54, 32), fcol=(210, 200, 196), fin=RENTAL, seed=1985)

# Anand (1971): an old tape, the poster's orange, the blue ornamented serif (typeset), Anand smiling in the flowers (no logo file: its company in type)
std('anand-1971', ('solid', (240, 90, 20)), (30, 50, 170),
    T('Anand', 'pagb', 120, (30, 50, 176), outline=((250, 230, 200), 1.6)),
    photo=ph(.5, .62, .5, 1.0), pb=(30, 50, 176), studio=['RUPAM CHITRA'], scol=(30, 50, 176), order='lPTCF', credit=['RAJESH KHANNA', 'AMITABH BACHCHAN'], ccol=(30, 30, 40),
    ft='e', fcol=(30, 30, 40), fin=OLD, seed=1971)

# Hachi: A Dog's Tale (2009): the garden's green, white serif (typeset), Hachi
std('hachi-a-dog-s-tale-2009', ('grad', [(0, (90, 130, 70)), (.6, (40, 60, 30)), (1, (10, 16, 8))]), WHT,
    [T('HACHI', 'ter', 90, WHT, track=.1), T("A DOG'S TALE", 'ter', 40, WHT, track=.06)], tgap=6,
    photo=ph(.68, .55, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['RICHARD GERE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 60, 30), fcol=(220, 230, 210), fin=SLIP, seed=2009)

# Come and See (1985): an old tape, the poster's sky blue and khaki, the pale stencil capitals (typeset), Flyora's face
std('come-and-see-1985', ('grad', [(0, (150, 190, 210)), (.5, (80, 90, 70)), (1, (20, 24, 18))]), (190, 214, 214),
    T('COME AND SEE', 'hcnb', 84, (196, 220, 220), squeeze=.86, rough=.6, outline=((30, 40, 40), 1.2)),
    photo=ph(.5, .32, .5, 1.0), pb=(196, 220, 220), lg=WHT, lw=.6, order='LPTCSF', credit=['AN ELEM KLIMOV', 'FILM'], ccol=WHT,
    stick=BAR('15 01985', top='WAR', fill=(240, 230, 200), ink=(60, 40, 20)), ft='e', fcol=(220, 226, 220), fin=OLD, seed=1985)

# The Bandit (1996): Istanbul night black, white spaced capitals (typeset), Baran (no logo file: its company in type)
std('the-bandit-1996', ('grad', [(0, (60, 40, 30)), (.6, (20, 14, 10)), (1, (4, 4, 4))]), WHT,
    [T('THE', 'her', 30, WHT, track=.6), T('BANDIT', 'her', 76, WHT, track=.5)], tgap=8,
    photo=ph(.5, .38, .45, 1.0), pb=WHT, studio=['ARTCAM', 'INTERNATIONAL'], scol=WHT, order='lPTCF', credit=['ŞENER ŞEN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 14, 10), fcol=(210, 200, 196), fin=WORN, seed=1996)

# Shithouse: the poster's orange, the cream fat capitals with the grawlix (typeset), Alex and Maggie (no logo file: its company in type)
std('shithouse-2020', ('grad', [(0, (230, 100, 50)), (.6, (190, 60, 40)), (1, (80, 20, 14))]), (250, 232, 200),
    T('S#!%HOUSE', 'intbk', 92, (252, 234, 204), squeeze=.86),
    photo=ph(.55, .7, .55, 1.0), pb=(252, 234, 204), studio=['CMR PRODUCTIONS'], scol=(252, 234, 204), order='lPTCF', credit=['A COOPER RAIFF', 'FILM'], ccol=(252, 234, 204),
    ft='a', vbox=(252, 234, 204), vink=(190, 60, 40), fcol=(252, 234, 204), fin=MINT)

# Dangerous Days: Making Blade Runner: a 2-tape box (214 minutes), Los Angeles 2019 black and the refinery fire, white serif capitals (typeset)
std('dangerous-days-making-blade-runner-2007', ('grad', [(0, (40, 34, 30)), (.6, (14, 12, 10)), (1, (4, 4, 4))]), WHT,
    [T('DANGEROUS DAYS', 'ter', 110, WHT, track=.04), T('MAKING BLADE RUNNER', 'ter', 40, (230, 160, 70), track=.3)],
    photo=ph(.5, .16, .9, .3), pb=(230, 160, 70), lg=WHT, lw=.5, order='LPTCSF', tgap=10, credit=['A DOCUMENTARY'], ccol=WHT,
    stick=TWOST((230, 160, 70), (14, 12, 10)), ft='c', vbox=WHT, vink=(14, 12, 10), fcol=(200, 196, 190), fin=SLIP, seed=2007, **TWO)

# The Mole: Undercover in North Korea: the red-and-blue split, yellow heavy capitals (typeset), Ulrich
std('the-mole-undercover-in-north-korea-2020', ('grad', [(0, (200, 40, 50)), (.5, (60, 90, 150)), (1, (16, 24, 50))]), (250, 220, 40),
    [T('THE MOLE', 'intbk', 92, (250, 222, 44), squeeze=.86), T('UNDERCOVER IN NORTH KOREA', 'herb', 22, (250, 222, 44), track=.08)], tgap=8,
    photo=ph(.5, .18, .5, 1.0), pb=(250, 222, 44), lg=WHT, lw=.6, order='LPTCF', credit=['A MADS BRÜGGER', 'FILM'], ccol=WHT,
    ft='a', vbox=(250, 222, 44), vink=(60, 90, 150), fcol=WHT, fin=MINT)

# Kajillionaire: the poster's blush pink, black wide capitals (typeset), Old Dolio
std('kajillionaire-2020', ('grad', [(0, (246, 220, 214)), (.6, (236, 200, 196)), (1, (190, 150, 146))]), (30, 28, 28),
    T('KAJILLIONAIRE', 'intbk', 70, (30, 28, 28), track=.06),
    photo=ph(.5, .45, .45, 1.0), pb=(30, 28, 28), lg=(30, 28, 28), lw=.6, order='LPTCF', credit=['EVAN RACHEL WOOD'], ccol=(30, 28, 28),
    ft='a', vbox=(30, 28, 28), fcol=(30, 28, 28), fin=MINT)

# The Firm (1993): a real rental, black, white serif capitals (typeset), Mitch's face
std('the-firm-1993', ('grad', [(0, (60, 60, 70)), (.6, (18, 18, 22)), (1, (4, 4, 6))]), WHT,
    [T('THE', 'ter', 40, WHT, track=.2), T('FIRM', 'ter', 120, WHT)], tgap=6,
    photo=ph(.55, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['TOM CRUISE', 'GENE HACKMAN'], ccol=WHT,
    stick=PRC(['3 NIGHTS', '$2.49']), ft='a', vbox=WHT, vink=(18, 18, 22), fcol=(200, 200, 206), fin=RENTAL, seed=1993)

# Borat Subsequent Moviefilm: White House lawn green, the yellow Cyrillic-style capitals (typeset), Borat and Tutar (no logo file: the studio in type)
std('borat-subsequent-moviefilm-delivery-of-prodigious-bribe-to-american-regime-for-make-benefit-once-glorious-nation-of-kazakhstan-2020', ('grad', [(0, (120, 170, 200)), (.5, (80, 130, 60)), (1, (20, 40, 14))]), (240, 200, 30),
    [T('BORAT', 'intbk', 100, (242, 204, 34), outline=((60, 50, 10), 1.6)), T('SUBSEQUENT MOVIEFILM', 'intbk', 30, (242, 204, 34), outline=((60, 50, 10), 1.0))], tgap=8,
    photo=ph(.38, .3, .45, 1.0), pb=(242, 204, 34), studio=['AMAZON STUDIOS'], scol=WHT, order='lPTCF', credit=['SACHA BARON COHEN', 'MARIA BAKALOVA'], ccol=WHT,
    ft='a', vbox=(242, 204, 34), vink=(20, 40, 14), fcol=WHT, fin=MINT)

# Holiday: the Riviera's pale sea, the magenta wide capitals (typeset), Sascha on the bow
std('holiday-2018', ('grad', [(0, (220, 240, 236)), (.6, (150, 210, 210)), (1, (60, 120, 130))]), (220, 30, 190),
    T('HOLIDAY', 'intbk', 90, (224, 34, 196), track=.3),
    photo=ph(.5, .62, .45, 1.0), pb=(224, 34, 196), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['AN ISABELLA EKLÖF', 'FILM'], ccol=(30, 30, 30),
    ft='a', vbox=(224, 34, 196), fcol=(30, 30, 30), fin=MINT)

# Quiz: the falling-cash confetti teal, the yellow heavy capitals (typeset), Charles with his head in his hands
std('quiz-2020', ('grad', [(0, (40, 90, 110)), (.6, (16, 34, 44)), (1, (4, 10, 14))]), (246, 200, 40),
    T('QUIZ', 'intbk', 130, (248, 204, 44)),
    photo=ph(.55, .35, .55, 1.0), pb=(248, 204, 44), lg=WHT, lw=.6, order='LPTCF', credit=['THE COMPLETE', 'SERIES'], ccol=(248, 204, 44),
    ft='a', vbox=(248, 204, 44), vink=(16, 34, 44), fcol=(196, 210, 214), fin=MINT)

# You Were Never Really Here: the bokeh red-gold, white spaced capitals (typeset), Joe with the hammer
std('you-were-never-really-here-2017', ('grad', [(0, (180, 80, 30)), (.5, (80, 40, 20)), (1, (20, 30, 20))]), WHT,
    T('YOU WERE NEVER REALLY HERE', 'hcnb', 60, WHT, track=.25),
    photo=ph(.5, .2, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JOAQUIN PHOENIX'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 40, 20), fcol=(230, 210, 196), fin=SLIP)

# The Fresh Prince of Bel-Air Reunion: grey with the poster's neon green and pink graffiti lettering (typeset), the cast
std('the-fresh-prince-of-bel-air-reunion-2020', ('grad', [(0, (200, 196, 190)), (.6, (120, 116, 110)), (1, (30, 28, 26))]), (120, 240, 60),
    [TT([('Fresh', (130, 246, 70)), ('Prince', (130, 246, 70))], 'intbki', 76, sp=.15, outline=((240, 80, 200), 2.4)), T('of Bel-Air  REUNION', 'herbi', 34, (40, 220, 220), outline=((40, 20, 60), 1.2))], tgap=8,
    photo=ph(.5, .8, .9, .6), pb=(240, 80, 200), lg=(30, 28, 26), lw=.6, order='LPTCF', credit=['WILL SMITH'], ccol=WHT,
    ft='a', vbox=(240, 80, 200), fcol=WHT, fin=MINT)


# =====================================================================================
# the 2017 shelf (films-2017.json).  Same approach as 2019-2021: titles mostly typeset (each
# comment says so), credits and typed labels from IMDb (17 Nov 2026).  Finding Dory (Pixar) is a clamshell;
# Rogue One (Lucasfilm) is a slipcase like the Marvel films.
# =====================================================================================

# Elle: black, the cream distressed capitals, Michèle at the edge of the frame
std('elle-2016', ('grad', [(0, (50, 46, 44)), (.6, (18, 16, 16)), (1, (4, 4, 4))]), (236, 226, 210),
    L((0.5, 0.225, 0.93, 0.405), 130, (238, 228, 212), mode='light', speck=.02),
    photo=ph(.15, .3, .3, 1.0), pb=(200, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['ISABELLE HUPPERT'], ccol=(238, 228, 212),
    ft='a', vbox=(200, 40, 40), fcol=(200, 196, 190), fin=SLIP)

# The Night Of: the city at night from above, white spaced capitals, the streets
std('the-night-of-2016', ('grad', [(0, (50, 56, 54)), (.6, (16, 20, 18)), (1, (4, 6, 6))]), WHT,
    L((0.06, 0.56, 0.96, 0.615), 64, WHT, mode='light'),
    photo=ph(.5, .3, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['THE COMPLETE', 'SERIES'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 20, 18), fcol=(190, 200, 196), fin=MINT)

# Alone in the Wilderness (2004): Twin Lakes' mountains, the white serif lettering, Dick by his cabin (no logo file: its company in type)
std('alone-in-the-wilderness-2004', ('grad', [(0, (110, 150, 200)), (.5, (60, 90, 60)), (1, (20, 30, 16))]), WHT,
    L([(0.34, 0.02, 0.89, 0.115), (0.47, 0.115, 0.67, 0.165), (0.09, 0.155, 0.955, 0.25)], 66, WHT, mode='key', key=(252, 252, 252), t=(15, 45), speck=.03),
    photo=ph(.55, .7, .5, 1.0), pb=WHT, studio=['BOB SWERER', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['DICK PROENNEKE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 90, 60), fcol=(220, 230, 214), fin=WORN, seed=2004)

# Weiner: the tabloid grey, the red heavy capitals, Anthony on the street
std('weiner-2016', ('grad', [(0, (220, 220, 218)), (.6, (170, 170, 168)), (1, (80, 80, 78))]), (220, 40, 40),
    L((0.08, 0.82, 0.97, 0.92), 110, (222, 42, 42), mode='key', key=(228, 60, 60), t=(70, 150)),
    photo=ph(.5, .22, .45, 1.0), pb=(222, 42, 42), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(30, 30, 30),
    ft='a', vbox=(222, 42, 42), fcol=WHT, fin=MINT)

# Finding Dory: a Pixar clamshell.  Ocean blue, the poster's white FINDING DORY cut off it, Dory in the diamond
disney('finding-dory-2016', ('grad', [(0, (40, 140, 220)), (.5, (20, 80, 170)), (1, (6, 30, 80))]), fin=dict(CLAM, vivid=.25),
       title=LC([(0.2, 0.32, 0.82, 0.46)], 150, cuts=[key_cut(lambda a: (_lum(a) > .78) & (_sat(a) < .25))]),
       face=ph(.55, .53, .2, 1.4), lcol=WHT)

# Hunt for the Wilderpeople: the bush green, the white antler lettering, Ricky and Hec
std('hunt-for-the-wilderpeople-2016', ('grad', [(0, (110, 160, 120)), (.6, (50, 80, 50)), (1, (14, 24, 14))]), WHT,
    L((0.0, 0.875, 1.0, 0.99), 76, WHT, mode='light'),
    photo=ph(.6, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A TAIKA WAITITI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(50, 80, 50), fcol=(220, 230, 214), fin=MINT, dotst=(['STAFF', 'PICK'], (230, 120, 30)))

# True Story: black and white, the yellow stencil capitals, Christian and Michael
std('true-story-2015', ('grad', [(0, (70, 70, 70)), (.6, (24, 24, 24)), (1, (6, 6, 6))]), (240, 200, 40),
    L((0.0, 0.81, 0.99, 0.935), 96, (242, 204, 44), mode='key', key=(236, 196, 40), t=(70, 150)),
    photo=ph(.5, .35, .8, .6), pb=(242, 204, 44), lg=WHT, lw=.6, order='LPTCF', credit=['JONAH HILL', 'JAMES FRANCO'], ccol=WHT,
    ft='a', vbox=(242, 204, 44), vink=(24, 24, 24), fcol=(200, 200, 200), fin=SLIP)

# Sour Grapes: the poster's art-deco bottles, cream and wine red, the red-on-cream SOUR GRAPES (no logo file: its company in type)
std('sour-grapes-2016', ('grad', [(0, (240, 220, 190)), (.5, (200, 120, 90)), (1, (60, 20, 20))]), (190, 40, 30),
    L([(0.12, 0.41, 0.48, 0.505), (0.13, 0.515, 0.49, 0.6)], 76, (194, 44, 32), mode='key', key=(200, 50, 40), t=(110, 190)),
    photo=ph(.5, .12, .7, .6), pb=(194, 44, 32), studio=['METFILM', 'PRODUCTION'], scol=(60, 30, 20), order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(194, 44, 32), fcol=WHT, fin=MINT)

# Manchester by the Sea: the harbour's winter blue, the slate thin capitals, Lee and Randi
std('manchester-by-the-sea-2016', ('grad', [(0, (210, 226, 236)), (.6, (170, 190, 204)), (1, (100, 116, 130))]), (50, 70, 90),
    [L((0.1, 0.09, 0.9, 0.175), 64, (52, 72, 92), mode='dark'), L((0.38, 0.17, 0.91, 0.245), 34, (52, 72, 92), mode='dark')], tgap=6,
    photo=ph(.5, .65, .6, 1.0), pb=(52, 72, 92), lg=(52, 72, 92), lw=.6, order='LPTCF', credit=['CASEY AFFLECK', 'MICHELLE WILLIAMS'], ccol=(52, 72, 92),
    ft='a', vbox=(52, 72, 92), fcol=(40, 50, 60), fin=MINT)

# Moonlight: the poster's blue and violet, thin white glowing capitals, the three faces as one
std('moonlight-2016', ('grad', [(0, (60, 120, 200)), (.5, (110, 70, 170)), (1, (20, 20, 50))]), WHT,
    L((0.06, 0.82, 0.94, 0.91), 76, WHT, mode='light'),
    photo=ph(.5, .3, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A BARRY JENKINS', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 70, 170), fcol=(220, 220, 240), fin=MINT)

# Arrival: Montana mist grey, the spaced thin capitals, Louise
std('arrival-2016', ('grad', [(0, (180, 186, 186)), (.6, (100, 106, 104)), (1, (30, 32, 30))]), WHT,
    L((0.06, 0.89, 0.96, 0.945), 76, WHT, mode='light'),
    photo=ph(.55, .25, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['AMY ADAMS', 'JEREMY RENNER'], ccol=WHT,
    ft='a', vbox=WHT, vink=(100, 106, 104), fcol=(220, 226, 224), fin=MINT)

# The Girl on the Train: the rain-streaked window's teal, white spaced capitals, Rachel at the glass
std('the-girl-on-the-train-2016', ('grad', [(0, (60, 100, 100)), (.6, (20, 36, 36)), (1, (6, 10, 10))]), WHT,
    L((0.06, 0.565, 0.94, 0.61), 50, WHT, mode='light'),
    photo=ph(.7, .2, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['EMILY BLUNT'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 36, 36), fcol=(200, 214, 214), fin=MINT)

# Captain Fantastic: the Pacific Northwest sky, white stencil capitals, the family by the bus
std('captain-fantastic-2016', ('grad', [(0, (90, 140, 200)), (.6, (60, 80, 100)), (1, (40, 24, 20))]), WHT,
    L([(0.19, 0.105, 0.84, 0.195), (0.14, 0.195, 0.89, 0.285)], 76, WHT, mode='key', key=(250, 250, 250), t=(50, 110), grow=.2, gapf=.4),
    photo=ph(.4, .7, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['VIGGO MORTENSEN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 80, 100), fcol=(220, 220, 226), fin=MINT)

# The Founder: the arches' red and yellow, cream condensed capitals, Ray in his suit
std('the-founder-2016', ('solid', (210, 30, 30)), (250, 236, 210),
    L([(0.12, 0.13, 0.195, 0.18), (0.185, 0.12, 0.87, 0.25)], 96, [(250, 200, 40), (250, 236, 210)], mode='light'),
    photo=ph(.5, .55, .4, 1.0), pb=(250, 200, 40), lg=WHT, lw=.6, order='LPTCF', credit=['MICHAEL KEATON'], ccol=(250, 200, 40),
    ft='a', vbox=(250, 200, 40), vink=(210, 30, 30), fcol=(250, 236, 210), fin=MINT, under=[frame((250, 200, 40), 8, 2.4)])

# Aguirre, the Wrath of God (1972): an old tape, the jungle's dark green, the yellow gothic capitals, Aguirre in his helmet
std('aguirre-the-wrath-of-god-1972', ('grad', [(0, (60, 80, 70)), (.6, (20, 30, 24)), (1, (6, 8, 6))]), (226, 220, 50),
    [L((0.28, 0.075, 0.72, 0.195), 84, (230, 224, 54), mode='key', key=(228, 214, 60), t=(70, 150)), L((0.3, 0.193, 0.71, 0.245), 36, (230, 224, 54), mode='key', key=(228, 214, 60), t=(70, 150))], tgap=6,
    photo=ph(.3, .72, .45, 1.0), pb=(230, 224, 54), lg=WHT, lw=.6, order='LPTCSF', credit=['KLAUS KINSKI', 'A WERNER HERZOG FILM'], ccol=(230, 224, 54),
    stick=PRC(['$2.99', 'FOREIGN']), ft='e', fcol=(200, 210, 200), fin=OLD, seed=1972)

# Betting on Zero: blender white, the green heavy capitals, the cash in the jug
std('betting-on-zero-2016', ('grad', [(0, (244, 244, 240)), (.6, (220, 222, 216)), (1, (150, 160, 150))]), (30, 130, 60),
    L([(0.29, 0.812, 0.69, 0.868), (0.28, 0.865, 0.71, 0.92)], 70, (30, 132, 62), mode='light'),
    photo=ph(.5, .2, .5, 1.0), pb=(30, 132, 62), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 132, 62), fcol=(30, 30, 30), fin=MINT)

# Paterson: the bedroom's dark blue, the white handwriting, Paterson and Laura asleep
std('paterson-2016', ('grad', [(0, (40, 50, 80)), (.6, (14, 18, 30)), (1, (4, 6, 10))]), WHT,
    L((0.24, 0.8, 0.76, 0.895), 100, WHT, mode='light'),
    photo=ph(.55, .45, .55, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A JIM JARMUSCH', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 18, 30), fcol=(190, 196, 214), fin=MINT)

# Hacksaw Ridge: the smoke's grey-white, dark spaced capitals, Desmond carrying a man
std('hacksaw-ridge-2016', ('grad', [(0, (226, 228, 224)), (.6, (196, 200, 194)), (1, (130, 136, 130))]), (40, 44, 40),
    L([(0.28, 0.445, 0.71, 0.505), (0.36, 0.515, 0.64, 0.58)], 64, (40, 44, 40), mode='light', grow=.08),
    photo=ph(.55, .18, .45, 1.0), pb=(40, 44, 40), lg=(40, 44, 40), lw=.6, order='LPTCF', credit=['ANDREW GARFIELD'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 44, 40), fcol=WHT, fin=SLIP)

# Eating You Alive: the prescription-pad grey, black and white heavy capitals, the fork in the O (no logo file: its company in type)
std('eating-you-alive-2016', ('grad', [(0, (200, 204, 204)), (.6, (150, 156, 156)), (1, (60, 120, 50))]), (20, 20, 20),
    L([(0.14, 0.045, 0.85, 0.215), (0.19, 0.215, 0.86, 0.415), (0.13, 0.44, 0.9, 0.66)], 92, [(20, 20, 20), WHT, (20, 20, 20)], mode=['key', 'light', 'key'], key=(25, 25, 25), t=(60, 130)),
    photo=ph(.12, .89, .2, 1.0), pb=(20, 20, 20), studio=['SMALLBOX', 'ENTERTAINMENT'], scol=(20, 20, 20), order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(20, 20, 20), fcol=WHT, fin=MINT)

# Wonder Woman: the Themysciran sunset orange, white spaced capitals, Diana with her sword
std('wonder-woman-2017', ('grad', [(0, (240, 170, 70)), (.5, (200, 90, 40)), (1, (60, 20, 14))]), WHT,
    L((0.1, 0.76, 0.92, 0.83), 66, WHT, mode='light'),
    photo=ph(.5, .45, .45, 1.0), pb=(230, 190, 90), lg=WHT, lw=.6, order='LPTCF', credit=['GAL GADOT', 'CHRIS PINE'], ccol=WHT,
    ft='a', vbox=(230, 190, 90), vink=(200, 90, 40), fcol=WHT, fin=SLIP)

# The Bad Kids: black, the photo-filled THE BAD KIDS cut off the poster in its own colours (no picture: the poster is all title) (no logo file: the label in type)
std('the-bad-kids-2016', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), (220, 60, 70),
    LC([(0.02, 0.15, 0.98, 0.48), (0.02, 0.48, 0.98, 0.81)], 150, gapf=.12, cuts=[fill_cut(), fill_cut()]),
    studio=['LOW KEY PICTURES'], scol=WHT, order='lTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 14, 16), fcol=(190, 190, 196), fin=MINT)

# Rogue One: A Star Wars Story (Lucasfilm, a slipcase like the Marvel films): Scarif blue-grey, the framed ROGUE ONE / A STAR WARS STORY logo lifted off the poster (copper there, cream here), Jyn
std('rogue-one-a-star-wars-story-2016', ('grad', [(0, (120, 150, 160)), (.6, (40, 56, 66)), (1, (10, 14, 18))]), (230, 220, 200),
    L((0.225, 0.728, 0.775, 0.803), 120, (232, 222, 202), mode='key', key=(123, 76, 51), t=(100, 170), speck=0), tgap=8,
    photo=ph(.48, .2, .4, 1.0), pb=(232, 222, 202), lg=WHT, lw=.6, order='LPTCF', credit=['FELICITY JONES', 'DIEGO LUNA'], ccol=(232, 222, 202),
    ft='a', vbox=(232, 222, 202), vink=(40, 56, 66), fcol=(200, 210, 214), fin=SLIP)

# Jim & Andy: The Great Beyond: the poster's beige, white heavy capitals, Jim upside down
std('jim-andy-the-great-beyond-featuring-a-very-special-contractually-obligated-mention-of-tony-clifton-2017', ('grad', [(0, (220, 200, 170)), (.6, (190, 160, 130)), (1, (110, 80, 60))]), WHT,
    [L((0.16, 0.755, 0.84, 0.84), 84, WHT, mode='light', outline=((90, 60, 40), 1.4)), L((0.34, 0.84, 0.66, 0.875), 26, (60, 40, 30), mode='light')], tgap=8,
    photo=ph(.5, .35, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(60, 40, 30),
    ft='a', vbox=WHT, vink=(110, 80, 60), fcol=WHT, fin=MINT)

# Cameraperson: black, the cream condensed capitals, the road through the trees
std('cameraperson-2016', ('grad', [(0, (40, 44, 36)), (.6, (14, 16, 12)), (1, (4, 4, 4))]), (230, 226, 210),
    L((0.15, 0.745, 0.85, 0.845), 84, (232, 228, 212), mode='light'),
    photo=ph(.5, .45, .55, 1.0), pb=(232, 228, 212), lg=WHT, lw=.6, order='LPTCF', credit=['A KIRSTEN JOHNSON', 'FILM'], ccol=(232, 228, 212),
    ft='a', vbox=(232, 228, 212), vink=(14, 16, 12), fcol=(190, 196, 186), fin=MINT)

# Logan Lucky: the poster's cream and the race-car yellow, the yellow-over-red italic capitals (keyed off the cream), the Logans on the car
std('logan-lucky-2017', ('grad', [(0, (236, 232, 220)), (.6, (220, 214, 196)), (1, (160, 150, 120))]), (210, 30, 30),
    L((0.07, 0.807, 0.95, 0.885), 90, (214, 32, 32), mode='nkey', key=(228, 224, 210), t=(25, 70), grad=[(0, (244, 186, 30)), (.5, (244, 186, 30)), (.52, (226, 32, 26)), (1, (226, 32, 26))]),
    photo=ph(.5, .35, .8, .7), pb=(214, 32, 32), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['CHANNING TATUM', 'ADAM DRIVER'], ccol=(30, 30, 30),
    ft='a', vbox=(214, 32, 32), fcol=(30, 30, 30), fin=MINT)


# =====================================================================================
# the 2018 shelf (films-2018.json).  Same approach as 2017.  Coco, Incredibles 2 and the short Bao
# (Pixar) are clamshells; The Last Jedi (Lucasfilm) and the Marvel films are slipcases.
# =====================================================================================

# Tokyo Idols: Akihabara pink and neon, the pink TOKYO IDOLS cut off the poster in its own pink-to-orange (the idol stands in front of the O, so it keeps her outline), the idol on stage
std('tokyo-idols-2017', ('grad', [(0, (230, 80, 170)), (.5, (120, 60, 160)), (1, (30, 30, 80))]), (250, 110, 190),
    LC([(0.06, 0.13, 0.94, 0.272), (0.08, 0.29, 0.86, 0.43)], 100, outline=(WHT, 1.6), cuts=[key_cut(lambda a: (_sat(a) > .5) & (_lum(a) > .35) & (a[..., 0] > .8))] * 2),
    photo=ph(.5, .62, .4, 1.0), pb=(250, 230, 60), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(250, 230, 60), vink=(120, 60, 160), fcol=WHT, fin=MINT)

# The Florida Project: the motel sky's teal, the white script, Moonee running
std('the-florida-project-2017', ('grad', [(0, (90, 180, 190)), (.6, (60, 140, 160)), (1, (200, 150, 180))]), WHT,
    [L((0.17, 0.25, 0.8, 0.475), 120, WHT, mode='key', key=(250, 250, 250), t=(25, 60)), L((0.19, 0.465, 0.85, 0.635), 100, WHT, mode='key', key=(250, 250, 250), t=(25, 60))], tgap=4,
    photo=ph(.6, .86, .5, 1.0), pb=(240, 120, 180), lg=WHT, lw=.6, order='LPTCF', credit=['A SEAN BAKER', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 120, 180), fcol=WHT, fin=MINT)

# Coco: a Pixar clamshell.  The Land of the Dead's violet, the poster's papel-picado COCO cut off it, Dante in the diamond
disney('coco-2017', ('grad', [(0, (90, 60, 140)), (.5, (50, 30, 90)), (1, (20, 14, 40))]), fin=dict(CLAM, vivid=.25),
       title=LC([(0.14, 0.8, 0.86, 0.9)], 150, cuts=[key_cut(lambda a: (_sat(a) > .45) & (_lum(a) > .3))]),
       face=ph(.73, .32, .2, 1.4), lcol=WHT)

# Darkest Hour: black, the white heavy condensed capitals, Churchill with his cigar
std('darkest-hour-2017', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (4, 4, 4))]), WHT,
    L((0.13, 0.775, 0.87, 0.85), 96, WHT, mode='light'),
    photo=ph(.42, .2, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['GARY OLDMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 16, 16), fcol=(200, 200, 200), fin=MINT)

# My Friend Dahmer: the poster's faded cream, the red heavy capitals, Jeff in his glasses
std('my-friend-dahmer-2017', ('grad', [(0, (236, 226, 214)), (.6, (220, 206, 190)), (1, (160, 140, 120))]), (200, 40, 40),
    L([(0.59, 0.575, 0.95, 0.612), (0.57, 0.608, 0.97, 0.68)], 92, (204, 44, 44), mode='key', key=(200, 50, 50), t=(70, 150)),
    photo=ph(.62, .27, .3, 1.0), pb=(204, 44, 44), lg=(50, 40, 30), lw=.6, order='LPTCF', credit=['ROSS LYNCH'], ccol=(50, 40, 30),
    ft='a', vbox=(204, 44, 44), fcol=(50, 40, 30), fin=MINT)

# Murder on the Orient Express (2017): the dining car's teal night, pale blue spaced capitals, Poirot
std('murder-on-the-orient-express-2017', ('grad', [(0, (40, 80, 100)), (.6, (14, 30, 40)), (1, (4, 10, 14))]), (150, 210, 230),
    [L((0.06, 0.06, 0.93, 0.14), 50, (156, 214, 234), mode='light'), L((0.06, 0.14, 0.94, 0.2), 40, (156, 214, 234), mode='light')],
    photo=ph(.25, .42, .4, 1.0), pb=(156, 214, 234), lg=WHT, lw=.6, order='LPTCF', credit=['KENNETH BRANAGH', 'PENÉLOPE CRUZ'], ccol=WHT,
    ft='a', vbox=(156, 214, 234), vink=(14, 30, 40), fcol=(190, 210, 220), fin=MINT)

# Three Billboards Outside Ebbing, Missouri: the Missouri dusk, red stencil THREE BILLBOARDS, the billboards
std('three-billboards-outside-ebbing-missouri-2017', ('grad', [(0, (40, 50, 70)), (.6, (16, 20, 30)), (1, (60, 20, 14))]), (226, 70, 50),
    [L((0.29, 0.37, 0.99, 0.5), 130, (230, 74, 52), mode='light', cut=(.2, .5)), L((0.455, 0.5, 0.82, 0.66), 90, (230, 74, 52), mode='light', cut=(.2, .5), speck=0)], tgap=8,
    photo=ph(.5, .82, .9, .6), pb=(230, 74, 52), lg=WHT, lw=.6, order='LPTCF', credit=['FRANCES McDORMAND'], ccol=WHT,
    ft='a', vbox=(230, 74, 52), fcol=(200, 200, 210), fin=MINT)

# Call Me by Your Name: the poster's flat blue, the yellow handwriting, Elio and Oliver
std('call-me-by-your-name-2017', ('solid', (30, 100, 200)), (246, 220, 40),
    L((0.05, 0.09, 0.95, 0.345), 170, (248, 222, 44), mode='key', key=(232, 222, 50), t=(70, 150)),
    photo=ph(.4, .8, .6, 1.0), pb=(248, 222, 44), lg=WHT, lw=.6, order='LPTCF', credit=['TIMOTHÉE CHALAMET', 'ARMIE HAMMER'], ccol=WHT,
    ft='a', vbox=(248, 222, 44), vink=(30, 100, 200), fcol=WHT, fin=MINT)

# Lady Bird: the poster's white with the stained-glass border, the red blackletter, Christine
std('lady-bird-2017', ('grad', [(0, (244, 242, 236)), (.6, (226, 222, 214)), (1, (170, 160, 150))]), (176, 30, 30),
    L((0.08, 0.06, 0.9, 0.19), 100, (180, 32, 32), mode='key', key=(190, 40, 40), t=(70, 150)),
    photo=ph(.62, .58, .4, 1.0), pb=(180, 32, 32), lg=(40, 30, 30), lw=.6, order='LPTCF', credit=['A GRETA GERWIG', 'FILM'], ccol=(40, 30, 30),
    ft='a', vbox=(180, 32, 32), fcol=(40, 30, 30), fin=MINT, under=[frame((60, 120, 180), 8, 2.0)])

# Spider-Man: Homecoming: Queens sky blue, red SPIDER-MAN and the script Homecoming, Peter crouched
std('spider-man-homecoming-2017', ('grad', [(0, (130, 180, 220)), (.5, (60, 90, 140)), (1, (20, 24, 40))]), (220, 40, 40),
    [L((0.13, 0.86, 0.78, 0.917), 80, (224, 44, 44), mode='light', outline=((20, 20, 30), 1.8)), L((0.22, 0.913, 0.71, 0.955), 40, WHT, mode='light')], tgap=6,
    photo=ph(.35, .55, .45, 1.0), pb=(224, 44, 44), lg=WHT, lw=.6, order='LPTCF', credit=['TOM HOLLAND'], ccol=WHT,
    ft='a', vbox=(224, 44, 44), fcol=(210, 220, 236), fin=SLIP)

# I, Tonya: the rink-wall white, the pink heavy capitals, Tonya in her costume
std('i-tonya-2017', ('grad', [(0, (246, 244, 244)), (.6, (226, 222, 224)), (1, (170, 160, 166))]), (230, 40, 110),
    L((0.04, 0.095, 0.93, 0.208), 104, (232, 44, 114), mode='key', key=(230, 50, 120), t=(70, 150)),
    photo=ph(.4, .45, .45, 1.0), pb=(232, 44, 114), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['MARGOT ROBBIE'], ccol=(30, 30, 30),
    ft='a', vbox=(232, 44, 114), fcol=(30, 30, 30), fin=MINT)

# The Shape of Water: underwater teal, the pale serif capitals, Elisa and the creature
std('the-shape-of-water-2017', ('grad', [(0, (40, 120, 120)), (.6, (14, 50, 54)), (1, (4, 16, 18))]), (210, 230, 220),
    L((0.15, 0.827, 0.86, 0.88), 66, (214, 234, 224), mode='key', key=(195, 199, 168), t=(50, 110)),
    photo=ph(.5, .5, .5, 1.0), pb=(214, 234, 224), lg=WHT, lw=.6, order='LPTCF', credit=['A GUILLERMO DEL TORO', 'FILM'], ccol=(214, 234, 224),
    ft='a', vbox=(214, 234, 224), vink=(14, 50, 54), fcol=(190, 210, 206), fin=MINT)

# Get Out: the poster's black and white split, its heavy capitals lifted (GET white off the black half, OUT black off the white half), Chris in the chair
std('get-out-2017', ('grad', [(0, (60, 60, 60)), (.6, (18, 18, 18)), (1, (4, 4, 4))]), WHT,
    L([(0.145, 0.105, 0.491, 0.178), (0.497, 0.105, 0.846, 0.178)], 120, WHT, mode=['key', 'dark'], key=(245, 245, 245), t=(40, 90), gapf=.12),
    photo=ph(.45, .35, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A JORDAN PEELE', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(18, 18, 18), fcol=(200, 200, 200), fin=MINT, dotst=(['STAFF', 'PICK'], (200, 40, 40)))

# The Keepers: the old photo's black, the cream serif, Sister Cathy
std('the-keepers-2017', ('grad', [(0, (50, 46, 40)), (.6, (18, 16, 14)), (1, (4, 4, 4))]), (240, 232, 200),
    L([(0.26, 0.035, 0.62, 0.145), (0.05, 0.14, 0.93, 0.27)], 100, (242, 234, 202), mode='key', key=(250, 250, 210), t=(22, 45)),
    photo=ph(.48, .45, .4, 1.0), pb=(242, 234, 202), lg=WHT, lw=.6, order='LPTCF', credit=['THE COMPLETE', 'DOCUSERIES'], ccol=(242, 234, 202),
    ft='a', vbox=(242, 234, 202), vink=(18, 16, 14), fcol=(200, 196, 186), fin=MINT)

# The Imposter (2012): the arrivals hall's blue-grey, white heavy capitals, the hooded figure
std('the-imposter-2012', ('grad', [(0, (60, 80, 110)), (.6, (20, 28, 40)), (1, (4, 6, 10))]), WHT,
    L([(0.06, 0.835, 0.16, 0.865), (0.06, 0.86, 0.95, 0.955)], 92, WHT, mode='light', valign='base'), tgap=6,
    photo=ph(.5, .45, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A BART LAYTON', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 28, 40), fcol=(190, 200, 214), fin=SLIP)

# A Murder in the Park: black and blood red, the poster's red and white condensed capitals cut off its dark band in their own colours, Anthony's face (no logo file: its company in type)
std('a-murder-in-the-park-2015', ('grad', [(0, (60, 40, 36)), (.6, (20, 12, 10)), (1, (4, 2, 2))]), (220, 30, 30),
    LC([(0.06, 0.625, 0.94, 0.695)], 84, cuts=[key_cut(lambda a: ((_lum(a) > .68) & (_sat(a) < .22)) | ((_sat(a) > .38) & (a[..., 0] > .42) & (a[..., 0] > a[..., 1] * 1.6)))]),
    photo=ph(.6, .18, .5, 1.0), pb=(224, 32, 32), studio=['TRANSITION', 'STUDIOS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(224, 32, 32), fcol=(200, 196, 196), fin=MINT)

# Amanda Knox: her face's warm grey, white spaced capitals, her eyes
std('amanda-knox-2016', ('grad', [(0, (150, 130, 120)), (.6, (80, 66, 60)), (1, (24, 20, 18))]), WHT,
    L((0.06, 0.55, 0.95, 0.615), 66, WHT, mode='key', key=(250, 250, 250), t=(30, 80), speck=0),
    photo=ph(.5, .37, .7, .45), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 66, 60), fcol=(230, 220, 214), fin=MINT)

# The Witness (2015): the torn newsprint white, grey spaced capitals, Kitty's portrait (no logo file: its company in type)
std('the-witness-2015', ('grad', [(0, (236, 236, 232)), (.6, (210, 210, 206)), (1, (140, 140, 136))]), (60, 60, 60),
    L([(0.21, 0.428, 0.29, 0.447), (0.21, 0.447, 0.81, 0.512)], 76, (60, 60, 60), mode='key', key=(250, 250, 250), t=(18, 40), speck=0), tgap=6,
    photo=ph(.55, .24, .4, 1.0), pb=(60, 60, 60), studio=['FIVE MORE MINUTES', 'PRODUCTIONS'], scol=(60, 60, 60), order='lPTCF', credit=['A DOCUMENTARY'], ccol=(60, 60, 60),
    ft='a', vbox=(60, 60, 60), fcol=(30, 30, 30), fin=MINT)

# Annihilation: the Shimmer's violet-blue, white spaced capitals, Lena in the light
std('annihilation-2018', ('grad', [(0, (30, 40, 90)), (.5, (60, 50, 140)), (1, (8, 10, 24))]), WHT,
    L((0.09, 0.865, 0.91, 0.935), 66, WHT, mode='light'),
    photo=ph(.5, .65, .5, 1.0), pb=(160, 200, 255), lg=WHT, lw=.6, order='LPTCF', credit=['AN ALEX GARLAND', 'FILM'], ccol=WHT,
    ft='a', vbox=(160, 200, 255), vink=(30, 40, 90), fcol=(200, 206, 230), fin=MINT)

# Film Stars Don't Die in Liverpool: the lamplit amber, cream wide capitals, Gloria's blonde hair
std('film-stars-don-t-die-in-liverpool-2017', ('grad', [(0, (150, 100, 50)), (.6, (60, 36, 18)), (1, (14, 8, 4))]), (246, 236, 210),
    [L((0.04, 0.255, 0.96, 0.343), 58, (248, 238, 212), mode='key', key=(234, 234, 220), t=(22, 50)), L([(0.04, 0.462, 0.96, 0.518), (0.04, 0.635, 0.96, 0.725)], 40, (248, 238, 212), mode='key', key=(234, 234, 220), t=(22, 50), speck=0, gapf=.6)], tgap=8,
    photo=ph(.5, .9, .4, 1.0), pb=(248, 238, 212), lg=WHT, lw=.6, order='LPTCF', credit=['ANNETTE BENING', 'JAMIE BELL'], ccol=(248, 238, 212),
    ft='a', vbox=(248, 238, 212), vink=(60, 36, 18), fcol=(220, 206, 190), fin=MINT)

# Phantom Thread: the House of Woodcock's black, the pale serif capitals, Alma in the gown
std('phantom-thread-2017', ('grad', [(0, (60, 60, 60)), (.6, (20, 20, 20)), (1, (4, 4, 4))]), (230, 226, 216),
    L([(0.23, 0.78, 0.8, 0.845), (0.23, 0.84, 0.8, 0.905)], 72, (232, 228, 218), mode='light'),
    photo=ph(.55, .38, .4, 1.0), pb=(232, 228, 218), lg=WHT, lw=.6, order='LPTCF', credit=['DANIEL DAY-LEWIS', 'VICKY KRIEPS'], ccol=(232, 228, 218),
    ft='a', vbox=(232, 228, 218), vink=(20, 20, 20), fcol=(200, 200, 196), fin=MINT)

# The Post: the newsroom's dusk, white heavy lower case, Kay at the typewriter
std('the-post-2017', ('grad', [(0, (60, 70, 70)), (.6, (22, 26, 26)), (1, (6, 8, 8))]), WHT,
    L((0.045, 0.08, 0.65, 0.165), 100, WHT, mode='light'),
    photo=ph(.7, .4, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['MERYL STREEP', 'TOM HANKS'], ccol=WHT,
    ft='a', vbox=WHT, vink=(22, 26, 26), fcol=(200, 206, 206), fin=MINT)

# The Commuter: the train's blue, white italic condensed capitals, Michael on the platform
std('the-commuter-2018', ('grad', [(0, (60, 90, 130)), (.6, (20, 30, 50)), (1, (6, 8, 14))]), WHT,
    L((0.13, 0.5, 0.88, 0.605), 84, WHT, mode='light'),
    photo=ph(.45, .12, .35, 1.0), pb=(240, 190, 50), lg=WHT, lw=.6, order='LPTCF', credit=['LIAM NEESON'], ccol=WHT,
    ft='a', vbox=(240, 190, 50), vink=(20, 30, 50), fcol=(196, 206, 220), fin=MINT)

# We Need to Talk About Kevin (2011): black, the small red line and white heavy KEVIN, Eva and Kevin
std('we-need-to-talk-about-kevin-2011', ('grad', [(0, (50, 40, 36)), (.6, (16, 12, 10)), (1, (4, 4, 4))]), WHT,
    [L((0.13, 0.2, 0.87, 0.235), 28, (226, 60, 50), mode='light'), L((0.13, 0.235, 0.87, 0.355), 110, WHT, mode='light')], tgap=6,
    photo=ph(.5, .62, .6, .8), pb=(226, 60, 50), lg=WHT, lw=.6, order='LPTCF', credit=['TILDA SWINTON', 'JOHN C. REILLY'], ccol=WHT,
    ft='a', vbox=(226, 60, 50), fcol=(200, 196, 196), fin=SLIP, seed=2011)

# Andre the Giant: the old photo's amber, the gold GIANT lifted off the poster (ANDRE THE typeset: it sits on his skin, the same gold), Andre with his arms folded
std('andre-the-giant-2018', ('grad', [(0, (120, 90, 50)), (.6, (50, 36, 20)), (1, (14, 10, 6))]), (230, 210, 100),
    [T('ANDRE THE', 'hcnb', 40, (234, 214, 104), squeeze=.8), L((0.08, 0.605, 0.93, 0.835), 120, (234, 214, 104), mode='key', key=(222, 206, 110), t=(45, 95), close=2)], tgap=6,
    photo=ph(.5, .15, .45, 1.0), pb=(234, 214, 104), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(234, 214, 104),
    ft='a', vbox=(234, 214, 104), vink=(50, 36, 20), fcol=(220, 206, 186), fin=MINT)

# The Cheshire Murders (2013): white, the black typewriter capitals, the house in the snapshot
std('the-cheshire-murders-2013', ('grad', [(0, (244, 244, 242)), (.6, (222, 222, 218)), (1, (150, 150, 146))]), (30, 30, 30),
    [L((0.345, 0.682, 0.46, 0.714), 28, (30, 30, 30), mode='dark', speck=0), L([(0.2, 0.712, 0.74, 0.768), (0.255, 0.767, 0.79, 0.82)], 56, (30, 30, 30), mode='dark')], tgap=6,
    photo=ph(.5, .33, .55, 1.0), pb=(30, 30, 30), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 30, 30), fcol=(30, 30, 30), fin=SLIP)

# Mercury 13: the poster's night navy, the rocket and the orange smoke, the black serif on cream
std('mercury-13-2018', ('grad', [(0, (20, 24, 70)), (.6, (10, 12, 40)), (1, (4, 4, 16))]), (240, 236, 220),
    L((0.1, 0.885, 0.9, 0.965), 80, (20, 20, 24), mode='dark', plate=((242, 238, 224), 10, 6)),
    photo=ph(.5, .4, .55, 1.0), pb=(240, 120, 50), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(240, 120, 50), vink=(10, 12, 40), fcol=(200, 200, 220), fin=MINT)

# Before Sunrise (1995): a real rental, the poster's cream, the gold spaced serif capitals, Jesse and Céline
std('before-sunrise-1995', ('grad', [(0, (244, 236, 214)), (.6, (230, 220, 194)), (1, (170, 150, 120))]), (190, 150, 70),
    L([(0.27, 0.2, 0.75, 0.255), (0.27, 0.255, 0.75, 0.31)], 66, (150, 110, 40), mode='key', key=(170, 130, 60), t=(60, 120)),
    photo=ph(.5, .72, .6, 1.0), pb=(192, 152, 72), lg=(60, 50, 40), lw=.6, order='LPTCSF', credit=['ETHAN HAWKE', 'JULIE DELPY'], ccol=(60, 50, 40),
    stick=flow(dot, 70, ['ROMANCE'], (200, 60, 80), d=62), ft='a', vbox=(192, 152, 72), fcol=(60, 50, 40), fin=RENTAL, seed=1995)

# Before Midnight (2013): the Peloponnese sky, the white and gold serif capitals cut off the poster in their own colours, Jesse and Céline walking
std('before-midnight-2013', ('grad', [(0, (60, 120, 160)), (.6, (40, 70, 60)), (1, (14, 20, 14))]), WHT,
    LC([(0.17, 0.11, 0.83, 0.195), (0.09, 0.193, 0.91, 0.28)], 76, gapf=.25, cuts=[key_cut(lambda a: (_lum(a) > .82) & (_sat(a) < .2)), key_cut(lambda a: (_sat(a) > .45) & (a[..., 0] > .65) & (a[..., 2] < .45))]),
    photo=ph(.5, .6, .55, 1.0), pb=(240, 200, 60), lg=WHT, lw=.6, order='LPTCF', credit=['ETHAN HAWKE', 'JULIE DELPY'], ccol=WHT,
    ft='a', vbox=(240, 200, 60), vink=(40, 70, 60), fcol=(210, 220, 210), fin=SLIP)

# Before Sunset (2004): the Seine at sunset, gold serif, Jesse and Céline by the river
std('before-sunset-2004', ('grad', [(0, (40, 30, 20)), (.5, (110, 70, 20)), (1, (14, 10, 6))]), (240, 200, 60),
    L((0.22, 0.135, 0.78, 0.275), 140, (242, 202, 64), mode='light'),
    photo=ph(.5, .52, .7, .7), pb=(242, 202, 64), lg=WHT, lw=.6, order='LPTCF', credit=['ETHAN HAWKE', 'JULIE DELPY'], ccol=(242, 202, 64),
    ft='a', vbox=(242, 202, 64), vink=(40, 30, 20), fcol=(220, 206, 180), fin=WORN, seed=2004)

# The Rachel Divide: the silhouette's black and white, the red condensed capitals (no logo file: the label in type)
std('the-rachel-divide-2018', ('grad', [(0, (40, 40, 40)), (.6, (14, 14, 14)), (1, (4, 4, 4))]), (200, 40, 40),
    [L((0.26, 0.195, 0.4, 0.23), 40, (204, 44, 44), mode='light', speck=0), L((0.09, 0.23, 0.56, 0.345), 90, (204, 44, 44), mode='key', key=(190, 40, 40), t=(70, 150))], tgap=6,
    photo=ph(.45, .7, .5, 1.0), pb=WHT, studio=['NETFLIX'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(204, 44, 44), fcol=(200, 200, 200), fin=MINT)

# Malcolm X (1992): an old 2-tape box (202 minutes), the poster's red X on grey, white thin capitals, Malcolm
std('malcolm-x-1992', ('grad', [(0, (200, 30, 30)), (.6, (120, 16, 16)), (1, (30, 4, 4))]), WHT,
    L((0.01, 0.15, 1.0, 0.25), 150, WHT, mode='key', key=(250, 250, 250), t=(25, 60)),
    photo=ph(.5, .6, .8, .5), pb=WHT, lg=WHT, lw=.5, order='LPTCSF', tgap=10, credit=['DENZEL WASHINGTON', 'A SPIKE LEE JOINT'], ccol=WHT,
    stick=TWOST(WHT, (120, 16, 16)), ft='c', vbox=WHT, vink=(120, 16, 16), fcol=(240, 210, 206), fin=RENTAL, seed=1992, **TWO)

# Star Wars: The Last Jedi (Lucasfilm, a slipcase): the poster's red, the black STAR WARS logo cut off it (THE LAST JEDI typeset: its thin red line is lost against the red), Luke
std('star-wars-the-last-jedi-2017', ('grad', [(0, (200, 30, 30)), (.6, (110, 14, 14)), (1, (20, 4, 4))]), (20, 18, 18),
    [LC([(0.26, 0.64, 0.72, 0.81)], 150), T('THE LAST JEDI', 'herb', 30, WHT, track=.25)], tgap=8,
    photo=ph(.5, .12, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['DAISY RIDLEY', 'MARK HAMILL'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 14, 14), fcol=(240, 210, 206), fin=SLIP)

# A Fantastic Woman: the poster's pink-to-blue light, white condensed capitals, Marina
std('a-fantastic-woman-2017', ('grad', [(0, (60, 70, 200)), (.5, (220, 70, 120)), (1, (240, 130, 70))]), WHT,
    L((0.08, 0.85, 0.92, 0.93), 76, WHT, mode='key', key=(250, 250, 250), t=(25, 60)),
    photo=ph(.6, .4, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['DANIELA VEGA'], ccol=WHT,
    ft='a', vbox=WHT, vink=(220, 70, 120), fcol=WHT, fin=MINT)

# Everybody Wants Some!! (2016): the 1980 front lawn, the cream-and-orange script cut off the poster in its own colours, the team piled up
std('everybody-wants-some-2016', ('grad', [(0, (150, 180, 200)), (.5, (110, 100, 70)), (1, (40, 30, 20))]), (246, 140, 40),
    LC([(0.08, 0.78, 0.93, 0.945)], 130, cuts=[key_cut(lambda a: ((_sat(a) > .5) & (a[..., 0] > .7)) | ((_lum(a) > .88) & (_sat(a) < .15)))]),
    photo=ph(.5, .55, .7, .7), pb=(248, 146, 44), lg=WHT, lw=.6, order='LPTCF', credit=['A RICHARD LINKLATER', 'FILM'], ccol=WHT,
    ft='a', vbox=(248, 146, 44), vink=(40, 30, 20), fcol=WHT, fin=SLIP)

# The Purge (2013): black and violet, the white distressed capitals, the grinning mask
std('the-purge-2013', ('grad', [(0, (60, 40, 80)), (.6, (20, 12, 28)), (1, (4, 2, 6))]), WHT,
    [L((0.13, 0.035, 0.87, 0.09), 40, WHT, mode='light'), L((0.14, 0.095, 0.9, 0.215), 110, WHT, mode='light')], tgap=6,
    photo=ph(.6, .6, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['ETHAN HAWKE', 'LENA HEADEY'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 12, 28), fcol=(200, 196, 210), fin=SLIP)

# Bloodsport (1988): a real rental, the Kumite's black, the red brush script, Frank in his fighting stance
std('bloodsport-1988', ('grad', [(0, (50, 30, 26)), (.6, (18, 10, 8)), (1, (4, 2, 2))]), (220, 50, 40),
    L((0.04, 0.1, 0.96, 0.245), 110, (224, 54, 42), mode='key', key=(210, 50, 40), t=(70, 150)),
    photo=ph(.45, .35, .5, 1.0), pb=(224, 54, 42), lg=WHT, lw=.6, order='LPTCSF', credit=['JEAN-CLAUDE VAN DAMME'], ccol=WHT,
    stick=BAR('15 01988', top='ACTION', fill=(250, 220, 200), ink=(80, 30, 20)), ft='a', vbox=(224, 54, 42), fcol=(200, 190, 186), fin=RENTAL, seed=1988)

# Good Time: Queens night, the poster's scan-lined neon GOOD TIME cut off it in its own red and white, Connie in the jar
std('good-time-2017', ('grad', [(0, (60, 20, 50)), (.6, (20, 8, 20)), (1, (4, 2, 4))]), (120, 240, 90),
    LC([(0.08, 0.835, 0.91, 0.93)], 100, cuts=[key_cut(lambda a: ((_sat(a) > .5) & (a[..., 0] > .6)) | (_lum(a) > .78))]),
    photo=ph(.5, .2, .4, 1.0), pb=(130, 246, 100), lg=WHT, lw=.6, order='LPTCF', credit=['ROBERT PATTINSON'], ccol=WHT,
    ft='a', vbox=(130, 246, 100), vink=(20, 8, 20), fcol=(200, 190, 200), fin=MINT)

# Playtime (1967): an old tape, the poster's grey-white grid, the green deco PlayTime, Hulot in the lobby
std('playtime-1967', ('grad', [(0, (236, 234, 226)), (.6, (216, 214, 204)), (1, (150, 146, 136))]), (40, 140, 110),
    L((0.19, 0.815, 0.77, 0.935), 100, (42, 144, 112), mode='key', key=(40, 150, 120), t=(60, 130)),
    photo=ph(.85, .72, .35, 1.0), pb=(42, 144, 112), lg=(40, 40, 40), lw=.6, order='LPTCSF', credit=['A JACQUES TATI', 'FILM'], ccol=(40, 40, 40),
    stick=PRC(['$2.99', 'COMEDY']), ft='e', fcol=(40, 40, 40), fin=OLD, seed=1967)

# Red Sparrow: the poster's red, white spaced condensed capitals (typeset: on the poster they climb at an angle across her coat), Dominika
std('red-sparrow-2018', ('grad', [(0, (200, 30, 30)), (.6, (100, 12, 12)), (1, (20, 4, 4))]), WHT,
    T('RED SPARROW', 'hcnb', 84, WHT, squeeze=.74, track=.2),
    photo=ph(.55, .15, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JENNIFER LAWRENCE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(100, 12, 12), fcol=(240, 210, 206), fin=MINT)

# Thoroughbreds: the lawn's cream, black spaced serif capitals, Lily and Amanda
std('thoroughbreds-2018', ('grad', [(0, (240, 230, 216)), (.6, (220, 206, 190)), (1, (110, 140, 90))]), (30, 30, 30),
    L((0.04, 0.07, 0.95, 0.13), 64, (30, 30, 30), mode='dark'),
    photo=ph(.6, .3, .45, 1.0), pb=(200, 40, 40), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['OLIVIA COOKE', 'ANYA TAYLOR-JOY'], ccol=(30, 30, 30),
    ft='a', vbox=(200, 40, 40), fcol=(30, 30, 30), fin=MINT)

# Ready Player One: the OASIS's electric blue, the outlined white capitals (typeset: the chrome logo sits in the crowd's glare and a cut loses letters), the crowd
std('ready-player-one-2018', ('grad', [(0, (40, 60, 150)), (.5, (90, 60, 170)), (1, (14, 16, 40))]), WHT,
    T('READY PLAYER ONE', 'popb', 66, (40, 60, 150), outline=(WHT, 2.4), soft=((120, 160, 255), 6, .5)),
    photo=ph(.5, .25, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['A STEVEN SPIELBERG', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(40, 60, 150), fcol=(200, 206, 230), fin=SLIP)

# Isle of Dogs: the poster's white, the red slab capitals, Atari and the dogs in their cage
std('isle-of-dogs-2018', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (150, 140, 130))]), (190, 40, 40),
    L((0.14, 0.765, 0.86, 0.86), 80, (194, 42, 42), mode='key', key=(190, 50, 40), t=(70, 150)),
    photo=ph(.4, .3, .55, 1.0), pb=(194, 42, 42), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['A WES ANDERSON', 'FILM'], ccol=(30, 30, 30),
    ft='a', vbox=(194, 42, 42), fcol=(30, 30, 30), fin=MINT, dotst=(['STAFF', 'PICK'], (30, 30, 30)))

# Super Troopers 2: the orange sunset, the gold badge logo cut off the poster in its own colours, the troopers and the flag
std('super-troopers-2-2018', ('grad', [(0, (240, 150, 40)), (.5, (180, 80, 20)), (1, (50, 20, 6))]), (240, 200, 80),
    LC([(0.1, 0.45, 0.9, 0.81)], 150),
    photo=ph(.6, .2, .6, 1.0), pb=(244, 206, 86), lg=WHT, lw=.6, order='LPTCF', credit=['JAY CHANDRASEKHAR', 'KEVIN HEFFERNAN'], ccol=WHT,
    ft='a', vbox=(244, 206, 86), vink=(180, 80, 20), fcol=WHT, fin=MINT)

# The Tale: the motel's marbled brown, white spaced capitals, Jennifer and young Jenny
std('the-tale-2018', ('grad', [(0, (150, 120, 80)), (.6, (80, 60, 36)), (1, (24, 18, 10))]), WHT,
    [L((0.49, 0.06, 0.69, 0.105), 34, WHT, mode='light'), L((0.49, 0.11, 0.9, 0.19), 100, WHT, mode='light')], tgap=6,
    photo=ph(.5, .72, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['LAURA DERN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 60, 36), fcol=(230, 220, 204), fin=MINT)

# Tully: Marlo's tired face, the pink script with its sticker stars (typeset: the script is pink on her pink skin and tilted; every lift lost letters)
std('tully-2018', ('grad', [(0, (200, 170, 150)), (.6, (130, 100, 90)), (1, (50, 36, 30))]), (240, 100, 160),
    T('Tully', 'cho', 150, (244, 110, 170), outline=(WHT, 1.4)),
    photo=ph(.4, .55, .5, 1.0), pb=(244, 110, 170), lg=WHT, lw=.6, order='LPTCF', credit=['CHARLIZE THERON'], ccol=WHT,
    ft='a', vbox=(244, 110, 170), fcol=WHT, fin=MINT)

# Black Panther: Wakanda's night teal, the silver-blue BLACK PANTHER cut off the poster in its own colours, T'Challa at the head
std('black-panther-2018', ('grad', [(0, (40, 90, 120)), (.6, (14, 30, 44)), (1, (4, 8, 14))]), (190, 200, 230),
    LC([(0.27, 0.73, 0.7, 0.8), (0.18, 0.79, 0.82, 0.91)], 100, gapf=.2),
    photo=ph(.5, .12, .35, 1.0), pb=(196, 206, 236), lg=WHT, lw=.6, order='LPTCF', credit=['CHADWICK BOSEMAN'], ccol=WHT,
    ft='a', vbox=(196, 206, 236), vink=(14, 30, 44), fcol=(190, 200, 210), fin=SLIP)

# Blade Runner 2049: the orange haze and the blue neon, the fiery BLADE RUNNER 2049 cut off the poster in its own colours, K
std('blade-runner-2049-2017', ('grad', [(0, (50, 70, 90)), (.5, (180, 80, 30)), (1, (30, 14, 6))]), (246, 140, 40),
    LC([(0.15, 0.73, 0.85, 0.96)], 150),
    photo=ph(.35, .15, .45, 1.0), pb=(248, 146, 44), lg=WHT, lw=.6, order='LPTCF', credit=['RYAN GOSLING', 'HARRISON FORD'], ccol=WHT,
    ft='a', vbox=(248, 146, 44), vink=(30, 14, 6), fcol=(220, 206, 200), fin=SLIP)

# American Animals: the poster's flat orange, cream heavy condensed capitals, the four in their animal masks
std('american-animals-2018', ('solid', (220, 80, 40)), (250, 236, 210),
    [L((0.07, 0.15, 0.94, 0.3), 90, (252, 238, 212), mode='key', key=(250, 242, 222), t=(40, 90)), L((0.07, 0.3, 0.94, 0.446), 90, (252, 238, 212), mode='key', key=(250, 242, 222), t=(40, 90))],
    photo=ph(.45, .7, .5, 1.0), pb=(252, 238, 212), lg=WHT, lw=.6, order='LPTCF', credit=['A BART LAYTON', 'FILM'], ccol=(252, 238, 212),
    ft='a', vbox=(252, 238, 212), vink=(220, 80, 40), fcol=(252, 238, 212), fin=MINT)

# Eighth Grade: the phone-glow pink, the yellow heavy capitals, Kayla
std('eighth-grade-2018', ('grad', [(0, (240, 210, 210)), (.6, (210, 150, 150)), (1, (120, 60, 60))]), (246, 230, 30),
    [L((0.05, 0.415, 0.93, 0.55), 84, (248, 232, 34), mode='key', key=(248, 232, 30), t=(60, 130), outline=((120, 60, 60), 1.4)), L((0.05, 0.55, 0.93, 0.685), 84, (248, 232, 34), mode='key', key=(248, 232, 30), t=(60, 130), outline=((120, 60, 60), 1.4))],
    photo=ph(.7, .2, .45, 1.0), pb=(248, 232, 34), lg=WHT, lw=.6, order='LPTCF', credit=['A BO BURNHAM', 'FILM'], ccol=(60, 30, 30),
    ft='a', vbox=(248, 232, 34), vink=(120, 60, 60), fcol=WHT, fin=MINT)

# BlacKkKlansman: the flag's black and white stripes, the black italic capitals, Ron in his coat
std('blackkklansman-2018', ('grad', [(0, (244, 244, 242)), (.6, (222, 222, 218)), (1, (150, 150, 146))]), (20, 20, 20),
    L((0.07, 0.03, 0.96, 0.105), 76, (20, 20, 20), mode='dark'),
    photo=ph(.5, .4, .45, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['A SPIKE LEE', 'JOINT'], ccol=(20, 20, 20),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=MINT, under=[frame((200, 30, 30), 8, 2.0)])

# Incredibles 2: a Pixar clamshell.  Supersuit red, the poster's white INCREDIBLES 2 cut off it, Elastigirl in the diamond
disney('incredibles-2-2018', ('grad', [(0, (220, 50, 30)), (.5, (160, 26, 18)), (1, (60, 10, 8))]), fin=dict(CLAM, vivid=.25),
       title=LC([(0.22, 0.85, 0.78, 0.95)], 140, cuts=[key_cut(lambda a: (_lum(a) > .75) & (_sat(a) < .3))]),
       face=ph(.37, .44, .18, 1.4), lcol=WHT)

# Bao (a short): a Pixar clamshell.  Steamer-paper cream, the poster's black brush bao lifted off it, the dumpling in the diamond
disney('bao-2018', ('grad', [(0, (244, 236, 220)), (.6, (234, 222, 200)), (1, (210, 190, 160))]), fin=dict(CLAM, vivid=.15),
       title=L((0.1, 0.04, 0.82, 0.2), 140, (24, 22, 20), mode='dark', speck=.01),
       face=ph(.56, .69, .22, 1.4), lcol=(24, 22, 20), ink=(24, 22, 20))


# =====================================================================================
# the 2016 shelf (films-2016.json).  Same approach as 2017 and 2018.  Zootopia (Disney Animation) and
# The Jungle Book (Walt Disney Pictures) are clamshells; the Star Wars films (Lucasfilm) are slipcases.
# The Hateful Eight (188 min) is a 2-tape box and O.J.: Made in America (467 min) a box set.
# =====================================================================================

# Sicario: the poster's desert cream, black stencil capitals, Kate's double exposure
std('sicario-2015', ('grad', [(0, (236, 226, 206)), (.6, (210, 196, 170)), (1, (120, 100, 76))]), (24, 22, 20),
    L((0.09, 0.83, 0.9, 0.92), 110, (24, 22, 20), mode='dark'),
    photo=ph(.55, .3, .55, 1.0), pb=(24, 22, 20), lg=(24, 22, 20), lw=.6, order='LPTCF', credit=['EMILY BLUNT', 'JOSH BROLIN'], ccol=(24, 22, 20),
    ft='a', vbox=(24, 22, 20), fcol=(24, 22, 20), fin=SLIP)

# Goodnight Mommy: black, white and red art-deco capitals, the bandaged head
std('goodnight-mommy-2015', ('grad', [(0, (30, 30, 30)), (.6, (10, 10, 10)), (1, (4, 4, 4))]), WHT,
    L([(0.0, 0.035, 1.0, 0.125), (0.19, 0.12, 0.81, 0.215)], 76, [WHT, (220, 40, 40)], mode=['light', 'key'], key=(210, 30, 30), t=(70, 150)),
    photo=ph(.5, .52, .5, 1.0), pb=(220, 40, 40), lg=WHT, lw=.6, order='LPTCF', credit=['FIALA & FRANZ'], ccol=WHT,
    ft='a', vbox=(220, 40, 40), fcol=(200, 200, 200), fin=SLIP)

# The Lobster: the poster's cream, black heavy capitals, David's head over the empty embrace
std('the-lobster-2015', ('solid', (240, 236, 226)), (20, 18, 18),
    L((0.16, 0.81, 0.83, 0.89), 90, (20, 18, 18), mode='dark'),
    photo=ph(.5, .25, .5, 1.0), pb=(20, 18, 18), lg=(20, 18, 18), lw=.6, order='LPTCF', credit=['A YORGOS LANTHIMOS', 'FILM'], ccol=(20, 18, 18),
    ft='a', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=SLIP, dotst=(['STAFF', 'PICK'], (200, 40, 40)))

# 20 Feet from Stardom: the stage lights' dark, the poster's magenta 20 FEET FROM and white STARDOM cut off it in their own colours and laid in one line, Darlene singing (no logo file: the label in type)
std('20-feet-from-stardom-2013', ('grad', [(0, (60, 30, 50)), (.6, (20, 10, 18)), (1, (4, 2, 4))]), (230, 40, 160),
    LC([(0.078, 0.673, 0.2, 0.732), (0.078, 0.733, 0.367, 0.79), (0.078, 0.79, 0.394, 0.85), (0.075, 0.851, 0.61, 0.91)], 74, gapf=.25, valign='base', margin=0, cuts=[key_cut(lambda a: (_sat(a) > .35) & (a[..., 0] > .4) & (a[..., 0] > a[..., 1] * 1.5)), key_cut(lambda a: (_sat(a) > .35) & (a[..., 0] > .4) & (a[..., 0] > a[..., 1] * 1.5)), key_cut(lambda a: (_sat(a) > .35) & (a[..., 0] > .4) & (a[..., 0] > a[..., 1] * 1.5)), key_cut(lambda a: (_lum(a) > .75) & (_sat(a) < .2))]),
    photo=ph(.5, .2, .5, 1.0), pb=(234, 44, 164), lg=WHT, lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(234, 44, 164), fcol=(210, 200, 210), fin=SLIP)

# Chef (2014): the poster's taco-truck yellow, the red block capitals, the crew at the window
std('chef-2014', ('solid', (248, 196, 30)), (214, 40, 30),
    L((0.17, 0.075, 0.83, 0.225), 140, (218, 44, 32), mode='key', key=(220, 50, 40), t=(70, 150)),
    photo=ph(.6, .5, .5, 1.0), pb=(218, 44, 32), lg=(40, 30, 20), lw=.6, order='LPTCF', credit=['JON FAVREAU'], ccol=(40, 30, 20),
    ft='a', vbox=(218, 44, 32), fcol=(40, 30, 20), fin=SLIP)

# Room (2015): the overcast sky, the yellow keyline ROOM, Ma and Jack
std('room-2015', ('grad', [(0, (130, 150, 170)), (.6, (70, 80, 90)), (1, (30, 34, 30))]), (246, 220, 40),
    L((0.19, 0.77, 0.82, 0.9), 100, (248, 222, 44), mode='key', key=(240, 210, 40), t=(70, 150)),
    photo=ph(.6, .45, .55, 1.0), pb=(248, 222, 44), lg=WHT, lw=.6, order='LPTCF', credit=['BRIE LARSON', 'JACOB TREMBLAY'], ccol=WHT,
    ft='a', vbox=(248, 222, 44), vink=(30, 34, 40), fcol=(210, 214, 220), fin=SLIP)

# The Danish Girl: the teal of the paintings, the cream spaced serif capitals, Lili
std('the-danish-girl-2015', ('grad', [(0, (40, 90, 100)), (.6, (16, 36, 40)), (1, (4, 10, 12))]), (236, 226, 206),
    L((0.06, 0.77, 0.91, 0.83), 64, (238, 228, 208), mode='light'),
    photo=ph(.7, .3, .45, 1.0), pb=(238, 228, 208), lg=WHT, lw=.6, order='LPTCF', credit=['EDDIE REDMAYNE', 'ALICIA VIKANDER'], ccol=(238, 228, 208),
    ft='a', vbox=(238, 228, 208), vink=(16, 36, 40), fcol=(200, 210, 206), fin=SLIP)

# The Big Short: white, the poster's gold THE and SHORT and black BIG cut off it in their own colours, the four in the boxes
std('the-big-short-2015', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (150, 140, 120))]), (20, 18, 18),
    LC([(0.37, 0.668, 0.735, 0.752), (0.3, 0.748, 0.86, 0.868), (0.27, 0.865, 0.91, 0.945)], 96, gapf=.2, valign='base', cuts=[key_cut(lambda a: (_sat(a) > .25) & (a[..., 0] > .45) & (_lum(a) < .85)), key_cut(lambda a: _lum(a) < .3), key_cut(lambda a: (_sat(a) > .25) & (a[..., 0] > .45) & (_lum(a) < .85))]),
    photo=ph(.5, .3, .8, .7), pb=(20, 18, 18), lg=(20, 18, 18), lw=.6, order='LPTCF', credit=['CHRISTIAN BALE', 'STEVE CARELL'], ccol=(20, 18, 18),
    ft='a', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=SLIP)

# Spotlight: the newsroom's grey-white, the gold serif capitals, the Globe team
std('spotlight-2015', ('grad', [(0, (70, 74, 76)), (.6, (30, 32, 34)), (1, (8, 8, 10))]), (200, 160, 50),
    L((0.035, 0.805, 0.95, 0.93), 86, (206, 166, 54), mode='key', key=(220, 180, 60), t=(70, 150)),
    photo=ph(.6, .45, .6, 1.0), pb=(206, 166, 54), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['MARK RUFFALO', 'MICHAEL KEATON'], ccol=WHT,
    ft='a', vbox=(206, 166, 54), vink=(30, 30, 30), fcol=WHT, fin=SLIP)

# Brooklyn (2015): the harbour sky, cream spaced capitals, Eilis at the rail
std('brooklyn-2015', ('grad', [(0, (110, 150, 170)), (.6, (50, 70, 80)), (1, (16, 24, 30))]), (240, 232, 214),
    L((0.09, 0.075, 0.91, 0.15), 76, (242, 234, 216), mode='light'),
    photo=ph(.55, .4, .45, 1.0), pb=(242, 234, 216), lg=WHT, lw=.6, order='LPTCF', credit=['SAOIRSE RONAN'], ccol=(242, 234, 216),
    ft='a', vbox=(242, 234, 216), vink=(50, 70, 80), fcol=(210, 220, 224), fin=SLIP)

# Anomalisa: the poster's misty grey, the black handwriting, Michael
std('anomalisa-2015', ('grad', [(0, (210, 210, 208)), (.6, (170, 170, 168)), (1, (80, 80, 78))]), (30, 30, 30),
    L((0.11, 0.12, 0.91, 0.24), 110, (30, 30, 30), mode='dark'),
    photo=ph(.4, .55, .5, 1.0), pb=(30, 30, 30), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['CHARLIE KAUFMAN', '& DUKE JOHNSON'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 30, 30), fcol=WHT, fin=SLIP)

# Whiplash (2014): black, the red wide capitals, Andrew at the kit
std('whiplash-2014', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), (220, 30, 30),
    L((0.02, 0.21, 0.97, 0.31), 90, (224, 32, 32), mode='key', key=(210, 30, 30), t=(70, 150)),
    photo=ph(.5, .6, .5, 1.0), pb=(224, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['MILES TELLER', 'J.K. SIMMONS'], ccol=WHT,
    ft='a', vbox=(224, 32, 32), fcol=(200, 200, 204), fin=SLIP)

# Steve Jobs: white, black lower case (typeset), Steve with his hand at his chin
std('steve-jobs-2015', ('grad', [(0, (246, 246, 246)), (.6, (226, 226, 226)), (1, (150, 150, 150))]), (20, 20, 20),
    T('steve jobs', 'her', 100, (20, 20, 20)),
    photo=ph(.4, .3, .5, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['MICHAEL FASSBENDER'], ccol=(20, 20, 20),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=SLIP)

# The Hateful Eight: a 2-tape box (188 minutes), the blizzard white, the red and black slab capitals (typeset), the stagecoach party in the snow
std('the-hateful-eight-2015', ('grad', [(0, (236, 236, 236)), (.6, (210, 210, 210)), (1, (130, 130, 130))]), (190, 30, 30),
    [TT([('THE', (194, 32, 32)), ('HATEFUL', (20, 18, 18))], 'bonb', 190, sp=.2), T('EIGHT', 'bonb', 190, (194, 32, 32))],
    photo=ph(.5, .3, .8, .45), pb=(20, 18, 18), lg=(20, 18, 18), lw=.5, order='LPTCSF', tgap=10, credit=['A QUENTIN TARANTINO', 'FILM'], ccol=(20, 18, 18),
    stick=TWOST((194, 32, 32), WHT), ft='c', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=SLIP, **TWO)

# The Revenant: frozen forest blue, the pale spaced capitals (typeset), Glass's eye
std('the-revenant-2015', ('grad', [(0, (100, 130, 150)), (.6, (40, 54, 64)), (1, (10, 14, 18))]), (210, 226, 236),
    T('THE REVENANT', 'herb', 64, (214, 230, 240), track=.3),
    photo=ph(.55, .38, .5, 1.0), pb=(214, 230, 240), lg=WHT, lw=.6, order='LPTCF', credit=['LEONARDO DiCAPRIO', 'TOM HARDY'], ccol=WHT,
    ft='a', vbox=(214, 230, 240), vink=(40, 54, 64), fcol=(200, 210, 216), fin=SLIP)

# Barbershop: The Next Cut: the shop's white tiles, red BARBERSHOP and black script (typeset), the crew
std('barbershop-the-next-cut-2016', ('grad', [(0, (244, 244, 242)), (.6, (222, 222, 220)), (1, (150, 150, 150))]), (200, 30, 40),
    [T('BARBERSHOP', 'ter', 80, (204, 32, 42), track=.02, bold=.4), T('THE NEXT CUT', 'herbi', 30, (20, 20, 30), track=.12)], tgap=6,
    photo=ph(.5, .5, .8, .6), pb=(204, 32, 42), lg=(20, 20, 30), lw=.6, order='LPTCF', credit=['ICE CUBE', 'REGINA HALL'], ccol=(20, 20, 30),
    ft='a', vbox=(204, 32, 42), fcol=(20, 20, 30), fin=MINT)

# The Jungle Book (2016): a Disney clamshell.  Jungle green, a gold storybook title (typeset), Bagheera in the diamond
disney('the-jungle-book-2016', ('grad', [(0, (40, 90, 60)), (.5, (20, 50, 30)), (1, (6, 20, 10))]), fin=dict(CLAM, vivid=.25),
       title=[T('The', 'pagb', 50, (236, 206, 90)), T('JUNGLE BOOK', 'pagb', 96, (236, 206, 90), grad=[(0, (250, 230, 130)), (1, (200, 150, 50))], shadow=((10, 20, 10), 3, 3))],  # typeset: the gold logo wouldn't cut off the jungle; Ian could supply it
       face=ph(.6, .58, .13, 1.4), lcol=WHT)

# Champs: the ring's black, silver heavy capitals (typeset), the fighter's gloves (no logo file: its company in type)
std('champs-2015', ('grad', [(0, (60, 40, 40)), (.6, (20, 14, 14)), (1, (4, 4, 4))]), (220, 220, 220),
    T('CHAMPS', 'intbk', 110, WHT, grad=[(0, (250, 250, 250)), (.5, (150, 150, 156)), (1, (230, 230, 236))]),
    photo=ph(.5, .3, .6, 1.0), pb=(200, 40, 40), studio=['BERT MARCUS', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(200, 40, 40), fcol=(200, 196, 196), fin=SLIP)

# Iverson: black, the gold condensed capitals (typeset), the cornrows (no logo file: its company in type)
std('iverson-2014', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (4, 4, 4))]), (220, 170, 70),
    T('IVERSON', 'hcnb', 100, (224, 174, 74), squeeze=.86),
    photo=ph(.5, .65, .6, 1.0), pb=(224, 174, 74), studio=['214 FILMS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY'], ccol=WHT,
    ft='a', vbox=(224, 174, 74), vink=(16, 16, 16), fcol=(200, 200, 200), fin=SLIP)

# Star Wars: The Force Awakens (Lucasfilm, a slipcase): space black, the yellow outline STAR WARS (typeset), Rey with the saber
std('star-wars-the-force-awakens-2015', ('grad', [(0, (30, 30, 50)), (.6, (10, 10, 18)), (1, (4, 4, 6))]), (246, 220, 40),
    [T('STAR WARS', 'intbk', 84, (10, 10, 18), outline=((248, 222, 44), 2.4)), T('THE FORCE AWAKENS', 'herb', 28, (248, 222, 44), track=.25)], tgap=8,
    photo=ph(.5, .3, .4, 1.0), pb=(248, 222, 44), lg=WHT, lw=.6, order='LPTCF', credit=['DAISY RIDLEY', 'JOHN BOYEGA'], ccol=WHT,
    ft='a', vbox=(248, 222, 44), vink=(10, 10, 18), fcol=(200, 200, 210), fin=SLIP)

# Spring, Summer, Fall, Winter... and Spring (2003): white, black serif (typeset), the temple on the lake
std('spring-summer-fall-winter-and-spring-2003', ('grad', [(0, (244, 244, 240)), (.6, (222, 224, 218)), (1, (150, 160, 150))]), (20, 20, 20),
    T('SPRING, SUMMER, FALL, WINTER... AND SPRING', 'ter', 44, (20, 20, 20)),
    photo=ph(.5, .63, .6, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['A KIM KI-DUK', 'FILM'], ccol=(20, 20, 20),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=WORN, seed=2003)

# Trumbo: Hollywood night blue, the white spaced capitals (typeset), Dalton in his white suit
std('trumbo-2015', ('grad', [(0, (40, 60, 90)), (.6, (14, 22, 34)), (1, (4, 6, 10))]), WHT,
    T('TRUMBO', 'her', 80, WHT, track=.5),
    photo=ph(.55, .45, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['BRYAN CRANSTON'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 22, 34), fcol=(200, 206, 220), fin=SLIP)

# Four Weddings and a Funeral (1994): a real rental, confetti white, the red serif (typeset), Charles and Carrie
std('four-weddings-and-a-funeral-1994', ('grad', [(0, (246, 244, 240)), (.6, (230, 226, 220)), (1, (170, 160, 150))]), (170, 30, 40),
    T('FOUR WEDDINGS AND A FUNERAL', 'ter', 56, (174, 32, 42), bold=.3),
    photo=ph(.35, .55, .5, 1.0), pb=(174, 32, 42), lg=(30, 30, 30), lw=.6, order='LPTCSF', credit=['HUGH GRANT', 'ANDIE MacDOWELL'], ccol=(30, 30, 30),
    stick=PRC(['$1.99', 'ROM-COM']), ft='a', vbox=(174, 32, 42), fcol=(30, 30, 30), fin=RENTAL, seed=1994)

# Post Tenebras Lux (2012): the poster's flat red and teal, the pink rounded lettering (typeset), the red figure
std('post-tenebras-lux-2012', ('grad', [(0, (40, 30, 90)), (.5, (60, 150, 200)), (1, (200, 50, 40))]), (240, 120, 160),
    T('Post Tenebras Lux', 'popm', 76, (244, 126, 166)),
    photo=ph(.5, .3, .4, 1.0), pb=(244, 126, 166), lg=WHT, lw=.6, order='LPTCF', credit=['A CARLOS REYGADAS', 'FILM'], ccol=WHT,
    ft='a', vbox=(244, 126, 166), vink=(40, 30, 90), fcol=WHT, fin=SLIP)

# Only God Forgives: Bangkok neon pink and blue, the white condensed capitals (typeset), Julian
std('only-god-forgives-2013', ('grad', [(0, (220, 40, 120)), (.5, (110, 40, 160)), (1, (20, 20, 60))]), WHT,
    T('ONLY GOD FORGIVES', 'hcnb', 80, WHT, squeeze=.74, bold=.4),
    photo=ph(.5, .2, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['RYAN GOSLING'], ccol=WHT,
    ft='a', vbox=WHT, vink=(110, 40, 160), fcol=(230, 210, 230), fin=SLIP)

# Deadpool (2016): white, the red stencil capitals (typeset), Deadpool's mask
std('deadpool-2016', ('grad', [(0, (244, 244, 244)), (.6, (220, 220, 220)), (1, (140, 140, 140))]), (170, 20, 30),
    T('DEADPOOL', 'hcnb', 100, (174, 22, 32), squeeze=.8, bold=1.0, rough=.4),
    photo=ph(.5, .32, .3, 1.0), pb=(174, 22, 32), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['RYAN REYNOLDS'], ccol=(20, 20, 20),
    ft='a', vbox=(174, 22, 32), fcol=(20, 20, 20), fin=SLIP)

# The Great Beauty: black, the yellow condensed capitals (typeset), Jep under the statue
std('the-great-beauty-2013', ('grad', [(0, (50, 46, 40)), (.6, (16, 14, 12)), (1, (4, 4, 4))]), (246, 230, 40),
    T('THE GREAT BEAUTY', 'hcnb', 80, (248, 232, 44), squeeze=.8, bold=.4),
    photo=ph(.5, .5, .55, 1.0), pb=(248, 232, 44), lg=WHT, lw=.6, order='LPTCF', credit=['TONI SERVILLO'], ccol=(248, 232, 44),
    ft='a', vbox=(248, 232, 44), vink=(16, 14, 12), fcol=(200, 196, 190), fin=SLIP, dotst=(['STAFF', 'PICK'], (200, 160, 40), (16, 14, 12)))

# Zootopia (2016): a Disney clamshell.  The city's blue sky, ZOOTOPIA in the street-sign green (typeset; Ian could supply the logo), Clawhauser in the diamond
disney('zootopia-2016', ('grad', [(0, (90, 170, 230)), (.5, (40, 100, 170)), (1, (14, 40, 80))]), fin=dict(CLAM, vivid=.25),
       title=T('ZOOTOPIA', 'popb', 110, WHT, box=((40, 130, 70), 12, 8)),
       face=ph(.82, .77, .17, 1.4), lcol=WHT)

# Spring Breakers: the poster's neon pink and violet, the scrawled neon lettering (typeset), the girls
std('spring-breakers-2013', ('grad', [(0, (200, 60, 160)), (.5, (100, 30, 110)), (1, (30, 10, 40))]), WHT,
    T('SPRING BREAKERS', 'cho', 84, WHT, soft=((250, 120, 220), 7, .7)),
    photo=ph(.5, .3, .6, 1.0), pb=(250, 140, 220), lg=WHT, lw=.6, order='LPTCF', credit=['A HARMONY KORINE', 'FILM'], ccol=WHT,
    ft='a', vbox=(250, 140, 220), vink=(100, 30, 110), fcol=WHT, fin=SLIP)

# The Deep Blue Sea (2011): dim grey-blue, white condensed capitals (typeset), Hester and Freddie
std('the-deep-blue-sea-2011', ('grad', [(0, (60, 70, 80)), (.6, (20, 24, 28)), (1, (4, 6, 8))]), WHT,
    T('THE DEEP BLUE SEA', 'hcn', 84, WHT, squeeze=.7),
    photo=ph(.5, .3, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['RACHEL WEISZ', 'TOM HIDDLESTON'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 24, 28), fcol=(196, 200, 206), fin=SLIP)

# Skyfall: white, the black spaced capitals and 007 (typeset), Bond with his gun
std('skyfall-2012', ('grad', [(0, (246, 246, 246)), (.6, (224, 224, 224)), (1, (150, 150, 150))]), (20, 20, 20),
    [T('SKYFALL', 'her', 76, (20, 20, 20), track=.4), T('007', 'intbki', 40, (20, 20, 20))], tgap=8,
    photo=ph(.1, .87, .2, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['DANIEL CRAIG'], ccol=(20, 20, 20),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=SLIP)

# The Cabin in the Woods: fog grey, the black serif (typeset), the cabin folding in on itself
std('the-cabin-in-the-woods-2012', ('grad', [(0, (210, 210, 206)), (.6, (150, 150, 146)), (1, (50, 50, 48))]), (20, 20, 20),
    [T('THE CABIN', 'ter', 76, (20, 20, 20)), T('IN THE WOODS', 'ter', 40, (20, 20, 20), track=.1)], tgap=6,
    photo=ph(.5, .4, .6, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['A DREW GODDARD', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(20, 20, 20), fcol=WHT, fin=SLIP)

# Zero Dark Thirty: night-vision dark, white condensed capitals (typeset), Maya
std('zero-dark-thirty-2012', ('grad', [(0, (70, 74, 70)), (.6, (24, 26, 24)), (1, (6, 6, 6))]), WHT,
    T('ZERO DARK THIRTY', 'hcnb', 84, WHT, squeeze=.74, bold=.6),
    photo=ph(.4, .3, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JESSICA CHASTAIN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(24, 26, 24), fcol=(200, 204, 200), fin=SLIP)

# Star Wars: Episode III (Lucasfilm, a slipcase): Mustafar fire and black, the gold engraved capitals (typeset), Anakin
std('star-wars-episode-iii-revenge-of-the-sith-2005', ('grad', [(0, (200, 80, 20)), (.5, (80, 26, 10)), (1, (10, 4, 2))]), (230, 190, 100),
    [T('STAR WARS  EPISODE III', 'ter', 50, (234, 196, 106), track=.06), T('REVENGE OF THE SITH', 'ter', 34, (234, 196, 106), track=.2)], tgap=8,
    photo=ph(.5, .1, .35, 1.0), pb=(234, 196, 106), lg=WHT, lw=.6, order='LPTCF', credit=['HAYDEN CHRISTENSEN', 'EWAN McGREGOR'], ccol=WHT,
    ft='a', vbox=(234, 196, 106), vink=(80, 26, 10), fcol=(220, 200, 180), fin=WORN, seed=2005)

# Mission: Impossible - Ghost Protocol (2011): Dubai dust gold, red and white italic capitals (typeset), Ethan
std('mission-impossible-ghost-protocol-2011', ('grad', [(0, (230, 170, 80)), (.5, (120, 70, 30)), (1, (20, 12, 6))]), (220, 30, 30),
    [T('MISSION: IMPOSSIBLE', 'hcnb', 54, (224, 32, 32), squeeze=.8, bold=.4), T('GHOST PROTOCOL', 'hcnb', 70, WHT, squeeze=.8, bold=.6)], tgap=8,
    photo=ph(.5, .25, .4, 1.0), pb=(224, 32, 32), lg=WHT, lw=.6, order='LPTCF', credit=['TOM CRUISE'], ccol=WHT,
    ft='a', vbox=(224, 32, 32), fcol=(240, 220, 200), fin=SLIP, seed=2011)

# Woman in the Dunes (1964): an old tape, white, the black brush lettering (typeset), the ink-wash figure
std('woman-in-the-dunes-1964', ('grad', [(0, (244, 242, 236)), (.6, (226, 222, 212)), (1, (160, 150, 130))]), (20, 18, 16),
    T('Woman in the Dunes', 'cho', 90, (20, 18, 16)),
    photo=ph(.5, .65, .7, .8), pb=(20, 18, 16), lg=(20, 18, 16), lw=.6, order='LPTCSF', credit=['A HIROSHI TESHIGAHARA', 'FILM'], ccol=(20, 18, 16),
    stick=flow(dot, 70, ['FOREIGN'], (200, 60, 40), d=62), ft='e', fcol=(20, 18, 16), fin=OLD, seed=1964)

# Tokyo Story (1953): an old tape, the grey of the harbour, white spaced capitals (typeset), the old couple
std('tokyo-story-1953', ('grad', [(0, (150, 150, 150)), (.6, (70, 70, 70)), (1, (16, 16, 16))]), WHT,
    T('TOKYO STORY', 'her', 70, WHT, track=.45),
    photo=ph(.4, .4, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A YASUJIRŌ OZU', 'FILM'], ccol=WHT,
    stick=PRC(['$2.99', 'CLASSIC']), ft='e', fcol=(220, 220, 220), fin=OLD, seed=1953)

# O.J.: Made in America: a box set (467 minutes), the poster's newsprint grey, black condensed capitals (typeset), the flag-painted hand
std('o-j-made-in-america-2016', ('grad', [(0, (220, 220, 218)), (.6, (180, 180, 178)), (1, (90, 90, 88))]), (20, 20, 20),
    [T('O.J.:', 'hcnb', 150, (190, 30, 40), squeeze=.76, bold=.8), T('MADE IN AMERICA', 'hcnb', 150, (20, 20, 20), squeeze=.76, bold=.8)],
    photo=ph(.5, .3, .6, .5), pb=(190, 30, 40), lg=(20, 20, 20), lw=.5, order='LPTCSF', tgap=10, credit=['THE COMPLETE DOCUSERIES', 'AN EZRA EDELMAN FILM'], ccol=(20, 20, 20),
    stick=flow(dot, 112, ['BOX', 'SET'], (190, 30, 40), WHT, d=104), ft='c', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=MINT, **TWO)

# 10 Cloverfield Lane: the storm sky's green-black, white heavy condensed capitals (typeset), Michelle
std('10-cloverfield-lane-2016', ('grad', [(0, (60, 80, 70)), (.6, (18, 24, 20)), (1, (4, 6, 4))]), WHT,
    [T('10', 'intbk', 60, WHT), T('CLOVERFIELD LANE', 'hcnb', 80, WHT, squeeze=.78, bold=.6)], tgap=8,
    photo=ph(.75, .72, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JOHN GOODMAN', 'MARY ELIZABETH WINSTEAD'], ccol=WHT,
    ft='a', vbox=WHT, vink=(18, 24, 20), fcol=(196, 206, 200), fin=SLIP)

# Punch-Drunk Love (2002): black and the colour wash, white tall serif (typeset), the kiss in the doorway
std('punch-drunk-love-2002', ('grad', [(0, (30, 30, 50)), (.5, (20, 20, 30)), (1, (40, 80, 160))]), WHT,
    T('PUNCH-DRUNK LOVE', 'adv', 70, WHT, track=.04),
    photo=ph(.5, .4, .5, 1.0), pb=(120, 170, 240), lg=WHT, lw=.6, order='LPTCF', credit=['ADAM SANDLER', 'EMILY WATSON'], ccol=WHT,
    ft='a', vbox=(120, 170, 240), vink=(20, 20, 30), fcol=(200, 200, 220), fin=WORN, seed=2002, dotst=(['STAFF', 'PICK'], (40, 80, 160)))

# These Birds Walk: the dusty sky's peach, the pale ochre capitals (typeset), the boy mid-leap
std('these-birds-walk-2012', ('grad', [(0, (236, 222, 196)), (.6, (220, 190, 150)), (1, (160, 120, 80))]), (190, 140, 60),
    T('THESE BIRDS WALK', 'her', 66, (160, 110, 40), track=.1, bold=.4),
    photo=ph(.5, .82, .6, 1.0), pb=(160, 110, 40), lg=(40, 30, 20), lw=.6, order='LPTCF', credit=['A DOCUMENTARY'], ccol=(40, 30, 20),
    ft='a', vbox=(160, 110, 40), fcol=(40, 30, 20), fin=SLIP)

# Doubt (2008): black, white blackletter D and spaced OUBT (typeset), Sister Aloysius
std('doubt-2008', ('grad', [(0, (40, 40, 44)), (.6, (14, 14, 16)), (1, (4, 4, 4))]), WHT,
    T('DOUBT', 'ter', 100, WHT, track=.3),
    photo=ph(.2, .17, .4, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['MERYL STREEP', 'PHILIP SEYMOUR HOFFMAN'], ccol=WHT,
    ft='a', vbox=WHT, vink=(14, 14, 16), fcol=(200, 200, 204), fin=WORN, seed=2008)

# A Girl Walks Home Alone at Night: the poster's red and black, white and red condensed capitals (typeset), the girl in her chador
std('a-girl-walks-home-alone-at-night-2014', ('solid', (226, 20, 20)), (20, 18, 18),
    TT([('A', WHT), ('GIRL', WHT), ('WALKS HOME ALONE AT NIGHT', (20, 18, 18))], 'hcnb', 70, sp=.2, squeeze=.74, bold=.6),
    photo=ph(.5, .2, .4, 1.0), pb=(20, 18, 18), lg=WHT, lw=.6, order='LPTCF', credit=['AN ANA LILY AMIRPOUR', 'FILM'], ccol=(20, 18, 18),
    ft='a', vbox=(20, 18, 18), fcol=(20, 18, 18), fin=SLIP)

# Before the Devil Knows You're Dead (2007): black, white heavy capitals (typeset), Andy and Hank
std('before-the-devil-knows-you-re-dead-2007', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (4, 4, 4))]), WHT,
    [T("BEFORE THE DEVIL", 'intbk', 60, WHT, squeeze=.84), T("KNOWS YOU'RE DEAD", 'intbk', 60, WHT, squeeze=.84)], tgap=8,
    photo=ph(.75, .15, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['PHILIP SEYMOUR HOFFMAN', 'ETHAN HAWKE'], ccol=WHT,
    ft='a', vbox=WHT, vink=(16, 16, 16), fcol=(200, 200, 200), fin=WORN, seed=2007)

# The Savages (2007): the poster's winter blue-grey, the white SAVAGES on red (typeset), Wendy and Jon on the bench
std('the-savages-2007', ('grad', [(0, (200, 214, 222)), (.6, (170, 186, 196)), (1, (110, 120, 130))]), WHT,
    T('THE SAVAGES', 'intbk', 80, WHT, box=((220, 30, 60), 10, 6)),
    photo=ph(.5, .45, .5, .8), pb=(220, 30, 60), lg=(30, 30, 30), lw=.6, order='LPTCF', credit=['LAURA LINNEY', 'PHILIP SEYMOUR HOFFMAN'], ccol=(30, 30, 30),
    ft='a', vbox=(220, 30, 60), fcol=(30, 30, 30), fin=WORN, seed=2007)

# Clouds of Sils Maria: the Maloja snake's mist, white spaced capitals (typeset), Maria and Valentine
std('clouds-of-sils-maria-2014', ('grad', [(0, (180, 214, 220)), (.6, (100, 140, 150)), (1, (30, 50, 56))]), WHT,
    T('CLOUDS OF SILS MARIA', 'her', 58, WHT, track=.3),
    photo=ph(.55, .3, .6, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['JULIETTE BINOCHE', 'KRISTEN STEWART'], ccol=WHT,
    ft='a', vbox=WHT, vink=(100, 140, 150), fcol=WHT, fin=SLIP)

# Bridesmaids (2011): the brick wall's red-brown, white heavy capitals (typeset), the bridal party in pink
std('bridesmaids-2011', ('grad', [(0, (140, 70, 60)), (.6, (70, 34, 30)), (1, (20, 10, 8))]), WHT,
    T('BRIDESMAIDS', 'intbk', 92, WHT, squeeze=.86),
    photo=ph(.5, .62, .8, .6), pb=(240, 80, 160), lg=WHT, lw=.6, order='LPTCF', credit=['KRISTEN WIIG', 'MAYA RUDOLPH'], ccol=WHT,
    ft='a', vbox=(240, 80, 160), vink=(70, 34, 30), fcol=(230, 210, 206), fin=SLIP, seed=2011)

# King Jack: the hazy violet, the white thin capitals with the drawn crown (typeset), Jack
std('king-jack-2015', ('grad', [(0, (150, 130, 160)), (.6, (80, 66, 90)), (1, (20, 16, 24))]), WHT,
    T('KING JACK', 'her', 90, WHT, track=.06),
    photo=ph(.5, .35, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCF', credit=['CHARLIE PLUMMER'], ccol=WHT,
    ft='a', vbox=WHT, vink=(80, 66, 90), fcol=(220, 210, 226), fin=SLIP)

# Tamasha: Corsica's golden haze, the red-gold carnival capitals (typeset), Ved and Tara
std('tamasha-2015', ('grad', [(0, (230, 180, 80)), (.5, (160, 100, 40)), (1, (40, 24, 10))]), (220, 50, 30),
    T('TAMASHA', 'intbk', 100, (224, 54, 32), outline=((250, 230, 150), 2.0)),
    photo=ph(.5, .55, .7, .8), pb=(224, 54, 32), lg=WHT, lw=.6, order='LPTCF', credit=['RANBIR KAPOOR', 'DEEPIKA PADUKONE'], ccol=WHT,
    ft='a', vbox=(224, 54, 32), vink=(40, 24, 10), fcol=WHT, fin=SLIP)

# The Nice Guys: the poster's seventies orange rings, the outlined white lower case (typeset), March and Healy
std('the-nice-guys-2016', ('grad', [(0, (240, 230, 200)), (.4, (240, 150, 50)), (.8, (200, 70, 30)), (1, (60, 20, 10))]), WHT,
    T('the nice guys', 'popb', 92, (60, 50, 140), outline=(WHT, 2.4)),
    photo=ph(.5, .3, .6, 1.0), pb=(60, 50, 140), lg=(40, 30, 20), lw=.6, order='LPTCF', credit=['RUSSELL CROWE', 'RYAN GOSLING'], ccol=WHT,
    ft='a', vbox=(60, 50, 140), fcol=WHT, fin=MINT)

# Howl's Moving Castle (2004): a Ghibli tape (a slipcase), the hills' green and the castle, the gold serif capitals (typeset)
std('howl-s-moving-castle-2004', ('grad', [(0, (50, 70, 80)), (.5, (30, 44, 26)), (1, (10, 14, 8))]), (230, 200, 110),
    T("HOWL'S MOVING CASTLE", 'terb', 66, (246, 220, 130), track=.04, shadow=((20, 16, 10), 3, 3)),
    photo=ph(.4, .3, .6, 1.0), pb=(234, 206, 116), lg=WHT, lw=.6, order='LPTCSF', credit=['A HAYAO MIYAZAKI', 'FILM'], ccol=WHT,
    stick=flow(dot, 70, ['ANIME'], (220, 60, 100), d=60), ft='a', vbox=(234, 206, 116), vink=(60, 80, 50), fcol=(220, 220, 210), fin=WORN, seed=2004)

# Scarface (1983): an old 2-hour-50 rental, the poster's black and white split, the red condensed capitals (typeset), Tony
std('scarface-1983', ('grad', [(0, (244, 244, 244)), (.5, (220, 220, 220)), (1, (30, 30, 30))]), (200, 20, 30),
    T('SCARFACE', 'hcnb', 110, (204, 22, 32), squeeze=.7, bold=.8),
    photo=ph(.6, .2, .45, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCSF', credit=['AL PACINO'], ccol=(20, 20, 20),
    stick=BAR('15 01983', top='CRIME', fill=(220, 236, 250), ink=(20, 40, 80)), ft='a', vbox=(204, 22, 32), fcol=WHT, fin=RENTAL, seed=1983)

# The In-Laws (1979): an old tape, the sky blue and wedding-cake white, the pink outlined lower case (typeset), Vince and Sheldon on top of the cake
std('the-in-laws-1979', ('grad', [(0, (140, 200, 230)), (.6, (200, 226, 236)), (1, (220, 220, 220))]), (230, 100, 170),
    T('the in-laws', 'popb', 100, (236, 110, 180), outline=(WHT, 2.4)),
    photo=ph(.5, .15, .5, 1.0), pb=(236, 110, 180), lg=(30, 30, 40), lw=.6, order='LPTCSF', credit=['PETER FALK', 'ALAN ARKIN'], ccol=(30, 30, 40),
    stick=PRC(['$0.99', 'COMEDY']), ft='e', fcol=(30, 30, 40), fin=OLD, seed=1979)

# About Elly (2009): the Caspian grey-green, white condensed capitals (typeset), Sepideh (no logo file: its company in type)
std('about-elly-2009', ('grad', [(0, (130, 150, 140)), (.6, (60, 70, 66)), (1, (16, 20, 18))]), WHT,
    T('ABOUT ELLY', 'hcnb', 92, WHT, squeeze=.8),
    photo=ph(.25, .45, .4, 1.0), pb=WHT, studio=['SIMAYE MEHR'], scol=WHT, order='lPTCF', credit=['AN ASGHAR FARHADI', 'FILM'], ccol=WHT,
    ft='a', vbox=WHT, vink=(60, 70, 66), fcol=(220, 226, 222), fin=WORN, seed=2009)

# Manhattan (1979): an old tape, white, the black skyline capitals (typeset), the couple on the bench under the bridge
std('manhattan-1979', ('grad', [(0, (244, 244, 244)), (.6, (222, 222, 222)), (1, (140, 140, 140))]), (20, 20, 20),
    T('MANHATTAN', 'hcnb', 100, (20, 20, 20), squeeze=.7, bold=1.0),
    photo=ph(.5, .2, .7, .7), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['WOODY ALLEN', 'DIANE KEATON'], ccol=(20, 20, 20),
    ft='e', fcol=(20, 20, 20), fin=OLD, seed=1979)

# Trainspotting (1996): a real rental, the poster's orange and white, the white heavy lower case on orange (typeset), Renton
std('trainspotting-1996', ('solid', (230, 90, 20)), WHT,
    T('Trainspotting', 'herb', 84, WHT),
    photo=ph(.75, .25, .45, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['EWAN McGREGOR'], ccol=WHT,
    stick=RWD(), ft='a', vbox=WHT, vink=(230, 90, 20), fcol=WHT, fin=RENTAL, seed=1996)

# Blade Runner (1982): an old tape, the poster's night and neon, the red stencil capitals (typeset), Deckard
std('blade-runner-1982', ('grad', [(0, (40, 30, 30)), (.5, (16, 14, 20)), (1, (60, 20, 10))]), (226, 40, 30),
    T('BLADE RUNNER', 'intbki', 80, (230, 44, 32), squeeze=.84),
    photo=ph(.4, .15, .45, 1.0), pb=(230, 44, 32), lg=WHT, lw=.6, order='LPTCSF', credit=['HARRISON FORD'], ccol=WHT,
    stick=flow(dot, 70, ['SCI-FI'], (40, 160, 200), d=60), ft='e', fcol=(200, 196, 196), fin=OLD, seed=1982)

# Dawg Fight: white, black wide-spaced capitals (typeset), the backyard fighters
std('dawg-fight-2015', ('grad', [(0, (244, 244, 244)), (.6, (220, 220, 220)), (1, (140, 140, 140))]), (20, 20, 20),
    T('DAWG FIGHT', 'herb', 70, (20, 20, 20), track=.5),
    photo=ph(.6, .85, .6, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['A BILLY CORBEN', 'FILM'], ccol=(20, 20, 20),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=SLIP)

# Parched: the Rajasthan dusk orange, the gold serif capitals (typeset), Rani dancing
std('parched-2015', ('grad', [(0, (220, 140, 70)), (.5, (130, 70, 30)), (1, (30, 14, 6))]), (236, 216, 150),
    T('PARCHED', 'ter', 96, (240, 220, 154), track=.06),
    photo=ph(.6, .25, .5, 1.0), pb=(240, 220, 154), lg=WHT, lw=.6, order='LPTCF', credit=['A LEENA YADAV', 'FILM'], ccol=WHT,
    ft='a', vbox=(240, 220, 154), vink=(130, 70, 30), fcol=WHT, fin=SLIP)

# The Handmaiden: black with the gold keyline, cream spaced capitals (typeset), Sook-hee and Lady Hideko
std('the-handmaiden-2016', ('grad', [(0, (40, 34, 30)), (.6, (14, 12, 10)), (1, (4, 4, 4))]), (230, 220, 190),
    [T('THE', 'her', 28, (232, 222, 192), track=.4), T('HANDMAIDEN', 'her', 70, (232, 222, 192), track=.2)], tgap=6,
    photo=ph(.5, .6, .45, 1.0), pb=(200, 170, 90), lg=WHT, lw=.6, order='LPTCF', credit=['A PARK CHAN-WOOK', 'FILM'], ccol=(232, 222, 192),
    ft='a', vbox=(200, 170, 90), vink=(14, 12, 10), fcol=(200, 196, 186), fin=MINT, under=[frame((200, 170, 90), 8, 1.4)])

# The Scavengers (1992): the poster is Boca de Lixo's, so the spine is too: white, black serif (typeset), the balloons and the vulture
std('the-scavengers-1992', ('grad', [(0, (246, 246, 244)), (.6, (224, 224, 220)), (1, (150, 150, 146))]), (20, 20, 20),
    [T('BOCA DE LIXO', 'terb', 76, (20, 20, 20)), T('THE SCAVENGERS', 'her', 26, (20, 20, 20), track=.3)], tgap=8,
    photo=ph(.5, .3, .6, 1.0), pb=(20, 20, 20), order='PTCF', credit=['AN EDUARDO COUTINHO', 'FILM'], ccol=(20, 20, 20),
    ft='e', fcol=(20, 20, 20), fin=OLD, seed=1992)

# Pink (2016): the courtroom's dark, the hot-pink heavy capitals (typeset), Deepak (no logo file: its company in type)
std('pink-2016', ('grad', [(0, (50, 40, 40)), (.6, (18, 14, 14)), (1, (4, 4, 4))]), (240, 30, 150),
    T('PINK', 'intbk', 130, (244, 34, 156)),
    photo=ph(.5, .2, .5, 1.0), pb=(244, 34, 156), studio=['NH STUDIOZ'], scol=WHT, order='lPTCF', credit=['AMITABH BACHCHAN', 'TAAPSEE PANNU'], ccol=WHT,
    ft='a', vbox=(244, 34, 156), fcol=(200, 196, 196), fin=SLIP)

# Salaam Bombay! (1988): an old tape, black, white and grey serif capitals (typeset), Krishna at the window
std('salaam-bombay-1988', ('grad', [(0, (50, 40, 30)), (.6, (16, 12, 10)), (1, (4, 4, 4))]), WHT,
    TT([('SALAAM', WHT), ('BOMBAY!', (190, 190, 190))], 'ter', 76, sp=.25),
    photo=ph(.3, .55, .5, 1.0), pb=WHT, lg=WHT, lw=.6, order='LPTCSF', credit=['A MIRA NAIR', 'FILM'], ccol=WHT,
    stick=PRC(['$1.99', 'FOREIGN']), ft='e', fcol=(210, 200, 190), fin=OLD, seed=1988)


if __name__ == '__main__':
    for k in (sys.argv[1:] or list(SPECS)):
        im = build(SPECS[k])
        print(k, im.size, round(im.width / im.height, 4))
