#!/usr/bin/env python3
"""Group reels that reuse the same source footage (same scene, character swapped).

Compares the 6-frame contact sheets with a 16x16 difference hash per frame; two reels match
when their best-aligned frames are close. Background dominates the frame, so a character swap
still matches. Output: analysis/sources.json (clusters with views per account).
"""
import glob, json, os, itertools
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
THRESH = 40  # hamming distance out of 256 bits


def hashes(sheet):
    im = Image.open(sheet).convert("L")
    w = im.width // 6
    out = []
    for i in range(6):
        f = im.crop((i * w, 0, (i + 1) * w, im.height)).resize((17, 16))
        a = np.asarray(f, dtype=np.int16)
        out.append((a[:, 1:] > a[:, :-1]).flatten())
    return out


def dist(h1, h2):
    # frames 1..4 (1s, 2s, 4s, 50%) are the most stable; take the best pair
    return min(int((a != b).sum()) for a in h1[1:5] for b in h2[1:5])


def main():
    reels = {}
    for u in sorted(os.listdir(f"{ROOT}/data")):
        for r in json.load(open(f"{ROOT}/data/{u}/reels.json")):
            s = f"{ROOT}/data/{u}/sheets/{r['shortCode']}.jpg"
            if r["ownerUsername"] == u and os.path.exists(s):
                reels[r["shortCode"]] = {"user": u, "views": r.get("videoPlayCount") or 0,
                                         "date": r["timestamp"][:16], "caption": (r.get("caption") or "")[:60],
                                         "h": hashes(s)}
    codes = list(reels)
    parent = {c: c for c in codes}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for a, b in itertools.combinations(codes, 2):
        if dist(reels[a]["h"], reels[b]["h"]) <= THRESH:
            parent[find(a)] = find(b)
    groups = {}
    for c in codes:
        groups.setdefault(find(c), []).append(c)
    clusters = []
    for g in groups.values():
        if len(g) < 2:
            continue
        items = sorted(({"code": c, **{k: v for k, v in reels[c].items() if k != "h"}} for c in g),
                       key=lambda x: x["date"])
        clusters.append({"size": len(g), "accounts": sorted({i["user"] for i in items}),
                         "total_views": sum(i["views"] for i in items), "items": items})
    clusters.sort(key=lambda c: -c["total_views"])
    os.makedirs(f"{ROOT}/analysis", exist_ok=True)
    json.dump(clusters, open(f"{ROOT}/analysis/sources.json", "w"), indent=1, ensure_ascii=False)
    n_in = sum(c["size"] for c in clusters)
    v_in = sum(c["total_views"] for c in clusters)
    v_all = sum(r["views"] for r in reels.values())
    print(f"{len(reels)} reels, {len(clusters)} shared-source clusters covering {n_in} reels "
          f"= {v_in/v_all:.0%} of all views")
    for c in clusters:
        print(f"\n[{c['size']} reels, {c['total_views']/1e6:.1f}M] {', '.join(c['accounts'])}")
        for i in c["items"]:
            print(f"   {i['date']} {i['user']:17} {i['code']} {i['views']/1e6:6.2f}M | {i['caption']}")


if __name__ == "__main__":
    main()
