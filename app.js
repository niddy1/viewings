(() => {
  'use strict';

  // Spine-title fonts, chosen by genre. Override any film with a "font" field in films.json.
  const GENRE_FONTS = {
    'Horror': ['Creepster', 'Pirata One'],
    'Science Fiction': ['Orbitron', 'Monoton'],
    'Comedy': ['Righteous', 'Bungee', 'Permanent Marker'],
    'Drama': ['Playfair Display', 'Abril Fatface'],
    'Action': ['Anton', 'Bebas Neue'],
    'Thriller': ['Oswald', 'Special Elite'],
    'Crime': ['Special Elite', 'Oswald'],
    'Romance': ['Abril Fatface', 'Playfair Display'],
    'Animation': ['Bungee', 'Righteous'],
    'War': ['Cinzel'],
    'History': ['Cinzel'],
    'Fantasy': ['Cinzel', 'Pirata One'],
    'Western': ['Rye'],
    'Documentary': ['Oswald'],
    'Music': ['Monoton', 'Rubik Mono One'],
  };
  const DEFAULT_FONTS = ['Bebas Neue', 'Anton', 'Oswald', 'Playfair Display'];

  const $ = (id) => document.getElementById(id);
  const shelves = $('shelves');
  let films = [];
  let spineEls = [];
  let current = -1;

  const hash = (s) => { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };

  function pickFont(f) {
    if (f.font) return f.font;
    for (const g of f.genres || []) {
      if (GENRE_FONTS[g]) { const l = GENRE_FONTS[g]; return l[hash(f.title) % l.length]; }
    }
    return DEFAULT_FONTS[hash(f.title) % DEFAULT_FONTS.length];
  }

  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    let h = 0, s = 0;
    if (max !== min) {
      const d = max - min;
      s = l > .5 ? d / (2 - max - min) : d / (max + min);
      h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h *= 60;
    }
    return [h, s, l];
  }

  const SPINE_H = 250;      // every tape is the same height
  const BOTTOM_ZONE = 40;   // VHS badge + sleeve notch
  // What sits above the title: the studio logo, a framed crop of the poster, a rental sticker, a
  // "A FILM BY" credit, or nothing (chosen per film in prepare()).
  const logoZone = (f) => ({ logo: 40, panel: 12 + (f._w - 10) + 9, sticker: 50, tag: 32 }[f._top] || 12);

  const loadImg = (src) => new Promise((resolve) => {
    if (!src) return resolve(null);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const lum = (r, g, b) => 0.299 * r + 0.587 * g + 0.114 * b;
  const rgbCss = (c) => `rgb(${c.map((v) => Math.round(v)).join(',')})`;
  function hslToRgb(h, s, l) {
    h = ((h % 360) + 360) % 360 / 360;
    const q = l < .5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    const f = (t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < .5 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
    return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255];
  }
  // Browns, tans and olives: the muddy tones we never want on a spine.
  const isMuddy = (h, s, l) => h >= 10 && h <= 75 && (s < 0.7 || l < 0.5);

  // Which colours does the poster actually use? Hue buckets weighted by how vivid they are.
  function posterPalette(img) {
    if (!img) return null;
    try {
      const gw = 24, gh = 36;
      const c = document.createElement('canvas'); c.width = gw; c.height = gh;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0, gw, gh);
      const d = x.getImageData(0, 0, gw, gh).data;
      const buckets = Array.from({ length: 12 }, () => ({ w: 0, s: 0, l: 0 }));
      let L = 0, N = 0;
      for (let i = 0; i < d.length; i += 4) {
        const [h, s, l] = rgbToHsl(d[i], d[i + 1], d[i + 2]); L += l; N++;
        if (s > .25 && l > .12 && l < .88) {
          const b = buckets[Math.floor(h / 30) % 12], w = s * Math.sqrt(1 - Math.abs(2 * l - 1));
          b.w += w; b.s += s * w; b.l += l * w;
        }
      }
      return { buckets, avgL: L / N, N };
    } catch { return null; }
  }

  // Pick a spine colour. `need` is 'dark' when the lettering is light (most tapes) or 'light'
  // when the lettering is dark. Black and charcoal are common on real shelves, so they come up often.
  function chooseSpine(pal, f, need) {
    const hh = hash(f.title);
    let best = null;
    if (pal) pal.buckets.forEach((b, i) => {
      if (!b.w) return;
      const h = i * 30 + 15, s = b.s / b.w, l = b.l / b.w;
      if (isMuddy(h, s, l)) return;
      if (!best || b.w > best.w) best = { w: b.w, h, s, l };
    });
    const colorful = best && best.w / pal.N > 0.035;
    if (need === 'light') return colorful ? hslToRgb(best.h, .35, .86) : hslToRgb(42, .18, .92);
    if (!colorful || hh % 4 === 0) return hslToRgb(best ? best.h : 220, .14, (5 + hh % 6) / 100);
    if (best.h >= 10 && best.h <= 75) return hslToRgb(best.h, .1, (5 + hh % 6) / 100); // dark orange/gold just reads as brown
    return hslToRgb(best.h, clamp(best.s, .5, .88), clamp(best.l * .55, .16, .3));
  }

  const borderStats = (px, w, h) => {
    const t = Math.max(1, Math.round(Math.min(w, h) * .08)), pts = [];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (x < t || y < t || x >= w - t || y >= h - t) { const k = (y * w + x) * 4; pts.push([px[k], px[k + 1], px[k + 2]]); }
    const med = [0, 1, 2].map((ch) => pts.map((p) => p[ch]).sort((a, b) => a - b)[pts.length >> 1]);
    const near = pts.filter((p) => Math.hypot(p[0] - med[0], p[1] - med[1], p[2] - med[2]) < 45);
    const bg = [0, 1, 2].map((ch) => near.reduce((a, p) => a + p[ch], 0) / (near.length || 1));
    const flat = pts.filter((p) => Math.hypot(p[0] - bg[0], p[1] - bg[1], p[2] - bg[2]) < 28).length / pts.length;
    const mean = [0, 1, 2].map((ch) => pts.reduce((a, p) => a + p[ch], 0) / pts.length);
    return { bg, flat, mean, lb: lum(...med) };
  };

  // Lift the title lettering off the poster, turn it so it reads down the spine, and fit it to the
  // space. The lettering is separated from its background (colour-keyed on flat backgrounds, by
  // light/dark on busy ones) so it sits straight on the spine colour with no pasted rectangle.
  function titleArt(f, img, W, H, pal) {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const crops = f.titleBox.map(([x0, y0, x1, y1]) => {
      const pw = (x1 - x0) * iw * 0.04, ph = (y1 - y0) * ih * 0.1;
      const sx = Math.max(0, x0 * iw - pw), sy = Math.max(0, y0 * ih - ph);
      return { sx, sy, sw: Math.min(iw, x1 * iw + pw) - sx, sh: Math.min(ih, y1 * ih + ph) - sy };
    });
    const GAP = 1;
    const sumH = crops.reduce((a, c) => a + c.sh, 0);
    const maxL = Math.max(...crops.map((c) => c.sw));
    const s = Math.min(H / maxL, (W - GAP * (crops.length - 1)) / sumH);
    const totalW = sumH * s + GAP * (crops.length - 1);

    // 1. each crop, upright, at its final pixel size
    const parts = crops.map((c) => {
      const w = Math.max(4, Math.round(c.sw * s * dpr)), h = Math.max(4, Math.round(c.sh * s * dpr));
      const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      const x = cv.getContext('2d'); x.imageSmoothingQuality = 'high';
      x.drawImage(img, c.sx, c.sy, c.sw, c.sh, 0, 0, w, h);
      const id = x.getImageData(0, 0, w, h), st = borderStats(id.data, w, h);
      return { cv, x, id, w, h, ...st, c };
    });

    // 2. decide how to separate lettering from background, per crop
    let ok = true;
    parts.forEach((p) => {
      const d = p.id.data, n = p.w * p.h, a = new Float32Array(n);
      let cov = 0, up = 0, down = 0;
      if (p.flat >= .72) {
        p.mode = 'flat';
        for (let i = 0; i < n; i++) {
          const dist = Math.hypot(d[i * 4] - p.bg[0], d[i * 4 + 1] - p.bg[1], d[i * 4 + 2] - p.bg[2]);
          a[i] = smooth(22, 64, dist); cov += a[i];
          if (a[i] > .6) lum(d[i * 4], d[i * 4 + 1], d[i * 4 + 2]) > lum(...p.bg) ? up++ : down++;
        }
      } else {
        p.mode = 'busy';
        for (let i = 0; i < n; i++) { const dl = lum(d[i * 4], d[i * 4 + 1], d[i * 4 + 2]) - p.lb; if (dl > 0) up += dl > 40 ? 1 : 0; else down += dl < -40 ? 1 : 0; }
        p.pol = up >= down ? 1 : -1;
        // raise the bar until only the strongest contrast (the lettering) is left
        for (const t of [26, 45, 65, 85, 105, 125]) {
          cov = 0;
          for (let i = 0; i < n; i++) { a[i] = smooth(t, t + 44, p.pol * (lum(d[i * 4], d[i * 4 + 1], d[i * 4 + 2]) - p.lb)); cov += a[i]; }
          if (cov / n <= .45) break;
        }
      }
      p.a = a; p.cov = cov / n; p.lighter = p.mode === 'flat' ? up >= down : p.pol > 0;
      if (p.cov < .02 || p.cov > .62) ok = false;
    });

    // 3. spine colour
    const lighter = parts.reduce((a, p) => a + (p.lighter ? p.cov : -p.cov), 0) >= 0;
    let rgb, mode;
    if (ok) {
      mode = 'key';
      const flatAll = parts.every((p) => p.mode === 'flat');
      const bgm = [0, 1, 2].map((ch) => parts.reduce((a, p) => a + p.bg[ch], 0) / parts.length);
      const [bh, bs, bl] = rgbToHsl(...bgm);
      rgb = f.color ? null : flatAll && !isMuddy(bh * 1, bs, bl) ? bgm : chooseSpine(pal, f, lighter ? 'dark' : 'light');
    } else { // can't separate it cleanly: feather the crop into a spine colour matching its surroundings
      mode = 'blend';
      rgb = [0, 1, 2].map((ch) => parts.reduce((a, p) => a + p.mean[ch], 0) / parts.length);
      const [mh, ms, ml] = rgbToHsl(...rgb);
      if (isMuddy(mh, ms, ml)) rgb = chooseSpine(pal, f, ml > .6 ? 'light' : 'dark');
    }

    // 4. composite, rotated 90 degrees clockwise, first line on the right
    const cv = document.createElement('canvas');
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);
    let right = (W + totalW) / 2;
    parts.forEach((p) => {
      const d = p.id.data, n = p.w * p.h;
      if (mode === 'key') {
        for (let i = 0; i < n; i++) {
          const a = p.a[i];
          if (p.mode === 'flat' && a > .02 && a < 1) for (let ch = 0; ch < 3; ch++) d[i * 4 + ch] = clamp(p.bg[ch] + (d[i * 4 + ch] - p.bg[ch]) / a, 0, 255);
          d[i * 4 + 3] = Math.round(a * 255);
        }
      } else {
        const ramp = Math.max(3, Math.round(p.h * .22));
        for (let y = 0; y < p.h; y++) for (let x = 0; x < p.w; x++) {
          const e = Math.min(x, y, p.w - 1 - x, p.h - 1 - y);
          d[(y * p.w + x) * 4 + 3] = Math.round(smooth(0, ramp, e) * 255);
        }
      }
      p.x.putImageData(p.id, 0, 0);
      ctx.save();
      ctx.translate(right, (H - p.c.sw * s) / 2);
      ctx.rotate(Math.PI / 2);
      ctx.drawImage(p.cv, 0, 0, p.c.sw * s, p.c.sh * s);
      ctx.restore();
      right -= p.c.sh * s + GAP;
    });
    return { cv, rgb, lighter };
  }

  async function prepare(f) {
    const img = await loadImg(f.poster);
    const pal = posterPalette(img);
    f._font = pickFont(f);
    const rt = f.runtime || (90 + hash(f.title) % 60);
    f._w = Math.round(Math.min(52, Math.max(42, 40 + (rt - 90) * 0.12)));
    // Wear: nearly every tape has some (about 1 in 25 is pristine), from a light scuff to badly battered.
    const r = hash(f.title + 'wear');
    f._r = r;
    f._h = SPINE_H - ((r >>> 5) % 5 === 0 ? 0 : (r >>> 8) % 5); // most sit a few px short of the tallest
    f._dmg = [];
    if ((r >> 11) % 6 === 0) f._dmg.push('sticker');
    if ((r >> 14) % 5 === 0) f._dmg.push('fade');
    f._sev = r % 25 === 0 ? 0 : 0.12 + 0.88 * Math.pow(((r >> 9) % 1000) / 1000, 1.6);
    const tbs = Array.isArray(f.titleBox) ? f.titleBox : [];
    f._top = f.logo ? 'logo'
      : img && tbs.length && f.title.length <= 14 && (r >>> 3) % 3 === 0 ? 'panel'
      : f._dmg.includes('sticker') ? 'sticker'
      : f.director && (r >>> 6) % 2 === 0 ? 'tag' : '';
    if (f._top !== 'sticker') f._dmg = f._dmg.filter((d) => d !== 'sticker');
    f._lab = (r >>> 17) % 13 === 0 ? 'lib' : (r >>> 20) % 17 === 0 ? 'rewind' : '';
    f._photo = f._top === 'panel' ? photoCrop(f, img) : null;
    f._art = null;
    let rgb = null;
    if (img && Array.isArray(f.titleBox) && f.titleBox.length) {
      const W = f._w - 4, H = f._h - logoZone(f) - BOTTOM_ZONE - 6;
      f._art = titleArt(f, img, W, H, pal);
      rgb = f._art.rgb;
    }
    if (!rgb) rgb = chooseSpine(pal, f, 'dark');
    if (f.color) {
      f._c = f.color;
      try { const t = document.createElement('canvas').getContext('2d'); t.fillStyle = f.color; const h = t.fillStyle; rgb = h[0] === '#' ? [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) : (h.match(/\d+/g) || [30, 30, 30]).slice(0, 3).map(Number); } catch { rgb = [30, 30, 30]; }
    } else f._c = rgbCss(rgb);
    f._rgb = rgb;
    f._t = lum(...rgb) > 150 ? '#2a2118' : '#efe6d2'; // ink for the badge and any plain-text title
  }

  // A square crop of the poster (away from its lettering) for the framed picture some spines carry up top.
  function photoCrop(f, img) {
    const iw = img.naturalWidth, ih = img.naturalHeight, side = iw * .66, pw = f._w - 10;
    const boxes = (f.titleBox || []).map((b) => [b[1] * ih, b[3] * ih]);
    let best = null;
    for (let c = .24; c <= .64; c += .02) {
      const y0 = clamp(c * ih - side / 2, 0, ih - side), y1 = y0 + side;
      const over = boxes.reduce((a, [t, u]) => a + Math.max(0, Math.min(y1, u) - Math.max(y0, t)), 0);
      const score = over + Math.abs(c - .38) * ih * .3;
      if (!best || score < best.score) best = { score, y0 };
    }
    const dpr = Math.min(window.devicePixelRatio || 1, 3), cv = document.createElement('canvas');
    cv.width = cv.height = Math.round(pw * dpr);
    const x = cv.getContext('2d');
    x.drawImage(img, (iw - side) / 2, best.y0, side, side, 0, 0, cv.width, cv.height);
    const g = x.createRadialGradient(cv.width / 2, cv.height / 2, cv.width * .25, cv.width / 2, cv.height / 2, cv.width * .75);
    g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(20,10,0,.45)');
    x.fillStyle = g; x.fillRect(0, 0, cv.width, cv.height);
    return cv;
  }

  // Procedural wear, drawn per tape from a seeded RNG: white cardboard showing through at the
  // frayed top, abraded edges, scuffs and hard creases. Nothing is cut away from the spine.
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  function wearCanvas(f) {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const W = f._w, H = f._h, PAD = 5, sev = f._sev, R = rng(f._r);
    const rr = (a, b) => a + R() * (b - a);
    const L = (lo, hi) => lo + (hi - lo) * sev;   // scale a quantity with severity
    const chance = (p) => R() < p;
    const cv = document.createElement('canvas');
    cv.width = Math.round(W * dpr); cv.height = Math.round((H + PAD) * dpr);
    cv.className = 'wear';
    cv.style.cssText = `width:${W}px;height:${H + PAD}px;top:${-PAD}px`;
    const x = cv.getContext('2d'); x.scale(dpr, dpr);
    const y0 = PAD, yb = PAD + H; // the spine's real top and bottom edges
    const SHELF = '#0b0805', [sr, sg, sb] = f._rgb, pale = lum(sr, sg, sb) > 165;

    // Real wear is mostly dry-brush scuffing: the print rubbed to a pale, fibrous dust along the edges that
    // fades inward, then hairline scratches and creases, and only at the worst a chip of grey board showing.
    // It is never a clean cream shape. Excellent copies (about 1 in 25) get nothing but the soft top highlight.
    const dust = (a) => (pale ? `rgba(${140 + R() * 24 | 0},${136 + R() * 22 | 0},${126 + R() * 22 | 0},${a})` : `rgba(${222 + R() * 28 | 0},${218 + R() * 26 | 0},${206 + R() * 28 | 0},${a})`);
    const board = (a) => `rgba(${186 + R() * 26 | 0},${180 + R() * 24 | 0},${164 + R() * 26 | 0},${a})`;
    const dark = (a) => `rgba(8,6,4,${a})`;

    const gr = x.createLinearGradient(0, y0, 0, y0 + 4.5);
    gr.addColorStop(0, 'rgba(255,255,255,.22)'); gr.addColorStop(.5, 'rgba(255,255,255,.07)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gr; x.fillRect(0, y0, W, 4.5);
    [0, 1].forEach((side) => { // slightly rounded top corners
      const r = rr(.9, 1.9), cx = side ? W : 0, dir = side ? -1 : 1;
      x.fillStyle = SHELF; x.beginPath(); x.moveTo(cx, y0); x.lineTo(cx + dir * r, y0); x.quadraticCurveTo(cx, y0, cx, y0 + r); x.closePath(); x.fill();
    });
    if (!sev) return cv;

    const tier = sev < .3 ? 0 : sev < .62 ? 1 : 2; // light, medium, heavy

    // --- primitives -------------------------------------------------------------------------------
    // Dry-brush streaks along one edge, densest at the edge and fading inward. `k` scales the amount.
    const brush = (edge, depth, n, k) => {
      for (let i = 0, m = n * k | 0; i < m; i++) {
        const d = depth * Math.pow(R(), 2.1), fade = 1 - d / depth * .55, a = rr(.2, .75) * fade;
        const along = (edge === 't' || edge === 'b') ? (chance(.5) ? rr(0, W) : chance(.5) ? rr(0, W * .22) : rr(W * .78, W)) : (chance(.55) ? rr(0, H * .25) : chance(.5) ? rr(H * .75, H) : rr(0, H));
        const len = rr(1.5, 9), th = rr(.5, 1.1);
        x.fillStyle = dust(a);
        if (edge === 't') x.fillRect(along, y0 + d, len, th);
        else if (edge === 'b') x.fillRect(along, yb - d - th, len, th);
        else if (edge === 'l') { if (chance(.6)) x.fillRect(d, y0 + along, th, len); else x.fillRect(d, y0 + along, rr(1, 3.5), .6); }
        else { if (chance(.6)) x.fillRect(W - d - th, y0 + along, th, len); else x.fillRect(W - d - rr(1, 3.5), y0 + along, rr(1, 3.5), .6); }
      }
    };
    // A hairline scratch or crease: a thin pale line (with a faint shadow beside it for creases).
    const hair = (px, py, ang, len, a, bend, shadow) => {
      const ex = px + Math.sin(ang) * len, ey = py + Math.cos(ang) * len;
      const cx = (px + ex) / 2 + Math.cos(ang) * bend, cy = (py + ey) / 2 - Math.sin(ang) * bend;
      if (shadow) { x.strokeStyle = dark(shadow); x.lineWidth = .7; x.beginPath(); x.moveTo(px + .8, py); x.quadraticCurveTo(cx + .8, cy, ex + .8, ey); x.stroke(); }
      x.strokeStyle = dust(a); x.lineWidth = rr(.4, .8); x.beginPath(); x.moveTo(px, py); x.quadraticCurveTo(cx, cy, ex, ey); x.stroke();
    };
    // A ragged chip of grey board where a corner has been knocked through, with dust thrown off round it.
    const chip = (cx, cy, size, sx, sy) => {
      x.beginPath();
      const n = 7;
      for (let i = 0; i <= n; i++) {
        const t = i / n * Math.PI / 2, rad = size * rr(.55, 1.15);
        const px = cx + sx * Math.cos(t) * rad, py = cy + sy * Math.sin(t) * rad;
        i ? x.lineTo(px, py) : x.moveTo(px, py);
      }
      x.lineTo(cx, cy); x.closePath();
      x.fillStyle = board(rr(.75, .95)); x.fill();
      for (let i = 0, m = size * 3 | 0; i < m; i++) { // fibres and flecks around the break
        const t = R() * Math.PI / 2, rad = size * rr(.6, 1.9);
        x.fillStyle = chance(.5) ? board(rr(.4, .8)) : dust(rr(.3, .7));
        x.fillRect(cx + sx * Math.cos(t) * rad, cy + sy * Math.sin(t) * rad, rr(.5, 1.5), rr(.5, 1.3));
      }
    };
    // The flap's edge along the very top: a thin strip of pale board with a ragged lower edge.
    const strip = () => {
      const th0 = rr(1.1, 1.9) + sev * 1.1, tilt = rr(-.5, .5);
      let h = th0, gap = 0;
      for (let px = 0; px < W; px += 1) {
        if (gap > 0) { gap--; continue; }
        if (chance(.04 + .06 * (1 - sev))) { gap = rr(2, 8) | 0; continue; }
        h = clamp(h + rr(-.4, .4), .5, th0 * 1.9);
        x.fillStyle = board(rr(.7, .98)); x.fillRect(px, y0 - .3 + tilt * (px / W), 1.1, h);
        if (chance(.12)) { x.fillStyle = board(rr(.4, .7)); x.fillRect(px, y0 + h - .3, rr(.6, 1.2), rr(.8, 2.2)); } // a frayed hair hanging below
      }
      x.fillStyle = dark(L(.18, .4)); for (let px = 0; px < W; px += 1) if (chance(.7)) x.fillRect(px, y0 + th0 + 1.1, 1.1, .8); // the shadow under it
    };

    // --- each tape rolls its own mix, so no two read alike -------------------------------------------
    const amt = { t: chance(.82) ? rr(.6, 1.3) : rr(0, .3), b: chance(.7) ? rr(.5, 1.2) : rr(0, .3), l: chance(.65) ? rr(.4, 1.2) : rr(0, .3), r: chance(.65) ? rr(.4, 1.2) : rr(0, .3) };
    if (tier === 0) { amt.t *= .8; amt.l *= .5; amt.r *= .5; }
    const density = L(26, 210);
    brush('t', L(2.5, 7), density * 1.2, amt.t);
    brush('b', L(2.5, 8), density * .9, amt.b);
    brush('l', L(1.8, 6), density * .8, amt.l);
    brush('r', L(1.8, 6), density * .8, amt.r);
    // frosted rim: the print worn a shade paler along the sides
    [0, 1].forEach((side) => {
      if (!chance(.35 + sev * .5)) return;
      const g = x.createLinearGradient(side ? W : 0, 0, side ? W - 3 : 3, 0);
      g.addColorStop(0, dust(L(.1, .3))); g.addColorStop(1, 'rgba(255,255,255,0)');
      x.fillStyle = g; x.fillRect(side ? W - 3 : 0, y0 + rr(0, H * .2), 3, rr(H * .4, H * .8));
    });

    if (chance([.12, .58, .92][tier])) strip();                       // the flap's pale edge
    [[0, 1, 1], [1, -1, 1]].forEach(([side, sx]) => {                 // top corners
      const p = [0, .35, .85][tier];
      if (chance(p)) chip(side ? W : 0, y0, rr(2, L(3, 8)), sx, 1);
    });
    [[0, 1], [1, -1]].forEach(([side, sx]) => {                       // bottom corners
      if (tier && chance([0, .2, .6][tier])) chip(side ? W : 0, yb, rr(2.5, L(3, 8)), sx, -1);
    });

    // scratches: a few short ones on most tapes, many on worn ones, plus long curved creases on the worst
    for (let i = 0, n = L(0, 12) * rr(.5, 1.3) | 0; i < n; i++) {
      hair(rr(1, W - 1), y0 + rr(4, H - 14), rr(-.4, .4) + (chance(.2) ? rr(-1, 1) : 0), rr(6, L(14, 42)), rr(.15, .5), rr(-2, 2), 0);
    }
    if (tier === 2 || (tier === 1 && chance(.3))) {
      for (let i = 0, n = tier === 2 ? 1 + (chance(.6) ? 1 : 0) + (chance(.3) ? 1 : 0) : 1; i < n; i++) {
        hair(rr(-2, W * .6), y0 + rr(H * .1, H * .7), rr(-.9, .9) * (chance(.5) ? 1 : .35), rr(40, 120) * (tier === 2 ? 1 : .5), rr(.3, .55), rr(-7, 7), rr(.18, .32));
      }
    }
    // scuffed flecks scattered over the face, thicker toward the sides
    for (let i = 0, n = L(8, 90) * rr(.5, 1.3) | 0; i < n; i++) {
      const px = chance(.55) ? (chance(.5) ? rr(0, W * .2) : rr(W * .8, W)) : rr(0, W);
      x.fillStyle = dust(rr(.25, .65)); x.fillRect(px, y0 + (chance(.5) ? rr(0, H * .35) : rr(0, H)), rr(.5, 1.3), rr(.5, 1.3));
    }

    // Bottom: the arch cut-out takes the most punishment. Dust fanned out round its rim, hairline cracks
    // climbing from it, and the bottom edge fraying into board on the worst copies.
    if (chance(.5 + sev * .45)) {
      const cx = W / 2, rim = 7;
      for (let i = 0, n = L(8, 44) | 0; i < n; i++) {
        const a = Math.PI + R() * Math.PI, rad = rim + Math.pow(R(), 1.8) * 9;
        x.fillStyle = dust(rr(.3, .75)); x.fillRect(cx + Math.cos(a) * rad, yb + Math.sin(a) * rad, rr(.6, 1.8), rr(.6, 1.5));
      }
      x.lineCap = 'round';
      for (let a0 = Math.PI; a0 < 2 * Math.PI; a0 += rr(.3, .7)) {
        if (!chance(.3 + sev * .5)) continue;
        x.strokeStyle = dust(rr(.35, .75)); x.lineWidth = rr(.6, L(.8, 1.6));
        x.beginPath(); x.arc(cx, yb, rim + rr(0, 1.2), a0, a0 + rr(.2, .5)); x.stroke();
      }
      x.lineCap = 'butt';
      for (let i = 0, n = L(0, 3.2) | 0; i < n; i++) hair(cx + rr(-6, 6), yb - rim, Math.PI + rr(-.25, .25), rr(6, L(8, 20)), rr(.35, .7), rr(-1.2, 1.2), 0);
      if (tier === 2 && chance(.55)) {
        for (let px = 0; px < W; px += rr(1.2, 2.6)) {
          if (Math.abs(px - cx) < rim - 1) continue;
          if (chance(.55)) { x.fillStyle = board(rr(.5, .9)); x.fillRect(px, yb - rr(.4, 2.6), rr(.8, 2), 4); }
        }
      }
    }
    return cv;
  }

  const STICKER_WORDS = { Horror: 'HORROR', 'Science Fiction': 'SCI-FI', Comedy: 'COMEDY', Action: 'ACTION', Thriller: 'THRILLER', Drama: 'DRAMA', Crime: 'CRIME', Romance: 'ROMANCE', Animation: 'FAMILY', Documentary: 'DOC' };

  function spineEl(f, i) {
    const b = document.createElement('button');
    b.className = 'spine ' + f._dmg.map((d) => 'dmg-' + d).join(' ');
    b.type = 'button';
    b.setAttribute('aria-label', `${f.title} (${f.year})`);
    const top = logoZone(f);
    const fs = Math.max(11, Math.min(f._w * 0.55, (f._h - top - BOTTOM_ZONE - 8) / (f.title.length * 0.6)));
    const r = f._r;
    b.style.cssText = `--w:${f._w}px;--h:${f._h}px;--c:${f._c};--t:${f._t};--f:'${f._font}';--fs:${fs.toFixed(1)}px;--top:${top}px;--bot:${BOTTOM_ZONE}px;`
      + `--cy:${15 + r % 70}%;--cx:${20 + (r >> 4) % 60}%;--flip:${(r >> 9) % 2 ? 1 : -1};--cut:${5 + r % 6}px`;
    if (f.logo) {
      const lg = document.createElement('img');
      lg.className = 'logo'; lg.src = f.logo; lg.alt = f.studio || ''; lg.loading = 'lazy';
      lg.onerror = () => lg.remove();
      b.append(lg);
    }
    if (f._art) {
      f._art.cv.className = 'art';
      f._art.cv.style.cssText = `width:${f._w - 4}px;height:${f._h - top - BOTTOM_ZONE - 6}px`;
      b.append(f._art.cv.cloneNode(false));
      b.lastChild.getContext('2d').drawImage(f._art.cv, 0, 0);
    } else {
      const title = document.createElement('span'); title.className = 'title'; title.textContent = f.title;
      b.append(title);
    }
    if (f._photo) {
      const ph = document.createElement('canvas'); ph.className = 'photo' + ((r >>> 5) % 4 === 0 ? ' round' : '');
      ph.width = f._photo.width; ph.height = f._photo.height; ph.style.width = ph.style.height = (f._w - 10) + 'px';
      ph.getContext('2d').drawImage(f._photo, 0, 0);
      b.append(ph);
    }
    if (f._top === 'tag') {
      const words = String(f.director).split(',')[0].trim().toUpperCase().split(/\s+/);
      const last = words.pop(), first = words.join(' ');
      const tag = document.createElement('span'); tag.className = 'tag';
      const px = Math.min(5.2, (f._w - 8) / (Math.max(last.length, first.length, 9) * .8));
      tag.style.fontSize = px.toFixed(1) + 'px';
      tag.textContent = ['A FILM BY', first, last].filter(Boolean).join('\n');
      b.append(tag);
    }
    // the base of the spine: format logo, hi-fi line and catalogue number, like a real release
    const base = document.createElement('span'); base.className = 'base';
    const vstyle = (r >>> 2) % 3;
    if ((r >>> 13) % 3) { const hf = document.createElement('span'); hf.className = 'hifi'; hf.textContent = (r >>> 15) % 2 ? 'hi-fi' : 'Hi-Fi Stereo'; base.append(hf); }
    const badge = document.createElement('span'); badge.className = 'vhs v' + vstyle; badge.textContent = 'VHS'; base.append(badge);
    if ((r >>> 16) % 4) {
      const cat = document.createElement('span'); cat.className = 'cat';
      cat.textContent = [`M${200000 + r % 700000}`, `VHS ${10000 + r % 89999}`, `NO. ${1000 + r % 9000}`][(r >>> 18) % 3];
      base.append(cat);
    }
    const notch = document.createElement('span'); notch.className = 'notch';
    b.append(base, notch);
    if (f._lab === 'lib') {
      const lb = document.createElement('span'); lb.className = 'lib';
      lb.style.cssText = `bottom:${56 + r % 28}px;--rot:${(((r >>> 3) % 7) - 3) * .6}deg`;
      lb.textContent = `(R)\n${10 + r % 40}\n${15000 + r % 9000}`;
      const bc = document.createElement('i'); bc.className = 'bc';
      let y = 0, st = [];
      const rb = rng(r ^ 0x9e3779b9);
      while (y < 30) { const th = 1 + Math.floor(rb() * 3), gap = 1 + Math.floor(rb() * 2); st.push(`#1d1a16 ${y}px ${y + th}px`, `transparent ${y + th}px ${y + th + gap}px`); y += th + gap; }
      bc.style.background = `linear-gradient(180deg, ${st.join(',')})`;
      lb.append(bc); b.append(lb);
    } else if (f._lab === 'rewind') {
      const rw = document.createElement('span'); rw.className = 'rew';
      rw.style.cssText = `bottom:${52 + r % 30}px;--rot:${(((r >>> 3) % 9) - 4) * .9}deg`;
      rw.textContent = 'BE\nKIND\nPLEASE\nREWIND'; b.append(rw);
    }
    b.append(wearCanvas(f));
    if (f._dmg.includes('sticker')) {
      const st = document.createElement('span'); st.className = 'sticker';
      const g = (f.genres || []).find((x) => STICKER_WORDS[x]);
      st.textContent = g ? STICKER_WORDS[g] : 'NEW';
      b.append(st);
    }
    if (i >= 0) b.addEventListener('click', () => openViewer(i));
    else b.tabIndex = -1; // a preview (see window.viewings below), not a real tape
    return b;
  }

  function layout() {
    shelves.textContent = '';
    spineEls = films.map(spineEl);
    const avail = shelves.clientWidth - 2 * (10 + 16);
    let row = [], used = 0, rows = [];
    films.forEach((f, i) => {
      const w = f._w;
      if (used + w > avail && row.length) { rows.push(row); row = []; used = 0; }
      row.push(i); used += w;
    });
    if (row.length) rows.push(row);
    rows.forEach((r) => {
      const wrap = document.createElement('div'); wrap.className = 'shelf-row';
      const shelf = document.createElement('div'); shelf.className = 'shelf';
      r.forEach((i) => shelf.appendChild(spineEls[i]));
      const board = document.createElement('div'); board.className = 'board';
      wrap.append(shelf, board);
      shelves.appendChild(wrap);
    });
    if (current >= 0) spineEls[current].classList.add('out');
  }

  /* ---------- viewer ---------- */
  const viewer = $('viewer'), cover = $('cover');

  function imdbUrl(f) {
    return f.imdb ? `https://www.imdb.com/title/${f.imdb}/` : `https://www.imdb.com/find/?q=${encodeURIComponent(f.title + ' ' + f.year)}`;
  }

  // Ratings are out of 10 (PassThePopcorn). Stars round to the nearest half: 8.5 -> 4.5 stars, 7.5 -> 4.
  // Films from the old Letterboxd import only have "rating" (out of 5).
  function stars(f) {
    const r10 = f.rating10 != null ? f.rating10 : (f.rating || 0) * 2, r = Math.round(r10) / 2;
    let h = '';
    for (let i = 1; i <= 5; i++) h += `<span class="star ${r >= i ? 'full' : r >= i - .5 ? 'half' : ''}">&#9733;</span>`;
    return h + `<small>${r10 ? +r10.toFixed(1) : '—'} / 10</small>`;
  }

  function fmtDate(iso) {
    const d = new Date(iso + 'T12:00:00');
    return isNaN(d) ? iso : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function fill(i) {
    const f = films[i];
    cover.href = imdbUrl(f);
    cover.setAttribute('aria-label', `${f.title} on IMDb`);
    cover.style.setProperty('--c', f._c); cover.style.setProperty('--t', f._t);
    cover.querySelectorAll('.fallback').forEach((n) => n.remove());
    cover.style.backgroundImage = f.poster ? `url("${f.poster}")` : 'none';
    if (!f.poster) {
      const fb = document.createElement('div');
      fb.className = 'fallback'; fb.textContent = f.title; fb.style.fontFamily = `'${f._font}'`;
      cover.prepend(fb);
    }
    // restart pull animation
    cover.style.animation = 'none'; void cover.offsetWidth; cover.style.animation = '';

    const t = $('v-title');
    t.textContent = f.title; t.style.setProperty('--f', `'${f._font}'`);
    const facts = [f.year, f.runtime ? `${f.runtime} min` : null, f.director ? `dir. ${f.director}` : null].filter(Boolean);
    $('v-facts').textContent = facts.join(' · ');
    $('v-rating').innerHTML = stars(f);
    $('v-watched').textContent = `Watched ${fmtDate(f.watched)}${f.rewatch ? ' (rewatch)' : ''}`;
    $('v-genres').innerHTML = (f.genres || []).map((g) => `<span>${g}</span>`).join('');
    $('v-note').textContent = f.note || '';
  }

  function openViewer(i) {
    const el = spineEls[i];
    el.classList.add('pulling');
    setTimeout(() => {
      el.classList.remove('pulling'); el.classList.add('out');
      current = i; fill(i);
      viewer.classList.add('open'); viewer.setAttribute('aria-hidden', 'false');
      $('close').focus({ preventScroll: true });
    }, 180);
  }

  function closeViewer() {
    if (current < 0) return;
    const el = spineEls[current];
    el.classList.remove('out'); el.classList.add('back');
    setTimeout(() => el.classList.remove('back'), 520);
    viewer.classList.remove('open'); viewer.setAttribute('aria-hidden', 'true');
    el.focus({ preventScroll: true });
    current = -1;
  }

  function step(d) {
    if (current < 0) return;
    const n = (current + d + films.length) % films.length;
    spineEls[current].classList.remove('out');
    current = n; spineEls[n].classList.add('out'); fill(n);
  }

  $('close').addEventListener('click', closeViewer);
  $('backdrop').addEventListener('click', closeViewer);
  $('prev').addEventListener('click', () => step(-1));
  $('next').addEventListener('click', () => step(1));
  document.addEventListener('keydown', (e) => {
    if (current < 0) return;
    if (e.key === 'Escape') closeViewer();
    else if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
  });
  // clicking empty space around the cover (but not the info panel) also closes
  document.querySelector('.panel').addEventListener('click', (e) => {
    if (e.target.classList.contains('panel')) closeViewer();
  });

  // Hooks for vcr.js: preview a spine for a film (with edited fields) and redraw the shelf.
  window.viewings = {
    get films() { return films; },
    get current() { return current >= 0 ? films[current] : null; },
    async preview(f) { await prepare(f); return spineEl(f, -1); },
    async refresh(f) { await prepare(f); layout(); },
  };

  /* ---------- boot ---------- */
  async function boot() {
    let data;
    try { data = await (await fetch('films.json', { cache: 'no-cache' })).json(); }
    catch { shelves.innerHTML = '<p style="text-align:center;opacity:.6">Couldn\'t load films.json. Serve this folder over http (see README).</p>'; return; }
    films = (data.films || []).slice().sort((a, b) => (a.watched || '').localeCompare(b.watched || ''));
    $('year').textContent = data.year || new Date().getFullYear();
    $('count').textContent = films.length;
    await Promise.all(films.map(prepare));
    layout();
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(layout, 150); });
  }
  boot();
})();
