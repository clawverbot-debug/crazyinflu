#!/usr/bin/env python3
"""Find reels that reuse the same source footage, across all accounts, with CLIP embeddings.

The character changes between copies but the set does not, so each frame is embedded twice:
whole frame and its background border (top band + side bands, character masked out).
Two reels match when their best frame pair is above THRESH on the border embedding.
Usage: /usr/bin/python3 scenes.py [calibrate]
Outputs: analysis/scene_emb.npz, analysis/scene_clusters.json
"""
import glob, json, os, sys, itertools
import numpy as np, torch, open_clip
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
KNOWN = [("abu.shalab/Dd4WBQrt48X", "dahab.daddy/Dd_qcXdgsdb"), ("abu.yalla/Dd62X7dJbCD", "dahab.daddy/Dd_qcXdgsdb"),
         ("abu.shalab/DdxCLS5NMRz", "dahab.daddy/DdzgbbAR4VM"), ("abu.shalab/DeCCJ4fNAvB", "dahab.daddy/Dd8iR7XAS9H")]


def frames(sheet):
    im = Image.open(sheet).convert("RGB")
    w = im.width // 6
    return [im.crop((i * w, 0, (i + 1) * w, im.height)) for i in (1, 2, 3, 4)]  # 1s, 2s, 4s, 50%


def border(f):
    """Keep the background: top 28% band + left/right 22% bands, centre (character) blanked."""
    a = np.asarray(f).copy()
    h, w = a.shape[:2]
    a[int(h * .28):, int(w * .22):int(w * .78)] = 127
    return Image.fromarray(a)


def embed():
    out = f"{ROOT}/analysis/scene_emb.npz"
    sheets = sorted(glob.glob(f"{ROOT}/data/*/sheets/*.jpg"))
    keys = [f"{s.split('/')[-3]}/{os.path.basename(s)[:-4]}" for s in sheets]
    if os.path.exists(out):
        z = np.load(out, allow_pickle=True)
        if list(z["keys"]) == keys:
            return keys, z["full"], z["bord"]
    model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    model.eval()
    full, bord = [], []
    with torch.no_grad():
        for i, s in enumerate(sheets):
            fr = frames(s)
            x = torch.stack([pre(f) for f in fr] + [pre(border(f)) for f in fr])
            e = model.encode_image(x)
            e = e / e.norm(dim=-1, keepdim=True)
            full.append(e[:4].numpy())
            bord.append(e[4:].numpy())
            if i % 50 == 0:
                print(f"  embedded {i}/{len(sheets)}", flush=True)
    full, bord = np.stack(full), np.stack(bord)
    np.savez(out, keys=np.array(keys), full=full, bord=bord)
    return keys, full, bord


def sim(E, i, j):
    return float((E[i] @ E[j].T).max())


def main():
    keys, full, bord = embed()
    k2i = {k: i for i, k in enumerate(keys)}
    known = [(k2i[a], k2i[b]) for a, b in KNOWN if a in k2i and b in k2i]
    rng = np.random.default_rng(0)
    rand = [tuple(rng.choice(len(keys), 2, replace=False)) for _ in range(3000)]
    for name, E in (("full", full), ("border", bord)):
        ks = [sim(E, i, j) for i, j in known]
        rs = sorted(sim(E, i, j) for i, j in rand if keys[i].split("/")[0] != keys[j].split("/")[0])
        print(f"{name}: known pairs {np.round(ks, 3)} | random cross-account p50 {rs[len(rs)//2]:.3f} "
              f"p99 {rs[int(len(rs)*.99)]:.3f} p99.9 {rs[int(len(rs)*.999)]:.3f}")
    if len(sys.argv) > 1:
        return
    thresh = float(os.environ.get("THRESH", 0.93))
    n = len(keys)
    S = np.zeros((n, n))
    for i in range(n):
        S[i] = (bord[i].reshape(-1, bord.shape[-1]) @ bord.reshape(-1, bord.shape[-1]).T).reshape(4, n, 4).max(axis=(0, 2))
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i, j in zip(*np.where(np.triu(S, 1) >= thresh)):
        parent[find(i)] = find(j)
    views = {}
    for u in {k.split("/")[0] for k in keys}:
        p = f"{ROOT}/data/{u}/reels.json"
        if os.path.exists(p):
            for r in json.load(open(p)):
                views[f"{u}/{r.get('shortCode')}"] = (r.get("videoPlayCount") or 0, r.get("timestamp", "")[:16])
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(keys[i])
    clusters = []
    for g in groups.values():
        if len(g) < 2:
            continue
        items = sorted(({"key": k, "account": k.split("/")[0], "views": views.get(k, (0, ""))[0],
                         "date": views.get(k, (0, ""))[1]} for k in g), key=lambda x: x["date"])
        clusters.append({"size": len(g), "accounts": sorted({x["account"] for x in items}),
                         "total_views": sum(x["views"] for x in items), "items": items})
    clusters.sort(key=lambda c: (-len(c["accounts"]), -c["total_views"]))
    json.dump(clusters, open(f"{ROOT}/analysis/scene_clusters.json", "w"), indent=1)
    cross = [c for c in clusters if len(c["accounts"]) > 1]
    print(f"\nthreshold {thresh}: {len(clusters)} clusters, {len(cross)} shared across accounts")
    for c in cross[:25]:
        print(f"[{c['size']} reels / {len(c['accounts'])} comptes / {c['total_views']/1e6:.1f}M]")
        for x in c["items"]:
            print(f"    {x['date']} {x['key']:38} {x['views']/1e6:6.2f}M")


if __name__ == "__main__":
    main()
