import json, numpy as np, librosa
M = json.load(open("motion.json"))
def norm(x): x = np.asarray(x, float); x = x - np.convolve(x, np.ones(48)/48, "same"); return np.clip(x, 0, None)
def acf_tempi(env, fr):
    x = (env - env.mean()) / (env.std() + 1e-9); n = len(x)
    ac = np.correlate(x, x, "full")[n-1:] / np.arange(n, 0, -1)
    res = []
    for bpm in np.arange(60, 181, 0.25):
        lag = 60 / bpm * fr; i = int(lag); f = lag - i
        # comb: beat lag + 2 beats + 4 beats (reinforces true period)
        v = sum((ac[int(k*lag)] * (1 - (k*lag) % 1) + ac[int(k*lag)+1] * ((k*lag) % 1)) / k for k in (1, 2, 4) if int(k*lag)+1 < n//2)
        res.append((v, bpm))
    res.sort(reverse=True); out = []
    for v, b in res:
        if all(abs(b - o) > 3 for _, o in out): out.append((round(v, 2), b))
        if len(out) == 4: break
    return out
for k, d in M.items():
    fr = d["fps"]; imp = norm(d["impact"])
    mt = acf_tempi(imp, fr)
    y, sr = librosa.load(k + ".wav", sr=22050)
    oe = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    t_oe = np.arange(len(oe)) * 512 / sr
    oe24 = np.interp(np.arange(len(imp)) / fr, t_oe, oe)
    # sync test: correlation between motion impact and audio onsets at lags -0.3..0.3 s
    a = (oe24 - oe24.mean()) / oe24.std(); m = (imp - imp.mean()) / imp.std()
    cc = [(np.mean(a[max(0, L):len(a)+min(0, L)] * m[max(0, -L):len(m)+min(0, -L)]), L/fr) for L in range(-8, 9)]
    best = max(cc)
    at = acf_tempi(norm(oe24), fr)
    print(f"{k:24s} motion {mt}\n{'':24s} audio  {at}\n{'':24s} audio↔motion corr {best[0]:.2f} at lag {best[1]:+.2f}s")
