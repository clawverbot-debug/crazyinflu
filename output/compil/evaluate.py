"""Beat-on-move score: music beats detected independently (librosa) in the final track, compared with the dancer's kinetic hits.
hit% = share of music beats within ±60 ms of a motion hit (peak of the deceleration envelope); 'on-beat' = mean z of the hit
envelope at the music beats (0 = random, higher = beats land on moves)."""
import json, numpy as np, librosa
from scipy.signal import find_peaks
from tempo3 import env, P
def score(clip, v0, v1, track, t_off):
    e = env(P[clip]); fr = P[clip]["fps"]; t = np.arange(len(e)) / fr
    pk, _ = find_peaks(e, height=0.3, distance=int(fr * 0.25)); hits = t[pk]
    y, sr = librosa.load(track, sr=22050, offset=t_off, duration=v1 - v0)
    _, mb = librosa.beat.beat_track(y=y, sr=sr, units="time", tightness=400)
    mb = mb[(mb > 0.15) & (mb < v1 - v0 - 0.15)] + v0
    if not len(mb): return None
    d = np.array([np.min(np.abs(hits - b)) for b in mb]) if len(hits) else np.full(len(mb), 9)
    on = np.interp(mb, t, e).mean()
    rnd = np.mean([np.interp(mb + np.random.uniform(-0.5, 0.5), t, e).mean() for _ in range(200)])
    return 100 * np.mean(d <= 0.06), on, rnd
def run(segs, track, name):
    off, rows = 0.0, []
    for clip, v0, v1 in segs:
        r = score(clip, v0, v1, track, off); off += v1 - v0
        if r: rows.append(r); print(f"  {clip:22s} hit {r[0]:5.1f}%   on-beat {r[1]:+.2f} (random {r[2]:+.2f})")
    a = np.array(rows); print(f"{name}: hit {a[:,0].mean():.1f}%   on-beat {a[:,1].mean():+.2f}   random {a[:,2].mean():+.2f}\n")
V1 = [("05_prime_thecoach", 3.08, 9.75), ("03_prime_cartman1", 0.67, 7.58), ("08_prime_banwavebarry", 0.67, 7.88), ("01_prime_texas_guy", 0.58, 6.46),
      ("02_prime_leopold", 0.46, 5.83), ("04_prime_oliviaa", 0.50, 5.88), ("09_prime_scotty", 0.54, 6.54), ("07_prime_roshi", 1.08, 6.75), ("06_prime_jacked", 0.96, 10.62)]
print("v1 (old: beat taken from the reel audio)"); run(V1, "music_track.wav", "v1")
print("v3 (new: beat taken from the dancer's body)"); run([(p["clip"], p["v0"], p["v1"]) for p in json.load(open("plan_v3.json"))], "music_track_v3.wav", "v3")
