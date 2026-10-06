#!/usr/bin/env python3
"""Download finished 480p/4K results of the batch and print 480p dimensions for the upscale call.
Files: 480p/<char>_<n>.mp4, 4k/<char>/<char>_<n>_4k.mp4 (n = 1..5 per character)."""
import json, os, subprocess, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(f"{H}/plan.json")); res = json.load(open(f"{H}/results.json"))
seen = {}
for i, p in enumerate(plan):
    seen[p["char"]] = seen.get(p["char"], 0) + 1
    n = seen[p["char"]]; r = res.get(str(i), {})
    if r.get("url"):
        f = f"{H}/480p/{p['char']}_{n}.mp4"; os.makedirs(os.path.dirname(f), exist_ok=True)
        if not os.path.exists(f): urllib.request.urlretrieve(r["url"], f)
        if "wh" not in r:
            o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
            r["wh"] = [int(x) for x in o.split(",")]
    if r.get("url4k"):
        f = f"{H}/4k/MB_{p['char']}/MB_{p['char']}_{n}_4k.mp4"; os.makedirs(os.path.dirname(f), exist_ok=True)
        if not os.path.exists(f): urllib.request.urlretrieve(r["url4k"], f)
    if r.get("url") and not r.get("up"):
        print(i, p["job"], r["wh"])
json.dump(res, open(f"{H}/results.json", "w"), indent=1)
