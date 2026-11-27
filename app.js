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

  /* ---------- which shelf: /viewings/2025/, or /viewings/1990s/ for the Vault (the bare /viewings/ = the newest year) ---------- */
  // One data file and one ticket image per year. Add a year here (and its watched-<year>.png) to add a shelf.
  const SHELVES = { 2016: 'films-2016.json', 2017: 'films-2017.json', 2018: 'films-2018.json', 2019: 'films-2019.json', 2020: 'films-2020.json', 2021: 'films-2021.json', 2022: 'films-2022.json', 2023: 'films-2023.json', 2024: 'films-2024.json', 2025: 'films-2025.json', 2026: 'films.json' };
  // The Vault: films from the years that were rated in bulk (2007-2015), one shelf per decade of release.
  const VAULT = ['1930s', '1940s', '1950s', '1960s', '1970s', '1980s', '1990s', '2000s', '2010s'];
  VAULT.forEach((d) => { SHELVES[d] = `vault-${d}.json`; });
  const YEARS = [...VAULT, ...Object.keys(SHELVES).filter((k) => !VAULT.includes(k)).map(Number).sort((a, b) => a - b)];
  const NEWEST = YEARS[YEARS.length - 1];
  // The Whole Store (/viewings/all/): every tape from every shelf on one giant case, with divider cards between groups.
  // It has no data file of its own: it is built from all of them (so the VCR and Re-mark spine stay off there).
  const ALL = 'all';
  const NAV = [...YEARS, ALL]; // the arrows' order: 1930s ... 2010s, 2016 ... 2026, then the Whole Store
  // Each shelf has its own address, a folder with a copy of index.html carrying that shelf's link preview
  // (made by make-pages.py): /viewings/2025/, /viewings/1990s/, /viewings/all/, /viewings/search/?q=disney.
  // The newest year is the bare /viewings/. Old ?shelf= links still work and are rewritten to the folder form.
  // The copies have <base href="../">, so every relative path (files, fetches) resolves from the site's root.
  const ROOT = new URL('./', document.baseURI).pathname; // the site's root path, e.g. /viewings/
  const SEARCH = 'search';
  const PARAMS = new URLSearchParams(location.search);
  const SEG = decodeURIComponent((location.pathname.startsWith(ROOT) ? location.pathname.slice(ROOT.length) : '').split('/')[0]);
  const shelfKey = (p) => { if (p === ALL || p === SEARCH) return ALL; const k = VAULT.includes(p) ? p : Number(p); return SHELVES[k] ? k : null; };
  const SHELF = shelfKey(SEG) ?? shelfKey(PARAMS.get('shelf') || '') ?? NEWEST;
  const IN_VAULT = VAULT.includes(SHELF);
  const IN_ALL = SHELF === ALL;
  // A search shelf (/search/?q=disney): the Whole Store cut down to one search's results, titled with the search.
  const SEARCH_Q = IN_ALL ? (PARAMS.get('q') || '').trim() : '';
  const IN_SEARCH = !!SEARCH_Q;
  const shelfPath = (k, search) => (search ? `${ROOT}${SEARCH}/` : k === NEWEST ? ROOT : `${ROOT}${k}/`);
  const searchLink = (q) => `${shelfPath(ALL, true)}?q=${encodeURIComponent(q.trim())}`;
  (function canonicalAddress() { // an old ?shelf= link (or a stray param) becomes the shelf's own address
    const q = new URLSearchParams(location.search);
    q.delete('shelf');
    if (!IN_SEARCH) q.delete('q');
    const want = shelfPath(SHELF, IN_SEARCH);
    if (want === location.pathname && q.toString() === PARAMS.toString()) return;
    // the page stays as loaded, so pin relative paths to the root before the address moves
    if (!document.querySelector('base')) { const b = document.createElement('base'); b.href = ROOT; document.head.prepend(b); }
    const qs = q.toString();
    history.replaceState(null, '', want + (qs ? '?' + qs : '') + location.hash);
  })();
  const DATA_FILE = IN_ALL ? null : SHELVES[SHELF];
  const shelfName = (k) => (k === ALL ? 'All' : VAULT.includes(k) ? `Vault ${k}` : String(k));
  // The address of another shelf (keeping the sort where it means the same there), optionally with a tape pulled out.
  function shelfLink(y, tape) {
    const q = new URLSearchParams(location.search);
    q.delete('genre'); // genres differ from shelf to shelf
    q.delete('tape');
    q.delete('q'); // a search shelf's search stays behind
    q.delete('shelf');
    // The Vault and the year shelves sort differently by default, so the sort is dropped crossing between them.
    // The Whole Store takes every sort; leaving it keeps the sort unless the Vault has no such sort.
    const sort = q.get('sort') || '';
    const keep = y === ALL || (IN_ALL ? !(VAULT.includes(y) && sort.startsWith('watched')) : VAULT.includes(y) === IN_VAULT);
    if (!keep) q.delete('sort');
    if (tape) q.set('tape', tape);
    const qs = q.toString();
    return shelfPath(y) + (qs ? '?' + qs : '');
  }
  (function shelfHeader() {
    const h1 = document.querySelector('h1.ticket'), img = h1 && h1.querySelector('img');
    if (img && IN_ALL) { // the Whole Store: a plate like the Vault's, no footnote; a search shelf's plate reads the search
      img.remove();
      const plate = document.createElement('span'); plate.className = 'vault-plate all-plate'; plate.setAttribute('aria-hidden', 'true');
      if (IN_SEARCH) {
        plate.classList.add('search-plate');
        const v2 = document.createElement('span'); v2.className = 'v2'; v2.textContent = 'Search';
        const v1 = document.createElement('span'); v1.className = 'v1'; v1.textContent = SEARCH_Q;
        if (SEARCH_Q.length > 9) v1.style.fontSize = `clamp(26px, ${Math.max(3, 72 / SEARCH_Q.length)}vw, ${Math.max(30, Math.round(640 / SEARCH_Q.length))}px)`;
        plate.append(v2, v1);
      } else plate.innerHTML = '<span class="v2">The Whole</span><span class="v1">Store</span>';
      h1.prepend(plate); h1.classList.add('vault');
    } else if (img && IN_VAULT) { // no ticket for the Vault: a plate in the shelf's lettering instead
      img.remove();
      const plate = document.createElement('span'); plate.className = 'vault-plate'; plate.setAttribute('aria-hidden', 'true');
      plate.innerHTML = `<span class="v1">The Vault</span><span class="v2">${SHELF}</span>`;
      h1.prepend(plate); h1.classList.add('vault');
      // the asterisk: Vault tapes have no viewing date, so a footnote under the plate says why
      const ASTERISK = '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 5v30M7 12.5l26 15M7 27.5l26-15"/></svg>';
      const star = document.createElement('span'); star.className = 'vault-star'; star.innerHTML = ASTERISK;
      plate.append(star);
      const note = document.createElement('p'); note.className = 'vault-note';
      note.innerHTML = '<span class="mark">' + ASTERISK + '</span><span>Everything in the Vault was watched before 2016, back before I kept a diary. '
        + 'The dates are lost to time, so these tapes are shelved by the decade they came out.</span>';
      h1.closest('.ticket-row').after(note);
    } else if (img && SHELF !== NEWEST) { img.src = `watched-${SHELF}.png`; img.alt = `Watched ${SHELF}`; }
    $('year').textContent = IN_SEARCH ? `search: ${SEARCH_Q}` : IN_ALL ? 'the whole store' : IN_VAULT ? `the Vault, ${SHELF}` : SHELF;
    if (SHELF !== NEWEST) document.title = IN_SEARCH ? `Viewings: “${SEARCH_Q}”` : IN_ALL ? 'Viewings: the whole store' : IN_VAULT ? `Viewings: the Vault, ${SHELF}` : `Viewings ${SHELF}`;
    // arrows either side of the ticket: older shelf on the left, newer on the right
    const link = shelfLink;
    const i = NAV.indexOf(SHELF);
    [['shelf-prev', NAV[i - 1]], ['shelf-next', NAV[i + 1]]].forEach(([id, y]) => {
      const a = $(id);
      if (!a) return;
      if (y == null) { a.hidden = true; return; }
      a.href = link(y);
      a.querySelector('.yr').textContent = shelfName(y);
      a.setAttribute('aria-label', y === ALL ? 'The whole store: every tape' : `${shelfName(y)} shelf`);
      a.hidden = false;
    });
  })();
  let films = [];
  let spineEls = [];
  let current = -1;
  let order = [];      // indices into films, in shelf order, after sorting and the genre filter
  // The Vault and the Whole Store open by release year, oldest first (a walk from the 1930s to now).
  const VIEW_DEFAULT = IN_VAULT || IN_ALL ? { sort: 'year', dir: 1 } : { sort: 'watched', dir: 1 };
  const view = { ...VIEW_DEFAULT, genres: new Set() };

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

  // Designed spine pictures load only when their tape comes near the window (the big Vault shelves hold
  // hundreds of them, several MB in all). Without IntersectionObserver they load straight away.
  let spineSizes = null;
  const spineIO = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
    for (const e of es) if (e.isIntersecting) { const el = e.target; el.style.backgroundImage = `url("${el.dataset.bg}")`; spineIO.unobserve(el); }
  }, { rootMargin: '600px 0px' }) : null;
  const lazySpine = (el, src) => { if (spineIO) { el.dataset.bg = src; spineIO.observe(el); } else el.style.backgroundImage = `url("${src}")`; };
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

  async function prepare(f, drawn) {
    // A designed spine picture (posters/<name>-spine-b.jpg, made by spinegen/) is used when there is one;
    // films without one (new arrivals) keep the drawn spine below. A designed tape needs only its spine
    // picture, so the full poster isn't downloaded or analysed for it (that made the first load slow).
    // drawn=true (the Re-mark spine preview) always builds the drawn spine.
    f._spine = null;
    let si = null;
    if (f.poster) {
      const sp = f.poster.replace(/\.[a-z]+$/i, '-spine-b.jpg');
      // posters/spines.json (written by spinegen) gives every designed picture's size, so the tape can be
      // sized and shelved without downloading it; the picture itself loads when it scrolls near (lazySpine).
      const known = spineSizes && spineSizes[sp.replace(/^.*\/|-spine-b\.jpg$/g, '')];
      if (known && !drawn) si = { naturalWidth: known[0], naturalHeight: known[1] };
      else si = await loadImg(sp);
      if (si) f._spine = sp;
    }
    if (f._spine && !drawn) {
      const rt = f.runtime || (90 + hash(f.title) % 60);
      f._w = Math.round(Math.min(52, Math.max(42, 40 + (rt - 90) * 0.12)));
      f._r = hash(f.title + 'wear'); f._h = SPINE_H; f._dmg = []; f._top = ''; f._font = pickFont(f);
      // Spine pictures are saved at 550px for a 250px slipcase. A taller picture is a Disney/Pixar clamshell,
      // which is a bigger box: show it at the same scale, so it stands taller and thicker than its neighbours.
      f._clam = si.naturalHeight > 560;
      if (f._clam) { const k = SPINE_H / 550; f._w = Math.round(si.naturalWidth * k); f._h = Math.round(si.naturalHeight * k); }
      // A picture much wider than the runtime rule is a multi-tape box (The Brutalist's 2-tape set): as wide as its picture.
      else if (si.naturalWidth * SPINE_H / 550 > f._w * 1.4) f._w = Math.round(si.naturalWidth * SPINE_H / 550);
      f._c = '#222'; f._t = '#efe6d2';
      return;
    }
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
    if (f._spine && i >= 0) { // the designed picture carries its own lettering, wear and stickers
      b.className = 'spine designed' + (f._clam ? ' clam' : ''); // a clamshell's moulded corners are rounded (CSS)
      lazySpine(b, f._spine);
      b.addEventListener('click', () => openViewer(i));
      return b;
    }
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
    if (spineIO) spineEls.forEach((el) => spineIO.unobserve(el)); // the old spines are thrown away
    spineEls = films.map(spineEl);
    // room inside the case: its width less the side panels (padding) and the gap at each end of a shelf
    const cs = getComputedStyle(shelves), gap = parseFloat(cs.getPropertyValue('--end-gap')) || 16;
    const avail = shelves.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 2 * gap;
    // On the Whole Store a divider card goes in front of each group (decade, star rating, year watched...).
    // Items are film indices, or divider objects. A card never ends a row on its own: it moves down with its first tape.
    const items = [], groups = IN_ALL ? groupsOf(order) : null;
    order.forEach((i, n) => { if (groups && groups.starts.has(n)) items.push(groups.starts.get(n)); items.push(i); });
    const wOf = (it) => (typeof it === 'number' ? films[it]._w : DIVIDER_W);
    let row = [], used = 0, rows = [];
    items.forEach((it, n) => {
      const w = wOf(it), next = typeof it === 'number' ? 0 : wOf(items[n + 1] ?? it);
      if (used + w + next > avail && row.length) { rows.push(row); row = []; used = 0; }
      row.push(it); used += w;
    });
    if (row.length) rows.push(row);
    rows.forEach((r) => {
      const wrap = document.createElement('div'); wrap.className = 'shelf-row';
      const shelf = document.createElement('div'); shelf.className = 'shelf';
      r.forEach((it) => shelf.appendChild(typeof it === 'number' ? spineEls[it] : dividerEl(it)));
      const board = document.createElement('div'); board.className = 'board';
      wrap.append(shelf, board);
      shelves.appendChild(wrap);
    });
    if (current >= 0) spineEls[current].classList.add('out');
  }

  /* ---------- divider cards (the Whole Store) ---------- */
  // Like the section cards in a video store: one stands in front of each group of tapes, and the groups follow
  // the sort: decades of release, my star ratings, IMDb scores, or the year watched (the Vault first).
  const DIVIDER_W = 40;
  function groupKey(f) {
    switch (view.sort) {
      case 'year': { const d = Math.floor((f.year || 0) / 10) * 10; return { k: d, big: `${d}s`, small: 'Released in the' }; }
      case 'rating': {
        const r = Math.floor(r10(f));
        return r < 4 ? { k: 3, big: 'Under 4', small: 'My rating' } : { k: r, big: r === 10 ? '10' : `${r}`, small: 'My rating', stars: true };
      }
      case 'imdb': {
        if (f.imdbRating == null) return { k: -1, big: 'No score', small: 'IMDb' };
        const r = Math.floor(f.imdbRating);
        return r < 5 ? { k: 4, big: 'Under 5', small: 'IMDb' } : { k: r, big: `${r}`, small: 'IMDb' };
      }
      case 'gap': { // you vs IMDb, in whole points: +3 and up, +2, +1, even, -1, -2, -3 and down
        if (f.imdbRating == null) return { k: -99, big: 'No score', small: 'IMDb' };
        const d = Math.max(-3, Math.min(3, Math.round(gapOf(f))));
        return d === 0 ? { k: 0, big: 'Even', small: 'You and IMDb' }
          : { k: d, big: (d > 0 ? '+' : '') + d + (Math.abs(d) === 3 ? (d > 0 ? ' up' : '') : ''), small: d > 0 ? 'You liked it more' : 'IMDb liked it more' };
      }
      default: return f._vault ? { k: 0, big: 'Vault', small: 'Watched before 2016' } : { k: +String(f.watched).slice(0, 4), big: String(f.watched).slice(0, 4), small: 'Watched in' };
    }
  }
  function groupsOf(ord) {
    const starts = new Map();
    let cur = null;
    ord.forEach((i, n) => {
      const g = groupKey(films[i]);
      if (!cur || cur.k !== g.k) { cur = { ...g, n: 0 }; starts.set(n, cur); }
      cur.n++;
    });
    return { starts };
  }
  function dividerEl(g) {
    const d = document.createElement('div');
    d.className = 'divider' + (g.big.length > 5 ? ' long' : '');
    d.setAttribute('role', 'heading'); d.setAttribute('aria-level', '2');
    d.setAttribute('aria-label', `${g.small} ${g.big}${g.stars ? ' out of 10' : ''}: ${g.n} tape${g.n === 1 ? '' : 's'}`);
    const big = g.stars ? `${g.big}<i>&#9733;</i>` : g.big.replace(/(\d)s$/, '$1<small>s</small>');
    d.innerHTML = `<span class="tab">${g.n}</span><span class="txt"><span class="sm">${g.small}</span><span class="bg">${big}</span></span>`;
    return d;
  }

  /* ---------- sorting and the genre filter ---------- */
  const SORT_DEFAULT_DIR = { watched: 1, rating: -1, imdb: -1, year: -1, gap: -1 }; // oldest viewing first; best and newest first
  const r10 = (f) => (f.rating10 != null ? f.rating10 : (f.rating || 0) * 2);
  const gapOf = (f) => r10(f) - f.imdbRating; // you vs IMDb: above 0, you liked it more than IMDb's voters did
  // On the Whole Store, Vault tapes (no real viewing date) come before everything watched since 2016.
  const wkey = (f) => (f._vault ? '0' : f.watched || '');
  const byWatched = (a, b) => wkey(a).localeCompare(wkey(b));
  const SORTS = {
    watched: byWatched,
    rating: (a, b) => r10(a) - r10(b),
    // films without an IMDb score (new arrivals until it's filled in) go to the end either way
    imdb: (a, b) => (a.imdbRating == null) - (b.imdbRating == null) || view.dir * ((a.imdbRating || 0) - (b.imdbRating || 0)),
    year: (a, b) => (a.year || 0) - (b.year || 0) || byWatched(a, b),
    // you vs IMDb (Ian, 26 Nov 2026): first the films you liked most over IMDb, last the ones IMDb liked most over you
    gap: (a, b) => (a.imdbRating == null) - (b.imdbRating == null) || view.dir * (gapOf(a) - gapOf(b)),
  };

  function computeOrder() {
    const cmp = SORTS[view.sort];
    order = films.map((f, i) => i)
      .filter((i) => !view.genres.size || (films[i].genres || []).some((g) => view.genres.has(g)))
      // ties (same rating, same year) keep the order they were watched in
      .sort((a, b) => (view.sort === 'imdb' || view.sort === 'gap' ? cmp(films[a], films[b]) : view.dir * cmp(films[a], films[b])) || byWatched(films[a], films[b]));
  }

  function updateTally() {
    const n = order.length;
    $('count').textContent = n;
    $('tapes').textContent = n === 1 ? 'Tape' : 'Tapes';
  }

  function saveView() { // in the address bar, so a sorted/filtered shelf can be shared or bookmarked
    const q = new URLSearchParams(location.search);
    const def = view.sort === VIEW_DEFAULT.sort && view.dir === VIEW_DEFAULT.dir;
    if (def) q.delete('sort'); else q.set('sort', view.sort + (view.dir === SORT_DEFAULT_DIR[view.sort] ? '' : '-rev'));
    if (view.genres.size) q.set('genre', [...view.genres].join(',')); else q.delete('genre');
    const qs = q.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }

  function loadView() {
    const q = new URLSearchParams(location.search);
    const m = /^(watched|rating|imdb|year|gap)(-rev)?$/.exec(q.get('sort') || '');
    if (m && !(IN_VAULT && m[1] === 'watched')) { view.sort = m[1]; view.dir = SORT_DEFAULT_DIR[m[1]] * (m[2] ? -1 : 1); }
    (q.get('genre') || '').split(',').filter(Boolean).forEach((g) => view.genres.add(g));
  }

  function applyView() {
    if (current >= 0 && !order.includes(current)) closeViewer();
    computeOrder();
    updateTally();
    renderControls();
    layout();
    saveView();
  }

  const controls = $('controls'), genreBtn = $('genre-btn'), genreList = $('genre-list');
  // Vault tapes have no viewing date (their dates are when they were rated in bulk), so no "Date watched" sort there
  if (IN_VAULT) controls.querySelector('[data-sort="watched"]').remove();

  function renderControls() {
    controls.querySelectorAll('[data-sort]').forEach((b) => {
      const on = b.dataset.sort === view.sort;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on);
      const arrow = view.sort === 'watched' ? (view.dir > 0 ? '\u2191' : '\u2193') : (view.dir < 0 ? '\u2193' : '\u2191');
      b.dataset.arrow = on ? arrow : '';
      b.title = on ? 'Click again to reverse' : '';
    });
    // genres present on the shelf, most common first
    const counts = new Map();
    films.forEach((f) => (f.genres || []).forEach((g) => counts.set(g, (counts.get(g) || 0) + 1)));
    [...view.genres].forEach((g) => { if (!counts.has(g)) view.genres.delete(g); });
    const list = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    genreList.textContent = '';
    const all = document.createElement('button');
    all.type = 'button'; all.className = 'all' + (view.genres.size ? '' : ' on'); all.textContent = 'All';
    all.addEventListener('click', () => { view.genres.clear(); applyView(); });
    genreList.append(all);
    list.forEach(([g, n]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = view.genres.has(g) ? 'on' : '';
      b.setAttribute('aria-pressed', view.genres.has(g));
      b.innerHTML = `${g} <small>${n}</small>`;
      b.addEventListener('click', () => { view.genres.has(g) ? view.genres.delete(g) : view.genres.add(g); applyView(); });
      genreList.append(b);
    });
    const sel = [...view.genres];
    $('genre-sel').textContent = !sel.length ? 'All' : sel.length <= 2 ? sel.join(' + ') : `${sel.length} picked`;
    genreBtn.classList.toggle('on', sel.length > 0);
  }

  controls.querySelectorAll('[data-sort]').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.sort;
    if (view.sort === k) view.dir *= -1; else { view.sort = k; view.dir = SORT_DEFAULT_DIR[k]; }
    applyView();
  }));
  function setGenreOpen(open) {
    genreList.hidden = !open; genreBtn.setAttribute('aria-expanded', open);
  }
  genreBtn.addEventListener('click', () => setGenreOpen(genreList.hidden));
  genreList.addEventListener('click', (e) => e.stopPropagation()); // the chips are redrawn on click, so the outside-click check below can't see them
  document.addEventListener('click', (e) => { if (!e.target.closest('.genre-pick')) setGenreOpen(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !genreList.hidden) { setGenreOpen(false); genreBtn.focus(); } });

  /* ---------- viewer ---------- */
  const viewer = $('viewer'), cover = $('cover');

  function imdbUrl(f) {
    return f.imdb ? `https://www.imdb.com/title/${f.imdb}/` : `https://www.imdb.com/find/?q=${encodeURIComponent(f.title + ' ' + f.year)}`;
  }

  // Ratings are out of 10 (PassThePopcorn), shown as ten stars: 8.5 -> eight full stars and a half.
  // Films from the old Letterboxd import only have "rating" (out of 5), doubled here.
  function stars(f) {
    const r10 = f.rating10 != null ? f.rating10 : (f.rating || 0) * 2, r = Math.round(r10 * 2) / 2;
    let h = '';
    for (let i = 1; i <= 10; i++) h += `<span class="star ${r >= i ? 'full' : r >= i - .5 ? 'half' : ''}">&#9733;</span>`;
    return `<span class="stars" role="img" aria-label="${r10 ? +r10.toFixed(1) : 'No rating'} out of 10">${h}</span>`
      + `<small>${r10 ? +r10.toFixed(1) : '—'} / 10</small>`;
  }

  function fmtDate(iso) {
    const d = new Date(iso + 'T12:00:00');
    return isNaN(d) ? iso : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function fill(i) {
    const f = films[i];
    document.body.classList.toggle('designed-spine', !!f._spine); // hides "Re-mark spine": it only changes drawn spines
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
    const g = f.imdbRating != null ? Math.round(gapOf(f) * 10) / 10 : null;
    $('v-imdb').textContent = f.imdbRating != null ? `IMDb ${f.imdbRating.toFixed(1)}${g ? ` \u00b7 you ${g > 0 ? '+' : ''}${g.toFixed(1)}` : ' \u00b7 you agree'}` : '';
    // Vault dates are when the film was rated in bulk, not watched (see the Vault note in the header)
    $('v-watched').textContent = IN_VAULT || f._vault ? 'Watched before 2016' : `Watched ${fmtDate(f.watched)}${f.rewatch ? ' (rewatch)' : ''}`;
    $('v-genres').innerHTML = (f.genres || []).map((g) => `<span>${g}</span>`).join('');
    $('v-note').textContent = f.note || '';
    $('v-play').hidden = !f.trailer;
  }

  /* ---------- sound: the trailer deck's clunks and clicks, synthesised with Web Audio (no sound files) ---------- */
  let actx = null, noise = null;
  function audio() {
    if (!actx) {
      actx = new (window.AudioContext || window.webkitAudioContext)();
      noise = actx.createBuffer(1, actx.sampleRate * 2, actx.sampleRate); // 2s of white noise, reused for every scrape and hiss
      const d = noise.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    if (actx.state === 'suspended') actx.resume();
    return actx;
  }
  function burst(c, at, dur, type, freq, q, peak, out = c.destination) { // a shaped slice of filtered noise
    const n = c.createBufferSource(); n.buffer = noise;
    const f = c.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(peak, at + Math.min(.015, dur / 4)); g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    n.connect(f).connect(g).connect(out); n.start(at, Math.random() * 1.5, dur + .05);
  }
  function thump(c, at, f0, f1, dur, peak) { // a damped knock of hollow plastic
    const o = c.createOscillator(); o.type = 'triangle';
    o.frequency.setValueAtTime(f0, at); o.frequency.exponentialRampToValueAtTime(f1, at + dur);
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(peak, at + .006); g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    o.connect(g).connect(c.destination); o.start(at); o.stop(at + dur + .02);
  }
  const SFX = {
    // a deck key: a short plastic click
    key(c, t) { thump(c, t, 1400, 700, .03, .12); burst(c, t, .02, 'highpass', 4000, .7, .05); },
    // the VCR takes the tape: clunk, the motor spins up and runs, then a click as the heads engage
    load(c, t) {
      burst(c, t, .12, 'bandpass', 1800, 1, .07); thump(c, t + .1, 120, 60, .25, .4);
      const o = c.createOscillator(); o.type = 'sawtooth';
      o.frequency.setValueAtTime(35, t + .3); o.frequency.exponentialRampToValueAtTime(95, t + 1.1);
      const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 500;
      const g = c.createGain(); g.gain.setValueAtTime(0.0001, t + .3); g.gain.exponentialRampToValueAtTime(.05, t + .7); g.gain.setValueAtTime(.05, t + 1.5); g.gain.exponentialRampToValueAtTime(0.0001, t + 2);
      o.connect(lp).connect(g).connect(c.destination); o.start(t + .3); o.stop(t + 2.05);
      burst(c, t + .3, 1.7, 'bandpass', 950, 2.5, .025);
      thump(c, t + 1.85, 900, 500, .05, .18);
    },
    // eject: a motor whine and the tape popping back up
    eject(c, t) {
      const o = c.createOscillator(); o.type = 'square'; o.frequency.setValueAtTime(70, t); o.frequency.linearRampToValueAtTime(140, t + .45);
      const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 400;
      const g = c.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(.03, t + .1); g.gain.exponentialRampToValueAtTime(0.0001, t + .5);
      o.connect(lp).connect(g).connect(c.destination); o.start(t); o.stop(t + .55);
      thump(c, t + .48, 160, 70, .18, .3);
    },
  };
  function sfx(name) { try { const c = audio(); SFX[name](c, c.currentTime + .01); } catch { /* no audio: carry on silently */ } }

  /* ---------- the trailer: into the VCR, onto the CRT ---------- */
  // `trailer` on a film is a YouTube id (from TMDB's trailer list, 26 Nov 2026). The Play button shows only when there is one.
  const tv = $('tv'), tvScreen = $('tv-screen'), vcrTitle = $('vcr-title'), vcrDisplay = $('vcr-display'), vcrIco = $('vcr-ico');
  let tvTimer = null, tvFocus = null, tvFlash = null;
  // The deck's keys drive the YouTube player through its postMessage API (enablejsapi=1): the player reports
  // its time and state back, which runs the counter on the display.
  const yt = { t: 0, state: -1, frame: null };
  const ICO = { play: '\u25B6', rew: '\u25C0\u25C0', ff: '\u25B6\u25B6', stop: '\u25A0' };
  let mode = 'play';
  const clock = (t) => { t = Math.max(0, Math.floor(t)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`; };
  function show(text, ms) { // the display: the counter, or a word for a moment
    clearTimeout(tvFlash);
    vcrDisplay.classList.remove('blink');
    if (text != null) { vcrDisplay.textContent = text; if (ms) tvFlash = setTimeout(() => { tvFlash = null; show(); }, ms); return; }
    if (!tvFlash && tv.classList.contains('playing')) vcrDisplay.textContent = clock(yt.t);
  }
  function setMode(m) {
    mode = m; vcrIco.textContent = ICO[m] || ICO.play;
    tv.querySelectorAll('.deck-keys [data-k]').forEach((b) => b.classList.toggle('on', b.dataset.k === m && tv.classList.contains('on')));
  }
  function ytCmd(func, args = []) { if (yt.frame) yt.frame.contentWindow.postMessage(JSON.stringify({ event: 'command', func, args, id: 1, channel: 'widget' }), '*'); }
  window.addEventListener('message', (e) => {
    if (!yt.frame || e.source !== yt.frame.contentWindow) return;
    let d; try { d = typeof e.data === 'string' ? JSON.parse(e.data) : e.data; } catch { return; }
    const info = d && d.info;
    if (!info || typeof info !== 'object') return;
    if (typeof info.currentTime === 'number') yt.t = info.currentTime;
    if (typeof info.playerState === 'number') {
      yt.state = info.playerState;
      if (yt.state === 1 && mode === 'stop') setMode('play'); // played from the picture itself
      if (yt.state === 2 && mode === 'play') setMode('stop');
      if (yt.state === 0) { setMode('stop'); show('END', 2500); } // the trailer ran out
    }
    show();
  });
  const KEYS = {
    play() { if (!tv.classList.contains('playing')) return; ytCmd('playVideo'); setMode('play'); show('PLAY', 900); },
    stop() { if (!tv.classList.contains('playing')) return; ytCmd('pauseVideo'); setMode('stop'); show('STOP', 900); },
    rew() { if (!tv.classList.contains('playing')) return; ytCmd('seekTo', [Math.max(0, yt.t - 10), true]); yt.t = Math.max(0, yt.t - 10); setMode('rew'); show('REW', 700); setTimeout(() => mode === 'rew' && setMode(yt.state === 2 ? 'stop' : 'play'), 700); },
    ff() { if (!tv.classList.contains('playing')) return; ytCmd('seekTo', [yt.t + 10, true]); yt.t += 10; setMode('ff'); show('FF', 700); setTimeout(() => mode === 'ff' && setMode(yt.state === 2 ? 'stop' : 'play'), 700); },
    eject() { closeTrailer(); },
    rec() { show('NO TAB', 1600); }, // a rental tape: the record tab is broken off
  };
  tv.querySelectorAll('.deck-keys [data-k]').forEach((b) => b.addEventListener('click', () => { if (b.dataset.k !== 'eject') sfx('key'); KEYS[b.dataset.k](); }));
  function openTrailer(f) {
    if (!f || !f.trailer || !tv.hidden) return;
    tvFocus = document.activeElement;
    tv.hidden = false; tv.classList.remove('playing', 'on'); document.body.classList.add('store-open');
    vcrTitle.textContent = f.title; // written on the cassette's label in marker
    vcrTitle.style.fontSize = Math.min(1.35, 21 / (0.7 * Math.max(f.title.length, 1))).toFixed(2) + 'cqw'; // long titles in a smaller hand
    show('LOAD'); setMode('play'); yt.t = 0; yt.state = -1; yt.frame = null;
    tvScreen.querySelector('iframe')?.remove();
    void tv.offsetWidth; tv.classList.add('loading'); // the tape slides into the slot
    sfx('load');
    tv.querySelector('.tv-x').focus({ preventScroll: true });
    clearTimeout(tvTimer);
    tvTimer = setTimeout(() => {
      tv.classList.add('on'); show('PLAY'); setMode('play'); // static, then the picture
      tvTimer = setTimeout(() => {
        const fr = document.createElement('iframe');
        fr.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(f.trailer)}?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1&origin=${encodeURIComponent(location.origin)}`;
        fr.addEventListener('load', () => { yt.frame = fr; fr.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 1, channel: 'widget' }), '*'); });
        fr.title = `${f.title}: trailer`;
        fr.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
        fr.allowFullscreen = true;
        tvScreen.prepend(fr);
        tv.classList.add('playing');
      }, 700);
    }, 1500);
  }
  function closeTrailer() {
    if (tv.hidden) return;
    clearTimeout(tvTimer);
    tvScreen.querySelector('iframe')?.remove();
    tv.classList.remove('loading', 'on', 'playing');
    yt.frame = null; setMode('play');
    clearTimeout(tvFlash); tvFlash = null;
    vcrDisplay.textContent = '12:00'; vcrDisplay.classList.add('blink'); // nobody ever set the clock
    tv.hidden = true;
    if (current < 0 && receipt.hidden && store.hidden) document.body.classList.remove('store-open');
    sfx('eject');
    if (tvFocus && tvFocus.focus) tvFocus.focus({ preventScroll: true });
  }
  tv.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeTrailer));
  $('v-play').addEventListener('click', () => openTrailer(films[current]));
  document.addEventListener('keydown', (e) => { if (!tv.hidden && e.key === 'Escape') { e.stopPropagation(); closeTrailer(); } }, true);

  function openViewer(i) {
    const el = spineEls[i];
    el.classList.add('pulling');
    setTimeout(() => {
      el.classList.remove('pulling'); el.classList.add('out');
      current = i; fill(i); setTapeParam(films[i]);
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
    setTapeParam(null);
  }

  function step(d) {
    if (current < 0) return;
    const p = order.indexOf(current);
    if (p < 0 || order.length < 2) return;
    const n = order[(p + d + order.length) % order.length];
    spineEls[current].classList.remove('out');
    current = n; spineEls[n].classList.add('out'); fill(n); setTapeParam(films[n]);
  }

  $('close').addEventListener('click', closeViewer);
  $('backdrop').addEventListener('click', closeViewer);
  $('prev').addEventListener('click', () => step(-1));
  $('next').addEventListener('click', () => step(1));
  document.addEventListener('keydown', (e) => {
    if (current < 0 || !store.hidden || !tv.hidden) return; // the store directory, when open, sits over the viewer and has the keys
    if (e.key === 'Escape') closeViewer();
    else if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
  });
  // clicking empty space around the cover (but not the info panel) also closes
  document.querySelector('.panel').addEventListener('click', (e) => {
    if (e.target.classList.contains('panel')) closeViewer();
  });

  /* ---------- the whole store: tape links, the store directory (every shelf + search) and Surprise me ---------- */
  // A tape's id in links (?tape=tt0181875): its IMDb id. Every film has one; the poster path is a fallback.
  const tapeId = (f) => f.imdb || f.poster || f.title;

  function setTapeParam(f) { // keep ?tape= in the address bar in step with the tape that's pulled out
    const q = new URLSearchParams(location.search);
    if (f) q.set('tape', tapeId(f)); else q.delete('tape');
    const qs = q.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }

  // Pull a tape on this shelf out by id. Clears the genre filter if it hides the tape. False if it isn't here.
  function pullOut(id, instant) {
    const i = films.findIndex((f) => tapeId(f) === id);
    if (i < 0) return false;
    if (!order.includes(i)) { view.genres.clear(); applyView(); }
    spineEls[i].scrollIntoView({ block: 'center', behavior: instant ? 'auto' : 'smooth' });
    if (current === i) return true;
    if (current >= 0) { spineEls[current].classList.remove('out'); current = i; spineEls[i].classList.add('out'); fill(i); setTapeParam(films[i]); }
    else openViewer(i);
    return true;
  }

  // Every tape in the store, loaded the first time the directory opens (all the shelf files: about 1MB, cached after).
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/&/g, ' and ').replace(/['’.]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  let storeP = null, stock = null;
  // The studio is searchable too, so "disney" finds every Disney film. Pixar counts as Disney, and so do
  // Disney releases whose TMDB studio is someone else's (James and the Giant Peach: Allied Filmmakers).
  const DISNEY_TOO = new Set(['tt0116683']);
  // Series words, searched like a studio (every match shown, in release order): "bond", "james bond", "007",
  // "indiana jones" / "indy" (Raiders has neither in its title), "mission impossible".
  // Keyed by IMDb id, since the studio can't tell (EON also made Film Stars Don't Die in Liverpool).
  // Add a new film's id to its series when it reaches a shelf.
  const SERIES = [
    ['james bond 007', ['tt0113189', 'tt0143145', 'tt0246460', 'tt0381061', 'tt1074638', 'tt2382320']],
    ['indiana jones indy', ['tt0082971', 'tt0097576']],
    ['mission impossible', ['tt1229238', 'tt2381249']],
  ].flatMap(([w, ids]) => ids.map((id) => [id, w]));
  const SERIES_OF = new Map(SERIES);
  const studioWords = (f) => {
    let st = norm(f.studio);
    if (!/disney/.test(st) && (/pixar/.test(st) || DISNEY_TOO.has(f.imdb))) st += ' disney';
    return SERIES_OF.has(f.imdb) ? `${st} ${SERIES_OF.get(f.imdb)}` : st;
  };
  function loadStore() {
    return storeP || (storeP = Promise.all(YEARS.map(async (k) => {
      try {
        const d = await (await fetch(SHELVES[k])).json();
        return (d.films || []).map((f) => {
          const t = norm(f.title), dn = norm(f.director), st = studioWords(f);
          return { k, f, t, bare: t.replace(/^(the|a|an) /, ''), d: dn, st, hay: `${t} ${dn} ${f.year || ''} ${st}` };
        });
      } catch { return []; }
    })).then((a) => { stock = a; return a; }));
  }

  // Easter eggs: an exact query (after norm) that returns a hand-picked set, all of it, in release order.
  const EGGS = { 'daughter fucker': (e) => /\bwoody allen\b/.test(e.d) };
  function search(q, every) {
    const nq = norm(q);
    if (!nq || !stock) return { hits: [], total: 0 };
    if (EGGS[nq]) {
      const hits = stock.flat().filter(EGGS[nq]).sort((a, b) => (a.f.year || 0) - (b.f.year || 0) || a.bare.localeCompare(b.bare));
      return { hits, total: hits.length };
    }
    const words = nq.split(' '), isYear = /^(19|20)\d\d$/.test(nq), hits = [];
    stock.flat().forEach((e) => {
      // numbers match from the start of a word, so "007" doesn't find every 2007 film
      if (!words.every((w) => (/^\d+$/.test(w) ? (' ' + e.hay).includes(' ' + w) : e.hay.includes(w)))) return;
      const s = e.t === nq || e.bare === nq ? 100
        : e.t.startsWith(nq) || e.bare.startsWith(nq) ? 80
        : isYear && String(e.f.year) === nq ? 70
        : (' ' + e.t).includes(' ' + nq) ? 60
        : e.t.includes(nq) ? 50
        : (' ' + e.d).includes(' ' + nq) ? 45
        : (' ' + e.st).includes(' ' + nq) ? 40
        : 20;
      hits.push([s, e]);
    });
    // Studio matches (a whole studio's tapes) come in release order and are all shown, however many.
    hits.sort((a, b) => b[0] - a[0]
      || (a[0] === 40 ? (a[1].f.year || 0) - (b[1].f.year || 0) || a[1].bare.localeCompare(b[1].bare)
        : a[1].bare.localeCompare(b[1].bare) || (a[1].f.year || 0) - (b[1].f.year || 0)));
    const nst = hits.filter((h) => h[0] === 40).length;
    const cap = nst ? Math.min(60, hits.filter((h) => h[0] > 40).length) + nst : 60;
    return { hits: (every ? hits : hits.slice(0, cap)).map((h) => h[1]), total: hits.length };
  }

  const store = $('store'), storeQ = $('store-q'), storeHits = $('store-results'), aisles = $('store-aisles');
  let lastFocus = null, sel = -1;
  const shortName = (k) => (VAULT.includes(k) ? `Vault ${k}` : String(k));

  // Go to a tape anywhere in the store: pull it out here, or load its shelf with it pulled out.
  // every tape is on the Whole Store; a search shelf has only its results
  const isHere = (k, f) => (IN_SEARCH ? films.some((x) => tapeId(x) === tapeId(f)) : IN_ALL || k === SHELF);
  function goTo(k, f) {
    if (isHere(k, f)) { closeStore(); pullOut(tapeId(f)); }
    else location.href = shelfLink(k, tapeId(f));
  }

  function renderAisles() {
    const tile = (k) => {
      const n = stock ? stock[YEARS.indexOf(k)].length : null;
      const here = k === SHELF;
      return `<a class="bay${here ? ' here' : ''}" href="${shelfLink(k)}"${here ? ' aria-current="page"' : ''}>`
        + `<span class="nm">${VAULT.includes(k) ? k.replace('s', '<small>s</small>') : k}</span>`
        + `<span class="n">${n == null ? '&nbsp;' : `${n} tape${n === 1 ? '' : 's'}`}</span>`
        + (here ? '<span class="you">You are here</span>' : '') + '</a>';
    };
    const total = stock ? stock.flat().length : null;
    const allHere = IN_ALL && !IN_SEARCH && view.sort !== 'gap';
    $('aisle-all').innerHTML = `<a class="bay all${allHere ? ' here' : ''}" href="${shelfLink(ALL)}"${allHere ? ' aria-current="page"' : ''}>`
      + '<span class="nm">The Whole Store</span>'
      + `<span class="n">${total == null ? '&nbsp;' : `Every tape, ${total.toLocaleString('en-US')} of them, on one case`}</span>`
      + (allHere ? '<span class="you">You are here</span>' : '') + '</a>';
    const vsHere = IN_ALL && !IN_SEARCH && view.sort === 'gap';
    $('aisle-all').innerHTML += `<a class="bay all vs${vsHere ? ' here' : ''}" href="${shelfPath(ALL)}?sort=gap">`
      + '<span class="nm">You vs IMDb</span>'
      + '<span class="n">Every tape by how far my rating is from IMDb\u2019s: my soft spots first</span>'
      + (vsHere ? '<span class="you">You are here</span>' : '') + '</a>';
    $('aisle-vault').innerHTML = VAULT.map(tile).join('');
    $('aisle-years').innerHTML = YEARS.filter((k) => !VAULT.includes(k)).slice().reverse().map(tile).join('');
    $('store-total').textContent = stock ? `${stock.flat().length.toLocaleString('en-US')} tapes on ${YEARS.length} shelves` : '';
  }

  function renderHits() {
    const q = storeQ.value.trim();
    aisles.hidden = !!q; storeHits.hidden = !q; storeQ.setAttribute('aria-expanded', !!q);
    sel = -1; storeHits.classList.remove('picking');
    if (!q) return;
    if (!stock) { storeHits.innerHTML = '<p class="none">Checking the shelves...</p>'; return; }
    const { hits, total } = search(q);
    if (!hits.length) { storeHits.innerHTML = `<p class="none">Nothing on the shelves for “${q.replace(/[<&]/g, '')}”.</p>`; return; }
    const esc0 = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const shelfIt = `<a class="to-shelf" href="${esc0(searchLink(q))}"><span>Put all ${total.toLocaleString('en-US')} on a shelf</span><kbd>Enter</kbd></a>`;
    storeHits.innerHTML = shelfIt + hits.map((e, j) => {
      const f = e.f, sp = f.poster ? f.poster.replace(/\.[a-z]+$/i, '-spine-b.jpg') : '';
      const r10 = f.rating10 != null ? f.rating10 : (f.rating || 0) * 2;
      const facts = [f.year, f.director ? `dir. ${f.director}` : null].filter(Boolean).join(' · ');
      const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      return `<a class="hit" role="option" id="hit-${j}" data-j="${j}" href="${shelfLink(e.k, tapeId(f))}">`
        + `<span class="sp">${sp ? `<img src="${esc(sp)}" alt="" loading="lazy" onerror="this.remove()">` : ''}</span>`
        + `<span class="tx"><b>${esc(f.title)}</b><small>${esc(facts)}</small></span>`
        + `<span class="mine" title="My rating">${r10 ? +r10.toFixed(1) : '—'}<small>/10</small></span>`
        + `<span class="where${isHere(e.k, e.f) ? ' here' : ''}">${IN_SEARCH && isHere(e.k, e.f) ? 'This shelf' : e.k === SHELF ? 'This shelf' : shortName(e.k)}</span></a>`;
    }).join('') + (total > hits.length ? `<p class="none">${total - hits.length} more: keep typing to narrow it down.</p>` : '');
    storeHits._hits = hits;
  }

  // -1 is the "put them all on a shelf" button at the top (what Enter does when no tape is picked)
  function markSel(j) {
    const els = storeHits.querySelectorAll('.hit');
    if (!els.length) return;
    sel = j < -1 ? els.length - 1 : j >= els.length ? -1 : j;
    els.forEach((el, n) => el.classList.toggle('sel', n === sel));
    storeHits.classList.toggle('picking', sel >= 0);
    (sel >= 0 ? els[sel] : storeHits.querySelector('.to-shelf')).scrollIntoView({ block: 'nearest' });
    if (sel >= 0) storeQ.setAttribute('aria-activedescendant', `hit-${sel}`); else storeQ.removeAttribute('aria-activedescendant');
  }

  function openStore(focusSearch) {
    if (store.hidden) {
      lastFocus = document.activeElement;
      store.hidden = false; document.body.classList.add('store-open');
      renderAisles();
      loadStore().then(() => { renderAisles(); renderHits(); });
    }
    if (focusSearch || !matchMedia('(hover: none)').matches) storeQ.focus(); // phones: don't throw the keyboard up unasked
  }
  function closeStore() {
    if (store.hidden) return;
    store.hidden = true; document.body.classList.remove('store-open');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  async function surprise() {
    const all = (await loadStore()).flat().filter((e) => !(isHere(e.k, e.f) && current >= 0 && tapeId(e.f) === tapeId(films[current])));
    const e = all[Math.floor(Math.random() * all.length)];
    if (e) goTo(e.k, e.f);
  }

  storeQ.addEventListener('input', renderHits);
  storeQ.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); markSel(sel + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); markSel(sel - 1); }
    else if (e.key === 'Enter') { // a result picked with the arrows pulls that tape out; otherwise every result goes on a shelf
      const hits = storeHits._hits || [], q = storeQ.value.trim();
      if (storeHits.hidden || !hits.length) return;
      e.preventDefault();
      if (sel >= 0) goTo(hits[sel].k, hits[sel].f);
      else location.href = searchLink(q);
    }
  });
  storeHits.addEventListener('click', (e) => {
    const a = e.target.closest('.hit');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return; // let a new-tab click through
    const h = storeHits._hits[+a.dataset.j];
    if (isHere(h.k, h.f)) { e.preventDefault(); goTo(h.k, h.f); }
  });
  aisles.addEventListener('click', (e) => { // this shelf's tile just closes the directory
    const a = e.target.closest('.bay.here');
    if (a) { e.preventDefault(); closeStore(); }
  });
  store.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeStore));
  $('store-lucky').addEventListener('click', surprise);
  $('find-btn').addEventListener('click', () => openStore(true));
  $('lucky-btn').addEventListener('click', surprise);
  const ticket = document.querySelector('h1.ticket');
  ticket.tabIndex = 0; ticket.setAttribute('role', 'button'); ticket.title = 'All shelves';
  ticket.setAttribute('aria-label', `Store directory (now showing ${IN_ALL ? 'the whole store' : IN_VAULT ? `the Vault, ${SHELF}` : SHELF})`);
  ticket.addEventListener('click', () => openStore());
  ticket.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openStore(); } });

  // Keys: "/" finds a tape, "[" and "]" step to the shelf before / after. Esc closes the directory (before the viewer).
  document.addEventListener('keydown', (e) => {
    if (!store.hidden && e.key === 'Escape') {
      e.stopPropagation();
      if (storeQ.value && document.activeElement === storeQ) { storeQ.value = ''; renderHits(); } else closeStore();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (document.querySelector('.vcr.open') || !$('receipt').hidden || !$('tv').hidden) return;
    if (e.key === '/') { e.preventDefault(); openStore(true); }
    else if ((e.key === '[' || e.key === ']') && store.hidden) {
      const a = $(e.key === '[' ? 'shelf-prev' : 'shelf-next');
      if (a && !a.hidden && a.href) location.href = a.href;
    }
  }, true);

  /* ---------- the receipt: a year shelf's rentals itemised on thermal paper, with the year's totals ---------- */
  // Year shelves only (the Vault has no viewing dates). Opened by the Receipt button; ?receipt in the address opens it
  // on load, so the link can be shared. Built from `films` (the whole year, whatever the sort or genre filter).
  const receipt = $('receipt'), paper = $('receipt-paper');
  const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const MONTH_NAMES = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
  const escR = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  const fmtR = (v) => (Number.isInteger(v) ? `${v}.0` : String(v));
  const mmdd = (iso) => (iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)}` : '--/--');

  function receiptHTML() {
    const year = Number(SHELF), list = films.slice().sort((a, b) => (a.watched || '').localeCompare(b.watched || ''));
    const n = list.length;
    const mins = list.reduce((s, f) => s + (f.runtime || 0), 0);
    const avg = n ? list.reduce((s, f) => s + r10(f), 0) / n : 0;
    const best = list.slice().sort((a, b) => r10(b) - r10(a) || (b.imdbVotes || 0) - (a.imdbVotes || 0))[0];
    const worst = list.slice().sort((a, b) => r10(a) - r10(b) || (b.imdbVotes || 0) - (a.imdbVotes || 0))[0];
    const tally = (key) => { const m = new Map(); list.forEach((f) => key(f).forEach((k) => k && m.set(k, (m.get(k) || 0) + 1))); return [...m].sort((a, b) => b[1] - a[1]); };
    const dirs = tally((f) => String(f.director || '').split(',').map((d) => d.trim()));
    const genres = tally((f) => f.genres || []);
    const months = tally((f) => [f.watched ? Number(f.watched.slice(5, 7)) - 1 : null].filter((m) => m != null));
    const oldest = list.filter((f) => f.year).sort((a, b) => a.year - b.year)[0];
    const longest = list.filter((f) => f.runtime).sort((a, b) => b.runtime - a.runtime)[0];
    const gap = (f) => r10(f) - f.imdbRating;
    const scored = list.filter((f) => f.imdbRating);
    // the you-vs-IMDb picks skip a tape already named above (the staff pick, the one not to rent)
    const loved = scored.filter((f) => f !== best).sort((a, b) => gap(b) - gap(a))[0];
    const cold = scored.filter((f) => f !== worst).sort((a, b) => gap(a) - gap(b))[0];
    const last = list.length ? list[list.length - 1].watched : null;
    const thisYear = year === new Date().getFullYear();
    const now = new Date(), today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`; // local date, not UTC
    const printed = thisYear ? today : `${year}-12-31`;
    const period = thisYear && last ? `JAN 01 - ${MONTHS[Number(last.slice(5, 7)) - 1]} ${last.slice(8, 10)} ${year}` : `JAN 01 - DEC 31 ${year}`;
    const hm = `${Math.floor(mins / 60)}H ${String(mins % 60).padStart(2, '0')}M`;
    const row = (l, r, cls = '') => `<div class="r-row ${cls}"><span class="r-l">${l}</span><span class="r-r">${r}</span></div>`;
    const pick = (label, f, right) => (f ? `<div class="r-pick"><div class="r-k">${label}</div>${row(escR(f.title), right)}</div>` : '');
    const signed = (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}`;
    // a barcode from the year and the count: bars of 1-3 units, seeded so a year always prints the same
    let seed = year * 131 + n * 7, bars = '', x = 0;
    for (let i = 0; i < 46; i++) { seed = (seed * 1103515245 + 12345) & 0x7fffffff; const w = 1 + (seed >> 8) % 3; if (i % 2 === 0) bars += `<rect x="${x}" width="${w}" height="40"/>`; x += w; }
    return `
      <div class="r-head">
        <div class="r-store">VIEWINGS VIDEO</div>
        <div>RENTALS &middot; RETURNS &middot; REWINDS</div>
        <div>IANANDREU.COM/VIEWINGS</div>
      </div>
      <div class="r-rule"></div>
      ${row('MEMBER', 'IAN A.')}${row('ACCT', '#00087')}${row('DATE', `${mmdd(printed)}/${printed.slice(0, 4)}`)}
      <div class="r-c r-period">YEAR IN REVIEW<br>${period}</div>
      <div class="r-rule"></div>
      ${row('DATE&nbsp; TITLE', 'RATING', 'r-colhead')}
      ${list.map((f) => row(`<span class="r-d">${mmdd(f.watched)}</span>${escR(f.title.toUpperCase())}`, fmtR(r10(f)), 'r-item')).join('')}
      <div class="r-rule"></div>
      ${row('TAPES RENTED', n, 'r-big')}
      ${mins ? row('TIME IN FRONT OF THE TV', hm) : ''}
      ${row('AVERAGE RATING', avg.toFixed(1))}
      ${dirs.length && dirs[0][1] > 1 ? row('TOP DIRECTOR', `${escR(dirs[0][0].toUpperCase())} x${dirs[0][1]}`) : ''}
      ${genres.length ? row('FAVOURITE AISLE', `${escR(genres[0][0].toUpperCase())} x${genres[0][1]}`) : ''}
      ${months.length ? row('BUSIEST MONTH', `${MONTH_NAMES[months[0][0]]} x${months[0][1]}`) : ''}
      <div class="r-rule dash"></div>
      ${pick('STAFF PICK', best, fmtR(r10(best || {})))}
      ${pick('PLEASE DO NOT RENT', worst !== best ? worst : null, fmtR(r10(worst || {})))}
      ${pick('OLDEST TAPE', oldest, oldest && oldest.year)}
      ${pick('LONGEST TAPE', longest, longest && `${longest.runtime} MIN`)}
      ${loved && gap(loved) > 0 ? pick('YOU LIKED MORE THAN IMDB DID', loved, signed(gap(loved))) : ''}
      ${cold && gap(cold) < 0 ? pick('IMDB LIKED MORE THAN YOU DID', cold, signed(gap(cold))) : ''}
      <div class="r-rule"></div>
      ${row('LATE FEES', '$0.00', 'r-big')}
      <div class="r-c">*** EVERY TAPE REWOUND ***</div>
      <svg class="r-bars" viewBox="0 0 ${x} 40" preserveAspectRatio="none" aria-hidden="true">${bars}</svg>
      <div class="r-c r-small">${year}${String(n).padStart(4, '0')}${String(mins % 10000).padStart(4, '0')}</div>
      <div class="r-c r-thanks">THANK YOU FOR RENTING<br>BE KIND, PLEASE REWIND</div>`;
  }

  function setReceiptParam(on) {
    const q = new URLSearchParams(location.search);
    if (on) q.set('receipt', ''); else q.delete('receipt');
    const qs = q.toString().replace(/receipt=(&|$)/, 'receipt$1');
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }
  let receiptFocus = null;
  function openReceipt() {
    if (!receipt.hidden) return;
    receiptFocus = document.activeElement;
    paper.innerHTML = receiptHTML();
    receipt.hidden = false; document.body.classList.add('store-open');
    paper.scrollTop = 0; receipt.querySelector('.receipt-slot').scrollTop = 0;
    receipt.querySelector('.receipt-x').focus({ preventScroll: true });
    setReceiptParam(true);
  }
  function closeReceipt() {
    if (receipt.hidden) return;
    receipt.hidden = true; document.body.classList.remove('store-open');
    setReceiptParam(false);
    if (receiptFocus && receiptFocus.focus) receiptFocus.focus({ preventScroll: true });
  }
  receipt.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeReceipt));
  $('receipt-btn').addEventListener('click', openReceipt);
  document.addEventListener('keydown', (e) => { if (!receipt.hidden && e.key === 'Escape') { e.stopPropagation(); closeReceipt(); } }, true);

  // Hooks for vcr.js: preview a spine for a film (with edited fields) and redraw the shelf.
  window.viewings = {
    shelf: SHELF,        // the year on show, or the Vault's decade ('1990s')
    vault: IN_VAULT,
    all: IN_ALL,         // the Whole Store: built from every shelf file, so vcr.js changes nothing here
    shelfFiles: YEARS.map((k) => SHELVES[k]), // every shelf's data file (vcr.js syncs ratings across all of them)
    dataFile: DATA_FILE, // films.json for the newest year, films-<year>.json for older ones (vcr.js reads and commits this)
    get films() { return films; },
    get current() { return current >= 0 ? films[current] : null; },
    async preview(f) { await prepare(f, true); return spineEl(f, -1); },
    async refresh(f) { await prepare(f); computeOrder(); updateTally(); renderControls(); layout(); },
  };

  /* ---------- boot ---------- */
  async function boot() {
    let data;
    const sizesP = fetch('posters/spines.json', { cache: 'no-cache' }).then((r) => r.json()).catch(() => null); // fetched alongside the shelf file
    if (IN_ALL) { // every shelf file (the same ones the store directory loads), Vault decades first, each year in watched order
      const st = await loadStore();
      films = st.flatMap((list, n) => {
        const k = YEARS[n], fs = list.map((e) => e.f);
        fs.forEach((f) => { f._k = k; f._vault = VAULT.includes(k); });
        return VAULT.includes(k) ? fs.slice().sort((a, b) => (a.year || 0) - (b.year || 0)) : fs.slice().sort((a, b) => (a.watched || '').localeCompare(b.watched || ''));
      });
      if (IN_SEARCH) { // only this search's results (every one of them), in the same order as the Whole Store
        const want = new Set(search(SEARCH_Q, true).hits.map((e) => e.f));
        films = films.filter((f) => want.has(f));
        if (!films.length) { shelves.innerHTML = `<p style="text-align:center;opacity:.7">Nothing on the shelves for “${SEARCH_Q.replace(/[<&]/g, '')}”.</p>`; return; }
      }
      if (!films.length) { shelves.innerHTML = '<p style="text-align:center;opacity:.6">Couldn\'t load the shelves. Serve this folder over http (see README).</p>'; return; }
    } else {
      try { data = await (await fetch(DATA_FILE, { cache: 'no-cache' })).json(); }
      catch { shelves.innerHTML = `<p style="text-align:center;opacity:.6">Couldn't load ${DATA_FILE}. Serve this folder over http (see README).</p>`; return; }
      films = (data.films || []).slice().sort((a, b) => (a.watched || '').localeCompare(b.watched || ''));
    }
    loadView();
    computeOrder();
    renderControls();
    updateTally();
    $('count').parentNode.hidden = false; // hidden until the real number is known (no "0 TAPES" while loading)
    spineSizes = await sizesP;
    await Promise.all(films.map((f) => prepare(f)));
    layout();
    controls.hidden = false;
    $('finder').hidden = false;
    if (!IN_VAULT && !IN_ALL) {
      $('receipt-btn').hidden = false;
      if (new URLSearchParams(location.search).has('receipt')) openReceipt();
    }
    const want = new URLSearchParams(location.search).get('tape');
    if (want && !pullOut(want, true)) setTapeParam(null); // ?tape= from a shared link or a search result on another shelf
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(layout, 150); });
  }
  boot();
})();
