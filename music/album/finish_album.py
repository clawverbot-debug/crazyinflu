"""Picks the best take per track and cuts dance loops.
Score = 'Prime Ads' heard clearly (ElevenLabs STT scribe_v1 count) + tempo steadiness. Loops start on the beat closest to the
[Chorus] / [Dance Break] start and last a whole number of 4-bar phrases (>= 15 s), so they repeat seamlessly.
Outputs final/NN_slug.mp3, loops/NN_slug_hook.mp3, loops/NN_slug_break.mp3, release.json."""
import json, os, re, subprocess, uuid, urllib.request, numpy as np, librosa
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(f"{H}/final", exist_ok=True); os.makedirs(f"{H}/loops", exist_ok=True)
EKEY = [l.split('=', 1)[1].strip().strip('"').strip("'") for l in open(os.path.expanduser('~/Downloads/clone-voix-fils/.env')) if l.strip().startswith('ELEVENLABS_API_KEY')][0]
def stt(path):
    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\nscribe_v1\r\n--{b}\r\nContent-Disposition: form-data; name="file"; filename="a.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode() + open(path, 'rb').read() + f'\r\n--{b}--\r\n'.encode()
    j = json.load(urllib.request.urlopen(urllib.request.Request('https://api.elevenlabs.io/v1/speech-to-text', data=body, headers={'xi-api-key': EKEY, 'Content-Type': f'multipart/form-data; boundary={b}'}), timeout=300))
    return j['text'], [{'w': x['text'], 's': x['start'], 'e': x['end']} for x in j['words'] if x.get('type') == 'word']
def beats_of(path, bpm):
    y, sr = librosa.load(path, sr=22050)
    _, b = librosa.beat.beat_track(y=y, sr=sr, start_bpm=bpm, tightness=300, units="time")
    i = np.arange(len(b)); s, c = np.polyfit(i, b, 1); return b, 60 / s, float(np.abs(b - (s * i + c)).max()), len(y) / sr
def section_start(words, tag):
    for w in words:
        if f"[{tag}" in w["w"]: return w["s"]
    return None
def cut_loop(src, dst, beats, t0, min_len=15.0):
    j0 = int(np.argmin(np.abs(beats - t0)))
    if beats[j0] > t0 + 0.12 and j0 > 0: j0 -= 1
    step = np.median(np.diff(beats)); bars = 4
    while bars * 4 * step < min_len: bars += 4              # whole 4-bar phrases
    j1 = j0 + bars * 4; ext = list(beats) + [beats[-1] + step * (k + 1) for k in range(64)]
    a, b = ext[j0], ext[j1]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.4f}", "-to", f"{b:.4f}", "-i", src, "-af", "afade=t=in:d=0.006,areverse,afade=t=in:d=0.006,areverse",
                    "-c:a", "libmp3lame", "-b:a", "256k", dst], check=True)
    return round(a, 3), round(b - a, 3), bars
A = json.load(open(f"{H}/album.json")); out = []
ONLY = set(os.environ.get("ONLY", "").split(",")) - {""}
prev = {str(r["n"]): r for r in json.load(open(f"{H}/release.json"))} if ONLY and os.path.exists(f"{H}/release.json") else {}
for k in sorted(A, key=int):
    v = A[k]; best = None
    if ONLY and k not in ONLY:
        if k in prev: out.append(prev[k])
        continue
    for t in v.get("takes", []):
        p = f"{H}/{t['file']}"; b, tempo, resid, dur = beats_of(p, v["bpm_target"])
        text, w = stt(p); low = text.lower()
        n_prime = len(re.findall(r"prime[\s-]?ads?\b", low)); n_bad = len(re.findall(r"\bprim(?:ax|ex|es|us)\b|\bprimes\b", low))
        sc = n_prime - 2 * n_bad - 10 * max(0, resid - 0.06)
        print(f"{v['title']:30s} {t['file'][-6:]} tempo {tempo:6.1f} resid {resid:.3f} 'Prime Ads' heard x{n_prime}, garbled x{n_bad} dur {dur:.0f}s -> {sc:.1f}", flush=True)
        if best is None or sc > best[0]: best = (sc, t, b, tempo, dur, n_prime)
    if not best: continue
    sc, t, b, tempo, dur, n_prime = best
    slug = re.sub(r"[^a-z0-9]+", "_", v["title"].lower()).strip("_"); src = f"{H}/{t['file']}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:a", "copy", f"{H}/final/{int(k):02d}_{slug}.mp3"], check=True)
    rec = dict(n=int(k), title=v["title"], bpm=round(tempo, 1), duration=round(dur, 1), take=t["file"], prime_ads_heard=n_prime, full=f"final/{int(k):02d}_{slug}.mp3")
    for tag, name in (("Chorus", "hook"), ("Dance Break", "break")):
        st = section_start(t["words"], tag)
        if st is None: continue
        a, L, bars = cut_loop(src, f"{H}/loops/{int(k):02d}_{slug}_{name}.mp3", b, st)
        rec[name] = dict(file=f"loops/{int(k):02d}_{slug}_{name}.mp3", start=a, length=L, bars=bars)
    out.append(rec)
json.dump(out, open(f"{H}/release.json", "w"), indent=1)
for r in out: print(r["n"], r["title"], r["bpm"], "BPM", r["duration"], "s", "hook", r.get("hook", {}).get("length"), "break", r.get("break", {}).get("length"))
