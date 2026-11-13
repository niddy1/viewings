#!/usr/bin/env node
/*
 * Builds films.json + posters/ from your Letterboxd diary export.
 *
 *   TMDB_KEY=your_key node fetch-posters.js [path/to/diary.csv] [year]
 *
 * - Needs Node 18+ (built-in fetch). No npm install.
 * - TMDB_KEY can be either the v3 API key or the v4 "Read Access Token".
 * - Safe to re-run: films already in films.json keep their poster, any manual
 *   edits (font, color, note) and are not re-fetched.
 * - Matches TMDB couldn't make confidently are listed in needs_review.txt.
 */
const fs = require('fs');
const path = require('path');

const KEY = process.env.TMDB_KEY;
const CSV = process.argv[2] || 'diary.csv';
const YEAR = String(process.argv[3] || process.env.YEAR || new Date().getFullYear());
const OUT = path.join(__dirname, 'films.json');
const POSTERS = path.join(__dirname, 'posters');

if (!KEY) { console.error('Set TMDB_KEY first, e.g.  TMDB_KEY=abc123 node fetch-posters.js diary.csv'); process.exit(1); }
if (!fs.existsSync(CSV)) { console.error(`Can't find ${CSV}. Pass the path to Letterboxd's diary.csv.`); process.exit(1); }
fs.mkdirSync(POSTERS, { recursive: true });

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
  const iName = col('Name'), iYear = col('Year'), iRating = col('Rating'), iRewatch = col('Rewatch'), iWatched = col('Watched Date');
  if ([iName, iYear, iWatched].includes(-1)) { console.error('That CSV is missing Name / Year / Watched Date columns. Is it diary.csv?'); process.exit(1); }

  const byFilm = new Map();
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
  console.log(`${byFilm.size} films watched in ${YEAR}.`);

  // ---- merge with existing
  let existing = new Map();
  if (fs.existsSync(OUT)) {
    try {
      const old = JSON.parse(fs.readFileSync(OUT, 'utf8'));
      for (const f of old.films || []) if (f.imdb || f.poster) existing.set(key(f.title, f.year), f);
    } catch {}
  }

  const review = [];
  const films = [];
  let n = 0;
  for (const base of byFilm.values()) {
    n++;
    const k = key(base.title, base.year);
    const old = existing.get(k);
    if (old && old.imdb && old.poster && fs.existsSync(path.join(__dirname, old.poster))) {
      films.push({ ...old, rating: base.rating, watched: base.watched, rewatch: base.rewatch });
      continue;
    }
    process.stdout.write(`[${n}/${byFilm.size}] ${base.title} (${base.year}) ... `);
    try {
      let search = await tmdb('/search/movie', { query: base.title, year: base.year });
      let hit = search.results[0];
      if (!hit) { search = await tmdb('/search/movie', { query: base.title }); hit = search.results[0]; if (hit) review.push(`${base.title} (${base.year}): no match for that year, used "${hit.title}" (${(hit.release_date || '').slice(0, 4)})`); }
      if (!hit) { review.push(`${base.title} (${base.year}): NOT FOUND`); films.push({ ...base, genres: [], imdb: '', poster: '' }); console.log('not found'); continue; }

      const d = await tmdb(`/movie/${hit.id}`, { append_to_response: 'credits,external_ids' });
      const relYear = Number((d.release_date || '').slice(0, 4));
      if (Math.abs(relYear - base.year) > 1 || d.title.toLowerCase() !== base.title.toLowerCase())
        review.push(`${base.title} (${base.year}): matched "${d.title}" (${relYear}) - check this one`);

      let poster = '';
      if (d.poster_path) {
        const file = `posters/${slug(base.title)}-${base.year}.jpg`;
        const img = await fetch(`https://image.tmdb.org/t/p/w780${d.poster_path}`);
        if (img.ok) { fs.writeFileSync(path.join(__dirname, file), Buffer.from(await img.arrayBuffer())); poster = file; }
      } else review.push(`${base.title} (${base.year}): no poster on TMDB`);

      const director = (d.credits?.crew || []).find((c) => c.job === 'Director');
      films.push({
        ...base,
        runtime: d.runtime || undefined,
        director: director ? director.name : undefined,
        genres: (d.genres || []).map((g) => g.name),
        imdb: d.external_ids?.imdb_id || '',
        poster,
      });
      console.log('ok');
    } catch (e) {
      console.log('error: ' + e.message);
      review.push(`${base.title} (${base.year}): ${e.message}`);
      films.push({ ...base, genres: [], imdb: '', poster: '' });
    }
    await new Promise((r) => setTimeout(r, 120)); // be polite to the API
  }

  films.sort((a, b) => a.watched.localeCompare(b.watched));
  fs.writeFileSync(OUT, JSON.stringify({ year: Number(YEAR), films }, null, 2) + '\n');
  fs.writeFileSync(path.join(__dirname, 'needs_review.txt'), review.length ? review.join('\n') + '\n' : 'All matches looked confident.\n');
  console.log(`\nWrote films.json (${films.length} films). ${review.length ? review.length + ' to double-check, see needs_review.txt' : 'No matches flagged.'}`);
})();
