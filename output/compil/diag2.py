import json, numpy as np
M = json.load(open("motion.json"))
def box(x, n=4): return np.apply_along_axis(lambda c: np.convolve(c, np.ones(n)/n, "same"), 0, x)
def env_of(d):
    D = box(np.array(d["dir"]))                      # 4-frame box filter kills the 4-frame interpolation jolt
    dec = np.r_[0, np.clip(D[:-1] - D[1:], 0, None).sum(1)]   # visual impact = sudden stops / turns
    dec = dec - np.convolve(dec, np.ones(48)/48, "same")
    return np.clip(dec, 0, None)
def tempi(env, fr, lo=60, hi=170):
    x = (env - env.mean()) / (env.std() + 1e-9); n = len(x)
    ac = np.correlate(x, x, "full")[n-1:] / np.arange(n, 0, -1)
    def at(l): i = int(l); f = l - i; return ac[i]*(1-f) + ac[i+1]*f if i+1 < n//2 else 0
    res = sorted(((at(60/b*fr) + at(2*60/b*fr)/2 + at(4*60/b*fr)/4, b) for b in np.arange(lo, hi, 0.25)), reverse=True)
    out = []
    for v, b in res:
        if all(abs(b - o) > 3 for _, o in out): out.append((round(float(v), 2), float(b)))
        if len(out) == 4: break
    return out
if __name__ == "__main__":
    for k, d in M.items():
        e = env_of(d); print(f"{k:24s}", tempi(e, d["fps"]))
