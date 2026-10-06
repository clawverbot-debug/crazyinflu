#!/usr/bin/env python3
"""Copy profile pictures gallery/pfp_<id>.png -> dashboard/img/pfp/<id>.jpg (320 px) and img/pfp/hd/<id>.jpg (1080 px)."""
import glob, os
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
D = f"{HERE}/../dashboard/img/pfp"
os.makedirs(f"{D}/hd", exist_ok=True)
n = 0
for p in sorted(glob.glob(f"{HERE}/gallery/pfp_*.png")):
    cid = os.path.basename(p)[4:-4]
    im = Image.open(p).convert("RGB")
    im.resize((1080, 1080), Image.LANCZOS).save(f"{D}/hd/{cid}.jpg", quality=92)
    im.resize((320, 320), Image.LANCZOS).save(f"{D}/{cid}.jpg", quality=85)
    n += 1
print(n, "profile pictures synced")
