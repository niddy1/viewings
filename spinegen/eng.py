from lib import *

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
B = REPO + 'posters/'
CUR = {}  # the poster of the tape being built (for L, lifted lettering)


class T:
    """one line of lettering"""
    def __init__(s, text, font, size, color, track=0.0, squeeze=1.0, sc=None, bold=0, outline=None, shadow=None,
                 soft=None, grad=None, organic=0, rough=0, skew=0, box=None, scs=0.8):
        s.__dict__.update(locals()); del s.__dict__['s']

    def render(s, k=1.0, seed=0):
        m = text_mask(s.text, s.font, s.size * k, s.track, s.squeeze, s.sc, s.scs)
        pad = int((10 + s.size * 0.12) * S * k) + (int(s.box[1] * S) if s.box else 0)
        mm = Image.new('L', (m.width + 2 * pad, m.height + 2 * pad), 0)
        mm.paste(m, (pad, pad))
        if s.bold:
            a = np.asarray(mm).astype(np.float32) / 255
            a = cv2.GaussianBlur(a, (0, 0), max(0.6, s.bold * S * 0.6))
            mm = Image.fromarray((np.clip((a - (0.5 - min(0.42, 0.16 * s.bold * S))) * 6 + 0.5, 0, 1) * 255).astype(np.uint8))
        if s.organic:
            a = np.asarray(dilate(mm, max(1, int(s.organic * 0.5 * S)))).astype(np.float32) / 255
            a = cv2.GaussianBlur(a, (0, 0), s.organic * S * k)
            mm = Image.fromarray((np.clip((a - 0.46) * 9 + 0.5, 0, 1) * 255).astype(np.uint8))
        if s.skew:
            mm = mm.transform(mm.size, Image.AFFINE, (1, s.skew, -s.skew * mm.height / 2, 0, 1, 0), Image.BICUBIC)
        if s.rough:
            rng = np.random.default_rng(seed + len(s.text))
            a = np.asarray(mm).astype(np.float32) / 255
            n = fbm(a.shape[0], a.shape[1], 2.2 * S, rng, 2)
            n2 = fbm(a.shape[0], a.shape[1], 14 * S, rng, 2)
            a = cv2.GaussianBlur(a, (0, 0), 1.0 * S)
            a = np.clip((a + n * 0.5 * s.rough + n2 * 0.2 * s.rough - 0.5) * 7 + 0.5, 0, 1)
            mm = Image.fromarray((a * 255).astype(np.uint8))
        cnv = Image.new('RGBA', mm.size, (0, 0, 0, 0))
        if s.box:
            col, px_, py_ = s.box[0], s.box[1], s.box[2] if len(s.box) > 2 else s.box[1]
            d = ImageDraw.Draw(cnv)
            d.rectangle([pad - px_ * S, pad - py_ * S, pad + m.width + px_ * S, pad + m.height + py_ * S], fill=tuple(col) + (255,),
                        outline=(tuple(s.box[3]) + (255,)) if len(s.box) > 3 else None, width=S)
        if s.soft:
            col, r, al = s.soft
            cnv.alpha_composite(colorize(mm.filter(ImageFilter.GaussianBlur(r * S)).point(lambda v: int(v * al)), col))
        o = dilate(mm, max(1, int(s.outline[1] * S * k))) if s.outline else mm
        if s.shadow:
            col, dx, dy = s.shadow
            n = max(1, int(max(abs(dx), abs(dy)) * S * k))
            for i in range(n, 0, -1):
                cnv.alpha_composite(colorize(ImageChops.offset(o, int(dx * S * k * i / n), int(dy * S * k * i / n)), col))
        if s.outline:
            cnv.alpha_composite(colorize(o, s.outline[0]))
        cnv.alpha_composite(vgrad(mm, s.grad) if s.grad else colorize(mm, s.color))
        s._pad = pad
        return cnv


class V:
    def __init__(s, lines, align='start', gap=13):
        s.lines = lines if isinstance(lines, list) else [lines]; s.align = align; s.gap = gap


class Hh:
    def __init__(s, lines, gap=4, margin=8):
        s.lines = lines if isinstance(lines, list) else [lines]; s.gap = gap; s.margin = margin


class Gap:
    def __init__(s, px): s.px = px


