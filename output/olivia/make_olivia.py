"""Olivia x 'Q4 Season': the song is locked on her dance (pose hits), starting on the chorus, >= 15 s of whole bars.
Usage: python3 make_olivia.py <video to cut (480p or 4K, same timing)> <output.mp4>"""
import json, sys, subprocess, numpy as np, librosa, soundfile as sf
from tempo3 import env, P
VID, OUT = sys.argv[1], sys.argv[2]
import os; SCALE = os.environ.get("SCALE", "1080:1920")
SONG = "../../music/album/final/04_q4_season.mp3"; REL = {r["n"]: r for r in json.load(open("../../music/album/release.json"))}[4]
e = env(P["gen_olivia"]); fr = P["gen_olivia"]["fps"]; t = np.arange(len(e)) / fr; dur = t[-1]
best = None
for T in np.arange(105.0 * 0.97, 105.0 * 1.03, 0.1):
    bt = 60 / T; n = 4 * int(np.ceil(15 / (4 * bt))); ph = np.arange(0, bt, 1 / 96)[:, None]
    for w0 in np.arange(0.0, dur - (n + 1) * bt - 0.05, 0.125):
        m = (t >= w0) & (t < w0 + n * bt); ee = e[m] - e[m].mean(); tt = t[m]
        dd = ((tt[None, :] - ph) / bt) % 1; dd = np.minimum(dd, 1 - dd) * bt
        cb = np.exp(-0.5 * (dd / 0.05) ** 2); cb -= cb.mean(1, keepdims=True)
        c = (cb @ ee) / (np.linalg.norm(cb, axis=1) * np.linalg.norm(ee) + 1e-9); i = int(c.argmax())
        if best is None or c[i] > best[0]: best = (float(c[i]), T, float(ph[i, 0]), w0, n)
sc, T, ph, w0, n = best; bt = 60 / T; k0 = int(np.ceil((w0 - ph) / bt))
E = lambda x: np.interp(x, t, e)
r = max((r for r in range(4) if ph + (k0 + r + n) * bt <= dur - 0.05), key=lambda r: E(ph + (k0 + r + 4 * np.arange(n // 4)) * bt).mean())
B = ph + (k0 + r + np.arange(n + 1)) * bt; c0, c1 = B[0], B[-1]
y, sr = librosa.load(SONG, sr=22050); _, sb = librosa.beat.beat_track(y=y, sr=sr, start_bpm=105, tightness=400, units="time")
j0 = int(np.argmin(np.abs(sb - REL["hook"]["start"]))); s0, s1 = sb[j0], sb[j0 + n]
FPS = 24; v0, v1 = np.floor(c0 * FPS) / FPS, np.ceil(c1 * FPS) / FPS
rr = (s1 - s0) / (c1 - c0); a0, a1 = s0 - (c0 - v0) * rr, s1 + (v1 - c1) * rr
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a0:.4f}", "-t", f"{a1 - a0:.4f}", "-i", SONG, "-ar", "48000", "-ac", "2", "song_raw.wav"], check=True)
subprocess.run(["rubberband", "-3", "-q", "-D", f"{v1 - v0:.5f}", "song_raw.wav", "song_fit.wav"], check=True, capture_output=True)
a, srr = sf.read("song_fit.wav"); N = int(round((v1 - v0) * srr)); a = a[:N] if len(a) >= N else np.vstack([a, np.zeros((N - len(a), 2))])
fl = int(0.4 * srr); a[-fl:] *= np.linspace(1, 0, fl)[:, None]; a[:int(0.005 * srr)] *= np.linspace(0, 1, int(0.005 * srr))[:, None]
sf.write("song_fit.wav", a, srr)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", VID, "-i", "song_fit.wav", "-filter_complex", f"[0:v]trim={v0:.5f}:{v1:.5f},setpts=PTS-STARTPTS,fps={FPS},scale={SCALE}:flags=lanczos,setsar=1[v]",
                "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart", "-shortest", OUT], check=True)
print(f"dance {T:.1f} BPM (corr {sc:.2f}), cut {v0:.2f}-{v1:.2f}s ({v1 - v0:.2f}s), song from {s0:.2f}s (chorus), stretch {1 / rr:.3f}")
