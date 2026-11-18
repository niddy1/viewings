# The Vault: films from the bulk-rated years (2007-2015), one shelf per decade of release (vault-<decade>.json).
# Run through tapes.py (exec'd at its end, same namespace): python3 spinegen/tapes.py <id> ...
# Made like the 2016-2025 shelves: lettering measured off each poster and lifted or cut in its own colours
# (each spec's comment says where and why a title is typeset), a poster crop picked for each film, credits and
# typed labels read from IMDb (JSON-LD director/actor, company credits for films with no logo file), and the
# layouts, stickers, picture shapes and foot styles mixed to the 2026 targets (see CLAUDE.md).

def _turn(rgb, al, rot):
    """turn a cut-out (rgb + alpha) by rot degrees, growing the canvas so nothing is clipped"""
    hgt, wid = al.shape; M = cv2.getRotationMatrix2D((wid / 2, hgt / 2), rot, 1)
    c_, s_ = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(hgt * s_ + wid * c_), int(hgt * c_ + wid * s_)
    M[0, 2] += nw / 2 - wid / 2; M[1, 2] += nh / 2 - hgt / 2
    return cv2.warpAffine(rgb, M, (nw, nh), flags=cv2.INTER_CUBIC), cv2.warpAffine(al, M, (nw, nh), flags=cv2.INTER_LINEAR)


