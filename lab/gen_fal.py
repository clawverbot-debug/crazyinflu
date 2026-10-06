#!/usr/bin/env python3
"""Generate Lab character images with GPT Image 2 on fal.ai (key read from ~/Downloads/ai_cartoon_engine/.env, never printed).
Usage: python3 gen_fal.py prompts.json   ->  gallery/<name>.png   (prompts.json = {"name": "prompt", ...})"""
import json, os, sys, time, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
KEY = next(l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/Downloads/ai_cartoon_engine/.env")) if l.startswith("FAL_KEY="))

def gen(item):
    name, spec = item
    spec = spec if isinstance(spec, dict) else {"prompt": spec}
    body = {"prompt": spec["prompt"], "image_size": spec.get("size") or {"width": 1152, "height": 2048}, "quality": "high", "num_images": 1}
    endpoint = "openai/gpt-image-2"
    if spec.get("ref"):  # edit mode: local reference image sent as a data URI
        import base64
        body["image_urls"] = ["data:image/jpeg;base64," + base64.b64encode(open(spec["ref"], "rb").read()).decode()]
        endpoint += "/edit"
    H = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
    try:
        req = urllib.request.Request(f"https://queue.fal.run/{endpoint}", data=json.dumps(body).encode(), headers=H)
        sub = json.load(urllib.request.urlopen(req, timeout=60))
        for _ in range(120):
            time.sleep(5)
            st = json.load(urllib.request.urlopen(urllib.request.Request(sub["status_url"], headers=H), timeout=60))
            if st.get("status") == "COMPLETED":
                break
        res = json.load(urllib.request.urlopen(urllib.request.Request(sub["response_url"], headers=H), timeout=60))
        url = res["images"][0]["url"]
        urllib.request.urlretrieve(url, f"{HERE}/gallery/{name}.png")
        return f"{name}: ok"
    except urllib.error.HTTPError as e:
        return f"{name}: HTTP {e.code} {e.read()[:300]}"
    except Exception as e:
        return f"{name}: {e}"

items = list(json.load(open(sys.argv[1])).items())
with cf.ThreadPoolExecutor(int(os.environ.get('PAR', 4))) as ex:
    for res in ex.map(gen, items):
        print(res, flush=True)
