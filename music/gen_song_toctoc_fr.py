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
Toc toc toc ! Qui c'est qui frappe ?
Toc toc toc ! C'est Prime Ads !

[Refrain]
Toc toc toc, qui frappe à ma porte ?
C'est Prime Ads, ouvre-lui vite !
Les comptes tournent, la pub est forte
Built to stay live, et tout le monde s'agite !

[Couplet]
Les mains en l'air, on monte le budget !
On tape des pieds, la campagne est lancée !
On tourne à gauche, on tourne à droite
Et le Q4 nous fait danser !

[Refrain]
Toc toc toc, qui frappe à ma porte ?
C'est Prime Ads, ouvre-lui vite !
Les comptes tournent, la pub est forte
Built to stay live, et tout le monde s'agite !"""
STYLE = ("Chanson festive française de bal populaire, ambiance fête de village et mariage, accordéon, cuivres et fanfare, "
         "basse oom-pah, claps, foule qui chante en chœur, chanson à gestes, voix masculine joviale et rigolote en français, "
         "refrain très simple à reprendre, 126 bpm, majeur, énergie de fin de soirée")
NEG = "sad, slow, ballad, rap, trap, english vocals, metal, orchestral"

def req(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))

d = req("https://api.kie.ai/api/v1/generate", {"prompt": LYRICS, "customMode": True, "instrumental": False, "model": "V5",
        "style": STYLE, "title": "Toc Toc Toc (Prime Ads)", "vocalGender": "m", "negativeTags": NEG,
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
    full = f"{H}/toctoc_fr_full_{i}.mp3"; urllib.request.urlretrieve(url, full)
    print("track", i, "duration", tr.get("duration"), flush=True)
