#!/usr/bin/env python3
"""GPT Image 2 image-to-image edits on kie.ai (key KIE_API_KEY from ~/Downloads/clone-voix-fils/.env, never printed).
Usage: python3 gen_kie.py edits.json   with edits.json = {"name": {"ref_url": "https://…", "prompt": "…"}}  ->  gallery/<name>.png"""
import json, os, sys, time, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
KEY = next(l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/Downloads/clone-voix-fils/.env")) if l.startswith("KIE_API_KEY="))
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=H)
    return json.load(urllib.request.urlopen(r, timeout=60))

def run(item):
    name, spec = item
    try:
        t = req("https://api.kie.ai/api/v1/jobs/createTask", {"model": "gpt-image-2-image-to-image", "input": {
            "prompt": spec["prompt"], "input_urls": [spec["ref_url"]], "aspect_ratio": spec.get("aspect_ratio", "9:16"), "resolution": "2K"}})
        tid = (t.get("data") or {}).get("taskId")
        if not tid: return f"{name}: create failed {json.dumps(t)[:200]}"
        for _ in range(120):
            time.sleep(6)
            d = req(f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={tid}").get("data") or {}
            if d.get("state") == "success":
                url = json.loads(d["resultJson"])["resultUrls"][0]
                urllib.request.urlretrieve(url, f"{HERE}/gallery/{name}.png")
                return f"{name}: ok"
            if d.get("state") == "fail": return f"{name}: fail {d.get('failMsg')}"
        return f"{name}: timeout ({tid})"
    except Exception as e:
        return f"{name}: {e}"

items = list(json.load(open(sys.argv[1])).items())
with cf.ThreadPoolExecutor(int(os.environ.get("PAR", 6))) as ex:
    for r in ex.map(run, items): print(r, flush=True)
