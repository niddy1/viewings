# Viewings

A shelf of VHS tapes, one per film Ian watched in 2026. Spines face out; clicking one pulls the tape out to a cover view with his rating and details; clicking the cover opens the film on IMDb. Live at ianandreu.com/viewings via GitHub Pages (this repo: niddy1/viewings, branch `main`, served from root).

## Stack
Plain HTML/CSS/JS. No build step, no dependencies, no framework. Keep it that way. All paths must stay relative (the site lives under `/viewings`).

## Files
- `index.html`, `style.css`, `app.js`: the whole site. `app.js` loads `films.json` and shows each tape's designed spine image if it has one (see "Designed spine images" below; since November 2026 all 71 do). For a film without one it draws the spine itself (all the same height; thickness by runtime; the title lettering is lifted off the poster using each film's `titleBox` (colour-keyed from flat backgrounds, light/dark-keyed from busy ones, so it sits straight on the spine colour); spine colours come from the poster palette with browns/tans/olives deliberately avoided (black, charcoal and vivid colours instead; `color` in films.json overrides); tapes sit flush with no gaps; and painted per-tape wear (white cardboard fraying at the top, rubbed edges, scuffs, creases; seeded per film so it is stable), rental stickers and fading), and handles the pull-out viewer.
- `films.json`: generated data (title, year, rating, watched date, genres, imdb id, poster path). Optional hand-edited fields per film: `font`, `color`, `note`, plus the spine-top fields set from the Re-mark spine editor: `top` (`logo` | `photo` | `tag` | `sticker` | `none`; absent = the seeded auto choice), `photoBox` (square `[x0,y0,x1,y1]` poster crop for the framed picture; absent = auto crop) `logoBox` (`[x0,y0,x1,y1]` crop of the logo image) and `logoStyle` (`color` | `white`; absent = auto: logos with real colour keep it, with black ink lifted to off-white on dark spines; the rest get a one-colour print that keeps lettering knocked out of any box, light on dark spines and dark on pale ones). `titleBox` is a list of `[x0,y0,x1,y1]` boxes (fractions 0-1 of the poster, one per line of lettering, top line first) that mark where the title is on the poster; films without one fall back to the title in a genre font (currently Zootopia 2, Heel, Coyote vs. Acme, Deep Water, Heart of the Beast, whose lettering is tilted, cropped or absent). `studio`/`logo` come from the fetch script.
- `posters/`: poster images, committed to the repo so the site doesn't depend on TMDB at runtime.
- `vcr.js`: hidden in-browser updater. Typing `vcr` (or `#vcr` in the URL) opens a panel that takes the PassThePopcorn ratings CSV, filters to the shelf's `year`, matches by IMDb id, looks up new films on TMDB from the browser, lets Ian drag `titleBox`es on new posters, and commits `films.json` + posters via the GitHub Git Data API in one commit. GitHub token and TMDB key live in his browser's localStorage only. It also adds a "Re-mark spine" link to the viewer (only when the GitHub token is in localStorage) for redrawing an existing film's `titleBox`, choosing/cropping the top of the spine (`top`, `photoBox`, `logoBox`) and picking a different studio logo from the film's TMDB production companies (downloads it into `logos/`), all with a live spine preview; edits queue and save in one commit that touches only those fields (plus any new logo file). `app.js` exposes `window.viewings` (`films`, `current`, `preview(f)`, `refresh(f)`) for this. Logos are not fetched here (the shelf doesn't have any yet; adding them for only new films would look inconsistent).
- `fetch-posters.js`: Node 18+ script that builds `films.json` + `posters/` from the PTP ratings CSV (or a Letterboxd `diary.csv`) using the TMDB API. Safe to re-run; only fetches films that are new.
- `logos/`: studio logos from TMDB, printed at the top of the spine (in colour or one-colour, see `logoStyle`). Only present after Ian re-runs the fetch script (see below).
- The shelf itself is all CSS (`style.css`, "shelf" section), modelled on Ian's reference photo of a home-built VHS case, then stained mahogany at his request: mahogany face frame, pale woodgrain wall panelling with dark grooves at uneven spacing, thin shelf boards on cleat blocks. Wood grain is SVG `feTurbulence` in data URIs (the `--pine-*` / `--panel-*` variables), so no texture images. `app.js` reads the case's padding and `--end-gap` to work out how many tapes fit per row.
- `wall/`: Ian's own poster images (Anatomy of a Murder, Bande à part), hung full-size (560px wide, about real scale next to the tapes) in black frames either side of the case (`.room` in `index.html`). They hang off the case's edges and are allowed to run off the window (Ian's call); the case never narrows for them. Desktop only (≥1100px; hidden on phones).
- Header: the "Watched 2026" ticket image (`watched-2026.png`, Ian's artwork; the old "Viewings 2026" text is kept visually hidden for screen readers and holds `#year`) and, top right just above the case, the tally "<n> TAPES" in Blockletter (`fonts/Blockletter.otf`, free for personal use; keep `fonts/Blockletter-readme.txt` with it). The number is `#count` (2x the size of TAPES), set from `films.length` in `app.js`.
- Sort and genre filter: `.controls` in the header, bottom left opposite the tally (static on phones). Sort by Date watched (oldest first), Rating (`rating10`, best first) or Year (newest first); clicking the active sort reverses it, and ties keep watched order. The Genre button opens a list of chips built from the films' `genres` (most common first, with counts); picking several shows films with ANY of them. State lives in the URL (`?sort=rating`, `?sort=year-rev`, `?genre=Horror,Comedy`), so a sorted/filtered shelf can be shared. `order` in `app.js` is the shown films (indices into `films`, which stays in watched order for vcr.js); `layout()` shelves `order`, the viewer's prev/next steps through it, and the tally shows its length. There is also an IMDb sort (`imdbRating`, best first; films without one go last) and the viewer shows "IMDb x.x" under the stars. `imdbRating`/`imdbVotes` in films.json were scraped once on 16 Nov 2026 from imdb.com title pages' JSON-LD (`aggregateRating`) by running fetch() in Ian's built-in browser on imdb.com (the workspace can't reach IMDb/TMDB). They don't update themselves; refresh the same way, and new VCR arrivals have none until then. vcr.js keeps unknown fields on existing films.
- Loading screen: until `layout()` stocks the shelf, `#shelves` shows `loading.webp` (Ian's 'Refreshments' popcorn GIF, converted to animated WebP: 286KB vs 990KB) with "Stocking the shelf..." in Blockletter. The tally is `hidden` until the count is known.
- `overrides.json`: fixes wrong TMDB matches, keyed `"Title|Year"` with `{ "tmdb": <id>, "type": "tv" (optional) }`.

## Shelves by year
Each year is its own shelf. `SHELVES` near the top of `app.js` maps year -> data file: the newest year is `films.json`, older years are `films-<year>.json` (currently `films-2025.json`, 64 films, seeded 16 Nov 2026 from the PTP CSV with TMDB details and IMDb scores; posters and studio logos come from Ian running `fetch-posters.js ... 2025`). `?shelf=2025` picks the shelf (no param = newest); the header swaps to `watched-<year>.png` (the 2025 ticket is Ian's 2026 artwork with the 6 reshaped into a 5 from its own strokes, not a font) and arrows either side of the ticket (`#shelf-prev` / `#shelf-next`, older on the left) link to the neighbouring years, keeping the sort and dropping the genre filter. `window.viewings.dataFile` tells vcr.js which file to read and commit, so the VCR and Re-mark spine work on whichever shelf is open. `fetch-posters.js` writes `films.json` when the year matches its `year`, else `films-<year>.json`. To add a year: add it to `SHELVES`, make its ticket image, and (when the year rolls over) move the old `films.json` to `films-<old year>.json` and point the new year at `films.json`.

## Designed spine images (`posters/<name>-spine-b.jpg`)
One designed spine picture per tape, made in November 2026 with `spinegen/` (ported from niddy1/readings and adapted for VHS). Live on the site since 14 November 2026 (all 71 tapes). The shelf uses them: `prepare()` in `app.js` looks for `<poster name>-spine-b.jpg` next to the poster and, if it loads, `spineEl()` shows it as the whole spine (`.spine.designed`). For a designed tape, `prepare()` loads only the spine picture, not the full poster (the poster loads when the tape is pulled out); this cut the first load from about 19MB to 2MB. A film without one (a new arrival from VCR) falls back to the drawn spine, and the Re-mark spine editor still works on it; the editor's top/picture/logo choices do not change a designed image (the button is hidden for those tapes), so change a designed spine by editing its spec and re-running the script. Deleting a film's `-spine-b.jpg` reverts it to the drawn spine. Each is drawn at 1100px tall and saved at 550px (`WEB_H` in `spinegen/lib.py`, twice the 250px shown, for retina; the 1100px files made the first load slow); width follows the shelf's runtime rule (42-52px at 250px tall), so they can drop in at the current tape widths.

- `spinegen/lib.py`: text rendering and `finish_vhs()`, which ages the box. `kind='slip'` is a card slipcase (white board at the folds, corners and mouth, scuffs, dents, torn patches, shelf rub); `kind='clam'` is a plastic clamshell (Zootopia 2, Hoppers, Toy Story 5). Wear is seeded per tape; nothing is identical on two spines.
- `spinegen/eng.py`: layout engine (background + top-to-bottom items; text shrinks to fit). `L(...)` lifts the title lettering off the poster from the film's `titleBox` and re-inks it; `TT` is a line in several colours; `notch()` is the thumb cut-out at the foot.
- `spinegen/tapes.py`: one hand-written spec per tape (`std(...)` for the usual layout, `add(...)` for the first five), plus the spine furniture: `logo()` (places the film's file from `logos/`, as is or in one ink; never redrawn), stickers (`rewind`, `barcode`, `price`, `dot`), format mark and catalogue numbers.
- Run from the repo root: `python3 spinegen/tapes.py` (all) or `python3 spinegen/tapes.py sinners-2025 creed-2015` (some). Needs Pillow, NumPy, OpenCV. Fonts are bundled in `spinegen/fonts/`. Output is deterministic.
- Titles are lifted from the poster where the `titleBox` gives a clean result and typeset otherwise (e.g. F1, Heel, Crime 101, Marty Supreme, Con Air, Face/Off, Spider-Man, the films with no `titleBox`).
- Catalogue numbers, sticker text and prices are invented. Malice uses the Castle Rock logo file because `films.json` has the wrong studio (Nelvana) for it.
- Check new spines scaled to 250px tall; thin lettering fades at that size.
- Rules Ian has set for spines: card wear must never show on the cassette inside the thumb notch (it is plastic; `finish_vhs(notch=...)` repaints it after the wear), the VHS mark and numbers always sit at the foot, and every spine has its title running down it (no title blocks set across the top; Girl in the Box and The Devil Wears Prada 2 were redone for this on 16 November 2026).
- Disney and Pixar films do not use the slipcase layout: see "Disney and Pixar clamshells" below.
- Look and sources: modelled on Ian's reference image of modern films given retro VHS box spines (title in the poster's own lettering, a framed picture at the head, studio logo, format mark and catalogue number at the foot, rental stickers, worn card). Studio logos and poster crops (including animated and comic characters) are welcome on spines; logos are placed from `logos/`, never redrawn. The typed-only "ZIPPORAH FILMS" (High School) and "UTOPIA" (The Sweet East), and the cast/director credit lines on some spines, were written from memory and may be wrong.
- Five tapes have no logo file and carry a line of type instead: High School, The Sweet East, Louis C.K.: Ridiculous, Jeff Arcuri, Face/Off.
- Not verified: that the "Re-mark spine" button is hidden on designed tapes (it only shows with the GitHub token saved, so it could not be seen in a test browser).
- Ian decided against making the generator follow the Re-mark spine editor (a GitHub Action re-rendering on each edit was considered and dropped as too much trouble). To change a designed spine, ask Claude to edit its spec.
- To add a tape: add a spec to `tapes.py` (copy a similar one), pick the `photo=ph(cx, cy, w, ar)` crop so it avoids the poster's title, run the script for that key.

## Disney and Pixar clamshells
Ian's rule (16 November 2026): **every Disney or Pixar film gets the white plastic clamshell, never a slipcase.** Currently Zootopia 2, Hoppers and Toy Story 5. The Devil Wears Prada 2 (20th Century Studios), Con Air (Touchstone) and Spider-Man (Marvel) are Disney-owned labels or partners and stay in slipcases unless Ian says otherwise. The model is the 1990s Walt Disney "Classics" clamshell spine, from his reference photos.

### What the spine must have, top to bottom
1. **White cap**: bright, clean white plastic showing above the paper insert (and the same at the foot). No yellowing or grime.
2. **Head emblem**: the thin black diamond, `logos/classics-diamond.png`. This is Ian's own low-res photo crop of the emblem, squared up and placed as a picture. It is never redrawn in code; if the file is missing a plain black diamond with "VHS 2026" is drawn instead. A sharper photo saved over the file is picked up on the next render.
3. **Studio logo reading down** the spine, in one ink, from the film's `logos/` file (left out when the title logo already carries the studio's name, as on Zootopia 2).
4. **Title in the film's own logo lettering**, reading down. Never a generic typeset title if the real logo can be had (see "Getting the title" below).
5. **One character's face in a red diamond** near the foot. A true diamond, clearly taller than wide, not a square on its corner, and a single face, not a group.
6. **CC box, "VHS", catalogue number** at the foot, then the bottom white cap.

Artwork or a colour taken from the poster runs the full length behind all of it. No thumb notch, no stickers, no card wear.

### The case itself
- **Bigger than a slipcase**: drawn 1.15x a slipcase's width and 1188px tall (1100 + a 44px cap each end), so on the shelf it stands about 270px tall and 49px wide beside 250px slipcases. (1.26x was tried first; Ian wanted it a tad slimmer.) `prepare()` in `app.js` sizes any spine picture taller than 560px from the picture itself and adds the `clam` class.
- **Rounded plastic, not a flat face**: the picture is shaded as a curved moulding falling away to both long edges, and `.spine.designed.clam` in `style.css` adds the same roll-off.
- **Ends close to square**: 4px corner radius, with the cap standing slightly proud of the sleeve. A rounder end was tried and Ian found it too rounded.
- **Bright print**: if a clamshell looks dark or dull, pass `fin=dict(CLAM, vivid=.2 to .3)` (Toy Story 5 and Hoppers use it).

### How to make one
1. In `spinegen/tapes.py`, add a `disney(...)` call in the "Disney and Pixar" block (copy the nearest of the three):
   `disney(id, bg, title, face, lcol=..., ink=..., studio=True, fin=dict(CLAM, vivid=.25))`
   - `id`: the poster file name without `.jpg`.
   - `bg`: `('strip', dict(x0=..., blur=14, wash=((r, g, b), .6)))` for blurred poster artwork tinted to one colour, or `('grad', [...])` for a colour run taken from the poster.
   - `title`: see below.
   - `face`: `ph(cx, cy, w, 1.4)`, a poster crop centred on one character's face (`w` about .2). Find the face by cropping the poster with a coordinate grid first; a guess usually lands on an ear or a neighbour.
   - `lcol` / `ink`: colour of the studio logo and of the CC/VHS/number (dark on a pale spine).
   - `studio=False` drops the studio logo line; `side=4` lets a wide title logo use nearly the full width.
2. **Getting the title**, in order of preference:
   - Ian supplies the title logo as an image: save it in `logos/<film>-title.png` and use `Pic('logos/<film>-title.png', size)`. If it sits on a coloured field that can't be cut away cleanly, keep the field, feather the edges to transparent, and grade the spine `bg` to match (Zootopia 2).
   - The logo is on the poster in one colour on a plain ground: `L(tb(id), size, ink)` (Hoppers).
   - The logo is on the poster in several colours: `LC([boxes...], size, cuts=[...])` cuts each piece out in its own colours. Toy Story 5 is the pattern for a stacked logo: its pieces are laid along the spine in reading order (TOY, the red STORY plate, the 5) the way the real Toy Story tapes did, using `ts_letters` and `ts_plate`.
   - Only if none of those work, typeset it, and tell Ian so he can supply the logo.
3. Render and check: `python3 spinegen/tapes.py <id>`, look at the picture at full size (cap, emblem, title, a single face in the diamond), then serve the site and screenshot the tape on the shelf next to its neighbours (see Workflow notes).
4. Logos and emblems are only ever placed from image files (TMDB's or Ian's). Never redraw one in code.

### Where the code is
- `disney()`, `head_emblem()`, `head_diamond()` (fallback), `vlogo()`, `portrait()`, `ccbox()` in `spinegen/tapes.py`.
- `Pic` (a logo picture as a title line) and `LC` (multi-colour lift) in `spinegen/eng.py`.
- `finish_vhs(kind='clam', vivid=...)` and `CLAM_CAP` in `spinegen/lib.py`: caps, sleeve edge, curved shading.
- `.spine.designed.clam` in `style.css`; the `f._clam` sizing in `prepare()` in `app.js`.

## Workflow notes
- **Whenever a new film is added to the shelf (VCR commit, fetch script, or by hand), refresh the IMDb scores for every film, the new ones included.** How: open any imdb.com page in Ian's built-in browser (the site is already allowed), run one fetch() script there over all the films' `imdb` ids (`/title/<id>/`, read `aggregateRating.ratingValue`/`ratingCount` from the page's `<script type="application/ld+json">`, about six at a time), then write `imdbRating`/`imdbVotes` into films.json (keep its 2-space JSON format) and push with the new film. Takes a few seconds; don't open the pages one by one.
- Publishing: `main` is the live site. Claude pushes work to a branch and Ian merges it on github.com (Compare & pull request → Create pull request → Merge pull request → Confirm merge), then waits a minute or two and hard-refreshes. Claude can merge and push to `main` instead if Ian asks.
- The site can be checked in Claude's workspace before pushing: `python3 -m http.server` in the repo root, then load it with Playwright driving `/usr/bin/google-chrome` and screenshot (count `.spine.designed`).
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