def comp_cut(test, keep=None, top=None, soft=1.4, rot=0):
    """an LC cut that keeps whole letters: the connected pieces passing test (rgb 0..1), filtered by
    keep(cx, cy) (the piece's centre, as fractions of the cut-out crop) and/or only the `top` biggest.
    For lettering that interlocks on the poster (arched, stacked or overlapping words), where a straight
    box edge would take slices of the neighbouring word."""
    def fn(rgb):
        a = rgb.astype(np.float32) / 255
        m = cv2.morphologyEx(test(a).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        h, w = m.shape; ok = np.zeros(n, bool)
        big = st[1:, cv2.CC_STAT_AREA].max() if n > 1 else 0
        for j in range(1, n):
            ok[j] = st[j, cv2.CC_STAT_AREA] > big * .015 and (keep is None or keep(cen[j][0] / w, cen[j][1] / h))
        if top:
            idx = [j for j in range(1, n) if ok[j]]; idx.sort(key=lambda j: -st[j, cv2.CC_STAT_AREA])
            ok[:] = False; ok[idx[:top]] = True
        al = _soft(ok[lab].astype(np.float32), soft)
        return _turn(rgb, al, rot) if rot else (rgb, al)
    return fn


def pick_cut(test, box, pts, margin=6, r=.025, flat=False, rot=0, soft=1.4, split=0):
    """an LC cut that keeps the letters whose centres lie within r (fraction of the poster width) of pts
    (poster fractions, read off the poster with the comps tool), so a word can be taken out of lettering
    that interlocks with its neighbours.  flat=True drops each letter onto one baseline (lettering that
    climbs the poster in steps, as At the Opera's); rot turns the cut word by that many degrees (lettering
    set on a slant).  box and margin must be the LC's own."""
    def fn(rgb):
        cw, ch = Image.open(CUR['cover']).size
        k = rgb.shape[1] / ((int(box[2] * cw) + margin) - max(0, int(box[0] * cw) - margin))
        ox, oy = max(0, int(box[0] * cw) - margin), max(0, int(box[1] * ch) - margin)
        a = rgb.astype(np.float32) / 255
        m = cv2.morphologyEx(test(a).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.erode(m, np.ones((split, split), np.uint8)) if split else m)
        P = lambda j: ((ox + cen[j][0] / k) / cw, (oy + cen[j][1] / k) / ch)
        keep = {j for j in range(1, n) if st[j, 4] > 30 and any((P(j)[0] - px) ** 2 + ((P(j)[1] - py) * ch / cw) ** 2 < r * r for px, py in pts)}
        for px, py in pts:  # a point inside a piece's outline box picks that piece (letters that join up when enlarged)
            qx, qy = (px * cw - ox) * k, (py * ch - oy) * k
            inb = [j for j in range(1, n) if st[j, 4] > 30 and st[j, 0] <= qx <= st[j, 0] + st[j, 2] and st[j, 1] <= qy <= st[j, 1] + st[j, 3]]
            if inb: keep.add(min(inb, key=lambda j: (cen[j][0] - qx) ** 2 + (cen[j][1] - qy) ** 2))
        keep = sorted(keep)
        if split:  # grow the picked pieces back over the letters they were eroded from (touching letters stay apart)
            grown = np.zeros_like(lab)
            for j in keep: grown[(cv2.dilate((lab == j).astype(np.uint8), np.ones((split + 2, split + 2), np.uint8)) > 0) & (m > 0) & (grown == 0)] = j
            lab = grown
            for j in keep:
                ys, xs = np.where(lab == j)
                if len(xs): st[j, :4] = [xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1]
        al = _soft(np.isin(lab, keep).astype(np.float32), soft)
        if flat and keep:  # every letter onto one baseline, keeping their spacing across
            pad = 4; rise = max(st[j, 3] for j in keep) + 2 * pad; hh = rise + 2
            nr = np.zeros((hh, rgb.shape[1], 3), np.uint8); na = np.zeros((hh, rgb.shape[1]), np.float32)
            for j in keep:
                x, y, w, h = st[j, :4]
                x0, x1 = max(0, x - pad), min(rgb.shape[1], x + w + pad); y0, y1 = max(0, y - pad), min(rgb.shape[0], y + h + pad)
                ty0 = (hh - 1 - pad) - ((y + h) - y0)          # the letter's bottom lands on row hh-1-pad
                if ty0 < 0: y0 -= ty0; ty0 = 0
                pa = _soft((lab[y0:y1, x0:x1] == j).astype(np.float32), soft)
                ty1 = min(hh, ty0 + (y1 - y0)); pa = pa[:ty1 - ty0]
                sub = na[ty0:ty1, x0:x1]; mm = pa > sub
                nr[ty0:ty1, x0:x1][mm] = rgb[y0:y0 + (ty1 - ty0), x0:x1][mm]; na[ty0:ty1, x0:x1] = np.maximum(sub, pa)
            rgb, al = nr, na
        if rot:
            hgt, wid = al.shape; M = cv2.getRotationMatrix2D((wid / 2, hgt / 2), rot, 1)
            c_, s_ = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(hgt * s_ + wid * c_), int(hgt * c_ + wid * s_)
            M[0, 2] += nw / 2 - wid / 2; M[1, 2] += nh / 2 - hgt / 2
            rgb = cv2.warpAffine(rgb, M, (nw, nh), flags=cv2.INTER_CUBIC); al = cv2.warpAffine(al, M, (nw, nh), flags=cv2.INTER_LINEAR)
        return rgb, al
    return fn


def seq_cut(test, box, pts, margin=6, gapf=.1, space=.45, soft=1.4, turn=None, holes=0):
    """an LC cut that rebuilds a word from the poster's own letters: pts are the letters' centres in reading
    order (poster fractions; None for a word space).  Each letter is turned level along the line through its
    neighbours (lettering set on an arc, as Grand Illusion's) and the letters are laid on one baseline.
    turn: optional list of per-letter angles (degrees) instead of the ones worked out from the arc."""
    def fn(rgb):
        cw, ch = Image.open(CUR['cover']).size
        ox, oy = max(0, int(box[0] * cw) - margin), max(0, int(box[1] * ch) - margin)
        k = rgb.shape[1] / ((int(box[2] * cw) + margin) - ox)
        a = rgb.astype(np.float32) / 255
        m = cv2.morphologyEx(test(a).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        Q = [None if p_ is None else ((p_[0] * cw - ox) * k, (p_[1] * ch - oy) * k) for p_ in pts]
        real = [q for q in Q if q is not None]
        letters = []; ri = 0
        for q in Q:
            if q is None: letters.append(None); continue
            big_ = st[1:, cv2.CC_STAT_AREA].max()
            j = min([j for j in range(1, n) if st[j, cv2.CC_STAT_AREA] > big_ * .03], key=lambda j: (cen[j][0] - q[0]) ** 2 + (cen[j][1] - q[1]) ** 2)
            prv, nxt = real[max(0, ri - 1)], real[min(len(real) - 1, ri + 1)]
            ang = np.degrees(np.arctan2(nxt[1] - prv[1], nxt[0] - prv[0])) if turn is None else turn[ri]
            x, y, w, h = st[j, :4]; pd = int(max(w, h) * .3) + 4
            x0, y0, x1, y1 = max(0, x - pd), max(0, y - pd), min(rgb.shape[1], x + w + pd), min(rgb.shape[0], y + h + pd)
            pm = (lab[y0:y1, x0:x1] == j).astype(np.uint8)
            if holes:  # fill small holes (Dumbo's white dots), keep the letters' counters open
                inv = 1 - pm; nh_, lh, sh, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
                for q in range(1, nh_):
                    if sh[q, 4] < holes * pm.sum() and not (sh[q, 0] == 0 or sh[q, 1] == 0 or sh[q, 0] + sh[q, 2] >= pm.shape[1] or sh[q, 1] + sh[q, 3] >= pm.shape[0]): pm[lh == q] = 1
            al = _soft(pm.astype(np.float32), soft); col = rgb[y0:y1, x0:x1]
            M = cv2.getRotationMatrix2D(((x1 - x0) / 2, (y1 - y0) / 2), ang, 1)
            al = cv2.warpAffine(al, M, (x1 - x0, y1 - y0)); col = cv2.warpAffine(col, M, (x1 - x0, y1 - y0), flags=cv2.INTER_CUBIC)
            ys, xs = np.where(al > .3)
            letters.append((col[ys.min():ys.max() + 1, xs.min():xs.max() + 1], al[ys.min():ys.max() + 1, xs.min():xs.max() + 1]))
            ri += 1
        hs = sorted(l[1].shape[0] for l in letters if l); H_ = hs[len(hs) // 2]; top = max(hs)
        g = int(H_ * gapf); sp = int(H_ * space)
        W_ = sum((l[1].shape[1] + g) if l else sp for l in letters) + 8
        out_c = np.zeros((top + 8, W_, 3), np.uint8); out_a = np.zeros((top + 8, W_), np.float32); x = 4
        for l in letters:
            if not l: x += sp; continue
            c_, a_ = l; hh, ww = a_.shape; y0 = top + 4 - hh
            sub = out_a[y0:y0 + hh, x:x + ww]; mm = a_ > sub
            out_c[y0:y0 + hh, x:x + ww][mm] = c_[mm]; out_a[y0:y0 + hh, x:x + ww] = np.maximum(sub, a_); x += ww + g
        return out_c, out_a
    return fn


def plate_cut(test, rot=0, soft=1.2):
    """an LC cut for a title printed on a sign or panel: the biggest piece passing test (the panel), its
    holes filled so the lettering printed on it comes along in its own colours, turned by rot degrees"""
    def fn(rgb):
        a = rgb.astype(np.float32) / 255
        m = cv2.morphologyEx(test(a).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        if n < 2: return rgb, m.astype(np.float32)
        j = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); p = (lab == j).astype(np.uint8)
        ff = cv2.copyMakeBorder(1 - p, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
        cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 2)
        p = (ff[1:-1, 1:-1] != 2).astype(np.float32)
        al = _soft(p, soft)
        return _turn(rgb, al, rot) if rot else (rgb, al)
    return fn


CC_YEL = lambda a: (a[..., 0] > .78) & (a[..., 1] > .62) & (a[..., 2] < .5)   # Charlie Chan poster yellow

# =====================================================================================
# 1930s (vault-1930s.json, 33 tapes)
# =====================================================================================

# Le Million (1931): the poster's cream and the brown sun, the black stencil LE MILLION keyed off it, the couple dancing among the flowers (no logo file: Films Sonores Tobis, from IMDb's company credits)
std('le-million-1931', ('grad', [(0, (238, 228, 210)), (.6, (222, 206, 180)), (1, (150, 116, 92))]), (26, 22, 22),
    L((0.025, 0.655, 0.975, 0.737), 84, (26, 22, 22), mode='key', key=(28, 24, 24), t=(70, 150)),
    photo=ph(0.48, 0.27, 0.66, 1.0), pb=(26, 22, 22), studio=['FILMS SONORES', 'TOBIS'], scol=(26, 22, 22), order='lPTCF',
    credit=['UN FILM DE', 'RENÉ CLAIR'], ccol=(26, 22, 22), ft='c', fcol=(26, 22, 22), fin=OLD, seed=1931)

# Boudu Saved from Drowning (1932): the poster's teal, the fat black BOUDU edged in white and the deco subtitle lifted together, Michel Simon's orange face
std('boudu-saved-from-drowning-1932', ('grad', [(0, (70, 160, 158)), (.6, (34, 100, 104)), (1, (10, 40, 44))]), (22, 22, 22),
    L([(0.02, 0.1, 0.99, 0.27), (0.105, 0.29, 0.905, 0.345)], 104, (22, 22, 22), mode='dark', gapf=.18, outline=((240, 232, 214), 2.6)),
    photo=ph(0.5, 0.64, 0.92, 0.75), pb=(240, 232, 214), order='PTCF', credit=['MICHEL SIMON'], ccol=(240, 232, 214),
    ft='b', fcol=(220, 230, 226), fin=OLD, seed=1932)

# The Most Dangerous Game (1932): black, the white geometric capitals lifted word by word in two lines, Zaroff's face from the top of the poster
std('the-most-dangerous-game-1932', ('grad', [(0, (34, 40, 40)), (.6, (12, 14, 14)), (1, (2, 2, 2))]), WHT,
    [L([(0.045, 0.468, 0.23, 0.527), (0.045, 0.532, 0.5, 0.592)], 64, WHT, mode='light', gapf=.3),
     L([(0.045, 0.596, 0.7, 0.656), (0.38, 0.66, 0.7, 0.72)], 64, WHT, mode='light', gapf=.3)],
    tgap=10, photo=ph(0.77, 0.2, 0.42, 1.4), pb=(150, 200, 196), lg=WHT, lw=.5, order='LPTSF', stick=RWD(),
    ft='d', fcol=(200, 210, 208), fin=RENTAL, seed=1932)

# Babes in Toyland (1934): the poster's Christmas green, its white BABES IN TOY LAND lifted word by word (TOY keeps its tilt, the scrolls between the words left out) and edged in its red, Laurel and Hardy (no logo file: the stars in type)
std('babes-in-toyland-1934', ('grad', [(0, (40, 130, 70)), (.6, (18, 80, 44)), (1, (6, 30, 16))]), WHT,
    L([(0.185, 0.468, 0.835, 0.567), (0.395, 0.574, 0.6, 0.656), (0.08, 0.662, 0.43, 0.782), (0.42, 0.696, 0.935, 0.822)], 96, WHT, mode='light', gapf=.2, speck=.02, outline=((210, 30, 34), 3)),
    photo=ph(0.52, 0.22, 0.9, 0.7), pb=(214, 32, 36), order='PTCF', credit=['STAN LAUREL', 'OLIVER HARDY'], ccol=WHT,
    ft='e', vbox=(214, 32, 36), fcol=(220, 230, 220), fin=OLD, seed=1934)

# Charlie Chan in London (1934): the poster's navy, the yellow condensed capitals keyed off it in two lines, Chan's face over the table
std('charlie-chan-in-london-1934', ('grad', [(0, (40, 56, 110)), (.6, (20, 28, 60)), (1, (6, 8, 20))]), (250, 218, 110),
    [L((0.01, 0.0, 0.985, 0.11), 70, (250, 218, 110), mode='key', key=(240, 215, 110), t=(70, 150)),
     L([(0.245, 0.122, 0.316, 0.158), (0.01, 0.163, 0.67, 0.275)], 70, (250, 218, 110), mode='key', key=(240, 215, 110), t=(70, 150), gapf=.25)],
    tgap=10, photo=ph(0.66, 0.46, 0.56, 1.0), pb=(250, 218, 110), lg=(250, 218, 110), lw=.66, order='LPTF',
    ft='a', vbox=(250, 218, 110), vink=(20, 28, 60), fcol=(220, 214, 196), fin=OLD, seed=1934)

# It Happened One Night (1934): the poster's cream, the red-orange deco capitals keyed off it, the kiss under the title
std('it-happened-one-night-1934', ('grad', [(0, (248, 238, 214)), (.6, (236, 218, 184)), (1, (176, 140, 100))]), (226, 64, 20),
    [L((0.19, 0.782, 0.805, 0.835), 62, (226, 64, 20), mode='key', key=(220, 70, 40), t=(70, 150)),
     L((0.225, 0.853, 0.745, 0.905), 62, (226, 64, 20), mode='key', key=(220, 70, 40), t=(70, 150))],
    tgap=10, photo=ph(0.5, 0.25, 1.0, 0.72), pb=(226, 64, 20), lg=(40, 30, 26), lw=.66, order='LTPCF',
    credit=['CLARK GABLE', 'CLAUDETTE COLBERT'], ccol=(60, 40, 30), ft='c', fcol=(60, 40, 30), fin=OLD, seed=1934)

# The Black Cat (1934): the poster's black and night blue, the neon script The and outlined BLACK CAT cut off it in their own colours (the poster's tilt kept), the woman in yellow laid on the altar
std('the-black-cat-1934', ('grad', [(0, (24, 40, 80)), (.6, (8, 12, 26)), (1, (2, 2, 4))]), (236, 90, 40),
    LC([(0.215, 0.752, 0.35, 0.822), (0.215, 0.818, 0.97, 0.948)], 100, gapf=.12, valign='base',
       cuts=[comp_cut(lambda a: ((a[..., 0] > .6) & (a[..., 2] < .55) & (a[..., 1] < .8)) | (_lum(a) > .8), keep=lambda x, y: x > .1), comp_cut(lambda a: ((a[..., 0] > .6) & (a[..., 2] < .55) & (a[..., 1] < .75)) | ((_lum(a) > .8) & (_sat(a) < .12)), keep=lambda x, y: x > .1)]),
    photo=ph(0.5, 0.37, 0.96, 0.62), pb=(236, 90, 40), lg=WHT, lw=.66, order='LPTF', dotst=('HORROR', (236, 90, 40), WHT),
    ft='b', fcol=(190, 196, 210), fin=RENTAL, seed=1934)

# Charlie Chan in Egypt (1935): the poster's red, the yellow capitals with their dark-red drop shadow keyed off it in two lines, Chan's face from the top of the poster
std('charlie-chan-in-egypt-1935', ('grad', [(0, (226, 40, 34)), (.6, (160, 20, 20)), (1, (60, 8, 8))]), (252, 220, 70),
    [L([(0.015, 0.54, 0.745, 0.66), (0.15, 0.668, 0.64, 0.785)], 64, (252, 222, 72), mode='key', key=(245, 215, 80), t=(70, 150), gapf=.2, shadow=((90, 10, 10), 3, 3)),
     L([(0.315, 0.784, 0.39, 0.836), (0.09, 0.836, 0.715, 0.952)], 64, (252, 222, 72), mode='key', key=(245, 215, 80), t=(70, 150), gapf=.2, shadow=((90, 10, 10), 3, 3))],
    tgap=8, photo=ph(0.66, 0.16, 0.66, 0.85), pb=(252, 222, 72), lg=(252, 222, 72), lw=.62, order='LPTF',
    ft='e', vbox=(252, 222, 72), vink=(160, 20, 20), fcol=(252, 230, 200), fin=OLD, seed=1935)

# Charlie Chan in Paris (1935): the poster's paper cream, the red CHARLIE CHAN and blue in PARIS cut off it in their own colours, Chan's painted face
std('charlie-chan-in-paris-1935', ('grad', [(0, (240, 230, 206)), (.6, (226, 210, 180)), (1, (160, 136, 100))]), (200, 40, 40),
    [LC([(0.18, 0.622, 0.625, 0.69), (0.215, 0.7, 0.515, 0.755)], 60, gapf=.22, cuts=[key_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .42) & (a[..., 2] < .42))] * 2),
     LC([(0.29, 0.738, 0.93, 0.89)], 76, cuts=[key_cut(lambda a: (a[..., 2] > .45) & (a[..., 0] < .45) & (a[..., 2] > a[..., 0] + .15))])],
    tgap=10, photo=ph(0.5, 0.25, 0.86, 0.72), pb=(40, 70, 160), order='LPTSF', stick=BAR('791.4 CHA', top='MYSTERY', fill=(230, 222, 200)),
    ft='d', fcol=(60, 40, 30), fin=RENTAL, seed=1935)

# Charlie Chan in Shanghai (1935): black, the yellow brush script keyed off it word by word (the poster's slant kept), Chan's green-lit face (directed by, from IMDb)
std('charlie-chan-in-shanghai-1935', ('grad', [(0, (40, 30, 26)), (.6, (12, 8, 8)), (1, (2, 2, 2))]), (250, 220, 80),
    [L([(0.33, 0.37, 0.81, 0.52), (0.32, 0.52, 0.75, 0.675)], 76, (250, 222, 84), mode='key', key=(245, 215, 80), t=(70, 150), gapf=.2),
     L([(0.44, 0.672, 0.61, 0.75), (0.09, 0.74, 0.735, 0.91)], 76, (250, 222, 84), mode='key', key=(245, 215, 80), t=(70, 150), gapf=.2)],
    tgap=8, photo=ph(0.17, 0.27, 0.34, 1.45), pb=(226, 40, 34), order='gPTCF', credit=['DIRECTED BY', 'JAMES TINLING'],
    ccol=(250, 222, 84), ft='a', vbox=(250, 222, 84), vink=(12, 8, 8), fcol=(200, 196, 190), fin=OLD, seed=1935)

# The 39 Steps (1935): the poster's grey sky, its teal THE, 39 and slanted STEPS cut off it letter by letter (they interlock, so each piece keeps only its own letters) into one line, the man running across the moor under it (no logo file: Gaumont British, from IMDb's company credits)
TEAL39 = lambda a: (a[..., 1] > a[..., 0] + .12) & (a[..., 0] < .35) & (a[..., 1] > .25)
std('the-39-steps-1935', ('grad', [(0, (214, 216, 214)), (.6, (176, 178, 176)), (1, (80, 82, 80))]), (16, 112, 104),
    LC([(0.3, 0.255, 0.49, 0.315), (0.32, 0.288, 0.645, 0.476), (0.43, 0.418, 0.73, 0.528)], 128, gapf=.12, valign='mid', margin=0,
       cuts=[comp_cut(TEAL39, keep=lambda x, y: y < .7), comp_cut(TEAL39, top=2), comp_cut(TEAL39, keep=lambda x, y: not (x < .12 and y < .25))]),
    photo=ph(0.52, 0.73, 1.0, 0.48), pb=(30, 30, 30), studio=['GAUMONT', 'BRITISH'], scol=(30, 30, 30), order='lTPF',
    ft='a', vbox=(16, 112, 104), fcol=(30, 30, 30), fin=OLD, seed=1935)

# Charlie Chan at the Circus (1936): the poster's deep sea-green, its arched yellow CHARLIE CHAN, the stacked AT THE and arched CIRCUS cut off it letter by letter (the words interlock under the arch), Chan's face (20th Century Fox in type)
std('charlie-chan-at-the-circus-1936', ('grad', [(0, (30, 70, 72)), (.6, (12, 34, 36)), (1, (4, 12, 12))]), (250, 210, 80),
    [LC([(0.0, 0.0, 1.0, 0.215)], 70, margin=0, cuts=[comp_cut(CC_YEL, keep=lambda x, y: y < .63 or x < .13 or x > .87)]),
     LC([(0.08, 0.18, 0.32, 0.31), (0.29, 0.12, 0.9, 0.275)], 70, gapf=.12, margin=0,
        cuts=[comp_cut(CC_YEL, keep=lambda x, y: x < .9 and not (x < .15 and y < .15)), comp_cut(CC_YEL, keep=lambda x, y: y > .3)])],
    tgap=8, photo=ph(0.68, 0.475, 0.56, 1.1), pb=(250, 212, 84), studio=['20TH CENTURY-FOX'], scol=(250, 212, 84), order='lPTF',
    ft='c', vbox=(250, 212, 84), vink=(12, 34, 36), fcol=(200, 214, 210), fin=OLD, seed=1936)

# Charlie Chan at the Opera (1936): night black, the yellow Charlie CHAN and AT THE OPERA cut off it letter by letter and set on one baseline (on the poster they climb in steps), Karloff and Chan from the top of the poster
CCOP = lambda a: (a[..., 0] > .78) & (a[..., 1] > .55) & (a[..., 2] < .5)
std('charlie-chan-at-the-opera-1936', ('grad', [(0, (40, 34, 60)), (.6, (14, 12, 24)), (1, (4, 4, 8))]), (250, 200, 90),
    [LC([(0.0, 0.38, 0.72, 0.62)], 74, cuts=[pick_cut(CCOP, (0.0, 0.38, 0.72, 0.62), [(0.071, 0.553), (0.251, 0.535), (0.381, 0.49), (0.467, 0.474), (0.551, 0.464), (0.63, 0.442)], flat=True)]),
     LC([(0.05, 0.37, 1.0, 0.75)], 74, cuts=[pick_cut(CCOP, (0.05, 0.37, 1.0, 0.75), [(0.114, 0.686), (0.183, 0.655), (0.292, 0.636), (0.378, 0.623), (0.463, 0.611), (0.595, 0.587), (0.686, 0.559), (0.767, 0.552), (0.851, 0.535), (0.935, 0.527)], flat=True)])],
    tgap=8, photo=ph(0.5, 0.16, 1.0, 0.5), pb=(250, 200, 90), lg=(250, 200, 90), lw=.55, order='LPTCF', credit=['WARNER OLAND', 'BORIS KARLOFF'],
    ccol=(230, 220, 200), ft='b', fcol=(200, 196, 210), fin=OLD, seed=1936)

# Charlie Chan at the Race Track (1936): the poster's ink black, its yellow italic capitals keyed off it (the small stacked at the kept in line), the two binocular views of the race
std('charlie-chan-at-the-race-track-1936', ('grad', [(0, (30, 40, 70)), (.6, (10, 14, 26)), (1, (2, 4, 8))]), (252, 226, 40),
    [L((0.005, 0.632, 0.995, 0.756), 70, (252, 228, 40), mode='key', key=(250, 225, 40), t=(70, 150)),
     L([(0.005, 0.764, 0.18, 0.889), (0.19, 0.764, 1.0, 0.889)], 70, (252, 228, 40), mode='key', key=(250, 225, 40), t=(70, 150), gapf=.18)],
    tgap=8, photo=ph(0.5, 0.45, 1.0, 0.42), pb=(252, 228, 40), order='TPCF', credit=['A H. BRUCE HUMBERSTONE', 'PRODUCTION'],
    ccol=(252, 228, 40), ft='d', vbox=(252, 228, 40), vink=(10, 14, 26), fcol=(200, 204, 214), fin=OLD, seed=1936)

# Charlie Chan's Secret (1936): black, the orange-yellow CHARLIE and CHAN'S straightened off their rise and SECRET set on one line from its arc, Chan's face from the foot of the poster
CCSE = lambda a: (a[..., 0] > .8) & (a[..., 1] > .45) & (a[..., 2] < .4)
std('charlie-chan-s-secret-1936', ('grad', [(0, (36, 30, 26)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (250, 170, 40),
    [LC([(0.05, 0.0, 0.89, 0.2)], 62, cuts=[pick_cut(CCSE, (0.05, 0.0, 0.89, 0.2), [(0.112, 0.149), (0.24, 0.134), (0.378, 0.119), (0.505, 0.098), (0.616, 0.087), (0.713, 0.069), (0.813, 0.055)], rot=-11)]),
     LC([(0.05, 0.14, 0.75, 0.33), (0.43, 0.26, 1.0, 0.49)], 62, gapf=.2, cuts=[pick_cut(CCSE, (0.05, 0.14, 0.75, 0.33), [(0.113, 0.278), (0.243, 0.261), (0.38, 0.246), (0.514, 0.225), (0.587, 0.173), (0.673, 0.2)], rot=-11),
                                                           pick_cut(CCSE, (0.43, 0.26, 1.0, 0.49), [(0.49, 0.447), (0.545, 0.389), (0.621, 0.345), (0.724, 0.314), (0.847, 0.304), (0.953, 0.311)], flat=True)])],
    tgap=8, photo=ph(0.68, 0.72, 0.62, 1.25), pb=(250, 172, 44), lg=(250, 172, 44), lw=.55, order='LPTSF', stick=flow(dot, 74, ['CRIME'], (250, 172, 44), (12, 10, 8)),
    ft='e', fcol=(210, 200, 190), fin=OLD, seed=1936)

# Charlie Chan on Broadway (1937): black, the yellow CHARLIE CHAN ON BROADWAY cut off it word by word and turned level (the poster sets it on a 21-degree rise), Chan's face from the poster's right
CCBW = lambda a: (a[..., 0] > .78) & (a[..., 1] > .62) & (a[..., 2] < .45)
std('charlie-chan-on-broadway-1937', ('grad', [(0, (60, 70, 100)), (.6, (16, 18, 30)), (1, (4, 4, 8))]), (252, 236, 30),
    [LC([(0.02, 0.12, 0.4, 0.26), (0.04, 0.17, 0.43, 0.38)], 64, gapf=.2, cuts=[
        pick_cut(CCBW, (0.02, 0.12, 0.4, 0.26), [(0.061, 0.225), (0.121, 0.207), (0.176, 0.193), (0.224, 0.179), (0.271, 0.171), (0.303, 0.162), (0.339, 0.153)], rot=-21, r=.02),
        pick_cut(CCBW, (0.04, 0.17, 0.43, 0.38), [(0.099, 0.301), (0.188, 0.281), (0.28, 0.261), (0.363, 0.234)], rot=-21, r=.02)]),
     LC([(0.24, 0.29, 0.35, 0.35), (0.0, 0.29, 0.62, 0.51)], 64, gapf=.2, cuts=[
        pick_cut(CCBW, (0.24, 0.29, 0.35, 0.35), [(0.272, 0.326), (0.314, 0.318)], rot=-21, r=.02),
        pick_cut(CCBW, (0.0, 0.29, 0.62, 0.51), [(0.047, 0.454), (0.127, 0.437), (0.196, 0.412), (0.266, 0.403), (0.329, 0.378), (0.419, 0.357), (0.502, 0.352), (0.555, 0.32)], rot=-21, r=.02)])],
    tgap=10, photo=ph(0.75, 0.2, 0.5, 1.2), pb=(252, 236, 30), studio=['20TH CENTURY-FOX'], scol=(252, 236, 30), order='lPTF',
    ft='a', vbox=(252, 236, 30), vink=(16, 18, 30), fcol=(200, 200, 210), fin=OLD, seed=1937)

# Sabotage (1936): Piccadilly at night, the lit circus, the red white-edged SABOTAGE cut off its sign in its own colours (director from IMDb)
std('sabotage-1936', ('grad', [(0, (60, 50, 90)), (.6, (24, 18, 40)), (1, (6, 4, 12))]), (214, 30, 36),
    LC([(0.095, 0.138, 0.9, 0.276)], 100, margin=0, cuts=[comp_cut(lambda a: ((a[..., 0] > .55) & (a[..., 1] < .3) & (a[..., 2] < .35)) | ((_lum(a) > .85) & (_sat(a) < .15)), keep=lambda x, y: .03 < x < .99)]),
    photo=ph(0.52, 0.665, 0.7, 1.3), pb=(238, 230, 214), order='PTCF', credit=['DIRECTED BY', 'ALFRED HITCHCOCK'], ccol=(238, 230, 214),
    ft='e', vbox=(214, 30, 36), fcol=(210, 200, 214), fin=OLD, seed=1936)

# The Case of the Black Cat (1936): the poster's sepia, its speckled ochre THE CASE OF THE and the big BLACK CAT lifted (keyed on the black round them, specks filled) and re-inked cream, the two faces under the title
std('the-case-of-the-black-cat-1936', ('grad', [(0, (150, 104, 56)), (.6, (82, 54, 28)), (1, (24, 14, 6))]), (244, 226, 180),
    [L([(0.04, 0.132, 0.15, 0.162), (0.0, 0.162, 0.41, 0.222)], 34, (244, 226, 180), mode='nkey', key=(24, 16, 10), t=(60, 140), gapf=.25, close=2),
     L([(0.0, 0.224, 1.0, 0.382), (0.3, 0.378, 0.95, 0.514)], 78, (244, 226, 180), mode='nkey', key=(24, 16, 10), t=(60, 140), gapf=.25, close=3)],
    tgap=8, photo=ph(0.5, 0.77, 0.82, 0.9), pb=(244, 226, 180), lw=.5, order='LTPSF', stick=PRC(['$2.49', 'MYSTERY']),
    ft='b', fcol=(230, 214, 180), fin=RENTAL, seed=1936)

# The Lower Depths (1936): the photograph's greys, the white the lower depths lifted in its own mixed weights, Gabin and Junie Astor under it
std('the-lower-depths-1936', ('grad', [(0, (110, 110, 108)), (.6, (50, 50, 50)), (1, (12, 12, 12))]), WHT,
    L((0.0, 0.505, 0.85, 0.572), 64, WHT, mode='light'),
    photo=ph(0.5, 0.8, 1.0, 0.6), pb=WHT, order='TPCF', credit=['UN FILM DE', 'JEAN RENOIR'], ccol=WHT,
    ft='b', fcol=(210, 210, 210), fin=OLD, seed=1936)

# Charlie Chan at Monte Carlo (1937): the poster's white, its dark ink-blue CHARLIE (set on one baseline from its climb), CHAN and the small stacked at MONTE CARLO cut off it in their own colours and run in one line, Chan's face
CCMC = lambda a: (a[..., 2] > a[..., 0] + .1) & (_lum(a) < .45)
std('charlie-chan-at-monte-carlo-1937', ('grad', [(0, (246, 246, 242)), (.6, (226, 228, 228)), (1, (150, 160, 168))]), (30, 60, 90),
    LC([(0.0, 0.63, 0.6, 0.89), (0.62, 0.68, 1.0, 0.93), (0.15, 0.83, 0.65, 0.98)], 150, gapf=.12, valign='base', cuts=[
        pick_cut(CCMC, (0.0, 0.63, 0.6, 0.89), [(0.054, 0.761), (0.162, 0.777), (0.253, 0.777), (0.343, 0.749), (0.422, 0.759), (0.49, 0.738), (0.549, 0.729)], flat=True),
        pick_cut(CCMC, (0.62, 0.68, 1.0, 0.93), [(0.671, 0.805), (0.776, 0.825), (0.868, 0.817), (0.953, 0.793)], flat=True),
        pick_cut(CCMC, (0.15, 0.83, 0.65, 0.98), [(0.182, 0.919), (0.254, 0.906), (0.322, 0.89), (0.386, 0.879), (0.439, 0.862), (0.482, 0.862), (0.404, 0.945), (0.461, 0.942), (0.509, 0.927), (0.549, 0.926), (0.605, 0.91)])]),
    tgap=6, photo=ph(0.24, 0.29, 0.44, 1.15), pb=(30, 60, 90), order='LPTF', ft='a', vbox=(30, 60, 90), fcol=(30, 60, 90), fin=OLD, seed=1937)

# Charlie Chan at the Olympics (1937): the poster's blue panel, its pink lettering in navy keyline cut off it in its own colours and turned level (the panel is tipped 7-8 degrees), Chan's face
CCOL = lambda a: (a[..., 0] > .82) & (a[..., 1] > .66) & (a[..., 2] > .55) & (a[..., 0] > a[..., 2] + .05)
std('charlie-chan-at-the-olympics-1937', ('grad', [(0, (40, 110, 150)), (.6, (20, 66, 96)), (1, (6, 22, 36))]), (246, 204, 196),
    [LC([(0.22, 0.52, 0.73, 0.64), (0.22, 0.59, 0.72, 0.72)], 66, gapf=.2, outline=((20, 30, 60), 2.2), cuts=[
        pick_cut(CCOL, (0.22, 0.52, 0.73, 0.64), [(0.314, 0.56), (0.39, 0.57), (0.463, 0.582), (0.528, 0.586), (0.583, 0.598), (0.635, 0.6), (0.68, 0.604)], rot=7, r=.02),
        pick_cut(CCOL, (0.22, 0.59, 0.72, 0.72), [(0.285, 0.632), (0.406, 0.648), (0.522, 0.663), (0.642, 0.674)], rot=7, r=.02)]),
     LC([(0.13, 0.66, 0.25, 0.745), (0.24, 0.68, 0.8, 0.81)], 66, gapf=.15, outline=((20, 30, 60), 2.2), cuts=[
        pick_cut(CCOL, (0.13, 0.66, 0.25, 0.745), [(0.174, 0.685), (0.212, 0.685), (0.153, 0.713), (0.185, 0.72), (0.218, 0.724)], rot=7, r=.015),
        pick_cut(CCOL, (0.24, 0.68, 0.8, 0.81), [(0.296, 0.717), (0.356, 0.728), (0.42, 0.726), (0.504, 0.741), (0.588, 0.746), (0.637, 0.757), (0.686, 0.763), (0.761, 0.773)], rot=8, r=.02)])],
    tgap=10, photo=ph(0.7, 0.3, 0.52, 1.0), pb=(246, 204, 196), lg=(246, 204, 196), lw=.55, order='LPTF',
    ft='c', vbox=(246, 204, 196), vink=(20, 66, 96), fcol=(214, 226, 236), fin=OLD, seed=1937)

# Grand Illusion (1937): the poster's red sky into black, its cream GRAND ILLUSION rebuilt letter by letter off the arc it curves round, Gabin's face (top-billed cast from IMDb)
std('grand-illusion-1937', ('grad', [(0, (226, 70, 24)), (.35, (90, 26, 10)), (.7, (14, 6, 4)), (1, (2, 2, 2))]), (248, 238, 200),
    LC([(0.05, 0.46, 0.95, 0.94)], 60, cuts=[seq_cut(lambda a: (_lum(a) > .78) & (a[..., 2] < a[..., 0]), (0.05, 0.46, 0.95, 0.94),
        [(0.116, 0.521), (0.258, 0.524), (0.399, 0.534), (0.49, 0.555), None, (0.599, 0.585), (0.634, 0.621), (0.686, 0.652), (0.747, 0.693), (0.797, 0.741), (0.826, 0.776), (0.855, 0.824), (0.881, 0.894)])]),
    photo=ph(0.52, 0.27, 0.62, 1.15), pb=(248, 238, 200), order='PTCF', credit=['JEAN GABIN', 'PIERRE FRESNAY'], ccol=(248, 238, 200),
    dotst=('WAR', (248, 238, 200), (40, 20, 10)), ft='d', vbox=(248, 238, 200), vink=(14, 6, 4), fcol=(220, 200, 190), fin=OLD, seed=1937)

# Pépé le Moko (1937): black and the poster's yellow, the yellow PÉPÉ (accents and all) and LE MOKO keyed off it, Gabin under his hat in the yellow band (no logo file: Paris Film, from IMDb's company credits)
std('pepe-le-moko-1937', ('grad', [(0, (30, 28, 20)), (.6, (10, 10, 6)), (1, (2, 2, 2))]), (250, 226, 30),
    L([(0.245, 0.665, 0.765, 0.784), (0.08, 0.788, 0.925, 0.888)], 84, (250, 228, 30), mode='key', key=(245, 225, 40), t=(70, 150), gapf=.3, speck=0),
    photo=ph(0.6, 0.3, 0.74, 1.1), pb=(250, 228, 30), studio=['PARIS FILM'], scol=(250, 228, 30), order='lPTF',
    ft='e', vbox=(250, 228, 30), vink=(10, 10, 6), fcol=(220, 214, 180), fin=OLD, seed=1937)

# Bringing Up Baby (1938): the poster's white band, its maroon serif Bringing Up Baby lifted, Hepburn on the telephone
std('bringing-up-baby-1938', ('grad', [(0, (248, 244, 236)), (.6, (234, 226, 214)), (1, (170, 150, 130))]), (92, 26, 30),
    L((0.025, 0.415, 0.97, 0.515), 78, (92, 26, 30), mode='dark'),
    photo=ph(0.62, 0.8, 0.6, 1.08), pb=(92, 26, 30), lg=(92, 26, 30), lw=.5, order='LPTF',
    ft='b', fcol=(92, 26, 30), fin=OLD, seed=1938)

# La Bête Humaine (1938): black, the poster's red LA, BÊTE (circumflex and all) and HUMAINE keyed off it, Gabin and Simone Simon (director from IMDb, credited the French way)
std('la-bete-humaine-1938', ('grad', [(0, (40, 30, 30)), (.6, (12, 8, 8)), (1, (2, 2, 2))]), (226, 24, 36),
    L([(0.255, 0.552, 0.405, 0.622), (0.155, 0.624, 0.482, 0.766), (0.1, 0.771, 0.897, 0.935)], 92, (228, 26, 38), mode='key', key=(220, 30, 40), t=(70, 150), gapf=.18, speck=0),
    photo=ph(0.56, 0.2, 0.86, 0.72), pb=(228, 26, 38), order='PTCF', credit=['RÉALISATION', 'JEAN RENOIR'], ccol=(230, 220, 214),
    ft='a', vbox=(228, 26, 38), fcol=(200, 196, 196), fin=OLD, seed=1938)

# Port of Shadows (1938): black and fog, the poster's metallic PORT OF SHADOWS cut off it with its own white-to-grey shading, the lovers' silhouettes (no logo file: Ciné-Alliance, from IMDb's company credits)
std('port-of-shadows-1938', ('grad', [(0, (200, 200, 200)), (.25, (90, 90, 90)), (.6, (20, 20, 20)), (1, (2, 2, 2))]), WHT,
    LC([(0.05, 0.77, 0.95, 0.872), (0.05, 0.865, 0.95, 0.967)], 76, gapf=.2, margin=0, cuts=[key_cut(lambda a: _lum(a) > .5)] * 2),
    photo=ph(0.62, 0.36, 0.66, 1.55), pb=(230, 230, 230), studio=['CINÉ-ALLIANCE'], scol=(30, 30, 30), order='lPTF',
    ft='c', fcol=(200, 200, 200), fin=OLD, seed=1938)

# Snow White and the Seven Dwarfs (1938): Disney, so the white clamshell; the poster's sky blue, its cream Snow White and and the Seven Dwarfs cut off the blue oval, Snow White's face in the red diamond
disney('snow-white-and-the-seven-dwarfs-1938', ('grad', [(0, (60, 170, 214)), (.5, (30, 140, 190)), (1, (14, 90, 140))]), fin=dict(CLAM, vivid=.2),
       title=[LC([(0.17, 0.728, 0.87, 0.806)], 96, cuts=[key_cut(lambda a: (_lum(a) > .85) & (a[..., 2] < a[..., 0]))]),
              LC([(0.26, 0.8, 0.73, 0.84)], 44, cuts=[key_cut(lambda a: (_lum(a) > .85) & (a[..., 2] < a[..., 0]))])],
       face=ph(.52, .355, .16, 1.4), lcol=WHT)

# The Adventures of Robin Hood (1938): the poster's shield red, its script The Adventures of and the white ROBIN HOOD edged in blue lifted, Flynn's grin under the feathered cap
std('the-adventures-of-robin-hood-1938', ('grad', [(0, (226, 40, 44)), (.6, (160, 20, 26)), (1, (60, 6, 10))]), WHT,
    [L((0.165, 0.538, 0.705, 0.575), 40, WHT, mode='key', key=(250, 250, 250), t=(70, 160)),
     L([(0.14, 0.588, 0.705, 0.692), (0.12, 0.705, 0.668, 0.815)], 90, WHT, mode='key', key=(250, 250, 250), t=(70, 160), gapf=.25, speck=.02, outline=((30, 50, 120), 2.6))],
    tgap=6, photo=ph(0.6, 0.14, 0.6, 1.2), pb=(250, 214, 60), lw=.55, order='LPTF',
    ft='d', vbox=(250, 214, 60), vink=(160, 20, 26), fcol=(240, 220, 210), fin=OLD, seed=1938)

# The Lady Vanishes (1938): the poster's red-orange, its black script the and the tall yellow Lady Vanishes cut off it letter by letter in their own colours (the letters fade into the red at their feet, as on the poster), edged in black for the poster's shadow, the night train (no logo file: Gainsborough Pictures, from IMDb's company credits)
LVY = lambda a: (a[..., 0] > .9) & (a[..., 1] > .3) & (a[..., 2] < .3)
std('the-lady-vanishes-1938', ('grad', [(0, (222, 84, 40)), (.6, (176, 52, 30)), (1, (60, 16, 8))]), (250, 196, 60),
    LC([(0.128, 0.082, 0.3, 0.14), (0.05, 0.1, 0.47, 0.45), (0.05, 0.36, 0.92, 0.6)], 150, gapf=.12, valign='base', outline=((18, 12, 10), 1.8), cuts=[
        comp_cut(lambda a: _lum(a) < .16, keep=lambda x, y: x > .06 and .1 < y < .9),
        pick_cut(LVY, (0.05, 0.1, 0.47, 0.45), [(0.078, 0.258), (0.19, 0.292), (0.302, 0.261), (0.418, 0.305)], r=.02),
        pick_cut(LVY, (0.05, 0.36, 0.92, 0.6), [(0.074, 0.454), (0.13, 0.452), (0.234, 0.487), (0.341, 0.491), (0.438, 0.496), (0.517, 0.488), (0.623, 0.463), (0.75, 0.494), (0.856, 0.482)], r=.02)]),
    photo=ph(0.5, 0.75, 1.0, 0.45), pb=(250, 200, 60), studio=['GAINSBOROUGH', 'PICTURES'], scol=(250, 210, 140), order='lTPSF',
    stick=BAR('16 4402', top='THRILLER', fill=(226, 214, 186)), ft='b', fcol=(240, 210, 180), fin=RENTAL, seed=1938)

# Charlie Chan at Treasure Island (1939): black, the poster's sea-green lettering cut off it word by word and turned level (it climbs 10 degrees), the medium and the faces from the top of the poster (director from IMDb)
CCTI = lambda a: (a[..., 1] > .55) & (a[..., 1] > a[..., 0] + .2) & (a[..., 2] > .35)
std('charlie-chan-at-treasure-island-1939', ('grad', [(0, (30, 40, 40)), (.6, (10, 14, 14)), (1, (2, 2, 2))]), (40, 220, 170),
    [LC([(0.0, 0.5, 0.47, 0.64), (0.02, 0.6, 0.49, 0.75)], 64, gapf=.2, cuts=[
        pick_cut(CCTI, (0.0, 0.5, 0.47, 0.64), [(0.08, 0.587), (0.188, 0.579), (0.254, 0.566), (0.318, 0.563), (0.368, 0.552), (0.417, 0.546)], rot=-10, r=.02),
        pick_cut(CCTI, (0.02, 0.6, 0.49, 0.75), [(0.083, 0.691), (0.192, 0.678), (0.306, 0.67), (0.415, 0.651)], rot=-10, r=.02)]),
     LC([(0.0, 0.76, 0.15, 0.87), (0.12, 0.64, 1.0, 0.85)], 64, gapf=.15, cuts=[
        pick_cut(CCTI, (0.0, 0.76, 0.15, 0.87), [(0.052, 0.827), (0.105, 0.812)], rot=-10, r=.02),
        pick_cut(CCTI, (0.12, 0.64, 1.0, 0.85), [(0.173, 0.786), (0.239, 0.785), (0.304, 0.777), (0.367, 0.773), (0.424, 0.76), (0.489, 0.754), (0.561, 0.744), (0.619, 0.737), (0.695, 0.727), (0.742, 0.721), (0.79, 0.716), (0.85, 0.71), (0.905, 0.7), (0.965, 0.692)], rot=-10, r=.015)])],
    tgap=10, photo=ph(0.48, 0.24, 1.0, 0.75), pb=(40, 220, 170), order='PTCF', credit=['A NORMAN FOSTER', 'FILM'], ccol=(40, 220, 170),
    ft='e', fcol=(190, 210, 204), fin=OLD, seed=1939)

# Mr. Smith Goes to Washington (1939): the poster's cream, its navy italic FRANK CAPRA'S and the red condensed MR. SMITH GOES TO WASHINGTON keyed off it, Stewart and Jean Arthur from the top of the poster
std('mr-smith-goes-to-washington-1939', ('grad', [(0, (244, 232, 206)), (.6, (230, 212, 178)), (1, (160, 130, 96))]), (196, 28, 34),
    [L((0.19, 0.355, 0.8, 0.418), 36, (30, 30, 90), mode='key', key=(28, 24, 80), t=(70, 150)),
     L([(0.185, 0.458, 0.81, 0.577), (0.092, 0.591, 0.888, 0.71)], 60, (200, 30, 36), mode='key', key=(200, 40, 40), t=(70, 150), gapf=.25, speck=.03),
     L((0.033, 0.725, 0.949, 0.844), 60, (200, 30, 36), mode='key', key=(200, 40, 40), t=(70, 150), speck=.03)],
    tgap=8, photo=ph(0.55, 0.16, 0.9, 0.62), pb=(200, 30, 36), lg=(60, 40, 30), lw=.6, order='LPTF',
    ft='e', fcol=(70, 50, 40), fin=OLD, seed=1939)

# The Rules of the Game (1939): the drawing's paper white, its navy THE, RULES, OF THE and GAME lifted into one line, the hunt and the house party from the drawing (the French title in type)
std('the-rules-of-the-game-1939', ('grad', [(0, (244, 242, 232)), (.6, (226, 222, 206)), (1, (150, 146, 126))]), (24, 34, 70),
    L([(0.18, 0.268, 0.32, 0.306), (0.022, 0.302, 0.47, 0.376), (0.145, 0.378, 0.325, 0.407), (0.026, 0.41, 0.46, 0.482)], 84, (24, 34, 70), mode='dark', gapf=.2),
    photo=ph(0.66, 0.66, 0.68, 1.5), pb=(24, 34, 70), order='PTCSF', credit=['LA RÈGLE DU JEU'], ccol=(24, 34, 70), stick=RWD(),
    ft='d', fcol=(24, 34, 70), fin=OLD, seed=1939)

# The Wizard of Oz (1939): the poster's pale sky, its arched golden THE WIZARD and big OF OZ (Toto in the O) cut off it in their own colours, the four on the yellow brick road
std('the-wizard-of-oz-1939', ('grad', [(0, (226, 236, 240)), (.6, (200, 216, 224)), (1, (110, 140, 150))]), (40, 60, 150),
    LC([(0.16, 0.045, 0.71, 0.215), (0.22, 0.212, 0.8, 0.444)], 150, gapf=.1, cuts=[key_cut(lambda a: _sat(a) > .35)] * 2),
    photo=ph(0.5, 0.68, 1.0, 0.85), pb=(240, 200, 40), lg=None, lw=.55, order='LPTF', dotst=('FAMILY', (40, 120, 60), WHT),
    ft='a', vbox=(40, 60, 150), fcol=(40, 60, 150), fin=OLD, seed=1939)


# =====================================================================================
# 1940s (vault-1940s.json, 51 tapes)
# =====================================================================================

# Fantasia (1940): Disney, so the white clamshell; the poster's night sky into cloud, its tall blue FANTASIA cut off it in its own colours, Mickey the sorcerer's apprentice in the red diamond
disney('fantasia-1940', ('grad', [(0, (30, 24, 70)), (.45, (70, 70, 150)), (1, (200, 206, 236))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.2, 0.765, 0.8, 0.912)], 140, cuts=[key_cut(lambda a: (a[..., 2] > a[..., 0] + .15) & (_lum(a) < .78))]),
       face=ph(.48, .41, .2, 1.4), lcol=WHT, ink=(20, 20, 60))

# Foreign Correspondent (1940): the poster's parchment, its maroon FOREIGN CORRESPONDENT cut off it word by word and turned level (it climbs 22 degrees), Joel McCrea in his trench coat (director from IMDb)
FCM = lambda a: (a[..., 0] > a[..., 1] + .18) & (_lum(a) < .5)
std('foreign-correspondent-1940', ('grad', [(0, (236, 226, 200)), (.6, (216, 200, 166)), (1, (140, 116, 84))]), (120, 30, 34),
    LC([(0.15, 0.04, 0.68, 0.3), (0.0, 0.1, 1.0, 0.47)], 70, gapf=.18, valign='base', cuts=[
        pick_cut(FCM, (0.15, 0.04, 0.68, 0.3), [(0.184, 0.228), (0.261, 0.211), (0.349, 0.187), (0.42, 0.169), (0.473, 0.157), (0.533, 0.144), (0.622, 0.117)], rot=-22, r=.02),
        pick_cut(FCM, (0.0, 0.1, 1.0, 0.47), [(0.041, 0.405), (0.115, 0.388), (0.195, 0.364), (0.276, 0.345), (0.341, 0.329), (0.406, 0.31), (0.474, 0.285), (0.56, 0.271), (0.644, 0.249), (0.725, 0.228), (0.793, 0.21), (0.869, 0.19), (0.944, 0.165)], rot=-22, r=.02)]),
    photo=ph(0.78, 0.66, 0.42, 1.9), pb=(120, 30, 34), order='PTCF', credit=['AN ALFRED HITCHCOCK', 'FILM'], ccol=(120, 30, 34),
    ft='b', fcol=(90, 40, 34), fin=OLD, seed=1940)

# His Girl Friday (1940): the poster's white, its black HIS GIRL and red FRIDAY cut off it in their own colours, Cary Grant and Rosalind Russell
std('his-girl-friday-1940', ('grad', [(0, (248, 248, 246)), (.6, (232, 232, 228)), (1, (160, 158, 150))]), (20, 20, 20),
    LC([(0.03, 0.795, 0.965, 0.884)], 84, cuts=[key_cut(lambda a: (_lum(a) < .3) | ((a[..., 0] > .6) & (a[..., 1] < .3)))]),
    photo=ph(0.52, 0.3, 1.0, 0.7), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTSF', stick=flow(dot, 74, ['COMEDY'], (214, 30, 40), WHT),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=OLD, seed=1940)

# Pinocchio (1940): Disney, the white clamshell; the poster's starry blue, its gold script Pinocchio cut off the red plaque in its own colours, Pinocchio's face in the red diamond
disney('pinocchio-1940', ('grad', [(0, (20, 40, 120)), (.5, (40, 90, 180)), (1, (120, 170, 220))]), fin=dict(CLAM, vivid=.22),
       title=LC([(0.345, 0.435, 0.93, 0.53)], 120, outline=((150, 20, 30), 3), cuts=[key_cut(lambda a: (a[..., 0] > .8) & (a[..., 1] > .6) & (a[..., 2] < .45))]),
       face=ph(.25, .335, .22, 1.4), lcol=WHT)

# Rebecca (1940): black, the poster's green script Rebecca keyed off it, Olivier and Joan Fontaine with Manderley behind
std('rebecca-1940', ('grad', [(0, (40, 30, 26)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (110, 200, 120),
    L((0.105, 0.712, 0.888, 0.888), 100, (112, 204, 124), mode='key', key=(100, 190, 110), t=(70, 150)),
    photo=ph(0.45, 0.3, 1.0, 0.75), pb=(112, 204, 124), order='PTF', ft='c', fcol=(200, 200, 196), fin=OLD, seed=1940)

# The Bank Dick (1940): the poster's yellow sun, its black THE, Bank and Dick lifted word by word and turned level (they climb 17 degrees), W.C. Fields from the cartoon at the top
BDK = lambda a: _lum(a) < .25
std('the-bank-dick-1940', ('grad', [(0, (250, 226, 60)), (.6, (240, 200, 30)), (1, (170, 120, 10))]), (20, 20, 20),
    LC([(0.39, 0.61, 0.56, 0.68), (0.15, 0.66, 0.56, 0.84), (0.52, 0.59, 0.89, 0.76)], 96, gapf=.14, valign='base', cuts=[
        pick_cut(BDK, (0.39, 0.61, 0.56, 0.68), [(0.427, 0.653), (0.472, 0.646), (0.518, 0.638)], rot=-17, r=.015),
        pick_cut(BDK, (0.15, 0.66, 0.56, 0.84), [(0.23, 0.772), (0.321, 0.77), (0.401, 0.751), (0.478, 0.728)], rot=-17, r=.02),
        pick_cut(BDK, (0.52, 0.59, 0.89, 0.76), [(0.596, 0.696), (0.654, 0.65), (0.677, 0.697), (0.739, 0.682), (0.81, 0.657)], rot=-17, r=.02)]),
    photo=ph(0.52, 0.17, 0.62, 1.2), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCF', credit=['W.C. FIELDS'], ccol=(20, 20, 20),
    ft='d', fcol=(20, 20, 20), fin=OLD, seed=1940)

# The Philadelphia Story (1940): the poster's red, its yellow script The, Philadelphia and Story cut off it word by word and turned level, edged in the poster's dark outline, the three stars kissing
PSY = lambda a: (a[..., 0] > .85) & (a[..., 1] > .7) & (a[..., 2] < .45)
std('the-philadelphia-story-1940', ('grad', [(0, (210, 50, 40)), (.6, (150, 30, 24)), (1, (60, 10, 8))]), (250, 220, 60),
    LC([(0.2, 0.02, 0.47, 0.14), (0.1, 0.0, 0.85, 0.235), (0.45, 0.08, 0.76, 0.24)], 96, gapf=.12, valign='base', outline=((50, 14, 12), 2.2), cuts=[
        pick_cut(PSY, (0.2, 0.02, 0.47, 0.14), [(0.281, 0.079), (0.37, 0.079)], rot=-10, r=.02),
        pick_cut(PSY, (0.1, 0.0, 0.85, 0.235), [(0.189, 0.175), (0.361, 0.149), (0.518, 0.108), (0.587, 0.09), (0.656, 0.066), (0.687, 0.066), (0.725, 0.061), (0.757, 0.043), (0.794, 0.042)], rot=-18, r=.012, split=9),
        pick_cut(PSY, (0.45, 0.08, 0.76, 0.24), [(0.504, 0.181), (0.603, 0.155), (0.7, 0.13), (0.731, 0.132)], rot=-18, r=.015, split=9)]),
    photo=ph(0.5, 0.42, 1.0, 0.55), pb=(250, 220, 60), lg=None, lw=.5, order='LPTF', ft='e', vbox=(250, 220, 60), vink=(150, 30, 24),
    fcol=(240, 214, 200), fin=OLD, seed=1940)

# The Thief of Bagdad (1940): the poster's parchment, its blue-grey script The and of and the maroon circus capitals THIEF and BAGDAD cut off it in their own colours, the flying horseman
TBM = lambda a: (a[..., 0] > a[..., 1] + .2) & (_lum(a) < .45)
TBB = lambda a: (_lum(a) < .5) & (a[..., 2] > a[..., 0] - .02) & (_sat(a) < .25)
std('the-thief-of-bagdad-1940', ('grad', [(0, (244, 236, 222)), (.6, (226, 212, 192)), (1, (150, 130, 104))]), (130, 20, 26),
    [LC([(0.035, 0.125, 0.135, 0.185), (0.035, 0.185, 0.56, 0.312)], 72, gapf=.15, valign='base', cuts=[comp_cut(TBB), comp_cut(TBM)]),
     LC([(0.55, 0.235, 0.665, 0.305), (0.27, 0.315, 0.97, 0.435)], 72, gapf=.15, valign='base', cuts=[comp_cut(TBB), comp_cut(TBM, keep=lambda x, y: x > .03)])],
    tgap=10, photo=ph(0.77, 0.115, 0.42, 0.85), pb=(130, 20, 26), order='PTSF', stick=PRC(['$1.99', 'ADVENTURE']),
    ft='c', fcol=(110, 40, 40), fin=RENTAL, seed=1940)

# Citizen Kane (1941): the poster's cream, its red-and-gold extruded CITIZEN KANE cut off it in its own colours and turned level (it climbs 31 degrees), Kane's face from the top of the poster
CKR = lambda a: (_sat(a) > .4) & (_lum(a) > .2)
std('citizen-kane-1941', ('grad', [(0, (246, 238, 220)), (.6, (230, 214, 186)), (1, (150, 120, 90))]), (190, 30, 30),
    LC([(0.35, 0.36, 0.99, 0.66), (0.48, 0.49, 0.96, 0.74)], 104, gapf=.15, valign='base', margin=0, cuts=[
        pick_cut(CKR, (0.35, 0.36, 0.99, 0.66), [(0.668, 0.501)], rot=-31, r=.03, margin=0),
        pick_cut(CKR, (0.48, 0.49, 0.96, 0.74), [(0.723, 0.612)], rot=-31, r=.03, margin=0)]),
    photo=ph(0.76, 0.17, 0.46, 1.2), pb=(190, 30, 30), lg=(30, 26, 24), lw=.5, order='LPTCF', credit=['AN ORSON WELLES', 'PRODUCTION'],
    ccol=(30, 26, 24), ft='b', fcol=(60, 40, 30), fin=OLD, seed=1941)

# Dumbo (1941): Disney, the white clamshell; the poster's circus yellow, its red dotted D U M B O rebuilt letter by letter off the diagonal they tumble down, each set upright, Dumbo's face in the red diamond
disney('dumbo-1941', ('grad', [(0, (250, 236, 120)), (.5, (240, 220, 70)), (1, (210, 180, 40))]), fin=dict(CLAM, vivid=.2), ink=(120, 20, 20),
       title=LC([(0.04, 0.24, 0.93, 0.73)], 120, outline=((60, 10, 10), 2.2), cuts=[seq_cut(lambda a: (a[..., 0] > .75) & (a[..., 1] < .3) & (a[..., 2] < .3), (0.04, 0.24, 0.93, 0.73),
           [(0.157, 0.309), (0.276, 0.413), (0.502, 0.447), (0.703, 0.531), (0.806, 0.665)], turn=[0, 8, 14, 22, 4], gapf=.18, holes=.06)]),
       face=ph(.34, .74, .2, 1.4), lcol=(120, 20, 20))

# Mr. & Mrs. Smith (1941): black, the poster's orange-red sign with its black Mr. & Mrs. Smith cut off it whole and turned level (it hangs at 10 degrees), Carole Lombard
std('mr-mrs-smith-1941', ('grad', [(0, (40, 30, 30)), (.6, (12, 10, 10)), (1, (2, 2, 2))]), (226, 92, 64),
    LC([(0.43, 0.0, 0.94, 0.2)], 150, margin=0, cuts=[plate_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .25) & (a[..., 1] < .55) & (a[..., 2] < .45), rot=-10)]),
    photo=ph(0.36, 0.5, 0.7, 1.2), pb=(226, 92, 64), lg=(226, 92, 64), lw=.5, order='LPTF',
    ft='c', vbox=(226, 92, 64), vink=(12, 10, 10), fcol=(210, 200, 196), fin=OLD, seed=1941)

# Sullivan's Travels (1941): the poster's black, its tan SULLIVAN'S and TRAVELS in their black keyline cut off it in their own colours and turned level, Joel McCrea and Veronica Lake (Paramount's mountain at the head)
SVT = lambda a: (a[..., 0] > .6) & (a[..., 1] > .5) & (a[..., 2] < .45) & (a[..., 0] > a[..., 2] + .15)
std('sullivan-s-travels-1941', ('grad', [(0, (40, 34, 26)), (.6, (14, 12, 8)), (1, (2, 2, 2))]), (226, 196, 120),
    [LC([(0.12, 0.04, 0.86, 0.25)], 70, outline=((14, 12, 8), 2), cuts=[pick_cut(SVT, (0.12, 0.04, 0.86, 0.25), [(0.212, 0.145), (0.327, 0.159), (0.402, 0.152), (0.458, 0.148), (0.514, 0.138), (0.576, 0.129), (0.65, 0.128), (0.727, 0.115), (0.81, 0.107)], rot=-6, r=.02)]),
     LC([(0.23, 0.16, 0.82, 0.31)], 70, outline=((14, 12, 8), 2), cuts=[pick_cut(SVT, (0.23, 0.16, 0.82, 0.31), [(0.271, 0.25), (0.354, 0.253), (0.453, 0.247), (0.538, 0.231), (0.617, 0.226), (0.691, 0.222), (0.768, 0.208)], rot=-6, r=.02)])],
    tgap=8, photo=ph(0.5, 0.48, 1.0, 0.6), pb=(226, 196, 120), lg=WHT, lw=.5, order='LTPCF', credit=['WRITTEN & DIRECTED BY', 'PRESTON STURGES'],
    ccol=(226, 196, 120), ft='a', vbox=(226, 196, 120), vink=(14, 12, 8), fcol=(200, 196, 186), fin=OLD, seed=1941)

# Suspicion (1941): the poster's white, its red brush Suspicion keyed off it, Cary Grant and Joan Fontaine in the blue
std('suspicion-1941', ('grad', [(0, (244, 244, 242)), (.6, (226, 228, 228)), (1, (150, 160, 166))]), (190, 20, 34),
    L((0.02, 0.698, 0.975, 0.856), 96, (194, 22, 36), mode='key', key=(180, 25, 40), t=(70, 150)),
    photo=ph(0.4, 0.22, 0.8, 0.85), pb=(30, 90, 110), lg=(30, 30, 30), lw=.5, order='LPTF', ft='c', fcol=(40, 40, 44), fin=OLD, seed=1941)

# The Lady Eve (1941): the poster's apple red, its yellow THE Lady and Eve in their black keyline cut off it in their own colours, Stanwyck and Fonda in the apple
LEY = lambda a: (a[..., 0] > .85) & (a[..., 1] > .75) & (a[..., 2] < .5)
std('the-lady-eve-1941', ('grad', [(0, (236, 80, 60)), (.6, (190, 40, 34)), (1, (80, 14, 12))]), (252, 226, 70),
    LC([(0.45, 0.35, 0.94, 0.66), (0.53, 0.59, 0.86, 0.76)], 150, gapf=.16, valign='base', outline=((24, 18, 14), 2.4), cuts=[
        pick_cut(LEY, (0.45, 0.35, 0.94, 0.66), [(0.58, 0.47), (0.766, 0.559)], r=.03), pick_cut(LEY, (0.53, 0.59, 0.86, 0.76), [(0.68, 0.691)], r=.03)]),
    photo=ph(0.34, 0.19, 0.6, 0.8), pb=(252, 226, 70), lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(252, 236, 120)),
    ft='e', vbox=(252, 226, 70), vink=(190, 40, 34), fcol=(250, 220, 200), fin=OLD, seed=1941)

# The Maltese Falcon (1941): the poster's white with its blue scribble, its red THE, Maltese and Falcon cut off it in their own colours and turned level (they climb 14 degrees), Bogart with the gun
MFR = lambda a: (a[..., 0] > .6) & (a[..., 1] < .3) & (a[..., 2] < .3)
std('the-maltese-falcon-1941', ('grad', [(0, (244, 246, 248)), (.6, (210, 220, 232)), (1, (70, 100, 150))]), (220, 40, 40),
    LC([(0.6, 0.58, 0.74, 0.64), (0.33, 0.58, 0.9, 0.79), (0.43, 0.7, 0.95, 0.87)], 100, gapf=.14, valign='base', cuts=[
        pick_cut(MFR, (0.6, 0.58, 0.74, 0.64), [(0.64, 0.611), (0.676, 0.609), (0.708, 0.603)], rot=-14, r=.015),
        pick_cut(MFR, (0.33, 0.58, 0.9, 0.79), [(0.404, 0.721), (0.529, 0.699), (0.619, 0.679), (0.723, 0.669), (0.835, 0.648)], rot=-14, r=.02),
        pick_cut(MFR, (0.43, 0.7, 0.95, 0.87), [(0.501, 0.795), (0.622, 0.789), (0.807, 0.76)], rot=-14, r=.02)]),
    photo=ph(0.6, 0.15, 0.7, 0.95), pb=(30, 60, 130), lg=(30, 60, 130), lw=.55, order='LPTCF', credit=['HUMPHREY BOGART'], ccol=(30, 60, 130),
    ft='b', fcol=(30, 60, 130), fin=OLD, seed=1941)

# Bambi (1942): Disney, the white clamshell; the poster's forest russet, its peach serif Bambi (set reading down the poster) cut off it in its own colours, Bambi's face in the red diamond
disney('bambi-1942', ('grad', [(0, (120, 50, 30)), (.5, (180, 90, 40)), (1, (60, 90, 50))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.105, 0.225, 0.305, 0.705)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .6) & (a[..., 2] > .4) & (a[..., 2] < .7), rot=90)]),
       face=ph(.53, .4, .4, 1.4), lcol=WHT)

# Cat People (1942): black, the poster's teal shaggy CAT PEOPLE rebuilt letter by letter off the curve it climbs, edged in black, Simone Simon in red
std('cat-people-1942', ('grad', [(0, (30, 50, 56)), (.6, (10, 18, 20)), (1, (2, 4, 4))]), (90, 200, 214),
    LC([(0.03, 0.12, 0.97, 0.37)], 100, outline=((8, 14, 16), 2), cuts=[seq_cut(lambda a: (a[..., 1] > .4) & (a[..., 2] > .4) & (a[..., 0] < .6), (0.03, 0.12, 0.97, 0.37),
        [(0.107, 0.325), (0.206, 0.278), (0.291, 0.235), None, (0.416, 0.197), (0.522, 0.204), (0.627, 0.19), (0.731, 0.177), (0.823, 0.187), (0.908, 0.184)], gapf=.08)]),
    photo=ph(0.47, 0.465, 0.4, 1.0), pb=(214, 40, 50), lg=(90, 200, 214), lw=.5, order='LPTSF', stick=flow(dot, 74, ['HORROR'], (214, 40, 50), WHT),
    ft='d', vbox=(90, 200, 214), vink=(10, 18, 20), fcol=(190, 210, 214), fin=RENTAL, seed=1942)

# Saboteur (1942): the poster's white, its orange-red brush Saboteur keyed off it, the burning factory and the running man under the title
std('saboteur-1942', ('grad', [(0, (244, 244, 240)), (.6, (222, 224, 222)), (1, (120, 126, 128))]), (226, 70, 30),
    L((0.055, 0.436, 0.93, 0.622), 100, (230, 74, 32), mode='key', key=(225, 70, 30), t=(70, 150)),
    photo=ph(0.6, 0.78, 0.66, 0.85), pb=(30, 30, 30), lg=(30, 30, 30), lw=.6, order='LTPF', ft='a', vbox=(230, 74, 32), fcol=(30, 30, 30), fin=OLD, seed=1942)

# Casablanca (1943): black, the poster's tall serif CASABLANCA cut off it in its own white-to-blue shading, Bogart and Bergman
std('casablanca-1943', ('grad', [(0, (30, 34, 40)), (.6, (10, 10, 12)), (1, (2, 2, 2))]), (190, 214, 236),
    LC([(0.13, 0.11, 0.87, 0.325)], 120, cuts=[key_cut(lambda a: _lum(a) > .55)]),
    photo=ph(0.5, 0.74, 1.0, 0.62), pb=(220, 228, 236), lg=WHT, lw=.55, order='LPTCF', credit=['HUMPHREY BOGART', 'INGRID BERGMAN'],
    ccol=(200, 214, 230), ft='c', fcol=(190, 196, 206), fin=OLD, seed=1943)

# Le Corbeau (1943): the poster's white, its ragged black brush Le Corbeau lifted (the crow's tail runs down into the b, as on the poster), the crow's black shape from the top of the poster (director from IMDb)
std('le-corbeau-1943', ('grad', [(0, (246, 246, 244)), (.6, (228, 228, 224)), (1, (150, 150, 146))]), (20, 20, 20),
    L((0.05, 0.6, 0.962, 0.782), 100, (20, 20, 20), mode='dark'),
    photo=ph(0.42, 0.25, 0.8, 0.85), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['UN FILM DE', 'H.-G. CLOUZOT'], ccol=(20, 20, 20),
    ft='e', fcol=(20, 20, 20), fin=OLD, seed=1943)

# Shadow of a Doubt (1943): the poster's white, its orange-red SHADOW of a DOUBT with the black extrusion cut off it in their own colours, Teresa Wright and Joseph Cotten
std('shadow-of-a-doubt-1943', ('grad', [(0, (246, 242, 236)), (.6, (230, 222, 212)), (1, (150, 130, 116))]), (230, 80, 34),
    LC([(0.0, 0.47, 1.0, 0.618)], 96, cuts=[comp_cut(lambda a: ((a[..., 0] > .75) & (a[..., 1] < .45) & (a[..., 2] < .3)) | (_lum(a) < .18))]),
    photo=ph(0.4, 0.2, 0.8, 0.72), pb=(230, 80, 34), lg=(30, 30, 30), lw=.6, order='LPTSF', stick=BAR('23 1150', top='SUSPENSE', fill=(236, 226, 200)),
    ft='b', fcol=(40, 34, 30), fin=RENTAL, seed=1943)

# Double Indemnity (1944): black, the poster's white DOUBLE INDEMNITY with its grey extrusion cut off it in its own colours, Barbara Stanwyck with the cigarette (director from IMDb)
std('double-indemnity-1944', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    [LC([(0.04, 0.178, 0.965, 0.32)], 80, cuts=[key_cut(lambda a: _lum(a) > .5)]), LC([(0.04, 0.355, 0.915, 0.5)], 80, cuts=[key_cut(lambda a: _lum(a) > .5)])],
    tgap=10, photo=ph(0.6, 0.745, 0.6, 1.15), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['DIRECTED BY', 'BILLY WILDER'],
    ccol=WHT, ft='d', fcol=(200, 200, 200), fin=OLD, seed=1944)

# Gaslight (1944): the poster's sepia brown, its yellow Gaslight keyed off it, Boyer and Bergman under the lamp
std('gaslight-1944', ('grad', [(0, (110, 80, 50)), (.6, (54, 36, 22)), (1, (14, 8, 4))]), (250, 214, 40),
    L((0.115, 0.75, 0.89, 0.925), 100, (252, 216, 40), mode='key', key=(245, 210, 40), t=(70, 150)),
    photo=ph(0.56, 0.36, 0.8, 0.9), pb=(252, 216, 40), lg=(252, 216, 40), lw=.55, order='LTPSF', stick=PRC(['$2.49', 'THRILLER']), ft='a', vbox=(252, 216, 40), vink=(54, 36, 22),
    fcol=(220, 200, 170), fin=OLD, seed=1944)

# Ivan the Terrible, Part I (1944): the poster's sepia, its red Slavonic IVAN the TERRIBLE and PART I keyed off it, the tsar in his robes
std('ivan-the-terrible-part-i-1944', ('grad', [(0, (226, 200, 170)), (.6, (190, 160, 126)), (1, (100, 76, 56))]), (190, 30, 30),
    L([(0.03, 0.038, 0.97, 0.153), (0.38, 0.165, 0.62, 0.2)], 76, (194, 32, 32), mode='key', key=(190, 40, 40), t=(70, 150), gapf=.25),
    photo=ph(0.5, 0.6, 0.6, 1.8), pb=(194, 32, 32), lg=(80, 40, 30), lw=.5, order='LPTCF', credit=['SERGEI EISENSTEIN'], ccol=(80, 40, 30),
    ft='c', fcol=(80, 50, 40), fin=OLD, seed=1944)

# Laura (1944): the poster's white, its red swash script Laura keyed off it, Gene Tierney and Dana Andrews
std('laura-1944', ('grad', [(0, (246, 244, 238)), (.6, (226, 222, 214)), (1, (140, 150, 140))]), (214, 36, 40),
    L((0.0, 0.47, 0.84, 0.832), 165, (216, 38, 42), mode='key', key=(210, 40, 40), t=(70, 150), speck=.04),
    photo=ph(0.4, 0.2, 0.8, 0.75), pb=(30, 120, 110), lg=(30, 30, 30), lw=.55, order='LPTF', ft='e', vbox=(216, 38, 42),
    fcol=(40, 40, 40), fin=OLD, seed=1944)

# And Then There Were None (1945): the poster's yellow panel, its red AND THEN THERE / WERE NONE cut off it word by word and turned level (it is set at 10 degrees), the ten guests' faces (20th Century-Fox in type)
ATR = lambda a: (a[..., 0] > .6) & (a[..., 1] < .45) & (a[..., 2] < .3)
std('and-then-there-were-none-1945', ('grad', [(0, (250, 220, 70)), (.6, (240, 196, 40)), (1, (170, 120, 20))]), (210, 50, 30),
    [LC([(0.0, 0.1, 0.36, 0.22), (0.0, 0.2, 0.39, 0.34), (0.0, 0.3, 0.45, 0.45)], 64, gapf=.2, valign='base', cuts=[
        pick_cut(ATR, (0.0, 0.1, 0.36, 0.22), [(0.063, 0.178), (0.164, 0.16), (0.275, 0.148)], rot=-10, r=.02),
        pick_cut(ATR, (0.0, 0.2, 0.39, 0.34), [(0.041, 0.276), (0.128, 0.278), (0.215, 0.265), (0.313, 0.254)], rot=-10, r=.02),
        pick_cut(ATR, (0.0, 0.3, 0.45, 0.45), [(0.034, 0.388), (0.112, 0.385), (0.204, 0.375), (0.298, 0.358), (0.383, 0.354)], rot=-10, r=.02)]),
     LC([(0.0, 0.41, 0.45, 0.54), (0.0, 0.52, 0.46, 0.67)], 64, gapf=.2, valign='base', cuts=[
        pick_cut(ATR, (0.0, 0.41, 0.45, 0.54), [(0.082, 0.496), (0.177, 0.491), (0.272, 0.471), (0.377, 0.465)], rot=-10, r=.02),
        pick_cut(ATR, (0.0, 0.52, 0.46, 0.67), [(0.072, 0.607), (0.188, 0.592), (0.306, 0.58), (0.395, 0.571)], rot=-10, r=.02)])],
    tgap=10, photo=ph(0.75, 0.24, 0.5, 1.2), pb=(30, 30, 30), studio=['20TH CENTURY-FOX'], scol=(60, 30, 20), order='lPTCF',
    credit=['DIRECTED BY', 'RENÉ CLAIR'], ccol=(60, 30, 20), ft='b', fcol=(60, 30, 20), fin=OLD, seed=1945)

# Brief Encounter (1945): the poster's yellow and night blue, its red brush Brief and encounter cut off it in their own colours and turned level (they climb 19 degrees), Celia Johnson and Trevor Howard (no logo file: Cineguild, from IMDb's company credits)
BER = lambda a: (a[..., 0] > .6) & (a[..., 1] < .35) & (a[..., 2] < .3)
std('brief-encounter-1945', ('grad', [(0, (30, 50, 90)), (.5, (20, 30, 56)), (1, (6, 8, 16))]), (226, 50, 40),
    LC([(0.09, 0.47, 0.62, 0.79), (0.09, 0.68, 0.97, 0.96)], 130, gapf=.18, valign='base', cuts=[
        pick_cut(BER, (0.09, 0.47, 0.62, 0.79), [(0.184, 0.676), (0.313, 0.698), (0.353, 0.628), (0.388, 0.691), (0.462, 0.675), (0.54, 0.6)], rot=-14, r=.02),
        pick_cut(BER, (0.09, 0.68, 0.97, 0.96), [(0.14, 0.911), (0.245, 0.885), (0.346, 0.863), (0.455, 0.842), (0.563, 0.822), (0.658, 0.794), (0.713, 0.737), (0.816, 0.762), (0.911, 0.732)], rot=-19, r=.02)]),
    photo=ph(0.55, 0.22, 0.86, 0.85), pb=(250, 214, 60), studio=['CINEGUILD'], scol=(250, 214, 60), order='lPTF',
    ft='c', vbox=(250, 214, 60), vink=(20, 30, 56), fcol=(200, 206, 220), fin=OLD, seed=1945)

# Spellbound (1945): the poster's snow white, its black script Spellbound lifted, Gregory Peck's face upside down from the top of the poster (no logo file: Selznick International, from IMDb's company credits)
std('spellbound-1945', ('grad', [(0, (246, 248, 250)), (.6, (222, 230, 238)), (1, (140, 160, 180))]), (24, 24, 30),
    L((0.14, 0.61, 0.94, 0.812), 104, (24, 24, 30), mode='dark'),
    photo=ph(0.74, 0.18, 0.5, 1.0), pb=(24, 24, 30), studio=['SELZNICK', 'INTERNATIONAL'], scol=(24, 24, 30), order='PTlF',
    ft='d', fcol=(24, 24, 30), fin=OLD, seed=1945)

# The Lost Weekend (1945): the poster's paper white, its red THE LOST / WEEK-END cut off it word by word and turned level (it leans 14 degrees), Ray Milland's face
LWR = lambda a: (a[..., 0] > .55) & (a[..., 1] < .4) & (a[..., 2] < .35)
std('the-lost-weekend-1945', ('grad', [(0, (238, 240, 240)), (.6, (210, 220, 226)), (1, (100, 120, 140))]), (226, 50, 40),
    [LC([(0.08, 0.1, 0.36, 0.22), (0.08, 0.19, 0.41, 0.33)], 76, gapf=.2, valign='base', cuts=[
        pick_cut(LWR, (0.08, 0.1, 0.36, 0.22), [(0.145, 0.179), (0.223, 0.168), (0.291, 0.154)], rot=-14, r=.02),
        pick_cut(LWR, (0.08, 0.19, 0.41, 0.33), [(0.136, 0.295), (0.212, 0.273), (0.295, 0.255), (0.361, 0.233)], rot=-14, r=.02)]),
     LC([(0.08, 0.27, 0.5, 0.43), (0.15, 0.37, 0.5, 0.53)], 76, gapf=.12, valign='base', cuts=[
        pick_cut(LWR, (0.08, 0.27, 0.5, 0.43), [(0.162, 0.38), (0.246, 0.361), (0.324, 0.346), (0.407, 0.336), (0.455, 0.31)], rot=-14, r=.02),
        pick_cut(LWR, (0.15, 0.37, 0.5, 0.53), [(0.233, 0.47), (0.311, 0.459), (0.377, 0.444), (0.417, 0.437)], rot=-14, r=.02)])],
    tgap=10, photo=ph(0.73, 0.42, 0.5, 1.0), pb=(226, 50, 40), lg=(30, 40, 50), lw=.5, order='LPTCF', credit=['RAY MILLAND', 'JANE WYMAN'],
    ccol=(30, 40, 50), ft='a', vbox=(226, 50, 40), fcol=(30, 40, 50), fin=OLD, seed=1945)

# To Have and Have Not (1945): the poster's cream, its black serif TO HAVE AND HAVE NOT lifted with its red drop shadow put back, Bogart and Bacall
std('to-have-and-have-not-1945', ('grad', [(0, (246, 238, 222)), (.6, (232, 218, 196)), (1, (170, 140, 110))]), (24, 20, 18),
    L((0.06, 0.758, 0.92, 0.806), 58, (24, 20, 18), mode='dark', shadow=((210, 60, 40), 3, 2.5)),
    photo=ph(0.5, 0.39, 0.58, 0.85), pb=(204, 42, 36), lg=None, lw=.55, order='LPTCSF', credit=['HUMPHREY BOGART'], ccol=(80, 40, 30),
    stick=flow(dot, 74, ['WAR'], (40, 80, 140), WHT), ft='c', fcol=(80, 50, 40), fin=OLD, seed=1945)

# Beauty and the Beast (1946): the photograph's greys, its white hairline script Beauty and the Beast lifted, Belle in her gown in the corridor (director from IMDb)
std('beauty-and-the-beast-1946', ('grad', [(0, (150, 152, 150)), (.6, (70, 72, 72)), (1, (12, 12, 12))]), WHT,
    L((0.55, 0.53, 0.985, 0.61), 70, WHT, mode='light', speck=0),
    photo=ph(0.38, 0.62, 0.62, 1.7), pb=WHT, order='TPCF', credit=['UN FILM DE', 'JEAN COCTEAU'], ccol=WHT,
    ft='b', fcol=(220, 220, 220), fin=OLD, seed=1946)

# Gilda (1946): black, the poster's red script Gilda keyed off it, Rita Hayworth in the strapless gown (tall picture)
std('gilda-1946', ('grad', [(0, (24, 30, 50)), (.6, (8, 10, 16)), (1, (2, 2, 4))]), (220, 40, 50),
    L((0.5, 0.57, 0.87, 0.68), 120, (222, 42, 52), mode='key', key=(210, 45, 55), t=(70, 150)),
    photo=ph(0.26, 0.5, 0.4, 1.95), pb=(222, 42, 52), lg=WHT, lw=.6, order='LPTF', ft='a', vbox=(222, 42, 52), fcol=(200, 200, 210), fin=OLD, seed=1946)

# Green for Danger (1946): the poster's cream, its green serif GREEN, FOR and DANGER cut off it in their own colours and turned level, Alastair Sim (no logo file: Individual Pictures, from IMDb's company credits)
GFG = lambda a: (a[..., 1] > a[..., 0] + .1) & (a[..., 1] > a[..., 2]) & (_lum(a) < .5)
std('green-for-danger-1946', ('grad', [(0, (244, 238, 222)), (.6, (226, 216, 192)), (1, (150, 130, 100))]), (30, 120, 70),
    LC([(0.42, 0.52, 0.84, 0.64), (0.53, 0.62, 0.83, 0.72), (0.43, 0.69, 0.97, 0.83)], 84, gapf=.18, valign='base', cuts=[
        pick_cut(GFG, (0.42, 0.52, 0.84, 0.64), [(0.474, 0.598), (0.557, 0.587), (0.632, 0.579), (0.703, 0.571), (0.776, 0.561)], rot=-5, r=.02),
        pick_cut(GFG, (0.53, 0.62, 0.83, 0.72), [(0.591, 0.671), (0.673, 0.668), (0.758, 0.659)], rot=-5, r=.02),
        pick_cut(GFG, (0.43, 0.69, 0.97, 0.83), [(0.499, 0.78), (0.582, 0.773), (0.654, 0.762), (0.74, 0.756), (0.82, 0.745), (0.902, 0.737)], rot=-5, r=.02)]),
    photo=ph(0.4, 0.2, 0.7, 0.9), pb=(30, 120, 70), studio=['INDIVIDUAL PICTURES'], scol=(30, 120, 70), order='lPTSF', stick=PRC(['$1.49', 'MYSTERY']),
    ft='e', vbox=(30, 120, 70), fcol=(40, 60, 44), fin=RENTAL, seed=1946)

# It's a Wonderful Life (1946): the poster's white, its red IT'S A WONDERFUL LIFE cut off it in its own colours and turned level (it climbs 20 degrees), George and Mary (no logo file: Liberty Films, from IMDb's company credits)
IWR = lambda a: (a[..., 0] > .6) & (a[..., 1] < .3) & (a[..., 2] < .3)
std('it-s-a-wonderful-life-1946', ('grad', [(0, (246, 246, 244)), (.6, (226, 228, 228)), (1, (140, 150, 160))]), (200, 30, 40),
    LC([(0.02, 0.55, 0.98, 0.88)], 64, cuts=[pick_cut(IWR, (0.02, 0.55, 0.98, 0.88), [(0.052, 0.825), (0.095, 0.818), (0.155, 0.815), (0.234, 0.804), (0.314, 0.782), (0.387, 0.77), (0.441, 0.751), (0.495, 0.735), (0.54, 0.715), (0.602, 0.696), (0.642, 0.676), (0.686, 0.661), (0.738, 0.645), (0.802, 0.625), (0.849, 0.616), (0.88, 0.604), (0.932, 0.613)], rot=-20, r=.015)]),
    photo=ph(0.55, 0.3, 0.86, 1.05), pb=(30, 60, 110), studio=['LIBERTY FILMS'], scol=(30, 60, 110), order='lPTCF',
    credit=['JAMES STEWART', 'DONNA REED'], ccol=(30, 60, 110), dotst=(['HOLIDAY', 'CLASSIC'], (200, 30, 40), WHT),
    ft='d', fcol=(30, 60, 110), fin=OLD, seed=1946)

# Notorious (1946): the poster's white, its yellow script Notorious in black keyline cut off it in its own colours, Grant and Bergman's kiss
std('notorious-1946', ('grad', [(0, (244, 244, 240)), (.6, (222, 226, 226)), (1, (120, 140, 150))]), (30, 30, 30),
    LC([(0.21, 0.745, 0.865, 0.84)], 100, cuts=[comp_cut(lambda a: ((a[..., 0] > .85) & (a[..., 1] > .8) & (a[..., 2] < .5)) | (_lum(a) < .2))]),
    photo=ph(0.45, 0.28, 0.9, 0.8), pb=(30, 90, 130), lg=(30, 30, 30), lw=.5, order='LPTF', ft='b', fcol=(30, 30, 30), fin=OLD, seed=1946)

# The Big Sleep (1946): black, the poster's white serif "THE BIG SLEEP" (quotes and all) lifted, Bogart and Bacall
std('the-big-sleep-1946', ('grad', [(0, (40, 34, 28)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), WHT,
    L((0.045, 0.028, 0.955, 0.124), 76, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.6, 1.0, 0.9), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(200, 196, 190), fin=OLD, seed=1946)

# The Killers (1946): black, the poster's white outlined THE Killers cut off it and turned level (it climbs 9 degrees), Burt Lancaster and Ava Gardner
std('the-killers-1946', ('grad', [(0, (34, 40, 46)), (.6, (12, 14, 16)), (1, (2, 2, 2))]), WHT,
    LC([(0.19, 0.09, 0.85, 0.26)], 120, cuts=[comp_cut(lambda a: _lum(a) > .75, rot=-9)]),
    photo=ph(0.5, 0.42, 1.0, 0.68), pb=WHT, lg=WHT, lw=.6, order='LPTF', dotst=('CRIME', (200, 30, 40), WHT), ft='a', fcol=(200, 204, 210), fin=OLD, seed=1946)

# Brute Force (1947): the poster's white, its black distressed BRUTE FORCE keyed off it (the scratches filled), Burt Lancaster behind the bars
std('brute-force-1947', ('grad', [(0, (236, 236, 234)), (.6, (210, 210, 206)), (1, (110, 110, 106))]), (20, 20, 20),
    L([(0.03, 0.632, 0.99, 0.773), (0.03, 0.773, 0.99, 0.92)], 84, (20, 20, 20), mode='key', key=(10, 8, 8), t=(60, 140), close=2, gapf=.25),
    photo=ph(0.55, 0.28, 1.0, 0.8), pb=(20, 20, 20), lg=(20, 20, 20), lw=.6, order='LPTCSF', credit=['DIRECTED BY', 'JULES DASSIN'], ccol=(20, 20, 20),
    stick=RWD(fill=(240, 236, 210)), ft='e', fcol=(20, 20, 20), fin=RENTAL, seed=1947)

# Dark Passage (1947): the poster's cream, its red serif italic DARK PASSAGE keyed off it, Bogart and Bacall in the dark blue brush stroke
std('dark-passage-1947', ('grad', [(0, (244, 238, 222)), (.6, (228, 218, 196)), (1, (150, 130, 104))]), (210, 30, 40),
    L([(0.52, 0.686, 0.905, 0.78), (0.395, 0.778, 0.95, 0.876)], 76, (212, 32, 42), mode='key', key=(205, 35, 45), t=(70, 150), gapf=.25),
    photo=ph(0.34, 0.43, 0.46, 1.4), pb=(20, 70, 90), lg=(20, 70, 90), lw=.55, order='LPTF', ft='d', vbox=(212, 32, 42), fcol=(40, 40, 40), fin=OLD, seed=1947)

# Jenny Lamour (1947): black, the poster's yellow condensed JENNY LAMOUR keyed off it, Jouvet's face over the spotlight (no logo file: Majestic Films; the French title, Quai des Orfèvres, in type)
std('jenny-lamour-1947', ('grad', [(0, (40, 30, 20)), (.6, (12, 8, 6)), (1, (2, 2, 2))]), (250, 210, 40),
    L((0.05, 0.72, 0.95, 0.832), 84, (252, 212, 42), mode='key', key=(245, 205, 45), t=(70, 150)),
    photo=ph(0.6, 0.2, 0.62, 1.2), pb=(226, 70, 30), studio=['MAJESTIC FILMS'], scol=(250, 210, 40), order='lPTCF', credit=['QUAI DES ORFÈVRES'],
    ccol=(226, 200, 150), ft='c', vbox=(250, 210, 40), vink=(12, 8, 6), fcol=(210, 200, 180), fin=OLD, seed=1947)

# The Lady from Shanghai (1947): the poster's deep blue, its gold LADY and SHANGHAI and the small pale-gold THE and FROM cut off it in their own colours, Rita Hayworth's face
std('the-lady-from-shanghai-1947', ('grad', [(0, (30, 60, 130)), (.6, (14, 26, 64)), (1, (4, 8, 20))]), (240, 196, 60),
    LC([(0.18, 0.775, 0.305, 0.825), (0.3, 0.735, 0.73, 0.842), (0.045, 0.89, 0.165, 0.94), (0.16, 0.83, 0.962, 0.962)], 150, gapf=.12, valign='base',
       cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .5) & (a[..., 2] < .62) & (a[..., 0] > a[..., 2] + .25))] * 4),
    photo=ph(0.3, 0.27, 0.6, 1.2), pb=(240, 196, 60), lg=WHT, lw=.6, order='LPTF', ft='b', fcol=(210, 214, 230), fin=OLD, seed=1947)

