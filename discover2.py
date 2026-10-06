#!/usr/bin/env python3
"""Deeper hunt for NEW (joinedRecently) character accounts that blow up fast.

Expansion rule: any account that is new, has <= MAX_POSTS posts and >= EXPAND_MIN followers
is "in the niche" → its related profiles get scraped next round. Also seeds the frontier with
Instagram user search on bio keywords. Reuses discovery/profiles.json from discover.py.

Usage: APIFY_TOKEN=... python3 discover2.py
Outputs: discovery/niche.csv (new + fast-growing, sorted by followers/post)
"""
import csv, json, os
from scrape import run_actor, ROOT

EXPAND_MIN = 10_000
MAX_POSTS = 80
ROUNDS = 4
MAX_PER_ROUND = 400
SEARCHES = ["dancer actor comedian", "road to 100k", "road to 1M followers", "made by higgsfield",
            "dancing uncle", "dancing grandpa", "ai character", "sir", "daddy dance", "habibi dance"]
OUT = f"{ROOT}/discovery"
DB = f"{OUT}/profiles.json"


def in_niche(p):
    return (p.get("joinedRecently") and (p.get("followersCount") or 0) >= EXPAND_MIN
            and (p.get("postsCount") or 0) <= MAX_POSTS)


def related(p):
    return [r["username"] for r in p.get("relatedProfiles") or []]


def main():
    db = json.load(open(DB))
    expanded = set()

    sp = f"{OUT}/search_users.json"
    if not os.path.exists(sp):
        print("search…", flush=True)
        res = []
        for q in SEARCHES:
            try:
                res += run_actor("apify~instagram-search-scraper",
                                 {"search": q, "searchType": "user", "searchLimit": 40}, timeout=600)
            except Exception as e:
                print("  search failed", q, e, flush=True)
        json.dump(res, open(sp, "w"), ensure_ascii=False)
    res = json.load(open(sp))
    frontier = {r.get("username") for r in res if r.get("username")}
    print(f"search users: {len(frontier)}", flush=True)

    for rnd in range(ROUNDS):
        niche = [p for p in db.values() if in_niche(p) and p["username"] not in expanded]
        for p in niche:
            frontier |= set(related(p))
            expanded.add(p["username"])
        todo = sorted(u for u in frontier if u not in db)[:MAX_PER_ROUND]
        if not todo:
            break
        print(f"round {rnd+1}: {len(niche)} niche accounts expanded, scraping {len(todo)}…", flush=True)
        for p in run_actor("apify~instagram-profile-scraper", {"usernames": todo}):
            if p.get("username"):
                db[p["username"]] = p
        json.dump(db, open(DB, "w"), ensure_ascii=False)
        frontier = set()
        print(f"  niche total: {sum(1 for p in db.values() if in_niche(p))}", flush=True)

    niche = sorted((p for p in db.values() if in_niche(p)), key=lambda p: -p["followersCount"])
    with open(f"{OUT}/niche.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["username", "followers", "posts", "followers_per_post", "following", "category", "bio", "link", "url"])
        for p in niche:
            n = p.get("postsCount") or 1
            w.writerow([p["username"], p["followersCount"], n, p["followersCount"] // n, p.get("followsCount"),
                        p.get("businessCategoryName"), (p.get("biography") or "").replace("\n", " | "),
                        p.get("externalUrl"), f"https://www.instagram.com/{p['username']}/"])
    print(f"done: {len(niche)} new accounts >= {EXPAND_MIN} followers, <= {MAX_POSTS} posts", flush=True)
    for p in niche:
        print(f"  {p['username']:28} {p['followersCount']:>9} {p.get('postsCount'):>4} posts | "
              f"{(p.get('biography') or '').replace(chr(10), ' ')[:80]}")


if __name__ == "__main__":
    main()
