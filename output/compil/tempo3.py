import json, numpy as np
from scipy.ndimage import gaussian_filter1d
from kine import kinetic
P = json.load(open("pose.json"))
def env(d):
    sp, dec, _ = kinetic(d)
    e = dec - gaussian_filter1d(dec, 24)
    pat = np.array([e[i::24].mean() for i in range(24)])          # 1-s compression / chunk artifact
    e = e - pat[np.arange(len(e)) % 24]
    e = gaussian_filter1d(e, 0.8)
    return (e - e.mean()) / e.std()
def comb_scores(e, fr, lo=60, hi=180, t0=0, t1=None):
    n = len(e); t = np.arange(n) / fr; t1 = t1 or t[-1]; m = (t >= t0) & (t <= t1); ee = e[m]; tt = t[m]
    out = []
    for T in np.arange(lo, hi, 0.1):
        bt = 60 / T; best = (-1, 0)
        for ph in np.arange(0, bt, 1 / 96):
            d = ((tt - ph) / bt) % 1; d = np.minimum(d, 1 - d) * bt          # distance to nearest beat (s)
            comb = np.exp(-0.5 * (d / 0.05) ** 2)
            c = np.corrcoef(ee, comb)[0, 1]
            if c > best[0]: best = (c, ph)
        out.append((best[0], T, best[1]))
    return out
def top(res, k=4):
    o = []
    for sc, T, ph in sorted(res, reverse=True):
        if all(abs(T - x[1]) > 4 for x in o): o.append((round(float(sc), 3), round(float(T), 1), round(float(ph), 3)))
        if len(o) == k: break
    return o
if __name__ == "__main__":
    R = {}
    for k, d in P.items():
        e = env(d); R[k] = top(comb_scores(e, d["fps"])); print(f"{k:24s}", R[k], flush=True)
    json.dump(R, open("tempo3.json", "w"))