# Bicycle Thieves (1948): the poster's watercolour cream, its slate-navy condensed BICYCLE THIEVES lifted (keyed on the cream, as the letters fade at their feet), Antonio and Bruno on the kerb (director from IMDb, credited in Italian)
std('bicycle-thieves-1948', ('grad', [(0, (246, 242, 232)), (.6, (230, 222, 206)), (1, (150, 140, 120))]), (40, 40, 80),
    L((0.12, 0.084, 0.85, 0.2), 76, (40, 40, 80), mode='nkey', key=(248, 246, 228), t=(40, 110)),
    photo=ph(0.55, 0.57, 0.66, 1.1), pb=(40, 40, 80), order='TPCF', credit=['UN FILM DI', 'VITTORIO DE SICA'], ccol=(40, 40, 80),
    ft='a', vbox=(40, 40, 80), fcol=(40, 40, 80), fin=OLD, seed=1948)

# Key Largo (1948): the poster's sunset into black, its orange KEY LARGO and the swoosh under it cut off it in their own colours, edged black and turned level, Bogart and Bacall
std('key-largo-1948', ('grad', [(0, (150, 90, 140)), (.35, (230, 140, 60)), (.7, (40, 24, 20)), (1, (4, 2, 2))]), (250, 150, 40),
    LC([(0.17, 0.64, 0.995, 0.91)], 130, outline=((10, 6, 4), 2.2), cuts=[comp_cut(lambda a: (a[..., 0] > .68) & (a[..., 1] > .2) & (a[..., 2] < .3) & (_lum(a) > .3), rot=-15)]),
    photo=ph(0.6, 0.3, 0.9, 0.8), pb=(250, 150, 40), lg=WHT, lw=.55, order='LPTCF', credit=['HUMPHREY BOGART', 'LAUREN BACALL'], ccol=(250, 200, 140),
    ft='c', vbox=(250, 150, 40), vink=(10, 6, 4), fcol=(210, 196, 180), fin=OLD, seed=1948)

