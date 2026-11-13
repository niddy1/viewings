# Viewings

A shelf of VHS tapes, one per film Ian watched in 2026. Spines face out; clicking one pulls the tape out to a cover view with his rating and details; clicking the cover opens the film on IMDb. Live at ianandreu.com/viewings via GitHub Pages (this repo: niddy1/viewings, branch `main`, served from root).

## Stack
Plain HTML/CSS/JS. No build step, no dependencies, no framework. Keep it that way. All paths must stay relative (the site lives under `/viewings`).

## Files
- `index.html`, `style.css`, `app.js`: the whole site. `app.js` loads `films.json`, draws spines (all the same height; thickness by runtime; the title lettering is lifted off the poster using each film's `titleBox` (colour-keyed from flat backgrounds, light/dark-keyed from busy ones, so it sits straight on the spine colour); spine colours come from the poster palette with browns/tans/olives deliberately avoided (black, charcoal and vivid colours instead; `color` in films.json overrides); tapes sit flush with no gaps; and painted per-tape wear (white cardboard fraying at the top, rubbed edges, scuffs, creases; seeded per film so it is stable), rental stickers and fading), and handles the pull-out viewer.
- `films.json`: generated data (title, year, rating, watched date, genres, imdb id, poster path). Optional hand-edited fields per film: `font`, `color`, `note`, plus the spine-top fields set from the Re-mark spine editor: `top` (`logo` | `photo` | `tag` | `sticker` | `none`; absent = the seeded auto choice), `photoBox` (square `[x0,y0,x1,y1]` poster crop for the framed picture; absent = auto crop) and `logoBox` (`[x0,y0,x1,y1]` crop of the logo image). `titleBox` is a list of `[x0,y0,x1,y1]` boxes (fractions 0-1 of the poster, one per line of lettering, top line first) that mark where the title is on the poster; films without one fall back to the title in a genre font (currently Zootopia 2, Heel, Coyote vs. Acme, Deep Water, Heart of the Beast, whose lettering is tilted, cropped or absent). `studio`/`logo` come from the fetch script.
- `posters/`: poster images, committed to the repo so the site doesn't depend on TMDB at runtime.
- `vcr.js`: hidden in-browser updater. Typing `vcr` (or `#vcr` in the URL) opens a panel that takes the PassThePopcorn ratings CSV, filters to the shelf's `year`, matches by IMDb id, looks up new films on TMDB from the browser, lets Ian drag `titleBox`es on new posters, and commits `films.json` + posters via the GitHub Git Data API in one commit. GitHub token and TMDB key live in his browser's localStorage only. It also adds a "Re-mark spine" link to the viewer (only when the GitHub token is in localStorage) for redrawing an existing film's `titleBox`, choosing/cropping the top of the spine (`top`, `photoBox`, `logoBox`) and picking a different studio logo from the film's TMDB production companies (downloads it into `logos/`), all with a live spine preview; edits queue and save in one commit that touches only those fields (plus any new logo file). `app.js` exposes `window.viewings` (`films`, `current`, `preview(f)`, `refresh(f)`) for this. Logos are not fetched here (the shelf doesn't have any yet; adding them for only new films would look inconsistent).
- `fetch-posters.js`: Node 18+ script that builds `films.json` + `posters/` from the PTP ratings CSV (or a Letterboxd `diary.csv`) using the TMDB API. Safe to re-run; only fetches films that are new.
- `logos/`: studio logos from TMDB, shown as white silhouettes at the top of the spine. Only present after Ian re-runs the fetch script (see below).
- `overrides.json`: fixes wrong TMDB matches, keyed `"Title|Year"` with `{ "tmdb": <id>, "type": "tv" (optional) }`.

## Workflow notes
- The fetch step must run on Ian's own Mac (`TMDB_KEY=... node fetch-posters.js diary.csv`). Claude's workspace cannot reach TMDB or download images.
- Source of ratings is now PassThePopcorn (`Title, Rating10, WatchedDate, ImdbID`), out of 10. Stored as `rating10`; `rating` = `Math.round(rating10)/2` for the stars. The viewer shows `x / 10`. Only rows whose WatchedDate is in the shelf's year are used.
- `diary.csv` is gitignored. Don't commit ratings CSVs either.
- Never commit or write the TMDB key or token anywhere. They were pasted in chat once; Ian should regenerate them.
- Preview locally with `npx serve .` (films.json is loaded with fetch, so file:// won't work).
- Pushing the posters over HTTPS hit an HTTP 400; fixed locally with `git config http.postBuffer 524288000` and `git config http.version HTTP/1.1`.
- TMDB attribution footer is required by their terms; keep it.
- Spine title fonts are an approximation (matched by genre), not the actual poster fonts. A film can be overridden with `font` in `films.json` (add the font to the Google Fonts link in `index.html`).

- `titleBox`es are drawn by Ian in the browser (VCR for new films, Re-mark spine for existing ones). OCR was tried and was unreliable on stylised lettering.
- Re-running `fetch-posters.js` once will backfill `studio` + `logo` for the existing films (posters are kept). Never draw studio logos by hand; only use TMDB's.

## Known stray file
`poster pull instructions.png` is in the repo root; it's served publicly and is probably safe to delete.
