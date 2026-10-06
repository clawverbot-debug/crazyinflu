import json, numpy as np
from scipy.signal import savgol_filter, find_peaks
P = json.load(open("pose.json"))
J = [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]   # nose, shoulders, elbows, wrists, hips, knees, ankles
def kinetic(d):
    K = np.array([k if k is not None else np.full((17, 3), np.nan) for k in d["kp"]], float)
    xy, c = K[:, J, :2], K[:, J, 2]
    xy[c < 0.3] = np.nan
    for j in range(xy.shape[1]):               # fill gaps
        for a in range(2):
            v = xy[:, j, a]; ok = ~np.isnan(v)
            xy[:, j, a] = np.interp(np.arange(len(v)), np.where(ok)[0], v[ok]) if ok.sum() > 5 else 0
    scale = np.nanmedian(np.linalg.norm(K[:, 5, :2] - K[:, 11, :2], axis=1)) or 100   # shoulder-hip length
    xy = savgol_filter(xy / scale, 7, 2, axis=0)  # smooths the 4-frame interpolation jolt
    sp = np.linalg.norm(np.diff(xy, axis=0), axis=2).mean(1) * d["fps"]   # mean joint speed (body lengths / s)
    sp = np.r_[sp[0], sp]
    dec = np.r_[0, np.clip(sp[:-1] - sp[1:], 0, None)]                     # deceleration = hit
    hipy = savgol_filter(xy[:, [7, 8], 1].mean(1), 7, 2)
    return sp, dec, hipy
def tempi(env, fr, lo=60, hi=170):
    x = env - np.convolve(env, np.ones(48)/48, "same"); x = (x - x.mean()) / (x.std() + 1e-9); n = len(x)
    ac = np.correlate(x, x, "full")[n-1:] / np.arange(n, 0, -1)
    def at(l): i = int(l); f = l - i; return ac[i]*(1-f) + ac[i+1]*f if i+1 < n//2 else 0
    res = sorted(((at(60/b*fr) + at(2*60/b*fr)/2 + at(4*60/b*fr)/4, b) for b in np.arange(lo, hi, 0.25)), reverse=True)
    out = []
    for v, b in res:
        if all(abs(b - o) > 3 for _, o in out): out.append((round(float(v), 2), float(b)))
        if len(out) == 4: break
    return out
if __name__ == "__main__":
    for k, d in P.items():
        sp, dec, hipy = kinetic(d)
        print(f"{k:24s} dec {tempi(dec, d['fps'])}\n{'':24s} hip {tempi(np.abs(np.gradient(hipy)), d['fps'])}  speed {np.median(sp):.2f}")