# Oliver Twist (1948): the poster's dark oils, its white serif OLIVER TWIST lifted, Fagin and Oliver (director from IMDb)
std('oliver-twist-1948', ('grad', [(0, (80, 50, 34)), (.6, (34, 20, 14)), (1, (8, 4, 2))]), WHT,
    L([(0.27, 0.724, 0.955, 0.836), (0.25, 0.85, 0.9, 0.96)], 80, WHT, mode='light', gapf=.28),
    photo=ph(0.32, 0.3, 0.62, 1.25), pb=(200, 40, 30), order='PTCF', credit=['A DAVID LEAN', 'FILM'], ccol=(230, 220, 210),
    ft='e', fcol=(210, 200, 190), fin=OLD, seed=1948)

# Rope (1948): the night skyline, the poster's red serif ROPE with the rope through its O keyed off it, James Stewart (no logo file: Transatlantic Pictures, from IMDb's company credits)
std('rope-1948', ('grad', [(0, (30, 50, 90)), (.6, (12, 18, 36)), (1, (2, 4, 10))]), (220, 50, 50),
    L((0.045, 0.64, 0.935, 0.82), 120, (222, 52, 52), mode='key', key=(215, 55, 55), t=(70, 150)),
    photo=ph(0.78, 0.22, 0.44, 1.5), pb=(222, 52, 52), studio=['TRANSATLANTIC', 'PICTURES'], scol=(220, 214, 220), order='lPTF',
    dotst=('THRILLER', (222, 52, 52), WHT), ft='b', fcol=(200, 204, 220), fin=OLD, seed=1948)

