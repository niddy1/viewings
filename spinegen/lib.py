import os, numpy as np, cv2, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

S = 2
H = 1100
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
F = {k: os.path.join(FONTS, v) for k, v in dict(
    adv='texgyreadventor-regular.otf',
    advb='texgyreadventor-bold.otf',
    bonb='texgyrebonum-bold.otf',
    bonbi='texgyrebonum-bolditalic.otf',
    cho='texgyrechorus-mediumitalic.otf',
    curbi='texgyrecursor-bolditalic.otf',
    dsc='DejaVuSerifCondensed-Bold.ttf',
    hcn='texgyreheroscn-regular.otf',
    hcnb='texgyreheroscn-bold.otf',
    her='texgyreheros-regular.otf',
    herb='texgyreheros-bold.otf',
    herbi='texgyreheros-bolditalic.otf',
    intbk='Inter-Black.otf',
    intbki='Inter-BlackItalic.otf',
    intxb='Inter-ExtraBold.otf',
    intm='Inter-Medium.otf',
    intsb='Inter-SemiBold.otf',
    lmdc='lmsansdemicond10-regular.otf',
    mono='lmmono10-regular.otf',
    monob='lmmonolt10-bold.otf',
    lora='Lora-Variable.ttf',
    pagb='texgyrepagella-bold.otf',
    pagbi='texgyrepagella-bolditalic.otf',
    popb='Poppins-Bold.ttf',
    popbi='Poppins-BoldItalic.ttf',
    popm='Poppins-Medium.ttf',
    schb='texgyreschola-bold.otf',
    ter='texgyretermes-regular.otf',
    terb='texgyretermes-bold.otf',
    terbi='texgyretermes-bolditalic.otf',
    teri='texgyretermes-italic.otf',
).items()}


def fnt(key, size):
    return ImageFont.truetype(F[key], max(4, int(round(size * S))))


