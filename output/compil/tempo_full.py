import json, numpy as np
from scipy.ndimage import gaussian_filter1d
from kine import kinetic
P = json.load(open("pose.json"))
def env(d):
    sp, dec, _ = kinetic(d)
    e = dec - gaussian_filter1d(dec, 24); e = gaussian_filter1d(e, 0.8); return (e - e.mean()) / e.std()
def scan(d, lo=60, hi=180):
    e = env(d); fr = d["fps"]; t = np.arange(len(e)) / fr; dur = t[-1]
    res = []
    for T in np.arange(lo, hi, 0.1):
        bt = 60 / T; best = (-9, 0)
        for ph in np.arange(0, bt, 1 / 96):
            B = np.arange(ph + 0.1, dur - 0.1, bt)
            sc = np.interp(B, t, e).mean() - np.interp(B + bt / 2, t, e).mean()
            if sc > best[0]: best = (sc, ph)
        res.append((best[0], T, best[1]))
    return res
if __name__ == "__main__":
    out = {}
    for k, d in P.items():
        res = scan(d); res_s = sorted(res, reverse=True); top = []
        for sc, T, ph in res_s:
            if all(abs(T - o[1]) > 4 for o in top): top.append((round(float(sc), 2), round(float(T), 1), round(float(ph), 3)))
            if len(top) == 4: break
        out[k] = top; print(f"{k:24s}", top)
    json.dump(out, open("tempo_full.json", "w"))
