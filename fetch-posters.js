#!/usr/bin/env node
/*
 * Builds films.json + posters/ from your PassThePopcorn ratings export
 * (Title, Rating10, WatchedDate, ImdbID) or a Letterboxd diary.csv.
 *
 *   TMDB_KEY=your_key node fetch-posters.js path/to/ratings.csv [year]
 *
 * (The VCR panel on the site does the same thing from the browser: type "vcr" on the page.)
 *
 * - Needs Node 18+ (built-in fetch). No npm install.
 * - TMDB_KEY can be either the v3 API key or the v4 "Read Access Token".
 * - Safe to re-run: films already in films.json keep their poster, any manual
 *   edits (font, color, note) and are not re-fetched.
 * - Also saves the studio logo for the top of each spine into logos/ (films with no
 *   logo on TMDB get a blank top). Films from before this existed are backfilled on the next run.
 * - Matches TMDB couldn't make confidently are listed in needs_review.txt.
 */
const fs = require('fs');
const path = require('path');

const KEY = process.env.TMDB_KEY;
const CSV = process.argv[2] || 'ratings.csv';
const YEAR = String(process.argv[3] || process.env.YEAR || new Date().getFullYear());
const OUT = path.join(__dirname, 'films.json');
const POSTERS = path.join(__dirname, 'posters');
const LOGOS = path.join(__dirname, 'logos');

if (!KEY) { console.error('Set TMDB_KEY first, e.g.  TMDB_KEY=abc123 node fetch-posters.js diary.csv'); process.exit(1); }
if (!fs.existsSync(CSV)) { console.error(`Can't find ${CSV}. Pass the path to your PTP ratings CSV (or Letterboxd's diary.csv).`); process.exit(1); }
fs.mkdirSync(POSTERS, { recursive: true });
fs.mkdirSync(LOGOS, { recursive: true });

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
      row.push(cur); cur = ''; if (row.some(Boolean)) rows.push(row); row = [];
    } else cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  return rows;
}

const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const key = (t, y) => `${t}|${y}`;
const englishTitle = (t) => { const p = t.split(/\s+AKA\s+/); return (p[1] || p[0]).trim(); }; // "Gisaengchung AKA Parasite" -> "Parasite"

async function tmdb(endpoint, params = {}) {
  const url = new URL('https://api.themoviedb.org/3' + endpoint);
  const headers = {};
  if (KEY.length > 40) headers.Authorization = `Bearer ${KEY}`; else url.searchParams.set('api_key', KEY);
  for (const [k, v] of Object.entries(params)) if (v != null) url.searchParams.set(k, v);
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`TMDB ${res.status} on ${endpoint}`);
  return res.json();
}

