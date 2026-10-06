#!/usr/bin/env python3
"""Scrape all reels + profile info of the benchmark accounts via Apify.

Usage: APIFY_TOKEN=... python3 scrape.py [username ...]
Outputs: data/<user>/profile.json, data/<user>/reels.json, data/<user>/videos/<shortcode>.mp4
"""
import json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf

TOKEN = os.environ["APIFY_TOKEN"]
USERS = sys.argv[1:] or ["dahab.daddy", "haroldpuddington", "abu.yalla", "abu.shalab"]
ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://api.apify.com/v2"


def _get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5)


def run_actor(actor, payload, timeout=1800):
    """Start the actor, poll until it finishes, return its dataset items (sync endpoint drops long runs)."""
    req = urllib.request.Request(f"{API}/acts/{actor}/runs?token={TOKEN}&timeout={timeout}",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        run = json.load(r)["data"]
    while run["status"] in ("READY", "RUNNING"):
        time.sleep(10)
        run = _get(f"{API}/actor-runs/{run['id']}?token={TOKEN}")["data"]
    if run["status"] != "SUCCEEDED":
        print(f"  {actor} run {run['id']} ended {run['status']}", flush=True)
    return _get(f"{API}/datasets/{run['defaultDatasetId']}/items?token={TOKEN}&clean=1")


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 10_000:
        return "skip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())
    return "ok"


def main():
    os.makedirs(f"{ROOT}/data", exist_ok=True)
    print("profiles…", flush=True)
    profiles = run_actor("apify~instagram-profile-scraper", {"usernames": USERS})
    for p in profiles:
        d = f"{ROOT}/data/{p['username']}"
        os.makedirs(f"{d}/videos", exist_ok=True)
        json.dump(p, open(f"{d}/profile.json", "w"), indent=1, ensure_ascii=False)
        print(f"  {p['username']}: {p.get('followersCount')} followers, {p.get('postsCount')} posts", flush=True)

    for u in USERS:
        d = f"{ROOT}/data/{u}"
        os.makedirs(f"{d}/videos", exist_ok=True)
        print(f"reels {u}…", flush=True)
        t = time.time()
        reels = run_actor("apify~instagram-reel-scraper", {"username": [u], "resultsLimit": 500})
        json.dump(reels, open(f"{d}/reels.json", "w"), indent=1, ensure_ascii=False)
        print(f"  {len(reels)} reels in {time.time()-t:.0f}s", flush=True)
        jobs = [(r["videoUrl"], f"{d}/videos/{r['shortCode']}.mp4") for r in reels if r.get("videoUrl")]
        with cf.ThreadPoolExecutor(6) as ex:
            res = list(ex.map(lambda j: _safe(download, *j), jobs))
        print(f"  downloaded {res.count('ok')}, skipped {res.count('skip')}, failed {len(res)-res.count('ok')-res.count('skip')}", flush=True)


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return f"err {e}"


if __name__ == "__main__":
    main()
