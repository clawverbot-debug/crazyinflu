#!/usr/bin/env python3
"""Original 30 s dance track for the characters, matched to the feel of @prime_leopold's "Toc Toc" reel audio
(analysed: instrumental, ~112 BPM, G# minor, very heavy sub-bass, 74 % percussive energy → amapiano / log-drum groove).
Same tempo, key, genre and energy so the same dance fits; original melody and English lyrics (no copy of the source).
Suno V5 through kie.ai (key KIE_API_KEY from ~/Downloads/clone-voix-fils/.env, never printed). Then the best
beat-aligned 30 s window is cut with ffmpeg → music/knock_knock_30s_<n>.mp3"""
import json, os, time, urllib.request, subprocess
H = os.path.dirname(os.path.abspath(__file__))
KEY = next(l.split("=", 1)[1].strip().strip('"') for l in open(os.path.expanduser("~/Downloads/clone-voix-fils/.env")) if l.startswith("KIE_API_KEY="))
LYRICS = """[Intro]
PRIME! (ADS!) Stay live!
PRIME! (ADS!) Stay live!

[Chorus]
Prime... Ads! Built to stay live
Meta ads running day and night
Q4 rush and we still ride
Prime... Ads! Built to stay live

[Verse]
Scale it up, don't slow it down
Agency accounts all over town
Raise the budget, let it fly
Campaigns on and the ROAS high

[Chorus]
Prime... Ads! Built to stay live
Meta ads running day and night
Q4 rush and we still ride
Prime... Ads! Built to stay live"""
STYLE = ("Amapiano dance track, 112 bpm, G# minor, deep rolling log drum bass, heavy sub bass, crisp shakers and rim shots, "
         "punchy kicks, sparse jazzy piano stabs, catchy male group chant vocals in English, call and response, the brand name PRIME ADS shouted clearly as two separate words (PRIME, then ADS) in call and response, very clear diction, "
         "viral dance challenge, groovy, minimal, club ready")
NEG = "slow, ballad, rock, acoustic guitar, children, orchestral, metal"

def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))

d = req("https://api.kie.ai/api/v1/generate", {"prompt": LYRICS, "customMode": True, "instrumental": False, "model": "V5",
        "style": STYLE, "title": "Built To Stay Live", "vocalGender": "m", "negativeTags": NEG,
        "callBackUrl": "https://example.com/kie-callback"})
if d.get("code") != 200: raise SystemExit(f"create failed: {d}")
tid = d["data"]["taskId"]; print("task", tid, flush=True)
sd = []
for _ in range(60):
    time.sleep(15)
    data = (req(f"https://api.kie.ai/api/v1/generate/record-info?taskId={tid}") or {}).get("data") or {}
    st = data.get("status"); sd = ((data.get("response") or {}).get("sunoData")) or []
    print(" ", st, len(sd), flush=True)
    if st in ("CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "SENSITIVE_WORD_ERROR"): raise SystemExit(f"{st}: {data.get('errorMessage')}")
    if st == "SUCCESS" and sd: break
for i, tr in enumerate(sd[:2], 1):
    url = tr.get("audioUrl") or tr.get("sourceAudioUrl") or tr.get("streamAudioUrl")
    full = f"{H}/stay_live_b_full_{i}.mp3"; urllib.request.urlretrieve(url, full)
    print("track", i, "duration", tr.get("duration"), flush=True)