class Flex:
    def __init__(s, w=1.0): s.w = w


class Rule:
    def __init__(s, color, th=1.5, inset=20, double=False): s.color = color; s.th = th; s.inset = inset; s.double = double


class Crop:
    """picture from the cover. box rel (x0,y0,x1,y1) or centred column (cx,y0,y1) fitted to h"""
    def __init__(s, box, h=None, inset=0, border=None, smooth=False, full=False):
        s.box = box; s.h = h; s.inset = inset; s.border = border; s.smooth = smooth


class Block:
    """solid band behind following items until EndBlock"""
    def __init__(s, color, to=None): s.color = color


class Fn:
    def __init__(s, fn, h): s.fn = fn; s.h = h


def w_for(runtime):
    """spine width in the 1100px image. The shelf draws tapes 250px tall and 42-52px wide by runtime."""
    return int(round(H * min(52, max(42, 40 + ((runtime or 105) - 90) * 0.12)) / 250))


class TT(T):
    """one line in several colours: runs = [(text, color), ...] (caps, so the pieces share a height)"""
    def __init__(s, runs, font, size, sp=0.0, **kw):
        T.__init__(s, ''.join(r[0] for r in runs), font, size, runs[0][1], **kw); s.runs = runs; s.sp = sp  # sp: extra gap between runs, in em

    def render(s, k=1.0, seed=0):
        ms = [text_mask(t, s.font, s.size * k, s.track, s.squeeze) for t, _ in s.runs]
        gap = int(s.track * s.size * k * S + s.size * k * S * (0.07 + s.sp))
        pad = int(8 * S)
        hh = max(m.height for m in ms)
        cnv = Image.new('RGBA', (sum(m.width for m in ms) + gap * (len(ms) - 1) + 2 * pad, hh + 2 * pad), (0, 0, 0, 0))
        x = pad
        for m, (_, col) in zip(ms, s.runs):
            cnv.alpha_composite(colorize(m, col), (x, pad + hh - m.height)); x += m.width + gap
        s._pad = pad
        return cnv


def lift_mask(box, mode='auto', key=None, t=(55, 115), cut=(0.35, 0.65), close=0, speck=0.004, k=2, nbg=1, gain=2.4):
    """lettering inside box (fractions of the current poster) as a tight L mask at poster resolution.
    'auto' splits the crop into k colour clusters; the nbg clusters commonest round the edge are background.
    'light' / 'dark' key on brightness; 'key' on distance from colour `key` (t0..t1)."""
    cov = Image.open(CUR['cover']).convert('RGB')
    cw, ch = cov.size
    c = np.asarray(cov.crop((int(box[0] * cw), int(box[1] * ch), int(box[2] * cw), int(box[3] * ch)))).astype(np.float32)
    if mode == 'key':
        d = np.sqrt(((c - np.array(key, np.float32)) ** 2).sum(axis=2))
        m = np.clip(1 - (d - t[0]) / (t[1] - t[0]), 0, 1)
    elif mode == 'auto':
        px = c.reshape(-1, 3)
        cv2.setRNGSeed(7)
        _, lab, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 4, cv2.KMEANS_PP_CENTERS)
        lab = lab.reshape(c.shape[:2])
        edge = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
        order = np.argsort(-np.bincount(edge, minlength=k))
        bgc, fgc = cen[order[:nbg]], cen[order[nbg:]]
        db = np.min(np.stack([np.sqrt(((c - b) ** 2).sum(axis=2)) for b in bgc]), 0)
        df = np.min(np.stack([np.sqrt(((c - f) ** 2).sum(axis=2)) for f in fgc]), 0)
        m = np.clip(0.5 + gain * (db - df) / (db + df + 1e-3), 0, 1)
    else:
        lum = c @ np.array([0.299, 0.587, 0.114], np.float32)
        bg, fg = np.percentile(lum, 50), np.percentile(lum, 99.5 if mode == 'light' else 0.5)
        m = np.clip(((lum - bg) / (fg - bg) - cut[0]) / (cut[1] - cut[0]), 0, 1)
    m = (m * 255).astype(np.uint8)
    if speck:  # drop stray flecks that are not lettering
        n, lab, st, _ = cv2.connectedComponentsWithStats((m > 90).astype(np.uint8), connectivity=8)
        big = st[1:, cv2.CC_STAT_AREA].max() if n > 1 else 0
        keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= speck * big * 10
        m = m * cv2.dilate(keep[lab].astype(np.uint8), np.ones((3, 3), np.uint8))
    m = Image.fromarray(m)
    if close:  # fill hatched or outlined lettering solid
        m = erode(dilate(m, close), close)
    bb = m.point(lambda v: 255 if v > 90 else 0).getbbox()
    return m.crop(bb) if bb else m


