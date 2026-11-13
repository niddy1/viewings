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

  // Average poster colour -> a deep, saturated spine colour.
  function posterColor(src) {
    return new Promise((resolve) => {
      if (!src) return resolve(null);
      const img = new Image();
      img.onload = () => {
        try {
          const c = document.createElement('canvas'); c.width = c.height = 8;
          const x = c.getContext('2d'); x.drawImage(img, 0, 0, 8, 8);
          const d = x.getImageData(0, 0, 8, 8).data;
          let r = 0, g = 0, b = 0, n = 0;
          for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
          resolve(rgbToHsl(r / n, g / n, b / n));
        } catch { resolve(null); }
      };
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  async function prepare(f) {
    const hsl = await posterColor(f.poster);
    const h = hsl ? hsl[0] : hash(f.title) % 360;
    const s = Math.max(hsl ? hsl[1] : .5, .38);
    const l = Math.min(Math.max(hsl ? hsl[2] : .28, .2), .36);
    f._c = f.color || `hsl(${h.toFixed(0)} ${(s * 100).toFixed(0)}% ${(l * 100).toFixed(0)}%)`;
    f._t = `hsl(${h.toFixed(0)} 70% 90%)`;
    f._font = pickFont(f);
    const rt = f.runtime || (90 + hash(f.title) % 60);
    f._w = Math.round(Math.min(58, Math.max(38, 36 + (rt - 80) * 0.2)));
    f._h = 236 + hash(f.title + 'h') % 28;
  }

  function spineEl(f, i) {
    const b = document.createElement('button');
    b.className = 'spine';
    b.type = 'button';
    b.setAttribute('aria-label', `${f.title} (${f.year})`);
    const len = f.title.length;
    const fs = Math.max(11, Math.min(f._w * 0.55, (f._h - 80) / (len * 0.6)));
    b.style.cssText = `--w:${f._w}px;--h:${f._h}px;--c:${f._c};--t:${f._t};--f:'${f._font}';--fs:${fs.toFixed(1)}px`;
    const stripe = document.createElement('span'); stripe.className = 'stripe';
    const title = document.createElement('span'); title.className = 'title'; title.textContent = f.title;
    const meta = document.createElement('span'); meta.className = 'meta'; meta.textContent = f.year;
    b.append(stripe, title, meta);
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
