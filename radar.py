#!/usr/bin/env python3
"""Radar: find every NEW account that is blowing up right now (Instagram + TikTok).

Instagram: snowball on relatedProfiles from all known character / motion-source accounts (depth 2)
           + owners of recent reels on broad content hashtags → keep joinedRecently & >= IG_MIN.
TikTok:    broad keyword search → authors >= TT_MIN fans → their latest videos → keep accounts
           whose oldest video is < NEW_DAYS old (TikTok has no "new" badge).
Usage: APIFY_TOKEN=... python3 radar.py
Outputs: radar/ig_profiles.json, radar/tt_search.json, radar/tt_authors.json, radar/new_accounts.json
"""
import json, os, glob, datetime as dt
from collect import guarded, TT
from scrape import ROOT

OUT = f"{ROOT}/radar"
IG_MIN, TT_MIN, NEW_DAYS = 20_000, 50_000, 30
IG_TAGS = ["dance", "dancing", "funnyvideos", "comedy", "weddingdance", "wedding", "uncle", "habibi", "dubai",
           "memes", "viralreels", "party", "oldmandancing", "grandpa", "mustache", "funnydance", "dancechallenge",
           "aicharacter", "aiinfluencer", "higgsfield", "aivideo", "aibaby", "aianimals", "fruitdrama", "aicomedy",
           "monkey", "chihuahua", "dogsofinstagram", "catsofinstagram", "brainrot", "italianbrainrot", "yeti",
           "bigfoot", "aiart", "vlog", "streetdance", "disco", "70s", "gentleman", "moustache"]
TT_QUERIES = [
    "ai dance", "ai character", "ai influencer", "ai baby", "ai animal", "ai monkey", "ai dog", "ai cat",
    "ai grandpa", "ai grandma", "ai uncle dance", "funny uncle dancing", "uncle dance wedding", "old man dancing",
    "mustache man dancing", "habibi dance", "dubai dance funny", "wedding dance funny", "party dance funny",
    "fruit drama", "fruit love story", "ai fruit", "ai food character", "ai yeti", "ai bigfoot vlog", "ai alien",
    "ai gorilla", "ai chimp vlog", "ai pug", "ai chihuahua", "ai capybara", "ai sloth", "ai panda dance",
    "ai baby dance", "ai baby podcast", "ai baby police", "ai toddler", "ai doll dance", "ai barbie",
    "italian brainrot", "brainrot character", "ai cartoon dance", "ai pixar", "ai 3d character",
    "higgsfield", "kling motion control", "motion control dance", "character swap dance", "ai swap dance",
    "funny dance trend", "dance trend october", "viral dance man", "sexy dance man funny", "disco dance man",
    "70s dance", "gentleman dance", "bowl cut dance", "wig dance funny", "thobe dance", "sheikh dance"]
NOW = dt.datetime.now(dt.timezone.utc)


def cached(name, fn):
    p = f"{OUT}/{name}"
    if os.path.exists(p):
        return json.load(open(p))
    d = fn()
    json.dump(d, open(p, "w"), ensure_ascii=False)
    return d


def known_ig():
    """Every Instagram profile already scraped, by username."""
    db = {}
    for f in [f"{ROOT}/discovery/profiles.json"]:
        if os.path.exists(f):
            db.update(json.load(open(f)))
    for f in [f"{ROOT}/pool/ig_profiles.json", f"{OUT}/ig_profiles.json"]:
        if os.path.exists(f):
            db.update({p["username"]: p for p in json.load(open(f)) if p.get("username")})
    return db


