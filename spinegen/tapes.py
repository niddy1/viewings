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

# Tombstone (1993): sun-bleached parchment, black wood-type capitals, the four of them walking out
std('tombstone-1993', ('grad', [(0, (238, 222, 176)), (.6, (222, 196, 140)), (1, (150, 110, 64))]), (26, 20, 16),
    T('TOMBSTONE', 'bonb', 118, (26, 20, 16), track=.08, rough=.3),
    photo=ph(.5, .4, .84, .7), pb=(26, 20, 16), lg=(26, 20, 16), lw=.6, order='LPTCSF', credit=['KURT RUSSELL', 'VAL KILMER'], ccol=(140, 30, 20),
    stick=BAR('27 06135', top='WESTERN', fill=(244, 236, 214)), ft='b', fcol=(40, 30, 22), fin=RENTAL, seed=1993)

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

# Snake Eyes (1998): casino purple, the poster's green SNAKE and white EYES (typeset, roughed up), Cage staring out
std('snake-eyes-1998', ('grad', [(0, (120, 70, 190)), (.5, (70, 40, 120)), (1, (20, 12, 36))]), WHT,
    TT([('SNAKE', (90, 220, 70)), ('EYES', WHT)], 'hcnb', 116, sp=.18, squeeze=.86, track=-.01),
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

# Spider-Man: Across the Spider-Verse: comic-book magenta and violet, red outlined capitals, Miles up top
std('spider-man-across-the-spider-verse-2023', ('grad', [(0, (240, 80, 150)), (.4, (120, 40, 150)), (1, (20, 12, 50))]), (232, 30, 40),
    [T('SPIDER-MAN', 'intbki', 96, (232, 30, 40), outline=((10, 10, 30), 2.5), track=-.01), T('ACROSS THE SPIDER-VERSE', 'advb', 24, WHT, track=.24)],
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
    photo=ph(.7, .38, .36, 1.2), pb=(236, 232, 222), studio=['A DOCUMENTARY BY', 'BEILINSON & HAWLEY'], scol=(220, 214, 204), order='lPTSF',
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

# Wonka: chocolate-shop plum, a gold script (typeset: the poster's swashes tangle with the sweets)
std('wonka-2023', ('grad', [(0, (130, 24, 64)), (.6, (70, 12, 40)), (1, (24, 6, 16))]), (244, 196, 70),
    T('Wonka', 'cho', 150, (246, 200, 76), outline=((90, 20, 30), 2.2)),
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

# Road House: a Keys bar after dark, a neon-cyan script (typeset with a glow: the tubes won't lift off the bar)
std('road-house-2024', ('grad', [(0, (30, 44, 50)), (.6, (16, 22, 26)), (1, (6, 8, 10))]), (120, 236, 246),
    T('Road House', 'cho', 130, (190, 250, 252), soft=((40, 210, 240), 9, .9), outline=((30, 170, 200), 1.2)),
    photo=ph(.5, .42, .5, 1.0), pb=(120, 236, 246), lg=WHT, lw=.4, order='LPTCF', credit=['JAKE GYLLENHAAL'], ccol=(120, 236, 246),
    ft='a', vbox=(120, 236, 246), vink=(16, 22, 26), fcol=(196, 210, 214), fin=SLIP)

# Argylle: navy argyle, the poster's gold dotted capitals
std('argylle-2024', ('grad', [(0, (40, 52, 120)), (.6, (22, 28, 70)), (1, (8, 10, 24))]), (226, 186, 96),
    L((0.14, 0.81, 0.86, 0.895), 76, (230, 192, 100), mode='key', key=(220, 180, 92), t=(70, 160), speck=.005),
    photo=ph(.5, .42, 1.0, .6), pb=(226, 186, 96), lg=WHT, lw=.5, order='LPTCF', credit=['A MATTHEW VAUGHN', 'FILM'], ccol=(226, 186, 96),
    ft='a', vbox=(226, 186, 96), vink=(22, 28, 70), fcol=(200, 206, 230), fin=SLIP, under=[frame((226, 186, 96), 8, 1.2)])

# Snack Shack: summer-pool blue, a fat yellow slab with a red keyline (typeset: the poster's sits on a tilted banner)
std('snack-shack-2024', ('grad', [(0, (70, 180, 214)), (.6, (34, 120, 160)), (1, (14, 50, 70))]), (252, 220, 50),
    T('Snack Shack', 'bonb', 110, (252, 222, 54), outline=((200, 30, 30), 3), shadow=((90, 10, 10), 3, 3)),
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

# Hot Fuzz (2007): an explosion behind black, chrome capitals with a police-badge feel (typeset: lettering over flames)
std('hot-fuzz-2007', ('grad', [(0, (240, 140, 40)), (.3, (120, 40, 10)), (1, (12, 8, 6))]), (214, 218, 226),
    T('HOT FUZZ', 'intbk', 112, (214, 218, 226), grad=[(0, (246, 248, 252)), (.5, (150, 160, 176)), (.55, (90, 100, 116)), (1, (220, 226, 236))], outline=((20, 20, 24), 2), track=.02),
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

# Beverly Hills Cop: Axel F: palm-tree sky blue (like the 1987 tape next door a year on), chrome capitals and the red script F
std('beverly-hills-cop-axel-f-2024', ('grad', [(0, (60, 160, 230)), (.6, (40, 110, 190)), (1, (14, 40, 80))]), WHT,
    [T('BEVERLY HILLS COP', 'intbk', 54, WHT, outline=((14, 50, 110), 2), track=-.02), T('Axel F', 'herbi', 88, (226, 30, 40), outline=((70, 10, 14), 2))],
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
    photo=ph(.6, .8, .7, .6), pb=(150, 230, 230), lg=WHT, lw=.8, order='LPTCF', tgap=10, credit=['JOHN MAGARO', 'STEVE BUSCEMI'], ccol=(150, 230, 230),
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


if __name__ == '__main__':
    for k in (sys.argv[1:] or list(SPECS)):
        im = build(SPECS[k])
        print(k, im.size, round(im.width / im.height, 4))
