#!/usr/bin/env python3
"""Phase C: last ~25 videos of every account kept at triage (A/B/C) → per-account metrics.

Usage: APIFY_TOKEN=... python3 deep.py
Inputs: pool/candidates.json, pool/triage_index.json, pool/triage_labels_*.json
Outputs: pool/deep_tt.json, pool/deep_ig.json, analysis/accounts.csv, analysis/accounts.json,
         pool/best_worst/<handle>.jpg (top 3 + bottom 2 covers)
"""
import csv, glob, json, os, statistics as st, datetime as dt
from PIL import Image, ImageDraw
from collect import guarded, cached, TT, OUT as POOL
from triage import fetch
from scrape import ROOT

N = 20
NOW = dt.datetime.now(dt.timezone.utc)


def labels():
    idx = json.load(open(f"{POOL}/triage_index.json"))
    cands = json.load(open(f"{POOL}/candidates.json"))
    keep = {}
    for f in glob.glob(f"{POOL}/triage_labels_*.json"):
        lab = json.load(open(f))
        for cat in "ABC":
            for n in lab.get(cat, []):
                k = idx.get(str(n))
                if k:
                    keep[k] = {**cands[k], "category": cat, "note": (lab.get("notes") or {}).get(str(n), "")}
    # the benchmark accounts and the origin of the wave are always in
    from collect import IG_SEEDS
    for u in IG_SEEDS + os.listdir(f"{ROOT}/data"):
        k = f"ig:{u}"
        if k in cands and k not in keep:
            keep[k] = {**cands[k], "category": "A", "note": "seed"}
    return keep


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def norm_tt(v):
    m = v.get("musicMeta") or {}
    return {"views": v.get("playCount") or 0, "likes": v.get("diggCount") or 0, "comments": v.get("commentCount") or 0,
            "shares": v.get("shareCount") or 0, "date": v.get("createTimeISO"), "duration": (v.get("videoMeta") or {}).get("duration"),
            "caption": v.get("text") or "", "original_sound": bool(m.get("musicOriginal")),
            "sound": f"{m.get('musicAuthor','')} - {m.get('musicName','')}", "cover": (v.get("videoMeta") or {}).get("coverUrl"),
            "url": v.get("webVideoUrl")}


def norm_ig(r):
    m = r.get("musicInfo") or {}
    return {"views": r.get("videoPlayCount") or r.get("videoViewCount") or 0, "likes": r.get("likesCount") or 0,
            "comments": r.get("commentsCount") or 0, "shares": None, "date": r.get("timestamp"),
            "duration": r.get("videoDuration"), "caption": r.get("caption") or "",
            "original_sound": bool(m.get("uses_original_audio")),
            "sound": f"{m.get('artist_name','')} - {m.get('song_name','')}", "cover": r.get("displayUrl"), "url": r.get("url")}


def metrics(acc, vids):
    vids = [v for v in vids if v["date"]]
    if not vids:
        return None
    dates = sorted(ts(v["date"]) for v in vids)
    span = max((dates[-1] - dates[0]).total_seconds() / 86400, 1)
    views = [v["views"] for v in vids]
    durs = [float(v["duration"]) for v in vids if v["duration"]]
    words = [len(v["caption"].split()) for v in vids]
    tags = [v["caption"].count("#") for v in vids]
    fol = acc["followers"] or 1
    return {"platform": acc["platform"], "handle": acc["handle"], "category": acc["category"], "note": acc["note"],
            "followers": acc["followers"], "posts_total": acc.get("posts"), "new_badge": acc.get("new"),
            "followers_per_post": round(fol / max(acc.get("posts") or 1, 1)),
            "videos_analyzed": len(vids), "window_days": round(span, 1), "posts_per_day": round(len(vids) / span, 2),
            "oldest_in_window": dates[0].date().isoformat(), "latest": dates[-1].date().isoformat(),
            "median_views": int(st.median(views)), "max_views": max(views), "min_views": min(views),
            "median_views_per_follower": round(st.median(views) / fol, 2),
            "hit_rate_1M": round(sum(x >= 1_000_000 for x in views) / len(views), 2),
            "median_duration_s": round(st.median(durs), 1) if durs else None,
            "pct_original_sound": round(sum(v["original_sound"] for v in vids) / len(vids), 2),
            "median_caption_words": st.median(words), "median_hashtags": st.median(tags),
            "bio": acc["bio"].replace("\n", " | "), "url": acc["url"]}


