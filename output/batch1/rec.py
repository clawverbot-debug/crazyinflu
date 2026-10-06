#!/usr/bin/env python3
"""rec.py <field> idx=value ...  → results.json[idx][field]=value (url values may be given as the hf_… file stem)."""
import json, sys, os
H = os.path.dirname(os.path.abspath(__file__)); B = "https://d8j0ntlcm91z4.cloudfront.net/user_3KBMjsKZKfoMloFADHAlRKcM31C/"
res = json.load(open(f"{H}/results.json")); field = sys.argv[1]
for kv in sys.argv[2:]:
    k, v = kv.split("=", 1)
    if v.startswith("hf_"): v = B + v + ".mp4"
    res.setdefault(k, {})[field] = v
json.dump(res, open(f"{H}/results.json", "w"), indent=1)
print(len(res), "entries;", sum(1 for r in res.values() if r.get("url")), "480p,", sum(1 for r in res.values() if r.get("up")), "up,", sum(1 for r in res.values() if r.get("url4k")), "4k")
