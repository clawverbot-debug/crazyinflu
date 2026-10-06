#!/usr/bin/env python3
"""Do the wave accounts delete (or archive) their flops?

Re-scrapes the reels of each wave account and compares with the earlier snapshot in data/<u>/reels.json.
A reel seen before, inside the period the new scrape still covers, and missing now = removed.
Usage: APIFY_TOKEN=... python3 deletions.py
Outputs: analysis/deletions.json
"""
import json, os, statistics as st, datetime as dt
from collect import guarded
from scrape import ROOT

WAVE = ["jean_philanthrope", "benjamin_stachio", "don_nuger", "sebastianperfill", "edmond_lebon", "mr_twirlo",
        "abu.shalab", "abu.yalla", "dahab.daddy", "haroldpuddington"]


def main():
    old = {u: json.load(open(f"{ROOT}/data/{u}/reels.json")) for u in WAVE if os.path.exists(f"{ROOT}/data/{u}/reels.json")}
    snap_path = f"{ROOT}/analysis/rescrape_reels.json"
    if not os.path.exists(snap_path):
        new = guarded("apify~instagram-reel-scraper", {"username": WAVE, "resultsLimit": 80})
        json.dump(new, open(snap_path, "w"), ensure_ascii=False)
    new = json.load(open(snap_path))
    prof = guarded("apify~instagram-profile-scraper", {"usernames": WAVE})
    posts_now = {p["username"]: p.get("postsCount") for p in prof if p.get("username")}
    out = {}
    for u, rs in old.items():
        rs = [r for r in rs if r.get("ownerUsername") == u]
        now = [r for r in new if r.get("ownerUsername") == u]
        now_codes = {r["shortCode"] for r in now}
        if not now:
            out[u] = {"error": "no reels returned"}
            continue
        oldest_now = min(r["timestamp"] for r in now)
        covered = [r for r in rs if r["timestamp"] >= oldest_now]  # only judge reels the new scrape should still list
        gone = [r for r in covered if r["shortCode"] not in now_codes]
        kept = [r for r in covered if r["shortCode"] in now_codes]
        v = lambda r: r.get("videoPlayCount") or 0
        out[u] = {"before": len(rs), "now": len(now), "covered": len(covered), "removed": len(gone),
                  "posts_count_profile": posts_now.get(u),
                  "removed_median_views": int(st.median([v(r) for r in gone])) if gone else None,
                  "kept_median_views": int(st.median([v(r) for r in kept])) if kept else None,
                  "removed": [{"code": r["shortCode"], "date": r["timestamp"][:16], "views": v(r),
                               "caption": (r.get("caption") or "")[:60]} for r in gone]}
        print(f"{u:20} avant {len(rs):3} | couverts {len(covered):3} | disparus {len(gone):2} "
              f"(médiane {out[u]['removed_median_views']}) | gardés médiane {out[u]['kept_median_views']} | posts profil {posts_now.get(u)}")
        for g in out[u]["removed"]:
            print(f"     - {g['date']} {g['views']:>10} vues | {g['caption']}")
    json.dump(out, open(f"{ROOT}/analysis/deletions.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
