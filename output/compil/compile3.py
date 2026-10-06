"""v3: music locked on the dance. Pose (YOLO11) → kinetic hits (1-s compression pattern removed) → per clip, joint search of
tempo + phase + 6-s window by correlation with a beat pulse train (reel-audio tempo only breaks ties) → whole bars >= 5 s from the
strongest beat of the bar → Prime Ads song take closest in tempo (x0.5/1/2), rubberband R3 stretch so song beats land on dance beats.
Lyrics run line by line across clips and always end on 'Contact us now! Prime Ads!'."""
import json, subprocess, re, numpy as np, soundfile as sf, librosa
from tempo3 import env, P
M = "../../music/"; FPS, SR = 24, 48000
SB = json.load(open(M + "promo_beats.json")); LY = json.load(open(M + "promo_lyrics.json")); T3 = json.load(open("tempo3.json"))
TAKES = {"A1": "promoA_full_1.mp3", "A2": "promoA_full_2.mp3", "B1": "promoB_full_1.mp3", "B2": "promoB_full_2.mp3", "C1": "promoC_full_1.mp3", "C2": "promoC_full_2.mp3"}
AUD = {"01_prime_texas_guy": 122.5, "02_prime_leopold": 131.0, "03_prime_cartman1": 105.7, "04_prime_oliviaa": 130.8, "05_prime_thecoach": 108.5,
       "06_prime_jacked": 73.8, "07_prime_roshi": 86.8, "08_prime_banwavebarry": 101.5, "09_prime_scotty": 117.5, "04b_prime_oliviaa": 97.5}
ORDER = ["05_prime_thecoach", "03_prime_cartman1", "08_prime_banwavebarry", "01_prime_texas_guy", "02_prime_leopold",
         "04b_prime_oliviaa", "09_prime_scotty", "07_prime_roshi", "06_prime_jacked"]
SONGDUR = {k: librosa.get_duration(path=M + v) for k, v in TAKES.items()}
TT = {k: 60 / np.polyfit(np.arange(len(SB[v]["beats"])), SB[v]["beats"], 1)[0] for k, v in TAKES.items()}
def lines(take):
    out, cur, st = [], [], None
    for w in LY[take]:
        txt = re.sub(r"\[.*?\]\s*", "", w["w"])
        if st is None and txt.strip(): st = w["s"]
        cur.append(txt.strip())
        if "\n" in w["w"] or w is LY[take][-1]:
            tx = " ".join(x for x in cur if x)
            if tx: out.append((st, tx))
            cur, st = [], None
    return out
CANON = ["prime ads prime ads", "meta media buyers this one s for you", "prime ads the best agency accounts", "meta ad accounts to scale your q4",
         "built to stay live built to stay live", "prime ads built to stay live", "for meta media buyers only", "bigger budgets scale it up",
         "q4 is coming are you ready", "contact us now prime ads", "prime ads the best agency accounts", "meta ad accounts to scale your q4",
         "built to stay live built to stay live", "prime ads built to stay live", "contact us now prime ads"]