def best_worst(handle, vids):
    vids = sorted((v for v in vids if v.get("cover")), key=lambda v: -v["views"])
    pick = vids[:3] + vids[-2:] if len(vids) > 5 else vids
    os.makedirs(f"{POOL}/best_worst/covers", exist_ok=True)
    W, H = 160, 284
    im = Image.new("RGB", (W * len(pick), H + 18), "white")
    d = ImageDraw.Draw(im)
    for i, v in enumerate(pick):
        p = fetch(v["cover"], f"{POOL}/best_worst/covers/{handle}_{i}.jpg")
        try:
            t = Image.open(p).convert("RGB")
            t.thumbnail((W, H))
            im.paste(t, (i * W, 18))
        except Exception:
            pass
        d.text((i * W + 3, 3), f"{'TOP' if i < 3 else 'LOW'} {v['views']/1e6:.2f}M", fill="black")
    im.save(f"{POOL}/best_worst/{handle}.jpg", quality=80)


def main():
    keep = labels()
    # motion-source libraries (C) are only listed, not deep-scraped (budget)
    src = sorted((a for a in keep.values() if a["category"] == "C"), key=lambda a: -a["followers"])
    os.makedirs(f"{ROOT}/analysis", exist_ok=True)
    with open(f"{ROOT}/analysis/motion_sources.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["platform", "handle", "followers", "note", "bio", "url"])
        for a in src:
            w.writerow([a["platform"], a["handle"], a["followers"], a["note"], a["bio"].replace("\n", " | "), a["url"]])
    keep = {k: a for k, a in keep.items() if a["category"] != "C"}
    tt =[a["handle"] for a in keep.values() if a["platform"] == "tiktok"]
    ig = [a["handle"] for a in keep.values() if a["platform"] == "instagram"]
    print(f"kept {len(keep)} accounts: {len(tt)} TikTok, {len(ig)} Instagram", flush=True)
    tt_raw = cached("deep_tt.json", lambda: guarded(TT, {
        "profiles": tt, "resultsPerPage": N, "profileScrapeSections": ["videos"], "profileSorting": "latest",
        "shouldDownloadVideos": False, "shouldDownloadCovers": False}))
    ig_raw = cached("deep_ig.json", lambda: guarded("apify~instagram-reel-scraper",
                                                     {"username": ig, "resultsLimit": N}) if ig else [])
    by = {}
    for v in tt_raw:
        by.setdefault(("tiktok", (v.get("authorMeta") or {}).get("name")), []).append(norm_tt(v))
    for r in ig_raw:
        by.setdefault(("instagram", r.get("ownerUsername")), []).append(norm_ig(r))
    # the 4 seed accounts are fully scraped already
    for u in os.listdir(f"{ROOT}/data"):
        by[("instagram", u)] = [norm_ig(r) for r in json.load(open(f"{ROOT}/data/{u}/reels.json"))
                                if r["ownerUsername"] == u]

    rows = []
    for a in keep.values():
        vids = by.get((a["platform"], a["handle"]), [])
        m = metrics(a, vids)
        if m:
            rows.append(m)
            best_worst(a["handle"], vids)
    rows.sort(key=lambda r: (r["category"], -r["followers"]))
    os.makedirs(f"{ROOT}/analysis", exist_ok=True)
    json.dump({"accounts": rows, "videos": {f"{p}:{h}": v for (p, h), v in by.items()}},
              open(f"{ROOT}/analysis/accounts.json", "w"), ensure_ascii=False)
    with open(f"{ROOT}/analysis/accounts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"done: {len(rows)} accounts with metrics → analysis/accounts.csv", flush=True)


if __name__ == "__main__":
    main()