# The Naked City (1948): the poster's cream, its yellow-to-orange NAKED CITY (the skyline printed in CITY) cut off it in its own colours and edged in the extrusion's blue, the city and the faces under it (Universal-International in type)
std('the-naked-city-1948', ('grad', [(0, (246, 230, 200)), (.6, (232, 206, 164)), (1, (160, 120, 80))]), (230, 100, 30),
    LC([(0.2, 0.2, 0.96, 0.39), (0.29, 0.42, 0.88, 0.61)], 110, gapf=.2, valign='base', outline=((40, 60, 110), 2.6), cuts=[
        comp_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .35) & (a[..., 2] < .45) & (a[..., 0] > a[..., 2] + .4), keep=lambda x, y: y > .12),
        comp_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .35) & (a[..., 2] < .45) & (a[..., 0] > a[..., 2] + .4))]),
    photo=ph(0.26, 0.76, 0.52, 1.3), pb=(40, 60, 90), studio=['UNIVERSAL-INTERNATIONAL'], scol=(40, 60, 90), order='lTPCF',
    credit=['DIRECTED BY', 'JULES DASSIN'], ccol=(40, 60, 90), ft='d', fcol=(40, 60, 90), fin=OLD, seed=1948)

# The Treasure of the Sierra Madre (1948): the poster's fire red, its white THE TREASURE OF THE SIERRA MADRE lifted with the red keyline, Bogart under the hat
std('the-treasure-of-the-sierra-madre-1948', ('grad', [(0, (236, 70, 30)), (.6, (170, 40, 20)), (1, (60, 14, 6))]), WHT,
    [L((0.43, 0.15, 0.575, 0.2), 34, WHT, mode='light'),
     L((0.16, 0.198, 0.845, 0.29), 72, WHT, mode='light', outline=((140, 20, 14), 2)),
     L((0.14, 0.298, 0.865, 0.386), 72, WHT, mode='light', outline=((140, 20, 14), 2))],
    tgap=6, photo=ph(0.55, 0.72, 0.8, 0.9), pb=WHT, lg=WHT, lw=.55, order='LPTSF', stick=BAR('47 0098', top='WESTERN', fill=(230, 220, 196)),
    ft='a', vbox=WHT, vink=(170, 40, 20), fcol=(240, 220, 210), fin=RENTAL, seed=1948)