class L:
    """title lettering lifted off the poster and re-inked.  box = (x0,y0,x1,y1) fractions of the poster,
    or a list of boxes that are joined into one line (scaled together, so a small "THE" stays small).
    size = height of the lettering on the spine (px in the 1100 image).  color may be a list, one per box.
    grad = vertical stops through the letters; hgrad = stops along the line."""
    def __init__(s, box, size, color, mode='auto', grow=0.0, grad=None, hgrad=None, shadow=None, outline=None, gapf=0.28, valign='base', **mk):
        s.__dict__.update(locals()); del s.__dict__['s']

    def render(s, k=1.0, seed=0):
        boxes = s.box if isinstance(s.box[0], (list, tuple)) else [s.box]
        cols = s.color if isinstance(s.color[0], (list, tuple)) else [s.color] * len(boxes)
        ms = [lift_mask(b, s.mode, **s.mk) for b in boxes]
        th = max(4, int(s.size * k * S))
        f = th / max(m.height for m in ms)
        ms = [m.resize((max(1, int(m.width * f)), max(1, int(m.height * f))), Image.LANCZOS) for m in ms]
        out = []
        for m in ms:
            a = cv2.GaussianBlur(np.asarray(m).astype(np.float32) / 255, (0, 0), max(0.5, th / 160))
            out.append(Image.fromarray((np.clip((a - 0.5 + s.grow) * 5 + 0.5, 0, 1) * 255).astype(np.uint8)))
        gap = int(th * s.gapf)
        pad = int(8 * S) + (int(s.outline[1] * S) if s.outline else 0)
        Wd = sum(m.width for m in out) + gap * (len(out) - 1)
        mm = Image.new('L', (Wd + 2 * pad, th + 2 * pad), 0)
        cnv = Image.new('RGBA', mm.size, (0, 0, 0, 0))
        ink = Image.new('RGBA', mm.size, (0, 0, 0, 0))
        x = pad
        for m, col in zip(out, cols):
            y = pad + (th - m.height if s.valign == 'base' else (th - m.height) // 2)
            mm.paste(m, (x, y))
            one = Image.new('L', mm.size, 0); one.paste(m, (x, y))
            ink.alpha_composite(colorize(one, col)); x += m.width + gap
        if s.grad:
            ink = vgrad(mm, s.grad)
        if s.hgrad:
            ink = vgrad(mm.rotate(90, expand=True), s.hgrad).rotate(-90, expand=True)
        if s.shadow:
            col, ox, oy = s.shadow
            cnv.alpha_composite(colorize(ImageChops.offset(mm, int(ox * S), int(oy * S)), col))
        if s.outline:
            cnv.alpha_composite(colorize(dilate(mm, max(1, int(s.outline[1] * S * k))), s.outline[0]))
        cnv.alpha_composite(ink)
        s._pad = pad
        return cnv


def make_bg(W, bg, cover, rng):
    h, w = H * S, W * S
    kind = bg[0]
    yy = (np.mgrid[0:h, 0:w][0].astype(np.float32)) / h
    if kind == 'solid':
        a = np.ones((h, w, 3), np.float32) * np.array(bg[1], np.float32)
    elif kind == 'grad':
        a = np.zeros((h, w, 3), np.float32)
        for c in range(3):
            a[..., c] = np.interp(yy, [s[0] for s in bg[1]], [s[1][c] for s in bg[1]])
    elif kind == 'bands':
        a = np.zeros((h, w, 3), np.float32)
        for y0, y1, col in bg[1]:
            a[int(y0 * h):int(y1 * h)] = col
    elif kind == 'strip':
        o = bg[1]
        cov = cv2.cvtColor(cv2.imread(cover), cv2.COLOR_BGR2RGB)
        ch, cw = cov.shape[:2]
        sw = int(round(W * ch / H))
        x0 = int(o.get('x0', 0) * cw)
        st = cov[:, x0:x0 + sw][:, ::-1]
        big = cv2.resize(st, (w, h), interpolation=cv2.INTER_CUBIC)
        if o.get('blur'):
            big = cv2.GaussianBlur(big, (0, 0), o['blur'] * S)
        a = big.astype(np.float32)
        a += (fbm(h, w, 3 * S, rng, 2) * 6)[..., None]
        if o.get('dark'):
            a *= (1 - o['dark'])
        if o.get('wash'):
            col, al = o['wash']
            a = a * (1 - al) + np.array(col, np.float32) * al
    return a


def cloth(a, rng, amt=7):
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    weave = np.sin(xx * 2 * np.pi / (2.2 * S)) * np.sin(yy * 2 * np.pi / (2.2 * S))
    weave += 0.6 * fbm(h, w, 2 * S, rng, 1)
    return a + (weave * amt)[..., None]


def build(spec, out=None):
    cover = B + spec.get('cover', f"{spec['id']}.jpg")
    CUR['cover'] = cover
    W = spec.get('W') or w_for(spec.get('runtime'))
    seed = spec.get('seed', sum(map(ord, str(spec['id']))))
    rng = np.random.default_rng(seed)
    a = make_bg(W, spec['bg'], cover, rng)
    if spec.get('cloth'):
        a = cloth(a, rng, spec['cloth'])
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGBA')
    for fn in spec.get('under', []):
        r = fn(im, W, rng)
        if r is not None: im = r
    items = spec['items']
    top, bot = spec.get('top', 34), spec.get('bot', 30)
    covim = None

    def crop_img(it, k=1.0):
        nonlocal covim
        if covim is None: covim = Image.open(cover).convert('RGB')
        cw, ch = covim.size
        tw = W - 2 * it.inset
        if len(it.box) == 3:
            cx, y0, y1 = it.box
            hh = it.h or 300
            ph = (y1 - y0) * ch
            pw = ph * tw / hh
            x0 = min(max(0, cx * cw - pw / 2), cw - pw)
            box = (x0, y0 * ch, x0 + pw, y1 * ch)
        else:
            box = (it.box[0] * cw, it.box[1] * ch, it.box[2] * cw, it.box[3] * ch)
            hh = it.h or tw * (box[3] - box[1]) / (box[2] - box[0])
        c = covim.crop(tuple(int(v) for v in box)).resize((int(tw * S), int(hh * S)), Image.BICUBIC)
        if it.smooth:
            c = c.filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.GaussianBlur(1.2)).filter(ImageFilter.UnsharpMask(4, 120, 2))
        else:
            c = c.filter(ImageFilter.UnsharpMask(3, 70, 2))
        return c, hh

    # measure
    def measure(k):
        res = []
        for it in items:
            if isinstance(it, V):
                ims = [t.render(k, seed) for t in it.lines]
                thick = sum(i.height - 2 * t._pad for i, t in zip(ims, it.lines)) / S + it.gap * (len(ims) - 1)
                ln = max(i.width - 2 * t._pad for i, t in zip(ims, it.lines)) / S
                res.append((it, ims, ln, thick))
            elif isinstance(it, Hh):
                ims = []
                for t in it.lines:
                    i_ = t.render(1.0, seed)
                    mw = (W - 2 * it.margin) * S + 2 * t._pad
                    if i_.width > mw:
                        i_ = t.render(mw / i_.width * 0.98, seed)
                    ims.append(i_)
                ln = sum(i.height - 2 * t._pad for i, t in zip(ims, it.lines)) / S + it.gap * (len(ims) - 1)
                res.append((it, ims, ln, 0))
            elif isinstance(it, Gap): res.append((it, None, it.px, 0))
            elif isinstance(it, Rule): res.append((it, None, 6 if it.double else 2, 0))
            elif isinstance(it, Crop):
                c, hh = crop_img(it); res.append((it, c, hh, 0))
            elif isinstance(it, Fn): res.append((it, None, it.h, 0))
            else: res.append((it, None, 0, 0))
        return res
    k = 1.0
    for _ in range(6):
        res = measure(k)
        tot = sum(r[2] for r in res)
        vt = sum(r[2] for r in res if isinstance(r[0], V))
        over = tot - (H - top - bot)
        wide = max([r[3] / (W - spec.get('side', 14)) for r in res if isinstance(r[0], V)] + [0])
        if over <= 0 and wide <= 1: break
        f = 1.0
        if over > 0: f = min(f, (vt - over) / vt)
        if wide > 1: f = min(f, 1 / wide)
        k *= f * 0.985
    spare = max(0, H - top - bot - sum(r[2] for r in res))
    fw = sum(r[0].w for r in res if isinstance(r[0], Flex))
    y = top + (spare / 2 if fw == 0 and spec.get('center') else 0)
    d = ImageDraw.Draw(im)
    blocks = []
    pos = []
    for it, ims, ln, thick in res:
        pos.append(y)
        if isinstance(it, Flex): y += spare * it.w / fw
        else: y += ln
    # blocks first
    for (it, ims, ln, thick), y0 in zip(res, pos):
        if isinstance(it, Block):
            nxt = [p for (i2, _, _, _), p in zip(res, pos) if isinstance(i2, Block) and p > y0 + 0.5]
            y1 = nxt[0] if nxt else H
            if it.color is not None:
                d.rectangle([0, int(y0 * S), W * S, int(y1 * S)], fill=tuple(it.color) + (255,))
    for (it, ims, ln, thick), y0 in zip(res, pos):
        if isinstance(it, V):
            hs = [(i.height - 2 * t._pad) / S for i, t in zip(ims, it.lines)]
            x = W / 2 + thick / 2
            for i_, t, hh in zip(ims, it.lines, hs):
                l = (i_.width - 2 * t._pad) / S
                off = 0 if it.align == 'start' else ((ln - l) / 2 if it.align == 'center' else ln - l)
                put(im, rot(i_), x - hh / 2, y0 + off + l / 2)
                x -= hh + it.gap
        elif isinstance(it, Hh):
            yy_ = y0
            for i_, t in zip(ims, it.lines):
                hh = (i_.height - 2 * t._pad) / S
                put(im, i_, W / 2, yy_ + hh / 2)
                yy_ += hh + it.gap
        elif isinstance(it, Rule):
            col = tuple(it.color) + (255,)
            d.line([(it.inset * S, y0 * S), ((W - it.inset) * S, y0 * S)], fill=col, width=max(1, int(it.th * S)))
            if it.double:
                d.line([(it.inset * S, (y0 + 4) * S), ((W - it.inset) * S, (y0 + 4) * S)], fill=col, width=max(1, int(it.th * S * 0.5)))
        elif isinstance(it, Crop):
            im.paste(ims, (int(it.inset * S), int(y0 * S)))
            if it.border:
                d.rectangle([int(it.inset * S), int(y0 * S), int(it.inset * S) + ims.width - 1, int(y0 * S) + ims.height - 1],
                            outline=tuple(it.border) + (255,), width=int(1.5 * S))
        elif isinstance(it, Fn):
            it.fn(im, W, y0, rng)
            d = ImageDraw.Draw(im)
    for fn in spec.get('over', []):
        r = fn(im, W, rng)
        if r is not None: im = r
    if spec.get('notch', True):
        notch(im, W, rng)
    fin = dict(spec.get('fin', {}))
    return finish_vhs(im, seed, out=out or (B + f"{spec['id']}-spine-b.jpg"), **fin)


def notch(im, W, rng):
    """the thumb cut-out at the open end of a slipcase, with the black cassette showing through"""
    d = ImageDraw.Draw(im)
    r = W * rng.uniform(0.19, 0.22) * S
    cx, by = W / 2 * S + rng.uniform(-2, 2) * S, H * S
    ry = r * rng.uniform(0.78, 0.9)
    d.ellipse([cx - r - 1.5 * S, by - ry - 1.5 * S, cx + r + 1.5 * S, by + ry + 1.5 * S], fill=(232, 228, 216, 255))  # cut edge of the board
    d.ellipse([cx - r, by - ry, cx + r, by + ry], fill=(14, 14, 15, 255))
    d.ellipse([cx - r * 0.86, by - ry * 0.55, cx + r * 0.86, by + ry], fill=(26, 26, 28, 255))  # the cassette shell catching light
