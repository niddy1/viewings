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
    f._top = f.logo && (r >>> 10) % 2 === 0 ? 'logo' // about half the tapes show their studio, as on a real shelf
      : img && tbs.length && f.title.length <= 14 && (r >>> 3) % 3 === 0 ? 'panel'
      : f._dmg.includes('sticker') ? 'sticker'
      : f.director && (r >>> 6) % 2 === 0 ? 'tag' : '';
    // "top" in films.json picks it by hand (set from the Re-mark spine editor): logo, photo, tag, sticker or none.
    const want = { logo: f.logo ? 'logo' : '', photo: img ? 'panel' : '', tag: f.director ? 'tag' : '', sticker: 'sticker', none: '' }[f.top];
    if (want !== undefined) {
      f._top = want;
      if (want === 'sticker' && !f._dmg.includes('sticker')) f._dmg.push('sticker');
    }
    f._logoCrop = null; f._logoColor = false;
    if (f._top === 'logo') {
      const li = await loadImg(f.logo);
      if (li && Array.isArray(f.logoBox)) f._logoCrop = logoCrop(li, f.logoBox);
      // Plain wordmarks print as a white silhouette; logos with real colour (MGM's lion, the WB shield) keep it,
      // with any black ink reprinted white so it shows on a dark spine.
      // "logoStyle": "color" | "white" in films.json overrides the guess.
      f._logoColor = f.logoStyle ? f.logoStyle === 'color' : logoIsGraphic(f._logoCrop || li);
      if (li) f._logoCrop = f._logoCrop || logoCrop(li, [0, 0, 1, 1]);
    }
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
    f._light = lum(...rgb) > 150; // pale spine: logos print dark instead of white
    if (f._logoCrop) f._logoCrop = f._logoColor ? (f._light ? f._logoCrop : inkToWhite(f._logoCrop)) : monoPrint(f._logoCrop, f._light ? [29, 26, 22] : [240, 232, 210]);
  }

  // A one-colour print of a logo: solid shapes become ink, and lettering inside a box stays knocked out
  // (so boxed logos don't turn into a blank bar). Which tone counts as ink is read from the logo itself.
  function monoPrint(cv, ink) {
    try {
      const x = cv.getContext('2d'), id = x.getImageData(0, 0, cv.width, cv.height), d = id.data;
      let lo = 1, hi = 0, sum = 0, n = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] < 128) continue;
        const l = lum(d[i], d[i + 1], d[i + 2]) / 255; lo = Math.min(lo, l); hi = Math.max(hi, l); sum += l; n++;
      }
      const range = hi - lo, darkInk = n && sum / n < (lo + hi) / 2 + .15; // mostly dark marks: dark is the ink
      for (let i = 0; i < d.length; i += 4) {
        if (!d[i + 3]) continue;
        let w = 1;
        if (range > .25) { const l = lum(d[i], d[i + 1], d[i + 2]) / 255; w = clamp(darkInk ? (hi - l) / range : (l - lo) / range, 0, 1); w = smooth(.25, .75, w); }
        d[i] = ink[0]; d[i + 1] = ink[1]; d[i + 2] = ink[2]; d[i + 3] = Math.round(d[i + 3] * w);
      }
      x.putImageData(id, 0, 0);
    } catch {}
    return cv;
  }

  // Black and dark-grey ink in a colour logo, lifted to the off-white the spine lettering uses.
  function inkToWhite(cv) {
    try {
      const x = cv.getContext('2d'), id = x.getImageData(0, 0, cv.width, cv.height), d = id.data;
      for (let i = 0; i < d.length; i += 4) {
        if (!d[i + 3]) continue;
        const [, s, l] = rgbToHsl(d[i], d[i + 1], d[i + 2]);
        if (l < .3 && s < .35) { const k = 1 - l / .3; d[i] += (239 - d[i]) * k; d[i + 1] += (230 - d[i + 1]) * k; d[i + 2] += (210 - d[i + 2]) * k; }
      }
      x.putImageData(id, 0, 0);
    } catch {}
    return cv;
  }

  // Does a logo carry real colour (MGM gold, WB blue) rather than being a one-colour or black-and-white mark?
  function logoIsGraphic(src) {
    if (!src) return false;
    try {
      const w = 48, hgt = Math.max(1, Math.round(48 * (src.height || src.naturalHeight) / (src.width || src.naturalWidth)));
      const c = document.createElement('canvas'); c.width = w; c.height = hgt;
      const x = c.getContext('2d'); x.drawImage(src, 0, 0, w, hgt);
      const d = x.getImageData(0, 0, w, hgt).data;
      let n = 0, sat = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] < 200) continue;
        const [, s, l] = rgbToHsl(d[i], d[i + 1], d[i + 2]);
        n++; if (s > .3 && l > .15 && l < .9) sat++;
      }
      return n >= 20 && sat / n > .15;
    } catch { return false; }
  }

  // Part of the studio logo ("logoBox" = [x0,y0,x1,y1] fractions of the logo image).
  function logoCrop(img, [x0, y0, x1, y1]) {
    if (!img) return null;
    const iw = img.naturalWidth, ih = img.naturalHeight, sw = Math.max(1, (x1 - x0) * iw), sh = Math.max(1, (y1 - y0) * ih);
    const cv = document.createElement('canvas'); cv.width = Math.round(sw); cv.height = Math.round(sh);
    cv.getContext('2d').drawImage(img, x0 * iw, y0 * ih, sw, sh, 0, 0, cv.width, cv.height);
    return cv;
  }

  // A square crop of the poster (away from its lettering) for the framed picture some spines carry up top.
  // "photoBox" ([x0,y0,x1,y1] fractions of the poster) picks the crop by hand.
  function photoCrop(f, img) {
    const iw = img.naturalWidth, ih = img.naturalHeight, pw = f._w - 10;
    let src;
    if (Array.isArray(f.photoBox)) {
      const [x0, y0, x1, y1] = f.photoBox;
      src = [x0 * iw, y0 * ih, Math.max(1, (x1 - x0) * iw), Math.max(1, (y1 - y0) * ih)];
    } else {
      const side = iw * .66;
      const boxes = (f.titleBox || []).map((b) => [b[1] * ih, b[3] * ih]);
      let best = null;
      for (let c = .24; c <= .64; c += .02) {
        const y0 = clamp(c * ih - side / 2, 0, ih - side), y1 = y0 + side;
        const over = boxes.reduce((a, [t, u]) => a + Math.max(0, Math.min(y1, u) - Math.max(y0, t)), 0);
        const score = over + Math.abs(c - .38) * ih * .3;
        if (!best || score < best.score) best = { score, y0 };
      }
      src = [(iw - side) / 2, best.y0, side, side];
    }
    const dpr = Math.min(window.devicePixelRatio || 1, 3), cv = document.createElement('canvas');
    cv.width = cv.height = Math.round(pw * dpr);
    const x = cv.getContext('2d');
    x.drawImage(img, ...src, 0, 0, cv.width, cv.height);
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
    // fades inward, then hairline scratches and creases, and at the worst a rounded-off corner with grey board
    // showing along it. Everything is drawn as soft round-capped strokes and dust, never as hard pixel blocks.
    // Excellent copies (about 1 in 25) get nothing but the soft top highlight.
    const dustC = () => (pale ? [140 + R() * 24, 136 + R() * 22, 126 + R() * 22] : [222 + R() * 28, 218 + R() * 26, 206 + R() * 28]);
    const boardC = () => [186 + R() * 26, 180 + R() * 24, 164 + R() * 26];
    const col = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
    const dust = (a) => col(dustC(), a), board = (a) => col(boardC(), a), dark = (a) => `rgba(8,6,4,${a})`;
    x.lineCap = 'round'; x.lineJoin = 'round';

    const gr = x.createLinearGradient(0, y0, 0, y0 + 4.5);
    gr.addColorStop(0, 'rgba(255,255,255,.22)'); gr.addColorStop(.5, 'rgba(255,255,255,.07)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gr; x.fillRect(0, y0, W, 4.5);

    x.beginPath(); x.rect(0, y0, W, H); x.clip(); // nothing is drawn outside the spine itself
    const tier = !sev ? -1 : sev < .3 ? 0 : sev < .62 ? 1 : 2; // excellent (-1), light, medium, heavy (0..2)

    // --- primitives -------------------------------------------------------------------------------
    const fibre = (px, py, ang, len, th, c, a) => {
      x.strokeStyle = col(c, a); x.lineWidth = th; x.beginPath(); x.moveTo(px, py);
      x.quadraticCurveTo(px + Math.cos(ang) * len * .5 + rr(-.4, .4), py + Math.sin(ang) * len * .5 + rr(-.4, .4), px + Math.cos(ang) * len, py + Math.sin(ang) * len);
      x.stroke();
    };
    const puff = (px, py, r, a, c) => {
      c = c || dustC(); const g = x.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, col(c, a)); g.addColorStop(1, col(c, 0)); x.fillStyle = g; x.fillRect(px - r, py - r, r * 2, r * 2);
    };
    const fleck = (px, py, r, a, c) => { x.fillStyle = col(c || dustC(), a); x.beginPath(); x.arc(px, py, r, 0, 6.283); x.fill(); };
    // Dry-brush streaks along one edge, densest at the edge and fading inward, with soft dust over it.
    const brush = (edge, depth, n, k) => {
      const horiz = edge === 't' || edge === 'b';
      for (let i = 0, m = n * k | 0; i < m; i++) {
        const d = depth * Math.pow(R(), 2.1), fade = 1 - d / depth * .55;
        const along = horiz ? (chance(.5) ? rr(0, W) : chance(.5) ? rr(0, W * .22) : rr(W * .78, W)) : (chance(.55) ? rr(0, H * .25) : chance(.5) ? rr(H * .75, H) : rr(0, H));
        const px = edge === 'l' ? d : edge === 'r' ? W - d : along, py = edge === 't' ? y0 + d : edge === 'b' ? yb - d : y0 + along;
        const base = horiz ? (chance(.5) ? 0 : Math.PI) : Math.PI / 2;
        fibre(px, py, base + rr(-.35, .35) + (chance(.15) ? rr(-1, 1) : 0), rr(1.2, 6.5), rr(.35, .85), dustC(), rr(.18, .62) * fade);
      }
      for (let i = 0, m = n * k / 9 | 0; i < m; i++) { // dust dulling the print along the edge
        const d = depth * rr(0, .8), along = horiz ? rr(0, W) : rr(0, H);
        puff(edge === 'l' ? d : edge === 'r' ? W - d : along, edge === 't' ? y0 + d : edge === 'b' ? yb - d : y0 + along, rr(2, 5.5), rr(.05, .15) * k);
      }
    };
    // A hairline scratch or crease: a thin pale line (with a faint shadow beside it for creases).
    const hair = (px, py, ang, len, a, bend, shadow) => {
      const ex = px + Math.sin(ang) * len, ey = py + Math.cos(ang) * len;
      const cx = (px + ex) / 2 + Math.cos(ang) * bend, cy = (py + ey) / 2 - Math.sin(ang) * bend;
      if (shadow) { x.strokeStyle = dark(shadow); x.lineWidth = .7; x.beginPath(); x.moveTo(px + .8, py); x.quadraticCurveTo(cx + .8, cy, ex + .8, ey); x.stroke(); }
      x.strokeStyle = dust(a); x.lineWidth = rr(.4, .75); x.beginPath(); x.moveTo(px, py); x.quadraticCurveTo(cx, cy, ex, ey); x.stroke();
    };
    // A corner worn round. The sharp corner is knocked off along an uneven curve and a rim of pale board
    // shows along the new edge, with fibres and dust thrown off it. v = -1 for the top, +1 for the bottom.
    const rounded = (side, bottom, r, rough) => {
      const dir = side ? -1 : 1, cx = side ? W : 0, ey = bottom ? yb : y0, vy = bottom ? -1 : 1;
      const Cx = cx + dir * r, Cy = ey + vy * r, pts = [];
      for (let i = 0, n = 9; i <= n; i++) {
        const ph = i / n * Math.PI / 2, rad = r * (1 + rr(-rough, rough * .6));
        pts.push([Cx - dir * rad * Math.sin(ph), Cy - vy * rad * Math.cos(ph)]);
      }
      x.fillStyle = bottom ? 'rgba(14,8,4,.96)' : SHELF; x.beginPath();
      x.moveTo(cx - dir * 2, ey - vy * 3); x.lineTo(Cx, ey - vy * 3); pts.forEach(([px, py]) => x.lineTo(px, py)); x.lineTo(cx - dir * 2, Cy); x.closePath(); x.fill();
      if (tier >= 1) {
        x.strokeStyle = board(rr(.7, .95)); x.lineWidth = rr(.9, 1.3 + tier * .45); x.beginPath();
        pts.forEach(([px, py], i) => (i ? x.lineTo(px + dir * .6, py + vy * .6) : x.moveTo(px + dir * .6, py + vy * .6))); x.stroke();
        for (let i = 0, m = 3 + r * 1.6 | 0; i < m; i++) {
          const [px, py] = pts[R() * pts.length | 0];
          if (chance(.5)) fibre(px + dir * .8, py + vy * .8, rr(0, 6.28), rr(.8, 2.4), rr(.3, .6), boardC(), rr(.4, .85));
          else fleck(px + dir * rr(.5, 2.5), py + vy * rr(.5, 2.5), rr(.3, .8), rr(.4, .85), dustC());
        }
        puff(Cx - dir * r * .6, Cy - vy * r * .6, r * 1.3, rr(.08, .2) * (tier + 1) / 3);
      }
    };
    // A knocked-in dent at a corner: a soft, uneven patch of grey board, never a clean shape.
    const bruise = (side, bottom, size) => {
      const dir = side ? -1 : 1, vy = bottom ? -1 : 1, cx = side ? W : 0, cy = bottom ? yb : y0;
      for (let i = 0, m = size * 5 | 0; i < m; i++) {
        const t = R() * Math.PI / 2, rad = size * Math.pow(R(), .7) * 1.3;
        const px = cx + dir * Math.cos(t) * rad, py = cy + vy * Math.sin(t) * rad;
        if (chance(.45)) fleck(px, py, rr(.4, 1.1), rr(.35, .8), boardC()); else fibre(px, py, rr(0, 6.28), rr(1, 3), rr(.3, .7), chance(.5) ? boardC() : dustC(), rr(.3, .7));
      }
      puff(cx + dir * size * .45, cy + vy * size * .45, size * 1.1, rr(.12, .26), boardC());
    };
    // The flap's edge along the very top: a thin, uneven strip of pale board, torn in places.
    const strip = () => {
      const th0 = rr(1.1, 1.8) + sev * 1.0, tilt = rr(-.5, .5), yTop = (px) => y0 - .3 + tilt * (px / W);
      let px = rr(-1, 2);
      while (px < W) {
        const len = rr(6, 26);
        if (chance(.18 + .1 * (1 - sev))) { px += rr(2, 7); continue; } // a gap where the board has been rubbed off
        const end = Math.min(W + 1, px + len), pts = [];
        let h = th0 * rr(.7, 1.2);
        for (let p = px; p <= end; p += 1.6) { h = clamp(h + rr(-.35, .35), .5, th0 * 1.8); pts.push([p, yTop(p) + h * Math.min(1, (p - px) / 2 + .15, (end - p) / 2 + .15)]); }
        const g = x.createLinearGradient(0, y0 - 1, 0, y0 + th0 * 2);
        g.addColorStop(0, col(boardC(), .96)); g.addColorStop(1, col([160, 154, 140], .92));
        x.fillStyle = g; x.beginPath(); x.moveTo(px, yTop(px));
        pts.forEach(([p, q]) => x.lineTo(p, q)); x.lineTo(end, yTop(end)); x.closePath(); x.fill();
        x.strokeStyle = dark(L(.15, .38)); x.lineWidth = .8; x.beginPath();
        pts.forEach(([p, q], i) => (i ? x.lineTo(p, q + 1.1) : x.moveTo(p, q + 1.1))); x.stroke();
        pts.forEach(([p, q]) => { if (chance(.18)) fibre(p, q, Math.PI / 2 + rr(-.6, .6), rr(.8, 2.4), rr(.3, .55), boardC(), rr(.35, .75)); });
        px = end + rr(0, 3);
      }
    };

    // --- each tape rolls its own mix, so no two read alike -------------------------------------------
    if (tier >= 0) {
      const amt = { t: chance(.82) ? rr(.6, 1.3) : rr(0, .3), b: chance(.7) ? rr(.5, 1.2) : rr(0, .3), l: chance(.65) ? rr(.4, 1.2) : rr(0, .3), r: chance(.65) ? rr(.4, 1.2) : rr(0, .3) };
      if (tier === 0) { amt.t *= .8; amt.l *= .5; amt.r *= .5; }
      const density = L(22, 170);
      brush('t', L(2.5, 7), density * 1.1, amt.t);
      brush('b', L(2.5, 8), density * .8, amt.b);
      brush('l', L(1.8, 6), density * .7, amt.l);
      brush('r', L(1.8, 6), density * .7, amt.r);
      [0, 1].forEach((side) => { // frosted rim: the print worn a shade paler down the sides
        if (!chance(.35 + sev * .5)) return;
        const g = x.createLinearGradient(side ? W : 0, 0, side ? W - 3.5 : 3.5, 0);
        g.addColorStop(0, dust(L(.1, .3))); g.addColorStop(1, 'rgba(255,255,255,0)');
        x.fillStyle = g; x.fillRect(side ? W - 3.5 : 0, y0 + rr(0, H * .2), 3.5, rr(H * .4, H * .8));
      });
      if (chance([.12, .58, .92][tier])) strip();

      // corners: nothing stays a perfect right angle once a tape has been handled; the worse the wear,
      // the rounder and more uneven the corner
      [0, 1].forEach((side) => {
        rounded(side, false, tier === 0 ? rr(1, 2) : tier === 1 ? rr(1.8, 4.2) : rr(3, 8.5), tier === 2 ? .35 : .18);
        if (tier === 2 && chance(.6)) bruise(side, false, rr(3, 8));
        if (tier >= 1 && chance(tier === 1 ? .35 : .85)) rounded(side, true, tier === 1 ? rr(1.5, 3.5) : rr(2.5, 7.5), tier === 2 ? .35 : .18);
        if (tier === 2 && chance(.5)) bruise(side, true, rr(3, 7));
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
      // scuffed flecks over the face, thicker toward the sides
      for (let i = 0, n = L(8, 80) * rr(.5, 1.3) | 0; i < n; i++) {
        const px = chance(.55) ? (chance(.5) ? rr(0, W * .2) : rr(W * .8, W)) : rr(0, W);
        fleck(px, y0 + (chance(.5) ? rr(0, H * .35) : rr(0, H)), rr(.3, .75), rr(.25, .65));
      }
      // Bottom: the arch cut-out takes the most punishment. Dust fanned round its rim, hairline cracks
      // climbing from it, and the bottom edge fraying into board on the worst copies.
      if (chance(.5 + sev * .45)) {
        const cx = W / 2, rim = 7;
        for (let i = 0, n = L(8, 40) | 0; i < n; i++) {
          const an = Math.PI + R() * Math.PI, rad = rim + Math.pow(R(), 1.8) * 9;
          fleck(cx + Math.cos(an) * rad, yb + Math.sin(an) * rad, rr(.3, .8), rr(.3, .75));
        }
        for (let a0 = Math.PI; a0 < 2 * Math.PI; a0 += rr(.3, .7)) {
          if (!chance(.3 + sev * .5)) continue;
          x.strokeStyle = dust(rr(.35, .75)); x.lineWidth = rr(.6, L(.8, 1.5));
          x.beginPath(); x.arc(cx, yb, rim + rr(0, 1.2), a0, a0 + rr(.2, .5)); x.stroke();
        }
        for (let i = 0, n = L(0, 3.2) | 0; i < n; i++) hair(cx + rr(-6, 6), yb - rim, Math.PI + rr(-.25, .25), rr(6, L(8, 20)), rr(.35, .7), rr(-1.2, 1.2), 0);
        if (tier === 2 && chance(.55)) {
          for (let px = 0; px < W; px += rr(1.2, 2.6)) {
            if (Math.abs(px - cx) < rim - 1) continue;
            if (chance(.55)) fibre(px, yb - rr(.2, 1.5), -Math.PI / 2 + rr(-.5, .5), rr(1, 3), rr(.35, .75), boardC(), rr(.45, .9));
          }
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
    if (f._top === 'logo' && f._logoCrop) {
      const c = f._logoCrop, k = Math.min((f._w - 10) / c.width, 26 / c.height);
      const lg = document.createElement('canvas'); lg.className = 'logo ' + (f._logoColor ? 'color' : 'mono'); lg.width = c.width; lg.height = c.height;
      lg.style.width = (c.width * k).toFixed(1) + 'px'; lg.style.height = (c.height * k).toFixed(1) + 'px';
      lg.getContext('2d').drawImage(c, 0, 0);
      b.append(lg);
    } else if (f._top === 'logo') {
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
    // room inside the case: its width less the side panels (padding) and the gap at each end of a shelf
    const cs = getComputedStyle(shelves), gap = parseFloat(cs.getPropertyValue('--end-gap')) || 16;
    const avail = shelves.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 2 * gap;
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