def phrases(take):
    """start time of each canonical phrase in this take, matched on the word stream (line splits differ between takes)."""
    W = [(re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\[.*?\]", " ", w["w"].lower())).split(), w["s"]) for w in LY[take]]
    toks = [(tok, s) for ws, s in W for tok in ws]
    out, i = [], 0
    for ph in CANON:
        p = ph.split()
        while i < len(toks) and [x for x, _ in toks[i:i + len(p)]] != p: i += 1
        if i >= len(toks): out.append(None); continue
        out.append(toks[i][1]); i += len(p)
    return out
import os
FORCE = json.loads(os.environ.get("FORCE", "{}"))   # {"clip": [Tmin, Tmax]} to test a tempo range
def octave_near(T, ref):
    return min(abs(np.log(T * m / ref)) for m in (0.5, 1, 2))
def best_grid(clip, W=6.0):
    d = P[clip]; e = env(d); t = np.arange(len(e)) / d["fps"]; dur = t[-1]
    cands = set()
    for _, T, _ in T3[clip]: cands.update(np.round(np.arange(T * 0.985, T * 1.015, 0.1), 1))
    cands.update(np.round(np.arange(AUD[clip] * 0.98, AUD[clip] * 1.02, 0.1), 1))
    cands = sorted(T for T in cands if 64 <= T <= 140)
    if clip in FORCE: cands = [T for T in np.round(np.arange(FORCE[clip][0], FORCE[clip][1], 0.1), 1)]
    best = None
    for w0 in np.arange(0.2, dur - W - 0.1, 0.25):
        m = (t >= w0) & (t < w0 + W); ee = e[m] - e[m].mean(); tt = t[m]
        for T in cands:
            bt = 60 / T; ph = np.arange(0, bt, 1 / 96)[:, None]
            if w0 + (4 * int(np.ceil(5 / (4 * bt))) + 4) * bt > dur - 0.08: continue   # whole segment (+ downbeat shift) must fit in the clip
            dd = ((tt[None, :] - ph) / bt) % 1; dd = np.minimum(dd, 1 - dd) * bt
            comb = np.exp(-0.5 * (dd / 0.05) ** 2); comb -= comb.mean(1, keepdims=True)
            c = (comb @ ee) / (np.linalg.norm(comb, axis=1) * np.linalg.norm(ee) + 1e-9)
            i = int(c.argmax()); sc = c[i] + (0.015 if octave_near(T, AUD[clip]) < 0.02 else 0)
            if best is None or sc > best[0]: best = (sc, T, float(ph[i, 0]), w0)
    sc, T, ph, w0 = best; bt = 60 / T
    n = 4 * int(np.ceil(5 / (4 * bt)))
    k0 = int(np.ceil((w0 - ph) / bt))
    E = lambda x: np.interp(x, t, e)
    strength = [E(ph + (k0 + r + 4 * np.arange(n // 4)) * bt).mean() for r in range(4)]
    for r in np.argsort(strength)[::-1]:
        B = ph + (k0 + r + np.arange(n + 1)) * bt
        if B[0] >= 0.05 and B[-1] <= dur - 0.05: break
    else:
        B = ph + (k0 + np.arange(n + 1)) * bt
    assert B[-1] <= dur, f"{clip}: segment ends after the clip"
    return dict(T=T, score=sc, beats=B, n=n)
def choose_take(T, ns_dance, start_line, last):
    opts = []
    for k, st in TT.items():
        for m in (0.5, 1, 2):
            err = abs(np.log(st / (T * m)))
            if err > 0.09: continue
            opts.append((err, k, m))
    return sorted(opts)
if __name__ == "__main__":
    cursor = 0; segs, log, plan = [], [], []
    for idx, clip in enumerate(ORDER):
        g = best_grid(clip); B = g["beats"]; c0, c1 = B[0], B[-1]; last = idx == len(ORDER) - 1
        if not last and cursor > 12: cursor = 2
        line_idx = 13 if last else cursor
        done = None
        for err, take, m in choose_take(g["T"], g["n"], line_idx, last):
            L = lines(take); sb = SB[TAKES[take]]["beats"]; PH = phrases(take)
            if PH[line_idx] is None or (last and PH[14] is None): continue
            target = PH[line_idx]
            ns = int(round(g["n"] * m))
            if last:   # end the film on the song's real ending, outro included
                jend = max(i for i, x in enumerate(sb) if x <= SONGDUR[take] - 0.3); j0 = jend - ns
                if j0 >= 0 and sb[j0] <= PH[14] - 0.2: done = (take, m, L, sb, j0, ns); break
                continue
            j0 = max(i for i, x in enumerate(sb) if x <= target + 0.08)
            if j0 + ns < len(sb) and sb[j0 + ns] < SONGDUR[take] - 0.3: done = (take, m, L, sb, j0, ns); break
        if done is None: raise SystemExit(f"no song take for {clip} at {g['T']:.1f} BPM, line {line_idx}")
        take, m, L, sb, j0, ns = done; PH = phrases(take)
        s0, s1 = sb[j0], sb[j0 + ns]
        cursor = next((i for i, s in enumerate(PH) if s is not None and i > line_idx and s >= s1 - 0.35), 15)
        v0, v1 = np.floor(c0 * FPS) / FPS, min(np.ceil(c1 * FPS) / FPS, (len(P[clip]["kp"]) - 1) / FPS)
        r = (s1 - s0) / (c1 - c0); a0, a1 = s0 - (c0 - v0) * r, s1 + (v1 - c1) * r
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a0:.4f}", "-t", f"{a1 - a0:.4f}", "-i", M + TAKES[take], "-ar", str(SR), "-ac", "2", f"raw{idx}.wav"], check=True)
        subprocess.run(["rubberband", "-3", "-q", "-D", f"{v1 - v0:.5f}", f"raw{idx}.wav", f"st{idx}.wav"], check=True, capture_output=True)
        a, _ = sf.read(f"st{idx}.wav"); N = int(round((v1 - v0) * SR))
        a = a[:N] if len(a) >= N else np.vstack([a, np.zeros((N - len(a), 2))])
        fl = int(0.006 * SR); w = np.linspace(0, 1, fl)[:, None]; a[:fl] *= w; a[-fl:] *= w[::-1]; segs.append(a)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip + ".mp4", "-vf", f"trim={v0:.5f}:{v1:.5f},setpts=PTS-STARTPTS,fps={FPS},scale=1080:1920:flags=lanczos,setsar=1",
                        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", f"v3seg{idx}.mp4"], check=True)
        lyr = " / ".join(CANON[i] for i, s in enumerate(PH) if s is not None and s0 - 0.35 <= s < s1 - 0.35)
        plan.append(dict(clip=clip, v0=v0, v1=v1, dance_beats=[float(x - v0) for x in B], T=g["T"], take=take, mult=m, a0=float(a0), a1=float(a1), r=float(r)))
        log.append(f"{clip:24s} dance {g['T']:6.1f} BPM (corr {g['score']:.2f})  {v0:5.2f}-{v1:5.2f}s  take {take} {TT[take]:.1f}{' x'+str(m) if m != 1 else ''}  stretch {1/r:.3f}  « {lyr} »")
    sf.write("music_track_v3.wav", np.vstack(segs), SR)
    json.dump(plan, open("plan_v3.json", "w"))
    open("list3.txt", "w").write("".join(f"file 'v3seg{i}.mp4'\n" for i in range(len(ORDER))))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list3.txt", "-i", "music_track_v3.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", "prime_ads_compil_v3.mp4"], check=True)
    print("\n".join(log))
