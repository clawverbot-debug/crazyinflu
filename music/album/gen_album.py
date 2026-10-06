"""Generates the PRIME ADS album with Suno V5 through kie.ai (key KIE_API_KEY from ~/Downloads/clone-voix-fils/.env, never printed).
2 takes per track → takes/NN_<slug>_<k>.mp3 + timestamped lyrics → album.json (task, audio ids, durations, words)."""
import json, os, re, time, urllib.request
from tracks import TRACKS, COMMON, NEG
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(f"{H}/takes", exist_ok=True)
KEY = next(l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/Downloads/clone-voix-fils/.env")) if l.startswith("KIE_API_KEY="))
def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
state = json.load(open(f"{H}/album.json")) if os.path.exists(f"{H}/album.json") else {}
for t in TRACKS:
    k = str(t["n"])
    if k in state and state[k].get("task"): continue
    d = req("https://api.kie.ai/api/v1/generate", {"prompt": t["lyrics"], "customMode": True, "instrumental": False, "model": "V5",
            "style": COMMON + t["style"], "title": t["title"], "negativeTags": NEG, "callBackUrl": "https://example.com/kie-callback"})
    if d.get("code") != 200: print("create failed", t["title"], d.get("msg")); continue
    state[k] = {"title": t["title"], "bpm_target": t["bpm"], "task": d["data"]["taskId"]}; print("submitted", t["n"], t["title"], flush=True)
    json.dump(state, open(f"{H}/album.json", "w"), indent=1); time.sleep(1.5)
for _ in range(80):
    pending = [k for k, v in state.items() if not v.get("takes")]
    if not pending: break
    time.sleep(15)
    for k in pending:
        v = state[k]; data = (req(f"https://api.kie.ai/api/v1/generate/record-info?taskId={v['task']}") or {}).get("data") or {}
        st = data.get("status"); sd = ((data.get("response") or {}).get("sunoData")) or []
        if st in ("CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "SENSITIVE_WORD_ERROR"): v["takes"] = []; v["error"] = f"{st}: {data.get('errorMessage')}"; print("FAILED", v["title"], v["error"]); continue
        if st == "SUCCESS" and sd:
            v["takes"] = []
            for i, tr in enumerate(sd[:2], 1):
                url = tr.get("audioUrl") or tr.get("sourceAudioUrl") or tr.get("streamAudioUrl")
                f = f"takes/{int(k):02d}_{slug(v['title'])}_{i}.mp3"; urllib.request.urlretrieve(url, f"{H}/{f}")
                words = []
                try:
                    lw = req("https://api.kie.ai/api/v1/generate/get-timestamped-lyrics", {"taskId": v["task"], "audioId": tr["id"]})
                    words = [{"w": w["word"], "s": w["startS"], "e": w["endS"]} for w in ((lw.get("data") or {}).get("alignedWords") or [])]
                except Exception as e: print("lyrics failed", f, e)
                v["takes"].append({"file": f, "audio_id": tr["id"], "duration": tr.get("duration"), "words": words})
            print("done", k, v["title"], [x["duration"] for x in v["takes"]], flush=True)
    json.dump(state, open(f"{H}/album.json", "w"), indent=1)
print("ALBUM DONE", sum(len(v.get("takes", [])) for v in state.values()), "takes")
