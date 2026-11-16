"""Draw title boxes (magenta) and photo crops (cyan) over posters, tiled, to check them before rendering.
Run from anywhere:

    python3 spinegen/check_boxes.py boxes.json out.png

boxes.json: {"<poster name>": {"t": [[x0,y0,x1,y1], ...], "p": [cx, cy, w, ar]}, ...}
(the same numbers a tapes.py spec passes to L(...) and ph(...)).  Guessing from a gridded poster is
usually off by a few percent; this shows the real fit at a glance.
"""
import os
import sys, json
from PIL import Image, ImageDraw
P=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posters') + '/'
B=json.loads(open(sys.argv[1]).read()); out=sys.argv[2]
W,H=300,450; cols=6
items=list(B.items()); rows=(len(items)+cols-1)//cols
sh=Image.new('RGB',(W*cols,(H+16)*rows),'#222'); d0=ImageDraw.Draw(sh)
for i,(pid,v) in enumerate(items):
    im=Image.open(P+pid+'.jpg').convert('RGB').resize((W,H)); d=ImageDraw.Draw(im)
    for b in v.get('t',[]): d.rectangle([b[0]*W,b[1]*H,b[2]*W,b[3]*H],outline=(255,0,255),width=2)
    if 'p' in v:
        cx,cy,w,ar=v['p']; h=w*ar*780/1170; x0=min(max(0,cx-w/2),1-w); y0=min(max(0,cy-h/2),1-h)
        d.rectangle([x0*W,y0*H,(x0+w)*W,(y0+h)*H],outline=(0,255,255),width=2)
    sh.paste(im,((i%cols)*W,(i//cols)*(H+16))); d0.text(((i%cols)*W+3,(i//cols)*(H+16)+H+2),pid[:45],fill='white')
sh.save(out)
