#!/usr/bin/env python3
"""Phase B: visual triage sheets of candidate accounts (one row per account, top 4 covers).

Usage: python3 triage.py
Outputs: pool/covers/<key>_<i>.jpg, pool/triage_<n>.jpg (24 accounts per sheet), pool/triage_index.json
"""
import json, os, urllib.request, concurrent.futures as cf
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
POOL = f"{ROOT}/pool"
PER_SHEET, THUMBS, W, H = 24, 4, 120, 213


def fetch(url, path):
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
            f.write(r.read())
        return path
    except Exception:
        return None


def main():
    cands = json.load(open(f"{POOL}/candidates.json"))
    os.makedirs(f"{POOL}/covers", exist_ok=True)
    keys = sorted(cands, key=lambda k: -(cands[k]["followers"] or 0))
    jobs = []
    for k in keys:
        top = sorted((s for s in cands[k]["samples"] if s.get("cover")), key=lambda s: -s["views"])[:THUMBS]
        cands[k]["thumbs"] = []
        for i, s in enumerate(top):
            p = f"{POOL}/covers/{k.replace(':', '_')}_{i}.jpg"
            cands[k]["thumbs"].append(p)
            jobs.append((s["cover"], p))
    with cf.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))

    index = {}
    for n in range(0, len(keys), PER_SHEET):
        chunk = keys[n:n + PER_SHEET]
        cols = 2  # two accounts side by side
        rows = (len(chunk) + cols - 1) // cols
        cw = THUMBS * W + 10
        sheet = Image.new("RGB", (cols * cw, rows * (H + 30)), "white")
        d = ImageDraw.Draw(sheet)
        for i, k in enumerate(chunk):
            c = cands[k]
            x0, y0 = (i % cols) * cw, (i // cols) * (H + 30)
            num = n + i + 1
            index[num] = k
            d.text((x0 + 2, y0 + 2), f"#{num} {c['platform'][:2]} @{c['handle'][:24]}  {c['followers']/1e3:.0f}k  "
                                     f"{c.get('posts')}p{' NEW' if c.get('new') else ''}", fill="black")
            for j, p in enumerate(c["thumbs"]):
                try:
                    im = Image.open(p).convert("RGB")
                    im.thumbnail((W, H))
                    sheet.paste(im, (x0 + j * W, y0 + 16))
                except Exception:
                    pass
        out = f"{POOL}/triage_{n // PER_SHEET + 1}.jpg"
        sheet.save(out, quality=80)
        print(out, len(chunk))
    json.dump(index, open(f"{POOL}/triage_index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
