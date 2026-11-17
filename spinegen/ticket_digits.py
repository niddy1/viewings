"""How watched-2022.png and watched-2023.png were made from watched-2026.png, in the manner of
ticket_four.py: the lettering is straightened, each digit found as a connected component, and the 6 is
painted out and replaced.  2022: the ticket's own third digit (a 2) copied into the 6's place.
2023: a 3 built from that 2: its top half (top bar, chamfers, right stroke, the left hook cut short),
the same flipped upside down for the bottom half, the right stroke joined between them and a middle
bar as thick as the 2's bars.  Run: python3 spinegen/ticket_digits.py"""
import numpy as np, cv2
from PIL import Image
R = '/home/claude/viewings/'
src = np.array(Image.open(R + 'watched-2026.png').convert('RGBA')).astype(np.float32)
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
    return min(range(1, n), key=lambda i: (cen[i][0] - x * S) ** 2 + (cen[i][1] - y * S) ** 2)
i2 = comp_near(670, 300); i6 = comp_near(736, 296)
x, y, w, h = st[i2][:4]
two = np.where(lab[y:y + h, x:x + w] == i2, r[y:y + h, x:x + w], 0)
X6, Y6, W6, H6 = st[i6][:4]
print('2', (st[i2][:4] / S).round(1), '6', (st[i6][:4] / S).round(1))

def three_from(g):
    h, w = g.shape
    # thickness of the top bar, measured down the middle column
    col = g[:, w // 2] > .5
    bar = int(np.argmax(~col[np.argmax(col):]))
    # right stroke: the columns lit at 30% height on the right half
    row = g[int(h * .3)] > .5
    rs = int(np.where(~row[: w][::-1][: w // 2] == False)[0][0]) if row[-1] else 0
    lit = np.where(row)[0]; rx0 = lit[lit > w // 2].min()
    k = int(h * .33)
    out = np.zeros_like(g)
    top = g[:k].copy()
    top[int(h * .22):, :w // 2] = 0                                        # shorten the 2's left hook
    g = np.vstack([top, g[k:]])
    out[:k] = g[:k]
    out[h - k:] = np.maximum(out[h - k:], g[:k][::-1])
    out[k:h - k, rx0:] = np.maximum(out[k:h - k, rx0:], g[k - 1:k, rx0:])   # join the right stroke
    m0 = h // 2 - bar // 2
    out[m0:m0 + bar, int(w * .28):rx0 + 1] = 1                              # middle bar
    return np.clip((cv2.GaussianBlur(out, (0, 0), .45 * S) - .5) * 3 + .5, 0, 1), bar

def make(digit, year):
    h, w = digit.shape
    place = np.zeros_like(r)
    ox = X6 + (W6 - w) // 2; oy = Y6 + (H6 - h) // 2
    place[oy:oy + h, ox:ox + w] = digit
    kl = cv2.dilate((place > .5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(2.6 * S) | 1,) * 2)).astype(np.float32)
    kl = cv2.GaussianBlur(kl, (0, 0), .5 * S)
    clr = np.zeros_like(r); clr[Y6 - 4 * S:Y6 + H6 + 4 * S, X6 - 4 * S:X6 + W6 + 4 * S] = 1
    clr = cv2.GaussianBlur(clr, (0, 0), .6 * S)
    back = [cv2.resize(rot(a, -ANG), (W, H), interpolation=cv2.INTER_AREA)[..., None] for a in (clr, kl, place)]
    rgb = src[..., :3]
    rgb = rgb * (1 - back[0]) + B * back[0]
    rgb = rgb * (1 - back[1]) + K * back[1]
    rgb = rgb * (1 - back[2]) + Y * back[2]
    out = src.copy(); out[..., :3] = rgb
    o = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')
    o.save(R + f'watched-{year}.png', optimize=True)
    x0, y0, x1, y1 = 505, 225, 790, 355
    o.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 3, (y1 - y0) * 3), Image.NEAREST).save(f'/tmp/ticket-{year}-check.png')

make(two, 2022)
three, bar = three_from(two)
print('bar', bar / S)
make(three, 2023)
