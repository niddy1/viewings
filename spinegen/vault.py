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


def comp_cut(test, keep=None, top=None, soft=1.4, rot=0, minf=.015, close=0, opn=3, fillh=False):
    """an LC cut that keeps whole letters: the connected pieces passing test (rgb 0..1), filtered by
    keep(cx, cy) (the piece's centre, as fractions of the cut-out crop) and/or only the `top` biggest.
    For lettering that interlocks on the poster (arched, stacked or overlapping words), where a straight
    box edge would take slices of the neighbouring word."""
    def fn(rgb):
        a = rgb.astype(np.float32) / 255
        m = test(a).astype(np.uint8)
        if opn > 1: m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((opn, opn), np.uint8))  # opn=1 keeps hairlines (thin serifs)
        if close: m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))  # join a letter broken by something across it
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        h, w = m.shape; ok = np.zeros(n, bool)
        big = st[1:, cv2.CC_STAT_AREA].max() if n > 1 else 0
        for j in range(1, n):
            ok[j] = st[j, cv2.CC_STAT_AREA] > big * minf and (keep is None or keep(cen[j][0] / w, cen[j][1] / h))
        if top:
            idx = [j for j in range(1, n) if ok[j]]; idx.sort(key=lambda j: -st[j, cv2.CC_STAT_AREA])
            ok[:] = False; ok[idx[:top]] = True
        k = ok[lab].astype(np.uint8)
        if fillh:  # fill each kept piece's holes, so letters outlined in the test colour come with their insides
            ff = cv2.copyMakeBorder(1 - k, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
            cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 2)
            k = (ff[1:-1, 1:-1] != 2).astype(np.uint8)
        al = _soft(k.astype(np.float32), soft)
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
        if rot == 'auto':  # level the panel: the angle of its long edge (minAreaRect), within +-45 degrees
            (_, _), (rw, rh), ang = cv2.minAreaRect(cv2.findNonZero(p.astype(np.uint8)))
            if rw < rh: ang -= 90
            rot_ = ang
        else: rot_ = rot
        al = _soft(p, soft)
        if rot_: return _turn(rgb, al, rot_)
        return rgb, al
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
    LC([(0.16, 0.045, 0.71, 0.215), (0.22, 0.212, 0.8, 0.444)], 150, gapf=.1, cuts=[key_cut(lambda a: (_sat(a) > .2) | (_lum(a) < .45))] * 2),
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


# =====================================================================================
# 1950s (vault-1950s.json, 74 tapes)
# =====================================================================================

# All About Eve (1950): the poster's white, its three printed blocks (yellow all on black, black about on red, blue eve on grey) cut off it whole in their own colours, the cast walking the arrows
std('all-about-eve-1950', ('grad', [(0, (248, 246, 240)), (.6, (232, 228, 220)), (1, (150, 146, 136))]), (20, 20, 20),
    LC([(0.035, 0.505, 0.705, 0.685)], 170, cuts=[key_cut(lambda a: _lum(a) < .9)]),
    photo=ph(0.8, 0.81, 0.4, 1.3), pb=(200, 30, 30), lg=(20, 20, 20), lw=.5, order='LPTF', ft='b', fcol=(20, 20, 20), fin=OLD, seed=1950)

# Cinderella (1950): Disney, the white clamshell; the poster's night blue, its white script Cinderella with the gold C cut off the oval, Cinderella's face in the red diamond
disney('cinderella-1950', ('grad', [(0, (20, 40, 110)), (.5, (40, 90, 180)), (1, (14, 30, 80))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.16, 0.495, 0.875, 0.6)], 120, cuts=[key_cut(lambda a: (_lum(a) > .6) & (a[..., 2] < a[..., 0] + .08))]),
       face=ph(.63, .27, .2, 1.4), lcol=WHT)

# Night and the City (1950): the poster's dark oils, NIGHT AND THE CITY typeset in heavy italic capitals in the poster's cream with its red shadow (typeset: NIGHT and CITY lift, but the small AND THE between them is painted over the boxers' fists and came apart in three cuts, and the title has to read whole), Widmark's face (top-billed cast from IMDb)
std('night-and-the-city-1950', ('grad', [(0, (70, 56, 40)), (.6, (26, 20, 14)), (1, (6, 4, 2))]), (240, 222, 160),
    TT([('NIGHT ', (240, 222, 160)), ('AND THE ', (214, 70, 40)), ('CITY', (240, 222, 160))], 'herbi', 74, sp=.1),
    photo=ph(0.45, 0.7, 0.8, 0.85), pb=(240, 222, 160), lg=(240, 222, 160), lw=.55, order='LPTCF', credit=['RICHARD WIDMARK', 'GENE TIERNEY'],
    ccol=(230, 214, 170), ft='c', vbox=(240, 222, 160), vink=(26, 20, 14), fcol=(210, 200, 180), fin=OLD, seed=1950)

# Rashomon (1950): the woods' dark gold, the poster's white wide RASHOMON lifted, Mifune from the top of the poster (director from IMDb)
std('rashomon-1950', ('grad', [(0, (90, 80, 40)), (.6, (34, 30, 14)), (1, (6, 6, 2))]), WHT,
    L((0.16, 0.615, 0.84, 0.69), 86, WHT, mode='key', key=(250, 250, 250), t=(60, 150)),
    photo=ph(0.45, 0.22, 0.9, 0.85), pb=(240, 200, 60), lg=WHT, lw=.55, order='LPTCF', credit=['A FILM BY', 'AKIRA KUROSAWA'], ccol=WHT,
    ft='d', fcol=(210, 206, 190), fin=OLD, seed=1950)

# Stage Fright (1950): the poster's yellow, its white extruded STAGE FRIGHT lifted and edged in its black shadow, Dietrich and Jane Wyman in the chevron
std('stage-fright-1950', ('grad', [(0, (252, 206, 30)), (.6, (240, 180, 10)), (1, (170, 110, 0))]), WHT,
    L([(0.02, 0.64, 0.58, 0.716), (0.22, 0.718, 0.955, 0.818)], 92, WHT, mode='key', key=(252, 252, 252), t=(50, 140), gapf=.2, outline=((20, 16, 12), 3)),
    photo=ph(0.56, 0.3, 0.6, 1.45), pb=(20, 16, 12), lg=(20, 16, 12), lw=.55, order='LPTSF', stick=RWD(fill=(250, 246, 230)),
    ft='e', vbox=(20, 16, 12), fcol=(30, 24, 16), fin=RENTAL, seed=1950)

# Sunset Boulevard (1950): the poster's red, SUNSET BOULEVARD typeset in condensed capitals in the poster's yellow with its black keyline (typeset: on the poster each letter rides the curling film strip at its own angle, half-hidden by the sprocket holes; two cuts, by word and by letter, came out in pieces), Gloria Swanson's face
std('sunset-boulevard-1950', ('grad', [(0, (226, 50, 40)), (.6, (170, 30, 24)), (1, (60, 10, 8))]), (250, 226, 80),
    T('SUNSET BOULEVARD', 'hcnb', 70, (250, 228, 84), track=.06, outline=((20, 16, 14), 2.6)),
    photo=ph(0.58, 0.17, 0.72, 0.72), pb=(250, 226, 80), lg=WHT, lw=.55, order='LPTF', ft='a', vbox=(250, 226, 80), vink=(170, 30, 24),
    fcol=(250, 220, 210), fin=OLD, seed=1950)

# A Streetcar Named Desire (1951): the poster's grey paper, its red serif "A Streetcar Named Desire" keyed off it, Brando and Vivien Leigh in the yellow frame
std('a-streetcar-named-desire-1951', ('grad', [(0, (236, 234, 228)), (.6, (216, 212, 204)), (1, (130, 126, 118))]), (200, 40, 40),
    L([(0.155, 0.675, 0.85, 0.74), (0.085, 0.742, 0.92, 0.828)], 70, (204, 42, 42), mode='key', key=(200, 50, 50), t=(70, 150), gapf=.25),
    photo=ph(0.48, 0.3, 0.86, 0.95), pb=(240, 210, 40), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['VIVIEN LEIGH', 'MARLON BRANDO'], ccol=(40, 40, 40),
    ft='b', fcol=(40, 40, 40), fin=OLD, seed=1951)

# Ace in the Hole (1951): the cave's dark, the poster's white condensed ACE IN THE HOLE lifted in its two lines, Kirk Douglas's face (director from IMDb)
std('ace-in-the-hole-1951', ('grad', [(0, (80, 66, 50)), (.6, (30, 24, 18)), (1, (6, 4, 2))]), WHT,
    [LC([(0.09, 0.6, 0.63, 0.792)], 80, margin=0, cuts=[comp_cut(lambda a: (_lum(a) > .62) & (_sat(a) < .3), keep=lambda x, y: x > .1, minf=.2)]),
     LC([(0.25, 0.79, 0.38, 0.88), (0.17, 0.885, 0.38, 0.958), (0.37, 0.765, 0.935, 0.958)], 80, gapf=.15, valign='base', cuts=[
        pick_cut(lambda a: _lum(a) > .62, (0.25, 0.79, 0.38, 0.88), [(0.282, 0.835), (0.335, 0.835)], r=.015),
        pick_cut(lambda a: _lum(a) > .5, (0.17, 0.885, 0.38, 0.958), [(0.214, 0.915), (0.281, 0.918), (0.34, 0.917)], r=.02),
        comp_cut(lambda a: _lum(a) > .5, keep=lambda x, y: x > .08 and y > .2, minf=.2)])],
    tgap=8, photo=ph(0.52, 0.27, 0.7, 0.9), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A BILLY WILDER', 'FILM'], ccol=WHT,
    ft='c', fcol=(210, 200, 190), fin=OLD, seed=1951)

# Alice in Wonderland (1951): Disney, the white clamshell; the mad tea party's black and pink, the poster's cream ALICE in WONDERLAND cut off it in its own colours, Alice's face in the red diamond
disney('alice-in-wonderland-1951', ('grad', [(0, (40, 30, 50)), (.5, (110, 40, 80)), (1, (20, 14, 26))]), fin=dict(CLAM, vivid=.2),
       title=[LC([(0.11, 0.7, 0.845, 0.85)], 90, cuts=[key_cut(lambda a: (_lum(a) > .78) & (a[..., 2] < a[..., 0]))]),
              LC([(0.07, 0.852, 0.93, 0.918)], 52, cuts=[key_cut(lambda a: (_lum(a) > .78) & (a[..., 2] < a[..., 0]))])],
       face=ph(.55, .19, .2, 1.4), lcol=WHT)

# Strangers on a Train (1951): the poster's orange and white, its three printed blocks (blue "strangers", lilac on a, red train") cut off it whole and levelled, Farley Granger smoking
std('strangers-on-a-train-1951', ('grad', [(0, (240, 100, 40)), (.5, (230, 70, 30)), (.55, (246, 246, 242)), (1, (200, 200, 196))]), (20, 30, 120),
    LC([(0.18, 0.07, 0.96, 0.22), (0.6, 0.34, 0.93, 0.47), (0.41, 0.47, 0.97, 0.65)], 90, gapf=.1, valign='mid', margin=0, cuts=[
        plate_cut(lambda a: (a[..., 2] > .45) & (a[..., 0] < .25), rot='auto'),
        plate_cut(lambda a: (a[..., 0] > .55) & (a[..., 2] > .6) & (a[..., 1] < .65), rot='auto'),
        plate_cut(lambda a: (a[..., 0] > .75) & (a[..., 1] < .2) & (a[..., 2] < .25), rot='auto')]),
    photo=ph(0.52, 0.36, 0.6, 1.0), pb=(20, 30, 120), lg=(20, 30, 120), lw=.55, order='LPTF', dotst=('THRILLER', (20, 30, 120), WHT),
    ft='d', vbox=(220, 30, 30), fcol=(40, 40, 60), fin=OLD, seed=1951)

# The Day the Earth Stood Still (1951): black and fire, the poster's white THE DAY THE EARTH / STOOD STILL lifted, Gort carrying the woman
std('the-day-the-earth-stood-still-1951', ('grad', [(0, (40, 60, 110)), (.5, (16, 22, 44)), (1, (4, 4, 8))]), WHT,
    [LC([(0.15, 0.832, 0.85, 0.879)], 56, margin=0, cuts=[key_cut(lambda a: (_lum(a) > .4) & (_sat(a) < .2))]), LC([(0.15, 0.881, 0.85, 0.945)], 56, margin=0, cuts=[key_cut(lambda a: (_lum(a) > .4) & (_sat(a) < .2))])],
    tgap=8, photo=ph(0.42, 0.27, 0.66, 1.25), pb=(240, 140, 40), lg=WHT, lw=.55, order='LPTSF', stick=BAR('47 1951', top='SCI-FI', fill=(220, 226, 236)),
    ft='a', vbox=(240, 140, 40), vink=(16, 22, 44), fcol=(200, 206, 220), fin=RENTAL, seed=1951)

# The Lavender Hill Mob (1951): the poster's sky blue, its navy THE LAVENDER and HILL MOB lifted, the chase along the London skyline
std('the-lavender-hill-mob-1951', ('grad', [(0, (150, 200, 210)), (.6, (100, 160, 176)), (1, (40, 80, 96))]), (20, 40, 70),
    [L((0.24, 0.552, 0.755, 0.78), 76, (20, 40, 70), mode='dark'), L((0.24, 0.78, 0.755, 0.912), 76, (20, 40, 70), mode='dark')],
    tgap=8, photo=ph(0.5, 0.42, 1.0, 0.42), pb=(20, 40, 70), lg=(20, 40, 70), lw=.55, order='LPTF', ft='e', fcol=(20, 40, 70), fin=OLD, seed=1951)

# The Man in the White Suit (1951): the poster's crimson, its black THE MAN IN THE and the cream WHITE and black SUIT cut off it in their own colours (keyed on the crimson round them), Guinness running in the suit
WSC = lambda a: _lum(a) < .15
std('the-man-in-the-white-suit-1951', ('grad', [(0, (150, 20, 40)), (.6, (100, 10, 26)), (1, (40, 4, 10))]), (240, 228, 200),
    [LC([(0.1, 0.025, 0.99, 0.13)], 44, margin=0, cuts=[comp_cut(lambda a: a[..., 0] < a[..., 1] + .12, minf=.05)]),
     LC([(0.0, 0.128, 0.995, 0.302)], 96, margin=0, cuts=[comp_cut(lambda a: a[..., 0] < a[..., 1] + .12, keep=lambda x, y: y > .3, minf=.05)])],
    tgap=6, photo=ph(0.45, 0.66, 0.8, 1.0), pb=(240, 228, 200), lg=(240, 228, 200), lw=.55, order='LPTF', ft='b', fcol=(230, 200, 200), fin=OLD, seed=1951)

# Ikiru (1952): the snowy night's black, the poster's white spaced IKIRU lifted, Watanabe on the swing (top-billed cast from IMDb)
std('ikiru-1952', ('grad', [(0, (50, 54, 56)), (.6, (18, 20, 22)), (1, (4, 4, 4))]), WHT,
    L((0.2, 0.177, 0.82, 0.258), 76, WHT, mode='light'),
    photo=ph(0.5, 0.6, 0.66, 1.25), pb=WHT, lg=WHT, lw=.55, order='LTPF', ft='e', fcol=(200, 204, 206), fin=OLD, seed=1952)

# Singin' in the Rain (1952): the rainy night's blue, its yellow SINGIN' and IN THE RAIN cut off it in their own colours and levelled, Gene Kelly on the lamp-post
SRY = lambda a: (a[..., 0] > .8) & (a[..., 1] > .6) & (a[..., 2] < .3)
std('singin-in-the-rain-1952', ('grad', [(0, (30, 60, 90)), (.6, (12, 26, 44)), (1, (4, 8, 14))]), (250, 210, 30),
    LC([(0.24, 0.62, 0.82, 0.735), (0.07, 0.7, 0.92, 0.815)], 90, gapf=.18, valign='base', cuts=[comp_cut(SRY, rot=6),
        pick_cut(SRY, (0.07, 0.7, 0.92, 0.815), [(0.109, 0.761), (0.189, 0.749), (0.309, 0.736), (0.389, 0.75), (0.476, 0.761), (0.605, 0.775), (0.705, 0.781), (0.777, 0.776), (0.856, 0.767)], r=.02, rot=2)]),
    photo=ph(0.55, 0.3, 0.8, 1.0), pb=(250, 210, 30), lg=WHT, lw=.55, order='LPTF', dotst=('MUSICAL', (250, 210, 30), (12, 26, 44)),
    ft='a', vbox=(250, 210, 30), vink=(12, 26, 44), fcol=(200, 210, 220), fin=OLD, seed=1952)

# The African Queen (1952): the jungle's green, THE AFRICAN QUEEN typeset in heavy italic capitals in the poster's yellow-green (typeset: the poster's A is mostly hidden behind the leaves, so a cut reads FRICAN; three cuts tried), Bogart and Hepburn (no logo file: Romulus Films, from IMDb's company credits)
std('the-african-queen-1952', ('grad', [(0, (40, 110, 60)), (.6, (16, 50, 26)), (1, (4, 16, 8))]), (230, 230, 70),
    TT([('THE ', (232, 236, 90)), ('AFRICAN QUEEN', (232, 236, 90))], 'intbki', 64, outline=((10, 30, 16), 2.2)),
    photo=ph(0.5, 0.56, 0.96, 0.8), pb=(230, 230, 70), studio=['ROMULUS FILMS'], scol=(230, 230, 70), order='lPTCF',
    credit=['HUMPHREY BOGART', 'KATHARINE HEPBURN'], ccol=(220, 230, 200), ft='c', vbox=(230, 230, 70), vink=(16, 50, 26), fcol=(200, 220, 200), fin=OLD, seed=1952)

# Umberto D. (1952): the poster's white, its red condensed UMBERTO D. keyed off it, Umberto and Flike under it (no logo file: Dear Film, from IMDb's company credits; director from IMDb, in Italian)
std('umberto-d-1952', ('grad', [(0, (244, 242, 238)), (.6, (226, 224, 218)), (1, (140, 138, 132))]), (200, 40, 40),
    L((0.425, 0.026, 0.998, 0.12), 80, (204, 42, 42), mode='key', key=(200, 50, 50), t=(70, 150)),
    photo=ph(0.4, 0.55, 0.62, 1.7), pb=(30, 30, 30), studio=['DEAR FILM'], scol=(30, 30, 30), order='lTPCF', credit=['UN FILM DI', 'VITTORIO DE SICA'],
    ccol=(30, 30, 30), ft='d', fcol=(30, 30, 30), fin=OLD, seed=1952)

# I Confess (1953): black and the yellow light, the poster's red "I Confess" in its yellow keyline cut off it whole and levelled (it climbs 10 degrees), Montgomery Clift in his cassock
std('i-confess-1953', ('grad', [(0, (40, 34, 30)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (230, 30, 40),
    LC([(0.0, 0.1, 0.66, 0.34)], 110, cuts=[comp_cut(lambda a: (_sat(a) > .5) & (a[..., 0] > .6), top=2, rot=-10)]),
    photo=ph(0.79, 0.3, 0.38, 1.7), pb=(250, 220, 40), lg=WHT, lw=.55, order='LPTSF', stick=PRC(['$1.99', 'THRILLER']),
    ft='b', fcol=(210, 200, 190), fin=RENTAL, seed=1953)

# I Vitelloni (1953): the poster's white, its red brush I VITELLONI keyed off it, Sandra in the waves (no logo file: Peg-Films, from IMDb's company credits; director from IMDb, in Italian)
std('i-vitelloni-1953', ('grad', [(0, (240, 244, 246)), (.6, (210, 222, 230)), (1, (110, 140, 160))]), (200, 30, 40),
    L((0.37, 0.758, 0.905, 0.915), 100, (204, 32, 42), mode='key', key=(200, 40, 50), t=(70, 150)),
    photo=ph(0.55, 0.35, 0.9, 0.8), pb=(30, 60, 90), studio=['PEG-FILMS'], scol=(30, 60, 90), order='lPTCF', credit=['UN FILM DI', 'FEDERICO FELLINI'],
    ccol=(30, 60, 90), ft='a', vbox=(200, 30, 40), fcol=(30, 60, 90), fin=OLD, seed=1953)

# Monsieur Hulot's Holiday (1953): the poster's sand, its blue MONSIEUR HULOT'S HOLIDAY lifted in its three lines into one, Hulot drawn on the beach under the title
std('monsieur-hulot-s-holiday-1953', ('grad', [(0, (236, 230, 216)), (.6, (220, 210, 190)), (1, (150, 136, 110))]), (30, 140, 200),
    L([(0.315, 0.046, 0.78, 0.141), (0.24, 0.15, 0.655, 0.228), (0.24, 0.228, 0.61, 0.305)], 76, (30, 140, 200), mode='key', key=(40, 150, 210), t=(70, 150), gapf=.22),
    photo=ph(0.55, 0.66, 0.66, 1.35), pb=(30, 140, 200), lg=(60, 60, 60), lw=.55, order='LTPCF', credit=['JACQUES TATI'], ccol=(60, 60, 60),
    ft='c', fcol=(60, 60, 60), fin=OLD, seed=1953)

# Peter Pan (1953): Disney, the white clamshell; the poster's night-sky blue, its white serif PETER PAN cut off the red plaque, Peter's face in the red diamond
disney('peter-pan-1953', ('grad', [(0, (20, 40, 120)), (.5, (40, 100, 190)), (1, (20, 60, 70))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.09, 0.512, 0.87, 0.6)], 110, cuts=[key_cut(lambda a: _lum(a) > .8)]),
       face=ph(.6, .22, .22, 1.4), lcol=WHT)

# Pickup on South Street (1953): the poster's white, its red brush Pickup and ON SOUTH STREET keyed off it, Jean Peters and Richard Widmark
std('pickup-on-south-street-1953', ('grad', [(0, (244, 242, 238)), (.6, (226, 222, 214)), (1, (150, 140, 130))]), (200, 30, 40),
    [L((0.12, 0.062, 0.88, 0.17), 80, (204, 32, 42), mode='key', key=(200, 40, 50), t=(70, 150)), L((0.22, 0.17, 0.875, 0.252), 50, (204, 32, 42), mode='key', key=(200, 40, 50), t=(70, 150))],
    tgap=8, photo=ph(0.5, 0.66, 0.9, 1.0), pb=(30, 90, 140), lg=(30, 30, 30), lw=.55, order='LPTSF', stick=RWD(),
    ft='e', fcol=(40, 40, 40), fin=RENTAL, seed=1953)

# The Wages of Fear (1953): black, the poster's pale-yellow THE WAGES and OF FEAR cut off it letter by letter, the burning truck (no logo file: Filmsonor, from IMDb's company credits)
WFY = lambda a: (a[..., 0] > .85) & (a[..., 1] > .85) & (a[..., 2] < .8)
std('the-wages-of-fear-1953', ('grad', [(0, (40, 30, 26)), (.6, (12, 8, 6)), (1, (2, 2, 2))]), (250, 246, 170),
    [LC([(0.08, 0.28, 0.86, 0.42)], 70, cuts=[pick_cut(WFY, (0.08, 0.28, 0.86, 0.42), [(0.109, 0.317), (0.15, 0.32), (0.193, 0.317), (0.307, 0.348), (0.437, 0.355), (0.548, 0.347), (0.657, 0.339), (0.78, 0.33)], r=.02, rot=-4)]),
     LC([(0.2, 0.37, 0.87, 0.53)], 70, cuts=[pick_cut(WFY, (0.2, 0.37, 0.87, 0.53), [(0.246, 0.447), (0.305, 0.438), (0.395, 0.453), (0.512, 0.447), (0.635, 0.437), (0.771, 0.425)], r=.02, rot=-4)])],
    tgap=8, photo=ph(0.55, 0.75, 0.9, 0.7), pb=(230, 70, 40), studio=['FILMSONOR'], scol=(250, 246, 170), order='lPTF', ft='d', fcol=(200, 196, 186), fin=OLD, seed=1953)

# Ugetsu (1953): the misty grey, the poster's white serif UGETSU lifted, the boat on the lake (director from IMDb)
std('ugetsu-1953', ('grad', [(0, (130, 130, 128)), (.6, (60, 60, 60)), (1, (14, 14, 14))]), WHT,
    L((0.155, 0.846, 0.85, 0.93), 76, WHT, mode='light'),
    photo=ph(0.5, 0.5, 1.0, 0.75), pb=WHT, lg=WHT, lw=.55, order='LPTCF', credit=['A FILM BY', 'KENJI MIZOGUCHI'], ccol=WHT,
    ft='b', fcol=(210, 210, 210), fin=OLD, seed=1953)

# Dial M for Murder (1954): the poster's dark red, its cream "dial, the red M on its cream tile, for and Murder" cut off it in their own colours and run in one line, the reaching hand and the telephone
DMC = lambda a: (_lum(a) > .78) | ((a[..., 0] > .7) & (a[..., 1] < .3))
std('dial-m-for-murder-1954', ('grad', [(0, (150, 20, 20)), (.6, (90, 10, 10)), (1, (30, 4, 4))]), (244, 238, 220),
    LC([(0.395, 0.575, 0.585, 0.665), (0.43, 0.67, 0.565, 0.765), (0.44, 0.77, 0.55, 0.825), (0.31, 0.825, 0.68, 0.915)], 100, gapf=.14, valign='base',
       cuts=[comp_cut(DMC, minf=.05), plate_cut(lambda a: (_lum(a) > .6) | ((a[..., 0] > .7) & (a[..., 1] < .3))), comp_cut(DMC), comp_cut(DMC, minf=.05)]),
    photo=ph(0.5, 0.2, 1.0, 0.6), pb=(244, 238, 220), lg=(244, 238, 220), lw=.55, order='LPTF', ft='c', vbox=(244, 238, 220), vink=(90, 10, 10), fcol=(230, 200, 196), fin=OLD, seed=1954)

# La Strada (1954): the poster's white, its red LA STRADA keyed off it in its two lines, Gelsomina at the pole (no logo file: Ponti-De Laurentiis, from IMDb's company credits)
std('la-strada-1954', ('grad', [(0, (246, 244, 240)), (.6, (230, 226, 218)), (1, (150, 144, 134))]), (220, 50, 30),
    L([(0.475, 0.342, 0.69, 0.414), (0.288, 0.422, 0.94, 0.497)], 84, (224, 52, 32), mode='key', key=(220, 60, 40), t=(70, 150), gapf=.3),
    photo=ph(0.2, 0.42, 0.3, 1.8), pb=(224, 52, 32), studio=['PONTI-DE LAURENTIIS'], scol=(30, 30, 30), order='lPTF', ft='a', vbox=(224, 52, 32), fcol=(30, 30, 30), fin=OLD, seed=1954)

# On the Waterfront (1954): the docks' gold into dark, the poster's yellow script On The Waterfront keyed off it, Brando walking with the hook
std('on-the-waterfront-1954', ('grad', [(0, (200, 150, 60)), (.5, (110, 70, 30)), (1, (20, 12, 6))]), (250, 200, 30),
    L((0.115, 0.856, 0.885, 0.918), 80, (252, 204, 32), mode='key', key=(240, 190, 40), t=(70, 150)),
    photo=ph(0.5, 0.4, 0.7, 1.3), pb=(250, 200, 30), lg=WHT, lw=.55, order='LPTF', ft='d', vbox=(250, 200, 30), vink=(20, 12, 6), fcol=(220, 200, 170), fin=OLD, seed=1954)

# Rear Window (1954): the brick red, the poster's pale teal REAR WINDOW keyed off it, Stewart with the camera and Grace Kelly under the title (no logo file: Alfred J. Hitchcock Productions, from IMDb's company credits)
std('rear-window-1954', ('grad', [(0, (160, 50, 40)), (.6, (90, 24, 20)), (1, (30, 6, 6))]), (150, 220, 214),
    L((0.072, 0.338, 0.925, 0.402), 76, (152, 222, 216), mode='key', key=(140, 210, 205), t=(70, 150)),
    photo=ph(0.55, 0.87, 0.8, 0.5), pb=(152, 222, 216), studio=['ALFRED J. HITCHCOCK', 'PRODUCTIONS'], scol=(152, 222, 216), order='lTPSF',
    stick=flow(dot, 74, ['SUSPENSE'], (152, 222, 216), (90, 24, 20)), ft='e', fcol=(220, 200, 196), fin=OLD, seed=1954)

# Samurai I: Musashi Miyamoto (1954): the poster's red sun, its black band with the white MUSASHI MIYAMOTO cut off it whole (SAMURAI I, printed small on the poster's edge, in type under it), Musashi drawing his sword
std('samurai-i-musashi-miyamoto-1954', ('grad', [(0, (226, 60, 40)), (.6, (170, 30, 20)), (1, (60, 10, 6))]), WHT,
    LC([(0.0, 0.872, 1.0, 0.962)], 70, margin=0, cuts=[plate_cut(lambda a: _lum(a) < .2)]),
    photo=ph(0.5, 0.42, 0.9, 1.15), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['SAMURAI I', 'TOSHIRŌ MIFUNE'], ccol=WHT,
    ft='b', fcol=(240, 220, 210), fin=OLD, seed=1954)

# Sansho the Bailiff (1954): the poster's grey-green, Sansho and THE BAILIFF typeset in a light serif like the poster's, in its white (typeset: the o of Sansho sits on a pale cloth of its own colour and drops out of every key; two tried), the figure in black
std('sansho-the-bailiff-1954', ('grad', [(0, (176, 186, 176)), (.6, (130, 140, 130)), (1, (50, 56, 50))]), WHT,
    TT([('Sansho', WHT), ('THE BAILIFF', (236, 238, 234))], 'ter', 80, sp=.5, outline=((60, 66, 60), 1.2)),
    photo=ph(0.48, 0.28, 0.6, 1.25), pb=(30, 34, 30), lg=(30, 34, 30), lw=.55, order='LPTF', ft='e', fcol=(30, 34, 30), fin=OLD, seed=1954)

# Seven Samurai (1954): a 2-tape box; the poster's charcoal, its white brush Seven Samurai lifted, the village and its faces
std('seven-samurai-1954', ('grad', [(0, (80, 80, 76)), (.6, (30, 30, 28)), (1, (6, 6, 6))]), WHT,
    L((0.17, 0.462, 0.86, 0.562), 110, WHT, mode='light'),
    photo=ph(0.5, 0.82, 1.0, 0.5), pb=WHT, lg=WHT, lw=.5, order='LTPCSF', credit=['TOSHIRŌ MIFUNE', 'TAKASHI SHIMURA'], ccol=WHT,
    stick=TWOST((200, 30, 30), WHT), ft='d', fcol=(210, 210, 206), fin=OLD, seed=1954, **TWO)

# Touchez pas au grisbi (1954): the poster's white, its red outlined GRISBI keyed off it (the French title under it in type), the hold-up from the top of the poster (no logo file: Del Duca Films, from IMDb's company credits)
std('touchez-pas-au-grisbi-1954', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (140, 136, 128))]), (210, 40, 60),
    L((0.022, 0.682, 0.762, 0.826), 110, (214, 42, 62), mode='key', key=(210, 50, 70), t=(70, 150)),
    photo=ph(0.42, 0.3, 0.76, 0.85), pb=(20, 20, 20), studio=['DEL DUCA FILMS'], scol=(20, 20, 20), order='lPTCF', credit=['TOUCHEZ PAS AU GRISBI'],
    ccol=(20, 20, 20), ft='a', vbox=(214, 42, 62), fcol=(20, 20, 20), fin=OLD, seed=1954)

# Diabolique (1955): black, the poster's cream DIABOLIQUE rebuilt letter by letter off the ripple it curves along, the hand over the water (no logo file: Filmsonor, from IMDb's company credits)
std('diabolique-1955', ('grad', [(0, (40, 34, 34)), (.6, (12, 10, 10)), (1, (2, 2, 2))]), (240, 232, 214),
    LC([(0.0, 0.62, 1.0, 0.78)], 90, cuts=[seq_cut(lambda a: (_lum(a) > .75) & (a[..., 2] < a[..., 0] + .05), (0.0, 0.62, 1.0, 0.78),
        [(0.098, 0.696), (0.165, 0.702), (0.221, 0.709), (0.318, 0.714), (0.447, 0.709), (0.541, 0.705), (0.616, 0.692), (0.701, 0.679), (0.792, 0.649), (0.885, 0.626)], gapf=.08)]),
    photo=ph(0.5, 0.25, 0.9, 0.7), pb=(214, 40, 40), studio=['FILMSONOR'], scol=(240, 232, 214), order='lPTCSF', credit=['SIMONE SIGNORET', 'VÉRA CLOUZOT'],
    ccol=(240, 232, 214), stick=RWD(fill=(240, 230, 210)), ft='c', fcol=(200, 196, 190), fin=RENTAL, seed=1955)

# Lady and the Tramp (1955): Disney, the white clamshell; the poster's night blue, its white script Lady and the Tramp cut off it, Lady's face in the red diamond
disney('lady-and-the-tramp-1955', ('grad', [(0, (30, 40, 120)), (.5, (50, 70, 170)), (1, (20, 24, 70))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.115, 0.162, 0.885, 0.255)], 110, cuts=[key_cut(lambda a: _lum(a) > .85)]),
       face=ph(.66, .66, .2, 1.4), lcol=WHT)

# Rififi (1955): the poster's blue, its yellow RIFIFI keyed off it, the safecracker's gloved hand with the diamond (no logo file: Pathé Consortium Cinéma, from IMDb's company credits; director from IMDb)
std('rififi-1955', ('grad', [(0, (30, 150, 230)), (.6, (20, 100, 170)), (1, (6, 34, 70))]), (250, 190, 30),
    L((0.055, 0.796, 0.946, 0.97), 110, (252, 192, 32), mode='key', key=(245, 185, 40), t=(70, 150)),
    photo=ph(0.5, 0.5, 0.8, 1.0), pb=WHT, studio=['PATHÉ'], scol=WHT, order='lPTCF', credit=['UN FILM DE', 'JULES DASSIN'], ccol=WHT,
    ft='b', fcol=(220, 230, 240), fin=OLD, seed=1955)

# Samurai II: Duel at Ichijoji Temple (1955): the poster's red sun, its black band with the white DUEL AT ICHIJOJI TEMPLE cut off it whole (SAMURAI II in type under it), Musashi among the swords
std('samurai-ii-duel-at-ichijoji-temple-1955', ('grad', [(0, (230, 70, 40)), (.6, (176, 40, 24)), (1, (70, 14, 8))]), WHT,
    LC([(0.0, 0.872, 1.0, 0.962)], 70, margin=0, cuts=[plate_cut(lambda a: _lum(a) < .2)]),
    photo=ph(0.45, 0.32, 0.8, 0.9), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCSF', credit=['SAMURAI II'], ccol=WHT, stick=BAR('59 0612', top='SAMURAI', fill=(236, 226, 206)),
    ft='a', vbox=(20, 20, 20), fcol=(240, 220, 210), fin=RENTAL, seed=1955)

# The Ladykillers (1955): the poster's pale blue-white, its red The Ladykillers with its grey shadow keyed off it, the gang in the parlour
std('the-ladykillers-1955', ('grad', [(0, (236, 242, 244)), (.6, (210, 222, 228)), (1, (120, 140, 150))]), (200, 30, 40),
    L((0.135, 0.722, 0.855, 0.95), 120, (204, 32, 42), mode='key', key=(200, 40, 50), t=(70, 150), shadow=((120, 130, 136), 3, 3)),
    photo=ph(0.5, 0.35, 0.9, 0.8), pb=(40, 60, 70), lg=(40, 60, 70), lw=.55, order='LPTF', ft='a', vbox=(204, 32, 42), fcol=(40, 60, 70), fin=OLD, seed=1955)

# The Night of the Hunter (1955): black, the poster's white serif THE NIGHT / OF THE HUNTER lifted, Mitchum and Shelley Winters (top-billed cast from IMDb)
std('the-night-of-the-hunter-1955', ('grad', [(0, (40, 40, 42)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    [L([(0.72, 0.597, 0.96, 0.68), (0.66, 0.685, 0.962, 0.768)], 66, WHT, mode='light', gapf=.3),
     L([(0.605, 0.773, 0.96, 0.856), (0.545, 0.862, 0.962, 0.945)], 66, WHT, mode='light', gapf=.3)],
    tgap=8, photo=ph(0.35, 0.3, 0.6, 1.1), pb=WHT, lg=WHT, lw=.55, order='LPTF', ft='c', fcol=(200, 200, 200), fin=OLD, seed=1955)

# The Trouble with Harry (1955): the poster's white, its red serif THE TROUBLE / WITH HARRY keyed off it, the man in the autumn woods (no logo file: Alfred J. Hitchcock Productions, from IMDb's company credits)
std('the-trouble-with-harry-1955', ('grad', [(0, (246, 242, 234)), (.6, (230, 220, 200)), (1, (150, 110, 70))]), (200, 40, 34),
    [L([(0.175, 0.433, 0.36, 0.487), (0.095, 0.492, 0.458, 0.545)], 64, (204, 42, 36), mode='key', key=(200, 50, 40), t=(70, 150), gapf=.3),
     L([(0.16, 0.552, 0.387, 0.601), (0.122, 0.61, 0.428, 0.655)], 64, (204, 42, 36), mode='key', key=(200, 50, 40), t=(70, 150), gapf=.3)],
    tgap=8, photo=ph(0.72, 0.52, 0.5, 1.7), pb=(204, 42, 36), studio=['ALFRED J. HITCHCOCK', 'PRODUCTIONS'], scol=(60, 40, 30), order='lPTSF',
    stick=PRC(['$1.49', 'COMEDY']), ft='e', fcol=(60, 40, 30), fin=RENTAL, seed=1955)

# And God Created Woman (1956): black, the poster's white serif "...and God created woman" lifted, Bardot (no logo file: Cocinor, from IMDb's company credits)
std('and-god-created-woman-1956', ('grad', [(0, (60, 20, 14)), (.6, (18, 6, 4)), (1, (2, 2, 2))]), WHT,
    L((0.335, 0.85, 0.9, 0.882), 50, WHT, mode='light', speck=0),
    photo=ph(0.55, 0.42, 0.8, 1.15), pb=(240, 160, 50), studio=['COCINOR'], scol=(240, 160, 50), order='lPTF', ft='b', fcol=(210, 200, 190), fin=OLD, seed=1956)

# Bob le Flambeur (1956): black, the poster's white ornate BOB, LE and FLAMBEUR from the playing card lifted into one line, Bob's profile in the spade (no logo file: O.G.C., from IMDb's company credits; director from IMDb)
std('bob-le-flambeur-1956', ('grad', [(0, (24, 44, 44)), (.6, (8, 14, 14)), (1, (2, 2, 2))]), WHT,
    L([(0.285, 0.1, 0.715, 0.19), (0.39, 0.775, 0.61, 0.832), (0.225, 0.855, 0.775, 0.906)], 80, WHT, mode='light', gapf=.25, speck=0),
    photo=ph(0.5, 0.48, 0.66, 0.9), pb=WHT, studio=['O.G.C.'], scol=WHT, order='lPTCF', credit=['UN FILM DE', 'JEAN-PIERRE MELVILLE'], ccol=WHT,
    ft='d', fcol=(190, 210, 206), fin=OLD, seed=1956)

# Night and Fog (1956): black, the poster's thin grey NIGHT AND FOG lifted, the barbed wire (director from IMDb)
std('night-and-fog-1956', ('grad', [(0, (40, 36, 30)), (.6, (14, 12, 10)), (1, (2, 2, 2))]), (190, 190, 186),
    L((0.11, 0.49, 0.9, 0.55), 60, (200, 200, 196), mode='light'),
    photo=ph(0.5, 0.2, 1.0, 0.4), pb=(150, 130, 100), lg=(200, 200, 196), lw=.55, order='LPTCF', credit=['A DOCUMENTARY BY', 'ALAIN RESNAIS'], ccol=(200, 200, 196),
    ft='a', fcol=(170, 170, 166), fin=OLD, seed=1956)

# Samurai III: Duel at Ganryu Island (1956): the poster's red sun, its black band with the white DUEL AT GANRYU ISLAND cut off it whole (SAMURAI III in type under it), Musashi in the boat
std('samurai-iii-duel-at-ganryu-island-1956', ('grad', [(0, (222, 64, 40)), (.6, (166, 34, 22)), (1, (60, 10, 6))]), WHT,
    LC([(0.0, 0.872, 1.0, 0.962)], 70, margin=0, cuts=[plate_cut(lambda a: _lum(a) < .2)]),
    photo=ph(0.42, 0.48, 0.86, 1.05), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['SAMURAI III'], ccol=WHT,
    ft='e', fcol=(240, 220, 210), fin=OLD, seed=1956)

# The Harder They Fall (1956): the ring's blue, the poster's red THE HARDER THEY FALL cut word by word off the newspaper page into one line, edged in its black shadow, the boxing gloves
std('the-harder-they-fall-1956', ('grad', [(0, (40, 150, 210)), (.6, (20, 90, 140)), (1, (6, 30, 50))]), (214, 40, 40),
    LC([(0.35, 0.618, 0.49, 0.685), (0.34, 0.728, 0.69, 0.812), (0.34, 0.812, 0.48, 0.9), (0.515, 0.852, 0.69, 0.945)], 80, gapf=.18, valign='base', outline=((20, 16, 14), 2),
       cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] < .4) & (a[..., 2] < .4), minf=.05)] * 4),
    photo=ph(0.45, 0.43, 0.8, 0.6), pb=(240, 236, 226), lg=WHT, lw=.55, order='LTPF', ft='b', fcol=(210, 226, 236), fin=OLD, seed=1956)

# The Killing (1956): the poster's blue and black, its white THE KILLING lifted, Sterling Hayden with the rifle (director from IMDb)
std('the-killing-1956', ('grad', [(0, (40, 140, 180)), (.6, (16, 60, 80)), (1, (4, 16, 20))]), WHT,
    L([(0.395, 0.118, 0.545, 0.192), (0.395, 0.148, 0.955, 0.35)], 150, WHT, mode='key', key=(250, 250, 250), t=(60, 150), gapf=.2, speck=.02),
    photo=ph(0.3, 0.64, 0.56, 1.3), pb=WHT, lg=WHT, lw=.55, order='LPTCF', credit=['A STANLEY KUBRICK', 'FILM'], ccol=WHT,
    ft='c', fcol=(200, 220, 226), fin=OLD, seed=1956)

# The Man Who Knew Too Much (1956): the poster's white, its navy THE MAN WHO / KNEW TOO MUCH lifted in two lines, Stewart and Doris Day
MWB = dict(mode='key', key=(50, 70, 120), t=(70, 150), gapf=.25)
std('the-man-who-knew-too-much-1956', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 224)), (1, (150, 40, 50))]), (40, 60, 110),
    [L([(0.11, 0.634, 0.245, 0.672), (0.13, 0.674, 0.316, 0.717), (0.145, 0.718, 0.372, 0.764)], 60, (44, 64, 116), **MWB),
     L([(0.16, 0.766, 0.552, 0.831), (0.18, 0.83, 0.468, 0.895), (0.21, 0.895, 0.597, 0.96)], 60, (44, 64, 116), **MWB)],
    tgap=8, photo=ph(0.4, 0.17, 0.8, 0.7), pb=(200, 30, 40), lg=(40, 60, 110), lw=.55, order='LPTF', dotst=('THRILLER', (200, 30, 40), WHT),
    ft='d', fcol=(40, 60, 110), fin=OLD, seed=1956)

# The Searchers (1956): Monument Valley's red into dark, the poster's white italic THE SEARCHERS lifted, John Wayne under the hat
std('the-searchers-1956', ('grad', [(0, (60, 40, 30)), (.5, (180, 90, 40)), (1, (60, 24, 10))]), WHT,
    L((0.05, 0.088, 0.95, 0.146), 70, WHT, mode='light'),
    photo=ph(0.5, 0.52, 0.9, 0.9), pb=(240, 180, 90), lg=WHT, lw=.55, order='LPTSF', stick=BAR('71 4420', top='WESTERN', fill=(232, 220, 196)), ft='a', vbox=(240, 180, 90), vink=(60, 24, 10), fcol=(240, 220, 200), fin=RENTAL, seed=1956)

# The Swan (1956): the poster's pale gold, THE SWAN typeset in a serif like the poster's, its grey-green with the S in its tan (typeset: the poster's tall S is a faint tan on cream and drops out of every key, the rest picks up the hair behind it; three tried), Grace Kelly's face
std('the-swan-1956', ('grad', [(0, (236, 228, 200)), (.6, (220, 206, 170)), (1, (140, 120, 80))]), (110, 120, 100),
    TT([('THE ', (100, 116, 100)), ('S', (170, 140, 90)), ('WAN', (100, 116, 100))], 'terb', 84),
    photo=ph(0.45, 0.42, 0.66, 1.05), pb=(200, 150, 60), lg=(110, 100, 80), lw=.55, order='LPTF', ft='e', fcol=(100, 90, 70), fin=OLD, seed=1956)

# The Wrong Man (1956): the poster's white, The WRONG MAN typeset in heavy italic capitals in the poster's red (typeset: the poster's W is half-hidden by black smoke, so a cut reads RONG; two cuts tried), Henry Fonda under the hat (director from IMDb)
std('the-wrong-man-1956', ('grad', [(0, (246, 242, 234)), (.6, (226, 218, 204)), (1, (110, 70, 50))]), (220, 60, 60),
    TT([('The', (226, 70, 70)), ('WRONG MAN', (226, 70, 70))], 'intbki', 76, sp=.3, outline=((40, 20, 20), 1.6)),
    photo=ph(0.4, 0.25, 0.6, 1.1), pb=(220, 60, 60), lg=(40, 30, 26), lw=.55, order='LPTCF', credit=['DIRECTED BY', 'ALFRED HITCHCOCK'], ccol=(40, 30, 26),
    ft='b', fcol=(40, 30, 26), fin=OLD, seed=1956)

# Written on the Wind (1956): the poster's blue, its white script Written on the Wind lifted, Rock Hudson and Lauren Bacall's kiss (director from IMDb)
std('written-on-the-wind-1956', ('grad', [(0, (50, 80, 170)), (.6, (24, 36, 90)), (1, (6, 10, 30))]), WHT,
    L((0.02, 0.578, 0.655, 0.94), 130, WHT, mode='light'),
    photo=ph(0.5, 0.22, 0.9, 0.85), pb=(240, 200, 40), lg=WHT, lw=.55, order='LPTCF', credit=['A DOUGLAS SIRK', 'PICTURE'], ccol=WHT,
    ft='a', vbox=(240, 200, 40), vink=(24, 36, 90), fcol=(210, 216, 230), fin=OLD, seed=1956)

# 12 Angry Men (1957): the poster's white, its gold 12 and dark-red ANGRY MEN cut off it in their own colours, four of the jurors (no logo file: Orion-Nova Productions, from IMDb's company credits)
std('12-angry-men-1957', ('grad', [(0, (246, 244, 238)), (.6, (226, 222, 212)), (1, (150, 130, 110))]), (150, 30, 30),
    LC([(0.1, 0.51, 0.9, 0.566)], 80, cuts=[key_cut(lambda a: (_lum(a) < .75) & (_sat(a) > .3))]),
    photo=ph(0.5, 0.2, 1.0, 0.6), pb=(150, 30, 30), studio=['ORION-NOVA', 'PRODUCTIONS'], scol=(150, 30, 30), order='lPTF', ft='c', fcol=(60, 40, 30), fin=OLD, seed=1957)

# Nights of Cabiria (1957): black, the poster's white slab-serif Nights of Cabiria lifted, Giulietta Masina with the cigarette (no logo file: Dino de Laurentiis, from IMDb's company credits)
std('nights-of-cabiria-1957', ('grad', [(0, (40, 50, 56)), (.6, (12, 16, 18)), (1, (2, 2, 2))]), WHT,
    L((0.055, 0.288, 0.63, 0.45), 110, WHT, mode='light'),
    photo=ph(0.78, 0.6, 0.44, 1.5), pb=(240, 200, 120), studio=['DINO DE LAURENTIIS'], scol=WHT, order='lPTCSF', credit=['UN FILM DI', 'FEDERICO FELLINI'], ccol=WHT,
    stick=flow(dot, 74, ['DRAMA'], (200, 40, 50), WHT), ft='e', fcol=(200, 206, 210), fin=OLD, seed=1957)

# Paths of Glory (1957): the poster's pale blue, its red "PATHS OF GLORY" keyed off it, the officer leading the charge (director from IMDb)
std('paths-of-glory-1957', ('grad', [(0, (180, 220, 226)), (.6, (130, 180, 190)), (1, (40, 70, 76))]), (200, 40, 30),
    L((0.165, 0.88, 0.87, 0.944), 76, (204, 42, 32), mode='key', key=(200, 50, 40), t=(70, 150)),
    photo=ph(0.48, 0.38, 0.86, 1.25), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LTPF', ft='d', vbox=(204, 42, 32), fcol=(20, 20, 20), fin=OLD, seed=1957)

# The Lower Depths (1957): black, the poster's white THE LOWER (light serif) and DEPTHS (bold) set reading down it, cut off it and run in one line, the tenement faces (director from IMDb)
std('the-lower-depths-1957', ('grad', [(0, (44, 44, 44)), (.6, (14, 14, 14)), (1, (2, 2, 2))]), WHT,
    LC([(0.44, 0.38, 0.56, 0.93)], 110, cuts=[comp_cut(lambda a: _lum(a) > .7, rot=90, minf=.01)]),
    photo=ph(0.5, 0.18, 1.0, 0.55), pb=WHT, lg=WHT, lw=.55, order='LPTCF', credit=['AKIRA KUROSAWA'], ccol=WHT,
    ft='b', fcol=(200, 200, 200), fin=OLD, seed=1957)

# The Seventh Seal (1957): black, the poster's thin spaced THE SEVENTH SEAL lifted, Max von Sydow's face (director from IMDb)
std('the-seventh-seal-1957', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), (220, 220, 216),
    L((0.07, 0.79, 0.93, 0.83), 50, (226, 226, 222), mode='light', speck=0),
    photo=ph(0.6, 0.32, 0.6, 1.5), pb=(226, 226, 222), lg=(226, 226, 222), lw=.55, order='LPTCF', credit=['EN FILM AV', 'INGMAR BERGMAN'], ccol=(226, 226, 222),
    ft='a', fcol=(190, 190, 186), fin=OLD, seed=1957)

# Throne of Blood (1957): the fog's white, the poster's red serif THRONE OF BLOOD keyed off it, Washizu pinned with arrows under the title
std('throne-of-blood-1957', ('grad', [(0, (236, 236, 234)), (.6, (210, 210, 206)), (1, (100, 100, 96))]), (200, 20, 30),
    L([(0.13, 0.318, 0.87, 0.404), (0.425, 0.402, 0.585, 0.458), (0.21, 0.458, 0.81, 0.544)], 76, (204, 22, 32), mode='key', key=(190, 30, 40), t=(70, 150), gapf=.25),
    photo=ph(0.5, 0.76, 0.8, 0.7), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LTPF', ft='e', vbox=(204, 22, 32), fcol=(20, 20, 20), fin=OLD, seed=1957)

# Wild Strawberries (1957): the poster's white, its grey WILD and maroon STRAWBERRIES cut off it in their own colours, Victor Sjöström under the tree
std('wild-strawberries-1957', ('grad', [(0, (244, 244, 242)), (.6, (222, 222, 218)), (1, (130, 130, 126))]), (30, 30, 30),
    LC([(0.36, 0.452, 0.975, 0.5)], 70, cuts=[comp_cut(lambda a: _lum(a) < .62, keep=lambda x, y: y > .3, minf=.05)]),
    photo=ph(0.62, 0.72, 0.6, 1.1), pb=(30, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTSF', stick=PRC(['$1.99', 'FOREIGN']),
    ft='c', fcol=(30, 30, 30), fin=RENTAL, seed=1957)

# Witness for the Prosecution (1957): the poster's red, its cream WITNESS FOR THE PROSECUTION keyed off it, the courtroom figure with the monocle (no logo file: Edward Small Productions, from IMDb's company credits)
std('witness-for-the-prosecution-1957', ('grad', [(0, (200, 50, 40)), (.6, (140, 30, 24)), (1, (50, 10, 6))]), (250, 240, 170),
    [L((0.03, 0.795, 1.0, 0.848), 54, (252, 242, 172), mode='key', key=(250, 240, 170), t=(70, 150)), L((0.205, 0.846, 0.96, 0.91), 54, (252, 242, 172), mode='key', key=(250, 240, 170), t=(70, 150))],
    tgap=8, photo=ph(0.55, 0.42, 0.9, 0.8), pb=(250, 240, 170), studio=['EDWARD SMALL', 'PRODUCTIONS'], scol=(250, 240, 170), order='lPTCF',
    credit=['A BILLY WILDER', 'FILM'], ccol=(250, 240, 170), ft='b', fcol=(240, 220, 200), fin=OLD, seed=1957)

# Big Deal on Madonna Street (1958): the poster's yellow, its navy BIG DEAL ON and maroon MADONNA STREET cut off it in their own colours, the gang drawn under it (no logo file: Lux Film, from IMDb's company credits)
std('big-deal-on-madonna-street-1958', ('grad', [(0, (250, 230, 60)), (.6, (236, 206, 30)), (1, (160, 130, 10))]), (120, 40, 50),
    LC([(0.05, 0.25, 0.94, 0.33), (0.05, 0.345, 0.95, 0.45), (0.005, 0.465, 0.955, 0.56)], 80, gapf=.2, valign='base', cuts=[key_cut(lambda a: _lum(a) < .55)] * 3),
    photo=ph(0.5, 0.78, 1.0, 0.6), pb=(120, 40, 50), studio=['LUX FILM'], scol=(40, 40, 90), order='lTPF', ft='a', vbox=(120, 40, 50), fcol=(40, 40, 90), fin=OLD, seed=1958)

# Elevator to the Gallows (1958): the poster's white, its black ELEVATOR and GALLOWS (the small TO THE set sideways between them) cut off it, Jeanne Moreau in blue (no logo file: NEF, from IMDb's company credits)
std('elevator-to-the-gallows-1958', ('grad', [(0, (246, 246, 246)), (.6, (224, 226, 228)), (1, (60, 100, 140))]), (20, 20, 20),
    LC([(0.145, 0.298, 0.975, 0.362), (0.145, 0.362, 0.975, 0.428)], 80, gapf=.2, valign='base', margin=0, cuts=[comp_cut(lambda a: _lum(a) < .3, keep=lambda x, y: x > .05, minf=.05)] * 2),
    photo=ph(0.6, 0.7, 0.8, 0.85), pb=(40, 90, 140), studio=['NEF'], scol=(20, 20, 20), order='lPTCF', credit=['UN FILM DE', 'LOUIS MALLE'], ccol=(20, 20, 20),
    ft='d', fcol=(20, 20, 20), fin=OLD, seed=1958)

# Ivan the Terrible, Part II (1958): the poster's dusky rose, its pink-red IVAN the TERRIBLE and tan PART II cut off it in their own colours, the tsar's face
std('ivan-the-terrible-part-ii-the-boyars-plot-1958', ('grad', [(0, (180, 120, 120)), (.6, (100, 60, 60)), (1, (30, 14, 14))]), (210, 50, 50),
    [LC([(0.02, 0.03, 0.335, 0.165), (0.33, 0.07, 0.44, 0.125), (0.43, 0.03, 0.98, 0.165)], 76, gapf=.14, valign='mid', cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 0] > a[..., 1] + .25)) | ((a[..., 0] > .75) & (a[..., 1] > .62) & (a[..., 0] - a[..., 1] < .2) & (a[..., 0] > a[..., 2] + .1)), minf=.03)] * 3),
     LC([(0.36, 0.155, 0.64, 0.215)], 34, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 0] > a[..., 2] + .15) & (a[..., 1] > .45), minf=.05)])],
    tgap=8, photo=ph(0.55, 0.6, 0.8, 1.0), pb=(214, 54, 54), lg=(230, 210, 200), lw=.5, order='LPTCF', credit=['SERGEI EISENSTEIN'], ccol=(230, 210, 200),
    ft='e', fcol=(220, 200, 196), fin=OLD, seed=1958)

# Mon Oncle (1958): the poster's cream, its black hand-lettered MON ONCLE lifted, Hulot tangled in the red ribbon (director from IMDb)
std('mon-oncle-1958', ('grad', [(0, (244, 238, 222)), (.6, (230, 220, 196)), (1, (160, 140, 110))]), (24, 24, 24),
    L([(0.545, 0.016, 0.79, 0.117), (0.63, 0.116, 0.95, 0.2)], 90, (24, 24, 24), mode='dark', gapf=.3),
    photo=ph(0.5, 0.55, 0.9, 1.1), pb=(220, 40, 40), lg=(24, 24, 24), lw=.55, order='LTPF', dotst=('COMEDY', (220, 40, 40), WHT), ft='b', fcol=(24, 24, 24), fin=OLD, seed=1958)

# The Blob (1958): the drive-in night's dark red, the poster's red dripping THE BLOB cut off it in its own colours, Steve McQueen on the phone (no logo file: Tonylyn Productions, from IMDb's company credits)
std('the-blob-1958', ('grad', [(0, (60, 20, 40)), (.6, (24, 6, 14)), (1, (4, 2, 4))]), (220, 40, 50),
    LC([(0.0, 0.13, 0.95, 0.36)], 120, cuts=[comp_cut(lambda a: (a[..., 0] > .5) & (a[..., 0] > a[..., 1] + .3) & (a[..., 0] > a[..., 2] + .2), minf=.05)]),
    photo=ph(0.35, 0.55, 0.7, 1.0), pb=(250, 220, 40), studio=['TONYLYN', 'PRODUCTIONS'], scol=(220, 200, 200), order='lPTSF', stick=flow(dot, 74, ['SCI-FI'], (250, 220, 40), (24, 6, 14)), ft='c', fcol=(200, 180, 186), fin=RENTAL, seed=1958)

# The Hidden Fortress (1958): the poster's paper cream, its black serif THE HIDDEN FORTRESS lifted, Mifune in the woods (director from IMDb)
std('the-hidden-fortress-1958', ('grad', [(0, (238, 232, 216)), (.6, (220, 212, 192)), (1, (130, 120, 100))]), (24, 24, 24),
    L([(0.44, 0.835, 0.58, 0.856), (0.31, 0.856, 0.72, 0.91), (0.265, 0.908, 0.765, 0.968)], 80, (24, 24, 24), mode='dark', gapf=.25),
    photo=ph(0.5, 0.35, 0.8, 1.05), pb=(24, 24, 24), lg=(24, 24, 24), lw=.55, order='LPTCF', credit=['A FILM BY', 'AKIRA KUROSAWA'], ccol=(24, 24, 24),
    ft='d', fcol=(24, 24, 24), fin=OLD, seed=1958)

# The Horse's Mouth (1958): the poster's white, its cyan THE HORSE'S MOUTH cut off it in its own colours, Alec Guinness among the painted figures (no logo file: Knightsbridge Films, from IMDb's company credits)
std('the-horse-s-mouth-1958', ('grad', [(0, (246, 248, 250)), (.6, (220, 230, 240)), (1, (40, 70, 150))]), (30, 190, 220),
    LC([(0.4, 0.36, 0.98, 0.58)], 110, cuts=[comp_cut(lambda a: (a[..., 1] > .5) & (a[..., 2] > .6) & (a[..., 0] < .55) & (a[..., 2] > a[..., 0] + .2), minf=.01)]),
    photo=ph(0.45, 0.22, 0.5, 0.8), pb=(220, 30, 60), studio=['KNIGHTSBRIDGE FILMS'], scol=(40, 70, 150), order='lPTF', ft='e', fcol=(40, 70, 150), fin=OLD, seed=1958)

# Touch of Evil (1958): the poster's orange, its cream ragged Touch of Evil cut off it in its own colours, Welles under the hat (director from IMDb)
std('touch-of-evil-1958', ('grad', [(0, (240, 110, 40)), (.6, (200, 80, 24)), (1, (90, 30, 8))]), (246, 236, 210),
    LC([(0.14, 0.3, 0.79, 0.68)], 130, cuts=[comp_cut(lambda a: (_lum(a) > .75) & (_sat(a) < .3), minf=.04)]),
    photo=ph(0.48, 0.19, 0.36, 0.95), pb=(246, 236, 210), lg=(246, 236, 210), lw=.55, order='LPTF', ft='b', fcol=(250, 220, 200), fin=OLD, seed=1958)

# Vertigo (1958): the poster's red-orange, its black VERTIGO lifted, the spiral with the falling figures
std('vertigo-1958', ('grad', [(0, (230, 76, 40)), (.6, (190, 50, 24)), (1, (80, 18, 8))]), (20, 16, 14),
    L((0.04, 0.826, 0.955, 0.916), 90, (20, 16, 14), mode='dark'),
    photo=ph(0.5, 0.38, 0.86, 0.9), pb=(20, 16, 14), lg=(20, 16, 14), lw=.55, order='LPTF', ft='a', vbox=(20, 16, 14), fcol=(30, 20, 16), fin=OLD, seed=1958)

# Anatomy of a Murder (1959): black, the poster's white ANATOMY OF A and the big broken MURDER lifted, James Stewart (no logo file: Otto Preminger Films, from IMDb's company credits)
std('anatomy-of-a-murder-1959', ('grad', [(0, (60, 20, 14)), (.6, (18, 6, 4)), (1, (2, 2, 2))]), WHT,
    L([(0.095, 0.77, 0.62, 0.827), (0.29, 0.825, 0.9, 0.935)], 96, WHT, mode='light', gapf=.2),
    photo=ph(0.65, 0.35, 0.7, 1.1), pb=(214, 60, 40), studio=['OTTO PREMINGER', 'FILMS'], scol=WHT, order='lPTCSF', credit=['JAMES STEWART', 'LEE REMICK'], ccol=WHT,
    stick=PRC(['$2.99', 'DRAMA']), ft='d', fcol=(210, 200, 196), fin=RENTAL, seed=1959)

# North by Northwest (1959): the poster's red, its cream NORTH BY NORTHWEST and the arrow cut off it in its own colours and levelled (it climbs 12 degrees), Cary Grant running from the plane
std('north-by-northwest-1959', ('grad', [(0, (200, 60, 40)), (.6, (150, 36, 24)), (1, (60, 14, 8))]), (240, 230, 220),
    LC([(0.08, 0.53, 0.92, 0.72)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .6) & (_sat(a) < .35), keep=lambda x, y: y < .85, rot=-12, minf=.05)]),
    photo=ph(0.48, 0.25, 0.9, 0.8), pb=(240, 230, 220), lg=(240, 230, 220), lw=.55, order='LTPF', ft='c', vbox=(240, 230, 220), vink=(150, 36, 24), fcol=(240, 220, 210), fin=OLD, seed=1959)

# Sleeping Beauty (1959): Disney, the white clamshell; the poster's violet, its gold script Sleeping Beauty cut off the blue shield, Aurora's face in the red diamond
disney('sleeping-beauty-1959', ('grad', [(0, (60, 40, 120)), (.5, (100, 60, 160)), (1, (30, 20, 60))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.305, 0.505, 0.69, 0.592), (0.33, 0.588, 0.665, 0.66)], 110, gapf=.2, valign='base', margin=0, outline=((40, 24, 10), 2),
                cuts=[comp_cut(lambda a: (a[..., 0] > a[..., 2] + .1) & (_lum(a) > .35), keep=lambda x, y: .02 < x < .98, minf=.01)] * 2),
       face=ph(.38, .22, .2, 1.4), lcol=WHT)

# Some Like It Hot (1959): the poster's white, its red SOME LIKE IT HOT in its black keyline cut off it in its own colours, Marilyn and the two "girls" (no logo file: The Mirisch Corporation, from IMDb's company credits)
std('some-like-it-hot-1959', ('grad', [(0, (246, 246, 244)), (.6, (228, 228, 224)), (1, (150, 150, 146))]), (220, 30, 40),
    LC([(0.065, 0.395, 0.94, 0.47)], 80, cuts=[key_cut(lambda a: ((a[..., 0] > .8) & (a[..., 1] < .4)) | (_lum(a) < .25))]),
    photo=ph(0.5, 0.2, 0.86, 0.55), pb=(30, 140, 100), studio=['THE MIRISCH', 'CORPORATION'], scol=(20, 20, 20), order='lPTCF', credit=['A BILLY WILDER', 'PRODUCTION'],
    ccol=(20, 20, 20), ft='a', vbox=(220, 30, 40), fcol=(20, 20, 20), fin=OLD, seed=1959)

# The 400 Blows (1959): black, the poster's white the 400 blows lifted, Antoine behind the wire (director from IMDb)
std('the-400-blows-1959', ('grad', [(0, (60, 60, 60)), (.6, (18, 18, 18)), (1, (4, 4, 4))]), WHT,
    LC([(0.635, 0.605, 0.97, 0.698), (0.4, 0.698, 0.97, 0.814), (0.4, 0.814, 0.97, 0.903)], 120, gapf=.2, valign='base', margin=0, cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.12)] * 3),
    photo=ph(0.4, 0.25, 0.8, 0.75), pb=WHT, lg=WHT, lw=.55, order='LPTCF', credit=['UN FILM DE', 'FRANÇOIS TRUFFAUT'], ccol=WHT,
    ft='e', fcol=(200, 200, 200), fin=OLD, seed=1959)

# The Human Condition I: No Greater Love (1959): a 2-tape box; the poster's peach, its black THE HUMAN CONDITION and Part I cut off it and run in one line, Nakadai's face (no logo file: Bungei Production Ninjin Club, from IMDb's company credits)
std('the-human-condition-i-no-greater-love-1959', ('grad', [(0, (250, 226, 200)), (.6, (236, 206, 176)), (1, (150, 120, 90))]), (30, 26, 24),
    LC([(0.055, 0.15, 0.4, 0.185), (0.055, 0.187, 0.375, 0.222), (0.055, 0.224, 0.18, 0.25)], 80, gapf=.4, valign='base', margin=0, cuts=[key_cut(lambda a: _lum(a) < .35)] * 3),
    photo=ph(0.6, 0.6, 0.8, 1.0), pb=(30, 26, 24), studio=['BUNGEI PRODUCTION', 'NINJIN CLUB'], scol=(30, 26, 24), order='lTPCSF', credit=['NO GREATER LOVE'],
    ccol=(30, 26, 24), stick=TWOST((30, 26, 24), (250, 226, 200)), ft='b', fcol=(30, 26, 24), fin=OLD, seed=1959, **TWO)

# The Human Condition II: Road to Eternity (1959): the poster's peach, its black THE HUMAN CONDITION and Part II cut off it and run in one line, the soldier with the gun (director from IMDb)
std('the-human-condition-ii-road-to-eternity-1959', ('grad', [(0, (250, 226, 200)), (.6, (236, 206, 176)), (1, (150, 120, 90))]), (30, 26, 24),
    LC([(0.06, 0.066, 0.47, 0.101), (0.06, 0.107, 0.45, 0.143), (0.06, 0.154, 0.21, 0.184)], 80, gapf=.7, valign='base', margin=0, cuts=[key_cut(lambda a: _lum(a) < .35)] * 3),
    photo=ph(0.55, 0.6, 0.86, 1.15), pb=(30, 26, 24), lg=None, studio=['A MASAKI KOBAYASHI', 'FILM'], scol=(30, 26, 24), order='TPlF',
    ft='c', fcol=(30, 26, 24), fin=OLD, seed=1959)


# =====================================================================================
# 1960s (vault-1960s.json, 82 tapes)
# =====================================================================================

# Breathless (1960): the poster's red and teal circles, its black stencil BREATHLESS lifted, Belmondo and Seberg (no logo file: Les Films Impéria, from IMDb's company credits; director from IMDb)
std('breathless-1960', ('grad', [(0, (230, 100, 100)), (.5, (110, 190, 180)), (1, (40, 90, 84))]), (20, 20, 20),
    L((0.025, 0.2, 0.965, 0.296), 80, (20, 20, 20), mode='dark'),
    photo=ph(0.5, 0.6, 1.0, 0.8), pb=(20, 20, 20), studio=['LES FILMS IMPÉRIA'], scol=(20, 20, 20), order='lPTCF', credit=['UN FILM DE', 'JEAN-LUC GODARD'],
    ccol=(20, 20, 20), ft='b', fcol=(20, 20, 20), fin=OLD, seed=1960)

# La Dolce Vita (1960): the fountain's grey, the poster's gold serif LA DOLCE VITA keyed off it in its three lines, the kiss in the Trevi
std('la-dolce-vita-1960', ('grad', [(0, (110, 110, 108)), (.6, (40, 40, 40)), (1, (8, 8, 8))]), (240, 200, 80),
    L([(0.375, 0.352, 0.62, 0.438), (0.17, 0.449, 0.816, 0.537), (0.278, 0.546, 0.713, 0.632)], 76, (242, 204, 84), mode='key', key=(235, 195, 80), t=(70, 150), gapf=.3),
    photo=ph(0.58, 0.82, 0.6, 0.85), pb=(242, 204, 84), lg=(242, 204, 84), lw=.55, order='LTPF', ft='a', vbox=(242, 204, 84), vink=(40, 40, 40), fcol=(200, 196, 190), fin=OLD, seed=1960)

# Le Trou (1960): black, the poster's yellow LE TROU with its glass-bubble O cut off it in its own colours, the two prisoners' faces (director from IMDb)
std('le-trou-1960', ('grad', [(0, (50, 50, 50)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), (250, 236, 20),
    LC([(0.035, 0.632, 0.96, 0.796)], 120, cuts=[key_cut(lambda a: ((a[..., 0] > .8) & (a[..., 1] > .75) & (a[..., 2] < .45)) | ((a[..., 2] > .7) & (a[..., 0] < .5)) | (_lum(a) > .75))]),
    photo=ph(0.5, 0.25, 1.0, 0.75), pb=(250, 236, 20), lg=(250, 236, 20), lw=.55, order='LPTCF', credit=['UN FILM DE', 'JACQUES BECKER'], ccol=(250, 236, 20),
    ft='c', fcol=(200, 200, 196), fin=OLD, seed=1960)

# Our Man in Havana (1960): the poster's blue and orange, its white stacked OUR MAN IN HAVANA lifted word by word into one line, Alec Guinness (no logo file: Kingsmead Productions, from IMDb's company credits)
std('our-man-in-havana-1960', ('grad', [(0, (40, 110, 160)), (.6, (20, 60, 96)), (1, (6, 20, 34))]), WHT,
    LC([(0.245, 0.08, 0.465, 0.185), (0.21, 0.186, 0.465, 0.292), (0.355, 0.293, 0.465, 0.399), (0.022, 0.4, 0.465, 0.505)], 90, gapf=.22, valign='base', margin=0, cuts=[comp_cut(lambda a: (_lum(a) > .8) & (_sat(a) < .2), minf=.1)] * 4),
    photo=ph(0.72, 0.75, 0.56, 1.0), pb=(250, 160, 50), studio=['KINGSMEAD', 'PRODUCTIONS'], scol=WHT, order='lPTSF', stick=RWD(fill=(250, 230, 190)),
    ft='e', fcol=(210, 220, 230), fin=RENTAL, seed=1960)

# Peeping Tom (1960): the poster's paper white, its orange-red PEEPING TOM keyed off it, the camera (no logo file: Michael Powell (Theatre), from IMDb's company credits)
std('peeping-tom-1960', ('grad', [(0, (240, 236, 226)), (.6, (222, 216, 202)), (1, (140, 130, 110))]), (220, 80, 40),
    L([(0.04, 0.11, 0.68, 0.172), (0.032, 0.17, 0.38, 0.232)], 80, (224, 82, 42), mode='key', key=(220, 85, 45), t=(70, 150), gapf=.3),
    photo=ph(0.6, 0.55, 0.62, 1.0), pb=(30, 30, 30), studio=['MICHAEL POWELL', '(THEATRE)'], scol=(30, 30, 30), order='lPTF', ft='d', fcol=(30, 30, 30), fin=OLD, seed=1960)

# Psycho (1960): the poster's dark blue, its yellow PSYCHO cut off it in its own colours, Janet Leigh and Anthony Perkins' hands (no logo file: Alfred J. Hitchcock Productions, from IMDb's company credits)
std('psycho-1960', ('grad', [(0, (30, 44, 70)), (.6, (12, 16, 28)), (1, (2, 4, 8))]), (250, 220, 70),
    LC([(0.05, 0.148, 0.625, 0.328)], 120, cuts=[key_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .5) & (a[..., 2] < .45))]),
    photo=ph(0.8, 0.3, 0.36, 1.4), pb=(250, 220, 70), studio=['ALFRED J. HITCHCOCK', 'PRODUCTIONS'], scol=(250, 220, 70), order='lPTSF',
    stick=flow(dot, 74, ['HORROR'], (220, 40, 40), WHT), ft='a', vbox=(250, 220, 70), vink=(12, 16, 28), fcol=(200, 204, 214), fin=RENTAL, seed=1960)

# Shoot the Piano Player (1960): the poster's sepia, its red brush SHOOT THE PIANO PLAYER cut off it in its own colours, three lines into one, Aznavour at the piano (no logo file: Les Films de la Pléiade, from IMDb's company credits)
std('shoot-the-piano-player-1960', ('grad', [(0, (230, 200, 160)), (.6, (190, 150, 110)), (1, (90, 60, 40))]), (180, 30, 30),
    LC([(0.118, 0.562, 0.53, 0.678), (0.055, 0.68, 0.598, 0.775), (0.118, 0.782, 0.528, 0.885)], 80, gapf=.25, valign='base', cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 0] > a[..., 1] + .25) & (a[..., 0] > a[..., 2] + .2), minf=.04)] * 3),
    photo=ph(0.45, 0.2, 0.86, 0.75), pb=(186, 32, 32), studio=['LES FILMS', 'DE LA PLÉIADE'], scol=(60, 40, 30), order='lPTCF', credit=['UN FILM DE', 'FRANÇOIS TRUFFAUT'],
    ccol=(60, 40, 30), ft='b', fcol=(60, 40, 30), fin=OLD, seed=1960)

# Spartacus (1960): the poster's red, its white jagged SPARTACUS cut off it, the gladiator with the net
std('spartacus-1960', ('grad', [(0, (226, 30, 30)), (.6, (160, 16, 16)), (1, (60, 4, 4))]), WHT,
    LC([(0.07, 0.115, 0.945, 0.255)], 90, cuts=[comp_cut(lambda a: _lum(a) > .8, minf=.05)]),
    photo=ph(0.45, 0.62, 0.8, 0.9), pb=WHT, lg=WHT, lw=.55, order='LPTF', ft='d', fcol=(240, 210, 210), fin=OLD, seed=1960)

# The Apartment (1960): the poster's red, its white THE APARTMENT lifted, Lemmon and MacLaine dancing (no logo file: The Mirisch Corporation, from IMDb's company credits)
std('the-apartment-1960', ('grad', [(0, (226, 30, 24)), (.6, (170, 16, 14)), (1, (60, 4, 4))]), WHT,
    L((0.205, 0.338, 0.955, 0.396), 70, WHT, mode='light'),
    photo=ph(0.63, 0.15, 0.4, 1.15), pb=WHT, studio=['THE MIRISCH', 'CORPORATION'], scol=WHT, order='lPTCF', credit=['A BILLY WILDER', 'PRODUCTION'], ccol=WHT,
    dotst=('COMEDY', WHT, (170, 16, 14)), ft='e', fcol=(240, 210, 210), fin=OLD, seed=1960)

# The Bad Sleep Well (1960): black, the poster's white THE SLEEP WELL and red BAD cut off it in their own colours, the office block with the red cross (director from IMDb)
std('the-bad-sleep-well-1960', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.018, 0.17, 0.98, 0.285)], 80, cuts=[key_cut(lambda a: (_lum(a) > .8) | ((a[..., 0] > .6) & (a[..., 1] < .3)))]),
    photo=ph(0.5, 0.66, 1.0, 0.6), pb=(214, 30, 40), lg=WHT, lw=.55, order='LTPF', ft='a', fcol=(200, 200, 200), fin=OLD, seed=1960)

# Tunes of Glory (1960): the poster's cream, its black TUNES and OF GLORY cut off it letter by letter and levelled (they climb 16 degrees), Alec Guinness's face (no logo file: Knightsbridge Films, from IMDb's company credits)
TGB = lambda a: _lum(a) < .25
std('tunes-of-glory-1960', ('grad', [(0, (248, 240, 200)), (.6, (232, 220, 170)), (1, (150, 130, 90))]), (24, 24, 24),
    LC([(0.02, 0.08, 0.48, 0.24), (0.08, 0.1, 0.76, 0.3)], 90, gapf=.2, valign='base', cuts=[
        pick_cut(TGB, (0.02, 0.08, 0.48, 0.24), [(0.065, 0.187), (0.148, 0.179), (0.24, 0.159), (0.324, 0.141), (0.41, 0.124)], rot=-16, r=.02),
        pick_cut(TGB, (0.08, 0.1, 0.76, 0.3), [(0.14, 0.244), (0.222, 0.223), (0.354, 0.202), (0.428, 0.192), (0.522, 0.167), (0.614, 0.147), (0.698, 0.126)], rot=-16, r=.02)]),
    photo=ph(0.72, 0.5, 0.56, 1.1), pb=(24, 24, 24), studio=['KNIGHTSBRIDGE FILMS'], scol=(24, 24, 24), order='lPTCF', credit=['ALEC GUINNESS', 'JOHN MILLS'],
    ccol=(24, 24, 24), ft='c', fcol=(24, 24, 24), fin=OLD, seed=1960)

# Breakfast at Tiffany's (1961): the poster's white, its magenta BREAKFAST AT TIFFANY'S cut off it in its own colours, Audrey Hepburn in the black dress (tall picture)
std('breakfast-at-tiffany-s-1961', ('grad', [(0, (246, 244, 242)), (.6, (226, 224, 222)), (1, (130, 170, 200))]), (210, 30, 110),
    LC([(0.395, 0.625, 0.91, 0.704), (0.395, 0.703, 0.9, 0.782)], 80, gapf=.2, valign='base', cuts=[key_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .4) & (a[..., 2] > .3))] * 2),
    photo=ph(0.24, 0.42, 0.34, 1.9), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF', ft='b', fcol=(20, 20, 20), fin=OLD, seed=1961)

# Il Posto (1961): the poster's cream, its white ERMANNO OLMI'S and yellow IL POSTO cut off it in their own colours, Domenico at the desk
std('il-posto-1961', ('grad', [(0, (238, 232, 216)), (.6, (220, 210, 190)), (1, (130, 120, 100))]), (40, 40, 40),
    LC([(0.05, 0.415, 0.545, 0.49)], 90, cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .4))]),
    photo=ph(0.55, 0.72, 0.86, 0.55), pb=(230, 190, 40), lg=(40, 40, 40), lw=.55, order='LTPF', ft='d', fcol=(40, 40, 40), fin=OLD, seed=1961)

# One Hundred and One Dalmatians (1961): Disney, the white clamshell; the poster's sky blue, its white-and-gold 101 DALMATIANS cut off the red banner and edged in its red, Pongo's face in the red diamond
disney('one-hundred-and-one-dalmatians-1961', ('grad', [(0, (40, 90, 170)), (.5, (70, 130, 200)), (1, (30, 60, 110))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.2, 0.44, 0.75, 0.572), (0.185, 0.566, 0.78, 0.608)], 150, gapf=.25, valign='base', margin=0, outline=((180, 20, 24), 3),
                cuts=[comp_cut(lambda a: (_lum(a) > .55) & (a[..., 1] > a[..., 0] - .25), minf=.05), comp_cut(lambda a: (_lum(a) > .7) & (_sat(a) < .3), minf=.25)]),
       face=ph(.63, .2, .3, 1.4), lcol=WHT)

# The Human Condition III: A Soldier's Prayer (1961): the poster's pink-white, its black THE HUMAN CONDITION and Part III cut off it and run in one line, Nakadai in the snow (no logo file: Toho, from IMDb's company credits)
std('the-human-condition-iii-a-soldier-s-prayer-1961', ('grad', [(0, (250, 236, 232)), (.6, (230, 216, 212)), (1, (60, 120, 150))]), (30, 26, 24),
    LC([(0.06, 0.066, 0.47, 0.101), (0.06, 0.107, 0.45, 0.143), (0.06, 0.154, 0.22, 0.184)], 80, gapf=.7, valign='base', margin=0, cuts=[key_cut(lambda a: _lum(a) < .35)] * 3),
    photo=ph(0.6, 0.6, 0.8, 1.15), pb=(40, 110, 140), studio=['TOHO'], scol=(30, 26, 24), order='lTPCF', credit=["A SOLDIER'S PRAYER"],
    ccol=(30, 26, 24), ft='a', vbox=(40, 110, 140), fcol=(30, 26, 24), fin=OLD, seed=1961)

# The Hustler (1961): the poster's lime green, its black THE HUSTLER lifted, Paul Newman in the circle with the cue (director from IMDb)
std('the-hustler-1961', ('grad', [(0, (200, 220, 60)), (.6, (150, 180, 30)), (1, (60, 80, 10))]), (20, 20, 20),
    L([(0.695, 0.393, 0.866, 0.453), (0.58, 0.45, 0.982, 0.522)], 80, (20, 20, 20), mode='dark', gapf=.25),
    photo=ph(0.7, 0.75, 0.5, 1.0), pb=(214, 40, 40), lg=(20, 20, 20), lw=.55, order='LPTF', ft='e', fcol=(20, 20, 20), fin=OLD, seed=1961)

# The Shadow of the Cat (1961): the poster's teal and black, its yellow THE SHADOW OF THE CAT cut off it in its own colours and levelled, the cat's eyes from the top of the poster
std('the-shadow-of-the-cat-1961', ('grad', [(0, (30, 110, 120)), (.6, (12, 50, 56)), (1, (2, 14, 16))]), (250, 230, 40),
    LC([(0.04, 0.63, 0.83, 0.89)], 110, outline=((10, 10, 10), 2), cuts=[comp_cut(lambda a: (a[..., 0] > .8) & (a[..., 1] > .75) & (a[..., 2] < .45), rot=-12, minf=.02)]),
    photo=ph(0.4, 0.18, 0.7, 0.85), pb=(250, 230, 40), lg=WHT, lw=.55, order='LPTSF', stick=BAR('61 2210', top='HORROR', fill=(232, 228, 200)),
    ft='c', fcol=(200, 220, 220), fin=RENTAL, seed=1961)

# Viridiana (1961): the poster's tan, its cream serif VIRIDIANA cut off it, Silvia Pinal's face under the veil (no logo file in type: Films 59; director from IMDb)
std('viridiana-1961', ('grad', [(0, (220, 170, 120)), (.6, (170, 120, 80)), (1, (60, 40, 24))]), (250, 236, 210),
    LC([(0.03, 0.64, 0.92, 0.722)], 76, cuts=[comp_cut(lambda a: (_lum(a) > .72) & (a[..., 0] > a[..., 2] + .02), keep=lambda x, y: x > .03, minf=.1)]),
    photo=ph(0.6, 0.27, 0.6, 1.2), pb=(30, 26, 24), lg=(250, 236, 210), lw=.55, order='LPTCF', credit=['UNA PELÍCULA DE', 'LUIS BUÑUEL'], ccol=(250, 236, 210),
    ft='b', fcol=(230, 210, 190), fin=OLD, seed=1961)

# West Side Story (1961): the poster's red, its black distressed WEST SIDE STORY lifted word by word into one line, the dancers on the fire escape
std('west-side-story-1961', ('grad', [(0, (230, 40, 30)), (.6, (180, 24, 18)), (1, (70, 8, 6))]), (20, 16, 14),
    L([(0.075, 0.195, 0.67, 0.393), (0.078, 0.393, 0.6, 0.59), (0.078, 0.59, 0.73, 0.8)], 110, (20, 16, 14), mode='dark', gapf=.2),
    photo=ph(0.8, 0.53, 0.38, 1.3), pb=WHT, lg=(20, 16, 14), lw=.55, order='LPTF', dotst=('MUSICAL', WHT, (180, 24, 18)),
    ft='a', vbox=(20, 16, 14), fcol=(40, 20, 16), fin=OLD, seed=1961)

# Yojimbo (1961): the poster's smoky gold, its white YOJIMBO lifted, Mifune under the sword (director from IMDb)
std('yojimbo-1961', ('grad', [(0, (150, 110, 40)), (.6, (60, 44, 20)), (1, (10, 8, 4))]), WHT,
    L((0.255, 0.606, 0.745, 0.656), 70, WHT, mode='light'),
    photo=ph(0.35, 0.3, 0.6, 1.2), pb=(240, 190, 60), lg=WHT, lw=.55, order='LPTF', ft='d', fcol=(220, 210, 190), fin=OLD, seed=1961)

# Carnival of Souls (1962): the poster's carnival colours, its red CARNIVAL rebuilt letter by letter off its arc, the black OF and yellow SOULS cut off it in their own colours, the screaming woman (no logo file: Harcourt Productions, from IMDb's company credits)
CSR = lambda a: (a[..., 0] > .7) & (a[..., 1] < .4) & (a[..., 2] < .4)
std('carnival-of-souls-1962', ('grad', [(0, (80, 50, 120)), (.6, (40, 20, 70)), (1, (10, 4, 20))]), (230, 50, 40),
    LC([(0.25, 0.3, 0.95, 0.63), (0.51, 0.558, 0.655, 0.652), (0.42, 0.62, 0.94, 0.81)], 90, gapf=.15, valign='base', cuts=[
        seq_cut(CSR, (0.25, 0.3, 0.95, 0.63), [(0.316, 0.401), (0.419, 0.387), (0.513, 0.398), (0.612, 0.43), (0.672, 0.47), (0.73, 0.499), (0.817, 0.53), (0.875, 0.568)], gapf=.06),
        comp_cut(lambda a: _lum(a) < .22, minf=.2),
        comp_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .75) & (a[..., 2] < .4), rot=8, minf=.05)]),
    photo=ph(0.7, 0.15, 0.6, 0.85), pb=(250, 220, 60), studio=['HARCOURT', 'PRODUCTIONS'], scol=(250, 220, 60), order='lPTCSF', credit=['A FILM BY', 'HERK HARVEY'],
    ccol=(250, 220, 60), stick=PRC(['$0.99', 'HORROR']), ft='e', fcol=(210, 200, 220), fin=RENTAL, seed=1962)

# Harakiri (1962): the poster's white, its black HARA KIRI with the red slash through it cut off it in its own colours, the red blade from the poster (director and star from IMDb)
std('harakiri-1962', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (130, 130, 126))]), (20, 20, 20),
    LC([(0.25, 0.47, 0.88, 0.69), (0.28, 0.7, 0.83, 0.87)], 100, gapf=.2, valign='base', margin=0, cuts=[key_cut(lambda a: (_lum(a) < .3) | ((a[..., 0] > .7) & (a[..., 1] < .3)))] * 2),
    photo=ph(0.5, 0.2, 0.5, 0.9), pb=(200, 20, 30), lg=(20, 20, 20), lw=.55, order='LTF', ft='b', fcol=(20, 20, 20), fin=OLD, seed=1962)

# Jules and Jim (1962): the poster's paper cream, its brown script Jules and Jim lifted, Jeanne Moreau's eyes (director from IMDb)
std('jules-and-jim-1962', ('grad', [(0, (244, 236, 216)), (.6, (228, 216, 190)), (1, (150, 130, 100))]), (150, 80, 50),
    L((0.075, 0.67, 0.92, 0.855), 110, (154, 82, 52), mode='dark'),
    photo=ph(0.6, 0.18, 0.86, 0.5), pb=(40, 30, 26), lg=(40, 30, 26), lw=.55, order='LPTCF', credit=['UN FILM DE', 'FRANÇOIS TRUFFAUT'], ccol=(40, 30, 26),
    ft='c', fcol=(40, 30, 26), fin=OLD, seed=1962)

# Knife in the Water (1962): the poster's white, its black thin KNIFE IN THE WATER lifted, the sail's black triangle (no logo file: Kamera, from IMDb's company credits; director from IMDb)
std('knife-in-the-water-1962', ('grad', [(0, (248, 248, 248)), (.6, (230, 230, 230)), (1, (140, 140, 140))]), (20, 20, 20),
    L((0.135, 0.172, 0.965, 0.225), 66, (20, 20, 20), mode='dark'),
    photo=ph(0.55, 0.6, 0.86, 0.95), pb=(20, 20, 20), studio=['ZESPÓŁ FILMOWY', '"KAMERA"'], scol=(20, 20, 20), order='lTPF', ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=OLD, seed=1962)

# Lawrence of Arabia (1962): a 2-tape box; the poster's desert yellow, its black serif LAWRENCE OF ARABIA lifted, Lawrence's shadowed face in the white keffiyeh (no logo file: Horizon Pictures, from IMDb's company credits)
std('lawrence-of-arabia-1962', ('grad', [(0, (250, 210, 50)), (.6, (240, 170, 40)), (1, (160, 90, 20))]), (24, 20, 16),
    L((0.05, 0.112, 0.958, 0.188), 80, (24, 20, 16), mode='dark'),
    photo=ph(0.5, 0.5, 0.9, 0.8), pb=(24, 20, 16), studio=['HORIZON PICTURES'], scol=(24, 20, 16), order='lPTCSF', credit=['A DAVID LEAN', 'FILM'], ccol=(24, 20, 16),
    stick=TWOST((24, 20, 16), (250, 210, 50)), ft='a', vbox=(24, 20, 16), fcol=(40, 30, 20), fin=OLD, seed=1962, **TWO)

# Lolita (1962): the poster's pink-white, its white LOLITA lifted and edged pink, the heart-shaped glasses and the lollipop
std('lolita-1962', ('grad', [(0, (250, 230, 230)), (.6, (236, 200, 200)), (1, (170, 110, 110)) ]), WHT,
    L((0.49, 0.218, 0.85, 0.286), 90, WHT, mode='light', outline=((220, 60, 80), 2)),
    photo=ph(0.48, 0.55, 0.9, 0.85), pb=(220, 40, 60), lg=(200, 40, 60), lw=.55, order='LPTF', ft='e', vbox=(220, 40, 60), fcol=(150, 50, 60), fin=OLD, seed=1962)

# Sanjuro (1962): the smoky gold, the poster's white SANJURO lifted, Mifune from the top of the poster (director from IMDb)
std('sanjuro-1962', ('grad', [(0, (130, 100, 50)), (.6, (50, 40, 22)), (1, (8, 6, 4))]), WHT,
    L((0.255, 0.605, 0.763, 0.677), 80, WHT, mode='light'),
    photo=ph(0.5, 0.2, 0.8, 0.85), pb=(230, 170, 60), lg=WHT, lw=.55, order='LPTF', ft='b', fcol=(220, 210, 190), fin=OLD, seed=1962)

# The Trial (1962): the poster's paper and black spiral, its red tall THE and TRIAL cut off it above and below the red band of eyes they run into (no logo file: Paris-Europa Productions, from IMDb's company credits; director from IMDb)
TRR = lambda a: (a[..., 0] > .55) & (a[..., 1] < .35) & (a[..., 2] < .35)
std('the-trial-1962', ('grad', [(0, (230, 222, 206)), (.6, (210, 196, 176)), (1, (120, 100, 80))]), (210, 30, 30),
    LC([(0.035, 0.11, 0.405, 0.355), (0.385, 0.578, 0.958, 0.825)], 150, gapf=.15, valign='base', margin=0, cuts=[key_cut(TRR)] * 2),
    photo=ph(0.5, 0.46, 1.0, 0.42), pb=(20, 20, 20), studio=['PARIS-EUROPA', 'PRODUCTIONS'], scol=(20, 20, 20), order='lTPCF', credit=['AN ORSON WELLES', 'FILM'],
    ccol=(20, 20, 20), ft='d', fcol=(20, 20, 20), fin=OLD, seed=1962)

# To Kill a Mockingbird (1962): the poster's yellow, its cream TO KILL A Mockingbird cut off the book cover word by word and levelled, the children and Atticus over the book (top-billed cast from IMDb)
TKC = lambda a: (a[..., 0] > .85) & (a[..., 1] > .8) & (a[..., 2] < .6)
std('to-kill-a-mockingbird-1962', ('grad', [(0, (250, 230, 120)), (.6, (240, 210, 80)), (1, (160, 130, 30))]), (40, 40, 60),
    LC([(0.52, 0.4, 0.95, 0.62), (0.67, 0.59, 0.79, 0.69), (0.52, 0.62, 0.96, 0.89)], 90, gapf=.18, valign='base', outline=((40, 40, 60), 2.4), cuts=[
        pick_cut(TKC, (0.52, 0.4, 0.95, 0.62), [(0.575, 0.549), (0.645, 0.539), (0.734, 0.508), (0.793, 0.489), (0.831, 0.483), (0.892, 0.462)], rot=-22, r=.02),
        pick_cut(TKC, (0.67, 0.59, 0.79, 0.69), [(0.724, 0.637)], r=.02),
        pick_cut(TKC, (0.52, 0.62, 0.96, 0.89), [(0.559, 0.804), (0.609, 0.801), (0.645, 0.791), (0.681, 0.768), (0.716, 0.765), (0.746, 0.757), (0.786, 0.757), (0.822, 0.72), (0.854, 0.719), (0.877, 0.706), (0.923, 0.686)], rot=-26, r=.015)]),
    photo=ph(0.55, 0.15, 0.6, 0.8), pb=(40, 40, 60), lg=(40, 40, 60), lw=.55, order='LPTF', ft='c', fcol=(40, 40, 60), fin=OLD, seed=1962)

# Billy Liar (1963): the poster's sky blue, its white BILLY LIAR cut off it, Tom Courtenay under the yellow crown (no logo file: Vic Films, from IMDb's company credits)
std('billy-liar-1963', ('grad', [(0, (70, 180, 200)), (.6, (40, 130, 150)), (1, (14, 50, 60))]), WHT,
    LC([(0.03, 0.02, 0.62, 0.14), (0.45, 0.12, 0.98, 0.26)], 90, gapf=.2, valign='base', cuts=[comp_cut(lambda a: (_lum(a) > .9) & (_sat(a) < .15), minf=.1, rot=-4)] * 2),
    photo=ph(0.55, 0.62, 0.8, 0.9), pb=(250, 190, 30), studio=['VIC FILMS'], scol=WHT, order='lPTSF', stick=flow(dot, 74, ['COMEDY'], (250, 190, 30), (20, 50, 60)),
    ft='a', vbox=WHT, vink=(40, 130, 150), fcol=(220, 240, 244), fin=OLD, seed=1963)

# Charade (1963): black, the poster's many-coloured CHARADE cut off it in its own colours, Cary Grant and Audrey Hepburn in the red spiral
std('charade-1963', ('grad', [(0, (30, 30, 30)), (.6, (10, 10, 10)), (1, (2, 2, 2))]), (240, 200, 40),
    LC([(0.07, 0.7, 0.93, 0.912)], 110, cuts=[key_cut(lambda a: _sat(a) > .45)]),
    photo=ph(0.5, 0.3, 0.86, 0.95), pb=(220, 40, 30), lg=WHT, lw=.55, order='LPTCF', credit=['CARY GRANT', 'AUDREY HEPBURN'], ccol=WHT,
    ft='b', fcol=(200, 200, 200), fin=OLD, seed=1963)

# Contempt (1963): the poster's white, its dark-maroon CONTEMPT lifted, Bardot in the maroon frame (no logo file: Rome Paris Films, from IMDb's company credits; director from IMDb)
std('contempt-1963', ('grad', [(0, (246, 244, 242)), (.6, (226, 222, 218)), (1, (130, 100, 100))]), (70, 20, 24),
    L((0.088, 0.695, 0.926, 0.83), 90, (70, 20, 24), mode='dark', speck=.03),
    photo=ph(0.5, 0.35, 0.8, 1.2), pb=(130, 40, 40), studio=['ROME PARIS FILMS'], scol=(70, 20, 24), order='lPTCF', credit=['UN FILM DE', 'JEAN-LUC GODARD'], ccol=(70, 20, 24),
    ft='a', vbox=(70, 20, 24), fcol=(70, 20, 24), fin=OLD, seed=1963)

# High and Low (1963): black, the poster's yellow HIGH, the sideways AND and LOW cut off it in their own colours, the men round the telephone (director from IMDb)
HLY = lambda a: (a[..., 0] > .8) & (a[..., 1] > .7) & (a[..., 2] < .4)
std('high-and-low-1963', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), (250, 220, 50),
    LC([(0.085, 0.085, 0.915, 0.255), (0.085, 0.255, 0.17, 0.425), (0.17, 0.252, 0.915, 0.425)], 100, gapf=.15, valign='base', cuts=[comp_cut(HLY), comp_cut(HLY, rot=-90), comp_cut(HLY)]),
    photo=ph(0.5, 0.72, 1.0, 0.75), pb=(250, 220, 50), lg=WHT, lw=.55, order='LTPCF', credit=['A FILM BY', 'AKIRA KUROSAWA'], ccol=WHT,
    ft='e', fcol=(200, 200, 200), fin=OLD, seed=1963)

# It's a Mad, Mad, Mad, Mad World (1963): the poster's white, its red "IT'S A MAD, MAD, MAD, MAD WORLD" cut off it line by line into one, the crowd on the globe
MMR = lambda a: (a[..., 0] > .7) & (a[..., 1] < .35)
std('it-s-a-mad-mad-mad-mad-world-1963', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 224)), (1, (140, 140, 136))]), (210, 30, 30),
    LC([(0.175, 0.668, 0.39, 0.724), (0.135, 0.726, 0.305, 0.782), (0.03, 0.784, 0.4, 0.843), (0.205, 0.844, 0.36, 0.899), (0.155, 0.901, 0.42, 0.958)], 60, gapf=.15, valign='base', margin=0,
       cuts=[comp_cut(MMR, minf=.03)] * 5),
    photo=ph(0.48, 0.3, 0.86, 0.9), pb=(210, 30, 30), lg=(210, 30, 30), lw=.55, order='LPTSF', stick=PRC(['$2.99', 'COMEDY']), ft='d', fcol=(30, 30, 30), fin=RENTAL, seed=1963)

# Lord of the Flies (1963): the poster's grey, its red italic LORD OF THE FLIES keyed off it, the boys' faces in the strip (no logo file: Allen-Hodgdon Productions, from IMDb's company credits)
std('lord-of-the-flies-1963', ('grad', [(0, (226, 226, 226)), (.6, (200, 200, 200)), (1, (110, 110, 110))]), (210, 50, 40),
    L([(0.395, 0.414, 0.895, 0.54), (0.378, 0.547, 0.9, 0.672)], 90, (214, 52, 42), mode='key', key=(210, 60, 50), t=(70, 150), gapf=.25),
    photo=ph(0.14, 0.5, 0.26, 1.9), pb=(30, 30, 30), studio=['ALLEN-HODGDON', 'PRODUCTIONS'], scol=(30, 30, 30), order='lPTCF', credit=['A FILM BY', 'PETER BROOK'],
    ccol=(30, 30, 30), ft='b', fcol=(30, 30, 30), fin=OLD, seed=1963)

# Shock Corridor (1963): the poster's white, its black SHOCK CORRIDOR lifted, the screaming patient and the crowd (no logo file: F & F Productions, from IMDb's company credits; director from IMDb)
std('shock-corridor-1963', ('grad', [(0, (248, 248, 248)), (.6, (228, 228, 228)), (1, (140, 140, 140))]), (20, 20, 20),
    L((0.39, 0.641, 0.82, 0.778), 90, (20, 20, 20), mode='dark'),
    photo=ph(0.6, 0.5, 0.86, 0.6), pb=(240, 220, 60), studio=['F & F PRODUCTIONS'], scol=(20, 20, 20), order='lTPF', ft='c', fcol=(20, 20, 20), fin=OLD, seed=1963)

# The Birds (1963): the poster's sky blue, its white serif The Birds lifted, Tippi Hedren and the gulls (no logo file: Alfred J. Hitchcock Productions, from IMDb's company credits)
std('the-birds-1963', ('grad', [(0, (60, 140, 200)), (.6, (30, 80, 140)), (1, (8, 24, 50))]), WHT,
    L((0.335, 0.108, 0.94, 0.226), 100, WHT, mode='light'),
    photo=ph(0.6, 0.5, 0.8, 1.1), pb=(20, 20, 20), studio=['ALFRED J. HITCHCOCK', 'PRODUCTIONS'], scol=WHT, order='lPTSF', stick=flow(dot, 74, ['THRILLER'], (20, 20, 20), WHT),
    ft='b', fcol=(210, 220, 236), fin=RENTAL, seed=1963)

# The Fiancés (1963): the poster's newsprint white, its black THE FIANCÉS (the tall swash F and the accent kept) cut off it letter by letter, ERMANNO OLMI'S in type, the couple's faces
std('the-fiances-1963', ('grad', [(0, (236, 234, 228)), (.6, (216, 214, 206)), (1, (120, 118, 110))]), (24, 24, 24),
    LC([(0.25, 0.74, 0.86, 0.93)], 100, cuts=[pick_cut(lambda a: _lum(a) < .3, (0.25, 0.74, 0.86, 0.93), [(0.282, 0.874), (0.337, 0.875), (0.39, 0.874), (0.488, 0.827), (0.528, 0.888), (0.53, 0.841), (0.578, 0.878), (0.647, 0.875), (0.711, 0.875), (0.765, 0.876), (0.82, 0.873)], r=.015)]),
    photo=ph(0.5, 0.47, 0.9, 0.75), pb=(24, 24, 24), lg=(24, 24, 24), lw=.55, order='LPTCF', credit=["ERMANNO OLMI'S"], ccol=(24, 24, 24),
    ft='d', fcol=(24, 24, 24), fin=OLD, seed=1963)

# The Great Escape (1963): the poster's white, its outlined grey THE GREAT ESCAPE in the barbed wire cut off it, McQueen and the men running (a 2-tape box)
std('the-great-escape-1963', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (120, 120, 116))]), (60, 60, 60),
    LC([(0.14, 0.74, 0.86, 0.96)], 130, cuts=[comp_cut(lambda a: _lum(a) < .7, minf=.01, close=3)]),
    photo=ph(0.5, 0.33, 0.9, 0.85), pb=(40, 50, 70), lg=(40, 50, 70), lw=.5, order='LPTSF', stick=TWOST((40, 50, 70), WHT), ft='a', vbox=(40, 50, 70), fcol=(40, 50, 70), fin=OLD, seed=1963, **TWO)

# The Pink Panther (1963): the poster's white, its small red THE PINK PANTHER label cut off it whole, the gang round the bed and the Panther (director from IMDb)
std('the-pink-panther-1963', ('grad', [(0, (250, 236, 240)), (.6, (240, 210, 220)), (1, (180, 120, 140))]), (220, 40, 60),
    LC([(0.385, 0.805, 0.615, 0.89)], 90, cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] < .45))]),
    photo=ph(0.55, 0.47, 0.9, 1.05), pb=(220, 40, 60), lg=(220, 40, 60), lw=.55, order='LPTCF', credit=['A BLAKE EDWARDS', 'FILM'], ccol=(150, 40, 60),
    ft='e', fcol=(150, 40, 60), fin=OLD, seed=1963)

# The Sword in the Stone (1963): Disney, the white clamshell; the poster's blue glow, its white THE SWORD IN THE STONE cut off it, Arthur's face in the red diamond
disney('the-sword-in-the-stone-1963', ('grad', [(0, (20, 50, 130)), (.5, (40, 100, 200)), (1, (10, 30, 80))]), fin=dict(CLAM, vivid=.2), studio=False,
       title=LC([(0.05, 0.44, 0.95, 0.6)], 100, cuts=[comp_cut(lambda a: (_lum(a) > .85) & (_sat(a) < .3), keep=lambda x, y: not (.4 < x < .62 and y < .35), minf=.01)]),
       face=ph(.63, .22, .2, 1.4), lcol=WHT)

# Youth of the Beast (1963): the poster's white, YOUTH OF THE BEAST typeset in heavy condensed capitals in its black (typeset: the T of BEAST is part of the gunman's black coat on the poster, so a cut reads BEAS; three tried), Jō Shishido with the gun (director from IMDb)
std('youth-of-the-beast-1963', ('grad', [(0, (248, 248, 248)), (.6, (230, 230, 230)), (1, (130, 130, 130))]), (20, 20, 20),
    TT([('YOUTH', (20, 20, 20)), ('OF', (20, 20, 20)), ('THE', (20, 20, 20)), ('BEAST', (20, 20, 20))], 'intbk', 80, sp=.3),
    photo=ph(0.82, 0.22, 0.36, 1.2), pb=(220, 30, 40), lg=(20, 20, 20), lw=.55, order='LPTF', ft='c', vbox=(220, 30, 40), fcol=(20, 20, 20), fin=OLD, seed=1963)

# A Fistful of Dollars (1964): the poster's blood red, its white A FISTFUL OF DOLLARS cut off it letter by letter, Clint Eastwood in the poncho (director from IMDb)
std('a-fistful-of-dollars-1964', ('grad', [(0, (180, 30, 24)), (.6, (110, 14, 10)), (1, (40, 4, 2))]), WHT,
    LC([(0.06, 0.42, 0.82, 0.535), (0.06, 0.53, 0.85, 0.64)], 90, gapf=.25, valign='base', cuts=[
        pick_cut(lambda a: _lum(a) > .8, (0.06, 0.42, 0.82, 0.535), [(0.111, 0.498), (0.252, 0.481), (0.359, 0.475), (0.422, 0.492), (0.424, 0.442), (0.486, 0.481), (0.557, 0.476), (0.617, 0.479), (0.692, 0.48), (0.762, 0.487)], r=.015),
        pick_cut(lambda a: _lum(a) > .8, (0.06, 0.53, 0.85, 0.64), [(0.132, 0.572), (0.201, 0.566), (0.261, 0.579), (0.354, 0.586), (0.437, 0.582), (0.506, 0.586), (0.562, 0.587), (0.636, 0.585), (0.72, 0.582), (0.796, 0.582)], r=.015)]),
    photo=ph(0.5, 0.2, 0.8, 0.6), pb=WHT, lg=WHT, lw=.55, order='LPTCSF', credit=['CLINT EASTWOOD'], ccol=WHT,
    stick=BAR('64 1105', top='WESTERN', fill=(232, 220, 196)), ft='b', fcol=(240, 210, 200), fin=RENTAL, seed=1964)

# Band of Outsiders (1964): the poster's white, BAND OF OUTSIDERS typeset in light geometric capitals like the poster's, in black (typeset: the poster's black frame runs into the F and the O of OUTSIDERS; two cuts tried), Anna Karina and the boys (no logo file: Columbia Films, from IMDb's company credits; director from IMDb)
std('band-of-outsiders-1964', ('grad', [(0, (248, 248, 248)), (.6, (230, 230, 230)), (1, (130, 130, 130))]), (20, 20, 20),
    T('BAND OF OUTSIDERS', 'adv', 70, (20, 20, 20), track=.04),
    photo=ph(0.5, 0.67, 0.86, 0.75), pb=(20, 20, 20), studio=['COLUMBIA FILMS'], scol=(20, 20, 20), order='lPTCF', credit=['UN FILM DE', 'JEAN-LUC GODARD'],
    ccol=(20, 20, 20), ft='e', fcol=(20, 20, 20), fin=OLD, seed=1964)

# Diary of a Chambermaid (1964): the poster's painted blues and reds, its dark script Diary of a Chambermaid lifted, Jeanne Moreau's face (no logo file: Ciné-Alliance, from IMDb's company credits)
std('diary-of-a-chambermaid-1964', ('grad', [(0, (120, 180, 220)), (.5, (220, 100, 70)), (1, (60, 30, 20))]), (30, 40, 60),
    L((0.05, 0.645, 0.99, 0.885), 120, (30, 40, 60), mode='key', key=(40, 50, 70), t=(70, 150)),
    photo=ph(0.5, 0.33, 0.8, 0.95), pb=(30, 40, 60), studio=['CINÉ-ALLIANCE'], scol=(30, 40, 60), order='lPTCF', credit=['JEANNE MOREAU'], ccol=(30, 40, 60),
    ft='a', vbox=(30, 40, 60), fcol=(30, 40, 60), fin=OLD, seed=1964)

# Dr. Strangelove (1964): the sky's grey, the poster's white column of DR. STRANGELOVE OR HOW I LEARNED TO STOP WORRYING AND LOVE THE BOMB cut off it and turned to run down the spine, the B-52 (director from IMDb)
std('dr-strangelove-or-how-i-learned-to-stop-worrying-and-love-the-bomb-1964', ('grad', [(0, (180, 180, 178)), (.6, (110, 110, 108)), (1, (30, 30, 30))]), WHT,
    LC([(0.38, 0.38, 0.66, 0.93)], 120, cuts=[comp_cut(lambda a: _lum(a) > .88, rot=90, minf=.003)]),
    photo=ph(0.55, 0.13, 1.0, 0.3), pb=WHT, lg=WHT, lw=.5, order='LPTF', dotst=('COMEDY', WHT, (60, 60, 60)), ft='d', fcol=(210, 210, 210), fin=OLD, seed=1964)

# Marnie (1964): the poster's white, its purple "MARNIE" keyed off it, Sean Connery and Tippi Hedren
std('marnie-1964', ('grad', [(0, (246, 244, 246)), (.6, (226, 220, 228)), (1, (120, 90, 130))]), (120, 40, 120),
    L((0.045, 0.492, 0.955, 0.598), 90, (124, 42, 124), mode='key', key=(120, 40, 120), t=(70, 150)),
    photo=ph(0.5, 0.2, 0.9, 0.85), pb=(124, 42, 124), lg=(40, 30, 40), lw=.55, order='LPTF', ft='c', fcol=(40, 30, 40), fin=OLD, seed=1964)

# Mary Poppins (1964): Disney, the white clamshell; the poster's sky blue, MARY POPPINS typeset in heavy capitals in the poster's white with a dotted look from its blue keyline (typeset: the poster's title is built of separate white dots among flowers, and every cut either breaks the letters into dots or swallows the flowers; three tried), Mary's face in the red diamond
disney('mary-poppins-1964', ('grad', [(0, (20, 90, 180)), (.5, (30, 120, 210)), (1, (10, 50, 120))]), fin=dict(CLAM, vivid=.2),
       title=TT([('MARY', WHT), ('POPPINS', WHT)], 'intbk', 90, sp=.35, outline=((20, 60, 140), 2.4)),
       face=ph(.605, .415, .085, 1.4), lcol=WHT)

# The Killers (1964): the poster's red, The Killers typeset in heavy rounded capitals in its cream with a dark keyline (typeset: Angie Dickinson's head is printed over the poster's ll, so a lift leaves a hole; two tried), Angie Dickinson in the black dress (director from IMDb)
std('the-killers-1964', ('grad', [(0, (240, 40, 30)), (.6, (190, 20, 16)), (1, (70, 6, 4))]), (246, 236, 210),
    TT([('The', (248, 238, 212)), ('Killers', (248, 238, 212))], 'popb', 100, sp=.25, outline=((40, 16, 12), 2.4)),
    photo=ph(0.48, 0.66, 0.6, 1.1), pb=(246, 236, 210), lg=(246, 236, 210), lw=.55, order='LPTCF', credit=['A DON SIEGEL', 'FILM'], ccol=(246, 236, 210),
    ft='a', vbox=(246, 236, 210), vink=(190, 20, 16), fcol=(250, 220, 210), fin=OLD, seed=1964)

# The Naked Kiss (1964): the poster's yellow, its violet bouncing The Naked Kiss cut off it line by line, Kelly with the suitcase (no logo file: Allied Artists, from IMDb's company credits)
std('the-naked-kiss-1964', ('grad', [(0, (250, 230, 110)), (.6, (240, 210, 70)), (1, (160, 130, 30))]), (110, 90, 170),
    LC([(0.14, 0.34, 0.48, 0.49), (0.06, 0.45, 0.69, 0.68), (0.17, 0.66, 0.62, 0.875)], 120, gapf=.15, valign='base', cuts=[
        pick_cut(lambda a: (a[..., 2] > a[..., 0] + .05) & (_lum(a) < .6), (0.14, 0.34, 0.48, 0.49), [(0.217, 0.409), (0.32, 0.418), (0.424, 0.424)], r=.02),
        comp_cut(lambda a: (a[..., 2] > a[..., 0] + .05) & (_lum(a) < .6), keep=lambda x, y: y > .2, minf=.05), comp_cut(lambda a: (a[..., 2] > a[..., 0] + .05) & (_lum(a) < .6), keep=lambda x, y: y > .08, minf=.05)]),
    photo=ph(0.5, 0.13, 0.8, 0.55), pb=(110, 90, 170), studio=['ALLIED ARTISTS'], scol=(60, 50, 100), order='lTPSF', stick=RWD(), ft='e', fcol=(60, 50, 100), fin=RENTAL, seed=1964)

# The Tomb of Ligeia (1964): the poster's white, its yellow THE TOMB OF LIGEIA cut off the black cat, the cat's eyes (no logo file: Alta Vista Productions, from IMDb's company credits)
std('the-tomb-of-ligeia-1964', ('grad', [(0, (30, 30, 30)), (.6, (10, 10, 10)), (1, (2, 2, 2))]), (250, 210, 50),
    LC([(0.33, 0.2, 0.69, 0.375)], 110, cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .5) & (a[..., 2] < .45))]),
    photo=ph(0.5, 0.5, 0.86, 0.45), pb=(250, 210, 50), studio=['ALTA VISTA', 'PRODUCTIONS'], scol=(250, 210, 50), order='lPTCSF', credit=['VINCENT PRICE'],
    ccol=(250, 210, 50), stick=flow(dot, 74, ['HORROR'], (250, 210, 50), (10, 10, 10)), ft='c', fcol=(200, 200, 196), fin=RENTAL, seed=1964)

# Alphaville (1965): the poster's white, its grey ALPHAVILLE lifted, Anna Karina in the blue star (no logo file: André Michelin Productions, from IMDb's company credits; director from IMDb)
std('alphaville-1965', ('grad', [(0, (246, 248, 250)), (.6, (222, 228, 234)), (1, (90, 130, 160))]), (60, 66, 72),
    L((0.2, 0.846, 0.81, 0.912), 80, (60, 66, 72), mode='dark'),
    photo=ph(0.4, 0.4, 0.8, 1.0), pb=(110, 190, 220), studio=['ANDRÉ MICHELIN', 'PRODUCTIONS'], scol=(60, 66, 72), order='lPTCF', credit=['UN FILM DE', 'JEAN-LUC GODARD'],
    ccol=(60, 66, 72), ft='b', fcol=(60, 66, 72), fin=OLD, seed=1965)

# Doctor Zhivago (1965): a 2-tape box; the poster's white, its maroon serif DOCTOR ZHIVAGO with the swash under it lifted, Julie Christie and Omar Sharif
std('doctor-zhivago-1965', ('grad', [(0, (246, 244, 242)), (.6, (226, 220, 216)), (1, (130, 100, 100))]), (90, 30, 40),
    L([(0.178, 0.466, 0.866, 0.558), (0.062, 0.556, 0.926, 0.705)], 90, (92, 32, 42), mode='dark', gapf=.25),
    photo=ph(0.5, 0.2, 0.86, 0.75), pb=(92, 32, 42), lg=(92, 32, 42), lw=.5, order='LPTCSF', credit=['A DAVID LEAN', 'FILM'], ccol=(92, 32, 42),
    stick=TWOST((92, 32, 42), WHT), ft='d', vbox=(92, 32, 42), fcol=(92, 32, 42), fin=OLD, seed=1965, **TWO)

# For a Few Dollars More (1965): the poster's white, its black distressed FOR, the small A, FEW, the rust DOLLARS and MORE cut off it in their own colours and run in one line, Eastwood under the hat
FDK = lambda a: _lum(a) < .72
std('for-a-few-dollars-more-1965', ('grad', [(0, (246, 242, 236)), (.6, (226, 216, 200)), (1, (150, 110, 70))]), (24, 20, 18),
    LC([(0.605, 0.37, 0.995, 0.54), (0.603, 0.62, 0.64, 0.69), (0.64, 0.54, 0.995, 0.685), (0.6, 0.683, 0.995, 0.762), (0.6, 0.76, 0.995, 0.87)], 90, gapf=.15, valign='base', margin=0,
       cuts=[comp_cut(FDK, minf=.1)] * 5),
    photo=ph(0.3, 0.27, 0.6, 1.0), pb=(24, 20, 18), lg=(24, 20, 18), lw=.55, order='LPTF', ft='b', fcol=(24, 20, 18), fin=OLD, seed=1965)

# Juliet of the Spirits (1965): black, the poster's green circle with its black JULIET OF THE SPIRITS cut off it whole, Giulietta Masina in blue (no logo file: Rizzoli Film, from IMDb's company credits)
std('juliet-of-the-spirits-1965', ('grad', [(0, (40, 40, 40)), (.6, (14, 14, 14)), (1, (2, 2, 2))]), (130, 180, 80),
    LC([(0.2, 0.695, 0.8, 0.915)], 160, cuts=[plate_cut(lambda a: (a[..., 1] > .5) & (a[..., 1] > a[..., 2] + .15))]),
    photo=ph(0.5, 0.42, 0.66, 1.15), pb=(130, 180, 80), studio=['RIZZOLI FILM'], scol=(130, 180, 80), order='lPTCF', credit=['UN FILM DI', 'FEDERICO FELLINI'],
    ccol=(130, 180, 80), ft='c', fcol=(200, 200, 196), fin=OLD, seed=1965)

# Story of a Prostitute (1965): the poster's sepia, STORY OF A PROSTITUTE typeset in heavy condensed capitals in its rust (typeset: the poster's lettering is printed half-faded over the photograph and breaks into specks in every lift; two tried), the lovers (director from IMDb)
std('story-of-a-prostitute-1965', ('grad', [(0, (190, 170, 150)), (.6, (110, 96, 80)), (1, (30, 24, 20))]), (160, 86, 54),
    TT([('STORY OF A', (166, 90, 56)), ('PROSTITUTE', (166, 90, 56))], 'intbk', 70, sp=.3, outline=((40, 26, 20), 1.4)),
    photo=ph(0.6, 0.7, 0.8, 1.1), pb=(160, 86, 54), lg=(240, 230, 220), lw=.55, order='LPTF', ft='a', vbox=(160, 86, 54), fcol=(220, 210, 200), fin=OLD, seed=1965)

# Death of a Salesman (1966): the poster's night blue, its pale DEATH OF A SALESMAN cut off it in its own shading, the salesman dissolving (made for CBS television: the network logo at the head)
std('death-of-a-salesman-1966', ('grad', [(0, (30, 34, 50)), (.6, (12, 14, 22)), (1, (2, 2, 4))]), (210, 206, 230),
    LC([(0.16, 0.078, 0.86, 0.208), (0.38, 0.2, 0.62, 0.255), (0.03, 0.258, 0.975, 0.385)], 76, gapf=.2, valign='base', margin=0, cuts=[comp_cut(lambda a: _lum(a) > .5, minf=.1)] * 3),
    photo=ph(0.67, 0.66, 0.5, 1.2), pb=(180, 180, 220), lg=WHT, lw=.5, order='LPTCF', credit=['BY ARTHUR MILLER'], ccol=(210, 206, 230),
    ft='e', fcol=(190, 190, 210), fin=OLD, seed=1966)

# Hotel Paradiso (1966): the poster's white, its red Hotel Paradiso lifted, the farce through the hotel doors
std('hotel-paradiso-1966', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (140, 130, 120))]), (210, 40, 30),
    L((0.672, 0.822, 0.942, 0.93), 100, (214, 42, 32), mode='key', key=(210, 50, 40), t=(70, 150)),
    photo=ph(0.5, 0.4, 0.86, 1.0), pb=(214, 42, 32), lg=(214, 42, 32), lw=.5, order='LPTF', ft='b', fcol=(60, 40, 30), fin=OLD, seed=1966)

# Masculin Féminin (1966): the poster's white, its black masculin and pink féminin cut off it in their own colours, Léaud in the black triangle (director from IMDb)
std('masculin-feminin-1966', ('grad', [(0, (248, 248, 248)), (.6, (230, 230, 230)), (1, (140, 140, 140))]), (20, 20, 20),
    LC([(0.15, 0.68, 0.71, 0.768), (0.34, 0.768, 0.785, 0.845)], 90, gapf=.2, valign='base', cuts=[key_cut(lambda a: _lum(a) < .2), key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] < .35))]),
    photo=ph(0.5, 0.28, 0.86, 0.75), pb=(230, 30, 120), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['UN FILM DE', 'JEAN-LUC GODARD'], ccol=(20, 20, 20),
    dotst=('FOREIGN', (230, 30, 120), WHT), ft='d', fcol=(20, 20, 20), fin=OLD, seed=1966)

# Persona (1966): the poster's white, its black thin PERSONA lifted, the two faces in shadow (director from IMDb)
std('persona-1966', ('grad', [(0, (248, 248, 248)), (.6, (226, 226, 226)), (1, (120, 120, 120))]), (20, 20, 20),
    L((0.17, 0.715, 0.865, 0.8), 80, (20, 20, 20), mode='dark'),
    photo=ph(0.5, 0.27, 1.0, 0.7), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['EN FILM AV', 'INGMAR BERGMAN'], ccol=(20, 20, 20),
    ft='c', fcol=(20, 20, 20), fin=OLD, seed=1966)

# The Battle of Algiers (1966): the poster's white, its red stencil THE BATTLE OF ALGIERS keyed off it, the paratroop colonel in his dark glasses (no logo file in type: Casbah Film; director from IMDb)
std('the-battle-of-algiers-1966', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (130, 130, 126))]), (200, 30, 40),
    L([(0.03, 0.055, 0.975, 0.17), (0.02, 0.168, 0.98, 0.282)], 80, (204, 32, 42), mode='key', key=(200, 40, 50), t=(70, 150), gapf=.25),
    photo=ph(0.6, 0.62, 0.66, 1.1), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A FILM BY', 'GILLO PONTECORVO'], ccol=(20, 20, 20),
    ft='b', vbox=(204, 32, 42), fcol=(20, 20, 20), fin=OLD, seed=1966)

# The Black Cat (1966): black, the poster's red slab-serif THE BLACK CAT keyed off it, the cat's red eyes (no logo file: Falcon International, from IMDb's company credits)
std('the-black-cat-1966', ('grad', [(0, (30, 20, 20)), (.6, (10, 6, 6)), (1, (2, 2, 2))]), (220, 30, 40),
    L([(0.455, 0.022, 0.82, 0.138), (0.155, 0.135, 0.815, 0.264), (0.155, 0.264, 0.815, 0.48)], 90, (224, 32, 42), mode='key', key=(210, 30, 40), t=(70, 150), gapf=.2),
    photo=ph(0.55, 0.72, 0.86, 0.6), pb=(224, 32, 42), studio=['FALCON', 'INTERNATIONAL'], scol=(224, 32, 42), order='lPTSF', stick=PRC(['$0.99', 'HORROR']),
    ft='d', fcol=(200, 190, 190), fin=RENTAL, seed=1966)

# The Good, the Bad and the Ugly (1966): the desert's dust, the poster's white distressed GOOD, BAD and UGLY with their small sideways THE, THE and AND THE cut off it in their own colours and run in one line, Eastwood under the hat
GBW = lambda a: (_lum(a) > .78) & (_sat(a) < .3)
std('the-good-the-bad-and-the-ugly-1966', ('grad', [(0, (190, 170, 140)), (.6, (120, 90, 60)), (1, (40, 26, 14))]), WHT,
    [LC([(0.278, 0.364, 0.326, 0.436), (0.33, 0.268, 0.795, 0.452), (0.395, 0.554, 0.444, 0.628), (0.444, 0.449, 0.795, 0.626)], 90,
        gapf=.12, valign='base', cuts=[comp_cut(GBW, rot=-90, minf=.1), comp_cut(GBW, minf=.1, close=3), comp_cut(GBW, rot=-90, minf=.1), comp_cut(GBW, minf=.1, close=3)]),
     LC([(0.345, 0.645, 0.398, 0.795), (0.399, 0.62, 0.8, 0.81)], 90, gapf=.12, valign='base', cuts=[comp_cut(GBW, rot=-90, minf=.05), comp_cut(GBW, minf=.1, close=3)])],
    tgap=6,
    photo=ph(0.5, 0.1, 0.6, 0.6), pb=(240, 200, 140), lg=WHT, lw=.5, order='LTPSF', stick=BAR('66 7310', top='WESTERN', fill=(232, 220, 196)), ft='a', vbox=(240, 200, 140), vink=(40, 26, 14), fcol=(240, 220, 200), fin=RENTAL, seed=1966)

# The Pornographers (1966): black, the poster's white condensed THE PORNOGRAPHERS lifted, the face behind the film camera (director from IMDb)
std('the-pornographers-1966', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    L((0.01, 0.276, 0.66, 0.35), 70, WHT, mode='light'),
    photo=ph(0.5, 0.62, 0.86, 0.85), pb=(160, 210, 60), lg=WHT, lw=.55, order='LPTCF', credit=['A FILM BY', 'SHŌHEI IMAMURA'], ccol=WHT,
    ft='e', fcol=(200, 200, 200), fin=OLD, seed=1966)

# The Sword of Doom (1966): the poster's fiery orange fog, its white THE SWORD OF DOOM lifted, the swordsman in the forest (top-billed cast from IMDb)
std('the-sword-of-doom-1966', ('grad', [(0, (240, 140, 20)), (.6, (170, 80, 10)), (1, (40, 16, 4))]), WHT,
    L((0.115, 0.75, 0.885, 0.827), 70, WHT, mode='light'),
    photo=ph(0.45, 0.34, 0.6, 1.4), pb=WHT, lg=WHT, lw=.55, order='LTPF', ft='c', fcol=(250, 230, 200), fin=OLD, seed=1966)

# Tokyo Drifter (1966): black, the poster's pink thin T O K Y stacked down its edge and its last O (the pink ring with the teal DRIFTER inside) cut off it in their own colours and run in one line, the yellow-suited gunman (director from IMDb)
TDP = lambda a: (a[..., 0] > .55) & (a[..., 2] > .35) & (a[..., 1] < .7) & (_lum(a) > .35)
std('tokyo-drifter-1966', ('grad', [(0, (30, 26, 34)), (.6, (10, 8, 12)), (1, (2, 2, 2))]), (240, 130, 170),
    LC([(0.76, 0.1, 0.93, 0.545), (0.772, 0.548, 0.925, 0.652)], 110, gapf=.2, valign='mid', cuts=[
        seq_cut(TDP, (0.76, 0.1, 0.93, 0.545), [(0.847, 0.156), (0.847, 0.277), (0.841, 0.385), (0.847, 0.485)], turn=[0] * 4, gapf=.18),
        key_cut(lambda a: _lum(a) > .3)]),
    photo=ph(0.4, 0.42, 0.6, 1.3), pb=(240, 200, 40), lg=(240, 130, 170), lw=.55, order='LPTCF', credit=['A FILM BY', 'SEIJUN SUZUKI'], ccol=(240, 130, 170),
    dotst=('ACTION', (240, 200, 40), (10, 8, 12)), ft='b', fcol=(200, 196, 200), fin=OLD, seed=1966)

# Torn Curtain (1966): the poster's dark red, its yellow 'TORN CURTAIN' keyed off it, Paul Newman and Julie Andrews torn apart by the knife
std('torn-curtain-1966', ('grad', [(0, (180, 20, 20)), (.6, (120, 10, 10)), (1, (40, 2, 2))]), (250, 230, 50),
    L([(0.3, 0.733, 0.59, 0.81), (0.325, 0.808, 0.78, 0.888)], 80, (252, 232, 52), mode='key', key=(250, 230, 60), t=(70, 150), gapf=.25),
    photo=ph(0.5, 0.33, 0.9, 0.7), pb=(250, 230, 50), lg=WHT, lw=.55, order='LPTF', ft='e', fcol=(240, 210, 200), fin=OLD, seed=1966)

# Bonnie and Clyde (1967): the poster's pale sky, its black condensed BONNIE AND CLYDE lifted, Beatty and Dunaway with their guns
std('bonnie-and-clyde-1967', ('grad', [(0, (226, 232, 236)), (.6, (190, 200, 206)), (1, (90, 100, 106))]), (20, 20, 20),
    L((0.115, 0.04, 0.915, 0.15), 80, (20, 20, 20), mode='dark'),
    photo=ph(0.5, 0.55, 0.9, 0.95), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF', ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=OLD, seed=1967)

# Cool Hand Luke (1967): the poster's white, its black COOL HAND LUKE with the chain lifted, Paul Newman's face in the yellow-orange zigzag
std('cool-hand-luke-1967', ('grad', [(0, (250, 230, 120)), (.6, (240, 160, 60)), (1, (160, 70, 20))]), (20, 20, 20),
    L((0.022, 0.83, 0.978, 0.884), 70, (20, 20, 20), mode='dark'),
    photo=ph(0.72, 0.42, 0.56, 1.25), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTSF', stick=RWD(fill=(250, 246, 230)),
    ft='d', fcol=(30, 20, 14), fin=RENTAL, seed=1967)

# Le Samouraï (1967): the poster's grey, its black thin LE SAMOURAÏ lifted (diaeresis and all), Delon tipping his hat (no logo file: CICC, from IMDb's company credits; director from IMDb, as on the poster)
std('le-samourai-1967', ('grad', [(0, (200, 204, 200)), (.6, (160, 164, 160)), (1, (60, 64, 60))]), (20, 20, 20),
    L((0.19, 0.058, 0.975, 0.13), 76, (20, 20, 20), mode='dark', speck=0),
    photo=ph(0.4, 0.45, 0.8, 1.0), pb=(20, 20, 20), studio=['CICC'], scol=(20, 20, 20), order='lPTCF', credit=['A FILM BY', 'JEAN-PIERRE MELVILLE'], ccol=(20, 20, 20),
    ft='c', fcol=(20, 20, 20), fin=OLD, seed=1967)

# Samurai Rebellion (1967): black, the poster's red SAMURAI and REBELLION rebuilt letter by letter off the diagonals they step down, Mifune's face (director from IMDb)
SRR = lambda a: (a[..., 0] > .7) & (a[..., 1] < .3)
std('samurai-rebellion-1967', ('grad', [(0, (40, 30, 34)), (.6, (12, 10, 12)), (1, (2, 2, 2))]), (230, 30, 40),
    LC([(0.28, 0.02, 0.55, 0.44), (0.4, 0.06, 0.75, 0.6)], 84, gapf=.25, valign='base', cuts=[
        seq_cut(SRR, (0.28, 0.02, 0.55, 0.44), [(0.329, 0.059), (0.359, 0.118), (0.388, 0.174), (0.419, 0.234), (0.443, 0.289), (0.479, 0.349), (0.508, 0.405)], turn=[0] * 7, gapf=.1),
        seq_cut(SRR, (0.4, 0.06, 0.75, 0.6), [(0.452, 0.096), (0.483, 0.155), (0.514, 0.212), (0.543, 0.27), (0.57, 0.335), (0.6, 0.393), (0.636, 0.443), (0.666, 0.5), (0.696, 0.558)], turn=[0] * 9, gapf=.1)]),
    photo=ph(0.25, 0.68, 0.46, 1.1), pb=(230, 30, 40), lg=WHT, lw=.55, order='LPTF', ft='a', vbox=(230, 30, 40), fcol=(200, 196, 196), fin=OLD, seed=1967)

# The Firemen's Ball (1967): the poster's red and black, THE FIREMEN'S BALL typeset in heavy condensed capitals in the star's yellow (typeset: on the poster the title is printed in black across the star at a 32-degree slant and runs off its points; two cuts came out in pieces), the firemen's faces (no logo file in type: Barrandov; director from IMDb)
std('the-firemen-s-ball-1967', ('grad', [(0, (200, 30, 20)), (.6, (100, 14, 10)), (1, (20, 2, 2))]), (250, 230, 40),
    TT([("THE FIREMEN'S", (250, 230, 40)), ('BALL', (250, 230, 40))], 'intbk', 80, sp=.3),
    photo=ph(0.5, 0.75, 1.0, 0.6), pb=(250, 230, 40), lg=(250, 230, 40), lw=.55, order='LPTCF', credit=['A FILM BY', 'MILOŠ FORMAN'], ccol=(250, 230, 40),
    ft='e', fcol=(220, 200, 196), fin=OLD, seed=1967)

# The Graduate (1967): the poster's grey, its white THE GRADUATE lifted, Dustin Hoffman framed by Mrs. Robinson's leg
std('the-graduate-1967', ('grad', [(0, (200, 206, 210)), (.6, (130, 136, 140)), (1, (40, 44, 46))]), WHT,
    LC([(0.26, 0.82, 0.975, 0.918)], 90, outline=((40, 40, 40), 1.6), cuts=[comp_cut(lambda a: _lum(a) > .85, keep=lambda x, y: x < .95, minf=.15)]),
    photo=ph(0.5, 0.35, 0.8, 1.0), pb=WHT, lg=WHT, lw=.55, order='LTPF', ft='b', fcol=(230, 230, 230), fin=OLD, seed=1967)

# The Jungle Book (1967): Disney, the white clamshell; the jungle green, the poster's olive-gold The Jungle Book cut off it in its own colours, Mowgli's face in the red diamond
disney('the-jungle-book-1967', ('grad', [(0, (60, 120, 50)), (.5, (100, 160, 60)), (1, (30, 70, 30))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.315, 0.725, 0.78, 0.873)], 120, outline=((30, 40, 10), 2), cuts=[key_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] > .4) & (a[..., 2] < .3))]),
       face=ph(.56, .44, .12, 1.4), lcol=WHT)

# 2001: A Space Odyssey (1968): space black, the poster's yellow 2001: a space odyssey keyed off it, the station and the shuttle (director from IMDb)
std('2001-a-space-odyssey-1968', ('grad', [(0, (20, 30, 50)), (.6, (6, 8, 16)), (1, (2, 2, 4))]), (250, 210, 40),
    L((0.085, 0.832, 0.918, 0.883), 70, (252, 212, 42), mode='key', key=(245, 205, 50), t=(70, 150)),
    photo=ph(0.5, 0.3, 1.0, 0.85), pb=(250, 210, 40), lg=WHT, lw=.55, order='LPTCF', credit=['A STANLEY KUBRICK', 'PRODUCTION'], ccol=WHT,
    dotst=('SCI-FI', (250, 210, 40), (6, 8, 16)), ft='a', vbox=(250, 210, 40), vink=(6, 8, 16), fcol=(200, 204, 214), fin=OLD, seed=1968)

# Rosemary's Baby (1968): the poster's green, its white Rosemary's Baby lifted, the pram on the hill under the title
std('rosemary-s-baby-1968', ('grad', [(0, (60, 150, 70)), (.6, (24, 70, 30)), (1, (2, 6, 2))]), WHT,
    L([(0.15, 0.06, 0.846, 0.142), (0.34, 0.14, 0.733, 0.222)], 90, WHT, mode='light', gapf=.25),
    photo=ph(0.45, 0.68, 0.8, 0.6), pb=WHT, lg=WHT, lw=.55, order='LTPF', ft='c', fcol=(200, 220, 200), fin=OLD, seed=1968)

# Stolen Kisses (1968): the poster's pink, its white "STOLEN KISSES" lifted, the lips (director from IMDb)
std('stolen-kisses-1968', ('grad', [(0, (240, 150, 140)), (.6, (210, 110, 100)), (1, (120, 50, 44))]), WHT,
    L((0.16, 0.672, 0.6, 0.732), 70, WHT, mode='light', outline=((150, 60, 54), 1.4)),
    photo=ph(0.5, 0.3, 0.9, 0.7), pb=WHT, lg=WHT, lw=.55, order='LPTCF', credit=['UN FILM DE', 'FRANÇOIS TRUFFAUT'], ccol=WHT,
    ft='d', fcol=(250, 230, 226), fin=OLD, seed=1968)

# The Party (1968): black, the poster's yellow bubbly THE PARTY keyed off it, Peter Sellers in the chaos (director from IMDb)
std('the-party-1968', ('grad', [(0, (230, 80, 120)), (.4, (60, 20, 30)), (1, (4, 2, 2))]), (250, 240, 40),
    L((0.145, 0.85, 0.876, 0.956), 90, (252, 242, 42), mode='key', key=(245, 235, 50), t=(70, 150)),
    photo=ph(0.5, 0.42, 0.9, 1.1), pb=(250, 240, 40), lg=WHT, lw=.55, order='LPTSF', stick=BAR('68 2219', top='COMEDY', fill=(240, 236, 210)),
    ft='e', fcol=(220, 200, 210), fin=RENTAL, seed=1968)

# Army of Shadows (1969): the poster's slate blue, ARMY OF SHADOWS typeset in a light serif like the poster's, in its pale blue (typeset: the poster's thin pale letters fade into the dark figure behind them, and every lift drops the R and the last S; two tried), the man on the chair (no logo file: Les Films Corona, from IMDb's company credits; director from IMDb)
std('army-of-shadows-1969', ('grad', [(0, (80, 100, 130)), (.6, (40, 56, 76)), (1, (10, 14, 20))]), (210, 220, 236),
    T('ARMY OF SHADOWS', 'ter', 70, (214, 224, 240), track=.1),
    photo=ph(0.45, 0.82, 0.6, 0.85), pb=(214, 224, 240), studio=['LES FILMS CORONA'], scol=(214, 224, 240), order='lPTCF', credit=['UN FILM DE', 'JEAN-PIERRE MELVILLE'],
    ccol=(214, 224, 240), ft='b', fcol=(200, 210, 220), fin=OLD, seed=1969)

# Butch Cassidy and the Sundance Kid (1969): the poster's mustard, its dark BUTCH CASSIDY AND THE SUNDANCE KID lifted, Newman and Redford and the bicycle
std('butch-cassidy-and-the-sundance-kid-1969', ('grad', [(0, (226, 196, 110)), (.6, (200, 160, 80)), (1, (110, 80, 30))]), (40, 26, 20),
    L([(0.067, 0.816, 0.937, 0.878), (0.064, 0.877, 0.892, 0.938)], 70, (40, 26, 20), mode='dark', gapf=.2),
    photo=ph(0.5, 0.4, 0.9, 1.0), pb=(40, 26, 20), lg=(40, 26, 20), lw=.55, order='LPTCF', credit=['PAUL NEWMAN', 'ROBERT REDFORD'], ccol=(40, 26, 20),
    ft='a', vbox=(40, 26, 20), fcol=(40, 26, 20), fin=OLD, seed=1969)

# Double Suicide (1969): the poster's pale photograph, its white DOUBLE and SUICIDE (the red O and red I among them) rebuilt letter by letter off the columns they run down, the lovers lying together (director from IMDb)
DSW = lambda a: ((_lum(a) > .92) & (_sat(a) < .12)) | ((a[..., 0] > .7) & (a[..., 1] < .3))
std('double-suicide-1969', ('grad', [(0, (200, 200, 196)), (.6, (130, 130, 126)), (1, (40, 40, 38))]), WHT,
    LC([(0.17, 0.0, 0.33, 0.92), (0.64, 0.0, 0.81, 0.99)], 90, gapf=.2, valign='base', outline=((40, 40, 38), 1.6), cuts=[
        seq_cut(DSW, (0.17, 0.0, 0.33, 0.92), [(0.244, 0.078), (0.24, 0.22), (0.249, 0.373), (0.245, 0.519), (0.24, 0.687), (0.238, 0.835)], turn=[0] * 6, gapf=.08),
        seq_cut(DSW, (0.64, 0.0, 0.81, 0.99), [(0.731, 0.078), (0.73, 0.223), (0.731, 0.358), (0.717, 0.499), (0.72, 0.63), (0.724, 0.781), (0.719, 0.921)], turn=[0] * 7, gapf=.08)]),
    photo=ph(0.48, 0.5, 0.3, 1.9), pb=(200, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTF', ft='c', fcol=(30, 30, 30), fin=OLD, seed=1969)

# Salesman (1969): the poster's teal, SALESMAN typeset in heavy stencil-like capitals in its white (typeset: the salesman's white silhouette is printed over the poster's MA and cuts it into the letters; two tried), Paul Brennan at the door (no logo file: Maysles Films, from IMDb's company credits; directors from IMDb)
std('salesman-1969', ('grad', [(0, (40, 110, 100)), (.6, (16, 50, 44)), (1, (2, 10, 8))]), WHT,
    T('SALESMAN', 'intbk', 84, WHT),
    photo=ph(0.6, 0.25, 0.8, 0.85), pb=WHT, studio=['MAYSLES FILMS'], scol=WHT, order='lPTCF', credit=['A DOCUMENTARY BY', 'ALBERT & DAVID MAYSLES'], ccol=WHT,
    ft='d', fcol=(200, 220, 216), fin=OLD, seed=1969)


# =====================================================================================
# 1970s (vault-1970s.json, 60 tapes)
# =====================================================================================

# Le Cercle Rouge (1970): black, the poster's white Le Cercle and Rouge with the red ring between them cut off it in their own colours, Delon in blue halftone (no logo file: Comacico, from IMDb's company credits; director from IMDb, as on the poster)
std('le-cercle-rouge-1970', ('grad', [(0, (30, 30, 34)), (.6, (10, 10, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.04, 0.17, 0.96, 0.3)], 90, cuts=[key_cut(lambda a: (_lum(a) > .8) | ((a[..., 0] > .6) & (a[..., 1] < .3)))]),
    photo=ph(0.5, 0.55, 0.8, 0.9), pb=(40, 170, 220), studio=['COMACICO'], scol=WHT, order='lPTCF', credit=['A FILM BY', 'JEAN-PIERRE MELVILLE'], ccol=WHT,
    ft='b', fcol=(200, 200, 204), fin=OLD, seed=1970)

# The Aristocats (1970): Disney, the white clamshell; the poster's white, its black THE ARISTOCATS cut off it, Duchess's face in the red diamond
disney('the-aristocats-1970', ('grad', [(0, (250, 200, 210)), (.5, (240, 170, 190)), (1, (200, 120, 150))]), fin=dict(CLAM, vivid=.15), ink=(40, 30, 40),
       title=LC([(0.07, 0.15, 0.91, 0.335)], 110, cuts=[comp_cut(lambda a: _lum(a) < .25, minf=.003)]),
       face=ph(.63, .32, .14, 1.4), lcol=(40, 30, 40))

# The Honeymoon Killers (1970): the poster's pink, its black THE HONEYMOON KILLERS lifted, the couple on the trunk (top-billed cast from IMDb)
std('the-honeymoon-killers-1970', ('grad', [(0, (244, 180, 196)), (.6, (220, 150, 170)), (1, (130, 70, 90))]), (20, 20, 20),
    [LC([(0.21, 0.864, 0.4, 0.914)], 40, cuts=[comp_cut(lambda a: _lum(a) < .3, minf=.2)]), LC([(0.1, 0.912, 0.79, 0.962)], 60, cuts=[key_cut(lambda a: _lum(a) < .3)])],
    tgap=8,
    photo=ph(0.5, 0.35, 0.86, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCSF', credit=['SHIRLEY STOLER', 'TONY LO BIANCO'], ccol=(20, 20, 20),
    stick=flow(dot, 74, ['CRIME'], (20, 20, 20), (244, 180, 196)), ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=RENTAL, seed=1970)

# A Clockwork Orange (1971): the poster's white, its orange A CLOCKWORK ORANGE with the black shadow cut off it in its own colours, Alex with the knife in the triangle
std('a-clockwork-orange-1971', ('grad', [(0, (248, 248, 248)), (.6, (230, 228, 224)), (1, (140, 130, 120))]), (240, 110, 20),
    LC([(0.185, 0.765, 0.81, 0.925)], 130, cuts=[key_cut(lambda a: ((a[..., 0] > .8) & (a[..., 1] > .25) & (a[..., 1] < .75) & (a[..., 2] < .35)) | (_lum(a) < .2))]),
    photo=ph(0.5, 0.3, 0.6, 1.2), pb=(240, 110, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A STANLEY KUBRICK', 'PRODUCTION'], ccol=(20, 20, 20),
    ft='d', vbox=(240, 110, 20), fcol=(20, 20, 20), fin=OLD, seed=1971)

# Straw Dogs (1971): the poster's white, its black stencil "STRAW DOGS" lifted, Dustin Hoffman behind the broken glasses (no logo file: Amerbroco, from IMDb's company credits)
std('straw-dogs-1971', ('grad', [(0, (246, 246, 246)), (.6, (226, 226, 226)), (1, (120, 120, 120))]), (20, 20, 20),
    L((0.105, 0.866, 0.895, 0.912), 70, (20, 20, 20), mode='dark'),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(20, 20, 20), studio=['AMERBROCO', 'PRODUCTIONS'], scol=(20, 20, 20), order='lPTCF', credit=['A SAM PECKINPAH', 'FILM'],
    ccol=(20, 20, 20), ft='e', fcol=(20, 20, 20), fin=OLD, seed=1971)

# The Cat o' Nine Tails (1971): the poster's yellow, its red script "Cat O'Nine Tails" keyed off it, the black cat with the woman on its back (director from IMDb)
std('the-cat-o-nine-tails-1971', ('grad', [(0, (250, 230, 40)), (.6, (240, 200, 20)), (1, (160, 120, 10))]), (210, 30, 30),
    L([(0.3, 0.686, 0.745, 0.744), (0.42, 0.742, 0.655, 0.796)], 80, (214, 32, 32), mode='key', key=(210, 40, 40), t=(70, 150), gapf=.25),
    photo=ph(0.75, 0.38, 0.5, 1.3), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCSF', credit=['A FILM BY', 'DARIO ARGENTO'], ccol=(20, 20, 20),
    stick=BAR('71 5530', top='GIALLO', fill=(236, 230, 210)), ft='b', fcol=(20, 20, 20), fin=RENTAL, seed=1971)

# The Last Picture Show (1971): the poster's white, its red slab-serif THE LAST PICTURE SHOW keyed off it, Cybill Shepherd and the boys (director from IMDb)
std('the-last-picture-show-1971', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (120, 120, 116))]), (190, 20, 30),
    L([(0.185, 0.055, 0.495, 0.142), (0.075, 0.145, 0.475, 0.232), (0.27, 0.232, 0.925, 0.32), (0.155, 0.322, 0.608, 0.41)], 76, (194, 22, 32), mode='key', key=(190, 30, 40), t=(70, 150), gapf=.22),
    photo=ph(0.5, 0.72, 0.9, 0.85), pb=(30, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['A PETER BOGDANOVICH', 'FILM'], ccol=(30, 30, 30),
    ft='c', fcol=(30, 30, 30), fin=OLD, seed=1971)

# The Murder of Fred Hampton (1971): the poster's black, its white stencil THE MURDER OF FRED HAMPTON lifted, the bullet holes in the wall (no logo file: The Film Group, Chicago, from IMDb's company credits)
std('the-murder-of-fred-hampton-1971', ('grad', [(0, (40, 40, 40)), (.6, (14, 14, 14)), (1, (2, 2, 2))]), (220, 220, 214),
    L([(0.005, 0.012, 0.93, 0.08), (0.0, 0.077, 0.985, 0.144)], 64, (226, 226, 220), mode='light', gapf=.25),
    photo=ph(0.5, 0.52, 0.86, 1.1), pb=(226, 226, 220), studio=['THE FILM GROUP'], scol=(226, 226, 220), order='lPTCF', credit=['A DOCUMENTARY BY', 'HOWARD ALK'],
    ccol=(226, 226, 220), ft='a', fcol=(190, 190, 186), fin=OLD, seed=1971)

# Walkabout (1971): the dusk sky, the poster's white spaced WALKABOUT lifted, the figure on the dune under the moon (no logo file: Max L. Raab Productions, from IMDb's company credits; director from IMDb)
std('walkabout-1971', ('grad', [(0, (60, 70, 100)), (.6, (40, 34, 40)), (1, (10, 8, 6))]), WHT,
    LC([(0.52, 0.425, 0.975, 0.47)], 64, cuts=[key_cut(lambda a: (_lum(a) > .62) & (_sat(a) < .2))]),
    photo=ph(0.5, 0.7, 0.86, 0.75), pb=(240, 150, 60), studio=['MAX L. RAAB', 'PRODUCTIONS'], scol=WHT, order='lPTCF', credit=['A NICOLAS ROEG', 'FILM'], ccol=WHT,
    ft='d', fcol=(200, 200, 210), fin=OLD, seed=1971)

# Willy Wonka & the Chocolate Factory (1971): the candy colours, the poster's gold WILLY WONKA & THE CHOCOLATE FACTORY cut off the sky in its own colours, Gene Wilder in the top hat (no logo file: Wolper Pictures, from IMDb's company credits)
std('willy-wonka-the-chocolate-factory-1971', ('grad', [(0, (120, 60, 140)), (.6, (70, 30, 90)), (1, (20, 8, 30))]), (250, 220, 60),
    LC([(0.04, 0.035, 0.8, 0.255)], 130, outline=((60, 30, 10), 2), cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .5) & (a[..., 2] < .6) & (a[..., 0] > a[..., 2] + .25), minf=.02, close=3)]),
    photo=ph(0.7, 0.6, 0.6, 1.3), pb=(250, 220, 60), studio=['WOLPER PICTURES'], scol=(250, 220, 60), order='lPTF', dotst=('FAMILY', (250, 220, 60), (70, 30, 90)), ft='a', vbox=(250, 220, 60), vink=(70, 30, 90), fcol=(220, 200, 230), fin=OLD, seed=1971)

# The Crimes of the Black Cat (1972): the poster's orange, its yellow The Crimes of the Black Cat cut off it in its own colours, the black cat over the torn photographs (no logo file: Compagnia Cinematografica Champion, from IMDb's company credits)
std('the-crimes-of-the-black-cat-1972', ('grad', [(0, (250, 180, 30)), (.6, (230, 130, 10)), (1, (120, 50, 0))]), (250, 230, 60),
    LC([(0.48, 0.43, 0.84, 0.735)], 170, outline=((30, 14, 4), 2.2), cuts=[key_cut(lambda a: (a[..., 0] > .85) & (a[..., 1] > .6) & (a[..., 2] < .35))]),
    photo=ph(0.3, 0.45, 0.6, 1.4), pb=(30, 14, 4), studio=['CHAMPION'], scol=(30, 14, 4), order='lPTSF', stick=RWD(fill=(250, 240, 210)),
    ft='e', fcol=(40, 20, 6), fin=RENTAL, seed=1972)

# The Getaway (1972): the poster's dark grey, its yellow THE GETAWAY keyed off it, the gun on the papers
std('the-getaway-1972', ('grad', [(0, (60, 60, 60)), (.6, (24, 24, 24)), (1, (4, 4, 4))]), (240, 220, 60),
    L((0.055, 0.138, 0.94, 0.224), 76, (242, 222, 62), mode='key', key=(235, 215, 70), t=(70, 150)),
    photo=ph(0.5, 0.58, 1.0, 0.75), pb=(242, 222, 62), lg=WHT, lw=.55, order='LPTCF', credit=['STEVE McQUEEN', 'ALI MacGRAW'], ccol=WHT,
    ft='b', fcol=(200, 200, 196), fin=OLD, seed=1972)

# The Godfather (1972): a 2-tape box; black, the poster's white The Godfather with the puppeteer's hand lifted, Brando with the cat
std('the-godfather-1972', ('grad', [(0, (30, 26, 24)), (.6, (10, 8, 8)), (1, (2, 2, 2))]), WHT,
    L((0.33, 0.745, 0.76, 0.928), 190, WHT, mode='light'),
    photo=ph(0.5, 0.32, 0.86, 0.9), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=TWOST((200, 30, 30), WHT),
    ft='b', fcol=(200, 196, 190), fin=OLD, seed=1972, **TWO)

# The Harder They Come (1972): the poster's sunset colours, THE HARDER THEY COME typeset in heavy rounded capitals in its rainbow, line by line (typeset: the poster's title is a 3-D rainbow block whose letters run into each other and break into stripes in every cut; two tried), Jimmy Cliff with the guns (no logo file: International Films, from IMDb's company credits)
std('the-harder-they-come-1972', ('grad', [(0, (250, 230, 60)), (.5, (240, 120, 40)), (1, (120, 30, 60))]), (40, 30, 90),
    TT([('THE', (220, 40, 40)), ('HARDER', (240, 140, 20)), ('THEY', (60, 150, 60)), ('COME', (60, 60, 170))], 'popb', 80, sp=.3, outline=((30, 20, 40), 2)),
    photo=ph(0.5, 0.55, 0.9, 0.95), pb=(40, 30, 90), studio=['INTERNATIONAL FILMS'], scol=(40, 30, 90), order='lPTF', ft='e', fcol=(40, 30, 90), fin=OLD, seed=1972)

# The Ruling Class (1972): the poster's dark leaves, its white script The Ruling Class lifted, Peter O'Toole under the top hat (no logo file: Keep Films, from IMDb's company credits)
std('the-ruling-class-1972', ('grad', [(0, (30, 50, 40)), (.6, (10, 18, 14)), (1, (2, 4, 2))]), WHT,
    LC([(0.05, 0.715, 0.27, 0.835), (0.06, 0.845, 0.94, 0.948)], 110, gapf=.2, valign='base', cuts=[comp_cut(lambda a: _lum(a) > .8, minf=.02)] * 2),
    photo=ph(0.5, 0.4, 0.8, 1.0), pb=WHT, studio=['KEEP FILMS'], scol=WHT, order='lPTF', ft='d', fcol=(200, 210, 204), fin=OLD, seed=1972)

# Amarcord (1973): the poster's painted blues and reds, its white AMARCORD on the black sign cut off it whole, the townsfolk at the tobacconist's (no logo file: F.C. Produzioni, from IMDb's company credits)
std('amarcord-1973', ('grad', [(0, (60, 140, 200)), (.6, (150, 40, 40)), (1, (50, 12, 12))]), WHT,
    LC([(0.27, 0.12, 0.73, 0.26)], 120, cuts=[plate_cut(lambda a: _lum(a) < .25)]),
    photo=ph(0.5, 0.6, 1.0, 0.85), pb=WHT, studio=['F.C. PRODUZIONI'], scol=WHT, order='lPTCF', credit=['UN FILM DI', 'FEDERICO FELLINI'], ccol=WHT,
    ft='a', vbox=WHT, vink=(150, 40, 40), fcol=(240, 220, 210), fin=OLD, seed=1973)

# F for Fake (1973): black, the poster's white F for FAKE (Orson Welles's in script over it) lifted, Welles's hand with the cigar (no logo file: Les Films de l'Astrophore, from IMDb's company credits)
std('f-for-fake-1973', ('grad', [(0, (40, 40, 44)), (.6, (12, 12, 14)), (1, (2, 2, 2))]), WHT,
    L((0.36, 0.295, 0.76, 0.44), 110, WHT, mode='light', speck=0),
    photo=ph(0.4, 0.6, 0.8, 0.85), pb=WHT, studio=["LES FILMS DE", "L'ASTROPHORE"], scol=WHT, order='lPTF', ft='c', fcol=(200, 200, 204), fin=OLD, seed=1973)

# Flesh for Frankenstein (1973): the poster's white, its orange-red dripping FLESH FOR FRANKENSTEIN keyed off it, the faces on the platter (no logo file: Champion, from IMDb's company credits)
std('flesh-for-frankenstein-1973', ('grad', [(0, (246, 244, 240)), (.6, (226, 222, 214)), (1, (140, 120, 100))]), (240, 80, 40),
    L([(0.2, 0.728, 0.762, 0.812), (0.055, 0.815, 0.948, 0.948)], 90, (242, 82, 42), mode='key', key=(240, 90, 50), t=(70, 150), gapf=.25),
    photo=ph(0.5, 0.35, 0.86, 1.0), pb=(242, 82, 42), studio=['CHAMPION'], scol=(40, 40, 40), order='lPTSF', stick=PRC(['$1.99', 'HORROR']),
    ft='b', fcol=(40, 40, 40), fin=RENTAL, seed=1973)

# Mean Streets (1973): the poster's red and white, its black blocky MEAN STREETS lifted, the gun hand among the tenements (no logo file: Warner Bros., from IMDb's company credits; director from IMDb)
std('mean-streets-1973', ('grad', [(0, (240, 50, 30)), (.6, (190, 30, 20)), (1, (80, 10, 6))]), (20, 20, 20),
    LC([(0.22, 0.68, 0.82, 0.875)], 120, cuts=[plate_cut(lambda a: _lum(a) > .85)]),
    photo=ph(0.5, 0.25, 0.86, 0.85), pb=(20, 20, 20), studio=['WARNER BROS.'], scol=(20, 20, 20), order='lPTCF', credit=['A MARTIN SCORSESE', 'PICTURE'], ccol=(20, 20, 20),
    ft='c', fcol=(240, 220, 210), fin=OLD, seed=1973)

# Paper Moon (1973): the poster's navy, its white PAPER MOON lifted, Tatum and Ryan O'Neal on the paper moon
std('paper-moon-1973', ('grad', [(0, (20, 30, 100)), (.6, (10, 14, 60)), (1, (2, 4, 20))]), WHT,
    LC([(0.1, 0.083, 0.9, 0.158)], 80, cuts=[key_cut(lambda a: _lum(a) > .8)]),
    photo=ph(0.45, 0.58, 0.5, 1.4), pb=WHT, lg=WHT, lw=.55, order='LTPF', ft='e', fcol=(200, 206, 230), fin=OLD, seed=1973)

# Papillon (1973): the poster's white, its blue PAPILLON keyed off it, McQueen and Hoffman in chains (no logo file: Les Films Corona, from IMDb's company credits)
std('papillon-1973', ('grad', [(0, (246, 248, 250)), (.6, (220, 230, 240)), (1, (120, 140, 160))]), (20, 110, 200),
    L((0.15, 0.144, 0.85, 0.255), 90, (22, 112, 204), mode='key', key=(20, 110, 200), t=(70, 150)),
    photo=ph(0.6, 0.55, 0.8, 0.9), pb=(22, 112, 204), studio=['LES FILMS CORONA'], scol=(30, 40, 60), order='lTPF', ft='a', vbox=(22, 112, 204), fcol=(30, 40, 60), fin=OLD, seed=1973)

# Robin Hood (1973): Disney, the white clamshell; the forest green, the poster's green ROBIN HOOD with its gold keyline cut off the banner in its own colours, Robin's face in the red diamond
disney('robin-hood-1973', ('grad', [(0, (40, 110, 60)), (.5, (70, 150, 80)), (1, (20, 60, 30))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.115, 0.468, 0.875, 0.6)], 110, outline=((250, 220, 120), 2.4), cuts=[comp_cut(lambda a: a[..., 2] > a[..., 0] + .2, minf=.05)]),
       face=ph(.45, .18, .2, 1.4), lcol=WHT)

# The Cat Creature (1973): the poster's dark, its gold condensed THE CAT CREATURE cut off it in its own colours, the woman with the gold cat medallion (no logo file: Douglas S. Cramer Company, from IMDb's company credits)
std('the-cat-creature-1973', ('grad', [(0, (60, 40, 20)), (.6, (20, 14, 8)), (1, (2, 2, 2))]), (220, 170, 90),
    LC([(0.0, 0.73, 1.0, 0.93)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .35) & (a[..., 0] > a[..., 2] + .1), minf=.05, close=3)]),
    photo=ph(0.5, 0.35, 0.7, 1.15), pb=(220, 170, 90), studio=['DOUGLAS S. CRAMER', 'COMPANY'], scol=(220, 170, 90), order='lPTF', ft='d', fcol=(200, 190, 170), fin=RENTAL, seed=1973)

# The Sting (1973): the poster's white, its maroon THE STING keyed off it, Newman and Redford in the frame (director from IMDb)
std('the-sting-1973', ('grad', [(0, (246, 242, 234)), (.6, (226, 218, 204)), (1, (140, 120, 100))]), (140, 40, 40),
    L((0.06, 0.125, 0.96, 0.235), 66, (144, 42, 42), mode='key', key=(140, 50, 50), t=(70, 150)),
    photo=ph(0.5, 0.62, 0.86, 0.95), pb=(144, 42, 42), lg=(40, 30, 26), lw=.55, order='LPTCF', credit=['PAUL NEWMAN', 'ROBERT REDFORD'], ccol=(40, 30, 26),
    ft='b', fcol=(40, 30, 26), fin=OLD, seed=1973)

# Blood for Dracula (1974): black, the poster's white thin BLOOD for DRACVLA lifted, the red hands and the face (no logo file: Champion, from IMDb's company credits)
std('blood-for-dracula-1974', ('grad', [(0, (60, 14, 14)), (.6, (18, 4, 4)), (1, (2, 2, 2))]), WHT,
    L((0.035, 0.858, 0.978, 0.944), 76, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.3, 0.9, 1.0), pb=(220, 30, 30), studio=['CHAMPION'], scol=WHT, order='lPTF', ft='e', fcol=(200, 190, 190), fin=OLD, seed=1974)

# Bring Me the Head of Alfredo Garcia (1974): black, the poster's white serif "BRING ME THE HEAD OF ALFREDO GARCIA" lifted line by line into one, the gold watch and crossed swords (director from IMDb)
std('bring-me-the-head-of-alfredo-garcia-1974', ('grad', [(0, (60, 40, 20)), (.6, (18, 12, 6)), (1, (2, 2, 2))]), WHT,
    LC([(0.65, 0.622, 0.925, 0.664), (0.578, 0.662, 0.94, 0.702), (0.545, 0.7, 0.96, 0.741), (0.554, 0.74, 0.975, 0.78), (0.56, 0.778, 0.963, 0.82)], 60, gapf=.2, valign='base', margin=0, cuts=[comp_cut(lambda a: (_lum(a) > .82) & (_sat(a) < .2), minf=.12)] * 5),
    photo=ph(0.37, 0.785, 0.36, 0.95), pb=(220, 180, 80), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(210, 200, 186), fin=OLD, seed=1974)

# Chinatown (1974): the poster's yellow, its crimson script Chinatown keyed off it, Faye Dunaway's face in the smoke
std('chinatown-1974', ('grad', [(0, (252, 220, 70)), (.6, (240, 190, 40)), (1, (160, 110, 10))]), (180, 20, 40),
    L((0.255, 0.627, 0.995, 0.818), 120, (184, 22, 42), mode='key', key=(180, 30, 50), t=(70, 150)),
    photo=ph(0.6, 0.18, 0.8, 0.7), pb=(184, 22, 42), lg=(184, 22, 42), lw=.55, order='LPTCSF', credit=['JACK NICHOLSON', 'FAYE DUNAWAY'], ccol=(60, 30, 20),
    stick=flow(dot, 74, ['NOIR'], (184, 22, 42), WHT), ft='a', vbox=(184, 22, 42), fcol=(60, 30, 20), fin=OLD, seed=1974)

# Murder on the Orient Express (1974): the poster's pale blue, its red MURDER ON THE ORIENT EXPRESS keyed off it, the suspects' faces
std('murder-on-the-orient-express-1974', ('grad', [(0, (226, 236, 240)), (.6, (190, 210, 220)), (1, (90, 110, 120))]), (190, 30, 30),
    L([(0.145, 0.098, 0.855, 0.182), (0.064, 0.188, 0.937, 0.256)], 70, (194, 32, 32), mode='key', key=(190, 40, 40), t=(70, 150), gapf=.25),
    photo=ph(0.48, 0.55, 0.8, 1.05), pb=(30, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['A SIDNEY LUMET', 'FILM'], ccol=(30, 30, 30),
    ft='c', fcol=(30, 30, 30), fin=OLD, seed=1974)

# The Conversation (1974): the poster's grey band, its dark-red "THE CONVERSATION" lifted, Gene Hackman with the headphones (no logo file: The Directors Company, from IMDb's company credits)
std('the-conversation-1974', ('grad', [(0, (110, 40, 30)), (.6, (50, 16, 12)), (1, (10, 4, 2))]), (226, 220, 210),
    LC([(0.095, 0.885, 0.905, 0.932)], 64, cuts=[key_cut(lambda a: _lum(a) < .5)], outline=((226, 220, 210), 3)),
    photo=ph(0.5, 0.3, 0.86, 0.9), pb=(226, 220, 210), studio=['THE DIRECTORS', 'COMPANY'], scol=(226, 220, 210), order='lPTF', ft='d', fcol=(220, 200, 190), fin=OLD, seed=1974)

# The Godfather Part II (1974): a 2-tape box; black, the poster's white The Godfather Part II with the puppeteer's hand lifted, Pacino in the chair
std('the-godfather-part-ii-1974', ('grad', [(0, (30, 26, 24)), (.6, (10, 8, 8)), (1, (2, 2, 2))]), WHT,
    L((0.325, 0.722, 0.675, 0.922), 190, WHT, mode='light'),
    photo=ph(0.5, 0.27, 0.86, 0.6), pb=(200, 30, 30), lg=WHT, lw=.5, order='LTPCSF', credit=['AL PACINO', 'ROBERT DE NIRO'], ccol=WHT, stick=TWOST((200, 30, 30), WHT),
    ft='c', fcol=(200, 196, 190), fin=OLD, seed=1974, **TWO)

# Dog Day Afternoon (1975): the poster's white, its red DOG DAY AFTERNOON keyed off it, Pacino's drawn face (no logo file: Warner Bros., from IMDb's company credits)
std('dog-day-afternoon-1975', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (130, 130, 126))]), (210, 30, 30),
    L([(0.32, 0.456, 0.965, 0.52), (0.035, 0.516, 0.958, 0.578)], 76, (214, 32, 32), mode='key', key=(210, 40, 40), t=(70, 150), gapf=.25),
    photo=ph(0.5, 0.25, 0.86, 0.75), pb=(20, 20, 20), studio=['WARNER BROS.'], scol=(20, 20, 20), order='lPTF', ft='a', vbox=(214, 32, 32), fcol=(20, 20, 20), fin=OLD, seed=1975)

# Jaws (1975): the poster's white into the sea, its red JAWS keyed off it, the shark rising to the swimmer under the title
std('jaws-1975', ('grad', [(0, (246, 246, 246)), (.35, (90, 170, 210)), (1, (10, 50, 90))]), (210, 40, 50),
    L((0.123, 0.066, 0.877, 0.224), 120, (214, 42, 52), mode='key', key=(205, 45, 55), t=(70, 150)),
    photo=ph(0.5, 0.75, 0.8, 1.0), pb=WHT, lg=(214, 42, 52), lw=.55, order='LTPSF', stick=BAR('75 0620', top='THRILLER', fill=(236, 234, 220)),
    ft='e', vbox=(214, 42, 52), fcol=(220, 230, 240), fin=RENTAL, seed=1975)

# Monty Python and the Holy Grail (1975): the poster's cream, its gold swash Monty Python AND THE Holy Grail keyed off it, Arthur and the knights (no logo file in type: Python (Monty) Pictures)
std('monty-python-and-the-holy-grail-1975', ('grad', [(0, (246, 240, 224)), (.6, (230, 220, 196)), (1, (150, 130, 90))]), (200, 150, 30),
    L([(0.06, 0.083, 0.945, 0.28), (0.08, 0.282, 0.922, 0.376)], 110, (196, 146, 30), mode='key', key=(200, 150, 40), t=(70, 160), gapf=.2),
    photo=ph(0.5, 0.75, 1.0, 0.75), pb=(140, 90, 30), lg=(140, 90, 30), lw=.6, order='LPTSF', stick=RWD(),
    ft='b', fcol=(80, 60, 30), fin=RENTAL, seed=1975)

# One Flew Over the Cuckoo's Nest (1975): the poster's white, its black ONE FLEW OVER / THE CUCKOO'S NEST (the red O of CUCKOO'S kept) cut off it, Nicholson grinning in the beanie (no logo file: Fantasy Films, from IMDb's company credits)
std('one-flew-over-the-cuckoo-s-nest-1975', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (130, 130, 126))]), (20, 20, 20),
    [LC([(0.13, 0.074, 0.9, 0.14)], 64, margin=0, cuts=[key_cut(lambda a: _lum(a) < .35)]), LC([(0.02, 0.138, 0.98, 0.204)], 64, margin=0, cuts=[key_cut(lambda a: (_lum(a) < .35) | ((a[..., 0] > .6) & (a[..., 1] < .3)))])],
    tgap=8, photo=ph(0.48, 0.78, 0.8, 0.85), pb=(200, 30, 30), studio=['FANTASY FILMS'], scol=(20, 20, 20), order='lTPF', ft='c', fcol=(20, 20, 20), fin=OLD, seed=1975)

# Marathon Man (1976): black, MARATHON MAN typeset in heavy condensed capitals in white (typeset: the poster prints its title three times over, overlapping, with Hoffman's face cut through it, so no clean line can be lifted; two tried), Dustin Hoffman's face behind the gun
std('marathon-man-1976', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    T('MARATHON MAN', 'intbk', 80, WHT),
    photo=ph(0.6, 0.415, 0.42, 0.6), pb=WHT, lg=WHT, lw=.55, order='LPTF', ft='d', fcol=(200, 200, 200), fin=OLD, seed=1976)

# Murder by Death (1976): black, the poster's yellow Murder by Death keyed off it, the detectives at the gate of the house
std('murder-by-death-1976', ('grad', [(0, (40, 34, 30)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (250, 220, 40),
    L((0.03, 0.83, 0.98, 0.932), 100, (252, 222, 42), mode='key', key=(245, 215, 50), t=(70, 150)),
    photo=ph(0.5, 0.45, 1.0, 0.6), pb=(250, 220, 40), lg=WHT, lw=.55, order='LPTF', dotst=('COMEDY', (250, 220, 40), (12, 10, 8)), ft='a', vbox=(250, 220, 40), vink=(12, 10, 8), fcol=(200, 196, 190), fin=OLD, seed=1976)

# Network (1976): the poster's white, its black italic NETWORK cut off it, the television set with the lightning bolt
std('network-1976', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (120, 120, 116))]), (20, 20, 20),
    LC([(0.15, 0.776, 0.85, 0.858)], 96, cuts=[key_cut(lambda a: _lum(a) < .35)]),
    photo=ph(0.5, 0.32, 0.8, 0.8), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF',
    ft='b', fcol=(20, 20, 20), fin=OLD, seed=1976)

# Rocky (1976): the poster's white, its black ROCKY cut off it, Rocky and Adrian walking hand in hand under the title
std('rocky-1976', ('grad', [(0, (246, 246, 244)), (.6, (226, 226, 222)), (1, (120, 120, 116))]), (20, 20, 20),
    LC([(0.068, 0.11, 0.926, 0.236)], 110, margin=0, cuts=[comp_cut(lambda a: _lum(a) < .35, minf=.2)]),
    photo=ph(0.5, 0.56, 0.62, 1.4), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LTPSF', stick=PRC(['$1.99', 'DRAMA']),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=RENTAL, seed=1976)

# Taxi Driver (1976): the poster's yellow cab, its red TAXI DRIVER keyed off the yellow band, De Niro walking past the cab
std('taxi-driver-1976', ('grad', [(0, (252, 214, 30)), (.55, (236, 190, 20)), (1, (120, 90, 6))]), (190, 30, 30),
    L((0.125, 0.872, 0.88, 0.935), 84, (190, 30, 30), mode='key', key=(190, 40, 40), t=(70, 150)),
    photo=ph(0.5, 0.32, 0.5, 1.4), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF', ft='a', vbox=(190, 30, 30), fcol=(20, 20, 20), fin=OLD, seed=1976)

# The Man Who Fell to Earth (1976): black, the poster's white THE MAN WHO FELL TO EARTH lifted into one line, Bowie in the circle (no logo file: British Lion, from IMDb's company credits)
std('the-man-who-fell-to-earth-1976', ('grad', [(0, (40, 70, 110)), (.6, (12, 20, 34)), (1, (2, 2, 4))]), WHT,
    L([(0.425, 0.741, 0.572, 0.771), (0.047, 0.775, 0.958, 0.819), (0.2, 0.823, 0.795, 0.868)], 74, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.3, 0.52, 1.0), pb=(110, 180, 230), studio=['BRITISH LION'], scol=WHT, order='lPTF', ft='c', fcol=(200, 210, 220), fin=OLD, seed=1976)

# The Tenant (1976): the poster's pale grey, its crimson stacked THE / TENANT (the falling man cut through the E) keyed off it, the gilt mirror (no logo file: Marianne Productions, from IMDb's company credits)
std('the-tenant-1976', ('grad', [(0, (232, 232, 230)), (.6, (210, 210, 206)), (1, (110, 110, 106))]), (128, 0, 50),
    L([(0.36, 0.8, 0.63, 0.876), (0.36, 0.874, 0.63, 0.91)], 96, (128, 0, 50), mode='key', key=(128, 0, 50), t=(70, 150), valign='base', speck=0, gapf=.12),
    photo=ph(0.5, 0.3, 0.46, 1.4), pb=(190, 150, 40), studio=['MARIANNE', 'PRODUCTIONS'], scol=(128, 0, 50), order='lPTCF', credit=['UN FILM DE', 'ROMAN POLANSKI'], ccol=(30, 30, 30),
    ft='e', fcol=(30, 30, 30), fin=OLD, seed=1976)

# Annie Hall (1977): the poster's white, its thin black "ANNIE HALL" lifted (the quotes kept), Diane Keaton and Woody Allen under the title
std('annie-hall-1977', ('grad', [(0, (246, 246, 244)), (.6, (230, 228, 222)), (1, (130, 128, 120))]), (20, 20, 20),
    LC([(0.068, 0.815, 0.625, 0.888)], 84, cuts=[key_cut(lambda a: _lum(a) < .4)]),
    photo=ph(0.6, 0.38, 0.58, 1.6), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LTPF',
    ft='b', fcol=(20, 20, 20), fin=OLD, seed=1977)

# Close Encounters of the Third Kind (1977): the night sky, the poster's blue CLOSE ENCOUNTERS and its small OF THE THIRD KIND cut off it in their own colours, the mothership's lights
std('close-encounters-of-the-third-kind-1977', ('grad', [(0, (60, 30, 10)), (.5, (20, 10, 6)), (1, (2, 4, 10))]), (110, 200, 230),
    LC([(0.038, 0.56, 0.96, 0.604), (0.345, 0.618, 0.655, 0.636)], 70, valign='base', margin=0, cuts=[comp_cut(lambda a: (_lum(a) > .3) & (a[..., 2] >= a[..., 0]), minf=.02, close=3)] * 2),
    photo=ph(0.5, 0.3, 0.9, 0.62), pb=(240, 160, 60), lg=WHT, lw=.55, order='LPTCF', credit=['A STEVEN SPIELBERG', 'FILM'], ccol=(200, 220, 230),
    ft='d', fcol=(200, 210, 220), fin=OLD, seed=1977)

# High Anxiety (1977): the poster's white, its red HIGH ANXIETY keyed off it, Mel Brooks falling into the spiral
std('high-anxiety-1977', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (214, 30, 30),
    L((0.135, 0.143, 0.86, 0.202), 84, (214, 30, 30), mode='key', key=(214, 40, 40), t=(70, 150)),
    photo=ph(0.5, 0.52, 0.56, 1.0), pb=(214, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTSF', stick=RWD(fill=(250, 226, 60)),
    ft='d', fcol=(30, 30, 30), fin=RENTAL, seed=1977)

# Star Wars (1977): Lucasfilm, a slipcase; the starfield, the poster's white stacked STAR / WARS cut into one line, Luke and Leia under the lightsaber
std('star-wars-1977', ('grad', [(0, (30, 40, 70)), (.6, (10, 14, 26)), (1, (60, 20, 10))]), WHT,
    LC([(0.274, 0.74, 0.746, 0.838), (0.16, 0.836, 0.842, 0.958)], 120, valign='base', margin=0, cuts=[key_cut(lambda a: _lum(a) > .8)] * 2),
    photo=ph(0.62, 0.45, 0.5, 1.2), pb=(240, 200, 120), lg=WHT, lw=.5, order='LPTF',
    ft='a', vbox=(220, 40, 30), fcol=(210, 210, 220), fin=RENTAL, seed=1977)

# Suspiria (1977): black, the poster's white Suspiria lifted, the dancer over the blood (no logo file: Seda Spettacoli, from IMDb's company credits)
std('suspiria-1977', ('grad', [(0, (120, 10, 14)), (.5, (30, 4, 4)), (1, (2, 2, 2))]), WHT,
    LC([(0.105, 0.56, 0.9, 0.775)], 110, cuts=[comp_cut(lambda a: _lum(a) > .75, minf=.05)]),
    photo=ph(0.62, 0.36, 0.5, 1.4), pb=(220, 20, 30), studio=['SEDA SPETTACOLI'], scol=WHT, order='lPTCF', credit=['UN FILM DI', 'DARIO ARGENTO'], ccol=WHT,
    dotst=('HORROR', (220, 20, 30), WHT), ft='c', fcol=(210, 190, 190), fin=OLD, seed=1977)

# That Obscure Object of Desire (1977): the poster's cream, its black serif That / Obscure / Object / Of Desire cut off it, line by line, into one, the face in the hand mirror (no logo file: Greenwich Film, from IMDb's company credits)
std('that-obscure-object-of-desire-1977', ('grad', [(0, (246, 240, 226)), (.6, (230, 222, 200)), (1, (140, 126, 96))]), (20, 20, 20),
    LC([(0.65, 0.635, 0.868, 0.715), (0.583, 0.682, 0.932, 0.762), (0.593, 0.732, 0.887, 0.812), (0.553, 0.786, 0.952, 0.866)], 70, valign='base', margin=0, gapf=.35, cuts=[comp_cut(lambda a: _lum(a) < .55, keep=lambda cx, cy: .25 < cy < .75, minf=.005, opn=1)] * 4),
    photo=ph(0.42, 0.4, 0.5, 1.0), pb=(150, 30, 40), studio=['GREENWICH FILM'], scol=(20, 20, 20), order='lPTF',
    ft='e', fcol=(30, 30, 30), fin=OLD, seed=1977)

# The Many Adventures of Winnie the Pooh (1977): Disney clamshell; the Hundred Acre Wood's greens, the cream lettering of the poster's wooden sign (The Many Adventures Of / WINNIE / The POOH) cut off it, The Many Adventures Of beside WINNIE The POOH, Pooh's face in the diamond
disney('the-many-adventures-of-winnie-the-pooh-1977', ('grad', [(0, (70, 130, 60)), (.5, (110, 160, 80)), (1, (40, 80, 40))]), fin=dict(CLAM, vivid=.2),
       title=[LC([(0.16, 0.2, 0.84, 0.283), (0.185, 0.282, 0.84, 0.355)], 110, valign='base', margin=0, outline=((62, 42, 20), 3), cuts=[key_cut(lambda a: (_lum(a) > .7) & (_sat(a) < .35))] * 2),
              LC([(0.155, 0.15, 0.855, 0.195)], 40, margin=0, outline=((62, 42, 20), 3), cuts=[key_cut(lambda a: (_lum(a) > .7) & (_sat(a) < .35))])],
       face=ph(.44, .585, .17, 1.4), lcol=WHT)

# The Rescuers (1977): Disney clamshell; the night-blue of the poster, its yellow The RESCUERS cut off it in its own colours, Miss Bianca's face in the diamond
disney('the-rescuers-1977', ('grad', [(0, (20, 60, 140)), (.5, (40, 110, 200)), (1, (10, 40, 100))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.15, 0.045, 0.82, 0.205)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .5) & (a[..., 2] < .45), minf=.03, close=3)], outline=((120, 30, 90), 2.4)),
       face=ph(.43, .35, .17, 1.4), lcol=WHT)

# National Lampoon's Animal House (1978): the poster's white, its red outlined ANIMAL HOUSE keyed off it, the Delta house in uproar
std('animal-house-1978', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (214, 30, 30),
    L((0.205, 0.798, 0.795, 0.84), 84, (214, 30, 30), mode='key', key=(214, 40, 40), t=(70, 160)),
    photo=ph(0.5, 0.42, 0.86, 1.2), pb=(214, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTF', ft='a', vbox=(214, 30, 30), fcol=(30, 30, 30), fin=RENTAL, seed=1978)

# Autumn Sonata (1978): the poster's painted ochre, its dark serif Autumn / Sonata cut off it into one line, the piano in the sunlit room (no logo file: Personafilm, from IMDb's company credits)
std('autumn-sonata-1978', ('grad', [(0, (220, 180, 120)), (.6, (190, 140, 80)), (1, (90, 60, 30))]), (40, 30, 20),
    LC([(0.232, 0.686, 0.775, 0.75), (0.283, 0.772, 0.732, 0.836)], 84, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: _lum(a) < .32)] * 2),
    photo=ph(0.55, 0.25, 0.86, 0.75), pb=(60, 40, 20), studio=['PERSONAFILM'], scol=(40, 30, 20), order='lPTCF', credit=['EN FILM AV', 'INGMAR', 'BERGMAN'], ccol=(40, 30, 20),
    ft='b', fcol=(40, 30, 20), fin=OLD, seed=1978)

# The Brink's Job (1978): the bank-note green, THE BRINK'S JOB typeset in heavy capitals in steel grey (typeset: the poster's riveted chrome letters stand in a pile of silver bank notes of the same tone, so no colour or brightness test parts them), the gang under the falling money
std('the-brink-s-job-1978', ('grad', [(0, (40, 70, 50)), (.6, (16, 30, 20)), (1, (4, 8, 6))]), (210, 214, 220),
    T("THE BRINK'S JOB", 'intbk', 74, (214, 218, 224), outline=((40, 44, 50), 2)),
    photo=ph(0.5, 0.25, 0.9, 0.62), pb=(200, 204, 210), lg=WHT, lw=.55, order='LPTF',
    ft='c', fcol=(200, 210, 200), fin=OLD, seed=1978)

# The Cheap Detective (1978): the poster's navy, its white "THE CHEAP DETECTIVE" with the red shadow lifted, Peter Falk through the magnifying glass
std('the-cheap-detective-1978', ('grad', [(0, (30, 40, 110)), (.6, (12, 16, 50)), (1, (2, 4, 14))]), WHT,
    LC([(0.255, 0.655, 0.42, 0.746), (0.12, 0.744, 0.9, 0.862)], 84, valign='base', margin=0, cuts=[key_cut(lambda a: (_lum(a) > .55) | ((a[..., 0] > .55) & (a[..., 2] < .35)))] * 2),
    photo=ph(0.5, 0.33, 0.62, 1.0), pb=(200, 30, 30), lg=WHT, lw=.55, order='LPTF', ft='e', fcol=(200, 206, 230), fin=OLD, seed=1978)

# The Deer Hunter (1978): a 2-tape box; black, the poster's white THE DEER HUNTER lifted, De Niro's face under the red headband
std('the-deer-hunter-1978', ('grad', [(0, (40, 38, 36)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    L((0.078, 0.828, 0.917, 0.886), 80, WHT, mode='light'),
    photo=ph(0.55, 0.3, 0.86, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=TWOST((200, 30, 30), WHT),
    ft='d', fcol=(200, 196, 190), fin=OLD, seed=1978, **TWO)

# Watership Down (1978): the dusk sky, the poster's white script Watership Down lifted, Hazel's silhouette with the moonlit eye under the title (no logo file: Nepenthe Productions, from IMDb's company credits)
std('watership-down-1978', ('grad', [(0, (120, 130, 160)), (.5, (60, 70, 100)), (1, (14, 20, 30))]), WHT,
    L((0.28, 0.185, 0.96, 0.27), 90, WHT, mode='light', speck=0),
    photo=ph(0.42, 0.55, 0.6, 1.3), pb=(220, 200, 150), studio=['NEPENTHE', 'PRODUCTIONS'], scol=WHT, order='lTPF',
    ft='b', fcol=(220, 220, 230), fin=OLD, seed=1978)

# Alien (1979): black, the poster's spaced white A L I E N lifted, the egg splitting with green light
std('alien-1979', ('grad', [(0, (20, 30, 20)), (.6, (6, 8, 6)), (1, (0, 0, 0))]), WHT,
    L((0.08, 0.112, 0.92, 0.145), 60, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.45, 0.55, 1.2), pb=(150, 220, 80), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(190, 200, 190), fin=RENTAL, seed=1979)

# Apocalypse Now (1979): the poster's red sky, its white brushed Apocalypse Now cut off it, the sun setting on the river and the helicopters
std('apocalypse-now-1979', ('grad', [(0, (200, 60, 30)), (.5, (120, 20, 10)), (1, (20, 4, 2))]), WHT,
    LC([(0.095, 0.098, 0.932, 0.283)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .82) & (_sat(a) < .18), minf=.01)]),
    photo=ph(0.5, 0.42, 0.9, 0.6), pb=(250, 180, 60), lg=WHT, lw=.5, order='LPTCF', credit=['A FRANCIS FORD', 'COPPOLA FILM'], ccol=WHT,
    ft='a', vbox=(250, 180, 60), vink=(30, 10, 6), fcol=(240, 210, 190), fin=OLD, seed=1979)

# Kramer vs. Kramer (1979): the poster's white, its brown serif Kramer / vs. / Kramer cut off it into one line, the family photo under the title
std('kramer-vs-kramer-1979', ('grad', [(0, (246, 244, 240)), (.6, (230, 226, 218)), (1, (130, 124, 112))]), (80, 40, 20),
    LC([(0.195, 0.735, 0.79, 0.815), (0.41, 0.812, 0.61, 0.869), (0.195, 0.845, 0.79, 0.935)], 80, valign='base', margin=0, gapf=.3, cuts=[comp_cut(lambda a: _lum(a) < .35, keep=lambda cx, cy: .2 < cy < .9, minf=.05)] * 3),
    photo=ph(0.5, 0.42, 0.7, 1.1), pb=(80, 40, 20), lg=(80, 40, 20), lw=.55, order='LTPF',
    ft='c', fcol=(60, 40, 30), fin=OLD, seed=1979)

# The Warriors (1979): the night, the poster's red THE Warriors cut off it whole, the gangs of the city
std('the-warriors-1979', ('grad', [(0, (50, 30, 30)), (.6, (14, 8, 8)), (1, (2, 2, 2))]), (226, 30, 30),
    LC([(0.12, 0.13, 0.88, 0.335)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3) & (a[..., 2] < .35), minf=.03, close=3)]),
    photo=ph(0.5, 0.65, 0.9, 0.85), pb=(226, 30, 30), lg=WHT, lw=.5, order='LPTF', dotst=('ACTION', (226, 30, 30), WHT),
    ft='b', fcol=(210, 196, 190), fin=OLD, seed=1979)

# Vengeance Is Mine (1979): the poster's skin and shadow, its white brushed Vengeance is Mine cut off it, Ken Ogata's face above
std('vengeance-is-mine-1979', ('grad', [(0, (160, 110, 80)), (.6, (70, 40, 30)), (1, (14, 8, 6))]), WHT,
    LC([(0.08, 0.418, 0.92, 0.498)], 96, cuts=[comp_cut(lambda a: (_lum(a) > .86) & (_sat(a) < .14), minf=.02)]),
    photo=ph(0.6, 0.2, 0.62, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(230, 210, 200), fin=OLD, seed=1979)


# ---------------------------------------------------------------- the 1980s
# Airplane! (1980): the poster's sky blue, its red extruded AIRPLANE! cut off it whole and turned nearer level, the airliner with its knotted fuselage
std('airplane-1980', ('grad', [(0, (230, 240, 250)), (.4, (60, 140, 220)), (1, (10, 50, 120))]), (220, 30, 40),
    LC([(0.03, 0.13, 0.96, 0.475)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .4) & (a[..., 0] > a[..., 1] + .25), top=1, rot=10)]),
    photo=ph(0.5, 0.72, 0.9, 0.62), pb=(220, 30, 40), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.49', 'COMEDY']),
    ft='a', vbox=(220, 30, 40), fcol=(230, 236, 246), fin=RENTAL, seed=1980)

# Kagemusha (1980): the poster's gold and black, its white KAGEMUSHA lifted, the warlord in his armour
std('kagemusha-1980', ('grad', [(0, (180, 140, 40)), (.5, (60, 44, 14)), (1, (8, 6, 2))]), WHT,
    L((0.13, 0.615, 0.882, 0.688), 76, WHT, mode='light'),
    photo=ph(0.48, 0.3, 0.8, 1.0), pb=(230, 190, 60), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'AKIRA KUROSAWA'], ccol=(240, 220, 170),
    ft='c', fcol=(230, 210, 170), fin=OLD, seed=1980)

# Raging Bull (1980): black, the poster's red stencilled RAGING / BULL keyed off it into one line, De Niro's bruised face
std('raging-bull-1980', ('grad', [(0, (60, 60, 60)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), (214, 36, 40),
    L([(0.175, 0.728, 0.805, 0.811), (0.175, 0.814, 0.805, 0.895)], 96, (214, 36, 40), mode='key', key=(214, 40, 44), t=(70, 150), valign='base'),
    photo=ph(0.4, 0.3, 0.7, 0.9), pb=WHT, lg=WHT, lw=.5, order='LTPF',
    ft='b', vbox=(214, 36, 40), fcol=(210, 210, 210), fin=OLD, seed=1980)

# The Blues Brothers (1980): black, the white THE BLUES and BROTHERS cut off the poster's two mugshot boards, Jake and Elwood in their hats and shades
std('the-blues-brothers-1980', ('grad', [(0, (40, 40, 44)), (.6, (12, 12, 14)), (1, (2, 2, 2))]), WHT,
    LC([(0.1, 0.49, 0.2, 0.535), (0.13, 0.531, 0.512, 0.648), (0.548, 0.682, 0.985, 0.786)], 80, valign='base', margin=0, cuts=[comp_cut(lambda a: _lum(a) > .78, minf=.08)] * 3),
    photo=ph(0.5, 0.22, 0.86, 0.6), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(200, 200, 210), fin=RENTAL, seed=1980)

# The Empire Strikes Back (1980): Lucasfilm, a slipcase; deep blue, the poster's whole white STAR WARS / THE EMPIRE STRIKES BACK logo cut off it, Han and Leia's embrace
std('the-empire-strikes-back-1980', ('grad', [(0, (40, 60, 120)), (.6, (12, 20, 46)), (1, (4, 6, 16))]), WHT,
    LC([(0.19, 0.685, 0.81, 0.935)], 150, cuts=[comp_cut(lambda a: (_lum(a) > .78) & (_sat(a) < .3), minf=.004)]),
    photo=ph(0.62, 0.3, 0.6, 0.9), pb=(250, 180, 80), lg=WHT, lw=.5, order='LPTSF', stick=RWD(),
    ft='e', fcol=(200, 210, 230), fin=RENTAL, seed=1980)

# The Shining (1980): the poster's yellow, its black THE (the T and H made of the halftone of Danny's face) and SHiNiNG cut off it word by word, dots and all, and turned level, the halftone face again in the frame
std('the-shining-1980', ('grad', [(0, (252, 220, 20)), (.6, (240, 200, 10)), (1, (150, 110, 4))]), (20, 20, 20),
    LC([(0.13, 0.19, 0.79, 0.565), (0.12, 0.44, 0.83, 0.7)], 110, valign='base', margin=0, gapf=.3,
       cuts=[comp_cut(lambda a: _lum(a) < .4, keep=lambda cx, cy: .19 + .375 * cy < .56 - .1417 * (.13 + .66 * cx - .2), minf=0, opn=1, rot=-18),  # THE: everything above the line between the words, every dot
             pick_cut(lambda a: _lum(a) < .4, (0.12, 0.44, 0.83, 0.7), [(0.218, 0.627), (0.321, 0.606), (0.406, 0.598), (0.407, 0.553), (0.491, 0.573), (0.579, 0.567), (0.58, 0.52), (0.668, 0.538), (0.765, 0.519)], r=.02, rot=-18, margin=0)]),
    photo=ph(0.47, 0.27, 0.34, 1.0), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF',
    ft='a', vbox=(20, 20, 20), vink=(250, 220, 20), fcol=(20, 20, 20), fin=OLD, seed=1980)

# Raiders of the Lost Ark (1981): the temple's dark gold, the poster's orange INDIANA JONES and its white "and the RAIDERS of the LOST ARK", each cut off it in its own colours and run into one line, Indy with the whip
std('raiders-of-the-lost-ark-1981', ('grad', [(0, (120, 80, 30)), (.6, (50, 30, 10)), (1, (10, 6, 2))]), (250, 180, 40),
    LC([(0.07, 0.06, 0.95, 0.236), (0.42, 0.158, 0.635, 0.193), (0.29, 0.192, 0.875, 0.227), (0.49, 0.228, 0.885, 0.266)], 90, valign='base', margin=0, gapf=.25,
       cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 2] < .4) & (a[..., 0] > a[..., 2] + .35), minf=.01, close=3)] + [comp_cut(lambda a: (_lum(a) > .75) & (_sat(a) < .25), minf=.02)] * 3),
    photo=ph(0.45, 0.55, 0.7, 1.15), pb=(250, 180, 40), lg=WHT, lw=.5, order='LPTF',
    ft='c', fcol=(230, 200, 150), fin=RENTAL, seed=1981)

# The Fox and the Hound (1981): Disney clamshell; the forest's teal, the poster's cream The Fox and the Hound with its orange edge cut off it whole, Tod's face in the diamond
disney('the-fox-and-the-hound-1981', ('grad', [(0, (20, 80, 80)), (.5, (40, 120, 110)), (1, (10, 50, 50))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.2, 0.168, 0.765, 0.35)], 130, cuts=[comp_cut(lambda a: (_lum(a) > .62) | ((a[..., 0] > .7) & (a[..., 1] < .55) & (a[..., 2] < .35)), minf=.01, close=2)]),
       face=ph(.7, .575, .17, 1.4), lcol=WHT)

# Thief (1981): black, the poster's blue brushed Thief keyed off it, James Caan in the welding goggles under the sparks (director from IMDb)
std('thief-1981', ('grad', [(0, (30, 30, 34)), (.6, (10, 10, 12)), (1, (2, 2, 2))]), (60, 140, 230),
    LC([(0.23, 0.76, 0.74, 0.88)], 110, cuts=[key_cut(lambda a: (a[..., 2] > .45) & (a[..., 2] > a[..., 0] + .2))]),
    photo=ph(0.5, 0.36, 0.8, 1.05), pb=(240, 200, 120), lg=WHT, lw=.5, order='LPTCF', credit=['A MICHAEL MANN', 'FILM'], ccol=(150, 190, 240),
    dotst=('CRIME', (60, 140, 230), WHT), ft='b', fcol=(190, 196, 210), fin=OLD, seed=1981)

# Time Bandits (1981): the poster's sky blue, its white serif TIME / BANDITS lifted into one line, the galleon on the giant's hat
std('time-bandits-1981', ('grad', [(0, (60, 150, 230)), (.6, (20, 90, 190)), (1, (6, 30, 80))]), WHT,
    LC([(0.565, 0.08, 0.935, 0.255), (0.565, 0.262, 0.935, 0.386)], 100, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: (_lum(a) > .68) & (_sat(a) < .4))] * 2),
    photo=ph(0.25, 0.68, 0.5, 1.5), pb=(250, 220, 150), lg=WHT, lw=.5, order='LTPF',
    ft='d', fcol=(220, 230, 246), fin=OLD, seed=1981)

# E.T. the Extra-Terrestrial (1982): night blue, the poster's white E.T. and its small THE EXTRA-TERRESTRIAL lifted into one line, the bicycle crossing the moon
std('e-t-the-extra-terrestrial-1982', ('grad', [(0, (40, 60, 110)), (.6, (12, 18, 40)), (1, (2, 4, 12))]), WHT,
    L([(0.345, 0.79, 0.65, 0.917), (0.262, 0.933, 0.738, 0.957)], 110, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.25, 0.86, 0.8), pb=(220, 230, 250), lg=WHT, lw=.5, order='LPTSF', stick=BAR('82 0611', top='FAMILY', fill=(226, 232, 240)),
    ft='a', vbox=(60, 90, 160), fcol=(200, 210, 230), fin=RENTAL, seed=1982)

# Missing (1982): the poster's white, its dark-red typewritten missing. keyed off it, Jack Lemmon and Sissy Spacek
std('missing-1982', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (150, 30, 40),
    L((0.432, 0.468, 0.955, 0.53), 84, (150, 30, 40), mode='key', key=(150, 30, 40), t=(70, 160), speck=0),
    photo=ph(0.6, 0.76, 0.76, 0.75), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A FILM BY', 'COSTA-GAVRAS'], ccol=(30, 30, 30),
    ft='e', fcol=(30, 30, 30), fin=OLD, seed=1982)

# The Secret of NIMH (1982): the poster's bramble purple and gold, its red THE SECRET of N.I.M.H keyed off the white glow into one line, Mrs. Brisby before the Great Owl
std('the-secret-of-nimh-1982', ('grad', [(0, (60, 40, 110)), (.5, (30, 20, 60)), (1, (8, 6, 18))]), (214, 40, 36),
    LC([(0.435, 0.65, 0.525, 0.678), (0.335, 0.678, 0.662, 0.732), (0.455, 0.731, 0.505, 0.752), (0.338, 0.743, 0.662, 0.798)], 84, valign='base', margin=0, gapf=.25,
       outline=((250, 240, 220), 3), cuts=[key_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .35) & (a[..., 2] < .35))] * 4),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(250, 200, 60), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(220, 210, 230), fin=RENTAL, seed=1982)

# The Thing (1982): the poster's icy blue, its black ragged THE / THING cut off it into one line, the hooded figure blazing with light
std('the-thing-1982', ('grad', [(0, (180, 220, 240)), (.5, (60, 140, 200)), (1, (8, 30, 60))]), (12, 16, 24),
    LC([(0.4, 0.735, 0.62, 0.768), (0.03, 0.766, 0.94, 0.926)], 110, valign='base', margin=0, cuts=[comp_cut(lambda a: _lum(a) < .25, minf=.01)] * 2),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(12, 16, 24), lg=(12, 16, 24), lw=.55, order='LPTSF', dotst=('HORROR', (12, 16, 24), (180, 220, 240)),
    ft='d', fcol=(12, 16, 24), fin=RENTAL, seed=1982)

# Tootsie (1982): the poster's white, its black slab-serif Tootsie cut off it, Dorothy Michaels in red sequins before the flag
std('tootsie-1982', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (20, 20, 20),
    LC([(0.01, 0.835, 0.993, 0.945)], 110, cuts=[key_cut(lambda a: _lum(a) < .3)]),
    photo=ph(0.4, 0.42, 0.5, 1.6), pb=(200, 30, 40), lg=(20, 20, 20), lw=.55, order='LPTF', ft='a', vbox=(200, 30, 40), fcol=(20, 20, 20), fin=OLD, seed=1982)

# A Christmas Story (1983): the tree's green, the poster's red arched A CHRISTMAS STORY cut off it whole and turned level, Ralphie in his glasses
std('a-christmas-story-1983', ('grad', [(0, (30, 80, 40)), (.5, (16, 50, 24)), (1, (4, 16, 8))]), (210, 30, 30),
    LC([(0.12, 0.08, 0.9, 0.42)], 140, outline=((250, 236, 200), 3), cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3) & (a[..., 2] < .35), minf=.05, rot=-30)]),
    photo=ph(0.65, 0.6, 0.6, 0.9), pb=(210, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$1.99', 'FAMILY']),
    ft='c', fcol=(210, 230, 210), fin=RENTAL, seed=1983)

# Return of the Jedi (1983): Lucasfilm, a slipcase; black, the poster's whole white logo (STAR WARS over RETURN OF THE JEDI between its rules) cut off it, Luke with the lightsaber over the others
std('return-of-the-jedi-1983', ('grad', [(0, (30, 40, 80)), (.6, (10, 12, 28)), (1, (2, 2, 6))]), WHT,
    LC([(0.1, 0.786, 0.895, 0.908)], 130, cuts=[key_cut(lambda a: _lum(a) > .6)]),
    photo=ph(0.45, 0.3, 0.8, 0.95), pb=(120, 180, 250), lg=WHT, lw=.5, order='LTPF',
    ft='b', fcol=(200, 210, 230), fin=RENTAL, seed=1983)

# Videodrome (1983): black, the poster's white condensed VIDEODROME lifted, James Woods reaching out of the television's blue (no logo file: Filmplan International, from IMDb's company credits)
std('videodrome-1983', ('grad', [(0, (30, 60, 140)), (.5, (10, 20, 60)), (1, (2, 4, 14))]), WHT,
    LC([(0.015, 0.018, 0.98, 0.186)], 120, cuts=[key_cut(lambda a: _lum(a) > .75)]),
    photo=ph(0.75, 0.48, 0.42, 1.3), pb=(80, 160, 250), studio=['FILMPLAN', 'INTERNATIONAL'], scol=WHT, order='lPTCF', credit=['A DAVID CRONENBERG', 'FILM'], ccol=(170, 200, 250),
    ft='e', fcol=(190, 200, 230), fin=OLD, seed=1983)

# Beverly Hills Cop (1984): the poster's sky blue, its white BEVERLY HILLS and red script Cop cut off it into one line, Eddie Murphy with the pistol
std('beverly-hills-cop-1984', ('grad', [(0, (120, 200, 240)), (.5, (40, 150, 220)), (1, (10, 60, 110))]), WHT,
    LC([(0.1, 0.045, 0.9, 0.099), (0.285, 0.097, 0.725, 0.212)], 90, valign='base', margin=0, gapf=.2,
       cuts=[key_cut(lambda a: _lum(a) > .85), key_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3))]),
    photo=ph(0.35, 0.5, 0.56, 1.3), pb=WHT, lg=WHT, lw=.5, order='LPTF',
    ft='a', vbox=(220, 30, 30), fcol=(230, 240, 250), fin=RENTAL, seed=1984)

# Ghostbusters (1984): the poster's green night, its white GHOSTBUSTERS with the no-ghost O cut off it in its own colours, the ghost in the red sign
std('ghostbusters-1984', ('grad', [(0, (40, 120, 60)), (.5, (14, 50, 24)), (1, (2, 10, 4))]), WHT,
    LC([(0.06, 0.845, 0.94, 0.925)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .72) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.01)]),
    photo=ph(0.5, 0.2, 0.86, 0.75), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTCSF', credit=['BILL MURRAY', 'DAN AYKROYD'], ccol=WHT, stick=RWD(fill=(236, 122, 40), ink=(20, 16, 12)),
    ft='b', fcol=(200, 220, 200), fin=RENTAL, seed=1984)

# Stranger Than Paradise (1984): black, the poster's white STRANGER / THAN / PARADISE lifted into one line, Willie and Eva by the "Welcome to Florida" sign
std('stranger-than-paradise-1984', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    L([(0.155, 0.085, 0.985, 0.186), (0.563, 0.19, 0.985, 0.288), (0.236, 0.291, 0.985, 0.393)], 84, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.75, 0.9, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'JIM JARMUSCH'], ccol=WHT,
    ft='c', fcol=(200, 200, 200), fin=OLD, seed=1984)

# Streets of Fire (1984): the poster's red and black, its yellow STREETS OF FIRE plate cut off it in its own colours, Tom Cody with the rifle
std('streets-of-fire-1984', ('grad', [(0, (200, 40, 40)), (.5, (80, 14, 14)), (1, (10, 2, 2))]), (250, 210, 60),
    LC([(0.285, 0.862, 0.73, 0.968)], 96, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .4) & (a[..., 2] < .45), minf=.002, keep=lambda cx, cy: .02 < cy < .98)]),
    photo=ph(0.5, 0.32, 0.8, 0.95), pb=(60, 190, 210), lg=WHT, lw=.5, order='LTPF',
    ft='e', fcol=(240, 210, 200), fin=RENTAL, seed=1984)

# The Terminator (1984): the night, the poster's chrome THE TERMINATOR cut off it, Arnold in the sunglasses with the pistol
std('the-terminator-1984', ('grad', [(0, (40, 60, 120)), (.6, (10, 14, 34)), (1, (2, 2, 8))]), (200, 210, 240),
    LC([(0.405, 0.787, 0.565, 0.827), (0.045, 0.827, 0.96, 0.882)], 96, valign='base', margin=0, cuts=[comp_cut(lambda a: (_lum(a) > .42) & (a[..., 2] >= a[..., 0] - .05), minf=.02, close=2)] * 2),
    photo=ph(0.58, 0.3, 0.6, 1.05), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('84 1026', top='SCI-FI', fill=(220, 226, 236)),
    ft='d', fcol=(190, 200, 230), fin=RENTAL, seed=1984)

# This Is Spinal Tap (1984): the poster's black, its whole gold Spinal Tap logo (THIS IS and the umlaut too) cut off it in its own colours, the band as gold statues
std('this-is-spinal-tap-1984', ('grad', [(0, (40, 30, 20)), (.6, (12, 8, 4)), (1, (2, 2, 2))]), (240, 200, 90),
    LC([(0.1, 0.064, 0.912, 0.322)], 130, cuts=[comp_cut(lambda a: _lum(a) > .2, minf=.005, close=2)]),
    photo=ph(0.5, 0.65, 0.7, 1.0), pb=(240, 200, 90), lg=WHT, lw=.5, order='LPTCF', credit=['A ROB REINER', 'FILM'], ccol=(240, 210, 140),
    ft='a', vbox=(240, 200, 90), vink=(20, 14, 6), fcol=(220, 200, 160), fin=OLD, seed=1984)

# After Hours (1985): night, the poster's red neon script After Hours cut off it, Griffin Dunne pinned by the clock's hands (company from the logo file: Geffen)
std('after-hours-1985', ('grad', [(0, (30, 40, 90)), (.6, (10, 14, 36)), (1, (2, 2, 10))]), (240, 80, 70),
    LC([(0.08, 0.03, 0.985, 0.2)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] < .6) & (a[..., 2] < .6), minf=.01, keep=lambda cx, cy: cy < .8 or cx > .35)]),
    photo=ph(0.5, 0.65, 0.9, 0.85), pb=(240, 80, 70), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(200, 200, 230), fin=RENTAL, seed=1985)

# Back to the Future (1985): the night road, the poster's whole BACK TO THE FUTURE logo cut off it in its own colours, Marty checking his watch by the DeLorean
std('back-to-the-future-1985', ('grad', [(0, (30, 50, 110)), (.5, (12, 18, 46)), (1, (60, 20, 6))]), (250, 160, 40),
    LC([(0.055, 0.044, 0.468, 0.176)], 140, cuts=[comp_cut(lambda a: ((a[..., 0] > .55) & (a[..., 0] > a[..., 2] + .25)) | (_lum(a) > .88), minf=.005, close=2)]),
    photo=ph(0.55, 0.52, 0.7, 1.0), pb=(250, 160, 40), lg=WHT, lw=.5, order='LPTSF', stick=BAR('85 0703', top='SCI-FI', fill=(232, 228, 214)),
    ft='a', vbox=(250, 160, 40), vink=(30, 12, 4), fcol=(220, 210, 200), fin=RENTAL, seed=1985)

# Blood Simple (1985): black, the poster's neon BLOOD / SIMPLE (pink, blue and red tubes) cut off it into one line, the figure crawling in the headlights (no logo file: River Road Productions, from IMDb's company credits)
std('blood-simple-1985', ('grad', [(0, (40, 20, 50)), (.6, (12, 6, 16)), (1, (2, 2, 4))]), (240, 120, 160),
    LC([(0.115, 0.082, 0.886, 0.226), (0.115, 0.235, 0.878, 0.357)], 90, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: (_lum(a) > .25) & (a.max(-1) > .45))] * 2),
    photo=ph(0.5, 0.62, 0.86, 0.85), pb=(120, 200, 240), studio=['RIVER ROAD', 'PRODUCTIONS'], scol=(220, 200, 230), order='lPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(220, 200, 230),
    ft='b', fcol=(200, 190, 210), fin=OLD, seed=1985)

# Brazil (1985): charcoal, so the neon reads, its pink and blue neon script Brazil cut off it, Sam flying with the wings (no logo file: Embassy International Pictures, from IMDb's company credits)
std('brazil-1985', ('grad', [(0, (70, 70, 76)), (.5, (34, 34, 40)), (1, (6, 6, 8))]), (230, 90, 170),
    LC([(0.195, 0.12, 0.915, 0.315)], 120, outline=((250, 120, 200), 2.2), cuts=[comp_cut(lambda a: ((a[..., 0] > .6) & (a[..., 1] < .55) & (a[..., 2] > .45)) | ((a[..., 2] > .6) & (a[..., 0] < .45)), minf=.01, close=3)]),
    photo=ph(0.42, 0.55, 0.7, 1.1), pb=(220, 220, 226), studio=['EMBASSY', 'INTERNATIONAL'], scol=(220, 220, 226), order='lPTCF', credit=['A TERRY GILLIAM', 'FILM'], ccol=(220, 220, 226),
    dotst=('SCI-FI', (230, 90, 170), WHT), ft='d', fcol=(200, 200, 206), fin=OLD, seed=1985)

# Clue (1985): black, the poster's white Clue lifted, the mansion with the suspects in its windows
std('clue-1985', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.21, 0.045, 0.79, 0.145)], 110, cuts=[key_cut(lambda a: _lum(a) > .8)]),
    photo=ph(0.5, 0.55, 0.8, 1.2), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['TIM CURRY', 'EILEEN BRENNAN'], ccol=WHT,
    ft='e', vbox=(200, 30, 30), fcol=(200, 200, 200), fin=RENTAL, seed=1985)

# Pee-wee's Big Adventure (1985): the poster's white and sky-blue swirl, its red PEE-WEE'S / BIG ADVENTURE keyed off it into one line, Pee-wee leaping off his bike
std('pee-wee-s-big-adventure-1985', ('grad', [(0, (230, 244, 252)), (.5, (160, 214, 240)), (1, (60, 120, 170))]), (220, 30, 40),
    L([(0.2, 0.07, 0.81, 0.172), (0.25, 0.178, 0.77, 0.227)], 84, (220, 30, 40), mode='key', key=(220, 40, 44), t=(70, 160), valign='base', speck=0),
    photo=ph(0.55, 0.55, 0.8, 1.1), pb=(220, 30, 40), lg=(30, 30, 40), lw=.55, order='LPTSF', stick=RWD(fill=(250, 200, 220), ink=(110, 20, 60)),
    ft='b', fcol=(30, 30, 40), fin=RENTAL, seed=1985)

# Ran (1985): the poster's storm-blue sky, its red kanji and red serif RAN keyed off it, the riders on the plain below
std('ran-1985', ('grad', [(0, (80, 140, 170)), (.5, (30, 70, 100)), (1, (6, 20, 30))]), (220, 30, 30),
    L([(0.4, 0.16, 0.556, 0.247), (0.244, 0.255, 0.737, 0.455)], 120, (220, 30, 30), mode='key', key=(220, 30, 30), t=(70, 160), valign='mid', speck=0, gapf=.3),
    photo=ph(0.5, 0.82, 0.9, 0.4), pb=(220, 30, 30), lg=WHT, lw=.5, order='LTPF',
    ft='a', vbox=(220, 30, 30), fcol=(210, 220, 230), fin=OLD, seed=1985)

# Tampopo (1985): the poster's yellow, its red brushed TAMPOPO (rising in an arc on the poster) cut off it whole and turned level, the noodle bowl and its eaters
std('tampopo-1985', ('grad', [(0, (252, 230, 90)), (.5, (246, 210, 60)), (1, (160, 120, 20))]), (220, 40, 40),
    LC([(0.03, 0.015, 0.79, 0.36)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .35) & (a[..., 2] < .4), minf=.05, rot=-22)]),
    photo=ph(0.55, 0.62, 0.8, 0.9), pb=(220, 40, 40), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['A FILM BY', 'JUZO ITAMI'], ccol=(60, 30, 20),
    ft='c', fcol=(60, 30, 20), fin=OLD, seed=1985)

# The Black Cauldron (1985): Disney clamshell; the poster's night blue, its orange THE BLACK / CAULDRON cut off it into one line, Taran's face in the diamond
disney('the-black-cauldron-1985', ('grad', [(0, (30, 40, 90)), (.5, (50, 60, 120)), (1, (14, 18, 44))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.24, 0.698, 0.71, 0.786), (0.195, 0.785, 0.795, 0.87)], 110, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .5) & (a[..., 2] < .35), minf=.01)] * 2),
       face=ph(.585, .41, .15, 1.4), lcol=WHT)

# Aliens (1986): the hive's blue-black, the poster's spaced A L I E N S lifted, Ripley carrying Newt with the pulse rifle
std('aliens-1986', ('grad', [(0, (30, 70, 100)), (.6, (8, 20, 34)), (1, (0, 2, 6))]), (150, 190, 230),
    L((0.245, 0.855, 0.765, 0.945), 70, (170, 200, 240), mode='light', speck=0),
    photo=ph(0.5, 0.3, 0.7, 1.15), pb=(150, 190, 230), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(170, 190, 220), fin=RENTAL, seed=1986)

# An American Tail (1986): the poster's sky, its red AN / AMERICAN / TAIL keyed off it word by word into one line, Fievel in his blue hat (Amblin, a slipcase)
std('an-american-tail-1986', ('grad', [(0, (120, 200, 240)), (.5, (60, 160, 220)), (1, (20, 70, 120))]), (220, 30, 40),
    LC([(0.225, 0.028, 0.35, 0.08), (0.07, 0.05, 0.945, 0.176), (0.07, 0.178, 0.35, 0.27)], 110, valign='base', margin=0, gapf=.25, outline=(WHT, 2.4),
       cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), minf=.05), comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), keep=lambda cx, cy: cy > .25, minf=.05), comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), minf=.05)]),
    photo=ph(0.5, 0.48, 0.5, 1.0), pb=(220, 30, 40), lg=WHT, lw=.5, order='LPTF',
    ft='d', fcol=(230, 240, 250), fin=RENTAL, seed=1986)

# Blue Velvet (1986): deep blue, the poster's white script Blue Velvet lifted, the lovers in the blue light
std('blue-velvet-1986', ('grad', [(0, (30, 40, 110)), (.6, (8, 12, 40)), (1, (2, 2, 10))]), WHT,
    L((0.06, 0.19, 0.958, 0.298), 100, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.65, 0.9, 0.6), pb=(110, 140, 240), lg=WHT, lw=.5, order='LPTCF', credit=['A DAVID LYNCH', 'FILM'], ccol=(170, 190, 250),
    ft='b', fcol=(170, 180, 230), fin=OLD, seed=1986)

# Down by Law (1986): the poster's white, its black stencilled DOWN / BY / LAW cut off it into one line, the three of them in the cell (Island Pictures logo)
std('down-by-law-1986', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (20, 20, 20),
    LC([(0.44, 0.553, 0.942, 0.631), (0.733, 0.641, 0.936, 0.716), (0.573, 0.726, 0.936, 0.803)], 90, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: _lum(a) < .32)] * 3),
    photo=ph(0.5, 0.26, 0.86, 0.75), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A FILM BY', 'JIM JARMUSCH'], ccol=(20, 20, 20),
    ft='e', fcol=(20, 20, 20), fin=OLD, seed=1986)

# Ferris Bueller's Day Off (1986): the poster's white, its red tilted FERRIS / BUELLER'S / DAY OFF cut off it whole and turned level, Ferris behind his sunglasses
std('ferris-bueller-s-day-off-1986', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (220, 30, 40),
    LC([(0.265, 0.72, 0.948, 0.946)], 120, outline=((20, 20, 20), 1.6), cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), minf=.03, rot=-14)]),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTSF', stick=PRC(['$2.99', 'COMEDY']),
    ft='a', vbox=(220, 30, 40), fcol=(20, 20, 20), fin=RENTAL, seed=1986)

# Hoosiers (1986): the poster's sky and fields, its red HOOSIERS keyed off it, Gene Hackman with the basketball (no logo file: Hemdale, from IMDb's company credits)
std('hoosiers-1986', ('grad', [(0, (90, 160, 220)), (.5, (110, 150, 80)), (1, (30, 50, 20))]), (220, 30, 30),
    L((0.033, 0.102, 0.967, 0.205), 84, (220, 30, 30), mode='key', key=(220, 36, 36), t=(70, 160)),
    photo=ph(0.55, 0.55, 0.7, 1.15), pb=(220, 30, 30), studio=['HEMDALE'], scol=WHT, order='lTPF',
    ft='b', fcol=(230, 230, 220), fin=RENTAL, seed=1986)

# Mona Lisa (1986): the poster's night teal, its yellow MONA / LISA keyed off it into one line, Bob Hoskins and Cathy Tyson
std('mona-lisa-1986', ('grad', [(0, (30, 80, 90)), (.6, (10, 26, 30)), (1, (2, 6, 8))]), (250, 220, 30),
    L([(0.262, 0.552, 0.914, 0.673), (0.5, 0.68, 0.974, 0.798)], 100, (250, 220, 30), mode='key', key=(250, 220, 40), t=(70, 160), valign='base'),
    photo=ph(0.5, 0.25, 0.86, 0.7), pb=(250, 220, 30), lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(200, 220, 220), fin=OLD, seed=1986)

# Platoon (1986): the jungle's dark green, the poster's chrome PLATOON with the dog-tag O cut off it, Elias falling with his arms raised (no logo file: Hemdale, from IMDb's company credits)
std('platoon-1986', ('grad', [(0, (40, 70, 50)), (.6, (12, 24, 16)), (1, (2, 6, 4))]), (220, 226, 220),
    LC([(0.08, 0.077, 0.914, 0.223)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .5) & (_sat(a) < .3), minf=.02, close=2)]),
    photo=ph(0.5, 0.48, 0.7, 1.0), pb=(220, 226, 220), studio=['HEMDALE'], scol=(220, 226, 220), order='lPTCSF', credit=['AN OLIVER STONE', 'FILM'], ccol=(220, 226, 220), stick=BAR('86 1219', top='WAR', fill=(226, 230, 220)),
    ft='c', fcol=(200, 210, 200), fin=RENTAL, seed=1986)

# Sid and Nancy (1986): the poster's punk pink, the torn white strip with its black ransom-note SiD & NANCY cut off it whole, Sid and Nancy against the fly-posters (no logo file: Zenith, from IMDb's company credits)
std('sid-and-nancy-1986', ('grad', [(0, (230, 60, 140)), (.5, (110, 20, 70)), (1, (16, 4, 10))]), WHT,
    LC([(0.05, 0.6, 0.975, 0.775)], 110, cuts=[plate_cut(lambda a: _lum(a) > .72)]),
    photo=ph(0.6, 0.25, 0.8, 0.85), pb=WHT, studio=['ZENITH'], scol=WHT, order='lPTF', dotst=('PUNK', (20, 20, 20), (250, 120, 190)),
    ft='a', vbox=(20, 20, 20), fcol=(250, 210, 230), fin=OLD, seed=1986)

# Stand by Me (1986): the poster's sky, its red STAND BY ME keyed off it, the four boys, and the walk along the lake's edge under the title
std('stand-by-me-1986', ('grad', [(0, (90, 170, 230)), (.5, (40, 100, 160)), (1, (6, 20, 30))]), (220, 30, 30),
    L((0.074, 0.454, 0.932, 0.519), 84, (220, 30, 30), mode='key', key=(220, 36, 36), t=(70, 160)),
    photo=ph(0.5, 0.2, 0.9, 0.62), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(220, 230, 240), fin=RENTAL, seed=1986)

# The Color of Money (1986): Touchstone, a slipcase; the felt green, the poster's white stacked the / Color / of / Money cut letter by letter into one line, Newman and Cruise at the table
std('the-color-of-money-1986', ('grad', [(0, (30, 90, 60)), (.6, (10, 34, 22)), (1, (2, 8, 4))]), WHT,
    LC([(0.775, 0.2, 0.88, 0.255), (0.655, 0.24, 0.855, 0.3), (0.8, 0.284, 0.88, 0.34), (0.695, 0.326, 0.945, 0.396)], 84, valign='base', margin=0, gapf=.3,
       cuts=[pick_cut(lambda a: _lum(a) > .8, (0.775, 0.2, 0.88, 0.255), [(0.792, 0.228), (0.82, 0.23), (0.858, 0.233)], margin=0, r=.015),
             pick_cut(lambda a: _lum(a) > .8, (0.655, 0.24, 0.855, 0.3), [(0.682, 0.27), (0.729, 0.276), (0.762, 0.27), (0.795, 0.276), (0.829, 0.273)], margin=0, r=.015),
             pick_cut(lambda a: _lum(a) > .8, (0.8, 0.284, 0.88, 0.34), [(0.824, 0.317), (0.86, 0.31)], margin=0, r=.015),
             pick_cut(lambda a: _lum(a) > .8, (0.695, 0.326, 0.945, 0.396), [(0.731, 0.355), (0.787, 0.361), (0.832, 0.36), (0.875, 0.361), (0.917, 0.365)], margin=0, r=.015)]),
    photo=ph(0.35, 0.66, 0.6, 1.2), pb=(240, 220, 160), lg=WHT, lw=.5, order='LTPF',
    ft='b', fcol=(200, 220, 210), fin=RENTAL, seed=1986)

# The Great Mouse Detective (1986): Disney clamshell; the poster's white into Baker Street brown, its black THE GREAT MOUSE beside DETECTIVE cut off it, Basil's face in the diamond
disney('the-great-mouse-detective-1986', ('grad', [(0, (240, 236, 226)), (.5, (200, 180, 150)), (1, (90, 60, 40))]), fin=dict(CLAM, vivid=.2),
       title=[LC([(0.415, 0.098, 0.582, 0.138), (0.165, 0.14, 0.838, 0.188)], 100, valign='base', margin=0, gapf=.25, cuts=[key_cut(lambda a: _lum(a) < .32)] * 2),
              LC([(0.224, 0.19, 0.788, 0.237)], 100, margin=0, cuts=[key_cut(lambda a: _lum(a) < .32)])],
       face=ph(.31, .5, .14, 1.4), lcol=(30, 20, 14), ink=(30, 20, 14))

# Top Gun (1986): the jacket's brown-black, the poster's white and red TOP GUN wings logo cut off it in its own colours, Maverick and Charlie
std('top-gun-1986', ('grad', [(0, (70, 50, 40)), (.6, (24, 16, 12)), (1, (4, 2, 2))]), WHT,
    LC([(0.0, 0.648, 0.968, 0.796)], 130, cuts=[comp_cut(lambda a: (_lum(a) > .8) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.01, close=2)]),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(200, 30, 40), lg=WHT, lw=.5, order='LPTF', ft='d', vbox=(200, 30, 40), fcol=(220, 210, 200), fin=RENTAL, seed=1986)

# Au revoir les enfants (1987): the navy of the poster's title plate, its cream AU REVOIR / LES ENFANTS and (GOODBYE, CHILDREN) cut off it into one line, the two boys
std('au-revoir-les-enfants-1987', ('grad', [(0, (30, 36, 80)), (.6, (12, 14, 34)), (1, (2, 2, 8))]), (240, 226, 170),
    LC([(0.3, 0.766, 0.705, 0.818), (0.278, 0.816, 0.735, 0.87), (0.32, 0.882, 0.688, 0.909)], 84, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: _lum(a) > .5)] * 3),
    photo=ph(0.55, 0.35, 0.86, 0.7), pb=(240, 226, 170), lg=(240, 226, 170), lw=.5, order='LPTCF', credit=['UN FILM DE', 'LOUIS MALLE'], ccol=(240, 226, 170),
    ft='c', fcol=(210, 210, 220), fin=OLD, seed=1987)

# Full Metal Jacket (1987): the poster's white, its black stencilled FULL / METAL / JACKET cut off it into one line, the helmet with BORN TO KILL
std('full-metal-jacket-1987', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (20, 20, 20),
    LC([(0.405, 0.642, 0.615, 0.706), (0.36, 0.705, 0.66, 0.767), (0.325, 0.765, 0.68, 0.828)], 90, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: _lum(a) < .32)] * 3),
    photo=ph(0.5, 0.35, 0.86, 0.75), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LTPF',
    ft='a', fcol=(20, 20, 20), fin=OLD, seed=1987)

# Raising Arizona (1987): the poster's white, its striped red, white and blue RAISING / ARIZONA (its A a safety pin) cut off it in its own colours into one line, H.I., Ed and the baby on their loungers (no logo file: Circle Films, from IMDb's company credits)
std('raising-arizona-1987', ('grad', [(0, (246, 246, 244)), (.5, (220, 230, 244)), (1, (110, 130, 170))]), (200, 40, 50),
    LC([(0.295, 0.67, 0.71, 0.742), (0.29, 0.742, 0.715, 0.81)], 90, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: (_sat(a) > .14) | (_lum(a) < .8))] * 2),
    photo=ph(0.4, 0.4, 0.6, 0.8), pb=(60, 80, 160), studio=['CIRCLE FILMS'], scol=(40, 50, 100), order='lPTF', ft='c', fcol=(40, 50, 100), fin=RENTAL, seed=1987)

# RoboCop (1987): the night street, the poster's white ROBOCOP with its red shadow cut off it in its own colours, RoboCop stepping out of the cruiser
std('robocop-1987', ('grad', [(0, (40, 50, 80)), (.6, (12, 14, 26)), (1, (2, 2, 6))]), WHT,
    LC([(0.09, 0.826, 0.91, 0.928)], 120, cuts=[comp_cut(lambda a: (_lum(a) > .7) | ((a[..., 0] > .55) & (a[..., 1] < .3)), minf=.01)]),
    photo=ph(0.4, 0.35, 0.7, 1.2), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('87 0717', top='ACTION', fill=(226, 228, 236)),
    ft='a', vbox=(200, 30, 30), fcol=(200, 206, 220), fin=RENTAL, seed=1987)

# The Princess Bride (1987): dusk, its gold THE PRINCESS BRIDE cut off it word by word into one line, Westley and Buttercup's kiss under the title
std('the-princess-bride-1987', ('grad', [(0, (50, 50, 70)), (.5, (90, 70, 50)), (1, (24, 16, 8))]), (240, 210, 90),
    LC([(0.385, 0.152, 0.55, 0.193), (0.09, 0.175, 0.87, 0.33), (0.24, 0.275, 0.69, 0.36)], 100, valign='base', margin=0, gapf=.3, outline=((50, 30, 10), 1.6),
       cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 0] > a[..., 2] + .25) & (_lum(a) > .45), minf=.05, keep=lambda cx, cy: cy > .2),
             comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 0] > a[..., 2] + .25) & (_lum(a) > .45), minf=.05, keep=lambda cx, cy: .1 < cy < .7),
             comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 0] > a[..., 2] + .25) & (_lum(a) > .45), minf=.05, keep=lambda cx, cy: cy > .3)]),
    photo=ph(0.47, 0.6, 0.6, 1.2), pb=(240, 210, 90), lg=WHT, lw=.5, order='LTPCF', credit=['A ROB REINER', 'FILM'], ccol=(250, 230, 160),
    ft='e', fcol=(240, 220, 180), fin=RENTAL, seed=1987)

# The Untouchables (1987): the dark of the suit, the poster's gold THE UNTOUCHABLES cut off it, Kevin Costner with the badge
std('the-untouchables-1987', ('grad', [(0, (60, 60, 64)), (.6, (18, 18, 20)), (1, (2, 2, 2))]), (220, 180, 110),
    LC([(0.095, 0.362, 0.905, 0.436)], 100, cuts=[key_cut(lambda a: (a[..., 0] > .5) & (a[..., 0] > a[..., 2] + .15) & (_lum(a) > .35))]),
    photo=ph(0.55, 0.15, 0.8, 0.5), pb=(220, 180, 110), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(200, 196, 190), fin=OLD, seed=1987)

# Beetlejuice (1988): the poster's purple dusk, its yellow BEETLEJUICE keyed off it, Beetlejuice on the model town with Lydia and the Maitlands
std('beetlejuice-1988', ('grad', [(0, (60, 40, 110)), (.5, (110, 60, 120)), (1, (14, 10, 30))]), (250, 220, 60),
    L((0.083, 0.112, 0.918, 0.198), 96, (250, 220, 60), mode='key', key=(240, 210, 60), t=(70, 160)),
    photo=ph(0.5, 0.45, 0.8, 1.1), pb=(250, 220, 60), lg=WHT, lw=.5, order='LPTF', dotst=('COMEDY', (130, 200, 80), (20, 20, 20)),
    ft='d', fcol=(220, 210, 230), fin=RENTAL, seed=1988)

# Bull Durham (1988): the evening sky, the poster's white BULL / DURHAM lifted into one line, Costner and Sarandon with the bat
std('bull-durham-1988', ('grad', [(0, (70, 80, 110)), (.6, (24, 26, 40)), (1, (4, 4, 8))]), WHT,
    L([(0.568, 0.76, 0.867, 0.832), (0.463, 0.831, 0.967, 0.9)], 90, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.33, 0.86, 0.95), pb=(200, 30, 40), lg=WHT, lw=.5, order='LPTF',
    ft='c', fcol=(210, 210, 220), fin=RENTAL, seed=1988)

# Dead Ringers (1988): black, the poster's thin red DEAD / RINGERS cut off it into one line, the twin faces of Jeremy Irons merging
std('dead-ringers-1988', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), (210, 30, 40),
    LC([(0.185, 0.771, 0.8, 0.843), (0.182, 0.852, 0.8, 0.928)], 100, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .25))] * 2),
    photo=ph(0.5, 0.25, 0.9, 0.7), pb=(210, 30, 40), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(200, 190, 190), fin=OLD, seed=1988)

# Die Hard (1988): black, the poster's red DIE HARD keyed off it, John McClane's face beside the burning tower
std('die-hard-1988', ('grad', [(0, (50, 40, 34)), (.6, (14, 10, 8)), (1, (2, 2, 2))]), (220, 30, 30),
    L((0.072, 0.844, 0.928, 0.925), 96, (220, 30, 30), mode='key', key=(220, 30, 30), t=(70, 160)),
    photo=ph(0.6, 0.38, 0.8, 1.0), pb=(250, 150, 40), lg=WHT, lw=.5, order='LPTF', ft='b', vbox=(220, 30, 30), fcol=(210, 200, 196), fin=RENTAL, seed=1988)

# Grave of the Fireflies (1988): Studio Ghibli, a slipcase; black, the poster's white GRAVE of the / FIREFLIES lifted into one line, Seita carrying Setsuko under the umbrella
std('grave-of-the-fireflies-1988', ('grad', [(0, (60, 40, 20)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), WHT,
    L([(0.06, 0.548, 0.535, 0.605), (0.06, 0.603, 0.465, 0.66)], 90, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.7, 0.62, 0.55, 1.4), pb=(240, 180, 90), lg=WHT, lw=.5, order='LTPF',
    ft='a', vbox=(240, 180, 90), vink=(30, 20, 10), fcol=(220, 210, 190), fin=OLD, seed=1988)

# Oliver & Company (1988): Disney clamshell; the New York sky blue, the poster's yellow OLIVER & Company cut off it in its own colours, Oliver's face in the diamond
disney('oliver-company-1988', ('grad', [(0, (60, 130, 220)), (.5, (90, 160, 230)), (1, (30, 70, 140))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.055, 0.088, 0.605, 0.18), (0.09, 0.18, 0.588, 0.262)], 110, valign='base', margin=0, gapf=.25,
                cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45)) | ((a[..., 0] > .6) & (a[..., 1] < .35)), minf=.01, close=2)] * 2),
       face=ph(.49, .462, .13, 1.4), lcol=WHT)

# Rain Man (1988): the poster's park greens, its white serif RAIN MAN lifted, Raymond and Charlie walking
std('rain-man-1988', ('grad', [(0, (120, 130, 100)), (.6, (50, 56, 40)), (1, (10, 12, 8))]), WHT,
    L((0.07, 0.83, 0.922, 0.917), 90, WHT, mode='light'),
    photo=ph(0.48, 0.4, 0.7, 1.15), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(220, 226, 210), fin=RENTAL, seed=1988)

# The Land Before Time (1988): Amblin and Universal, a slipcase; the valley's greens, the poster's whole gold-framed THE LAND BEFORE TIME panel cut off it as it is, Littlefoot and the others
std('the-land-before-time-1988', ('grad', [(0, (120, 190, 230)), (.5, (110, 170, 90)), (1, (40, 70, 30))]), WHT,
    LC([(0.095, 0.03, 0.905, 0.332)], 140, margin=0, cuts=[key_cut(lambda a: _lum(a) >= 0)]),
    photo=ph(0.6, 0.66, 0.8, 0.95), pb=(250, 210, 60), lg=WHT, lw=.5, order='LPTF',
    ft='e', fcol=(240, 240, 230), fin=RENTAL, seed=1988)

# The Thin Blue Line (1988): the poster's blue-black, its blue and red THE THIN BLUE LINE (crossed by the searchlight's white band) cut off it as it is, ground and all, Randall Adams' face (documentary; director from IMDb)
std('the-thin-blue-line-1988', ('grad', [(0, (20, 34, 60)), (.6, (6, 12, 24)), (1, (2, 2, 6))]), (120, 160, 230),
    LC([(0.25, 0.552, 0.99, 0.646)], 110, margin=0, cuts=[key_cut(lambda a: _lum(a) >= 0)]),
    photo=ph(0.3, 0.25, 0.6, 0.85), pb=(120, 160, 230), lg=WHT, lw=.5, order='LPTCF', credit=['A DOCUMENTARY BY', 'ERROL MORRIS'], ccol=(170, 200, 240),
    ft='c', fcol=(170, 186, 220), fin=OLD, seed=1988)

# The Unbearable Lightness of Being (1988): a 2-tape box; the poster's violet dark, its white italic THE UNBEARABLE / LIGHTNESS OF BEING lifted in two lines side by side, Juliette Binoche in the bowler hat
std('the-unbearable-lightness-of-being-1988', ('grad', [(0, (60, 50, 100)), (.6, (18, 14, 34)), (1, (2, 2, 8))]), WHT,
    [L([(0.428, 0.045, 0.572, 0.093), (0.228, 0.1, 0.77, 0.144)], 120, WHT, mode='light', valign='base', speck=0, gapf=.3),
     L([(0.268, 0.151, 0.73, 0.197), (0.345, 0.203, 0.655, 0.242)], 120, WHT, mode='light', valign='base', speck=0, gapf=.3)], tgap=10,
    photo=ph(0.42, 0.42, 0.42, 0.7), pb=(200, 190, 240), lg=WHT, lw=.5, order='LPTSF', stick=TWOST((120, 90, 190), WHT),
    ft='e', fcol=(200, 196, 220), fin=OLD, seed=1988, **TWO)

# The Vanishing (1988): black, the poster's orange spaced THE VANISHING keyed off it, the service station's lights at night (no logo file: Argos Films, from IMDb's company credits)
std('the-vanishing-1988', ('grad', [(0, (30, 26, 20)), (.6, (10, 8, 6)), (1, (2, 2, 2))]), (226, 120, 50),
    L((0.17, 0.122, 0.935, 0.18), 76, (226, 120, 50), mode='key', key=(220, 120, 50), t=(70, 160)),
    photo=ph(0.5, 0.9, 1.0, 0.3), pb=(226, 120, 50), studio=['ARGOS FILMS'], scol=(226, 120, 50), order='lTPCF', credit=['EEN FILM VAN', 'GEORGE SLUIZER'], ccol=(220, 200, 180),
    ft='d', fcol=(200, 190, 180), fin=OLD, seed=1988)

# Who Framed Roger Rabbit (1988): Amblin, a slipcase; Toontown's sky, the poster's red arched banner with its yellow Who framed ROGER RABBIT cut off it whole, Roger and Jessica over Eddie Valiant in Benny the Cab
std('who-framed-roger-rabbit-1988', ('grad', [(0, (60, 120, 210)), (.5, (40, 80, 170)), (1, (10, 20, 60))]), (250, 220, 40),
    LC([(0.095, 0.095, 0.955, 0.325)], 150, cuts=[plate_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3) | ((a[..., 0] > .7) & (a[..., 1] > .6) & (a[..., 2] < .4)))]),
    photo=ph(0.5, 0.6, 0.86, 0.95), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(220, 30, 40), fcol=(220, 230, 246), fin=RENTAL, seed=1988)

# Batman (1989): black, the poster's gold Bat-symbol over its outlined gold B A T M A N, each cut off it in its own colours
std('batman-1989', ('grad', [(0, (30, 30, 36)), (.6, (8, 8, 10)), (1, (0, 0, 0))]), (250, 190, 60),
    LC([(0.1, 0.74, 0.9, 0.885)], 90, cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 2] < .45), minf=.05, close=2)]),
    photo=ph(0.5, 0.31, 0.9, 0.62), pb=(250, 190, 60), lg=WHT, lw=.5, order='LPTCF', credit=['MICHAEL KEATON', 'JACK NICHOLSON'], ccol=(250, 210, 120),
    ft='b', vbox=(250, 190, 60), vink=(10, 8, 4), fcol=(220, 200, 160), fin=RENTAL, seed=1989)

# Dead Poets Society (1989): Touchstone, a slipcase; the poster's wheat gold, its dark-red ruled DEAD / POETS / SOCIETY cut off it into one line, the boys carrying Keating's pupil through the field
std('dead-poets-society-1989', ('grad', [(0, (230, 190, 130)), (.6, (200, 150, 90)), (1, (90, 60, 30))]), (110, 30, 30),
    LC([(0.312, 0.185, 0.693, 0.268), (0.312, 0.272, 0.693, 0.352), (0.312, 0.355, 0.693, 0.405)], 84, valign='base', margin=0, gapf=.3, cuts=[key_cut(lambda a: _lum(a) < .42)] * 3),
    photo=ph(0.5, 0.67, 0.86, 0.6), pb=(110, 30, 30), lg=(80, 30, 20), lw=.55, order='LPTF', ft='d', fcol=(70, 40, 20), fin=RENTAL, seed=1989)

# Do the Right Thing (1989): the poster's street blue, its yellow hand-lettered DO THE / RIGHT / THING with its coloured bars cut off it into one line, Mookie with the pizza box (Universal; director from IMDb)
std('do-the-right-thing-1989', ('grad', [(0, (40, 90, 200)), (.5, (24, 60, 160)), (1, (6, 16, 50))]), (250, 230, 60),
    LC([(0.355, 0.21, 0.665, 0.315), (0.36, 0.33, 0.645, 0.432), (0.355, 0.442, 0.64, 0.538)], 90, valign='base', margin=0, gapf=.3,
       cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .7) & (a[..., 2] < .5))] * 3),
    photo=ph(0.85, 0.55, 0.3, 1.5), pb=(250, 230, 60), lg=WHT, lw=.5, order='LPTCSF', credit=['A SPIKE LEE', 'JOINT'], ccol=(250, 230, 120), stick=RWD(),
    ft='a', vbox=(220, 30, 30), fcol=(220, 226, 246), fin=RENTAL, seed=1989)

# For All Mankind (1989): black space, the poster's white FOR ALL MANKIND lifted, the astronaut on the Moon (National Geographic logo; director from IMDb)
std('for-all-mankind-1989', ('grad', [(0, (40, 40, 44)), (.6, (12, 12, 14)), (1, (2, 2, 2))]), WHT,
    L((0.055, 0.133, 0.958, 0.19), 70, WHT, mode='light'),
    photo=ph(0.5, 0.55, 0.7, 1.4), pb=(200, 200, 200), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'AL REINERT'], ccol=WHT,
    ft='e', fcol=(200, 200, 200), fin=OLD, seed=1989)

# Glory (1989): the poster's dusk blue, its white serif GLORY lifted, Washington, Freeman and Broderick in their kepis
std('glory-1989', ('grad', [(0, (100, 120, 150)), (.5, (40, 50, 70)), (1, (8, 8, 14))]), WHT,
    L((0.125, 0.868, 0.895, 0.952), 100, WHT, mode='light'),
    photo=ph(0.55, 0.35, 0.86, 0.9), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['DENZEL WASHINGTON', 'MORGAN FREEMAN'], ccol=WHT,
    ft='c', fcol=(200, 206, 220), fin=RENTAL, seed=1989)

# How to Get Ahead in Advertising (1989): the poster's sky, its orange stone HOW TO GET AHEAD IN ADVERTISING monument cut off it whole, Dennis with his arms out over the fields
std('how-to-get-ahead-in-advertising-1989', ('grad', [(0, (100, 200, 230)), (.5, (60, 160, 200)), (1, (20, 70, 60))]), (240, 120, 50),
    LC([(0.035, 0.04, 0.975, 0.29)], 150, cuts=[comp_cut(lambda a: (a[..., 0] > a[..., 2] + .05) | (_lum(a) < .25) | ((a[..., 1] > a[..., 0] + .1) & (a[..., 2] < .5)), top=1, close=3)]),
    photo=ph(0.5, 0.55, 0.8, 1.0), pb=(240, 120, 50), lg=WHT, lw=.5, order='LPTF', dotst=('COMEDY', (240, 120, 50), WHT),
    ft='b', fcol=(230, 240, 240), fin=OLD, seed=1989)

# Indiana Jones and the Last Crusade (1989): the poster's sun-bleached parchment, INDIANA JONES / AND THE LAST CRUSADE typeset in heavy italic capitals in the logo's orange with a black keyline (parked for Ian's logo, see data/logos-wanted.md: the lettering's oranges are the parchment's own, so two colour cuts left holes and a slab showed a seam), Indy and his father
std('indiana-jones-and-the-last-crusade-1989', ('grad', [(0, (230, 200, 150)), (.5, (200, 160, 110)), (1, (90, 60, 30))]), (40, 26, 16),
    [T('INDIANA JONES', 'intbk', 84, (236, 120, 30), outline=((30, 16, 8), 2.2)), T('AND THE LAST CRUSADE', 'intbk', 40, (250, 200, 50), outline=((30, 16, 8), 1.6))], tgap=8,
    photo=ph(0.55, 0.42, 0.7, 0.8), pb=(60, 40, 20), lg=(60, 40, 20), lw=.55, order='LPTF',
    ft='d', fcol=(50, 34, 20), fin=RENTAL, seed=1989)

# The Killer (1989): the poster's white, its red brushed THE KILLER keyed off it, Chow Yun-fat with two pistols (no logo file: Film Workshop, from IMDb's company credits)
std('the-killer-1989', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (130, 128, 124))]), (220, 30, 30),
    L((0.058, 0.858, 0.936, 0.946), 96, (220, 30, 30), mode='key', key=(220, 30, 30), t=(70, 160)),
    photo=ph(0.55, 0.45, 0.8, 1.2), pb=(220, 30, 30), studio=['FILM WORKSHOP'], scol=(30, 30, 30), order='lPTCF', credit=['A JOHN WOO', 'FILM'], ccol=(30, 30, 30),
    ft='a', vbox=(220, 30, 30), fcol=(30, 30, 30), fin=RENTAL, seed=1989)

# The Little Mermaid (1989): Disney clamshell; the sea's blues, the poster's gold THE LITTLE / MERMAID cut off it, Ariel's face in the diamond
disney('the-little-mermaid-1989', ('grad', [(0, (40, 160, 220)), (.5, (30, 110, 190)), (1, (10, 40, 100))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.395, 0.757, 0.588, 0.791), (0.21, 0.79, 0.77, 0.86)], 110, valign='base', margin=0, gapf=.25, outline=((60, 40, 10), 1.6),
                cuts=[key_cut(lambda a: (_lum(a) > .55) & (a[..., 0] > a[..., 2] + .06)), comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 0] > a[..., 2] + .15) & (a[..., 1] > .4), minf=.02, close=2)]),
       face=ph(.47, .3, .13, 1.4), lcol=WHT)


# ---------------------------------------------------------------- the 1990s
# Dick Tracy (1990): Touchstone, a slipcase; black, the poster's red DICK TRACY with its yellow surround cut off it whole, Tracy's hat and profile in the red ring
std('dick-tracy-1990', ('grad', [(0, (30, 26, 26)), (.6, (10, 8, 8)), (1, (2, 2, 2))]), (250, 220, 40),
    LC([(0.2, 0.09, 0.8, 0.25)], 140, cuts=[comp_cut(lambda a: (a[..., 0] > .5) & (a[..., 2] < .35), top=1, close=2)]),
    photo=ph(0.5, 0.6, 0.9, 0.95), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTCF', credit=['WARREN BEATTY', 'MADONNA'], ccol=WHT,
    ft='b', vbox=(170, 20, 20), fcol=(230, 210, 120), fin=RENTAL, seed=1990)

# Die Hard 2 (1990): the poster's dusk blue, its white DIE HARD 2 with the red rule and DIE HARDER cut off it, McClane with the pistol
std('die-hard-2-1990', ('grad', [(0, (60, 90, 140)), (.6, (18, 26, 44)), (1, (60, 20, 6))]), WHT,
    LC([(0.1, 0.055, 0.915, 0.168)], 120, cuts=[comp_cut(lambda a: (_lum(a) > .72) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.005)]),
    photo=ph(0.4, 0.4, 0.8, 1.0), pb=(220, 40, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('90 0703', top='ACTION', fill=(228, 226, 216)),
    ft='a', vbox=(200, 30, 30), fcol=(210, 214, 226), fin=RENTAL, seed=1990)

# Edward Scissorhands (1990): the poster's white, its black edward / SCISSORHANDS between the rules cut off it into one line, Edward's blades and the butterfly under the title
std('edward-scissorhands-1990', ('grad', [(0, (246, 246, 246)), (.6, (226, 228, 232)), (1, (120, 124, 140))]), (20, 20, 24),
    LC([(0.42, 0.122, 0.735, 0.168), (0.24, 0.168, 0.9, 0.256)], 100, valign='base', margin=0, gapf=.25, cuts=[key_cut(lambda a: _lum(a) < .35)] * 2),
    photo=ph(0.55, 0.6, 0.86, 0.85), pb=(20, 20, 24), lg=(20, 20, 24), lw=.55, order='LTPF',
    ft='c', fcol=(20, 20, 24), fin=RENTAL, seed=1990)

# GoodFellas (1990): black, the poster's white GoodFellas lifted, De Niro between Liotta and Pesci
std('goodfellas-1990', ('grad', [(0, (40, 38, 38)), (.6, (12, 10, 10)), (1, (2, 2, 2))]), WHT,
    L((0.195, 0.53, 0.805, 0.632), 110, WHT, mode='light'),
    photo=ph(0.5, 0.18, 0.9, 0.55), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['A MARTIN SCORSESE', 'PICTURE'], ccol=WHT,
    ft='e', vbox=(200, 30, 30), fcol=(200, 196, 196), fin=RENTAL, seed=1990)

# Home Alone (1990): the poster's navy, its yellow HOME ALONE with the red house in the gap cut off it, Kevin's scream
std('home-alone-1990', ('grad', [(0, (30, 60, 130)), (.6, (12, 24, 60)), (1, (2, 6, 20))]), (250, 230, 60),
    LC([(0.035, 0.058, 0.962, 0.14)], 120, cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .6) & (a[..., 2] < .45)) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.01)]),
    photo=ph(0.5, 0.5, 0.55, 1.5), pb=(250, 230, 60), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$1.99', 'FAMILY']),
    ft='d', fcol=(220, 226, 246), fin=RENTAL, seed=1990)

# Kindergarten Cop (1990): the poster's white, its crayon-coloured Kindergarten and blue COP cut off it in their own colours into one line, Arnold with the children
std('kindergarten-cop-1990', ('grad', [(0, (246, 246, 244)), (.6, (228, 230, 236)), (1, (120, 130, 160))]), (20, 40, 140),
    LC([(0.085, 0.705, 0.915, 0.8), (0.215, 0.805, 0.79, 0.95)], 100, valign='base', margin=0, gapf=.25, cuts=[key_cut(lambda a: (_sat(a) > .2) | (_lum(a) < .45))] * 2),
    photo=ph(0.5, 0.32, 0.6, 1.3), pb=(20, 40, 140), lg=(20, 40, 140), lw=.55, order='LTPF',
    ft='a', vbox=(20, 40, 140), fcol=(20, 30, 60), fin=RENTAL, seed=1990)

# Miller's Crossing (1990): the woods' browns, the poster's gold MILLER'S / CROSSING cut off it into one line, the hat-and-coat figure in the trees (no logo file: Circle Films, from IMDb's company credits)
std('miller-s-crossing-1990', ('grad', [(0, (90, 80, 50)), (.6, (34, 30, 18)), (1, (6, 6, 4))]), (240, 180, 40),
    LC([(0.05, 0.76, 0.755, 0.826), (0.16, 0.828, 0.84, 0.908)], 90, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: (a[..., 0] > .65) & (a[..., 1] > .45) & (a[..., 2] < .35) | (_lum(a) < .12), minf=.02)] * 2),
    photo=ph(0.45, 0.45, 0.8, 1.1), pb=(240, 180, 40), studio=['CIRCLE FILMS'], scol=(240, 200, 120), order='lPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(240, 200, 120),
    ft='b', fcol=(220, 200, 160), fin=OLD, seed=1990)

# Teenage Mutant Ninja Turtles (1990): the city night's teal, TEENAGE MUTANT NINJA TURTLES typeset in heavy condensed capitals in the logo's green with a pale keyline (parked for Ian's logo, see data/logos-wanted.md: the green lettering sits on teal clouds of nearly its own colour, so two cuts lost NINJA and TURTLES), the four turtles peering out of the manhole
std('teenage-mutant-ninja-turtles-1990', ('grad', [(0, (20, 70, 80)), (.6, (6, 24, 30)), (1, (2, 6, 8))]), (80, 200, 80),
    T('TEENAGE MUTANT NINJA TURTLES', 'intbk', 80, (40, 160, 70), outline=((200, 240, 150), 2.2)),
    photo=ph(0.5, 0.86, 0.9, 0.35), pb=(80, 200, 80), lg=WHT, lw=.5, order='LPTF', dotst=('ACTION', (250, 140, 30), (20, 20, 20)),
    ft='e', fcol=(170, 220, 210), fin=RENTAL, seed=1990)

# The Rescuers Down Under (1990): Disney clamshell; the outback sky, the poster's gold The RESCUERS and its DOWN UNDER plate cut off it in their own colours, Cody's face in the diamond
disney('the-rescuers-down-under-1990', ('grad', [(0, (90, 170, 230)), (.5, (60, 140, 210)), (1, (20, 60, 120))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.155, 0.045, 0.835, 0.225)], 140, cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .45) & (a[..., 2] < .45)) | ((a[..., 0] > .55) & (a[..., 1] < .3)) | (_lum(a) < .2), minf=.003, close=2)]),
       face=ph(.58, .505, .13, 1.4), lcol=WHT)

# The Witches (1990): the poster's white, its white-on-black stencilled the / Witches... cut off it into one line, the Grand High Witch in her purple cloak
std('the-witches-1990', ('grad', [(0, (90, 40, 110)), (.6, (30, 12, 40)), (1, (4, 2, 8))]), WHT,
    LC([(0.155, 0.56, 0.36, 0.6), (0.215, 0.592, 0.815, 0.697)], 110, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: _lum(a) > .82)] * 2),
    photo=ph(0.4, 0.28, 0.5, 1.3), pb=(200, 120, 220), lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(220, 200, 230), fin=RENTAL, seed=1990)

# Barton Fink (1991): the poster's sepia, its white slab-serif BARTON / FINK lifted into one line, John Turturro's startled face
std('barton-fink-1991', ('grad', [(0, (180, 130, 80)), (.6, (90, 60, 30)), (1, (20, 12, 6))]), WHT,
    L([(0.095, 0.762, 0.955, 0.826), (0.095, 0.822, 0.943, 0.94)], 96, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.33, 0.86, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(240, 220, 200), fin=OLD, seed=1991)

# Beauty and the Beast (1991): Disney clamshell; the ballroom's blue, Beauty and the Beast typeset in a gold serif like the logo's with a dark keyline (parked for Ian's logo, see data/logos-wanted.md: Lumiere overlaps the poster's oval title plate, so the plate cut lost Beast, and the gold letters' shading broke a colour cut), Belle's face in the diamond
disney('beauty-and-the-beast-1991', ('grad', [(0, (30, 60, 150)), (.5, (50, 90, 190)), (1, (14, 30, 90))]), fin=dict(CLAM, vivid=.2),
       title=TT([('Beauty', (240, 200, 110)), ('and the', (240, 200, 110)), ('Beast', (240, 200, 110))], 'pagb', 96, sp=.3, outline=((40, 30, 80), 2)),
       face=ph(.255, .3, .12, 1.4), lcol=WHT)

# Boyz n the Hood (1991): the poster's blue night, its white graffiti BOYZ N THE HOOD cut off it whole, Tre and Doughboy on the car
std('boyz-n-the-hood-1991', ('grad', [(0, (40, 80, 160)), (.6, (12, 26, 60)), (1, (2, 6, 16))]), WHT,
    LC([(0.05, 0.805, 0.948, 0.965)], 130, cuts=[comp_cut(lambda a: _lum(a) > .78, minf=.01)]),
    photo=ph(0.5, 0.33, 0.86, 0.9), pb=(250, 200, 60), lg=WHT, lw=.5, order='LPTCF', credit=['WRITTEN & DIRECTED BY', 'JOHN SINGLETON'], ccol=WHT,
    ft='a', vbox=(250, 200, 60), vink=(20, 20, 20), fcol=(200, 210, 240), fin=RENTAL, seed=1991)

# Cape Fear (1991): Amblin, a slipcase; the storm-blue lake, the poster's white condensed CAPE FEAR lifted, De Niro's eyes in the water
std('cape-fear-1991', ('grad', [(0, (30, 70, 140)), (.6, (8, 20, 46)), (1, (2, 4, 10))]), WHT,
    L((0.104, 0.046, 0.888, 0.176), 110, WHT, mode='light'),
    photo=ph(0.5, 0.48, 0.9, 0.5), pb=(140, 180, 240), lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(236, 122, 40), ink=(20, 16, 12)),
    ft='c', fcol=(190, 206, 236), fin=RENTAL, seed=1991)

# Delicatessen (1991): black, the poster's gold DELICATESSEN cut off it, the plump pig above and the cleaver below the title
std('delicatessen-1991', ('grad', [(0, (40, 34, 20)), (.6, (12, 10, 6)), (1, (2, 2, 2))]), (220, 190, 120),
    LC([(0.103, 0.532, 0.902, 0.596)], 90, cuts=[key_cut(lambda a: (_lum(a) > .4) & (a[..., 0] > a[..., 2]))]),
    photo=ph(0.5, 0.3, 0.8, 0.6), pb=(220, 190, 120), lg=(220, 190, 120), lw=.5, order='LPTCF', credit=['UN FILM DE', 'JEUNET & CARO'], ccol=(220, 190, 120),
    ft='e', fcol=(200, 186, 150), fin=OLD, seed=1991)

# Hook (1991): Amblin, a slipcase; the treasure map's parchment, the poster's red swash Hook cut off it, Hook and Peter face to face
std('hook-1991', ('grad', [(0, (230, 200, 140)), (.5, (200, 160, 90)), (1, (90, 60, 30))]), (180, 20, 30),
    LC([(0.3, 0.6, 0.86, 0.82)], 150, cuts=[comp_cut(lambda a: ((a[..., 0] > .45) & (a[..., 1] < .25)) | (_lum(a) < .15), minf=.05, close=2)]),
    photo=ph(0.5, 0.2, 0.86, 0.6), pb=(140, 20, 30), lg=(60, 30, 14), lw=.55, order='LPTF', ft='b', fcol=(60, 30, 14), fin=RENTAL, seed=1991)

# Night on Earth (1991): the cab's black, the poster's tilted yellow band with its black NIGHT ON EARTH cut off it whole and levelled, Winona Ryder at the wheel (JVC logo)
std('night-on-earth-1991', ('grad', [(0, (30, 30, 40)), (.6, (10, 10, 14)), (1, (2, 2, 4))]), (250, 200, 30),
    LC([(0.0, 0.39, 1.0, 0.61)], 120, cuts=[plate_cut(lambda a: (a[..., 0] > .75) & (a[..., 1] > .6) & (a[..., 2] < .35), rot='auto')]),
    photo=ph(0.6, 0.18, 0.8, 0.6), pb=(250, 200, 30), lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(210, 206, 196), fin=OLD, seed=1991)

# Terminator 2: Judgment Day (1991): the night's steel blue, the poster's white TERMINATOR 2 and red-shadowed JUDGMENT DAY cut off it into one line, Arnold on the Harley with the shotgun
std('terminator-2-judgment-day-1991', ('grad', [(0, (40, 60, 90)), (.6, (10, 16, 26)), (1, (2, 2, 6))]), WHT,
    LC([(0.01, 0.832, 0.955, 0.898), (0.045, 0.898, 0.955, 0.962)], 110, valign='base', margin=0, gapf=.2,
       cuts=[comp_cut(lambda a: (_lum(a) > .7) | ((a[..., 0] > .55) & (a[..., 1] < .3)), minf=.01)] * 2),
    photo=ph(0.58, 0.35, 0.86, 1.1), pb=(200, 30, 30), lg=WHT, lw=.5, order='LTPF',
    ft='a', vbox=(200, 30, 30), fcol=(200, 210, 226), fin=RENTAL, seed=1991)

# The Fisher King (1991): black, the poster's white brushed THE / FISHER / KING cut off it whole, Jack and Parry in the doorway's light under the title
std('the-fisher-king-1991', ('grad', [(0, (60, 40, 20)), (.6, (18, 12, 6)), (1, (2, 2, 2))]), WHT,
    LC([(0.38, 0.7, 0.94, 0.945)], 140, cuts=[comp_cut(lambda a: _lum(a) > .8, minf=.005)]),
    photo=ph(0.38, 0.35, 0.76, 1.2), pb=(250, 200, 120), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(230, 210, 180), fin=RENTAL, seed=1991)

# The Silence of the Lambs (1991): the poster's black, its orange condensed the silence of the lambs keyed off it, the death's-head moth on Clarice's lips
std('the-silence-of-the-lambs-1991', ('grad', [(0, (60, 60, 60)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), (226, 110, 40),
    L((0.075, 0.81, 0.928, 0.903), 96, (226, 110, 40), mode='key', key=(220, 110, 40), t=(70, 160)),
    photo=ph(0.5, 0.45, 0.6, 1.1), pb=(226, 110, 40), lg=WHT, lw=.5, order='LPTCSF', credit=['JODIE FOSTER', 'ANTHONY HOPKINS'], ccol=WHT, dotst=('THRILLER', (226, 110, 40), WHT),
    ft='e', fcol=(220, 210, 200), fin=RENTAL, seed=1991)

# 3 Ninjas (1992): Touchstone, a slipcase; the poster's hot pink into orange, its purple 3 Ninjas cut off it whole and levelled, the three boys mid-kick
std('3-ninjas-1992', ('grad', [(0, (250, 60, 170)), (.5, (240, 120, 120)), (1, (240, 150, 40))]), (80, 30, 120),
    LC([(0.1, 0.735, 0.9, 0.9)], 120, cuts=[comp_cut(lambda a: (a[..., 2] > a[..., 1] + .08) & (_lum(a) < .45), minf=.02, rot=12)]),
    photo=ph(0.5, 0.3, 0.9, 0.8), pb=(80, 30, 120), lg=(60, 20, 90), lw=.55, order='LPTSF', stick=PRC(['$1.99', 'FAMILY']),
    ft='a', vbox=(80, 30, 120), fcol=(60, 20, 90), fin=RENTAL, seed=1992)

# A Few Good Men (1992): the dark of the poster, its gold A FEW GOOD MEN keyed off it, Cruise, Nicholson and Moore in uniform
std('a-few-good-men-1992', ('grad', [(0, (40, 50, 80)), (.6, (12, 14, 26)), (1, (2, 2, 6))]), (230, 190, 90),
    L((0.124, 0.752, 0.892, 0.812), 84, (230, 190, 90), mode='key', key=(220, 180, 70), t=(70, 160)),
    photo=ph(0.5, 0.3, 0.9, 0.7), pb=(230, 190, 90), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(210, 210, 220), fin=RENTAL, seed=1992)

# Aladdin (1992): Disney clamshell; the Genie's blue night, the poster's gold script Aladdin cut off it, Aladdin's face in the diamond
disney('aladdin-1992', ('grad', [(0, (40, 60, 160)), (.5, (60, 110, 210)), (1, (90, 40, 140))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.06, 0.055, 0.935, 0.21)], 130, outline=((60, 30, 10), 1.8), cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .4) & (a[..., 2] < .45), minf=.01, close=2)]),
       face=ph(.66, .477, .1, 1.4), lcol=WHT)

# Batman Returns (1992): the night, the poster's white serif BATMAN / RETURNS lifted into one line, Batman, Catwoman and the Penguin stacked in the dark
std('batman-returns-1992', ('grad', [(0, (30, 40, 70)), (.6, (8, 10, 20)), (1, (0, 0, 2))]), WHT,
    L([(0.198, 0.75, 0.8, 0.818), (0.128, 0.83, 0.874, 0.868)], 96, WHT, mode='light', valign='base', gapf=.2, speck=.05),
    photo=ph(0.5, 0.35, 0.6, 1.4), pb=(160, 190, 240), lg=WHT, lw=.5, order='LTPF',
    ft='d', fcol=(190, 200, 230), fin=RENTAL, seed=1992)

# Hard Boiled (1992): the poster's cream, its black HARD BOILED and red brushed 辣手神探 cut off it in their own colours into one line, Chow Yun-fat with the shotgun (no logo file: Golden Princess, from IMDb's company credits)
std('hard-boiled-1992', ('grad', [(0, (242, 236, 222)), (.6, (226, 214, 190)), (1, (130, 110, 80))]), (20, 20, 20),
    LC([(0.07, 0.765, 0.93, 0.85), (0.4, 0.85, 0.94, 0.93)], 100, valign='base', margin=0, gapf=.25,
       cuts=[key_cut(lambda a: _lum(a) < .3), key_cut(lambda a: (a[..., 0] > a[..., 1] + .2) & (a[..., 0] > .4))]),
    photo=ph(0.45, 0.33, 0.8, 1.0), pb=(190, 40, 30), studio=['GOLDEN PRINCESS'], scol=(20, 20, 20), order='lPTCF', credit=['A JOHN WOO', 'FILM'], ccol=(20, 20, 20),
    ft='c', fcol=(30, 26, 20), fin=RENTAL, seed=1992)

# Home Alone 2: Lost in New York (1992): the skyline's black band, the poster's white HOME ALONE 2 with the red house and the gold 2 and its yellow LOST IN NEW YORK cut off it, Kevin with the newspaper before the Empire State
std('home-alone-2-lost-in-new-york-1992', ('grad', [(0, (20, 20, 24)), (.4, (40, 90, 180)), (1, (10, 30, 80))]), WHT,
    LC([(0.06, 0.09, 0.93, 0.2)], 130, cuts=[comp_cut(lambda a: (_lum(a) > .8) | ((a[..., 0] > .6) & (a[..., 1] < .3)) | ((a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .4)), minf=.005)]),
    photo=ph(0.5, 0.52, 0.7, 1.0), pb=WHT, lg=WHT, lw=.5, order='LTPF',
    ft='e', fcol=(210, 220, 240), fin=RENTAL, seed=1992)

# Man Bites Dog (1992): black, the poster's red MAN BITES DOG keyed off it, Benoît Poelvoorde with the gun under the title (no logo file: Les Artistes Anonymes, from IMDb's company credits)
std('man-bites-dog-1992', ('grad', [(0, (30, 30, 30)), (.6, (10, 10, 10)), (1, (2, 2, 2))]), (200, 30, 30),
    L((0.52, 0.138, 0.988, 0.177), 70, (200, 30, 30), mode='key', key=(200, 30, 30), t=(70, 160)),
    photo=ph(0.55, 0.5, 0.8, 1.2), pb=(200, 30, 30), studio=['LES ARTISTES', 'ANONYMES'], scol=WHT, order='lTPCF', credit=["C'EST ARRIVÉ", 'PRÈS DE CHEZ VOUS'], ccol=WHT,
    ft='b', fcol=(200, 200, 200), fin=OLD, seed=1992)

# Reservoir Dogs (1992): the poster's black, its red condensed RESERVOIR / DOGS keyed off it into one line, the men in black suits walking
std('reservoir-dogs-1992', ('grad', [(0, (60, 40, 30)), (.6, (14, 10, 8)), (1, (2, 2, 2))]), (214, 30, 30),
    L([(0.03, 0.545, 0.755, 0.672), (0.03, 0.668, 0.385, 0.795)], 110, (214, 30, 30), mode='key', key=(214, 30, 30), t=(70, 160), valign='base'),
    photo=ph(0.6, 0.27, 0.8, 0.8), pb=WHT, lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(250, 226, 60)),
    ft='a', vbox=(214, 30, 30), fcol=(210, 200, 196), fin=RENTAL, seed=1992)

# The Mighty Ducks (1992): Disney, a live-action film, so a slipcase; the rink's white, the poster's yellow outlined THE MIGHTY / DUCKS cut off it into one line, Coach Bombay and his team
std('the-mighty-ducks-1992', ('grad', [(0, (30, 90, 60)), (.6, (12, 40, 26)), (1, (2, 10, 6))]), (250, 220, 40),
    LC([(0.05, 0.74, 0.65, 0.814), (0.05, 0.818, 0.655, 0.932)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: ((a[..., 0] > .65) & (a[..., 1] > .55) & (a[..., 2] < .45)) | (_lum(a) < .3), minf=.01)] * 2),
    photo=ph(0.5, 0.3, 0.9, 0.75), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTSF', dotst=('SPORTS', (250, 220, 40), (20, 30, 20)),
    ft='b', fcol=(200, 220, 206), fin=RENTAL, seed=1992)

# The Player (1992): the sunset sky, the poster's white serif The / Player lifted into one line, Tim Robbins hanging in the noose of film
std('the-player-1992', ('grad', [(0, (20, 40, 120)), (.5, (220, 120, 60)), (1, (20, 10, 10))]), WHT,
    LC([(0.555, 0.12, 0.71, 0.25), (0.575, 0.245, 0.89, 0.51)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) > .94, minf=.05)] * 2),
    photo=ph(0.35, 0.62, 0.6, 1.1), pb=(250, 200, 120), lg=WHT, lw=.5, order='LPTCF', credit=['A ROBERT ALTMAN', 'FILM'], ccol=WHT,
    ft='d', fcol=(230, 210, 200), fin=RENTAL, seed=1992)

# Unforgiven (1992): black, the poster's dim orange UNFORGIVEN keyed off it, Eastwood with the rifle in the dark
std('unforgiven-1992', ('grad', [(0, (50, 30, 14)), (.6, (14, 8, 4)), (1, (2, 2, 2))]), (220, 120, 40),
    LC([(0.3, 0.878, 0.7, 0.94)], 90, cuts=[key_cut(lambda a: (a[..., 0] > .45) & (a[..., 2] < .3))]),
    photo=ph(0.6, 0.4, 0.8, 1.2), pb=(220, 120, 40), lg=WHT, lw=.5, order='LPTCF', credit=['CLINT EASTWOOD', 'GENE HACKMAN'], ccol=(230, 190, 150),
    ft='e', fcol=(210, 190, 170), fin=RENTAL, seed=1992)

# Dazed and Confused (1993): the poster's sky blue, its red swirling DAZED AND CONFUSED with the smiley in the O cut off it whole, the kids leaning in
std('dazed-and-confused-1993', ('grad', [(0, (40, 170, 230)), (.5, (30, 130, 200)), (1, (10, 50, 100))]), (220, 40, 50),
    LC([(0.08, 0.29, 0.93, 0.615)], 150, cuts=[comp_cut(lambda a: ((a[..., 0] > .6) & (a[..., 1] < .35)) | ((a[..., 0] > .8) & (a[..., 1] > .7) & (a[..., 2] < .4)) | (_lum(a) > .92), minf=.01, close=3, fillh=True)]),
    photo=ph(0.5, 0.82, 0.9, 0.5), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'RICHARD LINKLATER'], ccol=WHT,
    ft='a', vbox=(220, 40, 50), fcol=(220, 236, 250), fin=RENTAL, seed=1993)

# Fearless (1993): the poster's sky, FEARLESS typeset in heavy capitals in its blue (parked for Ian's logo, see data/logos-wanted.md: the poster's letters are see-through, with sky and cloud showing in them, so both cuts came out holed), Jeff Bridges with his arms out on the building's edge
std('fearless-1993', ('grad', [(0, (200, 226, 240)), (.5, (120, 180, 220)), (1, (20, 60, 100))]), (20, 90, 150),
    T('FEARLESS', 'intbk', 110, (24, 100, 170)),
    photo=ph(0.4, 0.3, 0.6, 1.0), pb=(20, 90, 150), lg=(20, 50, 90), lw=.55, order='LTPF',
    ft='c', fcol=(20, 40, 70), fin=RENTAL, seed=1993)

# Groundhog Day (1993): the dawn sky, GROUNDHOG DAY typeset in heavy capitals in white with the logo's red keyline (parked for Ian's logo, see data/logos-wanted.md: the white letters sit on a pale sky, so a cut lost their insides twice), Bill Murray in the alarm clock
std('groundhog-day-1993', ('grad', [(0, (90, 160, 220)), (.5, (240, 190, 140)), (1, (90, 70, 50))]), WHT,
    T('GROUNDHOG DAY', 'intbk', 90, WHT, outline=((200, 30, 40), 2.6)),
    photo=ph(0.45, 0.52, 0.7, 0.8), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('93 0212', top='COMEDY', fill=(236, 230, 214)),
    ft='d', fcol=(240, 230, 220), fin=RENTAL, seed=1993)

# In the Name of the Father (1993): black, the poster's red condensed IN THE NAME / OF THE FATHER keyed off it into one line, Daniel Day-Lewis's face
std('in-the-name-of-the-father-1993', ('grad', [(0, (40, 30, 26)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (200, 30, 40),
    L([(0.155, 0.035, 0.838, 0.166), (0.105, 0.166, 0.892, 0.295)], 96, (200, 30, 40), mode='key', key=(200, 30, 40), t=(70, 160), valign='base'),
    photo=ph(0.5, 0.6, 0.8, 0.9), pb=(200, 30, 40), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(210, 200, 196), fin=RENTAL, seed=1993)

# Jurassic Park (1993): Amblin and Universal, a slipcase; black, the logo's yellow-framed JURASSIC PARK bar cut off the poster as it is, the T. rex skeleton in the red disc above
std('jurassic-park-1993', ('grad', [(0, (40, 30, 20)), (.6, (12, 8, 6)), (1, (2, 2, 2))]), (250, 190, 40),
    LC([(0.085, 0.36, 0.915, 0.465)], 150, margin=0, cuts=[key_cut(lambda a: _lum(a) >= 0)]),
    photo=ph(0.5, 0.23, 0.62, 0.55), pb=(250, 190, 40), lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(220, 30, 30), fcol=(220, 200, 170), fin=RENTAL, seed=1993)

# Naked (1993): black, the poster's thin lilac naked lifted, David Thewlis's face between the fishnet legs (Channel Four Films logo)
std('naked-1993', ('grad', [(0, (40, 30, 50)), (.6, (12, 10, 16)), (1, (2, 2, 4))]), (210, 200, 240),
    L((0.245, 0.83, 0.755, 0.9), 90, (210, 200, 240), mode='light', speck=0),
    photo=ph(0.4, 0.18, 0.6, 0.85), pb=(210, 200, 240), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'MIKE LEIGH'], ccol=(210, 200, 240),
    ft='e', fcol=(200, 196, 210), fin=OLD, seed=1993)

# Schindler's List (1993): a 2-tape box; black, the poster's silver SCHINDLER'S LIST lifted, the child's hand in the man's
std('schindler-s-list-1993', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), (220, 220, 220),
    L((0.11, 0.074, 0.91, 0.195), 110, (226, 226, 226), mode='light'),
    photo=ph(0.48, 0.5, 0.7, 1.1), pb=(180, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=TWOST((180, 30, 30), WHT),
    ft='b', fcol=(200, 200, 200), fin=RENTAL, seed=1993, **TWO)

# Short Cuts (1993): a 2-tape box; the poster's orange ground, SHORT CUTS typeset in heavy capitals in the shadows' near-black (parked for Ian's logo, see data/logos-wanted.md: the title is spelled by the long shadows of the people, slanting and joined to them, and a cut came out as a tangle), the walkers casting them
std('short-cuts-1993', ('grad', [(0, (230, 130, 70)), (.5, (200, 100, 50)), (1, (90, 40, 16))]), (40, 20, 10),
    T('SHORT CUTS', 'intbk', 110, (40, 20, 10)),
    photo=ph(0.5, 0.13, 0.9, 0.35), pb=(40, 20, 10), lg=(40, 20, 10), lw=.55, order='LPTSF', stick=TWOST((40, 20, 10), (240, 160, 100)),
    ft='a', vbox=(40, 20, 10), vink=(240, 160, 100), fcol=(40, 20, 10), fin=RENTAL, seed=1993, **TWO)

# The Nightmare Before Christmas (1993): Touchstone, so a slipcase; Halloween Town's black, the poster's gold THE / NIGHTMARE / BEFORE / CHRISTMAS cut off it into one line, Jack on the spiral hill before the moon
std('the-nightmare-before-christmas-1993', ('grad', [(0, (30, 30, 60)), (.6, (8, 8, 20)), (1, (2, 2, 4))]), (240, 180, 50),
    LC([(0.6, 0.535, 0.805, 0.582), (0.565, 0.578, 0.94, 0.636), (0.6, 0.632, 0.9, 0.686), (0.565, 0.682, 0.945, 0.738)], 100, valign='base', margin=0, gapf=.25,
       cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .45) & (a[..., 2] < .35), minf=.01, keep=lambda cx, cy: .1 < cy < .9)] * 4),
    photo=ph(0.5, 0.27, 0.6, 0.85), pb=(250, 220, 160), lg=WHT, lw=.5, order='LPTSF', dotst=('HALLOWEEN', (240, 140, 30), (20, 10, 4)),
    ft='c', fcol=(200, 200, 220), fin=RENTAL, seed=1993)

# The Sandlot (1993): the summer sky, the poster's yellow THE SANDLOT cut off it, the boys before the fence
std('the-sandlot-1993', ('grad', [(0, (40, 140, 220)), (.5, (30, 100, 180)), (1, (10, 40, 80))]), (250, 220, 40),
    LC([(0.055, 0.036, 0.94, 0.205)], 130, outline=((20, 40, 100), 2), cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45), minf=.01, close=2)]),
    photo=ph(0.5, 0.55, 0.6, 1.4), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTSF', stick=BAR('93 0407', top='FAMILY', fill=(240, 236, 220)),
    ft='b', fcol=(220, 230, 246), fin=RENTAL, seed=1993)

# True Romance (1993): the poster's white, its purple photo-filled TRUE / ROMANCE cut off it in its own colours into one line, Alabama by the Cadillac
std('true-romance-1993', ('grad', [(0, (246, 244, 248)), (.6, (226, 220, 236)), (1, (120, 100, 140))]), (150, 40, 160),
    LC([(0.03, 0.05, 0.52, 0.233), (0.03, 0.23, 0.97, 0.405)], 110, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: (a[..., 0] > a[..., 1] + .15) & (a[..., 2] > a[..., 1] + .15))] * 2),
    photo=ph(0.5, 0.66, 0.9, 0.5), pb=(150, 40, 160), lg=(60, 20, 70), lw=.55, order='LPTF', ft='d', fcol=(60, 20, 70), fin=RENTAL, seed=1993)

# What's Eating Gilbert Grape (1993): the poster's gold haze, its white WHAT'S / EATING / GILBERT / GRaPE lifted into one line, Johnny Depp's face
std('what-s-eating-gilbert-grape-1993', ('grad', [(0, (230, 180, 70)), (.5, (180, 120, 40)), (1, (60, 36, 10))]), WHT,
    L([(0.49, 0.1, 0.882, 0.155), (0.556, 0.153, 0.945, 0.205), (0.417, 0.203, 0.953, 0.264), (0.513, 0.262, 0.992, 0.325)], 90, WHT, mode='light', valign='base', gapf=.25),
    photo=ph(0.6, 0.65, 0.8, 0.9), pb=WHT, lg=WHT, lw=.5, order='LTPF',
    ft='e', fcol=(250, 230, 200), fin=RENTAL, seed=1993)

# Ace Ventura: Pet Detective (1994): the poster's violet glow, its red ACE VENTURA cut off his card (its arched PET DETECTIVE left off: it broke apart), Jim Carrey's grin
std('ace-ventura-pet-detective-1994', ('grad', [(0, (60, 60, 160)), (.5, (30, 30, 90)), (1, (6, 6, 24))]), (230, 40, 50),
    LC([(0.24, 0.425, 0.85, 0.53)], 110, margin=0, outline=(WHT, 2.4),
       cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .35), minf=.02)]),
    photo=ph(0.45, 0.22, 0.6, 0.9), pb=(230, 40, 50), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.49', 'COMEDY']),
    ft='a', vbox=(230, 40, 50), fcol=(210, 210, 236), fin=RENTAL, seed=1994)

# Chungking Express (1994): the poster's blurred green and blue, its thin black CHUNGKING / EXPRESS cut off it into one line, Faye in the blur (Jet Tone logo)
std('chungking-express-1994', ('grad', [(0, (220, 236, 190)), (.5, (170, 210, 190)), (1, (110, 160, 160))]), (20, 30, 30),
    LC([(0.04, 0.045, 0.965, 0.152), (0.37, 0.148, 0.965, 0.235)], 100, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: _lum(a) < .28)] * 2),
    photo=ph(0.5, 0.6, 0.86, 0.85), pb=(20, 30, 30), lg=(20, 30, 30), lw=.55, order='LTPF',
    ft='c', fcol=(20, 30, 30), fin=RENTAL, seed=1994)

# Clerks (1994): the poster's white, its ransom-note cLeRKS cut off it in its own colours, Dante, Randal and the regulars (View Askew logo)
std('clerks-1994', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (20, 20, 20),
    LC([(0.068, 0.595, 0.9, 0.81)], 120, cuts=[comp_cut(lambda a: _lum(a) < .9, minf=.05, close=2, fillh=True)]),
    photo=ph(0.5, 0.33, 0.86, 0.75), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A FILM BY', 'KEVIN SMITH'], ccol=(20, 20, 20),
    ft='b', fcol=(20, 20, 20), fin=RENTAL, seed=1994)

# D2: The Mighty Ducks (1994): Disney, a live-action film, so a slipcase; the poster's blue, its red D2 and THE MIGHTY DUCKS cut off it in its own colours into one line, the team in their helmets
std('d2-the-mighty-ducks-1994', ('grad', [(0, (60, 70, 170)), (.5, (30, 40, 110)), (1, (8, 10, 40))]), (220, 30, 40),
    LC([(0.13, 0.12, 0.85, 0.24), (0.1, 0.245, 0.895, 0.298)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: ((a[..., 0] > .55) & (a[..., 1] < .3)) | (_lum(a) > .85), minf=.01)] * 2),
    photo=ph(0.5, 0.62, 0.86, 0.85), pb=(220, 30, 40), lg=WHT, lw=.5, order='LTPF',
    ft='e', vbox=(220, 30, 40), fcol=(210, 210, 236), fin=RENTAL, seed=1994)

# Dumb and Dumber (1994): the poster's white, its blue DUMB AND DUMBER with the red AND cut off it in its own colours, Lloyd and Harry
std('dumb-and-dumber-1994', ('grad', [(0, (246, 246, 246)), (.6, (226, 230, 236)), (1, (120, 130, 150))]), (20, 70, 160),
    LC([(0.06, 0.045, 0.942, 0.158)], 120, cuts=[comp_cut(lambda a: ((a[..., 2] > .4) & (a[..., 0] < .35)) | ((a[..., 0] > .6) & (a[..., 1] < .35)) | ((_lum(a) > .85) & (_lum(a) < .97)), minf=.01, fillh=True)]),
    photo=ph(0.5, 0.55, 0.86, 0.9), pb=(20, 70, 160), lg=(20, 70, 160), lw=.55, order='LPTF', ft='d', fcol=(20, 40, 90), fin=RENTAL, seed=1994)

# Ed Wood (1994): Touchstone, a slipcase; black, ED WOOD typeset in heavy capitals in white with a grey keyline (parked for Ian's logo, see data/logos-wanted.md: the poster's chrome letters are tipped back in perspective and their shading broke both cuts), Ed in the director's chair
std('ed-wood-1994', ('grad', [(0, (40, 40, 44)), (.6, (12, 12, 14)), (1, (2, 2, 2))]), WHT,
    T('ED WOOD', 'intbk', 120, WHT, outline=((110, 110, 120), 2)),
    photo=ph(0.5, 0.33, 0.8, 1.1), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(200, 200, 206), fin=RENTAL, seed=1994)

# Forrest Gump (1994): the poster's sky blue, its navy serif Forrest / Gump cut off it into one line, Forrest on the bench
std('forrest-gump-1994', ('grad', [(0, (220, 236, 250)), (.5, (170, 206, 240)), (1, (60, 100, 150))]), (20, 30, 70),
    LC([(0.18, 0.13, 0.8, 0.285), (0.04, 0.285, 0.55, 0.405)], 110, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: (a[..., 2] > a[..., 0] + .1) & (_lum(a) < .4), minf=.02)] * 2),
    photo=ph(0.5, 0.7, 0.9, 0.55), pb=(20, 30, 70), lg=(20, 30, 70), lw=.55, order='LPTSF', stick=BAR('94 0706', top='DRAMA', fill=(236, 236, 226)),
    ft='a', vbox=(20, 30, 70), fcol=(20, 30, 70), fin=RENTAL, seed=1994)

# Hoop Dreams (1994): a 2-tape box would be too much at 174 minutes, so one tape; the dusk blue, the poster's white outlined HOOP / DREAMS cut off it into one line, the player rising to the hoop (Fine Line; director from IMDb)
std('hoop-dreams-1994', ('grad', [(0, (30, 50, 150)), (.5, (20, 30, 90)), (1, (220, 140, 40))]), WHT,
    LC([(0.225, 0.07, 0.775, 0.185), (0.225, 0.182, 0.775, 0.265)], 100, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) > .8, minf=.02)] * 2),
    photo=ph(0.6, 0.6, 0.6, 1.1), pb=(250, 180, 60), lg=WHT, lw=.5, order='LPTCF', credit=['A DOCUMENTARY BY', 'STEVE JAMES'], ccol=WHT,
    ft='e', fcol=(220, 220, 240), fin=OLD, seed=1994)

# Léon: The Professional (1994): black, the poster's yellow THE PROFESSIONAL keyed off it, Léon and Mathilda in the corridor's light
std('leon-the-professional-1994', ('grad', [(0, (50, 40, 20)), (.6, (14, 10, 6)), (1, (2, 2, 2))]), (250, 220, 40),
    L([(0.045, 0.792, 0.11, 0.83), (0.05, 0.828, 0.955, 0.932)], 110, (250, 220, 40), mode='key', key=(250, 220, 40), t=(70, 160), valign='base', speck=0),
    photo=ph(0.5, 0.35, 0.8, 1.0), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTCF', credit=['UN FILM DE', 'LUC BESSON'], ccol=(250, 230, 140),
    ft='b', vbox=(250, 220, 40), vink=(20, 16, 4), fcol=(220, 210, 180), fin=RENTAL, seed=1994)

# Natural Born Killers (1994): the poster's white over black, its yellow slanted NATURAL BORN KILLERS cut off it and levelled, Woody Harrelson in the red glasses
std('natural-born-killers-1994', ('grad', [(0, (50, 50, 50)), (.6, (14, 14, 14)), (1, (2, 2, 2))]), (250, 220, 40),
    LC([(0.04, 0.745, 0.96, 0.87)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45), minf=.02, rot=-7)]),
    photo=ph(0.5, 0.3, 0.86, 0.8), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTSF', dotst=('CRIME', (220, 30, 30), WHT),
    ft='d', fcol=(210, 210, 210), fin=RENTAL, seed=1994)

# Pulp Fiction (1994): the poster's red, its yellow distressed PULP FICTION keyed off it, Mia on the bed with the cigarette
std('pulp-fiction-1994', ('grad', [(0, (190, 30, 30)), (.6, (90, 12, 12)), (1, (14, 2, 2))]), (250, 220, 40),
    LC([(0.09, 0.05, 0.92, 0.185)], 110, cuts=[key_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45))]),
    photo=ph(0.48, 0.55, 0.8, 1.1), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTCF', credit=['A QUENTIN TARANTINO', 'FILM'], ccol=(250, 220, 120),
    ft='a', vbox=(250, 220, 40), vink=(30, 10, 4), fcol=(240, 200, 180), fin=RENTAL, seed=1994)

# Quiz Show (1994): black, the poster's red serif QUIZ SHOW keyed off it, the contestant in his booth's headphones
std('quiz-show-1994', ('grad', [(0, (30, 34, 50)), (.6, (8, 10, 16)), (1, (2, 2, 4))]), (200, 30, 40),
    L((0.16, 0.744, 0.84, 0.812), 84, (200, 30, 40), mode='key', key=(200, 30, 40), t=(70, 160)),
    photo=ph(0.5, 0.4, 0.86, 0.85), pb=(200, 30, 40), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(200, 200, 210), fin=RENTAL, seed=1994)

# The Hudsucker Proxy (1994): the boardroom's red glow, the poster's chrome HUDSUCKER and its spaced gold P R O X Y cut off it into one line, the man leaping from the window
std('the-hudsucker-proxy-1994', ('grad', [(0, (120, 30, 20)), (.5, (60, 14, 8)), (1, (10, 2, 2))]), (220, 220, 230),
    LC([(0.115, 0.752, 0.875, 0.872), (0.125, 0.885, 0.875, 0.902)], 110, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: _lum(a) > .45, minf=.02)] * 2),
    photo=ph(0.5, 0.22, 0.86, 0.7), pb=(230, 200, 140), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(220, 200, 190), fin=RENTAL, seed=1994)

# The Lion King (1994): Disney clamshell; the Pride Lands' red-orange sunset, the poster's white THE LION KING cut off it (its Disney mark left out, it is on the spine already), Simba's face in the diamond
disney('the-lion-king-1994', ('grad', [(0, (150, 40, 20)), (.5, (190, 80, 30)), (1, (90, 20, 14))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.28, 0.425, 0.85, 0.545), (0.21, 0.545, 0.85, 0.665)], 120, valign='base', margin=0, gapf=.2, outline=((120, 40, 20), 1.6),
                cuts=[comp_cut(lambda a: _lum(a) > .88, minf=.005), comp_cut(lambda a: _lum(a) > .88, minf=.03)]),
       face=ph(.53, .16, .2, 1.4), lcol=WHT)

# The Mask (1994): the poster's black, its green MASK cut off it (the tiny dark THE beside it doesn't come through), Jim Carrey in the yellow hat and green face
std('the-mask-1994', ('grad', [(0, (40, 40, 30)), (.6, (12, 12, 8)), (1, (2, 2, 2))]), (110, 200, 120),
    LC([(0.315, 0.655, 0.685, 0.78)], 110, cuts=[comp_cut(lambda a: (a[..., 1] > a[..., 0] + .1) & (a[..., 1] > .4), minf=.002)]),
    photo=ph(0.55, 0.38, 0.86, 0.9), pb=(250, 210, 40), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(220, 220, 180), fin=RENTAL, seed=1994)

# The Shawshank Redemption (1994): the rain's dark, the poster's white spaced SHAWSHANK / REDEMPTION lifted into one line, Andy with his arms out in the rain
std('the-shawshank-redemption-1994', ('grad', [(0, (70, 50, 30)), (.6, (20, 14, 8)), (1, (2, 2, 2))]), WHT,
    L([(0.112, 0.815, 0.902, 0.869), (0.113, 0.874, 0.897, 0.9)], 90, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.33, 0.86, 0.85), pb=(240, 200, 140), lg=WHT, lw=.5, order='LPTCF', credit=['TIM ROBBINS', 'MORGAN FREEMAN'], ccol=WHT,
    ft='d', fcol=(220, 210, 196), fin=RENTAL, seed=1994)

# A Goofy Movie (1995): Disney clamshell; the canyon's purple dusk, the poster's yellow A GOOFY MOVIE cut off it in its own colours, Max's face in the diamond
disney('a-goofy-movie-1995', ('grad', [(0, (120, 60, 150)), (.5, (200, 110, 120)), (1, (40, 120, 170))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.1, 0.07, 0.9, 0.31)], 130, cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45)) | (_lum(a) < .18) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.01, close=2)]),
       face=ph(.6, .655, .14, 1.4), lcol=WHT)

# Ace Ventura: When Nature Calls (1995): the jungle's green, the poster's red ACE VENTURA and its arched WHEN NATURE CALLS cut off it whole, Ace mid-leap in the striped trousers
std('ace-ventura-when-nature-calls-1995', ('grad', [(0, (40, 140, 90)), (.5, (20, 90, 60)), (1, (6, 40, 30))]), (230, 40, 40),
    LC([(0.05, 0.455, 0.95, 0.65)], 140, cuts=[comp_cut(lambda a: ((a[..., 0] > .6) & (a[..., 1] < .35)) | ((a[..., 0] > .75) & (a[..., 1] > .6) & (a[..., 2] < .4)), minf=.005, close=2)]),
    photo=ph(0.4, 0.18, 0.7, 1.0), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTF', dotst=('COMEDY', (250, 220, 40), (20, 20, 20)),
    ft='b', fcol=(210, 236, 220), fin=RENTAL, seed=1995)

# Bad Boys (1995): the poster's orange haze, its black stencilled BAD BOYS between the rules cut off it, the three of them walking out with the Porsche
std('bad-boys-1995', ('grad', [(0, (250, 200, 80)), (.5, (240, 160, 50)), (1, (130, 70, 20))]), (20, 16, 10),
    LC([(0.07, 0.115, 0.93, 0.248)], 110, cuts=[key_cut(lambda a: _lum(a) < .3)]),
    photo=ph(0.5, 0.6, 0.9, 0.85), pb=(20, 16, 10), lg=(20, 16, 10), lw=.55, order='LPTF', ft='a', vbox=(20, 16, 10), vink=(250, 200, 80), fcol=(30, 20, 10), fin=RENTAL, seed=1995)

# Batman Forever (1995): the night's blue, the poster's white BATMAN / FOREVER lifted into one line, Batman, Robin and the villains crowded below
std('batman-forever-1995', ('grad', [(0, (30, 50, 110)), (.6, (8, 14, 36)), (1, (0, 2, 8))]), WHT,
    L([(0.185, 0.77, 0.828, 0.83), (0.29, 0.846, 0.73, 0.886)], 96, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.38, 0.86, 0.95), pb=(100, 200, 230), lg=WHT, lw=.5, order='LPTSF', stick=BAR('95 0616', top='ACTION', fill=(226, 230, 240)),
    ft='c', fcol=(180, 196, 230), fin=RENTAL, seed=1995)

# Braveheart (1995): the poster's fire orange, its white serif BRAVEHEART lifted, Wallace with the sword
std('braveheart-1995', ('grad', [(0, (230, 120, 40)), (.5, (120, 50, 20)), (1, (20, 8, 4))]), WHT,
    L((0.045, 0.865, 0.952, 0.937), 90, WHT, mode='light'),
    photo=ph(0.55, 0.35, 0.7, 1.2), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(240, 210, 190), fin=RENTAL, seed=1995)

# Casino (1995): black, the poster's gold CASINO and the red dice cut off it, De Niro, Stone and Pesci
std('casino-1995', ('grad', [(0, (40, 30, 20)), (.6, (12, 8, 6)), (1, (2, 2, 2))]), (230, 160, 60),
    LC([(0.1, 0.718, 0.897, 0.825)], 110, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 2] < .4) & (a[..., 0] > a[..., 2] + .2), minf=.02)]),
    photo=ph(0.5, 0.33, 0.9, 0.8), pb=(230, 160, 60), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(220, 200, 170), fin=RENTAL, seed=1995)

# Clueless (1995): the poster's white, its black oval with the white Clueless cut off it whole, Cher, Dionne and Tai on the stairs
std('clueless-1995', ('grad', [(0, (250, 240, 246)), (.6, (240, 220, 230)), (1, (150, 110, 130))]), (20, 20, 20),
    LC([(0.13, 0.835, 0.865, 0.99)], 130, cuts=[plate_cut(lambda a: _lum(a) < .3)]),
    photo=ph(0.48, 0.35, 0.6, 1.4), pb=(220, 30, 60), lg=(20, 20, 20), lw=.55, order='LPTSF', stick=PRC(['$2.49', 'COMEDY']),
    ft='e', fcol=(30, 20, 26), fin=RENTAL, seed=1995)

# Dead Man (1995): the poster's grey, its white brushed DEAD / MAN lifted into one line, the riders in the ferns (Pandora logo)
std('dead-man-1995', ('grad', [(0, (120, 120, 120)), (.6, (50, 50, 50)), (1, (10, 10, 10))]), WHT,
    LC([(0.12, 0.175, 0.91, 0.38), (0.14, 0.395, 0.87, 0.575)], 110, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: _lum(a) > .68, minf=.02, close=2)] * 2),
    photo=ph(0.5, 0.82, 0.9, 0.45), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'JIM JARMUSCH'], ccol=WHT,
    ft='a', fcol=(220, 220, 220), fin=OLD, seed=1995)

# Die Hard with a Vengeance (1995): the fireball's orange, DIE HARD typeset in heavy capitals in the logo's red with a white keyline over WITH A VENGEANCE in white (parked for Ian's logo, see data/logos-wanted.md: the red letters sit in the fireball of nearly their own colour, so the cut broke up), McClane's bloodied face
std('die-hard-with-a-vengeance-1995', ('grad', [(0, (200, 100, 40)), (.5, (110, 40, 14)), (1, (14, 4, 2))]), WHT,
    [T('DIE HARD', 'intbk', 110, (210, 30, 30), outline=(WHT, 2.4)), T('WITH A VENGEANCE', 'intbk', 46, WHT)], tgap=8,
    photo=ph(0.5, 0.33, 0.86, 0.9), pb=WHT, lg=WHT, lw=.5, order='LPTF',
    ft='e', vbox=(200, 30, 30), fcol=(240, 210, 190), fin=RENTAL, seed=1995)

# Friday (1995): the poster's blue, its white Friday with the red shadow cut off it, Craig and Smokey on the porch
std('friday-1995', ('grad', [(0, (30, 70, 160)), (.6, (10, 26, 70)), (1, (2, 6, 20))]), WHT,
    LC([(0.14, 0.05, 0.86, 0.235)], 120, cuts=[comp_cut(lambda a: (_lum(a) > .78) | ((a[..., 0] > .55) & (a[..., 1] < .3)), minf=.01)]),
    photo=ph(0.5, 0.55, 0.9, 0.8), pb=(220, 40, 40), lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(200, 210, 240), fin=RENTAL, seed=1995)

# GoldenEye (1995): the poster's midnight blue, its silver GOLDENEYE cut off it (parked for Ian's logo, see data/logos-wanted.md: the gold 007 and gun barrel sit on Bond's sleeve and wouldn't cut, and the silver E's shine breaks up), Bond's kiss
std('goldeneye-1995', ('grad', [(0, (30, 50, 90)), (.6, (8, 14, 30)), (1, (2, 2, 6))]), (220, 220, 230),
    LC([(0.045, 0.495, 0.955, 0.59)], 110, cuts=[comp_cut(lambda a: (_lum(a) > .8) & (_sat(a) < .15), minf=.05)]),
    photo=ph(0.5, 0.2, 0.86, 0.6), pb=(220, 190, 90), lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(200, 170, 70), vink=(10, 10, 20), fcol=(200, 206, 226), fin=RENTAL, seed=1995)

# Heat (1995): the night's blue, the poster's spaced blue chrome H E A T cut off it, Pacino and De Niro
std('heat-1995', ('grad', [(0, (20, 40, 80)), (.6, (6, 12, 26)), (1, (0, 2, 6))]), (120, 180, 240),
    LC([(0.1, 0.885, 0.89, 0.955)], 90, cuts=[comp_cut(lambda a: (a[..., 2] > .45) & (a[..., 2] > a[..., 0] + .08) | (_lum(a) > .85), minf=.05)]),
    photo=ph(0.5, 0.3, 0.86, 0.8), pb=(120, 180, 240), lg=WHT, lw=.5, order='LPTCF', credit=['A MICHAEL MANN', 'FILM'], ccol=(170, 206, 246),
    ft='d', fcol=(170, 190, 220), fin=RENTAL, seed=1995)

# Jumanji (1995): the jungle's green, JUMANJI typeset in heavy capitals in the logo's gold with a dark keyline (parked for Ian's logo, see data/logos-wanted.md: the carved gold letters stand in leaves and vines of the same colours, so the cut came out in pieces), the stampede under the title
std('jumanji-1995', ('grad', [(0, (40, 120, 40)), (.5, (20, 70, 24)), (1, (6, 24, 8))]), (250, 200, 40),
    T('JUMANJI', 'intbk', 120, (250, 200, 40), outline=((60, 30, 10), 2.4)),
    photo=ph(0.5, 0.68, 0.86, 0.75), pb=(250, 200, 40), lg=WHT, lw=.5, order='LTPSF', stick=BAR('95 1215', top='FAMILY', fill=(240, 232, 210)),
    ft='b', fcol=(220, 236, 200), fin=RENTAL, seed=1995)

# Kids (1995): black, the poster's white brushed KIDS lifted, the tinted faces of the kids (Independent Pictures logo; director from IMDb)
std('kids-1995', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.1, 0.405, 0.9, 0.585)], 130, cuts=[comp_cut(lambda a: _lum(a) > .82, minf=.02)]),
    photo=ph(0.5, 0.75, 0.9, 0.5), pb=(220, 70, 60), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(200, 200, 200), fin=OLD, seed=1995)

# La Haine (1995): black, the poster's white distressed LA HAINE lifted, Vinz, Saïd and Hubert in black and white
std('la-haine-1995', ('grad', [(0, (60, 60, 60)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), WHT,
    LC([(0.035, 0.575, 0.955, 0.682)], 120, cuts=[key_cut(lambda a: _lum(a) > .75)]),
    photo=ph(0.5, 0.36, 0.9, 0.55), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['UN FILM DE', 'MATHIEU KASSOVITZ'], ccol=WHT,
    ft='e', fcol=(210, 210, 210), fin=OLD, seed=1995)

# Mallrats (1995): the poster's sky blue, its green spiky Mallrats cut off it whole and levelled, T.S. and Brodie
std('mallrats-1995', ('grad', [(0, (60, 170, 230)), (.5, (30, 120, 200)), (1, (8, 40, 90))]), (140, 210, 70),
    LC([(0.02, 0.06, 0.94, 0.33)], 140, cuts=[comp_cut(lambda a: ((a[..., 1] > .5) & (a[..., 1] > a[..., 2] + .1) & (a[..., 0] < .85)) | (_lum(a) < .2), top=1, close=3, rot=14)]),
    photo=ph(0.55, 0.5, 0.86, 0.8), pb=(140, 210, 70), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$1.99', 'COMEDY']),
    ft='d', fcol=(220, 236, 250), fin=RENTAL, seed=1995)

# Mortal Kombat (1995): black, the poster's red serif MORTAL / KOMBAT keyed off it into one line, the gold dragon emblem
std('mortal-kombat-1995', ('grad', [(0, (60, 20, 10)), (.6, (16, 6, 4)), (1, (2, 2, 2))]), (210, 30, 30),
    L([(0.228, 0.054, 0.782, 0.154), (0.228, 0.16, 0.784, 0.262)], 100, (210, 30, 30), mode='key', key=(200, 30, 30), t=(70, 160), valign='base'),
    photo=ph(0.5, 0.55, 0.6, 1.3), pb=(230, 170, 60), lg=WHT, lw=.5, order='LPTSF', dotst=('ACTION', (230, 170, 60), (20, 10, 4)),
    ft='a', vbox=(210, 30, 30), fcol=(220, 190, 170), fin=RENTAL, seed=1995)

# Pocahontas (1995): Disney clamshell; the sunset's orange, the poster's white brushed POCAHONTAS cut off it, Pocahontas's face in the diamond
disney('pocahontas-1995', ('grad', [(0, (200, 60, 30)), (.5, (230, 130, 40)), (1, (40, 30, 80))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.085, 0.81, 0.925, 0.928)], 130, outline=((40, 30, 90), 2), cuts=[comp_cut(lambda a: _lum(a) > .78, minf=.02)]),
       face=ph(.39, .49, .12, 1.4), lcol=WHT)

# Se7en (1995): the dark, the poster's scratched grey SE7EN with its red 7 cut off it in its own colours, Pitt and Freeman
std('se7en-1995', ('grad', [(0, (60, 56, 46)), (.6, (16, 14, 12)), (1, (2, 2, 2))]), (200, 200, 200),
    LC([(0.1, 0.81, 0.9, 0.935)], 110, cuts=[comp_cut(lambda a: ((_lum(a) > .3) & (_sat(a) < .25)) | ((a[..., 0] > .5) & (a[..., 1] < .25)), minf=.05, close=4, fillh=True)]),
    photo=ph(0.5, 0.35, 0.9, 0.7), pb=(200, 30, 30), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(190, 186, 176), fin=RENTAL, seed=1995)

# The Usual Suspects (1995): black, the poster's white the / Usual / Suspects cut off it whole, the five in the line-up
std('the-usual-suspects-1995', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.17, 0.745, 0.83, 0.91)], 130, cuts=[comp_cut(lambda a: _lum(a) > .82, minf=.02)]),
    photo=ph(0.5, 0.45, 0.9, 0.55), pb=WHT, lg=WHT, lw=.5, order='LPTCSF', credit=['KEVIN SPACEY', 'GABRIEL BYRNE'], ccol=WHT, stick=BAR('95 0816', top='MYSTERY', fill=(232, 228, 216)),
    ft='a', fcol=(200, 200, 200), fin=RENTAL, seed=1995)

# Toy Story (1995): Pixar clamshell, built like Toy Story 4 and 5; the poster's sky blue, its yellow TOY and red STORY plate cut off it, Woody's face in the diamond
disney('toy-story-1995', ('strip', dict(x0=.0, blur=14, wash=((36, 90, 200), .6))), fin=dict(CLAM, vivid=.3),
       title=LC([(0.03, 0.04, 0.47, 0.168), (0.03, 0.155, 0.48, 0.255)], 170, gapf=.05, cuts=[ts_letters, ts_plate(.25, .8)]),
       face=ph(.22, .515, .16, 1.4))

# Twelve Monkeys (1995): black, the poster's red brushed 12 MONKEYS keyed off it, Bruce Willis in the half-light with the red circle
std('twelve-monkeys-1995', ('grad', [(0, (40, 30, 30)), (.6, (12, 8, 8)), (1, (2, 2, 2))]), (210, 30, 30),
    L((0.055, 0.838, 0.94, 0.968), 110, (210, 30, 30), mode='key', key=(210, 30, 30), t=(70, 160)),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(210, 30, 30), lg=WHT, lw=.5, order='LPTF', ft='e', vbox=(210, 30, 30), fcol=(200, 196, 196), fin=RENTAL, seed=1995)

# Beavis and Butt-Head Do America (1996): the desert road, the poster's red BEAVIS AND BUTT-HEAD DO AMERICA cut off it word by word into one line, Beavis and Butt-Head's faces
std('beavis-and-butt-head-do-america-1996', ('grad', [(0, (120, 190, 240)), (.5, (200, 210, 230)), (1, (60, 60, 90))]), (210, 30, 30),
    LC([(0.42, 0.38, 0.62, 0.425), (0.36, 0.44, 0.785, 0.485), (0.45, 0.488, 0.58, 0.54), (0.29, 0.548, 0.745, 0.612)], 100, valign='base', margin=0, gapf=.25,
       cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), minf=.02)] * 4),
    photo=ph(0.5, 0.2, 0.9, 0.5), pb=(210, 30, 30), lg=(30, 30, 40), lw=.55, order='LPTF',
    ft='b', fcol=(30, 30, 40), fin=RENTAL, seed=1996)

# Bottle Rocket (1996): the poster's pink, its red BOTTLE / ROCKET keyed off it into one line, the motel under the title
std('bottle-rocket-1996', ('grad', [(0, (250, 210, 220)), (.5, (240, 190, 200)), (1, (150, 110, 120))]), (210, 30, 30),
    L([(0.222, 0.078, 0.775, 0.153), (0.22, 0.167, 0.782, 0.244)], 96, (210, 30, 30), mode='key', key=(210, 30, 30), t=(70, 160), valign='base'),
    photo=ph(0.5, 0.36, 0.9, 0.3), pb=(210, 30, 30), lg=(60, 20, 30), lw=.55, order='LTPCF', credit=['A FILM BY', 'WES ANDERSON'], ccol=(60, 20, 30),
    ft='c', fcol=(60, 20, 30), fin=RENTAL, seed=1996)

# Box of Moonlight (1996): the poster's white, BOX OF MOONLIGHT typeset in condensed capitals in its red (parked for Ian's logo, see data/logos-wanted.md: the small OF sits on a tilted black tag that wouldn't cut with the red words), the man with the clock (Lakeshore logo; director from IMDb)
std('box-of-moonlight-1996', ('grad', [(0, (246, 248, 250)), (.6, (226, 232, 240)), (1, (120, 130, 150))]), (190, 40, 40),
    TT([('BOX', (196, 50, 44)), ('OF', (30, 30, 40)), ('MOONLIGHT', (196, 50, 44))], 'hcnb', 100, sp=.3),
    photo=ph(0.7, 0.38, 0.6, 1.3), pb=(190, 40, 40), lg=(40, 40, 60), lw=.55, order='LPTCF', credit=['A FILM BY', 'TOM DiCILLO'], ccol=(40, 40, 60),
    ft='d', fcol=(40, 40, 60), fin=OLD, seed=1996)

# Eraser (1996): the poster's steel greys, its green spaced E R A S E R cut off it, Arnold in the leather jacket
std('eraser-1996', ('grad', [(0, (90, 100, 90)), (.6, (24, 28, 24)), (1, (2, 4, 2))]), (150, 220, 90),
    LC([(0.05, 0.81, 0.94, 0.885)], 90, cuts=[comp_cut(lambda a: (a[..., 1] > .45) & (a[..., 1] > a[..., 2] + .12), minf=.05)]),
    photo=ph(0.7, 0.3, 0.6, 1.3), pb=(150, 220, 90), lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(150, 220, 90), vink=(10, 20, 10), fcol=(200, 210, 200), fin=RENTAL, seed=1996)

# Fargo (1996): the poster's cross-stitch white, its red script Fargo cut off it, the stitched body in the snow (PolyGram logo)
std('fargo-1996', ('grad', [(0, (244, 240, 236)), (.6, (226, 220, 214)), (1, (130, 120, 110))]), (190, 30, 30),
    LC([(0.14, 0.105, 0.822, 0.288)], 120, cuts=[key_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .35))]),
    photo=ph(0.5, 0.55, 0.86, 0.6), pb=(190, 30, 30), lg=(60, 30, 30), lw=.55, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(60, 30, 30),
    ft='b', fcol=(60, 30, 30), fin=RENTAL, seed=1996)

# James and the Giant Peach (1996): Walt Disney Pictures, so the clamshell; the sky over the peach, James and the Giant Peach typeset in white with an orange keyline (parked for Ian's logo, see data/logos-wanted.md: the white letters sit on the peach's pale highlight, and the cut lost James), James's face in the diamond
disney('james-and-the-giant-peach-1996', ('grad', [(0, (90, 170, 230)), (.5, (240, 140, 50)), (1, (60, 120, 40))]), fin=dict(CLAM, vivid=.2),
       title=TT([('James', WHT), ('and the', (40, 30, 20)), ('Giant Peach', WHT)], 'popb', 90, sp=.3, outline=((170, 70, 10), 2.2)),
       face=ph(.48, .735, .09, 1.4), lcol=WHT, studio=False)

# Jingle All the Way (1996): the poster's white, its red Jingle All The Way cut off it whole, Arnold diving for the Turbo-Man box
std('jingle-all-the-way-1996', ('grad', [(0, (246, 244, 244)), (.6, (226, 226, 230)), (1, (120, 120, 140))]), (210, 30, 30),
    LC([(0.385, 0.105, 0.875, 0.352)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] < .3), minf=.02)]),
    photo=ph(0.45, 0.5, 0.86, 0.75), pb=(30, 120, 60), lg=(30, 30, 40), lw=.55, order='LPTSF', stick=BAR('96 1122', top='FAMILY', fill=(236, 240, 230)),
    ft='d', fcol=(30, 30, 40), fin=RENTAL, seed=1996)

# La Promesse (1996): the poster's pale grey, its pencilled la promesse lifted and darkened, Igor and Assita on the bridge (Les Films du Fleuve logo)
std('la-promesse-1996', ('grad', [(0, (226, 226, 220)), (.6, (200, 200, 194)), (1, (110, 110, 104))]), (60, 60, 60),
    L((0.04, 0.2, 0.96, 0.37), 110, (50, 50, 54), mode='dark', speck=0),
    photo=ph(0.6, 0.72, 0.9, 0.45), pb=(60, 60, 60), lg=(60, 60, 60), lw=.55, order='LPTCF', credit=['UN FILM DE', 'JEAN-PIERRE ET', 'LUC DARDENNE'], ccol=(60, 60, 60),
    ft='e', fcol=(50, 50, 50), fin=OLD, seed=1996)

# Mars Attacks! (1996): the burning city's red, the poster's red slanted MARS ATTACKS! cut off it whole and levelled, the Martian with the ray gun
std('mars-attacks-1996', ('grad', [(0, (60, 70, 140)), (.5, (140, 40, 30)), (1, (14, 4, 2))]), (220, 30, 30),
    LC([(0.06, 0.785, 0.95, 0.915)], 130, outline=((250, 240, 200), 2.2), cuts=[comp_cut(lambda a: (a[..., 0] > .5) & (a[..., 1] < .25), minf=.02, rot=-8)]),
    photo=ph(0.55, 0.35, 0.86, 0.9), pb=(140, 230, 90), lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(220, 200, 200), fin=RENTAL, seed=1996)

# Matilda (1996): the night's starry blue, Matilda typeset letter by letter in the logo's rainbow colours (parked for Ian's logo, see data/logos-wanted.md: each letter is shaded from light to dark, so two colour cuts lost the t, i and l), Matilda with the floating orb under the title
std('matilda-1996', ('grad', [(0, (30, 60, 140)), (.6, (10, 20, 60)), (1, (2, 4, 16))]), (250, 220, 60),
    TT([('M', (220, 40, 50)), ('a', (250, 140, 30)), ('t', (250, 220, 50)), ('i', (90, 190, 70)), ('l', (60, 160, 230)), ('d', (240, 200, 40)), ('a', (180, 80, 200))], 'pagb', 120, sp=0, outline=(WHT, 1.6)),
    photo=ph(0.45, 0.5, 0.86, 0.9), pb=(250, 220, 60), lg=WHT, lw=.5, order='LTPSF', stick=PRC(['$1.99', 'FAMILY']),
    ft='b', fcol=(200, 210, 240), fin=RENTAL, seed=1996)

# Paradise Lost: The Child Murders at Robin Hood Hills (1996): the poster's sepia, its black PARADISE / LOST and THE CHILD MURDERS AT ROBIN HOOD HILLS cut off it into one line, the three boys' faces (no logo file: HBO, from IMDb's company credits; directors from IMDb)
std('paradise-lost-the-child-murders-at-robin-hood-hills-1996', ('grad', [(0, (180, 110, 60)), (.5, (110, 60, 30)), (1, (20, 10, 4))]), (20, 14, 8),
    LC([(0.14, 0.6, 0.85, 0.69), (0.3, 0.69, 0.68, 0.788)], 100, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: _lum(a) < .18, minf=.02)] * 2),
    photo=ph(0.5, 0.2, 0.9, 0.5), pb=(20, 14, 8), studio=['HBO'], scol=(20, 14, 8), order='lPTCF', credit=['A DOCUMENTARY BY', 'BERLINGER &', 'SINOFSKY'], ccol=(240, 200, 160),
    ft='a', fcol=(240, 200, 160), fin=OLD, seed=1996)

# Primal Fear (1996): the storm's dark gold, the poster's white serif PRIMAL · FEAR lifted, Richard Gere in the coat
std('primal-fear-1996', ('grad', [(0, (120, 110, 70)), (.6, (34, 30, 18)), (1, (4, 4, 2))]), WHT,
    L((0.052, 0.848, 0.948, 0.918), 84, WHT, mode='light'),
    photo=ph(0.32, 0.4, 0.5, 1.3), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(220, 214, 196), fin=RENTAL, seed=1996)

# Space Jam (1996): the space blue, the poster's green-and-orange SPACE JAM cut off it in its own colours, Michael Jordan and Bugs
std('space-jam-1996', ('grad', [(0, (30, 40, 120)), (.6, (10, 14, 50)), (1, (2, 2, 14))]), (140, 210, 60),
    LC([(0.165, 0.09, 0.89, 0.31)], 130, cuts=[comp_cut(lambda a: ((a[..., 1] > .45) & (a[..., 1] > a[..., 2] + .05)) | ((a[..., 0] > .7) & (a[..., 2] < .35)), minf=.01, close=2)]),
    photo=ph(0.5, 0.6, 0.9, 0.7), pb=(250, 140, 40), lg=WHT, lw=.5, order='LPTSF', dotst=('FAMILY', (250, 140, 40), WHT),
    ft='e', fcol=(200, 206, 240), fin=RENTAL, seed=1996)

# The Cable Guy (1996): the lightning's blue, the poster's white THE / CABLE / GUY lifted into one line, Jim Carrey with the cable
std('the-cable-guy-1996', ('grad', [(0, (30, 60, 170)), (.6, (10, 20, 70)), (1, (2, 4, 20))]), WHT,
    L([(0.375, 0.078, 0.585, 0.16), (0.322, 0.158, 0.645, 0.238), (0.195, 0.237, 0.605, 0.32)], 100, WHT, mode='light', valign='base', gapf=.2),
    photo=ph(0.6, 0.6, 0.86, 0.85), pb=(120, 200, 250), lg=WHT, lw=.5, order='LTPF',
    ft='a', fcol=(200, 210, 246), fin=RENTAL, seed=1996)

# The Hunchback of Notre Dame (1996): Disney clamshell; the cathedral's red glow, the poster's white THE HUNCHBACK OF NOTRE DAME cut off it, Quasimodo in the diamond
disney('the-hunchback-of-notre-dame-1996', ('grad', [(0, (180, 60, 40)), (.5, (110, 30, 24)), (1, (30, 8, 8))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.2, 0.815, 0.83, 0.948)], 130, cuts=[comp_cut(lambda a: _lum(a) > .82, minf=.01)]),
       face=ph(.53, .62, .14, 1.4), lcol=WHT)

# When We Were Kings (1996): the poster's cream, its black WHEN WE WERE / KINGS cut off it into one line, MUHAMMAD ALI under it in the poster's rust, Ali in the painted Africa (no logo file: Das Films, from IMDb's company credits; director from IMDb)
std('when-we-were-kings-1996', ('grad', [(0, (246, 240, 226)), (.6, (230, 220, 200)), (1, (140, 120, 90))]), (20, 20, 20),
    LC([(0.245, 0.817, 0.755, 0.858), (0.245, 0.858, 0.755, 0.97)], 110, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: _lum(a) < .3)] * 2),
    photo=ph(0.5, 0.3, 0.86, 0.75), pb=(170, 80, 50), studio=['DAS FILMS'], scol=(20, 20, 20), order='lPTCF', credit=['MUHAMMAD ALI'], ccol=(180, 90, 60),
    ft='b', fcol=(40, 30, 20), fin=OLD, seed=1996)

# As Good as It Gets (1997): the poster's sky, its red small-caps AS GOOD AS IT GETS keyed off it, Jack Nicholson with the dog
std('as-good-as-it-gets-1997', ('grad', [(0, (200, 226, 246)), (.5, (150, 200, 240)), (1, (60, 100, 150))]), (190, 30, 40),
    L((0.05, 0.158, 0.95, 0.224), 76, (190, 30, 40), mode='key', key=(190, 40, 50), t=(70, 160)),
    photo=ph(0.5, 0.45, 0.86, 0.75), pb=(190, 30, 40), lg=(30, 40, 70), lw=.55, order='LPTF', ft='a', vbox=(190, 30, 40), fcol=(30, 40, 70), fin=RENTAL, seed=1997)

# Austin Powers: International Man of Mystery (1997): the Union Jack pink, AUSTIN POWERS and INTERNATIONAL MAN OF MYSTERY typeset in heavy capitals in the logo's yellow with a black keyline (parked for Ian's logo, see data/logos-wanted.md: the outlined letters sit on the flag's pinks and whites, and the cut came out a jumble), Austin and Vanessa
std('austin-powers-international-man-of-mystery-1997', ('grad', [(0, (240, 60, 160)), (.5, (160, 40, 140)), (1, (30, 20, 80))]), (250, 230, 60),
    [T('AUSTIN POWERS', 'intbk', 90, WHT, outline=((20, 20, 20), 2.2)), T('INTERNATIONAL MAN OF MYSTERY', 'intbk', 50, (250, 230, 60), outline=((20, 20, 20), 1.8))], tgap=8,
    photo=ph(0.5, 0.18, 0.7, 0.75), pb=(250, 230, 60), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.99', 'COMEDY']),
    ft='e', fcol=(250, 220, 240), fin=RENTAL, seed=1997)

# Batman & Robin (1997): the night's blue, the poster's white chrome BATMAN & ROBIN lifted into one line, Freeze over the others
std('batman-robin-1997', ('grad', [(0, (30, 60, 140)), (.6, (8, 16, 50)), (1, (0, 2, 12))]), WHT,
    L([(0.21, 0.458, 0.81, 0.5), (0.365, 0.503, 0.8, 0.556)], 96, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.2, 0.7, 0.7), pb=(120, 200, 250), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(180, 200, 240), fin=RENTAL, seed=1997)

# Boogie Nights (1997): black, the poster's red outlined BOOGIE NIGHTS cut off it, the star of faces
std('boogie-nights-1997', ('grad', [(0, (60, 20, 30)), (.6, (16, 6, 8)), (1, (2, 2, 2))]), (220, 50, 50),
    LC([(0.095, 0.745, 0.92, 0.815)], 100, cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .35), minf=.03, close=2, fillh=True)]),
    photo=ph(0.5, 0.32, 0.86, 0.85), pb=(250, 200, 60), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'PAUL THOMAS ANDERSON'], ccol=WHT,
    ft='d', vbox=(220, 50, 50), fcol=(220, 196, 196), fin=RENTAL, seed=1997)

# Chasing Amy (1997): the poster's white, its black serif chasing and red AMY cut off it into one line, Holden, Alyssa and the gang (View Askew logo)
std('chasing-amy-1997', ('grad', [(0, (60, 60, 60)), (.6, (20, 20, 20)), (1, (2, 2, 2))]), WHT,
    LC([(0.19, 0.775, 0.895, 0.845), (0.1, 0.84, 0.89, 0.9)], 100, valign='base', margin=0, gapf=.2,
       cuts=[comp_cut(lambda a: _lum(a) > .92, minf=.03), key_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3))]),
    photo=ph(0.6, 0.35, 0.8, 0.8), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', dotst=('ROMANCE', (200, 30, 30), WHT),
    ft='b', fcol=(210, 210, 210), fin=RENTAL, seed=1997)

# Donnie Brasco (1997): the poster's amber, its white slanted DONNIE BRASCO cut off it and levelled, Pacino and Depp walking
std('donnie-brasco-1997', ('grad', [(0, (220, 150, 50)), (.5, (140, 80, 30)), (1, (20, 10, 4))]), WHT,
    LC([(0.0, 0.44, 0.99, 0.605)], 120, cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.03, rot=-9)]),
    photo=ph(0.5, 0.2, 0.9, 0.4), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='a', fcol=(240, 220, 190), fin=RENTAL, seed=1997)

# Funny Games (1997): black, the poster's red stencilled FUNNY / GAMES keyed off it into one line, the boy in the white mask's hood (Wega Film logo)
std('funny-games-1997', ('grad', [(0, (40, 30, 30)), (.6, (12, 8, 8)), (1, (2, 2, 2))]), (210, 30, 30),
    L([(0.115, 0.565, 0.885, 0.69), (0.115, 0.685, 0.885, 0.805)], 110, (210, 30, 30), mode='key', key=(200, 30, 30), t=(70, 160), valign='base'),
    photo=ph(0.5, 0.25, 0.86, 0.6), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['EIN FILM VON', 'MICHAEL HANEKE'], ccol=WHT,
    ft='e', fcol=(200, 196, 196), fin=OLD, seed=1997)

# Good Will Hunting (1997): the autumn gold, the poster's white serif GOOD WILL HUNTING lifted, Matt Damon and Robin Williams on the bench
std('good-will-hunting-1997', ('grad', [(0, (200, 150, 50)), (.5, (110, 80, 30)), (1, (16, 12, 4))]), WHT,
    L((0.11, 0.872, 0.892, 0.918), 76, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.5, 0.86, 0.8), pb=WHT, lg=WHT, lw=.5, order='LTPF', ft='b', fcol=(240, 220, 190), fin=RENTAL, seed=1997)

# Hercules (1997): Disney clamshell; the Greek sky, the poster's gold Greek-key HERCULES cut off it in its own colours, Hercules's face in the diamond
disney('hercules-1997', ('grad', [(0, (30, 90, 180)), (.5, (60, 140, 220)), (1, (20, 60, 130))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.03, 0.055, 0.97, 0.19)], 140, outline=((30, 20, 60), 2), cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .45) & (a[..., 2] < .45)) | ((a[..., 0] > .6) & (a[..., 1] < .3) & (a[..., 2] < .3)), minf=.01, close=2)]),
       face=ph(.42, .42, .55, 1.4), lcol=WHT)

# Home Alone 3 (1997): the poster's navy, its white HOME ALONE with the red house and gold 3 cut off it, Alex with his binoculars and the crooks at the door
std('home-alone-3-1997', ('grad', [(0, (30, 50, 120)), (.6, (10, 18, 50)), (1, (2, 4, 14))]), WHT,
    LC([(0.04, 0.085, 0.955, 0.165)], 130, cuts=[comp_cut(lambda a: (_lum(a) > .82) | ((a[..., 0] > .6) & (a[..., 1] < .3)) | ((a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .4)), minf=.005)]),
    photo=ph(0.6, 0.55, 0.8, 0.95), pb=(250, 200, 50), lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(250, 226, 60)),
    ft='d', fcol=(200, 210, 236), fin=RENTAL, seed=1997)

# Jackie Brown (1997): black, the poster's gold script Jackie / Brown cut off it into one line, Pam Grier aiming the pistol
std('jackie-brown-1997', ('grad', [(0, (40, 34, 30)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), (250, 200, 50),
    LC([(0.235, 0.775, 0.675, 0.842), (0.275, 0.837, 0.73, 0.905)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .4) & (a[..., 2] < .45), minf=.02, close=2)] * 2),
    photo=ph(0.6, 0.35, 0.8, 0.9), pb=(250, 200, 50), lg=WHT, lw=.5, order='LPTCF', credit=['A QUENTIN TARANTINO', 'FILM'], ccol=(250, 220, 140),
    ft='c', fcol=(220, 210, 190), fin=RENTAL, seed=1997)

# Kiss the Girls (1997): the poster's white mist, its black kiss the girls cut off it, Morgan Freeman and Ashley Judd
std('kiss-the-girls-1997', ('grad', [(0, (240, 240, 240)), (.5, (180, 190, 196)), (1, (40, 46, 50))]), (20, 20, 20),
    LC([(0.105, 0.805, 0.895, 0.875)], 100, cuts=[key_cut(lambda a: _lum(a) < .3)]),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(200, 80, 30), lg=(20, 20, 20), lw=.55, order='LPTF', dotst=('THRILLER', (200, 80, 30), WHT),
    ft='e', fcol=(220, 220, 220), fin=RENTAL, seed=1997)

# L.A. Confidential (1997): black, the poster's red slanted L.A. Confidential cut off it whole and levelled, Kim Basinger in the hood
std('l-a-confidential-1997', ('grad', [(0, (50, 40, 40)), (.6, (14, 10, 10)), (1, (2, 2, 2))]), (210, 30, 30),
    LC([(0.34, 0.6, 0.96, 0.86)], 140, cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .3), minf=.02, rot=-20)]),
    photo=ph(0.4, 0.2, 0.7, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='a', vbox=(210, 30, 30), fcol=(210, 206, 206), fin=RENTAL, seed=1997)

# Liar Liar (1997): the poster's white, LIAR LIAR typeset in heavy capitals, the first in the poster's dark red and the second in black (parked for Ian's logo, see data/logos-wanted.md: Jim Carrey's hair cuts through the second LIAR), Jim Carrey's grin
std('liar-liar-1997', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (20, 20, 20),
    TT([('LIAR', (150, 24, 30)), ('LIAR', (20, 20, 20))], 'intbk', 110, sp=.3),
    photo=ph(0.5, 0.45, 0.6, 0.85), pb=(160, 30, 30), lg=(20, 20, 20), lw=.55, order='LPTSF', stick=PRC(['$2.49', 'COMEDY']),
    ft='b', fcol=(30, 30, 30), fin=RENTAL, seed=1997)

# Life Is Beautiful (1997): the poster's stone, its dark serif LIFE IS BEAUTIFUL cut off it into one line, Guido with Giosuè on the bicycle (director from IMDb)
std('life-is-beautiful-1997', ('grad', [(0, (236, 230, 220)), (.6, (210, 200, 186)), (1, (110, 100, 86))]), (40, 26, 20),
    LC([(0.03, 0.565, 0.505, 0.695), (0.03, 0.69, 0.505, 0.775)], 100, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) < .28, minf=.02)] * 2),
    photo=ph(0.65, 0.5, 0.7, 1.2), pb=(40, 26, 20), lg=(40, 26, 20), lw=.55, order='LPTCF', credit=['LA VITA È BELLA'], ccol=(120, 40, 30),
    ft='c', fcol=(40, 26, 20), fin=RENTAL, seed=1997)

# Princess Mononoke (1997): Studio Ghibli, a slipcase; the forest's green, the poster's white spaced PRINCESS / MONONOKE lifted into one line, San with the blood on her face and the white wolf
std('princess-mononoke-1997', ('grad', [(0, (80, 110, 80)), (.6, (24, 40, 26)), (1, (4, 8, 4))]), WHT,
    L([(0.315, 0.112, 0.715, 0.127), (0.08, 0.13, 0.945, 0.215)], 96, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.4, 0.5, 0.86, 1.0), pb=(200, 40, 30), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'HAYAO MIYAZAKI'], ccol=WHT,
    ft='d', fcol=(210, 220, 210), fin=RENTAL, seed=1997)

# Schizopolis (1997): the poster's white, its black mixed-type Schizopolis cut off it, the grid of Soderbergh faces (no logo file: .406 Production, from IMDb's company credits)
std('schizopolis-1997', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (20, 20, 20),
    LC([(0.16, 0.715, 0.83, 0.82)], 110, cuts=[key_cut(lambda a: _lum(a) < .32)]),
    photo=ph(0.5, 0.33, 0.9, 0.75), pb=(200, 30, 30), studio=['.406 PRODUCTION'], scol=(20, 20, 20), order='lPTCF', credit=['A FILM BY', 'STEVEN SODERBERGH'], ccol=(20, 20, 20),
    ft='a', fcol=(20, 20, 20), fin=OLD, seed=1997)

# Taste of Cherry (1997): the poster's ochre, TASTE OF CHERRY typeset in spaced capitals in cream (parked for Ian's logo, see data/logos-wanted.md: the poster's pale title is barely lighter than the ochre and the lift came out in pieces), Mr. Badii's shadow (Kanoon logo; director from IMDb)
std('taste-of-cherry-1997', ('grad', [(0, (220, 160, 50)), (.6, (170, 110, 30)), (1, (60, 36, 8))]), (250, 236, 200),
    TT([('TASTE', (250, 236, 200)), ('OF', (250, 236, 200)), ('CHERRY', (250, 236, 200))], 'intxb', 84, sp=.4),
    photo=ph(0.4, 0.35, 0.7, 1.2), pb=(250, 236, 200), lg=(250, 236, 200), lw=.5, order='LPTCF', credit=['A FILM BY', 'ABBAS KIAROSTAMI'], ccol=(250, 236, 200),
    ft='b', fcol=(250, 236, 200), fin=OLD, seed=1997)

# The Game (1997): black, the poster's white serif THE / GAME lifted into one line, Michael Douglas's face coming apart in puzzle pieces
std('the-game-1997', ('grad', [(0, (40, 30, 26)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), WHT,
    L([(0.29, 0.742, 0.62, 0.81), (0.24, 0.805, 0.935, 0.91)], 110, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.3, 0.86, 0.75), pb=(200, 80, 40), lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(206, 200, 196), fin=RENTAL, seed=1997)

# The Ice Storm (1997): the night's black and ice blue, the poster's pale blue theicestorm lifted, the families in the frozen woods
std('the-ice-storm-1997', ('grad', [(0, (30, 50, 70)), (.6, (8, 14, 20)), (1, (2, 2, 4))]), (170, 210, 236),
    L((0.315, 0.14, 0.97, 0.2), 90, (170, 210, 236), mode='light', speck=0),
    photo=ph(0.55, 0.55, 0.6, 1.4), pb=(170, 210, 236), lg=WHT, lw=.5, order='LTPF',
    ft='e', fcol=(170, 196, 220), fin=RENTAL, seed=1997)

# The Rainmaker (1997): American Zoetrope, the poster's black, its gold serif THE RAINMAKER cut off it, Matt Damon and the courtroom
std('the-rainmaker-1997', ('grad', [(0, (60, 40, 26)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), (220, 180, 100),
    LC([(0.03, 0.06, 0.975, 0.145)], 100, cuts=[key_cut(lambda a: (a[..., 0] > .45) & (a[..., 2] < .4) & (a[..., 0] > a[..., 2] + .15))]),
    photo=ph(0.5, 0.4, 0.86, 0.8), pb=(220, 180, 100), lg=WHT, lw=.5, order='LPTF', ft='a', fcol=(220, 200, 170), fin=RENTAL, seed=1997)

# Wag the Dog (1997): black, the poster's red WAG, white THE and blue DOG cut off it in their own colours, Hoffman above and De Niro below
std('wag-the-dog-1997', ('grad', [(0, (30, 30, 40)), (.6, (10, 10, 14)), (1, (2, 2, 4))]), WHT,
    LC([(0.155, 0.492, 0.83, 0.565)], 100, cuts=[key_cut(lambda a: (_sat(a) > .4) | ((_lum(a) > .6) & (_sat(a) < .2)))]),
    photo=ph(0.5, 0.25, 0.86, 0.6), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['DUSTIN HOFFMAN', 'ROBERT DE NIRO'], ccol=WHT,
    ft='d', fcol=(200, 200, 210), fin=RENTAL, seed=1997)

# A Bug's Life (1998): Pixar clamshell; the leaf's green, the poster's yellow a bug's life cut off it, Flik's face in the diamond
disney('a-bug-s-life-1998', ('grad', [(0, (120, 190, 60)), (.5, (80, 160, 40)), (1, (30, 80, 20))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.28, 0.14, 0.73, 0.34)], 150, outline=((60, 40, 10), 2), cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .5) & (a[..., 2] < .45), minf=.01, close=2)]),
       face=ph(.32, .46, .22, 1.4), lcol=WHT)

# American History X (1998): the poster's red, the white strip with its black AMERICAN HISTORY and red X cut off it (it already runs down the poster) and turned to read along the spine, Edward Norton's face
std('american-history-x-1998', ('grad', [(0, (210, 50, 30)), (.5, (130, 24, 14)), (1, (20, 4, 2))]), WHT,
    LC([(0.742, 0.06, 0.995, 0.93)], 120, cuts=[comp_cut(lambda a: (_lum(a) < .22) | ((a[..., 0] > .6) & (a[..., 1] < .3)), keep=lambda cx, cy: cx > .06, minf=.01, rot=90)]),
    photo=ph(0.3, 0.4, 0.6, 1.2), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(240, 210, 200), fin=RENTAL, seed=1998)

# Antz (1998): the poster's sky, its black ANTZ with the green edge cut off it, Z and the ants on the picnic below
std('antz-1998', ('grad', [(0, (90, 180, 240)), (.5, (60, 150, 220)), (1, (20, 70, 30))]), (20, 30, 20),
    LC([(0.07, 0.09, 0.97, 0.505)], 140, outline=((120, 200, 60), 2.4), cuts=[comp_cut(lambda a: _lum(a) < .2, minf=.15, fillh=True)]),
    photo=ph(0.5, 0.73, 0.5, 1.4), pb=(20, 30, 20), lg=WHT, lw=.5, order='LPTSF', stick=BAR('98 1002', top='ANIMATION', fill=(236, 240, 226)),
    ft='a', vbox=(20, 30, 20), fcol=(220, 236, 220), fin=RENTAL, seed=1998)

# Cats (1998): black, the poster's white hand-lettered CATS cut off it, the yellow cat's eyes, and the company in costume under the title (PolyGram logo; director from IMDb)
std('cats-1998', ('grad', [(0, (30, 30, 40)), (.6, (8, 8, 12)), (1, (2, 2, 2))]), WHT,
    LC([(0.24, 0.245, 0.76, 0.44)], 130, cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.05)]),
    photo=ph(0.5, 0.7, 0.86, 0.75), pb=(250, 220, 40), lg=WHT, lw=.5, order='LTPF', dotst=('MUSICAL', (250, 220, 40), (20, 20, 20)),
    ft='e', fcol=(200, 200, 210), fin=RENTAL, seed=1998)

# Central Station (1998): the poster's dusty ochre, its black stencilled CENTRAL / STATION cut off it into one line, Dora and Josué at the fence
std('central-station-1998', ('grad', [(0, (230, 170, 90)), (.5, (200, 140, 70)), (1, (90, 60, 30))]), (30, 20, 14),
    LC([(0.065, 0.14, 0.49, 0.2), (0.065, 0.202, 0.465, 0.255)], 90, valign='base', margin=0, gapf=.25, cuts=[key_cut(lambda a: _lum(a) < .3)] * 2),
    photo=ph(0.5, 0.6, 0.9, 0.85), pb=(30, 20, 14), lg=(30, 20, 14), lw=.55, order='LPTCF', credit=['UM FILME DE', 'WALTER SALLES'], ccol=(30, 20, 14),
    ft='c', fcol=(30, 20, 14), fin=RENTAL, seed=1998)

# Fear and Loathing in Las Vegas (1998): the poster's yellow desert, its red hand-lettered Fear and Loathing in LAS VEGAS cut off it, Johnny Depp's Raoul Duke in the shades and hat
std('fear-and-loathing-in-las-vegas-1998', ('grad', [(0, (250, 220, 90)), (.5, (240, 170, 50)), (1, (120, 60, 20))]), (200, 30, 30),
    LC([(0.36, 0.585, 0.91, 0.84)], 140, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3), minf=.01)]),
    photo=ph(0.5, 0.2, 0.9, 0.6), pb=(200, 30, 30), lg=(60, 30, 14), lw=.55, order='LPTCF', credit=['JOHNNY DEPP', 'BENICIO DEL TORO'], ccol=(60, 30, 14),
    ft='d', fcol=(60, 30, 14), fin=RENTAL, seed=1998)

# Half Baked (1998): the field's green, the poster's blue and yellow Half Baked cut off it in its own colours, Thurgood and friends by the KEEP OFF THE GRASS sign (director from IMDb)
std('half-baked-1998', ('grad', [(0, (120, 190, 240)), (.5, (80, 170, 60)), (1, (20, 60, 14))]), (30, 70, 200),
    LC([(0.07, 0.84, 0.93, 0.94)], 120, cuts=[comp_cut(lambda a: ((a[..., 2] > .45) & (a[..., 0] < .45)) | ((a[..., 0] > .7) & (a[..., 1] > .6) & (a[..., 2] < .45)), minf=.02, close=2)]),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$1.99', 'COMEDY']),
    ft='b', fcol=(230, 240, 220), fin=RENTAL, seed=1998)

# Happiness (1998): the poster's orange into yellow, its white HAPPINESS lifted, the drawn cast in a crowd (Good Machine logo; director from IMDb)
std('happiness-1998', ('grad', [(0, (220, 80, 50)), (.5, (240, 160, 50)), (1, (240, 200, 60))]), WHT,
    L((0.105, 0.09, 0.895, 0.19), 100, WHT, mode='light'),
    photo=ph(0.5, 0.86, 0.9, 0.35), pb=(30, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'TODD SOLONDZ'], ccol=(60, 30, 14),
    ft='a', vbox=(30, 30, 30), fcol=(60, 30, 14), fin=OLD, seed=1998)

# He Got Game (1998): black, the poster's white distressed HE GOT GAME lifted, Denzel Washington's eyes over his steepled hands
std('he-got-game-1998', ('grad', [(0, (60, 40, 26)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), WHT,
    L((0.085, 0.782, 0.902, 0.842), 90, WHT, mode='light'),
    photo=ph(0.5, 0.42, 0.86, 0.75), pb=(220, 120, 40), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(220, 200, 186), fin=RENTAL, seed=1998)

# Lock, Stock and Two Smoking Barrels (1998): black, the poster's white LOCK STOCK and yellow & Two Smoking Barrels cut off it into one line, the four silhouettes on the red bars
std('lock-stock-and-two-smoking-barrels-1998', ('grad', [(0, (40, 30, 30)), (.6, (12, 8, 8)), (1, (2, 2, 2))]), WHT,
    LC([(0.135, 0.775, 0.865, 0.87), (0.13, 0.872, 0.85, 0.916)], 110, valign='base', margin=0, gapf=.2,
       cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.02), comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45), minf=.02)]),
    photo=ph(0.5, 0.2, 0.62, 0.62), pb=(220, 40, 30), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'GUY RITCHIE'], ccol=WHT,
    ft='c', vbox=(220, 40, 30), fcol=(210, 200, 196), fin=RENTAL, seed=1998)

# Mulan (1998): Disney clamshell; the poster's red, its white brushed MULAN cut off its plate, Mulan's face in the diamond
disney('mulan-1998', ('grad', [(0, (200, 30, 30)), (.5, (150, 20, 20)), (1, (60, 8, 8))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.335, 0.758, 0.66, 0.83)], 130, outline=((60, 10, 10), 1.8), cuts=[comp_cut(lambda a: _lum(a) > .72, minf=.02)]),
       face=ph(.67, .37, .14, 1.4), lcol=WHT)

# Out of Sight (1998): the poster's red and yellow, its red outlined "OUT OF SIGHT" cut off it, Jennifer Lopez with the shotgun
std('out-of-sight-1998', ('grad', [(0, (230, 40, 30)), (.5, (240, 180, 40)), (1, (20, 6, 4))]), (220, 30, 30),
    LC([(0.0, 0.835, 0.99, 0.918)], 120, outline=(WHT, 1.6), cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .2), minf=.02, fillh=True)]),
    photo=ph(0.6, 0.45, 0.8, 1.0), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTCF', credit=['A STEVEN SODERBERGH', 'FILM'], ccol=WHT,
    ft='b', vbox=(220, 30, 30), fcol=(240, 220, 200), fin=RENTAL, seed=1998)

# Ronin (1998): the Paris grey, the poster's yellow RONIN cut off it, De Niro aiming down the street
std('ronin-1998', ('grad', [(0, (150, 150, 146)), (.6, (50, 50, 48)), (1, (6, 6, 6))]), (250, 210, 40),
    LC([(0.09, 0.575, 0.925, 0.75)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .5) & (a[..., 2] < .4), minf=.1)]),
    photo=ph(0.6, 0.25, 0.8, 0.6), pb=(250, 210, 40), lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(220, 220, 214), fin=RENTAL, seed=1998)

# Rounders (1998): black, the poster's white serif ROUNDERS with the spade in the O lifted, the players round the table
std('rounders-1998', ('grad', [(0, (60, 40, 30)), (.6, (16, 10, 8)), (1, (2, 2, 2))]), WHT,
    L((0.068, 0.848, 0.94, 0.934), 90, WHT, mode='light'),
    photo=ph(0.5, 0.33, 0.86, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['MATT DAMON', 'EDWARD NORTON'], ccol=WHT,
    ft='e', fcol=(210, 200, 196), fin=RENTAL, seed=1998)

# Rush Hour (1998): the night street's blue, the poster's red slanted RUSH / HOUR cut off it whole, Jackie Chan and Chris Tucker
std('rush-hour-1998', ('grad', [(0, (30, 70, 140)), (.6, (10, 24, 50)), (1, (2, 4, 12))]), (220, 30, 30),
    LC([(0.17, 0.68, 0.835, 0.905)], 140, outline=(WHT, 1.8), cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3), minf=.02)]),
    photo=ph(0.5, 0.32, 0.9, 0.7), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('98 0918', top='ACTION', fill=(230, 232, 240)),
    ft='a', vbox=(220, 30, 30), fcol=(200, 210, 236), fin=RENTAL, seed=1998)

# Rushmore (1998): Touchstone, a slipcase; the poster's striped pale wallpaper, its red-and-yellow tiled RUSHMORE cut off it whole, Max in the go-kart under the title
std('rushmore-1998', ('grad', [(0, (236, 236, 220)), (.6, (220, 220, 200)), (1, (120, 120, 100))]), (190, 30, 30),
    LC([(0.05, 0.125, 0.95, 0.205)], 110, margin=0, cuts=[key_cut(lambda a: _lum(a) >= 0)]),
    photo=ph(0.5, 0.58, 0.6, 0.75), pb=(190, 30, 30), lg=(60, 30, 20), lw=.55, order='LTPCF', credit=['A FILM BY', 'WES ANDERSON'], ccol=(60, 30, 20),
    ft='b', fcol=(60, 30, 20), fin=RENTAL, seed=1998)

# Saving Private Ryan (1998): a 2-tape box would not quite be needed at 169 minutes, so one tape; the battlefield's grey, the poster's white saving private ryan lifted, the soldiers' faces
std('saving-private-ryan-1998', ('grad', [(0, (120, 130, 130)), (.6, (34, 38, 38)), (1, (4, 4, 4))]), WHT,
    L((0.085, 0.78, 0.92, 0.838), 84, WHT, mode='light'),
    photo=ph(0.5, 0.33, 0.9, 0.7), pb=WHT, lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(206, 210, 210), fin=RENTAL, seed=1998)

# The Big Lebowski (1998): black, the poster's white serif THE BIG LEBOWSKI lifted, the Dude's bowling-alley sunglasses
std('the-big-lebowski-1998', ('grad', [(0, (40, 30, 40)), (.6, (12, 8, 12)), (1, (2, 2, 2))]), WHT,
    L([(0.43, 0.105, 0.57, 0.13), (0.05, 0.135, 0.95, 0.176)], 90, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.48, 0.86, 0.75), pb=(220, 40, 40), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=WHT, ft='d', fcol=(210, 200, 210), fin=RENTAL, seed=1998)

# The Cruise (1998): the poster's grey city, its yellow-and-black THE CRUISE cut off it, Speed Levitch on the bus (no logo file: Charter Films, from IMDb's company credits)
std('the-cruise-1998', ('grad', [(0, (200, 200, 200)), (.6, (120, 120, 120)), (1, (20, 20, 20))]), (20, 20, 20),
    LC([(0.25, 0.168, 0.935, 0.228)], 100, cuts=[comp_cut(lambda a: (_lum(a) < .25) | ((a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45)), minf=.02)]),
    photo=ph(0.6, 0.6, 0.86, 0.85), pb=(250, 220, 40), studio=['CHARTER FILMS'], scol=(20, 20, 20), order='lPTCF', credit=['A DOCUMENTARY BY', 'BENNETT MILLER'], ccol=WHT,
    ft='e', fcol=(220, 220, 220), fin=OLD, seed=1998)

# The Parent Trap (1998): Disney, a live-action film, so a slipcase; the poster's white, its black serif the PARENT TRAP cut off it into one line, the twins
std('the-parent-trap-1998', ('grad', [(0, (246, 244, 240)), (.6, (228, 224, 218)), (1, (120, 114, 104))]), (20, 20, 20),
    LC([(0.07, 0.36, 0.3, 0.42), (0.07, 0.4, 0.94, 0.48), (0.38, 0.715, 0.95, 0.86)], 100, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) < .18, minf=.02)] * 3),
    photo=ph(0.5, 0.18, 0.9, 0.5), pb=(200, 40, 40), lg=(20, 20, 20), lw=.55, order='LPTSF', stick=PRC(['$2.49', 'FAMILY']),
    ft='a', vbox=(20, 20, 20), fcol=(20, 20, 20), fin=RENTAL, seed=1998)

# The Rugrats Movie (1998): the poster's purple, its white starburst with THE RUGRATS MOVIE cut off it whole, the babies with Reptar (Klasky-Csupo logo; directors from IMDb)
std('the-rugrats-movie-1998', ('grad', [(0, (110, 50, 170)), (.5, (200, 90, 100)), (1, (60, 120, 40))]), WHT,
    LC([(0.35, 0.05, 0.86, 0.23)], 140, cuts=[plate_cut(lambda a: _lum(a) > .85)]),
    photo=ph(0.5, 0.6, 0.6, 1.4), pb=(250, 200, 40), lg=WHT, lw=.5, order='LTPF',
    ft='c', fcol=(240, 220, 236), fin=RENTAL, seed=1998)

# The Truman Show (1998): the mosaic's blue, the poster's white The Truman Show lifted, Truman's face made of the show's stills
std('the-truman-show-1998', ('grad', [(0, (60, 120, 200)), (.6, (20, 50, 100)), (1, (4, 10, 24))]), WHT,
    LC([(0.03, 0.03, 0.97, 0.29)], 140, cuts=[comp_cut(lambda a: _lum(a) > .9, minf=.03)]),
    photo=ph(0.5, 0.65, 0.6, 1.5), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A PETER WEIR', 'FILM'], ccol=WHT,
    ft='b', fcol=(200, 216, 240), fin=RENTAL, seed=1998)

# There's Something About Mary (1998): the poster's white, its purple there's something about and pink mary cut off it into one line, Cameron Diaz with the dog
std('there-s-something-about-mary-1998', ('grad', [(0, (246, 246, 246)), (.6, (234, 226, 236)), (1, (130, 110, 130))]), (230, 40, 150),
    LC([(0.07, 0.215, 0.47, 0.33), (0.02, 0.33, 0.545, 0.45)], 110, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: _sat(a) > .35)] * 2),
    photo=ph(0.72, 0.62, 0.5, 1.3), pb=(230, 40, 150), lg=(60, 20, 60), lw=.55, order='LPTF',
    ft='d', fcol=(60, 20, 60), fin=RENTAL, seed=1998)

# 10 Things I Hate About You (1999): Touchstone, a slipcase; the poster's green panel with its pink 10 things and white I hate about you cut off it whole, the cast in a row
std('10-things-i-hate-about-you-1999', ('grad', [(0, (120, 190, 60)), (.5, (80, 150, 40)), (1, (20, 50, 10))]), WHT,
    LC([(0.155, 0.02, 0.845, 0.43)], 150, cuts=[comp_cut(lambda a: (_lum(a) > .9) | ((a[..., 0] > .6) & (a[..., 1] < .35) & (a[..., 2] > .3)), minf=.01)]),
    photo=ph(0.5, 0.7, 0.9, 0.6), pb=(220, 40, 120), lg=WHT, lw=.5, order='LPTF', ft='e', fcol=(230, 246, 220), fin=RENTAL, seed=1999)

# American Beauty (1999): DreamWorks, the poster's skin and rose, its black spaced AMERICAN BEAUTY cut off it, the rose against the belly
std('american-beauty-1999', ('grad', [(0, (240, 200, 160)), (.6, (220, 150, 100)), (1, (110, 60, 30))]), (20, 14, 10),
    LC([(0.085, 0.055, 0.91, 0.11)], 90, cuts=[key_cut(lambda a: _lum(a) < .28)]),
    photo=ph(0.65, 0.6, 0.7, 1.1), pb=(190, 20, 30), lg=(40, 20, 10), lw=.55, order='LPTF',
    ft='a', vbox=(190, 20, 30), fcol=(40, 20, 10), fin=RENTAL, seed=1999)

# American Pie (1999): the poster's white with the red border, its red stamped AMERICAN / PIE cut off it whole, the cast round the pie
std('american-pie-1999', ('grad', [(0, (246, 244, 244)), (.6, (230, 226, 226)), (1, (130, 120, 120))]), (210, 30, 30),
    LC([(0.085, 0.035, 0.915, 0.285)], 140, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .35), minf=.02, close=2)]),
    photo=ph(0.5, 0.62, 0.6, 1.3), pb=(210, 30, 30), lg=(40, 20, 20), lw=.55, order='LPTSF', stick=BAR('99 0709', top='COMEDY', fill=(240, 236, 226)),
    ft='b', fcol=(40, 20, 20), fin=RENTAL, seed=1999)

# Austin Powers: The Spy Who Shagged Me (1999): the poster's sky blue, its orange outlined AUSTIN POWERS / THE SPY WHO SHAGGED ME cut off it whole, Austin and Felicity
std('austin-powers-the-spy-who-shagged-me-1999', ('grad', [(0, (40, 180, 230)), (.5, (220, 40, 50)), (1, (120, 200, 60))]), (250, 160, 30),
    LC([(0.04, 0.115, 0.52, 0.385)], 150, cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .4) & (a[..., 2] < .35)) | (_lum(a) < .15), minf=.01, close=2)]),
    photo=ph(0.65, 0.45, 0.6, 1.2), pb=(250, 160, 30), lg=WHT, lw=.5, order='LPTSF', dotst=('COMEDY', (250, 160, 30), (20, 20, 20)),
    ft='e', fcol=(240, 240, 250), fin=RENTAL, seed=1999)

# Being John Malkovich (1999): black, the poster's white spaced BEING JOHN MALKOVICH lifted, the crowd of Malkovich heads
std('being-john-malkovich-1999', ('grad', [(0, (60, 50, 40)), (.6, (16, 12, 10)), (1, (2, 2, 2))]), WHT,
    L((0.02, 0.89, 0.98, 0.935), 70, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.35, 0.9, 0.75), pb=(200, 40, 40), lg=WHT, lw=.5, order='LPTCF', credit=['A SPIKE JONZE', 'FILM'], ccol=WHT,
    ft='c', fcol=(210, 200, 190), fin=RENTAL, seed=1999)

# Big Daddy (1999): the brownstone's pale steps, the poster's red BIG DADDY keyed off it, Sonny and Julian at the door
std('big-daddy-1999', ('grad', [(0, (236, 230, 220)), (.6, (210, 200, 186)), (1, (110, 100, 86))]), (210, 40, 40),
    L((0.11, 0.83, 0.885, 0.928), 96, (210, 40, 40), mode='key', key=(210, 50, 40), t=(70, 160)),
    photo=ph(0.55, 0.35, 0.6, 1.4), pb=(210, 40, 40), lg=(40, 30, 20), lw=.55, order='LTPF',
    ft='a', vbox=(210, 40, 40), fcol=(40, 30, 20), fin=RENTAL, seed=1999)

# Dogma (1999): the poster's black, its red DOGMA with the cross in the O cut off it, the cast in the holy light
std('dogma-1999', ('grad', [(0, (200, 80, 30)), (.4, (60, 20, 10)), (1, (2, 2, 2))]), (220, 30, 30),
    LC([(0.105, 0.655, 0.89, 0.765)], 120, outline=(WHT, 1.4), cuts=[comp_cut(lambda a: (a[..., 0] > .5) & (a[..., 1] < .25), minf=.03, fillh=True)]),
    photo=ph(0.5, 0.25, 0.9, 0.6), pb=(250, 200, 120), lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(220, 200, 190), fin=RENTAL, seed=1999)

# Fight Club (1999): the poster's sickly green, FIGHT CLUB typeset in heavy capitals in the soap's pink (parked for Ian's logo, see data/logos-wanted.md: the title is pressed into a tilted pink soap bar held in a hand, and the bar wouldn't cut cleanly), Brad Pitt and Edward Norton
std('fight-club-1999', ('grad', [(0, (120, 160, 80)), (.5, (60, 90, 40)), (1, (10, 20, 8))]), (240, 110, 180),
    T('FIGHT CLUB', 'intbk', 110, (240, 120, 190), outline=((90, 20, 60), 2)),
    photo=ph(0.6, 0.62, 0.8, 0.85), pb=(240, 110, 180), lg=WHT, lw=.5, order='LPTF', ft='b', fcol=(220, 230, 210), fin=RENTAL, seed=1999)

# Ghost Dog: The Way of the Samurai (1999): the poster's blue-grey, its white chalked GHOST DOG and THE WAY OF THE SAMURAI cut off it into one line, Forest Whitaker in the hood (JVC logo)
std('ghost-dog-the-way-of-the-samurai-1999', ('grad', [(0, (60, 80, 110)), (.6, (20, 28, 40)), (1, (2, 4, 8))]), WHT,
    LC([(0.025, 0.215, 0.48, 0.43), (0.06, 0.445, 0.43, 0.67)], 110, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: _lum(a) > .68, minf=.01, opn=1)] * 2),
    photo=ph(0.7, 0.4, 0.6, 1.2), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'JIM JARMUSCH'], ccol=WHT,
    ft='e', fcol=(200, 210, 220), fin=OLD, seed=1999)

# Magnolia (1999): a 2-tape box (189 minutes); black, the poster's white serif magnolia lifted, the flower full of the cast's faces
std('magnolia-1999', ('grad', [(0, (40, 30, 20)), (.6, (12, 10, 6)), (1, (2, 2, 2))]), WHT,
    L((0.17, 0.735, 0.845, 0.795), 100, WHT, mode='light'),
    photo=ph(0.5, 0.38, 0.9, 0.75), pb=(240, 210, 160), lg=WHT, lw=.5, order='LPTCSF', credit=['A PAUL THOMAS', 'ANDERSON FILM'], ccol=WHT, stick=TWOST((240, 210, 160), (20, 16, 10)),
    ft='a', fcol=(220, 210, 200), fin=RENTAL, seed=1999, **TWO)

# Man on the Moon (1999): the curtain's red, the poster's white MAN ON THE MOON lifted, Jim Carrey as Andy Kaufman in the spotlight (Mutual Film logo)
std('man-on-the-moon-1999', ('grad', [(0, (180, 30, 30)), (.6, (90, 12, 12)), (1, (14, 2, 2))]), WHT,
    L((0.1, 0.145, 0.805, 0.19), 80, WHT, mode='light'),
    photo=ph(0.3, 0.55, 0.6, 1.3), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['JIM CARREY'], ccol=WHT,
    ft='c', fcol=(240, 210, 200), fin=RENTAL, seed=1999)

# Office Space (1999): the poster's white, its red OfficeSpace cut off it, the man covered head to foot in yellow sticky notes
std('office-space-1999', ('grad', [(0, (246, 246, 240)), (.6, (236, 232, 210)), (1, (140, 130, 90))]), (200, 30, 30),
    LC([(0.055, 0.058, 0.945, 0.178)], 120, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3), minf=.02)]),
    photo=ph(0.5, 0.55, 0.6, 1.4), pb=(250, 220, 60), lg=(40, 30, 20), lw=.55, order='LPTSF', stick=PRC(['$1.99', 'COMEDY']),
    ft='d', fcol=(40, 30, 20), fin=RENTAL, seed=1999)

# She's All That (1999): the poster's purple and orange, its black-and-orange she's all that plate cut off it as it is, Zack and Laney
std('she-s-all-that-1999', ('grad', [(0, (120, 60, 160)), (.5, (240, 140, 40)), (1, (60, 20, 50))]), (250, 160, 40),
    LC([(0.105, 0.775, 0.875, 0.858)], 130, margin=0, cuts=[key_cut(lambda a: _lum(a) >= 0)]),
    photo=ph(0.5, 0.35, 0.86, 0.75), pb=(250, 160, 40), lg=WHT, lw=.5, order='LPTF',
    ft='b', fcol=(246, 230, 220), fin=RENTAL, seed=1999)

# Sleepy Hollow (1999): the poster's black, its red script Sleepy Hollow cut off it, Johnny Depp and Christina Ricci in the fog
std('sleepy-hollow-1999', ('grad', [(0, (40, 50, 60)), (.6, (10, 12, 16)), (1, (2, 2, 2))]), (200, 30, 30),
    LC([(0.09, 0.085, 0.93, 0.195)], 120, cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .25), minf=.01)]),
    photo=ph(0.5, 0.5, 0.9, 0.6), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTF', ft='e', vbox=(200, 30, 30), fcol=(200, 206, 210), fin=RENTAL, seed=1999)

# Star Wars: Episode I – The Phantom Menace (1999): Lucasfilm, a slipcase; the poster's gold and black, its silver STAR WARS / EPISODE I / THE PHANTOM MENACE cut off it into one line, Anakin with Maul's eyes above
std('star-wars-episode-i-the-phantom-menace-1999', ('grad', [(0, (120, 70, 20)), (.5, (40, 20, 8)), (1, (4, 2, 2))]), (226, 220, 210),
    [LC([(0.1, 0.8, 0.43, 0.83), (0.1, 0.838, 0.89, 0.883)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) > .65, minf=.01)] * 2),
     LC([(0.1, 0.932, 0.89, 0.96)], 110, margin=0, cuts=[comp_cut(lambda a: _lum(a) > .65, minf=.01)])], tgap=8,
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(250, 190, 80), lg=WHT, lw=.5, order='LPTSF', dotst=('SCI-FI', (250, 190, 80), (20, 10, 4)),
    ft='c', fcol=(220, 200, 170), fin=RENTAL, seed=1999)

# Stuart Little (1999): the poster's yellow, its blue STUART LITTLE with the yellow face cut off it, Stuart on the sneaker
std('stuart-little-1999', ('grad', [(0, (252, 220, 40)), (.5, (244, 200, 20)), (1, (150, 110, 10))]), (30, 90, 200),
    LC([(0.06, 0.648, 0.94, 0.732)], 120, cuts=[comp_cut(lambda a: ((a[..., 2] > .55) & (a[..., 0] < .6)) | (_lum(a) < .2), minf=.02, fillh=True)]),
    photo=ph(0.4, 0.25, 0.6, 1.0), pb=(200, 30, 30), lg=(30, 40, 80), lw=.55, order='LPTSF', stick=RWD(fill=(250, 200, 220), ink=(110, 20, 60)),
    ft='a', vbox=(30, 90, 200), fcol=(30, 40, 80), fin=RENTAL, seed=1999)

# Tarzan (1999): Disney clamshell; the jungle's greens, the poster's carved bronze TARZAN cut off it, Tarzan's face in the diamond
disney('tarzan-1999', ('grad', [(0, (30, 110, 80)), (.5, (60, 160, 110)), (1, (20, 70, 40))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.15, 0.08, 0.85, 0.2)], 140, outline=((40, 20, 10), 1.6), cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 2] < .35) & (a[..., 0] > a[..., 1] + .08), minf=.02, close=2, fillh=True)]),
       face=ph(.61, .555, .14, 1.4), lcol=WHT)

# The Bone Collector (1999): the dark, the poster's pale the BONE COLLECTOR cut off it into one line, Denzel Washington and Angelina Jolie
std('the-bone-collector-1999', ('grad', [(0, (60, 40, 26)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), (236, 226, 206),
    LC([(0.115, 0.8, 0.52, 0.856), (0.115, 0.862, 0.91, 0.948)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) > .68, minf=.02)] * 2),
    photo=ph(0.5, 0.3, 0.86, 0.75), pb=(236, 226, 206), lg=WHT, lw=.5, order='LPTF', ft='d', fcol=(210, 200, 186), fin=RENTAL, seed=1999)

# The Boondock Saints (1999): the poster's red, its white THE BOONDOCK SAINTS cut off it into one line, the MacManus brothers with their pistols
std('the-boondock-saints-1999', ('grad', [(0, (220, 50, 30)), (.6, (120, 20, 10)), (1, (14, 2, 2))]), WHT,
    LC([(0.44, 0.075, 0.57, 0.103), (0.05, 0.103, 0.94, 0.19)], 96, valign='base', margin=0, gapf=.2, cuts=[key_cut(lambda a: (_lum(a) > .82) & (_sat(a) < .2))] * 2),
    photo=ph(0.5, 0.45, 0.9, 0.7), pb=WHT, lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.49', 'ACTION']),
    ft='b', fcol=(240, 210, 200), fin=RENTAL, seed=1999)

# The Green Mile (1999): a 2-tape box (189 minutes); the cell block's green dark, the poster's white serif THE GREEN MILE lifted, John Coffey's light in his hands
std('the-green-mile-1999', ('grad', [(0, (50, 70, 50)), (.6, (14, 20, 14)), (1, (2, 4, 2))]), WHT,
    L([(0.43, 0.075, 0.57, 0.1), (0.15, 0.1, 0.86, 0.19)], 96, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.48, 0.86, 0.9), pb=(240, 230, 160), lg=WHT, lw=.5, order='LPTCSF', credit=['TOM HANKS'], ccol=WHT, stick=TWOST((240, 230, 160), (20, 30, 20)),
    ft='e', fcol=(200, 220, 200), fin=RENTAL, seed=1999, **TWO)

# The Iron Giant (1999): Warner Bros. Animation, a slipcase; the evening sky, the poster's white stencilled THE IRON GIANT cut off it whole, the Giant's head and Hogarth's hand
std('the-iron-giant-1999', ('grad', [(0, (60, 90, 120)), (.5, (40, 60, 80)), (1, (14, 20, 26))]), WHT,
    LC([(0.0, 0.055, 0.6, 0.25)], 140, cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.01)]),
    photo=ph(0.5, 0.48, 0.9, 0.8), pb=(240, 200, 120), lg=WHT, lw=.5, order='LTPF', ft='a', vbox=(200, 40, 30), fcol=(210, 220, 230), fin=RENTAL, seed=1999)

# The Matrix (1999): the code's green black, the poster's silver THE MATRIX lifted, Neo, Morpheus and Trinity in the rain of code
std('the-matrix-1999', ('grad', [(0, (20, 60, 30)), (.6, (6, 20, 10)), (1, (0, 4, 2))]), (200, 230, 210),
    L([(0.44, 0.835, 0.56, 0.848), (0.14, 0.846, 0.865, 0.912)], 96, (210, 236, 214), mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(80, 220, 100), lg=WHT, lw=.5, order='LPTSF', stick=BAR('99 0331', top='SCI-FI', fill=(220, 236, 220)),
    ft='d', fcol=(170, 220, 180), fin=RENTAL, seed=1999)

# The Sixth Sense (1999): black, the poster's white hand-lettered THE SIXTH SENSE lifted, Cole's face and Bruce Willis below
std('the-sixth-sense-1999', ('grad', [(0, (40, 30, 26)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), WHT,
    L((0.13, 0.045, 0.855, 0.125), 90, WHT, mode='light', speck=0),
    photo=ph(0.4, 0.38, 0.7, 0.75), pb=(250, 180, 80), lg=WHT, lw=.5, order='LPTF', ft='c', fcol=(210, 200, 196), fin=RENTAL, seed=1999)

# The Talented Mr. Ripley (1999): the Italian dusk gold, the poster's white serif THE / TALENTED / MR. RIPLEY lifted into one line, Matt Damon, Jude Law and Gwyneth Paltrow
std('the-talented-mr-ripley-1999', ('grad', [(0, (200, 140, 60)), (.5, (100, 60, 24)), (1, (14, 8, 4))]), WHT,
    L([(0.41, 0.775, 0.875, 0.845), (0.44, 0.845, 0.905, 0.905)], 96, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.35, 0.9, 0.75), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['AN ANTHONY MINGHELLA', 'FILM'], ccol=WHT,
    ft='b', fcol=(240, 220, 200), fin=RENTAL, seed=1999)

# The World Is Not Enough (1999): the explosion's orange into midnight, the poster's white italic The World Is Not Enough lifted, Bond in the suit
std('the-world-is-not-enough-1999', ('grad', [(0, (30, 50, 80)), (.5, (12, 18, 30)), (1, (200, 90, 30))]), WHT,
    L((0.015, 0.423, 0.945, 0.47), 90, WHT, mode='light'),
    photo=ph(0.5, 0.25, 0.8, 0.6), pb=(220, 190, 90), lg=WHT, lw=.5, order='LPTF', ft='e', vbox=(200, 170, 70), vink=(10, 10, 20), fcol=(200, 206, 226), fin=RENTAL, seed=1999)

# Three Kings (1999): the desert's white, THREE KINGS typeset in wide spaced capitals in the poster's blue (parked for Ian's logo, see data/logos-wanted.md: the letters fade from blue into the white sky, so both cuts lost their middles), the three soldiers walking with their gold
std('three-kings-1999', ('grad', [(0, (230, 236, 246)), (.6, (200, 210, 226)), (1, (90, 100, 120))]), (40, 90, 160),
    TT([('THREE', (40, 90, 170)), ('KINGS', (40, 90, 170))], 'advb', 96, sp=.4),
    photo=ph(0.5, 0.52, 0.86, 0.8), pb=(40, 90, 160), lg=(30, 50, 90), lw=.55, order='LPTF', ft='a', fcol=(30, 50, 90), fin=RENTAL, seed=1999)

# Toy Story 2 (1999): Pixar clamshell, built like the other Toy Storys; the poster's star-sky blue, its yellow TOY, red STORY plate and the 2 cut off it, Jessie's face in the diamond
disney('toy-story-2-1999', ('strip', dict(x0=.0, blur=14, wash=((36, 90, 200), .6))), fin=dict(CLAM, vivid=.3),
       title=LC([(0.27, 0.065, 0.69, 0.17), (0.25, 0.16, 0.73, 0.235), (0.37, 0.215, 0.6, 0.335)], 170, gapf=.05, cuts=[ts_letters, ts_plate(.3, .75), ts_letters]),
       face=ph(.295, .535, .1, 1.4))


# ---------------------------------------------------------------- the 2000s
# Almost Famous (2000): the poster's warm orange, its white ALMOST FAMOUS cut out of the sunglasses' lenses, Kate Hudson's smile under the title
std('almost-famous-2000', ('grad', [(0, (230, 120, 50)), (.5, (180, 70, 30)), (1, (60, 20, 8))]), WHT,
    LC([(0.07, 0.38, 0.93, 0.455)], 120, cuts=[comp_cut(lambda a: _lum(a) > .86, minf=.03, keep=lambda cx, cy: not (.4 < cx < .6))]),
    photo=ph(0.5, 0.75, 0.86, 0.5), pb=WHT, lg=WHT, lw=.5, order='LTPCF', credit=['A CAMERON CROWE', 'FILM'], ccol=WHT,
    ft='b', fcol=(250, 220, 200), fin=MINT, seed=2000)

# American Psycho (2000): black, the poster's white serif AMERICAN / PSYCHO lifted into one line, Bale with the knife
std('american-psycho-2000', ('grad', [(0, (60, 30, 40)), (.6, (16, 8, 10)), (1, (2, 2, 2))]), WHT,
    L([(0.3, 0.85, 0.68, 0.888), (0.205, 0.888, 0.795, 0.982)], 100, WHT, mode='light', valign='base'),
    photo=ph(0.6, 0.35, 0.8, 1.1), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['CHRISTIAN BALE'], ccol=WHT,
    ft='a', vbox=(200, 30, 30), fcol=(210, 200, 200), fin=MINT, seed=2000)

# Amores Perros (2000): the poster's white, AMORES PERROS typeset in heavy capitals in its red (parked for Ian's logo, see data/logos-wanted.md: the poster chops the words into blocks that run off its edges and behind the photo, so the cut came out in pieces), the screaming face (no logo file: Altavista Films, from IMDb's company credits)
std('amores-perros-2000', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (220, 20, 30),
    TT([('AMORES', (220, 20, 30)), ('PERROS', (220, 20, 30))], 'intbk', 110, sp=.3),
    photo=ph(0.6, 0.45, 0.5, 0.8), pb=(220, 20, 30), studio=['ALTAVISTA FILMS'], scol=(20, 20, 20), order='lPTCF', credit=['UNA PELÍCULA DE', 'ALEJANDRO G. IÑÁRRITU'], ccol=(20, 20, 20),
    ft='c', fcol=(20, 20, 20), fin=MINT, seed=2000)

# Boiler Room (2000): the trading floor's black, the poster's white glowing BOILER ROOM lifted, Ribisi, Diesel and Long
std('boiler-room-2000', ('grad', [(0, (30, 40, 60)), (.6, (8, 12, 20)), (1, (2, 2, 4))]), WHT,
    L((0.06, 0.148, 0.94, 0.234), 90, WHT, mode='light'),
    photo=ph(0.5, 0.45, 0.86, 0.75), pb=(120, 200, 240), lg=WHT, lw=.5, order='LPTSF', stick=BAR('00 0218', top='DRAMA', fill=(226, 230, 236)),
    ft='d', fcol=(190, 200, 220), fin=MINT, seed=2000)

# Chicken Run (2000): the poster's white, its red italic CHICKEN RUN keyed off it, Ginger and the hens on the run (Aardman logo)
std('chicken-run-2000', ('grad', [(0, (200, 226, 246)), (.6, (170, 200, 230)), (1, (80, 100, 130))]), (210, 30, 30),
    L((0.12, 0.818, 0.9, 0.894), 96, (210, 30, 30), mode='key', key=(210, 30, 30), t=(70, 160)),
    photo=ph(0.5, 0.45, 0.86, 0.85), pb=(210, 30, 30), lg=(30, 30, 40), lw=.55, order='LPTF',
    ft='b', vbox=(210, 30, 30), fcol=(30, 30, 40), fin=MINT, seed=2000)

# Crouching Tiger, Hidden Dragon (2000): the poster's gold, its pale serif CROUCHING TIGER / HIDDEN DRAGON lifted into one line, Michelle Yeoh and Chow Yun-fat
std('crouching-tiger-hidden-dragon-2000', ('grad', [(0, (220, 160, 60)), (.5, (150, 90, 30)), (1, (40, 20, 6))]), (250, 236, 200),
    L([(0.065, 0.055, 0.935, 0.106), (0.1, 0.11, 0.9, 0.175)], 90, (250, 236, 200), mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.6, 0.9, 0.8), pb=(250, 236, 200), lg=WHT, lw=.5, order='LPTCF', credit=['AN ANG LEE', 'FILM'], ccol=(250, 236, 200),
    ft='e', fcol=(250, 230, 200), fin=MINT, seed=2000)

# Dave Chappelle: Killin' Them Softly (2000): the poster's green and yellow, dave chappelle typeset in a script in its green (parked for Ian's logo, see data/logos-wanted.md: the hand lettering runs sideways in green on green and yellow, and the cut came out as smudges), Dave on stage (HBO logo)
std('dave-chappelle-killin-them-softly-2000', ('grad', [(0, (250, 230, 40)), (.5, (110, 190, 60)), (1, (40, 120, 200))]), (40, 110, 40),
    T('dave chappelle', 'cho', 120, (40, 120, 40)),
    photo=ph(0.55, 0.65, 0.7, 1.3), pb=(220, 60, 40), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=["KILLIN' THEM SOFTLY", 'STAND-UP SPECIAL'], ccol=(30, 30, 30),
    ft='a', fcol=(30, 30, 30), fin=MINT, seed=2000)

# Dinosaur (2000): Disney clamshell; the poster's sky, DINOSAUR typeset in a bronze serif with a dark keyline (parked for Ian's logo, see data/logos-wanted.md: the carved bronze letters are shaded light to dark over cloud, so both cuts came out garbled), Aladar's face in the diamond
disney('dinosaur-2000', ('grad', [(0, (60, 120, 200)), (.5, (90, 160, 220)), (1, (40, 90, 60))]), fin=dict(CLAM, vivid=.2),
       title=T('DINOSAUR', 'pagb', 110, (200, 140, 60), outline=((50, 26, 10), 2.2)),
       face=ph(.5, .4, .36, 1.4), lcol=WHT)

# Fantasia 2000 (2000): Disney clamshell; the poster's wine red, its gold FANTASIA / 2000 cut off it into one line, Mickey the sorcerer's apprentice in the diamond
disney('fantasia-2000-2000', ('grad', [(0, (110, 20, 50)), (.5, (150, 30, 70)), (1, (60, 10, 30))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.14, 0.075, 0.87, 0.18), (0.29, 0.188, 0.71, 0.26)], 120, valign='base', margin=0, gapf=.25, cuts=[comp_cut(lambda a: (a[..., 0] > .65) & (a[..., 1] > .5) & (a[..., 2] < .6), minf=.02)] * 2),
       face=ph(.62, .43, .2, 1.4), lcol=WHT)

# Finding Forrester (2000): the dusk sky over the city, the poster's white serif FINDING / FORRESTER lifted into one line, Sean Connery's face
std('finding-forrester-2000', ('grad', [(0, (230, 210, 170)), (.5, (200, 140, 80)), (1, (50, 30, 20))]), WHT,
    L([(0.45, 0.652, 0.935, 0.722), (0.295, 0.72, 0.97, 0.79)], 90, WHT, mode='light', valign='base'),
    photo=ph(0.5, 0.33, 0.86, 0.75), pb=WHT, lg=WHT, lw=.5, order='LPTF',
    ft='c', fcol=(250, 230, 210), fin=MINT, seed=2000)

# Gladiator (2000): the arena's dust, the poster's gold spaced GLADIATOR cut off it in its own shading, Maximus with his sword raised
std('gladiator-2000', ('grad', [(0, (150, 110, 60)), (.5, (70, 46, 20)), (1, (10, 6, 2))]), (230, 190, 120),
    LC([(0.1, 0.095, 0.9, 0.185)], 100, cuts=[key_cut(lambda a: (_lum(a) > .38) & (a[..., 0] > a[..., 2] + .1))]),
    photo=ph(0.5, 0.55, 0.86, 0.9), pb=(230, 190, 120), lg=WHT, lw=.5, order='LPTCSF', credit=['RUSSELL CROWE'], ccol=WHT, dotst=('ACTION', (190, 40, 30), WHT),
    ft='a', fcol=(230, 210, 180), fin=MINT, seed=2000)

# Gone in Sixty Seconds (2000): Touchstone, a slipcase; the poster's fire orange, GONE IN 60 SECONDS typeset in heavy italic capitals, the 60 in chrome white (parked for Ian's logo, see data/logos-wanted.md: the slanted red and chrome lettering sits in flames of its own colours), Nicolas Cage
std('gone-in-sixty-seconds-2000', ('grad', [(0, (240, 140, 30)), (.5, (180, 60, 20)), (1, (30, 6, 2))]), WHT,
    TT([('GONE IN', (190, 20, 20)), ('60', WHT), ('SECONDS', (190, 20, 20))], 'intbki', 100, sp=.3, outline=((30, 10, 4), 1.6)),
    photo=ph(0.6, 0.2, 0.8, 0.5), pb=WHT, lg=WHT, lw=.5, order='LPTF',
    ft='e', vbox=(200, 30, 20), fcol=(250, 220, 200), fin=MINT, seed=2000)

# High Fidelity (2000): Touchstone, a slipcase; the poster's orange record sleeve, its blue condensed High Fidelity keyed off it, the grid of John Cusack's faces
std('high-fidelity-2000', ('grad', [(0, (250, 150, 40)), (.5, (240, 120, 30)), (1, (120, 50, 10))]), (30, 60, 140),
    LC([(0.53, 0.305, 0.945, 0.402)], 100, cuts=[key_cut(lambda a: (a[..., 2] > a[..., 0] + .05) & (_lum(a) < .55))]),
    photo=ph(0.5, 0.62, 0.86, 0.75), pb=(30, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['JOHN CUSACK'], ccol=(30, 30, 30),
    ft='a', vbox=(30, 60, 140), fcol=(40, 20, 10), fin=MINT, seed=2000)

# How the Grinch Stole Christmas (2000): the night blue, the poster's green GRINCH with its red STOLE CHRISTMAS cut off it whole, the Grinch leaping before the moon
std('how-the-grinch-stole-christmas-2000', ('grad', [(0, (30, 60, 140)), (.6, (10, 20, 60)), (1, (2, 4, 16))]), (120, 200, 60),
    LC([(0.18, 0.66, 0.94, 0.94)], 140, cuts=[comp_cut(lambda a: ((a[..., 1] > a[..., 0] + .1) & (a[..., 1] > .4) & (a[..., 2] < .5)) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.02, close=3)]),
    photo=ph(0.5, 0.3, 0.86, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.99', 'FAMILY']),
    ft='b', fcol=(200, 216, 240), fin=MINT, seed=2000)

# In the Mood for Love (2000): the poster's red, IN THE MOOD FOR LOVE typeset in a pale gold serif like the poster's (parked for Ian's logo, see data/logos-wanted.md: the huge pale letters run behind and over the couple, so two cuts lost half of each word), Maggie Cheung and Tony Leung
std('in-the-mood-for-love-2000', ('grad', [(0, (190, 30, 30)), (.6, (120, 14, 14)), (1, (30, 4, 4))]), (230, 200, 130),
    T('IN THE MOOD FOR LOVE', 'ter', 90, (232, 204, 140)),
    photo=ph(0.55, 0.33, 0.6, 0.6), pb=(230, 200, 130), lg=(230, 200, 130), lw=.5, order='LPTCF', credit=['A FILM BY', 'WONG KAR-WAI'], ccol=(230, 200, 130),
    ft='e', fcol=(240, 210, 190), fin=MINT, seed=2000)

# Me, Myself & Irene (2000): the poster's white, its blue Me, Myself and red & Irene cut off it in their own colours, Jim Carrey's split face
std('me-myself-irene-2000', ('grad', [(0, (246, 246, 246)), (.6, (226, 230, 236)), (1, (120, 130, 150))]), (30, 70, 160),
    LC([(0.015, 0.06, 0.935, 0.25)], 130, cuts=[comp_cut(lambda a: _sat(a) > .4, minf=.02)]),
    photo=ph(0.5, 0.6, 0.86, 0.85), pb=(200, 30, 40), lg=(30, 40, 80), lw=.55, order='LPTF',
    ft='d', fcol=(30, 40, 80), fin=MINT, seed=2000)

# Meet the Parents (2000): the poster's white, its red serif Meet the Parents cut off it, De Niro and Stiller at the lie detector
std('meet-the-parents-2000', ('grad', [(0, (246, 246, 244)), (.6, (228, 226, 222)), (1, (120, 116, 110))]), (180, 20, 40),
    LC([(0.115, 0.022, 0.885, 0.27)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .5) & (a[..., 1] < .25), minf=.02)]),
    photo=ph(0.5, 0.62, 0.86, 0.85), pb=(180, 20, 40), lg=(30, 30, 30), lw=.55, order='LPTSF', stick=RWD(fill=(250, 226, 60)),
    ft='c', fcol=(30, 30, 30), fin=MINT, seed=2000)

# Memento (2000): the polaroid's white, MEMENTO typeset in a slanting hand in black (parked for Ian's logo, see data/logos-wanted.md: the handwriting runs at a tilt across the polaroid's edge and the cut broke into strokes), Guy Pearce in the nested photographs
std('memento-2000', ('grad', [(0, (246, 244, 238)), (.6, (230, 226, 218)), (1, (120, 116, 108))]), (20, 20, 20),
    T('MEMENTO', 'curbi', 110, (20, 20, 20)),
    photo=ph(0.5, 0.3, 0.86, 0.75), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTCF', credit=['A CHRISTOPHER NOLAN', 'FILM'], ccol=(20, 20, 20),
    ft='b', fcol=(20, 20, 20), fin=MINT, seed=2000)

# Nurse Betty (2000): the poster's white, its red NURSE BETTY keyed off it, Renée Zellweger with Morgan Freeman and Chris Rock
std('nurse-betty-2000', ('grad', [(0, (246, 246, 246)), (.6, (226, 230, 236)), (1, (120, 130, 150))]), (210, 30, 30),
    L((0.04, 0.795, 0.948, 0.868), 90, (210, 30, 30), mode='key', key=(210, 30, 30), t=(70, 160)),
    photo=ph(0.5, 0.33, 0.9, 0.75), pb=(210, 30, 30), lg=(30, 30, 40), lw=.55, order='LPTCF', credit=['A NEIL LABUTE', 'FILM'], ccol=(30, 30, 40),
    ft='a', vbox=(210, 30, 30), fcol=(30, 30, 40), fin=MINT, seed=2000)

# O Brother, Where Art Thou? (2000): Touchstone, a slipcase; the poster's sepia, O BROTHER, WHERE ART THOU? typeset in heavy slab capitals in its black (parked for Ian's logo, see data/logos-wanted.md: the distressed letters sit on a mottled sepia field and both cuts came out speckled), the three in their prison stripes
std('o-brother-where-art-thou-2000', ('grad', [(0, (210, 190, 130)), (.6, (160, 130, 70)), (1, (50, 40, 20))]), (30, 24, 14),
    [T('O BROTHER,', 'schb', 100, (30, 24, 14)), T('WHERE ART THOU?', 'schb', 50, (30, 24, 14))], tgap=8,
    photo=ph(0.5, 0.33, 0.9, 0.75), pb=(30, 24, 14), lg=(30, 24, 14), lw=.55, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=(30, 24, 14),
    ft='d', fcol=(30, 24, 14), fin=MINT, seed=2000)

# Paradise Lost 2: Revelations (2000): black, the poster's gold PARADISE LOST 2 / REVELATIONS cut off it into one line, the faces of the three (HBO logo; directors from IMDb)
std('paradise-lost-2-revelations-2000', ('grad', [(0, (110, 70, 30)), (.6, (30, 18, 8)), (1, (2, 2, 2))]), (230, 160, 80),
    LC([(0.13, 0.722, 0.87, 0.78), (0.13, 0.78, 0.87, 0.824)], 100, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 2] < .5), minf=.01)] * 2),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(230, 160, 80), lg=WHT, lw=.5, order='LPTCF', credit=['A DOCUMENTARY BY', 'BERLINGER &', 'SINOFSKY'], ccol=(230, 200, 160),
    ft='e', fcol=(220, 200, 170), fin=MINT, seed=2000)

# Reindeer Games (2000): the poster's black, its orange REINDEER / GAMES cut off it into one line, Ben Affleck and the burning casino
std('reindeer-games-2000', ('grad', [(0, (60, 30, 20)), (.6, (16, 8, 4)), (1, (2, 2, 2))]), (240, 150, 40),
    LC([(0.31, 0.745, 0.74, 0.812), (0.285, 0.812, 0.725, 0.905)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .4) & (a[..., 2] < .35), minf=.02)] * 2),
    photo=ph(0.5, 0.33, 0.86, 0.8), pb=(240, 150, 40), lg=WHT, lw=.5, order='LPTSF', dotst=('ACTION', (240, 150, 40), (20, 10, 4)),
    ft='c', fcol=(220, 200, 186), fin=MINT, seed=2000)

# Remember the Titans (2000): Disney, a live-action film, so a slipcase; the poster's black, its white REMEMBER THE / TITANS lifted into one line, Denzel Washington's face
std('remember-the-titans-2000', ('grad', [(0, (60, 40, 20)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), WHT,
    L([(0.25, 0.11, 0.76, 0.14), (0.148, 0.142, 0.868, 0.22)], 96, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.55, 0.86, 0.85), pb=(230, 160, 60), lg=WHT, lw=.5, order='LPTCF', credit=['DENZEL WASHINGTON'], ccol=WHT,
    ft='b', fcol=(220, 200, 186), fin=MINT, seed=2000)

# Scary Movie (2000): the theatre's dark, the poster's red dripping SCARY / MOVIE cut off it into one line, the cast screaming in their seats
std('scary-movie-2000', ('grad', [(0, (40, 80, 120)), (.6, (10, 20, 34)), (1, (2, 2, 6))]), (220, 30, 30),
    LC([(0.22, 0.682, 0.785, 0.79), (0.215, 0.785, 0.77, 0.89)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .3), minf=.02)] * 2),
    photo=ph(0.5, 0.33, 0.9, 0.7), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=BAR('00 0707', top='COMEDY', fill=(232, 228, 216)),
    ft='a', vbox=(220, 30, 30), fcol=(200, 210, 230), fin=MINT, seed=2000)

# Snatch (2000): the poster's yellow, its black brushed Snatch. cut off it, the tangle of fists, pistols and the diamond (Marv logo)
std('snatch-2000', ('grad', [(0, (250, 200, 40)), (.5, (240, 170, 30)), (1, (130, 80, 10))]), (20, 16, 10),
    LC([(0.095, 0.745, 0.92, 0.905)], 130, cuts=[comp_cut(lambda a: _lum(a) < .25, minf=.02)]),
    photo=ph(0.5, 0.33, 0.8, 0.95), pb=(20, 16, 10), lg=(20, 16, 10), lw=.55, order='LPTCF', credit=['A FILM BY', 'GUY RITCHIE'], ccol=(20, 16, 10),
    ft='b', vbox=(20, 16, 10), vink=(250, 200, 40), fcol=(40, 26, 10), fin=MINT, seed=2000)

# The Emperor's New Groove (2000): Disney clamshell; the jungle sky, the poster's blue plate with THE EMPEROR'S and its golden NEW GROOVE cut off it whole, Kuzco the llama in the diamond
disney('the-emperor-s-new-groove-2000', ('grad', [(0, (80, 170, 230)), (.5, (60, 140, 210)), (1, (40, 110, 50))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.03, 0.02, 0.98, 0.23)], 140, cuts=[plate_cut(lambda a: (a[..., 2] > .35) & (a[..., 2] > a[..., 0] + .15), rot='auto')]),
       face=ph(.6, .42, .2, 1.4), lcol=WHT)

# The Road to El Dorado (2000): DreamWorks, a slipcase; the jungle's gold, the poster's gold THE ROAD TO / EL DORADO cut off it into one line, Tulio and Miguel on Altivo before the city
std('the-road-to-el-dorado-2000', ('grad', [(0, (230, 180, 60)), (.5, (110, 120, 40)), (1, (20, 40, 10))]), (250, 220, 90),
    LC([(0.35, 0.812, 0.65, 0.84), (0.09, 0.84, 0.91, 0.918)], 110, valign='base', margin=0, gapf=.2, outline=((40, 30, 10), 1.6), cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .55), minf=.02)] * 2),
    photo=ph(0.5, 0.5, 0.86, 0.85), pb=(250, 220, 90), lg=WHT, lw=.5, order='LPTSF', dotst=('ANIMATION', (250, 220, 90), (40, 30, 10)),
    ft='c', fcol=(230, 220, 180), fin=MINT, seed=2000)

# The Virgin Suicides (2000): the poster's pale skin and hair, its white THE VIRGIN SUICIDES lifted and inked in the hair's dark gold, Kirsten Dunst's face (American Zoetrope logo)
std('the-virgin-suicides-2000', ('grad', [(0, (246, 236, 230)), (.6, (230, 210, 196)), (1, (180, 140, 100))]), (140, 90, 40),
    L([(0.04, 0.82, 0.17, 0.85), (0.04, 0.85, 0.965, 0.915)], 90, (140, 90, 40), mode='light', valign='base', speck=0),
    photo=ph(0.55, 0.35, 0.86, 0.75), pb=(140, 90, 40), lg=(140, 90, 40), lw=.55, order='LPTCF', credit=['A FILM BY', 'SOFIA COPPOLA'], ccol=(140, 90, 40),
    ft='e', fcol=(110, 70, 40), fin=MINT, seed=2000)

# Titan A.E. (2000): 20th Century Fox, a slipcase; space, TITAN A.E. typeset in wide heavy capitals in chrome white with a blue keyline (parked for Ian's logo, see data/logos-wanted.md: the chrome letters reflect the starfield and the cut came out in pieces), Cale flying from the ship
std('titan-a-e-2000', ('grad', [(0, (30, 30, 60)), (.6, (8, 8, 20)), (1, (2, 2, 6))]), (220, 220, 236),
    TT([('TITAN', (226, 228, 240)), ('A.E.', (226, 228, 240))], 'advb', 100, sp=.4, outline=((40, 80, 160), 2)),
    photo=ph(0.5, 0.72, 0.8, 0.6), pb=(120, 180, 240), lg=WHT, lw=.5, order='LPTF',
    ft='a', vbox=(200, 40, 40), fcol=(190, 196, 220), fin=MINT, seed=2000)

# Traffic (2000): the poster's dark green, its white stencilled TRAFFIC lifted, the cast's faces in the grain (USA Films logo)
std('traffic-2000', ('grad', [(0, (60, 80, 50)), (.6, (16, 22, 12)), (1, (2, 4, 2))]), WHT,
    LC([(0.06, 0.798, 0.94, 0.878)], 100, cuts=[comp_cut(lambda a: _lum(a) > .75, minf=.05, close=2, fillh=True)]),
    photo=ph(0.5, 0.33, 0.9, 0.75), pb=(200, 200, 140), lg=WHT, lw=.5, order='LPTCF', credit=['A STEVEN SODERBERGH', 'FILM'], ccol=WHT,
    ft='d', fcol=(200, 210, 190), fin=MINT, seed=2000)

# Wonder Boys (2000): black, the poster's white script Wonder Boys lifted, the four of them, Douglas in the glasses
std('wonder-boys-2000', ('grad', [(0, (40, 34, 30)), (.6, (12, 10, 8)), (1, (2, 2, 2))]), WHT,
    L((0.025, 0.52, 0.98, 0.618), 110, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.25, 0.9, 0.6), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['MICHAEL DOUGLAS', 'TOBEY MAGUIRE'], ccol=WHT,
    ft='a', fcol=(210, 200, 196), fin=MINT, seed=2000)

# A Beautiful Mind (2001): the chalkboard's dark, the poster's gold A BEAUTIFUL / MIND cut off it into one line, Russell Crowe behind the window of equations
std('a-beautiful-mind-2001', ('grad', [(0, (60, 60, 40)), (.6, (16, 16, 10)), (1, (2, 2, 2))]), (240, 210, 90),
    LC([(0.195, 0.83, 0.845, 0.892), (0.3, 0.89, 0.77, 0.97)], 100, valign='base', margin=0, gapf=.4, cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 1] > .5) & (a[..., 2] < .45), minf=.02)] * 2),
    photo=ph(0.5, 0.33, 0.86, 0.85), pb=(240, 210, 90), lg=WHT, lw=.5, order='LPTCF', credit=['A RON HOWARD', 'FILM'], ccol=(240, 220, 150),
    ft='e', fcol=(210, 210, 190), fin=MINT, seed=2001)

# Along Came a Spider (2001): the shattered glass blue into white, the poster's white along came a spider lifted onto the blue, Morgan Freeman and Monica Potter
std('along-came-a-spider-2001', ('grad', [(0, (20, 60, 100)), (.6, (10, 30, 60)), (1, (2, 10, 20))]), WHT,
    L((0.215, 0.072, 0.97, 0.148), 90, WHT, mode='light', speck=0),
    photo=ph(0.5, 0.38, 0.86, 0.75), pb=(220, 30, 30), lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(236, 122, 40), ink=(20, 16, 12)),
    ft='b', fcol=(190, 210, 230), fin=MINT, seed=2001)

# Amélie (2001): the poster's green, its yellow script Amelie cut off it, Audrey Tautou's smile
std('amelie-2001', ('grad', [(0, (30, 130, 60)), (.6, (12, 60, 24)), (1, (2, 14, 6))]), (250, 220, 40),
    LC([(0.07, 0.79, 0.93, 0.95)], 130, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .55) & (a[..., 2] < .45), minf=.02)]),
    photo=ph(0.48, 0.35, 0.8, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['UN FILM DE', 'JEAN-PIERRE JEUNET'], ccol=(250, 230, 140),
    ft='c', fcol=(210, 230, 210), fin=MINT, seed=2001)

# Atlantis: The Lost Empire (2001): Disney clamshell; the poster's deep blue, ATLANTIS / THE LOST EMPIRE typeset in a white serif like the logo's (parked for Ian's logo, see data/logos-wanted.md: the thin white letters sit in the crystal's white glow, and both cuts broke), Milo's face in the diamond
disney('atlantis-the-lost-empire-2001', ('grad', [(0, (20, 60, 120)), (.5, (40, 110, 180)), (1, (10, 30, 70))]), fin=dict(CLAM, vivid=.2),
       title=[T('ATLANTIS', 'pagb', 100, WHT, outline=((20, 50, 110), 1.6)), T('THE LOST EMPIRE', 'pagb', 46, WHT)],
       face=ph(.5, .72, .12, 1.4), lcol=WHT)

# Baby Boy (2001): the poster's sky, BABY BOY typeset in light spaced capitals in white (parked for Ian's logo, see data/logos-wanted.md: the thin white letters on a pale sky lost their strokes twice), Tyrese Gibson on the bike
std('baby-boy-2001', ('grad', [(0, (180, 210, 230)), (.5, (140, 150, 140)), (1, (40, 40, 30))]), WHT,
    TT([('BABY', WHT), ('BOY', WHT)], 'hcn', 100, sp=.4, outline=((60, 80, 100), 1.6)),
    photo=ph(0.55, 0.55, 0.86, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['WRITTEN & DIRECTED BY', 'JOHN SINGLETON'], ccol=WHT,
    ft='d', fcol=(220, 220, 210), fin=MINT, seed=2001)

# Blow (2001): the poster's red, its white stencilled BLOW lifted, Johnny Depp and Penélope Cruz lying together
std('blow-2001', ('grad', [(0, (170, 50, 60)), (.5, (110, 24, 30)), (1, (24, 4, 6))]), WHT,
    LC([(0.125, 0.105, 0.88, 0.205)], 110, cuts=[comp_cut(lambda a: _lum(a) > .85, minf=.05)]),
    photo=ph(0.5, 0.45, 0.86, 0.6), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['JOHNNY DEPP', 'PENÉLOPE CRUZ'], ccol=WHT,
    ft='b', fcol=(240, 210, 210), fin=MINT, seed=2001)

# Donnie Darko (2001): the night forest's blue, the poster's pale serif DONNIE DARKO lifted, Frank the rabbit in the trees (Flower Films logo)
std('donnie-darko-2001', ('grad', [(0, (30, 50, 80)), (.6, (8, 14, 26)), (1, (2, 4, 8))]), (200, 220, 236),
    L((0.19, 0.888, 0.81, 0.932), 90, (210, 226, 240), mode='light', speck=0),
    photo=ph(0.5, 0.33, 0.7, 1.1), pb=(170, 200, 230), lg=WHT, lw=.5, order='LPTCF', credit=['JAKE GYLLENHAAL'], ccol=(200, 220, 236),
    ft='c', fcol=(170, 190, 210), fin=MINT, seed=2001)

# From Hell (2001): black, the poster's white FROM / HELL lifted into one line, the red slash of light and Ripper's silhouette (no logo file: 20th Century Fox, from IMDb's company credits)
std('from-hell-2001', ('grad', [(0, (60, 20, 20)), (.6, (16, 6, 6)), (1, (2, 2, 2))]), WHT,
    L([(0.52, 0.676, 0.866, 0.746), (0.52, 0.746, 0.866, 0.816)], 110, WHT, mode='light', valign='base'),
    photo=ph(0.65, 0.2, 0.6, 0.55), pb=(210, 30, 30), studio=['20TH CENTURY FOX'], scol=WHT, order='lPTSF', stick=BAR('01 1019', top='HORROR', fill=(230, 226, 214)),
    ft='a', vbox=(210, 30, 30), fcol=(210, 200, 200), fin=MINT, seed=2001)

# Hannibal (2001): black, the poster's red serif HANNIBAL keyed off it, Anthony Hopkins's face in the dark with its red eye
std('hannibal-2001', ('grad', [(0, (60, 40, 20)), (.6, (16, 10, 6)), (1, (2, 2, 2))]), (200, 30, 30),
    LC([(0.03, 0.1, 0.95, 0.175)], 90, cuts=[comp_cut(lambda a: (a[..., 0] > .45) & (a[..., 1] < .22) & (a[..., 0] > a[..., 1] * 2.5), minf=.1)]),
    photo=ph(0.55, 0.5, 0.9, 0.75), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTF',
    ft='e', fcol=(210, 196, 180), fin=MINT, seed=2001)

# Harry Potter and the Philosopher's Stone (2001): Warner Bros., a slipcase; the night blue over Hogwarts, the poster's silver Harry Potter with its lightning P cut off it, and AND THE PHILOSOPHER'S STONE, Harry in his glasses
std('harry-potter-and-the-philosopher-s-stone-2001', ('grad', [(0, (20, 40, 80)), (.6, (8, 16, 36)), (1, (2, 4, 10))]), (220, 220, 230),
    LC([(0.06, 0.03, 0.94, 0.22), (0.5, 0.22, 0.96, 0.266)], 140, valign='mid', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) > .62, minf=.003)] * 2),
    photo=ph(0.55, 0.52, 0.8, 0.85), pb=(240, 200, 120), lg=WHT, lw=.5, order='LPTCF', credit=['DANIEL RADCLIFFE'], ccol=WHT,
    ft='d', fcol=(190, 200, 220), fin=MINT, seed=2001)

# Jay and Silent Bob Strike Back (2001): the road map, the poster's silver JAY AND SILENT BOB STRIKE BACK badge cut off it whole and levelled, Jay, Silent Bob and the cast
std('jay-and-silent-bob-strike-back-2001', ('grad', [(0, (240, 236, 226)), (.6, (220, 214, 200)), (1, (120, 110, 96))]), (30, 30, 34),
    LC([(0.2, 0.53, 0.82, 0.78)], 140, cuts=[plate_cut(lambda a: (_lum(a) < .45) | ((_sat(a) < .15) & (_lum(a) > .5) & (_lum(a) < .85)), rot='auto')]),
    photo=ph(0.5, 0.25, 0.9, 0.6), pb=(30, 30, 34), lg=(30, 30, 34), lw=.55, order='LPTCSF', credit=['A FILM BY', 'KEVIN SMITH'], ccol=(30, 30, 34), stick=PRC(['$1.99', 'COMEDY']),
    ft='b', fcol=(30, 30, 34), fin=MINT, seed=2001)

# Kiss of the Dragon (2001): the fire's red into black, KISS OF THE DRAGON typeset in white spaced capitals (parked for Ian's logo, see data/logos-wanted.md: the small white letters sit in the flames' bright glow and two cuts lost them), Jet Li and Bridget Fonda (EuropaCorp logo)
std('kiss-of-the-dragon-2001', ('grad', [(0, (170, 40, 20)), (.5, (80, 14, 8)), (1, (6, 2, 2))]), WHT,
    T('KISS OF THE DRAGON', 'hcnb', 80, WHT),
    photo=ph(0.5, 0.4, 0.86, 0.85), pb=(250, 160, 60), lg=WHT, lw=.5, order='LPTF', dotst=('ACTION', (250, 160, 60), (30, 10, 4)),
    ft='a', fcol=(230, 200, 190), fin=MINT, seed=2001)

# Knockaround Guys (2001): the desert's pale sky, the poster's white KNOCKAROUND and red GUYS cut off it in their own colours, the four in their leather jackets (no logo file: New Line Cinema, from IMDb's company credits)
std('knockaround-guys-2001', ('grad', [(0, (200, 210, 220)), (.5, (150, 150, 140)), (1, (40, 34, 26))]), WHT,
    LC([(0.08, 0.39, 0.98, 0.55)], 130, outline=((30, 30, 30), 1.6), cuts=[comp_cut(lambda a: (_lum(a) > .9) | ((a[..., 0] > .6) & (a[..., 1] < .3) & (a[..., 2] < .3)), minf=.08)]),
    photo=ph(0.5, 0.72, 0.86, 0.6), pb=(200, 30, 30), studio=['NEW LINE CINEMA'], scol=(30, 30, 30), order='lPTF',
    ft='e', fcol=(240, 236, 226), fin=MINT, seed=2001)

# Lagaan: Once Upon a Time in India (2001): a 2-tape box (233 minutes); the poster's cream, its green serif LAGAAN and Once upon a time in India cut off it into one line, Aamir Khan's face
std('lagaan-once-upon-a-time-in-india-2001', ('grad', [(0, (246, 234, 200)), (.6, (230, 210, 170)), (1, (130, 110, 70))]), (30, 80, 50),
    [LC([(0.075, 0.78, 0.94, 0.875)], 120, cuts=[key_cut(lambda a: (a[..., 1] > a[..., 0]) & (_lum(a) < .45))]), LC([(0.075, 0.882, 0.935, 0.905)], 40, cuts=[key_cut(lambda a: (a[..., 1] > a[..., 0]) & (_lum(a) < .5))])], tgap=6,
    photo=ph(0.5, 0.3, 0.86, 0.75), pb=(30, 80, 50), lg=(30, 60, 40), lw=.55, order='LPTSF', stick=TWOST((30, 80, 50), (246, 234, 200)),
    ft='c', fcol=(30, 60, 40), fin=MINT, seed=2001, **TWO)

# Monsters, Inc. (2001): Pixar clamshell; the door's blue, the poster's white panel with its blue MONSTERS, INC. cut off it whole, Mike's face in the diamond
disney('monsters-inc-2001', ('grad', [(0, (30, 80, 200)), (.5, (60, 120, 220)), (1, (20, 40, 120))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.06, 0.06, 0.96, 0.24)], 140, cuts=[plate_cut(lambda a: _lum(a) > .85)]),
       face=ph(.62, .77, .2, 1.4), lcol=WHT)

# Mulholland Drive (2001): black, the poster's white condensed MULHOLLAND DRIVE lifted, Naomi Watts and Laura Harring in the blue light
std('mulholland-drive-2001', ('grad', [(0, (30, 40, 80)), (.6, (8, 10, 24)), (1, (2, 2, 4))]), WHT,
    L((0.105, 0.86, 0.893, 0.93), 90, WHT, mode='light'),
    photo=ph(0.5, 0.45, 0.86, 0.85), pb=(80, 130, 240), lg=WHT, lw=.5, order='LPTCF', credit=['A DAVID LYNCH', 'FILM'], ccol=(170, 190, 240),
    ft='b', fcol=(180, 190, 220), fin=MINT, seed=2001)

# Ocean's Eleven (2001): the poster's white, OCEAN'S 11 typeset in heavy condensed capitals in its red (parked for Ian's logo, see data/logos-wanted.md: OCEAN'S runs diagonally inside the big red 11 and the cut came out a sliver), the eleven's legs walking
std('ocean-s-eleven-2001', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (210, 30, 30),
    TT([("OCEAN'S", (210, 30, 30)), ('11', (210, 30, 30))], 'intbk', 110, sp=.3),
    photo=ph(0.6, 0.15, 0.8, 0.4), pb=(30, 30, 30), lg=(30, 30, 30), lw=.55, order='LPTCF', credit=['GEORGE CLOONEY', 'BRAD PITT'], ccol=(30, 30, 30),
    ft='a', vbox=(210, 30, 30), fcol=(30, 30, 30), fin=MINT, seed=2001)

# Osmosis Jones (2001): Warner Bros., a slipcase; the poster's cell blue, its green outlined OSMOSIS / JONES cut off it whole and levelled, Osmosis mid-flight
std('osmosis-jones-2001', ('grad', [(0, (60, 120, 220)), (.5, (30, 70, 170)), (1, (10, 20, 70))]), (150, 220, 60),
    LC([(0.06, 0.65, 0.92, 0.85)], 140, cuts=[comp_cut(lambda a: (a[..., 1] > .5) & (a[..., 1] > a[..., 2] + .1) & (a[..., 0] < .85), minf=.02, close=3, fillh=True, rot=-12)]),
    photo=ph(0.4, 0.3, 0.8, 0.95), pb=(250, 200, 40), lg=WHT, lw=.5, order='LPTSF', dotst=('ANIMATION', (250, 200, 40), (30, 20, 10)),
    ft='c', fcol=(200, 220, 250), fin=MINT, seed=2001)

# Raw Deal: A Question of Consent (2001): black, the poster's white RAW DEAL and A QUESTION OF CONSENT lifted into one line, the hand on the body (rakontur logo; director from IMDb)
std('raw-deal-a-question-of-consent-2001', ('grad', [(0, (60, 60, 64)), (.6, (16, 16, 18)), (1, (2, 2, 2))]), WHT,
    L([(0.125, 0.648, 0.895, 0.703), (0.13, 0.712, 0.88, 0.742)], 90, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.4, 0.4, 0.6, 1.0), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A DOCUMENTARY BY', 'BILLY CORBEN'], ccol=WHT,
    ft='e', fcol=(200, 200, 200), fin=MINT, seed=2001)

# Sex and Lucía (2001): the poster's sky white into red, its white sex and lucía with the small red and cut off it, Paz Vega on the motorbike
std('sex-and-lucia-2001', ('grad', [(0, (220, 230, 240)), (.5, (220, 120, 100)), (1, (130, 20, 20))]), WHT,
    LC([(0.02, 0.415, 0.985, 0.537)], 120, outline=((120, 20, 20), 1.6), cuts=[comp_cut(lambda a: (_lum(a) > .9) | ((a[..., 0] > .6) & (a[..., 1] < .3)), minf=.02)]),
    photo=ph(0.5, 0.18, 0.7, 0.55), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['UNA PELÍCULA DE', 'JULIO MEDEM'], ccol=WHT,
    ft='b', fcol=(250, 220, 220), fin=MINT, seed=2001)

# Shrek (2001): DreamWorks (PDI), a slipcase; the swamp green, SHREK typeset in a heavy serif in the logo's green with a dark keyline (parked for Ian's logo, see data/logos-wanted.md: the green carved letters sit on green grass and both cuts lost them), the green S with Shrek, Fiona and Donkey under it
std('shrek-2001', ('grad', [(0, (120, 180, 230)), (.5, (110, 170, 60)), (1, (40, 80, 20))]), (110, 170, 40),
    T('SHREK', 'schb', 120, (120, 180, 50), outline=((30, 50, 10), 2.2)),
    photo=ph(0.5, 0.38, 0.86, 0.85), pb=(110, 170, 40), lg=WHT, lw=.5, order='LPTSF', stick=BAR('01 1102', top='ANIMATION', fill=(230, 240, 220)),
    ft='a', vbox=(60, 110, 20), fcol=(230, 240, 220), fin=MINT, seed=2001)

# Spirited Away (2001): Studio Ghibli, a slipcase; black, the poster's white serif SPIRITED AWAY lifted, Chihiro before the bathhouse
std('spirited-away-2001', ('grad', [(0, (60, 30, 30)), (.6, (16, 8, 8)), (1, (2, 2, 2))]), WHT,
    L((0.078, 0.125, 0.91, 0.19), 90, WHT, mode='light'),
    photo=ph(0.45, 0.6, 0.8, 1.0), pb=(220, 60, 50), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'HAYAO MIYAZAKI'], ccol=WHT,
    ft='d', fcol=(220, 200, 196), fin=MINT, seed=2001)

# Super Troopers (2001): the sky blue, SUPER TROOPERS typeset in heavy capitals in the logo's yellow with a dark keyline (parked for Ian's logo, see data/logos-wanted.md: the moustache badge sits on the T of TROOPERS and the cut lost it twice), the five troopers hanging upside down
std('super-troopers-2001', ('grad', [(0, (120, 180, 220)), (.5, (60, 120, 180)), (1, (20, 40, 70))]), (250, 210, 50),
    T('SUPER TROOPERS', 'intbk', 100, (250, 200, 40), outline=((60, 30, 10), 2.2)),
    photo=ph(0.5, 0.25, 0.9, 0.55), pb=(250, 210, 50), lg=WHT, lw=.5, order='LPTF',
    ft='b', fcol=(220, 230, 240), fin=MINT, seed=2001)

# Swordfish (2001): the poster's black and white, its yellow-green SWORDFISH cut off it, Travolta, Jackman and Halle Berry round the keyboard
std('swordfish-2001', ('grad', [(0, (60, 60, 60)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), (200, 230, 50),
    LC([(0.06, 0.845, 0.94, 0.94)], 110, cuts=[comp_cut(lambda a: (a[..., 1] > .55) & (a[..., 2] < .45), minf=.02)]),
    photo=ph(0.5, 0.35, 0.86, 0.75), pb=(200, 230, 50), lg=WHT, lw=.5, order='LPTF',
    ft='e', fcol=(200, 200, 200), fin=MINT, seed=2001)

# The Lord of the Rings: The Fellowship of the Ring (2001): a 2-tape box (179 minutes, the theatrical cut); the poster's golden haze, THE LORD OF THE RINGS and THE FELLOWSHIP OF THE RING typeset in a gold serif (parked for Ian's logo, see data/logos-wanted.md: the logo's gold sits on a gold haze and the cut came out faint and broken), Frodo with the Fellowship round him
std('the-lord-of-the-rings-the-fellowship-of-the-ring-2001', ('grad', [(0, (120, 100, 60)), (.5, (60, 50, 26)), (1, (10, 8, 4))]), (230, 190, 100),
    T('THE LORD OF THE RINGS', 'pagb', 130, (236, 196, 110), outline=((40, 26, 10), 1.6)),
    photo=ph(0.5, 0.5, 0.6, 0.7), pb=(230, 190, 100), lg=WHT, lw=.5, order='LPTCSF', credit=['THE FELLOWSHIP', 'OF THE RING'], ccol=(236, 210, 160), stick=TWOST((230, 190, 100), (30, 24, 10)),
    ft='c', fcol=(220, 206, 180), fin=MINT, seed=2001, **TWO)

# The Man Who Wasn't There (2001): black, THE MAN WHO WASN'T THERE typeset in heavy condensed capitals in the poster's grey and yellow (parked for Ian's logo, see data/logos-wanted.md: the poster's huge grey MAN is cut into strips across the faces, and only WHO WASN'T THERE would cut), Billy Bob Thornton (USA Films logo)
std('the-man-who-wasn-t-there-2001', ('grad', [(0, (50, 50, 50)), (.6, (14, 14, 14)), (1, (2, 2, 2))]), (220, 220, 70),
    TT([('THE MAN', (190, 190, 190)), ("WHO WASN'T THERE", (220, 220, 70))], 'intbk', 90, sp=.3),
    photo=ph(0.6, 0.45, 0.6, 1.0), pb=(220, 220, 70), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'JOEL & ETHAN COEN'], ccol=WHT,
    ft='a', fcol=(200, 200, 200), fin=MINT, seed=2001)

# The Royal Tenenbaums (2001): Touchstone, a slipcase; the poster's white, its red Futura THE ROYAL TENENBAUMS keyed off it, the family lined up in their clothes
std('the-royal-tenenbaums-2001', ('grad', [(0, (246, 240, 230)), (.6, (230, 220, 206)), (1, (130, 116, 100))]), (190, 30, 30),
    L((0.03, 0.072, 0.97, 0.112), 76, (190, 30, 30), mode='key', key=(190, 40, 40), t=(70, 160)),
    photo=ph(0.5, 0.45, 0.86, 0.85), pb=(190, 30, 30), lg=(40, 30, 30), lw=.55, order='LPTCF', credit=['A FILM BY', 'WES ANDERSON'], ccol=(40, 30, 30),
    ft='b', fcol=(40, 30, 30), fin=MINT, seed=2001)

# Training Day (2001): the poster's dark sepia, its white serif TRAINING / DAY lifted into one line, Denzel Washington and Ethan Hawke
std('training-day-2001', ('grad', [(0, (100, 90, 70)), (.6, (30, 26, 20)), (1, (2, 2, 2))]), WHT,
    L([(0.13, 0.015, 0.92, 0.145), (0.23, 0.145, 0.63, 0.228)], 110, WHT, mode='light', valign='base', speck=0),
    photo=ph(0.5, 0.55, 0.86, 0.85), pb=(230, 190, 90), lg=WHT, lw=.5, order='LPTCSF', credit=['DENZEL WASHINGTON', 'ETHAN HAWKE'], ccol=WHT, stick=RWD(),
    ft='d', fcol=(220, 210, 190), fin=MINT, seed=2001)

# Wet Hot American Summer (2001): the camp's pines, WET HOT AMERICAN SUMMER typeset in heavy capitals in the logo's blue and red with white keylines (parked for Ian's logo, see data/logos-wanted.md: the star-spangled letters are striped with white and the cut came out in shreds), the campers piled in the truck (no logo file: USA Films, from IMDb's company credits)
std('wet-hot-american-summer-2001', ('grad', [(0, (60, 130, 200)), (.5, (40, 110, 60)), (1, (10, 40, 14))]), WHT,
    TT([('WET', (30, 60, 160)), ('HOT', (210, 30, 40)), ('AMERICAN', (210, 30, 40)), ('SUMMER', (30, 60, 160))], 'intbk', 90, sp=.25, outline=(WHT, 2)),
    photo=ph(0.5, 0.65, 0.86, 0.85), pb=(200, 30, 40), studio=['USA FILMS'], scol=WHT, order='lPTCF', credit=['A DAVID WAIN', 'FILM'], ccol=WHT,
    ft='a', vbox=(200, 30, 40), fcol=(220, 236, 220), fin=MINT, seed=2001)

# 25th Hour (2002): Touchstone, a slipcase; the poster's red, its white stencilled 25th / hour cut off it whole, Edward Norton walking his dog
std('25th-hour-2002', ('grad', [(0, (200, 30, 30)), (.5, (140, 16, 16)), (1, (30, 4, 4))]), WHT,
    LC([(0.04, 0.2, 0.71, 0.49)], 140, cuts=[comp_cut(lambda a: _lum(a) > .82, minf=.03)]),
    photo=ph(0.7, 0.72, 0.5, 1.1), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['A SPIKE LEE', 'JOINT'], ccol=WHT,
    ft='a', vbox=(20, 20, 20), fcol=(250, 220, 220), fin=MINT, seed=2002)

# 8 Mile (2002): black, the poster's yellow-orange 8 Mile cut off it, Eminem in the hood
std('8-mile-2002', ('grad', [(0, (40, 40, 40)), (.6, (12, 12, 12)), (1, (2, 2, 2))]), (250, 200, 40),
    LC([(0.22, 0.575, 0.78, 0.715)], 120, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .45) & (a[..., 2] < .4), minf=.02)]),
    photo=ph(0.5, 0.22, 0.7, 0.75), pb=(250, 200, 40), lg=WHT, lw=.5, order='LPTSF', dotst=('MUSIC', (250, 200, 40), (20, 20, 20)),
    ft='e', fcol=(200, 200, 200), fin=MINT, seed=2002)

# Adaptation. (2002): the poster's white, its green typewriter Adaptation. keyed off it, the orchid and Nicolas Cage in the flowerpot
std('adaptation-2002', ('grad', [(0, (246, 246, 244)), (.6, (230, 236, 226)), (1, (130, 140, 120))]), (40, 150, 70),
    LC([(0.1, 0.195, 0.9, 0.268)], 100, cuts=[key_cut(lambda a: a[..., 1] > a[..., 0] + .1)]),
    photo=ph(0.55, 0.65, 0.86, 0.6), pb=(40, 150, 70), lg=(30, 50, 30), lw=.55, order='LPTCF', credit=['A SPIKE JONZE', 'FILM'], ccol=(30, 50, 30),
    ft='b', fcol=(30, 50, 30), fin=MINT, seed=2002)

# Austin Powers in Goldmember (2002): the poster's sky blue, its gold GOLDMEMBER with the AUSTIN POWERS IN badge cut off it whole, Austin, Foxxy and the villains
std('austin-powers-in-goldmember-2002', ('grad', [(0, (60, 170, 230)), (.5, (30, 130, 200)), (1, (10, 50, 90))]), (250, 200, 40),
    LC([(0.13, 0.715, 0.87, 0.9)], 140, cuts=[comp_cut(lambda a: ((a[..., 0] > .7) & (a[..., 1] > .45) & (a[..., 2] < .4)) | (_lum(a) < .15), minf=.02, close=2)]),
    photo=ph(0.5, 0.35, 0.86, 0.8), pb=(250, 200, 40), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$2.99', 'COMEDY']),
    ft='c', fcol=(220, 236, 250), fin=MINT, seed=2002)

# Bend It Like Beckham (2002): the poster's white, its green-and-black BEND IT / LIKE BECKHAM cut off it into one line, Jess and Jules laughing
std('bend-it-like-beckham-2002', ('grad', [(0, (246, 246, 246)), (.6, (226, 232, 226)), (1, (120, 130, 120))]), (100, 180, 60),
    LC([(0.105, 0.115, 0.86, 0.196), (0.105, 0.193, 0.86, 0.237)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (_lum(a) < .3) | ((a[..., 1] > .55) & (a[..., 2] < .5) & (a[..., 0] < .8)), minf=.02)] * 2),
    photo=ph(0.5, 0.6, 0.86, 0.85), pb=(100, 180, 60), lg=(30, 30, 30), lw=.55, order='LPTF',
    ft='a', vbox=(100, 180, 60), fcol=(30, 30, 30), fin=MINT, seed=2002)

# Bowling for Columbine (2002): black, the poster's white BOWLING / COLUMBINE and red FOR cut off it into one line, the pins as bullets (director from IMDb)
std('bowling-for-columbine-2002', ('grad', [(0, (40, 40, 44)), (.6, (12, 12, 14)), (1, (2, 2, 2))]), WHT,
    LC([(0.05, 0.695, 0.95, 0.78), (0.05, 0.783, 0.95, 0.87)], 100, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (_lum(a) > .82) | ((a[..., 0] > .5) & (a[..., 1] < .3)), minf=.02)] * 2),
    photo=ph(0.5, 0.25, 0.86, 0.75), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['A FILM BY', 'MICHAEL MOORE'], ccol=WHT,
    ft='d', vbox=(200, 30, 30), fcol=(210, 210, 210), fin=MINT, seed=2002)

# Catch Me If You Can (2002): DreamWorks, a slipcase; the poster's white, its blue arrow with catch me / if you can cut off it whole, Frank and Hanratty running
std('catch-me-if-you-can-2002', ('grad', [(0, (246, 246, 246)), (.6, (226, 230, 236)), (1, (120, 130, 150))]), (30, 90, 170),
    LC([(0.0, 0.47, 0.89, 0.65)], 140, cuts=[plate_cut(lambda a: (a[..., 2] > .45) & (a[..., 0] < .35))]),
    photo=ph(0.87, 0.35, 0.26, 1.6), pb=(30, 90, 170), lg=(30, 40, 70), lw=.55, order='LPTCF', credit=['LEONARDO DiCAPRIO', 'TOM HANKS'], ccol=(30, 40, 70),
    ft='b', fcol=(30, 40, 70), fin=MINT, seed=2002)

# Changing Lanes (2002): the night street, the poster's yellow CHANGING / LANES cut off it into one line, Ben Affleck and Samuel L. Jackson
std('changing-lanes-2002', ('grad', [(0, (40, 50, 60)), (.6, (12, 14, 18)), (1, (2, 2, 4))]), (250, 220, 40),
    LC([(0.3, 0.522, 0.705, 0.6), (0.3, 0.598, 0.705, 0.712)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (a[..., 0] > .7) & (a[..., 1] > .6) & (a[..., 2] < .4), minf=.02)] * 2),
    photo=ph(0.5, 0.25, 0.86, 0.75), pb=(250, 220, 40), lg=WHT, lw=.5, order='LPTSF', stick=BAR('02 0412', top='THRILLER', fill=(232, 228, 214)),
    ft='e', fcol=(200, 206, 210), fin=MINT, seed=2002)

# City of God (2002): the poster's orange-red, its white CITY of GOD lifted, the gang on the dusty hill (O2 Filmes logo)
std('city-of-god-2002', ('grad', [(0, (240, 160, 40)), (.5, (200, 60, 30)), (1, (60, 10, 6))]), WHT,
    L((0.04, 0.432, 0.96, 0.534), 110, WHT, mode='light'),
    photo=ph(0.5, 0.2, 0.9, 0.5), pb=WHT, lg=WHT, lw=.5, order='LPTCF', credit=['UM FILME DE', 'FERNANDO MEIRELLES'], ccol=WHT,
    ft='c', fcol=(250, 220, 200), fin=MINT, seed=2002)

# Collateral Damage (2002): the poster's fire into black, its white COLLATERAL / DAMAGE lifted into one line, Arnold's face
std('collateral-damage-2002', ('grad', [(0, (200, 120, 40)), (.5, (90, 40, 14)), (1, (4, 2, 2))]), WHT,
    [L((0.025, 0.812, 0.975, 0.865), 96, WHT, mode='light'), L((0.025, 0.865, 0.975, 0.915), 96, WHT, mode='light')], tgap=8,
    photo=ph(0.45, 0.4, 0.86, 0.85), pb=WHT, lg=WHT, lw=.5, order='LPTF',
    ft='a', fcol=(230, 210, 190), fin=MINT, seed=2002)

# Die Another Day (2002): the ice-blue, the poster's white italic DIE / ANOTHER / DAY cut off it into one line (its gold 007 left off: it sits on the sea's glints), Bond with the pistol
std('die-another-day-2002', ('grad', [(0, (60, 150, 190)), (.5, (20, 70, 110)), (1, (4, 14, 26))]), WHT,
    LC([(0.18, 0.05, 0.44, 0.12), (0.05, 0.115, 0.625, 0.18), (0.22, 0.185, 0.71, 0.255)], 110, valign='base', margin=0, gapf=.2,
       cuts=[comp_cut(lambda a: _lum(a) > .8, minf=.03)] * 3),
    photo=ph(0.6, 0.55, 0.86, 0.85), pb=(220, 190, 90), lg=WHT, lw=.5, order='LPTCF', credit=['PIERCE BROSNAN'], ccol=WHT,
    ft='d', vbox=(200, 170, 70), vink=(10, 10, 20), fcol=(200, 220, 236), fin=MINT, seed=2002)

# Gangs of New York (2002): Miramax, the poster's dusk, GANGS OF NEW YORK typeset in condensed capitals in the poster's gold (parked for Ian's logo, see data/logos-wanted.md: the gold letters are distressed and sit on a gold skyline, and both cuts came out faint and broken), DiCaprio, Diaz and Day-Lewis
std('gangs-of-new-york-2002', ('grad', [(0, (80, 70, 40)), (.6, (24, 20, 10)), (1, (2, 2, 2))]), (230, 190, 100),
    T('GANGS OF NEW YORK', 'hcnb', 100, (230, 196, 110)),
    photo=ph(0.5, 0.2, 0.9, 0.5), pb=(230, 190, 100), lg=WHT, lw=.5, order='LPTCF', credit=['A MARTIN SCORSESE', 'PICTURE'], ccol=(230, 210, 160),
    ft='b', fcol=(220, 206, 180), fin=MINT, seed=2002)

# Harry Potter and the Chamber of Secrets (2002): Warner Bros., a slipcase; the poster's green, HARRY POTTER typeset in a gold serif with AND THE CHAMBER OF SECRETS (parked for Ian's logo, see data/logos-wanted.md: the logo's thin gold strokes sit on green light and both cuts broke them up), Harry, Ron and Hermione
std('harry-potter-and-the-chamber-of-secrets-2002', ('grad', [(0, (30, 70, 60)), (.6, (10, 26, 22)), (1, (2, 6, 4))]), (230, 190, 90),
    [T('HARRY POTTER', 'pagb', 110, (232, 194, 96), outline=((30, 20, 6), 1.6)), T('AND THE CHAMBER OF SECRETS', 'pagb', 46, (232, 210, 150))], tgap=8,
    photo=ph(0.5, 0.5, 0.86, 0.85), pb=(230, 190, 90), lg=WHT, lw=.5, order='LPTSF', stick=RWD(fill=(250, 226, 60)),
    ft='a', fcol=(200, 220, 210), fin=MINT, seed=2002)

# Hero (2002): the poster's sepia, HERO typeset in a wide gold serif (parked for Ian's logo, see data/logos-wanted.md: the gold letters fade into the gold army behind them and both lifts lost half of each), Jet Li and the warriors (Edko logo)
std('hero-2002', ('grad', [(0, (150, 120, 70)), (.5, (80, 60, 30)), (1, (14, 10, 4))]), (240, 200, 110),
    T('HERO', 'pagb', 130, (240, 200, 110), outline=((40, 26, 10), 1.6)),
    photo=ph(0.5, 0.3, 0.9, 0.7), pb=(240, 200, 110), lg=WHT, lw=.5, order='LPTCF', credit=['A ZHANG YIMOU', 'FILM'], ccol=(240, 220, 170),
    ft='c', fcol=(230, 210, 180), fin=MINT, seed=2002)

# Ice Age (2002): Blue Sky (Fox), a slipcase; the poster's sky blue, its white chunky ICE AGE lifted, Manny, Sid and Diego in the ice
std('ice-age-2002', ('grad', [(0, (60, 150, 230)), (.5, (130, 200, 240)), (1, (220, 236, 246))]), WHT,
    LC([(0.06, 0.04, 0.95, 0.175)], 140, outline=((20, 80, 160), 2), cuts=[comp_cut(lambda a: _lum(a) > .86, minf=.03)]),
    photo=ph(0.5, 0.55, 0.86, 0.85), pb=(20, 80, 160), lg=(20, 60, 120), lw=.55, order='LPTSF', dotst=('FAMILY', (240, 120, 30), WHT),
    ft='b', fcol=(20, 50, 100), fin=MINT, seed=2002)

# Insomnia (2002): black, INSOMNIA typeset in condensed grey capitals (parked for Ian's logo, see data/logos-wanted.md: the poster's grey letters are blurred, and the lift came out half gone), Al Pacino's face half in the dark
std('insomnia-2002', ('grad', [(0, (30, 40, 50)), (.6, (8, 10, 14)), (1, (2, 2, 2))]), (200, 206, 214),
    T('INSOMNIA', 'hcnb', 110, (200, 206, 214)),
    photo=ph(0.75, 0.42, 0.42, 1.2), pb=(200, 206, 214), lg=WHT, lw=.5, order='LTPCF', credit=['A CHRISTOPHER NOLAN', 'FILM'], ccol=(200, 206, 214),
    ft='e', fcol=(180, 186, 196), fin=MINT, seed=2002)

# Lilo & Stitch (2002): Disney clamshell; the wave's blue, LILO & STITCH typeset in heavy capitals in the logo's red with a white keyline (parked for Ian's logo, see data/logos-wanted.md: the bouncy red letters sit in the wave's white spray and the cut kept only two letters), Stitch's face in the diamond
disney('lilo-stitch-2002', ('grad', [(0, (60, 150, 220)), (.5, (40, 120, 200)), (1, (20, 60, 120))]), fin=dict(CLAM, vivid=.2),
       title=T('LILO & STITCH', 'intbk', 110, (210, 40, 40), outline=(WHT, 2.4)),
       face=ph(.56, .62, .14, 1.4), lcol=WHT)

# Mr. Deeds (2002): the hotel's gold, the poster's black MR. and red DEEDS cut off it into one line, Adam Sandler and Winona Ryder
std('mr-deeds-2002', ('grad', [(0, (220, 190, 130)), (.6, (170, 130, 70)), (1, (60, 40, 20))]), (200, 20, 30),
    LC([(0.03, 0.8, 0.43, 0.86), (0.03, 0.86, 0.71, 0.965)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: _lum(a) < .2, minf=.05), comp_cut(lambda a: (a[..., 0] > .55) & (a[..., 1] < .25), minf=.05)]),
    photo=ph(0.6, 0.4, 0.86, 0.75), pb=(200, 20, 30), lg=(40, 26, 10), lw=.55, order='LPTF',
    ft='d', fcol=(40, 26, 10), fin=MINT, seed=2002)

# Paid in Full (2002): the poster's brown and black, its gold PAID IN FULL cut off it, the three men (Roc-A-Fella logo)
std('paid-in-full-2002', ('grad', [(0, (110, 70, 30)), (.6, (30, 18, 8)), (1, (2, 2, 2))]), (240, 190, 50),
    L((0.045, 0.812, 0.945, 0.876), 100, (240, 190, 50), mode='light'),
    photo=ph(0.5, 0.35, 0.9, 0.85), pb=(240, 190, 50), lg=WHT, lw=.5, order='LPTCSF', credit=['MEKHI PHIFER', 'WOOD HARRIS'], ccol=WHT, stick=BAR('02 1025', top='CRIME', fill=(232, 226, 210)),
    ft='a', fcol=(220, 200, 170), fin=MINT, seed=2002)

# Poolhall Junkies (2002): the poster's white, poolhall junkies typeset in a rounded bold in its green (parked for Ian's logo, see data/logos-wanted.md: the felt-textured green letters came out holed both times), the cast in black
std('poolhall-junkies-2002', ('grad', [(0, (246, 246, 246)), (.6, (226, 232, 226)), (1, (120, 130, 120))]), (40, 140, 60),
    T('poolhall junkies', 'popb', 110, (40, 140, 60)),
    photo=ph(0.5, 0.48, 0.9, 0.5), pb=(40, 140, 60), lg=(30, 40, 30), lw=.55, order='LPTF',
    ft='c', fcol=(30, 40, 30), fin=MINT, seed=2002)

# Red Dragon (2002): the dark, the poster's red RED and white DRAGON serif lifted into one line, Anthony Hopkins's face
std('red-dragon-2002', ('grad', [(0, (60, 30, 20)), (.6, (16, 8, 6)), (1, (2, 2, 2))]), WHT,
    LC([(0.08, 0.095, 0.95, 0.155)], 100, cuts=[comp_cut(lambda a: (_lum(a) > .6) | ((a[..., 0] > .5) & (a[..., 1] < .25)), minf=.02)]),
    photo=ph(0.5, 0.45, 0.86, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['ANTHONY HOPKINS', 'EDWARD NORTON'], ccol=WHT,
    ft='b', vbox=(200, 30, 30), fcol=(210, 200, 196), fin=MINT, seed=2002)

# Return to Never Land (2002): Disney clamshell; the night sky over London, RETURN TO NEVER LAND typeset in a gold serif (parked for Ian's logo, see data/logos-wanted.md: the gold glowing letters fade into the moonlit sea and the cut kept a few strokes), Peter Pan's face in the diamond
disney('return-to-never-land-2002', ('grad', [(0, (20, 40, 100)), (.5, (40, 90, 160)), (1, (10, 20, 60))]), fin=dict(CLAM, vivid=.2),
       title=[T('NEVER LAND', 'pagb', 110, (250, 210, 80), outline=((40, 30, 10), 1.6)), T('RETURN TO', 'pagb', 50, (250, 220, 140))],
       face=ph(.63, .25, .1, 1.4), lcol=WHT)

# Road to Perdition (2002): DreamWorks, a slipcase; the rain's dark, the poster's bronze ROAD TO / PERDITION cut off it into one line, Tom Hanks in the hat and coat
std('road-to-perdition-2002', ('grad', [(0, (60, 60, 60)), (.6, (16, 16, 16)), (1, (2, 2, 2))]), (200, 170, 120),
    LC([(0.29, 0.76, 0.72, 0.82), (0.09, 0.82, 0.91, 0.925)], 110, valign='base', margin=0, gapf=.2, cuts=[comp_cut(lambda a: (_lum(a) > .45) & (a[..., 0] > a[..., 2]), minf=.02)] * 2),
    photo=ph(0.5, 0.35, 0.86, 0.85), pb=(200, 170, 120), lg=WHT, lw=.5, order='LPTCF', credit=['A SAM MENDES', 'FILM'], ccol=(220, 200, 170),
    ft='d', fcol=(200, 200, 200), fin=MINT, seed=2002)

# 11'09''01 September 11 (2002): the poster's white, its black brushed September 11 cut off it, the mosaic of faces (Galatée logo; eleven directors, so no line)
std('september-11-2002', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (20, 20, 20),
    LC([(0.11, 0.09, 0.89, 0.235)], 130, cuts=[comp_cut(lambda a: _lum(a) < .3, minf=.01)]),
    photo=ph(0.5, 0.52, 0.9, 0.5), pb=(20, 20, 20), lg=(20, 20, 20), lw=.55, order='LPTF',
    ft='e', fcol=(20, 20, 20), fin=MINT, seed=2002)

# Spider-Man (2002): Marvel, a slipcase; the poster's gold, SPIDER-MAN typeset in wide heavy capitals in chrome white (parked for Ian's logo, see data/logos-wanted.md: the chrome letters are banded with the gold background and the cut came out striped), Spider-Man hanging upside down
std('spider-man-2002', ('grad', [(0, (230, 170, 80)), (.5, (180, 110, 40)), (1, (60, 30, 10))]), WHT,
    T('SPIDER-MAN', 'advb', 100, WHT, outline=((90, 40, 10), 2)),
    photo=ph(0.45, 0.4, 0.86, 0.85), pb=(200, 30, 30), lg=WHT, lw=.5, order='LPTCF', credit=['TOBEY MAGUIRE'], ccol=WHT,
    ft='a', vbox=(200, 30, 30), fcol=(250, 230, 210), fin=MINT, seed=2002)

# Spirit: Stallion of the Cimarron (2002): DreamWorks, a slipcase; the sky, SPIRIT typeset in a wide serif in white (parked for Ian's logo, see data/logos-wanted.md: the white letters sit on white cloud and the lift lost the T), the stallion running with the mare
std('spirit-stallion-of-the-cimarron-2002', ('grad', [(0, (60, 130, 210)), (.5, (110, 170, 230)), (1, (60, 110, 40))]), WHT,
    T('SPIRIT', 'pagb', 120, WHT, outline=((40, 80, 140), 1.8)),
    photo=ph(0.5, 0.55, 0.86, 0.85), pb=(200, 120, 50), lg=WHT, lw=.5, order='LPTSF', stick=PRC(['$1.99', 'FAMILY']),
    ft='c', fcol=(230, 240, 250), fin=MINT, seed=2002)

# Star Wars: Episode II – Attack of the Clones (2002): Lucasfilm, a slipcase; the poster's gold dusk, STAR WARS / EPISODE II and ATTACK OF THE CLONES typeset in a gold serif (parked for Ian's logo, see data/logos-wanted.md: the gold letters sit on a gold glow and both lifts lost the edge letters), Anakin and Padmé
std('star-wars-episode-ii-attack-of-the-clones-2002', ('grad', [(0, (150, 90, 30)), (.5, (60, 30, 10)), (1, (6, 2, 2))]), (240, 200, 120),
    [T('EPISODE II', 'pagb', 120, (240, 200, 120), outline=((40, 20, 6), 1.6)), T('ATTACK OF THE CLONES', 'pagb', 50, (240, 210, 150))], tgap=8,
    photo=ph(0.5, 0.33, 0.86, 0.85), pb=(240, 200, 120), lg=WHT, lw=.5, order='LPTSF', dotst=('SCI-FI', (240, 200, 120), (30, 14, 4)),
    ft='b', fcol=(230, 210, 180), fin=MINT, seed=2002)

# The Bourne Identity (2002): the poster's blue, THE BOURNE IDENTITY typeset in white capitals (parked for Ian's logo, see data/logos-wanted.md: THE sits over Matt Damon's shoulder and the lift lost it twice), Matt Damon with the pistol
std('the-bourne-identity-2002', ('grad', [(0, (40, 90, 140)), (.6, (12, 30, 50)), (1, (2, 6, 10))]), WHT,
    TT([('THE', WHT), ('BOURNE', WHT), ('IDENTITY', WHT)], 'herb', 100, sp=.3),
    photo=ph(0.62, 0.1, 0.5, 0.42), pb=(250, 170, 60), lg=WHT, lw=.5, order='LPTCF', credit=['MATT DAMON'], ccol=WHT,
    ft='d', fcol=(190, 206, 226), fin=MINT, seed=2002)

# The Lord of the Rings: The Two Towers (2002): a 2-tape box (179 minutes, the theatrical cut); the poster's pale gold, THE LORD OF THE RINGS typeset in a gold serif like the first's (parked with it for Ian's logo, see data/logos-wanted.md: the same gold-on-gold logo), the Fellowship before the two towers
std('the-lord-of-the-rings-the-two-towers-2002', ('grad', [(0, (150, 130, 90)), (.5, (70, 60, 36)), (1, (10, 8, 4))]), (236, 196, 110),
    T('THE LORD OF THE RINGS', 'pagb', 130, (236, 196, 110), outline=((40, 26, 10), 1.6)),
    photo=ph(0.6, 0.5, 0.6, 1.0), pb=(236, 196, 110), lg=WHT, lw=.5, order='LPTCSF', credit=['THE TWO TOWERS'], ccol=(236, 210, 160), stick=TWOST((236, 196, 110), (30, 24, 10)),
    ft='e', fcol=(220, 206, 180), fin=MINT, seed=2002, **TWO)

# The Pianist (2002): black, THE PIANIST typeset in heavy capitals in its gold (parked for Ian's logo, see data/logos-wanted.md: the gold letters are scuffed and the final T came out broken twice), the hands on the keys
std('the-pianist-2002', ('grad', [(0, (50, 40, 30)), (.6, (14, 10, 8)), (1, (2, 2, 2))]), (240, 190, 60),
    T('THE PIANIST', 'intbk', 110, (240, 190, 60)),
    photo=ph(0.5, 0.7, 0.9, 0.6), pb=(240, 190, 60), lg=WHT, lw=.5, order='LTPCF', credit=['A FILM BY', 'ROMAN POLANSKI'], ccol=(240, 210, 140),
    ft='a', fcol=(210, 200, 186), fin=MINT, seed=2002)

# The Sum of All Fears (2002): the poster's fire into black, THE SUM OF ALL FEARS typeset in heavy condensed capitals in its gold (parked for Ian's logo, see data/logos-wanted.md: the gold letters are textured with the fire behind them and the cut came out patchy), Ben Affleck and Morgan Freeman
std('the-sum-of-all-fears-2002', ('grad', [(0, (180, 60, 20)), (.5, (80, 20, 8)), (1, (4, 2, 2))]), (240, 180, 60),
    T('THE SUM OF ALL FEARS', 'intbk', 90, (240, 180, 60)),
    photo=ph(0.5, 0.35, 0.9, 0.75), pb=(240, 180, 60), lg=WHT, lw=.5, order='LPTF',
    ft='c', fcol=(230, 200, 180), fin=MINT, seed=2002)

# The Transporter (2002): the poster's white, THE TRANSPORTER typeset in heavy italic capitals in its orange (parked for Ian's logo, see data/logos-wanted.md: the letters are streaked into a motion blur of their own orange), Jason Statham mid-kick with the pistols (TF1 Films logo)
std('the-transporter-2002', ('grad', [(0, (246, 246, 246)), (.6, (228, 228, 228)), (1, (120, 120, 120))]), (240, 150, 30),
    T('THE TRANSPORTER', 'intbki', 90, (240, 150, 30), outline=((40, 20, 4), 1.6)),
    photo=ph(0.5, 0.25, 0.9, 0.6), pb=(240, 150, 30), lg=(30, 30, 30), lw=.55, order='LPTSF', stick=BAR('02 1011', top='ACTION', fill=(240, 236, 226)),
    ft='e', fcol=(30, 30, 30), fin=MINT, seed=2002)

# The Wild Thornberrys Movie (2002): Paramount (Nickelodeon), a slipcase; the canyon's sunset, THE WILD THORNBERRYS MOVIE typeset in heavy capitals in its green (parked for Ian's logo, see data/logos-wanted.md: the logo sits on a blue badge with a sun behind it and the cut took the wrong piece), Eliza on the elephant
std('the-wild-thornberrys-movie-2002', ('grad', [(0, (240, 150, 50)), (.5, (200, 80, 40)), (1, (60, 20, 10))]), (120, 200, 60),
    TT([('THE WILD', (250, 230, 120)), ('THORNBERRYS', (120, 200, 60)), ('MOVIE', (250, 230, 120))], 'popb', 90, sp=.3, outline=((40, 30, 10), 1.8)),
    photo=ph(0.5, 0.65, 0.86, 0.85), pb=(120, 200, 60), lg=WHT, lw=.5, order='LPTF',
    ft='b', fcol=(250, 230, 210), fin=MINT, seed=2002)

# Treasure Planet (2002): Disney clamshell; the nebula's blue and orange, the poster's gold Treasure Planet cut off it, Jim Hawkins's face in the diamond
disney('treasure-planet-2002', ('grad', [(0, (230, 130, 60)), (.5, (60, 90, 160)), (1, (10, 20, 60))]), fin=dict(CLAM, vivid=.2),
       title=LC([(0.35, 0.6, 0.98, 0.75)], 130, outline=((30, 20, 40), 1.6), cuts=[comp_cut(lambda a: (a[..., 0] > .6) & (a[..., 2] < .5) & (_lum(a) > .5), minf=.01)]),
       face=ph(.27, .52, .1, 1.4), lcol=WHT)

# 2 Fast 2 Furious (2003): the poster's black, 2 FAST 2 FURIOUS typeset in heavy italic capitals in white and blue (parked for Ian's logo, see data/logos-wanted.md: the chrome letters sit over the cars' lights and the cut came out in pieces), Paul Walker and Tyrese
std('2-fast-2-furious-2003', ('grad', [(0, (40, 60, 100)), (.6, (10, 16, 30)), (1, (2, 2, 6))]), WHT,
    TT([('2 FAST', WHT), ('2 FURIOUS', (90, 160, 240))], 'intbki', 100, sp=.3),
    photo=ph(0.5, 0.15, 0.9, 0.4), pb=(60, 140, 240), lg=WHT, lw=.5, order='LPTCF', credit=['PAUL WALKER', 'TYRESE GIBSON'], ccol=WHT,
    ft='a', vbox=(60, 140, 240), fcol=(200, 206, 230), fin=MINT, seed=2003)

# 21 Grams (2003): the poster's red and dark, 21 GRAMS typeset in heavy condensed capitals, 21 in red and GRAMS in gold (parked for Ian's logo, see data/logos-wanted.md: the huge red 21 runs behind the cast's strips and GRAMS is slanted over them), the cast in their strips
std('21-grams-2003', ('grad', [(0, (140, 30, 20)), (.5, (60, 14, 8)), (1, (6, 2, 2))]), (220, 30, 30),
    TT([('21', (220, 30, 30)), ('GRAMS', (240, 190, 80))], 'intbk', 120, sp=.3),
    photo=ph(0.7, 0.4, 0.5, 1.3), pb=(240, 190, 80), lg=WHT, lw=.5, order='LPTCF', credit=['AN ALEJANDRO', 'GONZÁLEZ IÑÁRRITU FILM'], ccol=WHT,
    ft='d', fcol=(220, 200, 190), fin=MINT, seed=2003)
