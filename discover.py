#!/usr/bin/env python3
"""Find NEW Instagram accounts (badge "Nouveau" = joinedRecently) with 100k+ followers.

Snowball: seeds' related profiles + owners of posts on AI hashtags → profile scrape →
keep joinedRecently & followers >= MIN → their related profiles feed the next round.

Usage: APIFY_TOKEN=... python3 discover.py
Outputs: discovery/profiles.json (every profile scraped), discovery/hits.csv
"""
import csv, json, os, glob
from scrape import run_actor, ROOT

MIN_FOLLOWERS = 100_000
ROUNDS = 3
MAX_PER_ROUND = 250
HASHTAGS = ["higgsfieldcreator", "higgsfield", "higgsfieldai", "aicharacter", "aiinfluencer",
            "aicomedy", "aidance", "aiactor", "aivideo", "dancingdad"]
OUT = f"{ROOT}/discovery"


def related(p):
    return [r["username"] for r in p.get("relatedProfiles") or []]


def is_hit(p):
    return p.get("joinedRecently") and (p.get("followersCount") or 0) >= MIN_FOLLOWERS


def main():
    os.makedirs(OUT, exist_ok=True)
    db_path = f"{OUT}/profiles.json"
    db = json.load(open(db_path)) if os.path.exists(db_path) else {}
    for f in glob.glob(f"{ROOT}/data/*/profile.json"):
        p = json.load(open(f))
        db[p["username"]] = p

    frontier = {u for p in db.values() for u in related(p)}
    tag_path = f"{OUT}/hashtag_posts.json"
    if not os.path.exists(tag_path):
        print("hashtags…", flush=True)
        posts = run_actor("apify~instagram-hashtag-scraper", {"hashtags": HASHTAGS, "resultsLimit": 60})
        json.dump(posts, open(tag_path, "w"), ensure_ascii=False)
    posts = json.load(open(tag_path))
    frontier |= {x["ownerUsername"] for x in posts if x.get("ownerUsername")}
    print(f"hashtag owners: {len({x.get('ownerUsername') for x in posts})}", flush=True)

    for rnd in range(ROUNDS):
        todo = sorted(u for u in frontier if u not in db)[:MAX_PER_ROUND]
        if not todo:
            break
        print(f"round {rnd+1}: scraping {len(todo)} profiles…", flush=True)
        for p in run_actor("apify~instagram-profile-scraper", {"usernames": todo}):
            if p.get("username"):
                db[p["username"]] = p
        json.dump(db, open(db_path, "w"), ensure_ascii=False)
        hits = [p for p in db.values() if is_hit(p)]
        print(f"  hits so far: {len(hits)}", flush=True)
        # next round: related of hits first (same niche), then related of any new account
        frontier = {u for p in hits for u in related(p)}
        frontier |= {u for p in db.values() if p.get("joinedRecently") for u in related(p)}

    hits = sorted((p for p in db.values() if is_hit(p)), key=lambda p: -p["followersCount"])
    with open(f"{OUT}/hits.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["username", "followers", "posts", "following", "category", "bio", "link", "url"])
        for p in hits:
            w.writerow([p["username"], p["followersCount"], p.get("postsCount"), p.get("followsCount"),
                        p.get("businessCategoryName"), (p.get("biography") or "").replace("\n", " | "),
                        p.get("externalUrl"), f"https://www.instagram.com/{p['username']}/"])
    print(f"done: {len(hits)} new accounts with {MIN_FOLLOWERS}+ followers", flush=True)
    for p in hits:
        print(f"  {p['username']:28} {p['followersCount']:>9}  {p.get('postsCount')} posts | {(p.get('biography') or '')[:70]!r}")


if __name__ == "__main__":
    main()
