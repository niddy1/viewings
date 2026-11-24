"""Write posters/spines.json: the pixel size of every designed spine picture, keyed by its path.
The shelf reads it to size and place tapes before any picture has downloaded, then loads the
pictures as they scroll into view.  Run after rendering spines: python3 spinegen/manifest.py"""
import glob, json, os
from PIL import Image

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
out = {}
for p in sorted(glob.glob('posters/*-spine-b.jpg')):
    with Image.open(p) as im:
        out[p[len('posters/'):-len('-spine-b.jpg')]] = list(im.size)
with open('posters/spines.json', 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print(len(out), 'spines,', os.path.getsize('posters/spines.json'), 'bytes')
