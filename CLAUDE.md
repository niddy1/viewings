# Viewings

A shelf of VHS tapes, one per film Ian watched in 2026. Spines face out; clicking one pulls the tape out to a cover view with his rating and details; clicking the cover opens the film on IMDb. Live at ianandreu.com/viewings via GitHub Pages (this repo: niddy1/viewings, branch `main`, served from root).

## Stack
Plain HTML/CSS/JS. No build step, no dependencies, no framework. Keep it that way. All paths must stay relative (the site lives under `/viewings`).

## Files
- `index.html`, `style.css`, `app.js`: the whole site. `app.js` loads `films.json`, draws spines (colour from the poster's average colour, title font picked by genre, thickness by runtime), and handles the pull-out viewer.
- `films.json`: generated data (title, year, rating, watched date, genres, imdb id, poster path). Optional hand-edited fields per film: `font`, `color`, `note`.
- `posters/`: poster images, committed to the repo so the site doesn't depend on TMDB at runtime.
- `fetch-posters.js`: Node 18+ script that builds `films.json` + `posters/` from Letterboxd's `diary.csv` using the TMDB API. Safe to re-run; only fetches films that are new.
- `overrides.json`: fixes wrong TMDB matches, keyed `"Title|Year"` with `{ "tmdb": <id>, "type": "tv" (optional) }`.

## Workflow notes
- The fetch step must run on Ian's own Mac (`TMDB_KEY=... node fetch-posters.js diary.csv`). Claude's workspace cannot reach TMDB or download images.
- `diary.csv` is gitignored. Only 2026 watches are used (by Watched Date).
- Never commit or write the TMDB key or token anywhere. They were pasted in chat once; Ian should regenerate them.
- Preview locally with `npx serve .` (films.json is loaded with fetch, so file:// won't work).
- Pushing the posters over HTTPS hit an HTTP 400; fixed locally with `git config http.postBuffer 524288000` and `git config http.version HTTP/1.1`.
- TMDB attribution footer is required by their terms; keep it.
- Spine title fonts are an approximation (matched by genre), not the actual poster fonts. A film can be overridden with `font` in `films.json` (add the font to the Google Fonts link in `index.html`).

## Known stray file
`poster pull instructions.png` is in the repo root; it's served publicly and is probably safe to delete.
