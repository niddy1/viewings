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

## Update the shelf from Letterboxd

1. Letterboxd → Settings → Import & Export → **Export your data**. Unzip it and grab `diary.csv`.
2. Get a free API key from [themoviedb.org](https://www.themoviedb.org/settings/api).
3. Run:

   ```
   TMDB_KEY=your_key node fetch-posters.js path/to/diary.csv
   ```

   (Node 18+.) This downloads posters into `posters/` and rewrites `films.json`. Re-running only fetches films that are new.
4. Skim `needs_review.txt` for any films TMDB may have matched wrongly, fix them in `films.json`, commit, deploy.

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
