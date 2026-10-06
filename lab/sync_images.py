#!/usr/bin/env python3
"""Lab images: from the GPT Image 2 PNGs in lab/gallery, write the card thumbnail and the HD download.

images.json maps each published name (lab_p3, lab_m9…) to its current source PNG; edit it when a
character is regenerated. Outputs dashboard/img/<name>.jpg (720 px) and dashboard/img/hd/<name>.jpg (1080x1920).
"""
import json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "dashboard", "img")


def main():
    mapping = json.load(open(f"{HERE}/images.json"))
    os.makedirs(f"{OUT}/hd", exist_ok=True)
    for name, src in mapping.items():
        p = f"{HERE}/gallery/{src}"
        if not os.path.exists(p):
            print("missing", name, src)
            continue
        im = Image.open(p).convert("RGB")
        hd = im.copy()
        hd.thumbnail((1080, 1920))
        hd.save(f"{OUT}/hd/{name}.jpg", quality=90)
        th = im.copy()
        th.thumbnail((720, 1280))
        th.save(f"{OUT}/{name}.jpg", quality=84)
    print(f"{len(mapping)} images synced")


if __name__ == "__main__":
    main()
