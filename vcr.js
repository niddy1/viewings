/*
 * The VCR: a hidden panel for updating the shelf from the browser.
 *
 * Type "vcr" anywhere on the page (or open the page with #vcr on the end, for phones),
 * drop in a PassThePopcorn ratings CSV, and it:
 *   - keeps only films rated in this shelf's year (films.json "year"),
 *   - matches them to the shelf by IMDb id (no fuzzy title matching),
 *   - looks up new films on TMDB (poster, runtime, director, genres),
 *   - lets you drag a box around the title lettering on each new poster,
 *   - commits films.json + the new posters to GitHub in one commit. Pages redeploys in about a minute.
 *
 * Needs a GitHub fine-grained token (this repo only, Contents: read and write) and a TMDB key.
 * Both are kept in this browser's localStorage only; nothing is written to the repo.
 */
(() => {
  'use strict';

  const REPO = 'niddy1/viewings', BRANCH = 'main';
  const KEYS = { gh: 'vcr.githubToken', tmdb: 'vcr.tmdbKey' };
  const store = {
    get: (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
    set: (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch {} },
  };

  /* ---------- trigger: type v-c-r, or #vcr in the URL ---------- */
  let typed = '';
  document.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.key.length !== 1) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    typed = (typed + e.key.toLowerCase()).slice(-3);
    if (typed === 'vcr') { typed = ''; open(); }
  });
  window.addEventListener('hashchange', () => { if (location.hash === '#vcr') open(); });
  if (location.hash === '#vcr') open();

  /* ---------- small helpers ---------- */
  const h = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const r10Of = (f) => (f.rating10 != null ? f.rating10 : (f.rating || 0) * 2);
  const starsOf = (r10) => Math.round(r10) / 2; // PTP's 10-point scale onto half stars (8.5 -> 4.5, 7.5 -> 4)
  const fmt = (iso) => { const d = new Date(iso + 'T12:00:00'); return isNaN(d) ? iso : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); };
  const englishTitle = (t) => { const p = t.split(/\s+AKA\s+/); return (p[1] || p[0]).trim(); }; // "Gisaengchung AKA Parasite" -> "Parasite"

  function parseCSV(text) {
    const rows = []; let row = [], cur = '', q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) {
        if (c === '"' && text[i + 1] === '"') { cur += '"'; i++; }
        else if (c === '"') q = false;
        else cur += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(cur); cur = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(cur); cur = ''; if (row.some((v) => v.trim())) rows.push(row); row = [];
      } else cur += c;
    }
    if (cur || row.length) { row.push(cur); if (row.some((v) => v.trim())) rows.push(row); }
    return rows.map((r) => r.map((v) => v.trim()));
  }

  /* ---------- APIs ---------- */
  async function gh(path, opts = {}) {
    const token = store.get(KEYS.gh);
    if (!token) throw new Error('Add a GitHub token first.');
    const res = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
      ...opts,
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', ...(opts.headers || {}) },
    });
    if (!res.ok) {
      const msg = (await res.json().catch(() => ({}))).message || res.statusText;
      throw new Error(res.status === 401 ? 'GitHub rejected the token (expired or mistyped?).' : `GitHub ${res.status}: ${msg}`);
    }
    return res;
  }
  const ghJSON = (path, body, method = 'POST') => gh(path, { method, body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } }).then((r) => r.json());

  async function tmdb(endpoint, params = {}) {
    const key = store.get(KEYS.tmdb);
    if (!key) throw new Error('Add a TMDB key first.');
    const url = new URL('https://api.themoviedb.org/3' + endpoint);
    const headers = {};
    if (key.length > 40) headers.Authorization = `Bearer ${key}`; else url.searchParams.set('api_key', key);
    for (const [k, v] of Object.entries(params)) if (v != null) url.searchParams.set(k, v);
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(res.status === 401 ? 'TMDB rejected the key.' : `TMDB ${res.status}`);
    return res.json();
  }

  // Latest films.json straight from GitHub (so a stale Pages deploy can't undo an earlier update).
  async function loadShelf() {
    if (store.get(KEYS.gh)) {
      return (await gh(`/contents/films.json?ref=${BRANCH}`, { headers: { Accept: 'application/vnd.github.raw+json' }, cache: 'no-store' })).json();
    }
    return (await fetch('films.json', { cache: 'no-cache' })).json();
  }

  const toBase64 = (blob) => new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(',')[1]);
    r.onerror = reject;
    r.readAsDataURL(blob);
  });

  /* ---------- panel ---------- */
  let root, out, goBtn, state = null;

  function open() {
    if (!root) build();
    root.classList.add('open');
    root.setAttribute('aria-hidden', 'false');
    renderKeys();
  }
  function close() {
    root.classList.remove('open');
    root.setAttribute('aria-hidden', 'true');
    if (location.hash === '#vcr') history.replaceState(null, '', location.pathname + location.search);
  }

  function build() {
    root = h('div', 'vcr'); root.setAttribute('aria-hidden', 'true');
    const backdrop = h('div', 'vcr-backdrop'); backdrop.addEventListener('click', close);
    const box = h('div', 'vcr-box'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', 'Update the shelf');

    const top = h('div', 'vcr-top');
    top.append(h('span', 'vcr-led'), h('h2', null, 'VCR'), h('span', 'vcr-mode', 'REC'));
    const x = h('button', 'vcr-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close'); x.addEventListener('click', close);
    top.append(x);

    const keys = h('div', 'vcr-keys');

    const drop = h('label', 'vcr-drop');
    const file = h('input'); file.type = 'file'; file.accept = '.csv,text/csv';
    drop.append(h('strong', null, 'Insert ratings CSV'), h('span', null, 'Your PassThePopcorn ratings export. Click, or drop it here.'), file);
    file.addEventListener('change', () => file.files[0] && readFile(file.files[0]));
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('over'));
    drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]); });

    out = h('div', 'vcr-out');
    const foot = h('div', 'vcr-foot');
    goBtn = h('button', 'vcr-go', '● Record to shelf'); goBtn.type = 'button'; goBtn.disabled = true;
    goBtn.addEventListener('click', record);
    foot.append(goBtn);

    box.append(top, keys, drop, out, foot);
    root.append(backdrop, box);
    document.body.append(root);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && root.classList.contains('open')) { e.stopPropagation(); close(); } }, true);
  }

  function renderKeys() {
    const keys = root.querySelector('.vcr-keys');
    keys.textContent = '';
    const have = store.get(KEYS.gh) && store.get(KEYS.tmdb);
    const det = h('details'); det.open = !have;
    det.append(h('summary', null, have ? 'Keys saved in this browser' : 'Keys (saved in this browser only)'));
    const field = (label, k, help) => {
      const l = h('label', 'vcr-field');
      const i = h('input'); i.type = 'password'; i.autocomplete = 'off'; i.spellcheck = false; i.value = store.get(k); i.placeholder = help;
      i.addEventListener('change', () => store.set(k, i.value.trim()));
      l.append(h('span', null, label), i);
      return l;
    };
    det.append(
      field('GitHub token', KEYS.gh, 'fine-grained, viewings repo, Contents: read & write'),
      field('TMDB key', KEYS.tmdb, 'v3 API key or v4 read token'),
    );
    const forget = h('button', 'vcr-link', 'Forget both'); forget.type = 'button';
    forget.addEventListener('click', () => { store.set(KEYS.gh, ''); store.set(KEYS.tmdb, ''); renderKeys(); });
    det.append(forget);
    keys.append(det);
  }

  const status = (msg, cls = '') => { const p = h('p', 'vcr-status ' + cls, msg); out.append(p); return p; };

  /* ---------- 1. read the CSV and work out what changes ---------- */
  async function readFile(fileObj) {
    out.textContent = ''; goBtn.disabled = true; state = null;
    try {
      const rows = parseCSV(await fileObj.text());
      const head = (rows.shift() || []).map((v) => v.replace(/^﻿/, ''));
      const col = (n) => head.indexOf(n);
      const iT = col('Title'), iR = col('Rating10'), iW = col('WatchedDate'), iI = col('ImdbID');
      if ([iT, iR, iW, iI].includes(-1)) {
        throw new Error(head.includes('Watched Date')
          ? 'That looks like a Letterboxd export. This wants the PassThePopcorn ratings CSV (Title, Rating10, WatchedDate, ImdbID).'
          : 'Missing columns. Expected Title, Rating10, WatchedDate, ImdbID.');
      }
      const loading = status('Reading the shelf…');
      const data = await loadShelf();
      loading.remove();
      const year = String(data.year || new Date().getFullYear());

      // one entry per film for this year: the latest rating wins
      const byId = new Map();
      for (const r of rows) {
        const id = (r[iI] || '').trim(), watched = (r[iW] || '').slice(0, 10);
        if (!/^tt\d+$/.test(id) || !watched.startsWith(year)) continue;
        const prev = byId.get(id);
        if (!prev || watched > prev.watched) byId.set(id, { imdb: id, csvTitle: r[iT], r10: Number(r[iR]) || 0, watched });
      }

      const shelf = data.films || [];
      const onShelf = new Map(shelf.filter((f) => f.imdb).map((f) => [f.imdb, f]));
      const adds = [], updates = [];
      for (const e of byId.values()) {
        const f = onShelf.get(e.imdb);
        if (!f) adds.push(e);
        else if (r10Of(f) !== e.r10 || f.watched !== e.watched || f.rating10 == null) updates.push({ f, ...e });
      }
      const missing = shelf.filter((f) => !f.imdb || !byId.has(f.imdb));
      adds.sort((a, b) => a.watched.localeCompare(b.watched));

      state = { data, year, adds, updates, missing, remove: new Set() };
      renderPlan();
      if (adds.length) await lookUpNew();
      goBtn.disabled = !(adds.length || updates.length);
      if (!adds.length && !updates.length) status(`Nothing to record. The shelf already matches your ${year} ratings.`, 'ok');
    } catch (e) {
      status(e.message, 'err');
    }
  }

  function renderPlan() {
    const { year, adds, updates, missing } = state;
    out.textContent = '';
    const changed = updates.filter((u) => r10Of(u.f) !== u.r10 || u.f.watched !== u.watched);
    status(`Films rated in ${year}: ${adds.length} new, ${changed.length} with a changed rating or date.`);

    if (updates.length) {
      const d = h('details', 'vcr-list');
      d.append(h('summary', null, `${updates.length} already on the shelf${changed.length ? `, ${changed.length} with a new rating or date` : ''}`));
      const ul = h('ul');
      updates.forEach((u) => {
        const bits = [];
        if (r10Of(u.f) !== u.r10) bits.push(`${r10Of(u.f)} → ${u.r10}`); else bits.push(`${u.r10}`);
        if (u.f.watched !== u.watched) bits.push(`${fmt(u.f.watched)} → ${fmt(u.watched)}`);
        ul.append(h('li', null, `${u.f.title}  ·  ${bits.join('  ·  ')}`));
      });
      d.append(ul);
      out.append(d);
    }

    if (missing.length) {
      const d = h('details', 'vcr-list');
      d.append(h('summary', null, `${missing.length} on the shelf but not in this CSV (kept unless you tick them)`));
      const ul = h('ul');
      missing.forEach((f) => {
        const li = h('li'); const l = h('label');
        const c = h('input'); c.type = 'checkbox';
        c.addEventListener('change', () => { c.checked ? state.remove.add(f) : state.remove.delete(f); goBtn.disabled = !(state.adds.length || state.updates.length || state.remove.size); });
        l.append(c, document.createTextNode(` remove ${f.title} (${fmt(f.watched)})`));
        li.append(l); ul.append(li);
      });
      d.append(ul);
      out.append(d);
    }

    if (adds.length) {
      out.append(h('p', 'vcr-hint', 'New tapes. Drag a box around each line of the title lettering on the poster, top line first. Skip it and the spine prints the title in a typeface instead.'));
      state.cards = h('div', 'vcr-cards');
      out.append(state.cards);
    }
  }

  /* ---------- 2. look up new films on TMDB ---------- */
  async function lookUpNew() {
    for (const e of state.adds) {
      const card = h('div', 'vcr-card');
      const info = h('div', 'vcr-info');
      info.append(h('strong', null, englishTitle(e.csvTitle)), h('span', null, `${e.r10} / 10 · ${fmt(e.watched)} · looking up…`));
      card.append(info);
      state.cards.append(card);
      try {
        const found = await tmdb(`/find/${e.imdb}`, { external_source: 'imdb_id' });
        let kind = 'movie', hit = (found.movie_results || [])[0];
        if (!hit) { hit = (found.tv_results || [])[0]; kind = 'tv'; }
        if (!hit) throw new Error('not on TMDB');
        const d = await tmdb(`/${kind}/${hit.id}`, { append_to_response: 'credits' });
        const title = d.title || d.name || englishTitle(e.csvTitle);
        const year = Number((d.release_date || d.first_air_date || '').slice(0, 4)) || undefined;
        const director = kind === 'tv' ? (d.created_by || [])[0] : (d.credits?.crew || []).find((c) => c.job === 'Director');
        e.film = {
          title, year,
          rating: starsOf(e.r10), rating10: e.r10, watched: e.watched,
          tmdb: d.id, tmdbKind: kind,
          runtime: (kind === 'tv' ? (d.episode_run_time || [])[0] : d.runtime) || undefined,
          director: director ? director.name : undefined,
          genres: (d.genres || []).map((g) => g.name),
          imdb: e.imdb,
          poster: '',
        };
        if (d.poster_path) {
          try {
            const img = await fetch(`https://image.tmdb.org/t/p/w780${d.poster_path}`);
            if (!img.ok) throw new Error(img.status);
            e.posterBlob = await img.blob();
            e.film.poster = `posters/${slug(title)}-${year || 'x'}.jpg`;
          } catch { e.note = 'couldn’t download the poster'; }
        } else e.note = 'no poster on TMDB';

        info.textContent = '';
        info.append(
          h('strong', null, title),
          h('span', null, [year, e.film.director && `dir. ${e.film.director}`].filter(Boolean).join(' · ')),
          h('span', null, `${e.r10} / 10 · watched ${fmt(e.watched)}`),
        );
        if (title.toLowerCase() !== englishTitle(e.csvTitle).toLowerCase()) info.append(h('span', 'vcr-dim', `CSV calls it “${e.csvTitle}”`));
        if (e.note) info.append(h('span', 'vcr-warn', e.note));
        if (e.posterBlob) card.prepend(boxEditor(e.film, URL.createObjectURL(e.posterBlob)));
      } catch (err) {
        // still shelve it, with a plain typeface spine
        e.film = { title: englishTitle(e.csvTitle), rating: starsOf(e.r10), rating10: e.r10, watched: e.watched, genres: [], imdb: e.imdb, poster: '' };
        info.querySelector('span').textContent = `${e.r10} / 10 · ${fmt(e.watched)}`;
        info.append(h('span', 'vcr-warn', `${err.message}. It’ll go on the shelf without a poster.`));
      }
    }
  }

  // Drag boxes over the poster to mark the title lettering (stored as fractions, like titleBox in films.json).
  function boxEditor(film, url) {
    film.titleBox = [];
    const wrap = h('div', 'vcr-edit');
    const pic = h('div', 'vcr-poster');
    const img = new Image(); img.src = url; img.alt = ''; img.draggable = false;
    const layer = h('div', 'vcr-boxes');
    pic.append(img, layer);
    const tools = h('div', 'vcr-tools');
    const undo = h('button', 'vcr-link', 'undo box'); undo.type = 'button';
    const count = h('span', 'vcr-dim');
    tools.append(count, undo);
    wrap.append(pic, tools);

    const draw = () => {
      layer.textContent = '';
      film.titleBox.forEach(([x0, y0, x1, y1], i) => {
        const b = h('i', null, String(i + 1));
        Object.assign(b.style, { left: x0 * 100 + '%', top: y0 * 100 + '%', width: (x1 - x0) * 100 + '%', height: (y1 - y0) * 100 + '%' });
        layer.append(b);
      });
      count.textContent = film.titleBox.length ? `${film.titleBox.length} line${film.titleBox.length > 1 ? 's' : ''} marked` : 'no title marked';
      undo.hidden = !film.titleBox.length;
    };
    undo.addEventListener('click', () => { film.titleBox.pop(); draw(); });

    let start = null, live = null;
    const at = (e) => { const r = pic.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
    const rect = (a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
    pic.addEventListener('pointerdown', (e) => {
      e.preventDefault(); pic.setPointerCapture(e.pointerId);
      start = at(e); live = h('i', 'live'); layer.append(live);
    });
    pic.addEventListener('pointermove', (e) => {
      if (!start) return;
      const [x0, y0, x1, y1] = rect(start, at(e));
      Object.assign(live.style, { left: x0 * 100 + '%', top: y0 * 100 + '%', width: (x1 - x0) * 100 + '%', height: (y1 - y0) * 100 + '%' });
    });
    const end = (e) => {
      if (!start) return;
      const b = rect(start, at(e)); start = null;
      if (b[2] - b[0] > 0.03 && b[3] - b[1] > 0.01) {
        film.titleBox.push(b.map((v) => Math.round(v * 10000) / 10000));
        film.titleBox.sort((p, q) => p[1] - q[1]); // top line first
      }
      draw();
    };
    pic.addEventListener('pointerup', end);
    pic.addEventListener('pointercancel', end);
    draw();
    return wrap;
  }

  /* ---------- 3. one commit: films.json + new posters ---------- */
  async function record() {
    if (!state) return;
    goBtn.disabled = true;
    const busy = status('Recording…');
    try {
      const { data, adds, updates, remove } = state;
      const upd = new Map(updates.map((u) => [u.f, u]));
      const films = (data.films || [])
        .filter((f) => !remove.has(f))
        .map((f) => {
          const u = upd.get(f);
          return u ? { ...f, rating: starsOf(u.r10), rating10: u.r10, watched: u.watched } : f;
        });
      const added = adds.filter((e) => e.film).map((e) => {
        const f = { ...e.film };
        if (!f.titleBox || !f.titleBox.length) delete f.titleBox;
        return f;
      });
      const taken = new Set(films.map((f) => f.poster));
      for (const f of added) {
        if (f.poster && taken.has(f.poster)) f.poster = f.poster.replace(/\.jpg$/, `-${f.imdb}.jpg`);
        taken.add(f.poster);
      }
      const next = { ...data, films: [...films, ...added].sort((a, b) => (a.watched || '').localeCompare(b.watched || '')) };

      const ref = await (await gh(`/git/ref/heads/${BRANCH}`)).json();
      const head = await (await gh(`/git/commits/${ref.object.sha}`)).json();
      const tree = [{ path: 'films.json', mode: '100644', type: 'blob', content: JSON.stringify(next, null, 2) + '\n' }];
      for (let i = 0; i < adds.length; i++) {
        const e = adds[i], f = added.find((a) => a.imdb === e.imdb);
        if (!e.posterBlob || !f || !f.poster) continue;
        busy.textContent = `Recording… poster ${i + 1} of ${adds.length}`;
        const blob = await ghJSON('/git/blobs', { content: await toBase64(e.posterBlob), encoding: 'base64' });
        tree.push({ path: f.poster, mode: '100644', type: 'blob', sha: blob.sha });
      }
      const newTree = await ghJSON('/git/trees', { base_tree: head.tree.sha, tree });

      const parts = [];
      if (added.length) parts.push(`+${added.length} (${added.slice(0, 3).map((f) => f.title).join(', ')}${added.length > 3 ? '…' : ''})`);
      if (updates.length) parts.push(`${updates.length} rating${updates.length > 1 ? 's' : ''} synced`);
      if (remove.size) parts.push(`-${remove.size}`);
      const commit = await ghJSON('/git/commits', { message: `Shelf: ${parts.join(', ')} from PTP ratings`, tree: newTree.sha, parents: [ref.object.sha] });
      await ghJSON(`/git/refs/heads/${BRANCH}`, { sha: commit.sha }, 'PATCH');

      busy.remove();
      const done = status('Recorded. GitHub Pages redeploys in about a minute, then reload. ', 'ok');
      const a = h('a', null, 'See the commit'); a.href = commit.html_url; a.target = '_blank'; a.rel = 'noopener';
      done.append(a);
      state = null;
    } catch (e) {
      busy.remove();
      status(e.message.includes('Update is not a fast forward')
        ? 'The shelf changed on GitHub while this was open. Load the CSV again and re-record.'
        : e.message, 'err');
      goBtn.disabled = false;
    }
  }
})();
