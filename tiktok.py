#!/usr/bin/env python3
"""TikTok side: same characters on TikTok + hunt for NEW character accounts that blew up.

TikTok has no "new" badge → an account is new if its oldest video is < NEW_DAYS old.
Steps: 1) the 4 seed names on TikTok  2) keyword/hashtag search  3) full video list of every
author with >= MIN_FANS fans → age, cadence, views.

Usage: APIFY_TOKEN=... python3 tiktok.py
Outputs: tiktok/search.json, tiktok/authors/<name>.json, tiktok/new_accounts.csv
"""
import csv, json, os, datetime as dt
from scrape import run_actor, ROOT

ACTOR = "clockworks~tiktok-scraper"
SEEDS = ["dahab.daddy", "dahabdaddy", "haroldpuddington", "sirpuddington", "abu.shalab", "abushalab",
         "abu.yalla", "abuyalla", "benjamin_stachio"]
QUERIES = ["dahab daddy", "harold puddington", "abu shalab", "abu yalla", "dancing uncle",
           "old man dancing wedding", "grandpa dancing", "funny uncle dance", "ai character dance",
           "habibi dance", "mustache man dancing", "sir dancing", "higgsfield"]
HASHTAGS = ["higgsfield", "higgsfieldai", "aicharacter", "aidance", "dancinguncle", "dancinggrandpa",
            "aicomedy", "aiinfluencer"]
MIN_FANS = 50_000
NEW_DAYS = 45
OUT = f"{ROOT}/tiktok"
NOW = dt.datetime.now(dt.timezone.utc)


def cached(path, fn):
    if os.path.exists(path):
        return json.load(open(path))
    data = fn()
    json.dump(data, open(path, "w"), ensure_ascii=False)
    return data


def main():
    os.makedirs(f"{OUT}/authors", exist_ok=True)
    print("seed profiles…", flush=True)
    seeds = cached(f"{OUT}/seeds.json", lambda: run_actor(ACTOR, {
        "profiles": SEEDS, "resultsPerPage": 100, "profileScrapeSections": ["videos"],
        "shouldDownloadVideos": False, "shouldDownloadCovers": False}))
    print(f"  {len(seeds)} videos", flush=True)
    print("search…", flush=True)
    search = cached(f"{OUT}/search.json", lambda: run_actor(ACTOR, {
        "searchQueries": QUERIES, "hashtags": HASHTAGS, "resultsPerPage": 60,
        "searchSection": "/video", "shouldDownloadVideos": False, "shouldDownloadCovers": False}))
    print(f"  {len(search)} videos", flush=True)

    authors = {}
    for v in seeds + search:
        a = v.get("authorMeta") or {}
        if a.get("name") and (a.get("fans") or 0) >= MIN_FANS:
            authors[a["name"]] = a
    todo = [n for n in authors if not os.path.exists(f"{OUT}/authors/{n}.json")]
    print(f"{len(authors)} authors >= {MIN_FANS} fans, scraping {len(todo)} full profiles…", flush=True)
    if todo:
        vids = run_actor(ACTOR, {"profiles": todo, "resultsPerPage": 300, "profileScrapeSections": ["videos"],
                                 "profileSorting": "latest", "shouldDownloadVideos": False,
                                 "shouldDownloadCovers": False})
        by = {}
        for v in vids:
            by.setdefault((v.get("authorMeta") or {}).get("name"), []).append(v)
        for n in todo:
            json.dump(by.get(n, []), open(f"{OUT}/authors/{n}.json", "w"), ensure_ascii=False)

    rows = []
    for n, a in authors.items():
        vids = json.load(open(f"{OUT}/authors/{n}.json"))
        if not vids:
            continue
        times = sorted(dt.datetime.fromisoformat(v["createTimeISO"].replace("Z", "+00:00")) for v in vids
                       if v.get("createTimeISO"))
        if not times:
            continue
        age = (NOW - times[0]).days
        plays = sorted((v.get("playCount") or 0 for v in vids), reverse=True)
        rows.append({"name": n, "nick": a.get("nickName"), "fans": a.get("fans"), "videos": a.get("video"),
                     "scraped": len(vids), "first_post": times[0].date().isoformat(), "age_days": age,
                     "posts_per_day": round(len(vids) / max(age, 1), 1), "max_views": plays[0],
                     "median_views": plays[len(plays) // 2], "new": age <= NEW_DAYS,
                     "bio": (a.get("signature") or "").replace("\n", " | "),
                     "url": f"https://www.tiktok.com/@{n}"})
    rows.sort(key=lambda r: (not r["new"], -r["fans"]))
    with open(f"{OUT}/new_accounts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["name"])
        w.writeheader()
        w.writerows(rows)
    print(f"done: {sum(r['new'] for r in rows)} new accounts (< {NEW_DAYS} days) out of {len(rows)}", flush=True)
    for r in rows[:60]:
        print(f"  {'NEW' if r['new'] else '   '} {r['name']:26} {r['fans']:>9} fans  first {r['first_post']}  "
              f"{r['posts_per_day']}/d  max {r['max_views']:>10}  med {r['median_views']:>9} | {r['bio'][:60]}")


if __name__ == "__main__":
    main()