def text_mask(text, key, size, track=0.0, squeeze=1.0, sc=None, sc_scale=0.8):
    """Horizontal text as an L mask, tight-cropped. track in em. sc = font key for small caps."""
    f = fnt(key, size)
    fs = fnt(sc, size * sc_scale) if sc else None
    asc, desc = f.getmetrics()
    pad = int(size * S)
    widths = []
    for ch in text:
        if sc and ch.islower():
            widths.append((ch.upper(), fs, fs.getlength(ch.upper())))
        else:
            widths.append((ch, f, f.getlength(ch)))
    tr = track * size * S
    W = int(sum(w for _, _, w in widths) + tr * len(text) + 2 * pad)
    im = Image.new('L', (W, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(im)
    x = pad
    for ch, ff, w in widths:
        d.text((x, pad + asc), ch, font=ff, fill=255, anchor='ls')
        x += w + tr
    bb = im.getbbox()
    im = im.crop(bb)
    if squeeze != 1.0:
        im = im.resize((max(1, int(im.width * squeeze)), im.height), Image.LANCZOS)
    return im


def colorize(mask, fill):
    im = Image.new('RGBA', mask.size, tuple(fill) + (0,))
    im.putalpha(mask)
    return im


def vgrad(mask, stops):
    """fill mask with vertical gradient; stops [(t,(r,g,b)),...]"""
    h = mask.height
    ts = np.linspace(0, 1, h)
    arr = np.zeros((h, mask.width, 4), np.uint8)
    for c in range(3):
        arr[:, :, c] = np.interp(ts, [s[0] for s in stops], [s[1][c] for s in stops])[:, None]
    arr[:, :, 3] = np.asarray(mask)
    return Image.fromarray(arr, 'RGBA')


def rot(im):
    return im.rotate(-90, expand=True, resample=Image.BICUBIC)


def put(base, im, cx, cy):
    """paste RGBA centered at (cx,cy) in final px units"""
    x = int(cx * S - im.width / 2)
    y = int(cy * S - im.height / 2)
    base.alpha_composite(im, (x, y))


def dilate(mask, r):
    return mask.filter(ImageFilter.MaxFilter(2 * int(r) + 1))


def erode(mask, r):
    return mask.filter(ImageFilter.MinFilter(2 * int(r) + 1))


def fbm(h, w, scale, rng, octaves=3):
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    tot = 0
    for o in range(octaves):
        sc = max(1, scale / (2 ** o))
        sh, sw = max(2, int(h / sc) + 2), max(2, int(w / sc) + 2)
        n = rng.standard_normal((sh, sw)).astype(np.float32)
        out += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    return out / tot


def finish(img, seed, gloss=0.0, creases=0, wear=0.5, paper=(238, 232, 220), matte=0.02,
           warm=0.0, fade=0.0, crease_strength=0.6, hinge=False, blur=0.55, jpegq=90, out=None):
    """img: RGBA/RGB at S scale. returns final RGB PIL image."""
    rng = np.random.default_rng(seed)
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255.0
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xn = xx / (w - 1)
    yn = yy / (h - 1)
    pap = np.array(paper, np.float32) / 255.0

    # fading / ink unevenness
    if fade:
        a = a * (1 - fade) + fade * (0.5 * pap + 0.5 * a.mean(axis=2, keepdims=True))
    mott = fbm(h, w, 90 * S, rng, 4)
    a *= (1 + matte * mott)[..., None]

    # creases along the spine (paperbacks)
    if creases:
        cm = np.zeros((h, w), np.float32)
        sh = np.zeros((h, w), np.float32)
        for i in range(creases):
            x0 = rng.uniform(0.12, 0.88) * w
            ys = np.arange(0, h, 8)
            wob = np.cumsum(rng.standard_normal(len(ys))) * 0.9
            wob -= np.linspace(wob[0], wob[-1], len(ys))
            pts = np.stack([x0 + wob, ys], 1).astype(np.int32)
            y0, y1 = sorted(rng.uniform(0, 1, 2))
            if y1 - y0 < 0.35:
                y0, y1 = max(0, y0 - 0.25), min(1, y1 + 0.25)
            sel = pts[(pts[:, 1] >= y0 * h) & (pts[:, 1] <= y1 * h)]
            if len(sel) < 2: continue
            tmp = np.zeros((h, w), np.uint8)
            cv2.polylines(tmp, [sel.reshape(-1, 1, 2)], False, 255, int(rng.integers(1, 3)) * S // 2 + 1, cv2.LINE_AA)
            strength = rng.uniform(0.35, 1.0)
            cm = np.maximum(cm, tmp.astype(np.float32) / 255 * strength)
        # break up along length
        brk = np.clip(fbm(h, w, 30 * S, rng, 3) * 1.6 + 0.55, 0, 1)
        cm = cv2.GaussianBlur(cm * brk, (0, 0), 0.7 * S)
        sh = cv2.GaussianBlur(np.roll(cm, 2 * S, axis=1), (0, 0), 1.6 * S)
        a = a * (1 - 0.22 * crease_strength * sh[..., None])
        k = np.clip(cm * crease_strength, 0, 1)[..., None]
        a = a * (1 - k) + pap * k

    # edge / corner wear
    if wear:
        dy = np.minimum(yy, h - 1 - yy) / S
        dx = np.minimum(xx, w - 1 - xx) / S
        n = fbm(h, w, 5 * S, rng, 3) * 0.6 + fbm(h, w, 28 * S, rng, 2) * 0.6
        # each book wears differently: head and tail get their own amount, often none
        wt, wb = [0.0 if rng.random() < 0.45 else rng.uniform(0.35, 1.0) for _ in range(2)]
        reach = rng.uniform(3, 6 + 7 * wear, 2)
        ey = np.maximum(wt * np.clip(1 - (yy / S) / reach[0], 0, 1) ** 2, wb * np.clip(1 - ((h - 1 - yy) / S) / reach[1], 0, 1) ** 2)
        ex = np.clip(1 - dx / (2.5 + 2.5 * wear), 0, 1) ** 2 * rng.uniform(0.2, 1.0)
        k = np.clip((ey * (0.75 + 0.6 * wear) + ex * 0.55 * wear + n * 0.5 - 0.80) * 3.0, 0, 1) * (0.35 + 0.45 * wear)
        sc = np.clip((fbm(h, w, 10 * S, rng, 4) * fbm(h, w, 150 * S, rng, 2) * 4 - 1.7) * 2.0, 0, 1) * 0.04 * wear
        k = np.clip(k + sc, 0, 1)[..., None]
        a = a * (1 - k) + pap * k

    # light: curvature of the spine + overhead falloff
    curve = 1 - 0.16 * (2 * xn - 1) ** 2 - 0.05 * np.clip(2 * xn - 1, 0, 1) ** 2
    vert = 1.0 - rng.uniform(-0.03, 0.05) * (yn - 0.5) + 0.03 * fbm(h, w, 400 * S, rng, 1)
    a *= (curve * vert)[..., None]
    if hinge:
        for xc in (0.035, 0.965):
            g = np.exp(-((xn - xc) / 0.012) ** 2)
            a *= (1 - 0.10 * g)[..., None]
            g2 = np.exp(-((xn - xc - 0.02) / 0.012) ** 2)
            a += (0.03 * g2)[..., None]
    if gloss:
        band = np.exp(-((xn - 0.33 - 0.03 * fbm(h, w, 300 * S, rng, 2)) / 0.075) ** 2)
        band *= np.clip(0.75 + 0.5 * fbm(h, w, 160 * S, rng, 2), 0.2, 1.2)
        a = 1 - (1 - a) * (1 - gloss * band[..., None])
    # head/tail shadow
    if warm:
        a *= np.array([1 + warm, 1 + warm * 0.35, 1 - warm], np.float32)
    a = np.clip(a, 0, 1)
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((w // S, h // S), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    b = np.asarray(im).astype(np.float32)
    hh, ww, _ = b.shape
    lum = rng.standard_normal((hh, ww, 1)) * 3.2
    chro = rng.standard_normal((hh, ww, 3)) * 1.4
    fine = cv2.GaussianBlur(rng.standard_normal((hh, ww)).astype(np.float32), (0, 0), 1.1)[..., None] * 5.0
    b = np.clip(b + lum + chro + fine, 0, 255).astype(np.uint8)
    im = Image.fromarray(b)
    if out:
        im.save(out, quality=jpegq, subsampling=0)
    return im


def canvas(w, color):
    return Image.new('RGBA', (w * S, H * S), tuple(color) + (255,))


# ---------------------------------------------------------------- VHS finishing
def _lay(a, k, col):
    k = np.clip(k, 0, 1)[..., None]
    return a * (1 - k) + col * k


def finish_vhs(img, seed, kind='slip', wear=0.5, gloss=0.05, fade=0.0, warm=0.0, matte=0.025,
               card=(236, 231, 220), tears=0, dents=0, sun=0.0, blur=0.55, jpegq=90, out=None):
    """img: RGBA/RGB at S scale -> final RGB image.
    kind='slip': printed cardboard slipcase (white board showing at the folds, corners and mouth,
    scuffs, dents, torn patches).  kind='clam': plastic clamshell with a paper insert under a clear
    sleeve (rounded moulded edges, glare streaks, hairline scratches, no cardboard showing).
    Everything is seeded per tape; nothing here is the same on two spines."""
    rng = np.random.default_rng(seed)
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255.0
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xn, yn = xx / (w - 1), yy / (h - 1)
    crd = np.array(card, np.float32) / 255.0
    dx = np.minimum(xx, w - 1 - xx) / S
    dy = np.minimum(yy, h - 1 - yy) / S

    if fade:
        a = a * (1 - fade) + fade * (0.55 * crd + 0.45 * a.mean(axis=2, keepdims=True))
    if sun:  # sun-bleached toward one end, as on a tape that sat in a shop window
        t = np.clip((yn if rng.random() < 0.5 else 1 - yn) * 1.4 - 0.2, 0, 1) * sun
        g = a.mean(axis=2, keepdims=True)
        a = a * (1 - t[..., None]) + (0.6 * g + 0.4 * crd + 0.0 * a) * t[..., None]
    a *= (1 + matte * fbm(h, w, 90 * S, rng, 4))[..., None]

    if kind == 'slip':
        fine = fbm(h, w, 3 * S, rng, 3)
        mid = fbm(h, w, 22 * S, rng, 3)
        # long patchy variation down the length, so rubbing comes and goes
        along = cv2.resize(rng.standard_normal((max(4, h // (60 * S)), 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
        # dents: the board has been crushed across the spine
        for i in range(dents):
            y0 = rng.uniform(0.08, 0.92) * h
            xs = np.arange(0, w + 8, 8)
            wob = np.cumsum(rng.standard_normal(len(xs))) * 1.6 * S
            wob += np.linspace(0, rng.uniform(-14, 14) * S, len(xs))
            x0, x1 = (0, rng.uniform(0.45, 1.0)) if rng.random() < 0.5 else (rng.uniform(0, 0.55), 1)
            pts = np.stack([xs, y0 + wob], 1)
            pts = pts[(pts[:, 0] >= x0 * w) & (pts[:, 0] <= x1 * w)].astype(np.int32)
            if len(pts) < 2: continue
            tmp = np.zeros((h, w), np.uint8)
            cv2.polylines(tmp, [pts.reshape(-1, 1, 2)], False, 255, S, cv2.LINE_AA)
            ln = tmp.astype(np.float32) / 255 * np.clip(mid * 2.2 + 0.7, 0, 1)
            sh = cv2.GaussianBlur(np.roll(ln, 2 * S, axis=0), (0, 0), 2.2 * S)
            hi = cv2.GaussianBlur(np.roll(ln, -2 * S, axis=0), (0, 0), 1.6 * S)
            st = rng.uniform(0.5, 1.0)
            a = a * (1 - 0.5 * st * sh[..., None]) + 0.10 * st * hi[..., None]
            a = _lay(a, cv2.GaussianBlur(ln, (0, 0), 0.6 * S) * st * 0.75, crd)
        # torn patches: the printed paper has lifted off the board
        for i in range(tears):
            cx = rng.choice([rng.uniform(0, 0.25), rng.uniform(0.75, 1.0)]) * w
            cy = rng.uniform(0.06, 0.94) * h
            rx, ry = rng.uniform(8, 20) * S, rng.uniform(14, 46) * S
            d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
            k = np.clip((1 - d + mid * 0.9 + fine * 0.35) * 6, 0, 1)
            rim = np.clip(cv2.GaussianBlur(k, (0, 0), 1.6 * S) - k, 0, 1)
            a = a * (1 - 0.35 * rim[..., None])
            a = _lay(a, k, crd * (0.93 + 0.05 * fine[..., None]))
        if wear:
            # the two folds: a broken white line where ink has rubbed off the crease
            r = 1.2 + 2.6 * wear
            sides = [rng.uniform(0.25, 1.0), rng.uniform(0.25, 1.0)]
            for side, amt in enumerate(sides):
                d = (xx if side == 0 else w - 1 - xx) / S
                ph = np.roll(along, int(rng.integers(0, h)), axis=0)
                k = np.clip(1 - d / (r * (1 + 0.8 * np.clip(ph, 0, 2))), 0, 1) ** 1.3
                k = k * np.clip(ph * 1.1 + fine * 1.4 + 0.15 + 0.9 * wear * amt - 0.45, 0, 1) * 1.6
                a = _lay(a, k * (0.55 + 0.4 * wear), crd)
            # corners: each one knocked a different amount
            for cx_, cy_ in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
                if rng.random() < 0.25: continue
                R = rng.uniform(5, 9 + 24 * wear) * S
                d = np.sqrt((xx - cx_) ** 2 + ((yy - cy_) * rng.uniform(0.5, 1.0)) ** 2) / R
                a = _lay(a, (1 - d + mid * 0.7 + fine * 0.5) * 3.5, crd)
            # mouth and base: frayed board
            wt, wb = [0.0 if rng.random() < 0.3 else rng.uniform(0.4, 1.0) for _ in range(2)]
            reach = rng.uniform(2.5, 5 + 9 * wear, 2)
            ey = np.maximum(wt * np.clip(1 - (yy / S) / reach[0], 0, 1) ** 1.5, wb * np.clip(1 - ((h - 1 - yy) / S) / reach[1], 0, 1) ** 1.5)
            a = _lay(a, (ey * (1.0 + 0.5 * wear) + (fine * 0.7 + mid * 0.5) * np.clip(ey * 4, 0, 1) - 0.55) * 3.0, crd)
            # shelf rub: faint paler bands where neighbours slid past
            for i in range(int(rng.integers(1, 4))):
                yc, hh = rng.uniform(0.05, 0.95), rng.uniform(0.01, 0.05)
                band = np.exp(-((yn - yc) / hh) ** 2) * np.clip(mid * 1.5 + 0.5, 0, 1)
                a = _lay(a, band * 0.10 * wear, crd)
            # scuffs and nicks
            sc = np.zeros((h, w), np.uint8)
            for i in range(int(rng.integers(8, 14 + int(60 * wear)))):
                x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
                ang = rng.normal(0.0, 0.5) + (np.pi / 2 if rng.random() < 0.35 else 0)
                ln = rng.uniform(4, 40) * S
                cv2.line(sc, (int(x0), int(y0)), (int(x0 + math.cos(ang) * ln), int(y0 + math.sin(ang) * ln)),
                         int(rng.uniform(60, 255)), 1 if rng.random() < 0.75 else S, cv2.LINE_AA)
            for i in range(int(40 * wear) + 6):
                cv2.circle(sc, (int(rng.uniform(0, w)), int(rng.uniform(0, h))), int(rng.uniform(0.5, 1.6) * S), int(rng.uniform(80, 255)), -1, cv2.LINE_AA)
            scf = cv2.GaussianBlur(sc.astype(np.float32) / 255, (0, 0), 0.5 * S) * np.clip(mid * 2 + 0.8, 0, 1)
            a = _lay(a, scf * (0.25 + 0.4 * wear), crd)
        # light: a flat board face, slightly lit from one side, folds turning away at the edges
        a *= (1 + rng.uniform(-0.07, 0.07) * (xn - 0.5) - rng.uniform(-0.03, 0.06) * (yn - 0.5) + 0.03 * fbm(h, w, 400 * S, rng, 1))[..., None]
        e0, e1 = rng.uniform(0.08, 0.2, 2)
        a *= (1 - e0 * np.clip(1 - (xx / S) / 5.0, 0, 1) ** 2 - e1 * np.clip(1 - ((w - 1 - xx) / S) / 5.0, 0, 1) ** 2)[..., None]
        if gloss:
            band = np.exp(-((xn - rng.uniform(0.25, 0.7) - 0.04 * fbm(h, w, 300 * S, rng, 2)) / 0.11) ** 2)
            band *= np.clip(0.6 + 0.7 * fbm(h, w, 160 * S, rng, 2), 0.1, 1.2)
            a = 1 - (1 - a) * (1 - gloss * band[..., None])
    else:  # clamshell
        # moulded plastic rounds away at both sides; the sleeve catches light in streaks
        a *= (1 - 0.30 * np.clip(1 - dx / 9.0, 0, 1) ** 2)[..., None]
        for xc, wd, st in ((rng.uniform(0.2, 0.42), 0.035, 1.0), (rng.uniform(0.55, 0.8), 0.09, 0.45)):
            band = np.exp(-((xn - xc - 0.03 * fbm(h, w, 260 * S, rng, 2)) / wd) ** 2)
            band *= np.clip(0.55 + 0.9 * fbm(h, w, 120 * S, rng, 2), 0, 1.3) * st
            a = 1 - (1 - a) * (1 - (0.10 + gloss) * band[..., None])
        # sleeve weld ridge near top and bottom
        for yc in (rng.uniform(8, 13), None):
            yv = yy / S if yc else (h - 1 - yy) / S
            yc = yc or rng.uniform(8, 13)
            a *= (1 - 0.14 * np.exp(-((yv - yc) / 1.2) ** 2))[..., None]
            a += (0.05 * np.exp(-((yv - yc - 2.2) / 1.2) ** 2))[..., None]
        sc = np.zeros((h, w), np.uint8)
        for i in range(int(10 + 50 * wear)):
            x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
            ang = rng.normal(np.pi / 2, 0.35) if rng.random() < 0.6 else rng.uniform(0, np.pi)
            ln = rng.uniform(10, 90) * S
            cv2.line(sc, (int(x0), int(y0)), (int(x0 + math.cos(ang) * ln), int(y0 + math.sin(ang) * ln)), int(rng.uniform(40, 200)), 1, cv2.LINE_AA)
        a = 1 - (1 - a) * (1 - 0.22 * cv2.GaussianBlur(sc.astype(np.float32) / 255, (0, 0), 0.4 * S)[..., None])
        a = a * (1 - 0.04 * wear) + 0.04 * wear  # hazed plastic
        a *= (1 - rng.uniform(-0.03, 0.05) * (yn - 0.5))[..., None]
    if warm:
        a *= np.array([1 + warm, 1 + warm * 0.35, 1 - warm], np.float32)
    a = np.clip(a, 0, 1)
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((w // S, h // S), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    b = np.asarray(im).astype(np.float32)
    hh, ww, _ = b.shape
    lum = rng.standard_normal((hh, ww, 1)) * 3.0
    chro = rng.standard_normal((hh, ww, 3)) * 1.3
    fine = cv2.GaussianBlur(rng.standard_normal((hh, ww)).astype(np.float32), (0, 0), 1.1)[..., None] * 4.5
    im = Image.fromarray(np.clip(b + lum + chro + fine, 0, 255).astype(np.uint8))
    if out:
        im.save(out, quality=jpegq, subsampling=0)
    return im