(async () => {
  // ---- read diary
  const rows = parseCSV(fs.readFileSync(CSV, 'utf8'));
  const head = rows.shift().map((h) => h.trim());
  const col = (n) => head.indexOf(n);
  const ptp = ['Title', 'Rating10', 'WatchedDate', 'ImdbID'].every((n) => head.includes(n));
  const byFilm = new Map();
  if (ptp) { // PassThePopcorn: rated out of 10, matched on IMDb id. Stars round to the nearest half (8.5 -> 4.5).
    const iT = col('Title'), iR = col('Rating10'), iW = col('WatchedDate'), iI = col('ImdbID');
    for (const r of rows) {
      const watched = (r[iW] || '').trim().slice(0, 10), imdb = (r[iI] || '').trim();
      if (!watched.startsWith(YEAR) || !/^tt\d+$/.test(imdb)) continue;
      const r10 = Number(r[iR]) || 0, prev = byFilm.get(imdb);
      if (!prev || watched > prev.watched) byFilm.set(imdb, { title: englishTitle(r[iT]), imdb, rating: Math.round(r10) / 2, rating10: r10, watched });
    }
  } else {
  const iName = col('Name'), iYear = col('Year'), iRating = col('Rating'), iRewatch = col('Rewatch'), iWatched = col('Watched Date');
  if ([iName, iYear, iWatched].includes(-1)) { console.error('That CSV has neither PTP columns (Title, Rating10, WatchedDate, ImdbID) nor Letterboxd ones (Name, Year, Watched Date).'); process.exit(1); }

  for (const r of rows) {
    const watched = r[iWatched];
    if (!watched || !watched.startsWith(YEAR)) continue;
    const k = key(r[iName], r[iYear]);
    const prev = byFilm.get(k);
    const entry = {
      title: r[iName], year: Number(r[iYear]),
      rating: r[iRating] ? Number(r[iRating]) : 0,
      watched, rewatch: r[iRewatch] === 'Yes' || !!prev,
    };
    if (!prev || watched > prev.watched) byFilm.set(k, { ...entry, rewatch: entry.rewatch || (prev && prev.rewatch) });
    else prev.rewatch = true;
  }
  }
  console.log(`${byFilm.size} films watched in ${YEAR}.`);

  // ---- merge with existing
  let existing = new Map();
  if (fs.existsSync(OUT)) {
    try {
      const old = JSON.parse(fs.readFileSync(OUT, 'utf8'));
      for (const f of old.films || []) if (f.imdb || f.poster || f.tmdbOverride) { existing.set(key(f.title, f.year), f); if (f.imdb) existing.set(f.imdb, f); }
    } catch {}
  }

  let overrides = {};
  const ovPath = path.join(__dirname, 'overrides.json');
  if (fs.existsSync(ovPath)) {
    try { overrides = JSON.parse(fs.readFileSync(ovPath, 'utf8')); }
    catch (e) { console.error('overrides.json is not valid JSON: ' + e.message); process.exit(1); }
  }

  const review = [];
  const films = [];
  let n = 0;
  for (const base of byFilm.values()) {
    n++;
    let old = base.imdb ? existing.get(base.imdb) : existing.get(key(base.title, base.year));
    if (ptp && old) { base.title = old.title; base.year = old.year; } // PTP has no year and its own spellings; keep the shelf's
    const k = key(base.title, base.year);
    // "tmdbOverride" in films.json forces a specific TMDB movie. It is re-fetched
    // whenever it differs from the "tmdb" id the script recorded last time.
    // overrides.json ({"Title|Year": {"tmdb": 123, "type": "tv"}}) does the same without touching films.json.
    const ov = overrides[k] || {};
    const override = Number(ov.tmdb || (old && old.tmdbOverride)) || 0;
    const type = ov.type || (old && old.tmdbType) || 'movie'; // "movie" or "tv"
    const havePoster = old && old.imdb && old.poster && fs.existsSync(path.join(__dirname, old.poster));
    const upToDate = havePoster && 'logo' in old && (!override || (old.tmdb === override && (old.tmdbKind || 'movie') === type));
    if (upToDate) {
      films.push({ ...old, rating: base.rating, watched: base.watched, ...(ptp ? { rating10: base.rating10 } : { rewatch: base.rewatch }) });
      continue;
    }
    process.stdout.write(`[${n}/${byFilm.size}] ${base.title} (${base.year}) ... `);
    try {
      let hit;
      let ptpKind = 'movie';
      if (override) hit = { id: override };
      else if (base.imdb) { // exact match on IMDb id, no title guessing
        const found = await tmdb(`/find/${base.imdb}`, { external_source: 'imdb_id' });
        hit = (found.movie_results || [])[0];
        if (!hit && (hit = (found.tv_results || [])[0])) ptpKind = 'tv';
      } else {
        let search = await tmdb('/search/movie', { query: base.title, year: base.year });
        hit = search.results[0];
        if (!hit) { search = await tmdb('/search/movie', { query: base.title }); hit = search.results[0]; if (hit) review.push(`${base.title} (${base.year}): no match for that year, used "${hit.title}" (${(hit.release_date || '').slice(0, 4)})`); }
      }
      if (!hit) { review.push(`${base.title} (${base.year || base.imdb}): NOT FOUND`); films.push({ ...(old || {}), ...base, genres: [], imdb: base.imdb || '', poster: '' }); console.log('not found'); continue; }

      const isTv = override ? type === 'tv' : ptpKind === 'tv';
      const d = await tmdb(`/${isTv ? 'tv' : 'movie'}/${hit.id}`, { append_to_response: 'credits,external_ids' });
      const dTitle = d.title || d.name || '';
      const relYear = Number((d.release_date || d.first_air_date || '').slice(0, 4));
      if (ptp && !old) { base.title = dTitle || base.title; base.year = relYear || undefined; } // new film: TMDB's title and year
      if (!override && !base.imdb && (Math.abs(relYear - base.year) > 1 || dTitle.toLowerCase() !== base.title.toLowerCase()))
        review.push(`${base.title} (${base.year}): matched "${dTitle}" (${relYear}) - check this one`);

      let poster = '';
      const sameMovie = old && old.tmdb === d.id && (old.tmdbKind || 'movie') === (isTv ? 'tv' : 'movie');
      if (havePoster && (sameMovie || (!old.tmdb && !override))) poster = old.poster; // backfill pass: keep the poster we already have
      else if (d.poster_path) {
        const file = `posters/${slug(base.title)}-${base.year}.jpg`;
        const img = await fetch(`https://image.tmdb.org/t/p/w780${d.poster_path}`);
        if (img.ok) { fs.writeFileSync(path.join(__dirname, file), Buffer.from(await img.arrayBuffer())); poster = file; }
      } else review.push(`${base.title} (${base.year}): no poster on TMDB`);

      // Studio logo for the top of the spine: the first production company TMDB has a logo for.
      const co = (d.production_companies || []).find((c) => c.logo_path);
      let logo = '';
      if (co) {
        const file = `logos/${co.id}${path.extname(co.logo_path) || '.png'}`;
        if (fs.existsSync(path.join(__dirname, file))) logo = file;
        else {
          const li = await fetch(`https://image.tmdb.org/t/p/w185${co.logo_path}`);
          if (li.ok) { fs.writeFileSync(path.join(__dirname, file), Buffer.from(await li.arrayBuffer())); logo = file; }
        }
      }

      const director = isTv ? (d.created_by || [])[0] : (d.credits?.crew || []).find((c) => c.job === 'Director');
      films.push({
        ...(old || {}), // keep manual edits (font, color, note, tmdbOverride)
        ...base,
        tmdb: d.id,
        tmdbKind: isTv ? 'tv' : 'movie',
        runtime: (isTv ? (d.episode_run_time || [])[0] : d.runtime) || undefined,
        director: director ? director.name : undefined,
        genres: (d.genres || []).map((g) => g.name),
        imdb: d.external_ids?.imdb_id || base.imdb || '',
        poster,
        studio: co ? co.name : '',
        logo,
      });
      console.log('ok');
    } catch (e) {
      console.log('error: ' + e.message);
      review.push(`${base.title} (${base.year}): ${e.message}`);
      films.push({ ...(old || {}), ...base, genres: (old && old.genres) || [], imdb: base.imdb || (old && old.imdb) || '', poster: (old && old.poster) || '' });
    }
    await new Promise((r) => setTimeout(r, 120)); // be polite to the API
  }

  films.sort((a, b) => a.watched.localeCompare(b.watched));
  fs.writeFileSync(OUT, JSON.stringify({ year: Number(YEAR), films }, null, 2) + '\n');
  fs.writeFileSync(path.join(__dirname, 'needs_review.txt'), review.length ? review.join('\n') + '\n' : 'All matches looked confident.\n');
  console.log(`\nWrote films.json (${films.length} films). ${review.length ? review.length + ' to double-check, see needs_review.txt' : 'No matches flagged.'}`);
})();
