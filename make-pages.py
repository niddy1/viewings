#!/usr/bin/env python3
"""Give every shelf its own address with its own link preview.

GitHub Pages serves the same index.html whatever comes after the "?", and link-preview bots
(iMessage, WhatsApp, Discord, Slack...) don't run JavaScript, so a link to ?shelf=1990s used to
preview as the 2026 ticket. This writes a copy of index.html into a folder per shelf
(2025/, 1990s/, all/, search/) with that shelf's title, description and preview picture,
and sets the newest year's preview on the root index.html. app.js reads the shelf from the folder.

Run from the repo root after changing index.html or adding a shelf:  python3 make-pages.py
(.github/workflows/pages.yml runs it on every push to main, so the copies never drift.)
Standard library only. Preview pictures are share/<shelf>.jpg (made with make-pages.py --cards,
which needs Pillow and Playwright); a year without one falls back to its watched-<year>.png ticket.
"""
import html
import json
import os
import re
import sys

SITE = 'https://ianandreu.com/viewings/'
ROOT = os.path.dirname(os.path.abspath(__file__))
START, END = '<!-- preview: make-pages.py writes this block -->', '<!-- /preview -->'


def read_json(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as f:
        return json.load(f)


def shelves():
    """(key, data file) in app.js's order: the Vault decades, then the years. Read from app.js itself."""
    src = open(os.path.join(ROOT, 'app.js'), encoding='utf-8').read()
    years = dict(re.findall(r"(\d{4}): '([^']+\.json)'", re.search(r'const SHELVES = \{([^}]*)\}', src).group(1)))
    vault = re.findall(r"'(\d{4}s)'", re.search(r'const VAULT = \[([^\]]*)\]', src).group(1))
    return [(d, f'vault-{d}.json') for d in vault] + [(y, years[y]) for y in sorted(years)]


def picture(key):
    for p in (f'share/{key}.jpg', f'watched-{key}.png'):
        if os.path.exists(os.path.join(ROOT, p)):
            return p
    return 'share/all.jpg'


def block(title, desc, pic, url):
    e = lambda s: html.escape(s, quote=True)
    return '\n'.join([
        START,
        f'  <title>{e(title)}</title>',
        f'  <meta name="description" content="{e(desc)}">',
        '  <meta property="og:site_name" content="Viewings">',
        '  <meta property="og:type" content="website">',
        f'  <meta property="og:title" content="{e(title)}">',
        f'  <meta property="og:description" content="{e(desc)}">',
        f'  <meta property="og:url" content="{e(SITE + url)}">',
        f'  <meta property="og:image" content="{e(SITE + pic)}">',
        '  <meta property="og:image:width" content="1200">',
        '  <meta property="og:image:height" content="630">',
        '  <meta name="twitter:card" content="summary_large_image">',
        f'  <link rel="canonical" href="{e(SITE + url)}">',
        '  ' + END,
    ])


def with_block(page, new):
    if START in page:
        return re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda m: new.strip(), page, flags=re.S)
    # first run: swap the plain <title> and description for the block
    page = re.sub(r'\s*<meta name="description"[^>]*>', '', page, count=1)
    return re.sub(r'<title>.*?</title>', lambda m: new.strip(), page, count=1, flags=re.S)


def write(path, text):
    full = os.path.join(ROOT, path)
    old = open(full, encoding='utf-8').read() if os.path.exists(full) else None
    if old != text:
        os.makedirs(os.path.dirname(full) or ROOT, exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(text)
        print('wrote', path)


def plural(n, word='film'):
    return f'{n:,} {word}' + ('' if n == 1 else 's')


def pages():
    keys = shelves()
    counts = {k: len(read_json(f)['films']) for k, f in keys}
    total = sum(counts.values())
    newest = keys[-1][0]
    pages = {}
    for k, _ in keys:
        if k.endswith('s'):
            pages[k] = (f'Viewings: the Vault, {k}',
                        f'The Vault, {k}: {plural(counts[k])} I watched before 2016, shelved as VHS tapes by decade of release.')
        else:
            pages[k] = (f'Viewings {k}', f'The {plural(counts[k])} I watched in {k}, shelved as VHS tapes.')
    pages['all'] = ('Viewings: the whole store', f'Every tape on every shelf: {plural(total)}, shelved as VHS tapes.')
    pages['search'] = ('Viewings: search the store', f'A shelf of search results from {plural(total)}, shelved as VHS tapes.')

    index = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    index = re.sub(r'\s*<base href="[^"]*">', '', index)  # the root page has none
    title, desc = pages[newest]
    write('index.html', with_block(index, block('Viewings', desc, picture(newest), '')))
    for k, (title, desc) in pages.items():
        page = with_block(index, block(title, desc, picture(k), f'{k}/'))
        # the copy sits one folder down: resolve every relative path from the root
        page = page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  <base href="../">', 1)
        page = page.replace('<!doctype html>', '<!doctype html>\n<!-- made by make-pages.py from index.html; edit index.html, not this -->', 1)
        write(f'{k}/index.html', page)


def cards():
    """share/<shelf>.jpg, 1200x630: the shelf's ticket or plate on the site's wall colour, as rendered by the site."""
    import subprocess, time, threading, http.server, functools
    from PIL import Image
    from playwright.sync_api import sync_playwright
    os.makedirs(os.path.join(ROOT, 'share'), exist_ok=True)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    W, H = 1200, 630
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome')
        pg = b.new_page(viewport={'width': 1400, 'height': 900}, device_scale_factor=2)
        for k, _ in shelves() + [('all', None), ('search', None)]:
            url = f'http://127.0.0.1:8765/{k}/' + ('?q=the%20store' if k == 'search' else '')
            pg.goto(url)
            pg.wait_for_selector('h1.ticket img, h1.ticket .vault-plate')
            pg.wait_for_function("!document.querySelector('h1.ticket img') || document.querySelector('h1.ticket img').complete")
            pg.evaluate('document.fonts.ready')
            pg.add_style_tag(content='.vault-star{display:none!important}h1.ticket *{transition:none!important}')
            time.sleep(.4)
            wall = pg.evaluate('getComputedStyle(document.body).backgroundColor')
            el = pg.query_selector('h1.ticket img, h1.ticket .vault-plate')
            tmp = os.path.join(ROOT, 'share', '_tmp.png')
            el.screenshot(path=tmp, omit_background=True)
            art = Image.open(tmp).convert('RGBA'); os.remove(tmp)
            rgb = tuple(int(x) for x in re.findall(r'\d+', wall)[:3])
            card = Image.new('RGBA', (W, H), rgb + (255,))
            s = min(W * .84 / art.width, H * .84 / art.height)
            art = art.resize((round(art.width * s), round(art.height * s)), Image.LANCZOS)
            card.alpha_composite(art, ((W - art.width) // 2, (H - art.height) // 2))
            card.convert('RGB').save(os.path.join(ROOT, 'share', f'{k}.jpg'), quality=88, optimize=True)
            print('card', k)
        b.close()
    srv.shutdown()


if __name__ == '__main__':
    if '--cards' in sys.argv:
        pages()  # the folders must exist to render them
        cards()
    pages()
