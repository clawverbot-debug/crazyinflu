"""Square Prime Ads logos with the slogan, from Thibault's exact PNG (~/Downloads/ELIOMAT/logoprime2.png): crops + placement only,
the logo itself is never redrawn. Slogan in Inter SemiBold, navy of the 'rime' letters. Outputs logo/*.png (1080x1080)."""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
SRC = Image.open("/Users/thibault/Downloads/ELIOMAT/logoprime2.png").convert("RGB")
a = np.asarray(SRC).astype(int); BG = tuple(int(x) for x in np.median(a[:40, :40].reshape(-1, 3), 0))
NAVY = (20, 27, 43); BLUE = (43, 116, 240)
def inter(size, wght=600):
    f = ImageFont.truetype("fonts/Inter.ttf", size); f.set_variation_by_axes([min(32, max(14, size)), wght]); return f
def bbox_nonbg(img, thr=18):
    x = np.asarray(img).astype(int); m = np.abs(x - np.array(BG)).sum(2) > thr
    ys, xs = np.where(m); return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
W = 1080
# split tile / wordmark at the gap between them (column with no ink between x=560 and 660 of the original)
x = np.abs(a - np.array(BG)).sum(2) > 18; cols = x[:, 560:700].sum(0); gap = 560 + int(np.argmin(cols))
tile = SRC.crop((0, 0, gap, SRC.height)); tile = tile.crop(bbox_nonbg(tile, 10))
word = SRC.crop((gap, 0, SRC.width, SRC.height)); word = word.crop(bbox_nonbg(word))
full = SRC.crop(bbox_nonbg(SRC, 10))
def slogan(d, y, size):
    f = inter(size, 650); t = "Built to stay live"; tw = d.textlength(t, font=f)
    d.text(((W - tw) / 2, y), t, font=f, fill=NAVY)
# 1. stacked, circle-safe (profile pictures)
im = Image.new("RGB", (W, W), BG); d = ImageDraw.Draw(im)
t = tile.resize((300, int(tile.height * 300 / tile.width)), Image.LANCZOS)
w2 = word.resize((640, int(word.height * 640 / word.width)), Image.LANCZOS)
total = t.height + 34 + w2.height + 40 + 58; y = (W - total) // 2
im.paste(t, ((W - t.width) // 2, y)); y += t.height + 34
im.paste(w2, ((W - w2.width) // 2, y)); y += w2.height + 40
slogan(d, y, 52); im.save("logo/primeads_square_stacked.png")
# 2. horizontal logo + slogan (posts, pages)
im = Image.new("RGB", (W, W), BG); d = ImageDraw.Draw(im)
f2 = full.resize((920, int(full.height * 920 / full.width)), Image.LANCZOS)
y = (W - (f2.height + 56 + 62)) // 2
im.paste(f2, ((W - f2.width) // 2, y)); slogan(d, y + f2.height + 56, 60); im.save("logo/primeads_square_horizontal.png")
print("bg", BG, "gap", gap, "tile", tile.size, "word", word.size)
