# The Vault: films from the bulk-rated years (2007-2015), one shelf per decade of release (vault-<decade>.json).
# Run through tapes.py (exec'd at its end, same namespace): python3 spinegen/tapes.py <id> ...
# Made like the 2016-2025 shelves: lettering measured off each poster and lifted or cut in its own colours
# (each spec's comment says where and why a title is typeset), a poster crop picked for each film, credits and
# typed labels read from IMDb (JSON-LD director/actor, company credits for films with no logo file), and the
# layouts, stickers, picture shapes and foot styles mixed to the 2026 targets (see CLAUDE.md).

def comp_cut(test, keep=None, top=None, soft=1.4):
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
        return rgb, _soft(ok[lab].astype(np.float32), soft)
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
