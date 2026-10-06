"""Custom track for Leopold's step-dance video: Celtic step-dance pop at the dance's tempo (103 BPM, jig feel), Prime Ads chant.
Suno V5 via kie (key never printed). Outputs step_<n>.mp3 + timestamped lyrics in step.json."""
import json, os, time, urllib.request
KEY = next(l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/Downloads/clone-voix-fils/.env")) if l.startswith("KIE_API_KEY="))
def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))
LYRICS = """[Intro]
Hey! Prime! Ads!
[Chorus]
Step it up, step it up, Prime! Ads!
Feet on the floor for the Q4 ads
Step it up, step it up, built to stay live
Prime! Ads! Dance all night
[Verse]
Meta ad accounts, ready to go
Media buyers, steal the show
Kick to the left, kick to the right
Prime! Ads! Built to stay live
[Chorus]
Step it up, step it up, Prime! Ads!
Feet on the floor for the Q4 ads
Step it up, step it up, built to stay live
Prime! Ads! Dance all night
[Dance Break]
Hey! Hey! Prime! Ads!
Hey! Hey! Stay live!
[Outro]
Prime! Ads!"""
STYLE = ("Irish hornpipe pop, moderate tempo, dotted swing rhythm, fiddle and tin whistle melody, bodhran, hard shoe stomps and claps on every beat, "
         "half-time kick, 103 bpm, NOT fast, steady laid-back groove, energetic group chant vocals in English, PRIME and ADS shouted as two separate words, "
         "very clear diction, catchy hook from the first second, viral dance challenge")
NEG = "fast jig, reel, 140 bpm, double time, slow intro, ballad, rubato, tempo changes, metal, orchestral, children"
d = req("https://api.kie.ai/api/v1/generate", {"prompt": LYRICS, "customMode": True, "instrumental": False, "model": "V5", "style": STYLE,
        "title": "Step It Up (Prime Ads)", "negativeTags": NEG, "callBackUrl": "https://example.com/kie-callback"})
tid = d["data"]["taskId"]; print("task", tid, flush=True)
for _ in range(60):
    time.sleep(15)
    data = (req(f"https://api.kie.ai/api/v1/generate/record-info?taskId={tid}") or {}).get("data") or {}
    st = data.get("status"); sd = ((data.get("response") or {}).get("sunoData")) or []
    if st in ("CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "SENSITIVE_WORD_ERROR"): raise SystemExit(f"{st}: {data.get('errorMessage')}")
    if st == "SUCCESS" and sd: break
out = {"task": tid, "takes": []}
for i, tr in enumerate(sd[:2], 1):
    f = f"step_{i}.mp3"; urllib.request.urlretrieve(tr.get("audioUrl") or tr.get("streamAudioUrl"), f)
    lw = req("https://api.kie.ai/api/v1/generate/get-timestamped-lyrics", {"taskId": tid, "audioId": tr["id"]})
    out["takes"].append({"file": f, "duration": tr.get("duration"), "words": [{"w": w["word"], "s": w["startS"], "e": w["endS"]} for w in ((lw.get("data") or {}).get("alignedWords") or [])]})
    print("take", i, tr.get("duration"), flush=True)
json.dump(out, open("step.json", "w"), indent=1)
