# Viewings

A shelf of VHS tapes, one per film Ian watched in 2026. Spines face out; clicking one pulls the tape out to a cover view with his rating and details; clicking the cover opens the film on IMDb. Live at ianandreu.com/viewings via GitHub Pages (this repo: niddy1/viewings, branch `main`, served from root).

## Stack
Plain HTML/CSS/JS. No build step, no dependencies, no framework. Keep it that way. All paths must stay relative (the site lives under `/viewings`).

## Files
- `index.html`, `style.css`, `app.js`: the whole site. `app.js` loads `films.json`, draws spines (all the same height; thickness by runtime; the title lettering is lifted off the poster using each film's `titleBox` (colour-keyed from flat backgrounds, light/dark-keyed from busy ones, so it sits straight on the spine colour); spine colours come from the poster palette with browns/tans/olives deliberately avoided (black, charcoal and vivid colours instead; `color` in films.json overrides); tapes sit flush with no gaps; and painted per-tape wear (white cardboard fraying at the top, rubbed edges, scuffs, creases; seeded per film so it is stable), rental stickers and fading), and handles the pull-out viewer.
- `films.json`: generated data (title, year, rating, watched date, genres, imdb id, poster path). Optional hand-edited fields per film: `font`, `color`, `note`. `titleBox` is a list of `[x0,y0,x1,y1]` boxes (fractions 0-1 of the poster, one per line of lettering, top line first) that mark where the title is on the poster; films without one fall back to the title in a genre font (currently Zootopia 2, Heel, Coyote vs. Acme, Deep Water, Heart of the Beast, whose lettering is tilted, cropped or absent). `studio`/`logo` come from the fetch script.
- `posters/`: poster images, committed to the repo so the site doesn't depend on TMDB at runtime.
- `fetch-posters.js`: Node 18+ script that builds `films.json` + `posters/` from Letterboxd's `diary.csv` using the TMDB API. Safe to re-run; only fetches films that are new.
- `logos/`: studio logos from TMDB, shown as white silhouettes at the top of the spine. Only present after Ian re-runs the fetch script (see below).
- `overrides.json`: fixes wrong TMDB matches, keyed `"Title|Year"` with `{ "tmdb": <id>, "type": "tv" (optional) }`.

## Workflow notes
- The fetch step must run on Ian's own Mac (`TMDB_KEY=... node fetch-posters.js diary.csv`). Claude's workspace cannot reach TMDB or download images.
- `diary.csv` is gitignored. Only 2026 watches are used (by Watched Date).
- Never commit or write the TMDB key or token anywhere. They were pasted in chat once; Ian should regenerate them.
- Preview locally with `npx serve .` (films.json is loaded with fetch, so file:// won't work).
- Pushing the posters over HTTPS hit an HTTP 400; fixed locally with `git config http.postBuffer 524288000` and `git config http.version HTTP/1.1`.
- TMDB attribution footer is required by their terms; keep it.
- Spine title fonts are an approximation (matched by genre), not the actual poster fonts. A film can be overridden with `font` in `films.json` (add the font to the Google Fonts link in `index.html`).

- New films need a `titleBox` added by hand (look at the poster, estimate the lettering as fractions); the OCR approach was tried and was unreliable on stylised lettering, so boxes were placed by eye.
- Re-running `fetch-posters.js` once will backfill `studio` + `logo` for the existing films (posters are kept). Never draw studio logos by hand; only use TMDB's.

## Known stray file
`poster pull instructions.png` is in the repo root; it's served publicly and is probably safe to delete.
