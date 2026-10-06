#!/usr/bin/env python3
"""Phase A: collect a wide pool of candidate AI-character accounts (TikTok + Instagram).

Every Apify call goes through guarded() which stops when the monthly usage gets near the limit.
Usage: APIFY_TOKEN=... python3 collect.py
Outputs: pool/tt_search.json, pool/ig_hashtags.json, pool/ig_profiles.json, pool/candidates.json
"""
import json, os, datetime as dt
from scrape import run_actor, _get, API, TOKEN, ROOT

OUT = f"{ROOT}/pool"
TT = "clockworks~tiktok-scraper"
TT_QUERIES = [
    "ai character dancing", "ai influencer dance", "ai grandpa dancing", "ai uncle dancing",
    "ai old man dancing wedding", "ai baby dancing", "ai cat dancing", "ai dog dancing", "ai granny dancing",
    "ai sheikh dancing", "ai habibi dance", "kling motion control dance", "higgsfield ai influencer",
    "ai character vlog", "ai mustache man", "ai funny character", "ai monk dancing", "ai baby podcast",
    "ai bigfoot vlog", "ai yeti vlog", "ai alien vlog", "ai grandma rapping", "ai character street interview",
    "ai cop dancing", "ai chef character", "ai fruit drama", "ai gorilla vlog", "ai teddy bear dancing",
    "ai character wedding", "motion control character swap"]
HASHTAGS = ["aicharacter", "aiinfluencer", "higgsfield", "higgsfieldai", "klingai", "motioncontrol",
            "aidance", "aidancing", "aibaby", "aianimals", "aivlog", "seedance", "aicomedy", "veo3"]
# origin of the wave + known copycats (from analysis/twitter_research.md and related profiles)
IG_SEEDS = ["jean_philanthrope", "don_nuger", "luca.digit", "edmond_lebon", "sebastianperfill",
            "benjamin_stachio", "big_boss_chico", "mr_twirlo"]
NOW = dt.datetime.now(dt.timezone.utc)


def guarded(actor, payload, margin=1.0):
    lim = _get(f"{API}/users/me/limits?token={TOKEN}")["data"]
    used, cap = lim["current"]["monthlyUsageUsd"], lim["limits"]["maxMonthlyUsageUsd"]
    print(f"  [apify ${used:.2f} / ${cap}]", flush=True)
    if used > cap - margin:
        raise SystemExit(f"Apify budget nearly exhausted (${used:.2f}/${cap}) — raise the limit and rerun")
    return run_actor(actor, payload)


def cached(name, fn):
    p = f"{OUT}/{name}"
    if os.path.exists(p):
        return json.load(open(p))
    d = fn()
    json.dump(d, open(p, "w"), ensure_ascii=False)
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    print("tiktok search…", flush=True)
    tt = cached("tt_search.json", lambda: guarded(TT, {
        "searchQueries": TT_QUERIES, "hashtags": HASHTAGS, "resultsPerPage": 40, "searchSection": "/video",
        "shouldDownloadVideos": False, "shouldDownloadCovers": False}))
    old = json.load(open(f"{ROOT}/tiktok/search.json")) if os.path.exists(f"{ROOT}/tiktok/search.json") else []
    print(f"  {len(tt)} + {len(old)} videos", flush=True)

    print("instagram hashtags…", flush=True)
    ig_posts = cached("ig_hashtags.json", lambda: guarded("apify~instagram-hashtag-scraper", {
        "hashtags": HASHTAGS, "resultsLimit": 50, "resultsType": "reels"}))
    known = json.load(open(f"{ROOT}/discovery/profiles.json"))
    owners = sorted(({p.get("ownerUsername") for p in ig_posts if p.get("ownerUsername")} | set(IG_SEEDS))
                    - (set(known) - set(IG_SEEDS)))
    print(f"  {len(ig_posts)} posts, {len(owners)} new owners", flush=True)
    ig_new = cached("ig_profiles.json", lambda: guarded("apify~instagram-profile-scraper", {"usernames": owners}))
    ig = {**known, **{p["username"]: p for p in ig_new if p.get("username")}}

    cands = {}
    for v in tt + old:
        a = v.get("authorMeta") or {}
        if not a.get("name") or (a.get("fans") or 0) < 50_000:
            continue
        c = cands.setdefault(f"tt:{a['name']}", {
            "platform": "tiktok", "handle": a["name"], "followers": a.get("fans"), "posts": a.get("video"),
            "bio": a.get("signature") or "", "url": f"https://www.tiktok.com/@{a['name']}", "samples": []})
        c["samples"].append({"views": v.get("playCount") or 0, "date": (v.get("createTimeISO") or "")[:10],
                             "text": (v.get("text") or "")[:100], "cover": (v.get("videoMeta") or {}).get("coverUrl"),
                             "url": v.get("webVideoUrl")})
    for p in ig.values():
        if p["username"] not in IG_SEEDS and ((p.get("followersCount") or 0) < 50_000
                                              or (p.get("postsCount") or 0) > 300):
            continue
        cands[f"ig:{p['username']}"] = {
            "platform": "instagram", "handle": p["username"], "followers": p["followersCount"],
            "posts": p.get("postsCount"), "new": p.get("joinedRecently"), "bio": p.get("biography") or "",
            "url": f"https://www.instagram.com/{p['username']}/",
            "samples": [{"views": x.get("videoViewCount") or 0, "date": (x.get("timestamp") or "")[:10],
                         "text": (x.get("caption") or "")[:100], "cover": x.get("displayUrl"), "url": x.get("url")}
                        for x in p.get("latestPosts") or []]}
    json.dump(cands, open(f"{OUT}/candidates.json", "w"), ensure_ascii=False, indent=1)
    print(f"done: {len(cands)} candidates "
          f"({sum(c['platform']=='tiktok' for c in cands.values())} TikTok, "
          f"{sum(c['platform']=='instagram' for c in cands.values())} Instagram)", flush=True)


if __name__ == "__main__":
    main()
