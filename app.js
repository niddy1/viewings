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
    const cream = (a) => `rgba(${236 + R() * 14 | 0},${228 + R() * 14 | 0},${208 + R() * 14 | 0},${a})`;
    const y0 = PAD, yb = PAD + H; // the spine's real top and bottom edges

    // The top fold. The spine panel folds over into the top panel along a slightly rounded edge, so the very
    // top catches the light; over the years the printed colour cracks along that fold and the pale board
    // shows through as fibres, most of all at the two corners. No line across the spine, no top face.
    const SHELF = '#0b0805', wear = .3 + sev * .7;
    const buff = (a) => `rgba(${196 + R() * 28 | 0},${186 + R() * 26 | 0},${160 + R() * 28 | 0},${a})`;
    const gr = x.createLinearGradient(0, y0, 0, y0 + 4.5);
    gr.addColorStop(0, 'rgba(255,255,255,.24)'); gr.addColorStop(.5, 'rgba(255,255,255,.08)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gr; x.fillRect(0, y0, W, 4.5);
    // Each tape gets its own kind of top: bare, a thin wavy white lid line, a broken lid line, or a thicker
    // bent-up lid. Fibres and cracked corners are on only some of them, so no two read the same.
    const kind = R(), [sr, sg, sb] = f._rgb;
    const lidKind = kind < .3 ? 0 : kind < .62 ? 1 : kind < .82 ? 2 : 3;
    const useFib = chance(.55), useCorner = chance(.5);
    if (lidKind) {
      const ph1 = R() * 6.28, ph2 = R() * 6.28, f1 = rr(.12, .3), f2 = rr(.35, .7);
      const tilt = rr(-.9, .9) + (sev > .5 ? rr(-1.8, 1.8) * sev : 0);
      const off = rr(-.7, .3), baseTh = lidKind === 3 ? rr(2.2, 3.4) : rr(.9, 2.1);
      const yT = (px) => y0 + off + tilt * (px / W) + Math.sin(px * f1 + ph1) * .35 + Math.sin(px * f2 + ph2) * .15;
      const th = (px) => baseTh * (1 + .35 * Math.sin(px * .21 + ph2) + .2 * Math.sin(px * .6 + ph1));
      const alpha = rr(.65, 1);
      const lg = x.createLinearGradient(0, y0 - 1, 0, y0 + 3.5);
      lg.addColorStop(0, `rgba(246,242,230,${alpha})`); lg.addColorStop(1, `rgba(214,205,184,${alpha})`);
      const gaps = lidKind === 2 ? [] : null;
      if (gaps) for (let px = rr(0, 6); px < W; px += rr(5, 16)) gaps.push([px, px + rr(2, 8)]);
      const seg = (p0, p1) => {
        x.beginPath(); x.moveTo(p0, yT(p0));
        for (let px = p0 + 1; px <= p1; px++) x.lineTo(px, yT(px));
        for (let px = p1; px >= p0; px--) x.lineTo(px, yT(px) + th(px));
        x.closePath(); x.fillStyle = lg; x.fill();
      };
      if (gaps) { let p = 0; gaps.forEach(([g0, g1]) => { if (g0 > p) seg(p, Math.min(g0, W)); p = Math.min(g1, W); }); if (p < W) seg(p, W); }
      else seg(0, W);
      if (lidKind === 3) { // lid bent up at one end, showing its dark underside
        const lift = rr(1.2, 2.6), left = chance(.5), e = left ? 0 : W, m = left ? W * .75 : W * .25;
        x.fillStyle = `rgb(${[sr, sg, sb].map((v) => Math.round(v * .7)).join(',')})`;
        x.beginPath(); x.moveTo(e, yT(e)); x.lineTo(e, yT(e) - lift); x.lineTo(m, yT(m) - lift * .3); x.lineTo(m, yT(m)); x.closePath(); x.fill();
      }
      x.strokeStyle = 'rgba(0,0,0,.28)'; x.lineWidth = 1; x.beginPath(); x.moveTo(0, yT(0) + th(0) + .9);
      for (let px = 1; px <= W; px++) x.lineTo(px, yT(px) + th(px) + .9);
      x.stroke();
      if (chance(.4)) { const left = chance(.5), px = left ? 0 : W - 1; x.fillStyle = cream(.85); x.fillRect(px, yT(px), 1, rr(3, 7)); }
    }
    [0, 1].forEach((side) => { // slightly rounded top corners
      const r = rr(.9, 1.9), cx = side ? W : 0, dir = side ? -1 : 1;
      x.fillStyle = SHELF; x.beginPath(); x.moveTo(cx, y0); x.lineTo(cx + dir * r, y0); x.quadraticCurveTo(cx, y0, cx, y0 + r); x.closePath(); x.fill();
    });
    if (useFib) for (let px = 0; px < W; px += rr(.8, 1.8)) { // fibres where the print has cracked along the fold, thickest at the corners
      const corner = Math.exp(-Math.min(px, W - px) / 5);
      if (!chance((.1 + .5 * corner) * wear * 1.4)) continue;
      x.fillStyle = buff(rr(.45, .95)); x.fillRect(px, y0 + rr(-.1, .6), rr(.6, 1.3), rr(.8, 1.4 + 2.4 * corner * wear));
    }
    if (useFib) for (let px = 0; px < W;) { // the pale board along the very edge of the fold, in broken lengths
      const seg = rr(2, 8);
      if (chance(.35 * wear + .1)) { x.fillStyle = buff(rr(.4, .8)); x.fillRect(px, y0 + rr(-.1, .3), seg, rr(.5, .9)); }
      px += seg;
    }
    [0, 1].forEach((side) => { // corners where the colour has cracked right away
      if (!useCorner || !chance(.45 + .5 * wear)) return;
      const w = rr(2, 3 + 5 * wear), h = rr(2, 3 + 4 * wear), m = (u) => (side ? W - u : u);
      x.fillStyle = buff(rr(.7, .95)); x.beginPath();
      [[0, 0], [w, 0], [w * rr(.6, .9), h * rr(.3, .5)], [w * rr(.3, .6), h * rr(.6, .8)], [w * rr(.1, .4), h], [0, h * rr(.5, .9)]].forEach(([u, v], i) => (i ? x.lineTo(m(u), y0 + v) : x.moveTo(m(u), y0 + v)));
      x.closePath(); x.fill();
    });
    if (!sev) return cv;

    // Each damaged tape gets a different mix of problems, not all of them.
    const has = {
      top: false, peel: false, corner: sev > .3 && chance(.5),
      edges: chance(.55 + sev * .4), specks: chance(.6 + sev * .3), crease: chance(.25 + sev * .65),
      scratch: sev > .5 && chance(.6), bottom: chance(.55 + sev * .4),
    };
    if (!Object.values(has).some(Boolean)) has.specks = true;

    if (has.top) { // white board showing where the printed top has worn through, in broken patches along the edge
      const depth = L(.6, 2), rise = L(.2, 1);
      for (let px = -1; px < W;) {
        const seg = rr(3, 12);
        if (chance(.3 + sev * .5)) {
          const d = rr(.5, depth);
          x.beginPath(); x.moveTo(px, y0 + .5);
          for (let t = 0; t <= 1.001; t += .25) x.lineTo(px + seg * t, y0 - rr(0, rise));
          for (let t = 1; t >= -.001; t -= .25) x.lineTo(px + seg * t, y0 + d * rr(.35, 1));
          x.closePath(); x.fillStyle = cream(.92); x.fill();
        }
        px += seg;
      }
    }
    if (has.peel) for (let i = 0, n = sev > .75 ? 2 : 1; i < n; i++) { // printed layer lifted away
      const pw = rr(W * .25, W * .6), px = rr(0, W - pw), ph = rr(5, L(7, 14));
      x.beginPath(); x.moveTo(px, y0);
      for (let t = 0; t <= 1.001; t += .2) x.lineTo(px + pw * t, y0 + ph * rr(.3, 1) * Math.sin(Math.PI * t) + 1);
      x.closePath(); x.fillStyle = cream(.92); x.fill();
      x.strokeStyle = 'rgba(0,0,0,.28)'; x.lineWidth = .8; x.stroke();
    }
    if (has.corner) { // a top corner rubbed through
      const left = chance(.5), cs = rr(2.5, L(3.5, 6.5));
      x.beginPath();
      if (left) { x.moveTo(-1, y0 - 2); x.lineTo(cs, y0 - 2); x.lineTo(cs * .6, y0 + cs * .4); x.lineTo(cs * .2, y0 + cs * .9); x.lineTo(-1, y0 + cs); }
      else { x.moveTo(W + 1, y0 - 2); x.lineTo(W - cs, y0 - 2); x.lineTo(W - cs * .6, y0 + cs * .4); x.lineTo(W - cs * .2, y0 + cs * .9); x.lineTo(W + 1, y0 + cs); }
      x.closePath(); x.fillStyle = cream(.95); x.fill();
    }
    if (has.edges) for (let i = 0, n = L(4, 28) | 0; i < n; i++) { // rubbed sides, heaviest near the ends
      const side = chance(.5), e = R();
      const py = y0 + (e < .45 ? rr(0, H * .3) : e < .7 ? rr(H * .7, H) : rr(0, H));
      const wd = rr(.7, L(1.1, 2.4));
      x.fillStyle = cream(rr(.45, .9)); x.fillRect(side ? 0 : W - wd, py, wd, rr(3, L(8, 34)));
    }
    if (has.specks) for (let i = 0, n = L(20, 160) | 0; i < n; i++) { // scuffs
      const px = chance(.6) ? (chance(.5) ? rr(0, W * .22) : rr(W * .78, W)) : rr(0, W);
      x.fillStyle = cream(rr(.2, .7)); x.fillRect(px, y0 + (chance(.5) ? rr(0, H * .3) : rr(0, H)), rr(.5, 1.5), rr(.5, 1.5));
    }
    if (has.crease) for (let i = 0, n = sev > .7 ? 2 + (chance(.5) ? 1 : 0) : 1; i < n; i++) { // hard creases
      let cy = y0 + rr(H * .12, H * .85); const slope = rr(-.18, .18);
      for (let px = 0; px < W; px += rr(0, 1)) {
        const seg = rr(4, 11), ny = cy + slope * seg + rr(-.9, .9);
        if (!chance(.06)) {
          x.strokeStyle = 'rgba(0,0,0,.45)'; x.lineWidth = 1; x.beginPath(); x.moveTo(px, cy + 1); x.lineTo(px + seg, ny + 1); x.stroke();
          x.strokeStyle = cream(rr(.55, .95)); x.lineWidth = rr(.7, 1.5); x.beginPath(); x.moveTo(px, cy); x.lineTo(px + seg, ny); x.stroke();
        }
        px += seg; cy = ny;
      }
    }
    if (has.scratch) for (let i = 0, n = L(1, 5) | 0; i < n; i++) {
      const sx = rr(0, W), sy = y0 + rr(0, H), l = rr(8, 26), ang = rr(-.5, .5) + Math.PI / 2;
      x.strokeStyle = cream(rr(.15, .4)); x.lineWidth = .6; x.beginPath(); x.moveTo(sx, sy); x.lineTo(sx + Math.cos(ang) * l, sy + Math.sin(ang) * l); x.stroke();
    }

    // Bottom: the arch cut-out takes the most punishment. Fray around its rim, white stress
    // cracks climbing out of it, crushed lower corners and scuffing along the bottom edge.
    if (has.bottom) {
      const cx = W / 2, rim = 7;
      // whitened rim around the arch, in broken pieces
      x.lineCap = 'round';
      for (let a0 = Math.PI; a0 < 2 * Math.PI; a0 += rr(.25, .6)) {
        if (!chance(.45 + sev * .5)) continue;
        x.strokeStyle = cream(rr(.5, .95)); x.lineWidth = rr(.8, L(1.2, 2.6));
        x.beginPath(); x.arc(cx, yb, rim + rr(0, 1.5), a0, a0 + rr(.2, .5)); x.stroke();
      }
      x.lineCap = 'butt';
      // cracks climbing up from the arch
      for (let i = 0, n = L(0, 3.4) | 0; i < n; i++) {
        let px = cx + rr(-5, 5), py = yb - rim;
        x.strokeStyle = cream(rr(.5, .9)); x.lineWidth = rr(.6, 1.1); x.beginPath(); x.moveTo(px, py);
        for (let k = 0, m = rr(3, L(5, 16)); k < m; k += 2) { px += rr(-1.2, 1.2); py -= 2; x.lineTo(px, py); }
        x.stroke();
      }
      // ragged white fray along the bottom edge, thickest each side of the arch
      x.fillStyle = cream(.9);
      for (let px = 0; px < W; px += rr(1.5, 3.5)) {
        if (Math.abs(px - cx) < rim - 1) continue;
        const near = Math.abs(px - cx) < rim + 8 ? 1 : .45;
        if (chance(.35 + .5 * sev * near)) x.fillRect(px, yb - rr(.5, L(1.5, 5)) * near, rr(1, 2.6), 6);
      }
      // crushed lower corner
      if (sev > .35 && chance(.6)) {
        const left = chance(.5), cs = rr(3, L(4, 9));
        x.beginPath();
        if (left) { x.moveTo(-1, yb - cs); x.lineTo(cs * .5, yb - cs * .5); x.lineTo(cs, yb + 1); x.lineTo(-1, yb + 1); }
        else { x.moveTo(W + 1, yb - cs); x.lineTo(W - cs * .5, yb - cs * .5); x.lineTo(W - cs, yb + 1); x.lineTo(W + 1, yb + 1); }
        x.closePath(); x.fillStyle = cream(.92); x.fill();
      }
      for (let i = 0, n = L(4, 22) | 0; i < n; i++) { x.fillStyle = cream(rr(.3, .8)); x.fillRect(rr(0, W), yb - rr(0, 9), rr(.6, 2.2), rr(.6, 2)); }
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
