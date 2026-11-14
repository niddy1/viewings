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

FILMS = {f['poster'].split('/')[-1][:-4]: f for f in json.load(open(REPO + 'films.json', encoding='utf8'))['films']}
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
        elif ch == 'F': it += foot(ft, fcol, vbox, vink, cat, id)
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

# Zootopia 2: white clamshell, candy-coloured type, the crowd from the poster
std('zootopia-2-2025', ('solid', (249, 249, 244)), (20, 120, 84),
    TT([('ZOOTOPIA', (22, 140, 92)), ('2', (240, 132, 20))], 'popb', 96, track=.02),
    photo=ph(.5, .62, .86, 1.3), pb=(22, 140, 92), lg=(24, 50, 130), lw=.74, order='LPTSF',
    stick=flow(dot, 70, ['FAMILY', 'FUN'], (240, 132, 20), d=70), ft='a', vbox=(24, 50, 130), fcol=(24, 50, 130), fin=CLAM, notch=False, bot=40)

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

# Girl in the Box: TV movie, title block across the spine in its own serif
std('girl-in-the-box-2016', ('solid', (13, 11, 10)), (226, 214, 180),
    L(tb('girl-in-the-box-2016'), 190, (226, 214, 180), speck=.002),
    photo=ph(.55, .36, .62, 1.3), pb=(190, 150, 70), lg=None, lw=.7, order='LtPF', ft='a', vbox=(232, 40, 110),
    fcol=(196, 186, 160), fin=SLIP, stick=None)

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

# Hoppers: Pixar yellow clamshell
std('hoppers-2026', ('solid', (250, 190, 22)), (20, 18, 16),
    L(tb('hoppers-2026'), 104, (20, 18, 16), speck=.001),
    photo=ph(.5, .42, .92, 1.15), pb=(20, 18, 16), lg=(20, 18, 16), lw=.7, order='LPTF', ft='a', vbox=(20, 18, 16), vink=(250, 190, 22),
    fcol=(20, 18, 16), fin=CLAM, notch=False, bot=40)

# Louis C.K.: Ridiculous: a comedy-club special, slate and spotlight
std('louis-c-k-ridiculous-2026', ('grad', [(0, (30, 42, 54)), (1, (10, 14, 20))]), WHT,
    TT([('LOUIS C.K.', (150, 190, 206)), ('RIDICULOUS', WHT)], 'her', 70, track=.02, sp=.22),
    photo=ph(.5, .68, .9, 1.0), pb=(150, 190, 206), studio=['STAND-UP', 'SPECIAL'], scol=(150, 190, 206), order='lPTF',
    ft='b', fcol=(170, 186, 196), fin=SLIP)

# The Devil Wears Prada 2: couture red, title block across in its serif caps
std('the-devil-wears-prada-2-2026', ('solid', (172, 22, 36)), WHT,
    L(tb('the-devil-wears-prada-2-2026', pad=.004), 180, WHT, speck=.003),
    photo=ph(.5, .82, .62, 1.1), pb=WHT, photo2=ph(.38, .18, .5, 1.0), lg=WHT, lw=.5, order='LptPF', ft='a', vbox=(16, 14, 14),
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

# Toy Story 5: toy-box blue clamshell
std('toy-story-5-2026', ('solid', (34, 96, 206)), (250, 214, 40),
    TT([('TOY', (250, 214, 40)), ('STORY', (232, 44, 40)), ('5', (250, 214, 40))], 'popb', 100, track=.01),
    photo=ph(.5, .68, .92, 1.25), pb=(250, 214, 40), lg=WHT, lw=.7, order='LPTF', ft='a', vbox=(232, 44, 40), fcol=WHT,
    fin=CLAM, notch=False, bot=40)

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


if __name__ == '__main__':
    for k in (sys.argv[1:] or list(SPECS)):
        im = build(SPECS[k])
        print(k, im.size, round(im.width / im.height, 4))
