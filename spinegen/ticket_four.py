"""How watched-2024.png was made: a 4 built from the ticket's own 0 (its right stroke, the top half of its
left stroke, a crossbar as thick as its bars, open top) and put where the 6 is on watched-2026.png.
Kept as a pattern for other digits.  Run: python3 spinegen/ticket_four.py (writes watched-2024.png)."""
import numpy as np, cv2
from PIL import Image
src = np.array(Image.open('/home/claude/viewings/watched-2026.png').convert('RGBA')).astype(np.float32)
H, W = src.shape[:2]
Y = np.array([241, 194, 5.]); B = np.array([35, 59, 172.]); K = np.array([45, 53, 105.])
t = np.clip(((src[..., :3] - B) @ (Y - B)) / ((Y - B) @ (Y - B)), 0, 1)
S = 4; ANG = -4.5
big = cv2.resize(t, (W * S, H * S), interpolation=cv2.INTER_CUBIC)
cx, cy = 670 * S, 300 * S
def rot(a, ang):
    M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    return cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), flags=cv2.INTER_CUBIC)
r = rot(big, ANG)
m = (r > .5).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(m)
def comp_near(x, y):
    i = min(range(1, n), key=lambda i: (cen[i][0] - x * S) ** 2 + (cen[i][1] - y * S) ** 2)
    return i, st[i]
i0, s0 = comp_near(606, 300); i6, s6 = comp_near(736, 296)
x, y, w, h = s0[:4]
g = np.where(lab[y:y + h, x:x + w] == i0, r[y:y + h, x:x + w], 0)   # the 0, alone
X6, Y6, W6, H6 = s6[:4]
print('0', (s0[:4] / S).round(1), '6', (s6[:4] / S).round(1))
# counter of the 0
inner = (g < .5).astype(np.uint8)
nn, ll, ss, _ = cv2.connectedComponentsWithStats(inner)
cands = [k for k in range(1, nn) if ss[k, 0] > 0 and ss[k, 1] > 0 and ss[k, 0] + ss[k, 2] < w and ss[k, 1] + ss[k, 3] < h]
k = max(cands, key=lambda k: ss[k, 4]); hx, hy, hw, hh = ss[k, :4]
bar = max(hy, h - (hy + hh))
print('counter', hx / S, hy / S, hw / S, hh / S, 'bar', bar / S)
four = np.zeros_like(g)
four[:, hx + hw:] = g[:, hx + hw:]          # right stroke, full height
c0 = int(h * .58); c1 = c0 + bar             # crossbar
four[:c1, :hx] = g[:c1, :hx]                 # left stroke, top to the crossbar's foot
four[c0:c1, :] = np.maximum(four[c0:c1, :], (g[c0:c1, :].max(axis=0) > .5).astype(np.float32)[None, :] * 0 + 1)
four[:hy, hx:hx + hw] = 0                    # open top
four = np.clip((cv2.GaussianBlur(four, (0, 0), .45 * S) - .5) * 3 + .5, 0, 1)
# put it where the 6 was: centred on the 6's box, same height
cy_ = np.zeros_like(r)
ox = X6 + (W6 - w) // 2; oy = Y6 + (H6 - h) // 2
cy_[oy:oy + h, ox:ox + w] = four
kl = cv2.dilate((cy_ > .5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(2.6 * S) | 1,) * 2)).astype(np.float32)
kl = cv2.GaussianBlur(kl, (0, 0), .5 * S)
clr = np.zeros_like(r); clr[Y6 - 4 * S:Y6 + H6 + 4 * S, X6 - 4 * S:X6 + W6 + 4 * S] = 1
clr = cv2.GaussianBlur(clr, (0, 0), .6 * S)
back = [cv2.resize(rot(a, -ANG), (W, H), interpolation=cv2.INTER_AREA)[..., None] for a in (clr, kl, cy_)]
rgb = src[..., :3]
rgb = rgb * (1 - back[0]) + B * back[0]
rgb = rgb * (1 - back[1]) + K * back[1]
rgb = rgb * (1 - back[2]) + Y * back[2]
out = src.copy(); out[..., :3] = rgb
o = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')
o.save('/home/claude/viewings/watched-2024.png', optimize=True)
x0, y0, x1, y1 = 505, 225, 790, 355
o.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 3, (y1 - y0) * 3), Image.NEAREST).save('/tmp/ticket-digit-check.png')  # zoomed check
