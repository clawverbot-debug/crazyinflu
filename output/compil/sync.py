import json, numpy as np, librosa
from tempo3 import env, P
T3 = json.load(open("tempo3.json"))
AUD = {"01_prime_texas_guy": 122.5, "02_prime_leopold": 131.0, "03_prime_cartman1": 105.7, "04_prime_oliviaa": 130.8, "05_prime_thecoach": 108.5,
       "06_prime_jacked": 73.8, "07_prime_roshi": 86.8, "08_prime_banwavebarry": 101.5, "09_prime_scotty": 117.5}
def grid_corr(e, t, B):
    d = np.min(np.abs(t[:, None] - B[None, :]), 1); comb = np.exp(-0.5 * (d / 0.05) ** 2); return np.corrcoef(e, comb)[0, 1]
for k, d in P.items():
    e = env(d); t = np.arange(len(e)) / d["fps"]
    y, sr = librosa.load(k + ".wav", sr=22050)
    _, b = librosa.beat.beat_track(y=y, sr=sr, bpm=AUD[k], tightness=800, units="time")
    T = 60 / np.median(np.diff(b)); bt = 60 / T
    lags = np.arange(-bt / 2, bt / 2, 1 / 96)
    cs = [grid_corr(e, t, b + L) for L in lags]
    i = int(np.argmax(cs))
    print(f"{k:24s} audio {T:6.1f} BPM  corr at lag0 {grid_corr(e, t, b):.3f}  best {cs[i]:.3f} at lag {lags[i]*1000:+.0f} ms  (pose best {T3[k][0][1]} @ {T3[k][0][0]})")
