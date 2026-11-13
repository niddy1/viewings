# Viewings

A shelf of VHS tapes, one for every film I've watched this year. Spines face out; click one to pull it off the shelf and see the cover, my rating and the details. Click the cover to open the film on IMDb.

Plain HTML/CSS/JS. No build step, no dependencies. Lives at `ianandreu.com/viewings`.

## Run locally

`films.json` is loaded with `fetch`, so serve the folder rather than opening the file directly:

```
npx serve .
# or
python3 -m http.server 8000
```

## Update the shelf

### From the site (the VCR)

Type **`vcr`** anywhere on the page (on a phone, open the page with `#vcr` at the end of the URL). A little panel opens:

1. The first time, paste two keys. They're saved in that browser's localStorage only, never in the repo:
   - **GitHub token**: GitHub → Settings → Developer settings → Fine-grained tokens → generate one with access to **only** `niddy1/viewings` and **Contents: Read and write**.
   - **TMDB key**: from [themoviedb.org](https://www.themoviedb.org/settings/api) (the v3 key or the v4 read token).
2. Drop in your PassThePopcorn ratings CSV (`Title, Rating10, WatchedDate, ImdbID`).
3. It keeps only films rated in the shelf's year (`year` in `films.json`), matches them by IMDb id, syncs ratings and dates, and looks up new films on TMDB.
4. For each new film, drag a box around each line of the title on the poster (that's the spine lettering). Skip it and the spine uses a typeface.
5. **Record to shelf** makes one commit with `films.json` and the new posters. GitHub Pages redeploys in about a minute.

Films on the shelf that aren't in the CSV are kept unless you tick them for removal.

### Fixing a janky spine

In a browser where the VCR's GitHub token is saved, pull out any tape and click **✎ Re-mark spine** under "Put it back". Redraw the boxes around the title lettering (or clear them to use a typeface) and watch the preview. **Keep** applies it to the shelf; a **Save N spines** button then commits all your edits in one go. Visitors never see the button, and saving needs the token.

### From the command line

```
TMDB_KEY=your_key node fetch-posters.js path/to/ratings.csv
```

(Node 18+.) Takes the PTP CSV (or an old Letterboxd `diary.csv`), downloads posters into `posters/` and rewrites `films.json`. Re-running only fetches films that are new. Skim `needs_review.txt` afterwards.

Ratings are stored out of 10 as `rating10`; the stars round to the nearest half (8.5 → 4½, 7.5 → 4) and `rating` keeps that star value.

Poster images come from TMDB; film data is theirs too. Their API terms ask for an attribution line, so keep the footer credit if you add one.

## Customising a tape

Any film in `films.json` accepts these optional fields:

| field   | what it does                                            |
|---------|---------------------------------------------------------|
| `font`  | Google Font for the spine title (add it to `index.html`'s font link if it's new) |
| `color` | Any CSS colour for the spine body (default: derived from the poster) |
| `note`  | A line shown under the genres in the cover view         |
| `tmdbOverride` | (Or use `overrides.json`, keyed `"Title|Year"`, with `"type": "tv"` for TV titles.) Fixes a wrong match: the number from the film's TMDB URL (`themoviedb.org/movie/`**`603`**`-the-matrix`). Re-run `fetch-posters.js` and that film's poster, IMDb link and details are re-fetched from the right movie. |

Spine thickness follows runtime. Spine fonts are picked by genre unless you set `font`.

## Putting it at /viewings

The site uses only relative paths, so it works from any subfolder. Options:

- **GitHub Pages + custom path**: publish this repo with Pages, then have the main site proxy or redirect `/viewings` to it.
- **Same host as the main site**: deploy this repo's contents into a `viewings/` folder of the site (a CI step that copies it over works well).
- **Vercel/Netlify**: deploy this repo as its own project and add a rewrite for `/viewings/*` from the main project.

## Keyboard

`←` / `→` flip between tapes, `Esc` puts it back.
