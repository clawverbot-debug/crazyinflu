"""Targeted scan: women's dance trends on Instagram (last 72 h), ranked by views per hour. Apify instagram-hashtag-scraper (reels).
Token from ~/.config/viral-spy/apify_token (never printed). Output scan.json + thumbs/ for visual review."""
import json, os, time, urllib.request, datetime as dt
TOKEN = open(os.path.expanduser("~/.config/viral-spy/apify_token")).read().strip()
TAGS = ["irishdance", "irishdancing", "irishdancer", "stepdance", "tapdance", "riverdance", "irishdancechallenge", "feis"]
API = "https://api.apify.com/v2"
def call(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))
run = call(f"{API}/acts/apify~instagram-hashtag-scraper/runs?token={TOKEN}", {"hashtags": TAGS, "resultsLimit": 30, "resultsType": "reels"})["data"]
print("run", run["id"], flush=True)
for _ in range(80):
    time.sleep(10); st = call(f"{API}/actor-runs/{run['id']}?token={TOKEN}")["data"]
    if st["status"] not in ("READY", "RUNNING"): break
print("status", st["status"], "cost $", st.get("usageTotalUsd"))
items = call(f"{API}/datasets/{st['defaultDatasetId']}/items?token={TOKEN}&clean=1")
now = dt.datetime.now(dt.timezone.utc); out = {}
for r in items:
    if not r.get("shortCode") or not r.get("timestamp"): continue
    age = (now - dt.datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))).total_seconds() / 3600
    v = r.get("videoPlayCount") or r.get("videoViewCount") or 0
    dur = r.get("videoDuration") or 0
    if age > 120 or v < 15000 or not (7 <= dur <= 45): continue
    out[r["shortCode"]] = dict(code=r["shortCode"], url=r.get("url"), owner=r.get("ownerUsername"), views=v, age_h=round(age, 1), vph=round(v / max(age, 1)),
                               likes=r.get("likesCount"), dur=round(dur, 1), caption=(r.get("caption") or "")[:120], thumb=r.get("displayUrl"), video=r.get("videoUrl"),
                               music=(r.get("musicInfo") or {}).get("song_name") if isinstance(r.get("musicInfo"), dict) else None)
rank = sorted(out.values(), key=lambda x: -x["vph"])
json.dump(rank, open("scan.json", "w"), indent=1)
os.makedirs("thumbs", exist_ok=True)
for i, x in enumerate(rank[:24]):
    try: urllib.request.urlretrieve(x["thumb"], f"thumbs/{i:02d}.jpg")
    except Exception as e: print("thumb fail", i, e)
    print(f'{i:2d} {x["vph"]:>7}/h {x["views"]:>9} views {x["age_h"]:5.1f}h {x["dur"]:5.1f}s @{x["owner"]} | {x["caption"][:60]!r}')