def instagram():
    db = known_ig()
    seeds = set()
    for f in glob.glob(f"{ROOT}/pool/triage_labels_*.json"):
        lab = json.load(open(f))
        idx = json.load(open(f"{ROOT}/pool/triage_index.json"))
        for c in "ABC":
            seeds |= {idx[str(n)].split(":", 1)[1] for n in lab.get(c, []) if idx[str(n)].startswith("ig:")}
    seeds |= {u for u, p in db.items() if p.get("joinedRecently") and (p.get("followersCount") or 0) >= 5000}
    print(f"IG seeds: {len(seeds)}", flush=True)
    posts = cached("ig_tag_posts.json", lambda: guarded("apify~instagram-hashtag-scraper",
                                                         {"hashtags": IG_TAGS, "resultsLimit": 80,
                                                          "resultsType": "reels"}))
    frontier = {p.get("ownerUsername") for p in posts if p.get("ownerUsername")}
    for u in seeds:
        frontier |= {r["username"] for r in (db.get(u) or {}).get("relatedProfiles") or []}
    new_prof = json.load(open(f"{OUT}/ig_profiles.json")) if os.path.exists(f"{OUT}/ig_profiles.json") else []
    for depth in range(2):
        todo = sorted(u for u in frontier if u and u not in db)[:2000]
        print(f"IG depth {depth}: {len(todo)} profiles to scrape", flush=True)
        if not todo:
            break
        got = guarded("apify~instagram-profile-scraper", {"usernames": todo})
        new_prof += got
        json.dump(new_prof, open(f"{OUT}/ig_profiles.json", "w"), ensure_ascii=False)
        db.update({p["username"]: p for p in got if p.get("username")})
        hot = [p for p in got if p.get("joinedRecently") and (p.get("followersCount") or 0) >= 5000]
        frontier = {r["username"] for p in hot for r in p.get("relatedProfiles") or []}
        print(f"  new accounts >= 5k in this layer: {len(hot)}", flush=True)
    return [p for p in db.values() if p.get("joinedRecently") and (p.get("followersCount") or 0) >= IG_MIN]


def tiktok():
    vids = cached("tt_search.json", lambda: guarded(TT, {
        "searchQueries": TT_QUERIES, "resultsPerPage": 50, "searchSection": "/video",
        "shouldDownloadVideos": False, "shouldDownloadCovers": False}))
    authors = {}
    for v in vids:
        a = v.get("authorMeta") or {}
        if a.get("name") and (a.get("fans") or 0) >= TT_MIN and (a.get("video") or 999) <= 60:
            authors[a["name"]] = a
    print(f"TikTok: {len(vids)} videos, {len(authors)} candidate authors (<=60 videos)", flush=True)
    done = json.load(open(f"{OUT}/tt_authors.json")) if os.path.exists(f"{OUT}/tt_authors.json") else {}
    todo = [n for n in authors if n not in done]
    if todo:
        got = guarded(TT, {"profiles": todo, "resultsPerPage": 60, "profileScrapeSections": ["videos"],
                           "profileSorting": "latest", "shouldDownloadVideos": False, "shouldDownloadCovers": False})
        for v in got:
            done.setdefault((v.get("authorMeta") or {}).get("name"), []).append(v)
        json.dump(done, open(f"{OUT}/tt_authors.json", "w"), ensure_ascii=False)
    out = []
    for n, vs in done.items():
        ts = sorted(v["createTimeISO"] for v in vs if v.get("createTimeISO"))
        if not ts:
            continue
        a = vs[0].get("authorMeta") or {}
        age = (NOW - dt.datetime.fromisoformat(ts[0].replace("Z", "+00:00"))).days
        complete = len(vs) >= (a.get("video") or 0) * 0.9
        if age <= NEW_DAYS and complete:
            out.append({"platform": "tiktok", "handle": n, "followers": a.get("fans"), "videos": a.get("video"),
                        "first_post": ts[0][:10], "age_days": age, "bio": a.get("signature") or "",
                        "max_views": max(v.get("playCount") or 0 for v in vs),
                        "url": f"https://www.tiktok.com/@{n}"})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    ig = instagram()
    tt = tiktok()
    res = [{"platform": "instagram", "handle": p["username"], "followers": p["followersCount"],
            "posts": p.get("postsCount"), "bio": p.get("biography") or "", "url": f"https://www.instagram.com/{p['username']}/"}
           for p in ig] + tt
    res.sort(key=lambda r: -(r["followers"] or 0))
    json.dump(res, open(f"{OUT}/new_accounts.json", "w"), ensure_ascii=False, indent=1)
    print(f"done: {len(ig)} new IG accounts >= {IG_MIN}, {len(tt)} new TikTok accounts >= {TT_MIN}", flush=True)
    for r in res:
        print(f"  {r['platform'][:2]} {r['handle']:28} {r['followers']:>9} | {r['bio'].replace(chr(10), ' ')[:70]}")


if __name__ == "__main__":
    main()