# Kind Hearts and Coronets (1949): the poster's cream paper, its cream Kind Hearts (off the green panel) and its dark-green & Coronets cut off it in their own colours and edged in the panel's green, the eight d'Ascoynes (all Alec Guinness) in their frames
std('kind-hearts-and-coronets-1949', ('grad', [(0, (236, 228, 212)), (.6, (222, 212, 192)), (1, (150, 140, 120))]), (60, 110, 94),
    LC([(0.34, 0.72, 0.93, 0.822), (0.37, 0.785, 0.98, 0.925)], 120, gapf=.14, valign='base', cuts=[
        pick_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .82) & (a[..., 2] > .7), (0.34, 0.72, 0.93, 0.822), [(0.381, 0.773), (0.435, 0.781), (0.468, 0.779), (0.5, 0.786), (0.528, 0.785), (0.558, 0.774), (0.635, 0.771), (0.698, 0.78), (0.756, 0.786), (0.804, 0.775), (0.848, 0.776), (0.897, 0.784)], r=.012),
        comp_cut(lambda a: (a[..., 1] > a[..., 0] + .06) & (a[..., 1] < .57) & (_lum(a) < .5))], outline=((50, 96, 80), 2.6)),
    photo=ph(0.65, 0.38, 0.62, 1.05), pb=(70, 120, 100), lg=(60, 110, 94), lw=.55, order='LPTCF', credit=['A ROBERT HAMER', 'FILM'],
    ccol=(60, 110, 94), ft='c', fcol=(60, 90, 80), fin=OLD, seed=1949)

