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
  const logoZone = (f) => (f.logo ? 40 : f._dmg && f._dmg.includes('sticker') ? 50 : 12);

  const loadImg = (src) => new Promise((resolve) => {
    if (!src) return resolve(null);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });

  // Average poster colour -> a deep, saturated spine colour.
  function posterColor(img) {
    if (!img) return null;
    try {
      const c = document.createElement('canvas'); c.width = c.height = 8;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0, 8, 8);
      const d = x.getImageData(0, 0, 8, 8).data;
      let r = 0, g = 0, b = 0, n = 0;
      for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      return rgbToHsl(r / n, g / n, b / n);
    } catch { return null; }
  }

  // Mean + spread of the pixels around the edge of a crop. A flat edge means the
  // lettering sits on a plain background we can match with the spine colour.
  function edgeColor(img, sx, sy, sw, sh) {
    try {
      const c = document.createElement('canvas'); c.width = 24; c.height = 24;
      const x = c.getContext('2d'); x.drawImage(img, sx, sy, sw, sh, 0, 0, 24, 24);
      const d = x.getImageData(0, 0, 24, 24).data;
      const px = [];
      for (let i = 0; i < 24; i++) for (const [cx, cy] of [[i, 0], [i, 23], [0, i], [23, i]]) { const k = (cy * 24 + cx) * 4; px.push([d[k], d[k + 1], d[k + 2]]); }
      const m = [0, 1, 2].map((ch) => px.reduce((a, p) => a + p[ch], 0) / px.length);
      const sd = Math.max(...[0, 1, 2].map((ch) => Math.sqrt(px.reduce((a, p) => a + (p[ch] - m[ch]) ** 2, 0) / px.length)));
      return { m, sd };
    } catch { return null; }
  }

  // Cut the title lettering out of the poster, turn it 90 degrees so it reads down the
  // spine, and scale it to fill the space. Lines sit side by side, first line on the right.
  function titleArt(f, img, W, H) {
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

    const cv = document.createElement('canvas');
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);
    ctx.imageSmoothingQuality = 'high';
    let right = (W + totalW) / 2;
    const edges = [];
    crops.forEach((c) => {
      ctx.save();
      ctx.translate(right, (H - c.sw * s) / 2);
      ctx.rotate(Math.PI / 2);
      ctx.drawImage(img, c.sx, c.sy, c.sw, c.sh, 0, 0, c.sw * s, c.sh * s);
      ctx.restore();
      right -= c.sh * s + GAP;
      const e = edgeColor(img, c.sx, c.sy, c.sw, c.sh); if (e) edges.push(e);
    });
    let bg = null;
    if (edges.length && Math.max(...edges.map((e) => e.sd)) < 30) {
      const m = [0, 1, 2].map((ch) => edges.reduce((a, e) => a + e.m[ch], 0) / edges.length);
      bg = `rgb(${m.map((v) => Math.round(v)).join(',')})`;
    }
    return { cv, bg };
  }

  async function prepare(f) {
    const img = await loadImg(f.poster);
    const hsl = posterColor(img);
    const h = hsl ? hsl[0] : hash(f.title) % 360;
    const s = Math.max(hsl ? hsl[1] : .5, .38);
    const l = Math.min(Math.max(hsl ? hsl[2] : .28, .2), .36);
    f._c = f.color || `hsl(${h.toFixed(0)} ${(s * 100).toFixed(0)}% ${(l * 100).toFixed(0)}%)`;
    f._t = `hsl(${h.toFixed(0)} 70% 90%)`;
    f._font = pickFont(f);
    const rt = f.runtime || (90 + hash(f.title) % 60);
    f._w = Math.round(Math.min(52, Math.max(42, 40 + (rt - 90) * 0.12)));
    f._h = SPINE_H;
    // Wear and tear: a stable, per-film roll so the same tapes are always the battered ones.
    const r = hash(f.title + 'wear');
    f._dmg = [];
    if ((r >> 11) % 6 === 0) f._dmg.push('sticker');
    if ((r >> 14) % 5 === 0) f._dmg.push('fade');
    // ~1 in 5 tapes is damaged at all; severity runs from a light scuff (0.3) to badly beaten up (1)
    f._sev = r % 100 < 20 ? 0.3 + 0.7 * ((r >> 9) % 100) / 100 : 0;
    f._r = r;
    if (f.logo) f._dmg = f._dmg.filter((d) => d !== 'sticker');
    f._art = null;
    if (img && Array.isArray(f.titleBox) && f.titleBox.length) {
      const W = f._w - 4, H = f._h - logoZone(f) - BOTTOM_ZONE - 6;
      f._art = titleArt(f, img, W, H);
      if (f._art.bg && !f.color) {
        f._c = f._art.bg;
        const m = f._c.match(/\d+/g).map(Number);
        if (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2] > 150) f._t = '#2a2118'; // pale spine: dark ink
      }
    }
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

    // Each damaged tape gets a different mix of problems, not all of them.
    const has = {
      top: chance(.5 + sev * .45), peel: sev > .45 && chance(.6), corner: sev > .3 && chance(.5),
      edges: chance(.55 + sev * .4), specks: chance(.6 + sev * .3), crease: chance(.25 + sev * .65),
      scratch: sev > .5 && chance(.6), bottom: chance(.55 + sev * .4),
    };
    if (!Object.values(has).some(Boolean)) has.specks = true;

    if (has.top) { // frayed top: white cardboard, ragged both sides, poking above the edge
      const depth = L(1.2, 5.5), rise = L(1, 4.5), ph0 = R() * 6;
      x.beginPath(); x.moveTo(-1, y0 + 1);
      for (let px = 0; px <= W + 1; px += rr(1.5, 3.5)) x.lineTo(px, y0 - rr(0, rise));
      x.lineTo(W + 1, y0 + 1);
      for (let px = W + 1; px >= -1; px -= rr(1.5, 3.5)) x.lineTo(px, y0 + rr(0.4, depth) * (0.45 + 0.8 * Math.abs(Math.sin(px / 7 + ph0))));
      x.closePath(); x.fillStyle = cream(0.95); x.fill();
      x.fillStyle = 'rgba(0,0,0,.22)';
      for (let px = 0; px < W; px += rr(2, 4)) x.fillRect(px, y0 + depth + 0.5, rr(1, 3), 1);
    }
    if (has.peel) for (let i = 0, n = sev > .75 ? 2 : 1; i < n; i++) { // printed layer lifted away
      const pw = rr(W * .25, W * .6), px = rr(0, W - pw), ph = rr(5, L(7, 14));
      x.beginPath(); x.moveTo(px, y0);
      for (let t = 0; t <= 1.001; t += .2) x.lineTo(px + pw * t, y0 + ph * rr(.3, 1) * Math.sin(Math.PI * t) + 1);
      x.closePath(); x.fillStyle = cream(.92); x.fill();
      x.strokeStyle = 'rgba(0,0,0,.28)'; x.lineWidth = .8; x.stroke();
    }
    if (has.corner) { // a top corner rubbed through
      const left = chance(.5), cs = rr(4, L(5, 10));
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
    const badge = document.createElement('span'); badge.className = 'vhs'; badge.textContent = 'VHS';
    const notch = document.createElement('span'); notch.className = 'notch';
    b.append(badge, notch);
    if (f._sev > 0) b.append(wearCanvas(f));
    if (f._dmg.includes('sticker')) {
      const st = document.createElement('span'); st.className = 'sticker';
      const g = (f.genres || []).find((x) => STICKER_WORDS[x]);
      st.textContent = g ? STICKER_WORDS[g] : 'NEW';
      b.append(st);
    }
    b.addEventListener('click', () => openViewer(i));
    return b;
  }

  function layout() {
    shelves.textContent = '';
    spineEls = films.map(spineEl);
    const avail = shelves.clientWidth - 2 * (10 + 16);
    let row = [], used = 0, rows = [];
    films.forEach((f, i) => {
      const w = f._w + 2;
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

  function stars(r) {
    let h = '';
    for (let i = 1; i <= 5; i++) h += `<span class="star ${r >= i ? 'full' : r >= i - .5 ? 'half' : ''}">&#9733;</span>`;
    return h + `<small>${r ? r.toFixed(1) : '—'} / 5</small>`;
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
    $('v-rating').innerHTML = stars(f.rating || 0);
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
