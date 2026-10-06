"""v2: music locked on the DANCE (body keypoints), not on the reel's audio (which is not in sync with the moves).
1. kinetic beats: YOLO pose → mean joint speed → deceleration envelope (dance hits).
2. per clip: fine search of tempo + phase + window (whole bars >= 5 s) maximising hits on beats vs half-beats.
3. per clip: the Prime Ads song version (6 takes, 84-129 BPM) whose tempo (x0.5/x1/x2) is closest; lyrics continue line by line.
4. rubberband (R3 engine) stretches the song window so its beats land on the dance beats; downbeat on the bar's strongest hit."""
import json, subprocess, numpy as np, soundfile as sf, re
from scipy.ndimage import gaussian_filter1d
from kine import kinetic
P = json.load(open("pose.json")); M = "../../music/"
SB = json.load(open(M + "promo_beats.json")); LY = json.load(open(M + "promo_lyrics.json"))
TAKES = {"A1": "promoA_full_1.mp3", "A2": "promoA_full_2.mp3", "B1": "promoB_full_1.mp3", "B2": "promoB_full_2.mp3", "C1": "promoC_full_1.mp3", "C2": "promoC_full_2.mp3"}
ORDER = ["05_prime_thecoach", "03_prime_cartman1", "08_prime_banwavebarry", "01_prime_texas_guy", "02_prime_leopold",
         "04_prime_oliviaa", "09_prime_scotty", "07_prime_roshi", "06_prime_jacked"]
FPS, SR = 24, 48000
def song_tempo(b): b = np.array(b); i = np.arange(len(b)); return 60 / np.polyfit(i, b, 1)[0]
TT = {k: song_tempo(SB[v]["beats"]) for k, v in TAKES.items()}
def lines(take):
    out, cur, st = [], [], None
    for w in LY[take]:
        txt = re.sub(r"\[.*?\]\s*", "", w["w"])
        if st is None and txt.strip(): st = w["s"]
        cur.append(txt.strip())
        if "\n" in w["w"] or w is LY[take][-1]:
            t = " ".join(x for x in cur if x)
            if t: out.append((st, t))
            cur, st = [], None
    return out
def fit(d):
    sp, dec, _ = kinetic(d); fr = d["fps"]
    e = dec - gaussian_filter1d(dec, 24); e = gaussian_filter1d(e, 0.8); e = (e - e.mean()) / e.std()
    t = np.arange(len(e)) / fr; E = lambda x: np.interp(x, t, e)
    dur = len(e) / fr; best = None
    for T in np.arange(70, 150, 0.1):
        bt = 60 / T; n = 4 * int(np.ceil(5 / (4 * bt))); L = n * bt
        for ph in np.arange(0, bt, 1 / 96):
            k = np.arange(int((dur - ph) / bt) + 1); B = ph + k * bt
            on, off = E(B), E(B + bt / 2)
            for s in range(0, len(B) - n):                    # window = beats s..s+n
                if B[s] < 0.2 or B[s + n] > dur - 0.1: continue
                sc = on[s:s + n].mean() - off[s:s + n].mean()
                if best is None or sc > best[0]: best = (sc, T, ph, s, n)
    sc, T, ph, s, n = best; bt = 60 / T
    B = ph + np.arange(s, s + n + 1) * bt
    # downbeat: shift start to the strongest of the first 4 beats if the window still fits
    strength = [E(ph + (s + r + 4 * np.arange(n // 4)) * bt).mean() for r in range(4)]
    r = int(np.argmax(strength))
    if ph + (s + r + n) * bt <= dur - 0.1: B = ph + np.arange(s + r, s + r + n + 1) * bt
    rnd = np.mean([max(E(ph + (s + q) * bt + np.random.uniform(0, bt, n)).mean() - 0, -9) for q in range(1)])
    return dict(T=T, beats=B, score=sc, n=n)
def pick_take(T, used):
    c = []
    for k, st in TT.items():
        for m in (0.5, 1, 2):
            c.append((abs(np.log(st / (T * m))) + (0.01 if k in used else 0), k, m))
    return min(c)
cursor = 0; segs = []; log = []; used = set()
for idx, clip in enumerate(ORDER):
    f = fit(P[clip]); B = f["beats"]; c0, c1 = B[0], B[-1]
    err, take, m = pick_take(f["T"], used); used.add(take)
    sbeats = list(SB[TAKES[take]]["beats"]); sst = np.median(np.diff(sbeats)); sbeats += [sbeats[-1] + sst * (j + 1) for j in range(40)]
    L = lines(take)
    target = L[min(cursor, len(L) - 1)][0] if idx < len(ORDER) - 1 else [s for s, t in L if t.lower().startswith("prime ads, built")][-1]
    j0 = max(i for i, x in enumerate(sbeats) if x <= target + 0.08)
    ns = int(round(f["n"] * m)); s0, s1 = sbeats[j0], sbeats[j0 + ns]
    cursor = next((i for i, (s, t) in enumerate(L) if s >= s1 - 0.3), len(L))
    # frame-quantised video cut, audio mapped so song beat j0 lands exactly on dance beat c0
    v0, v1 = np.floor(c0 * FPS) / FPS, np.ceil(c1 * FPS) / FPS
    r = (s1 - s0) / (c1 - c0)                       # song seconds per video second
    a0, a1 = s0 - (c0 - v0) * r, s1 + (v1 - c1) * r
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a0:.4f}", "-t", f"{a1 - a0:.4f}", "-i", M + TAKES[take], "-ar", str(SR), "-ac", "2", f"raw{idx}.wav"], check=True)
    subprocess.run(["rubberband", "-3", "-q", "-D", f"{v1 - v0:.5f}", f"raw{idx}.wav", f"st{idx}.wav"], check=True)
    a, _ = sf.read(f"st{idx}.wav"); N = int(round((v1 - v0) * SR))
    a = a[:N] if len(a) >= N else np.vstack([a, np.zeros((N - len(a), 2))])
    fl = int(0.006 * SR); w = np.linspace(0, 1, fl)[:, None]; a[:fl] *= w; a[-fl:] *= w[::-1]
    segs.append(a)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip + ".mp4", "-vf", f"trim={v0:.5f}:{v1:.5f},setpts=PTS-STARTPTS,fps={FPS},scale=1080:1920:flags=lanczos,setsar=1",
                    "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", f"v2seg{idx}.mp4"], check=True)
    lyr = " / ".join(t for s, t in L if s0 - 0.3 <= s < s1 - 0.3)
    log.append(f"{clip:24s} dance {f['T']:6.1f} BPM (fit {f['score']:.2f})  {v0:5.2f}-{v1:5.2f}s  take {take} {TT[take]:.1f}{'x'+str(m) if m!=1 else ''}  stretch {1/r:.3f}  « {lyr} »")
sf.write("music_track_v2.wav", np.vstack(segs), SR)
open("list2.txt", "w").write("".join(f"file 'v2seg{i}.mp4'\n" for i in range(len(ORDER))))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list2.txt", "-i", "music_track_v2.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", "prime_ads_compil_v2.mp4"], check=True)
print("\n".join(log))