# Stray Dog (1949): the poster's grey paper, its dark-red STRAY DOG (set reading down the poster) cut off it in its own colours, Mifune with the gun (director from IMDb)
std('stray-dog-1949', ('grad', [(0, (214, 210, 204)), (.6, (186, 182, 176)), (1, (90, 86, 80))]), (130, 30, 30),
    LC([(0.125, 0.172, 0.262, 0.56)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .35) & (a[..., 1] < .25) & (a[..., 2] < .25) & (a[..., 0] > a[..., 1] + .15), keep=lambda x, y: x > .25, rot=90)]),
    photo=ph(0.72, 0.3, 0.56, 1.25), pb=(130, 30, 30), lg=(130, 30, 30), lw=.55, order='LPTCF', credit=['A FILM BY', 'AKIRA KUROSAWA'], ccol=(60, 40, 36),
    ft='d', fcol=(60, 40, 36), fin=OLD, seed=1949)

# The Third Man (1949): night blue, the poster's orange script The and THIRD MAN cut off it in their own colours and turned level (it climbs 12 degrees), Harry Lime's shadow under the arch (no logo file: London Film Productions, from IMDb's company credits)
std('the-third-man-1949', ('grad', [(0, (20, 40, 70)), (.6, (8, 16, 30)), (1, (2, 4, 8))]), (250, 120, 40),
    LC([(0.04, 0.03, 0.9, 0.26)], 120, cuts=[comp_cut(lambda a: (a[..., 0] > .8) & (a[..., 1] > .25) & (a[..., 1] < .65) & (a[..., 2] < .3), rot=-12)]),
    photo=ph(0.5, 0.58, 0.7, 1.35), pb=(80, 200, 200), studio=['LONDON FILM', 'PRODUCTIONS'], scol=(250, 140, 60), order='lPTCF', credit=['ORSON WELLES', 'JOSEPH COTTEN'],
    ccol=(200, 214, 230), ft='e', fcol=(190, 200, 214), fin=OLD, seed=1949)

# Thieves' Highway (1949): black, the poster's yellow condensed THIEVES' HIGHWAY keyed off it, Richard Conte and Valentina Cortese in the lamp-light
std('thieves-highway-1949', ('grad', [(0, (40, 34, 24)), (.6, (12, 10, 6)), (1, (2, 2, 2))]), (240, 220, 60),
    L((0.035, 0.75, 0.965, 0.834), 70, (242, 222, 62), mode='key', key=(235, 215, 70), t=(70, 150)),
    photo=ph(0.6, 0.32, 0.5, 1.4), pb=(242, 222, 62), lg=(242, 222, 62), lw=.55, order='LTPF', ft='a', vbox=(242, 222, 62), vink=(12, 10, 6),
    fcol=(200, 200, 190), fin=OLD, seed=1949)
