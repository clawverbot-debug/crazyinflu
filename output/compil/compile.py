"""Compilation of the 9 prime_* reels with the Prime Ads song, beat-locked clip by clip.
Each clip keeps its own dance; its segment is cut on whole bars of the clip's own beat (>= 5 s) and gets
the matching window of one of 3 versions of the same song (C 104 BPM, A 126 BPM, B 85 BPM), time-stretched
without pitch change (ffmpeg atempo) so the song's beats land on the clip's beats. Lyrics run on across a block.
Output: prime_ads_compil.mp4 (1080x1920, 24 fps)."""
import json, subprocess, numpy as np, librosa, soundfile as sf
M = "../../music/"
SONGS = {"C": M + "promoC_full_1.mp3", "A": M + "promoA_full_2.mp3", "B": M + "promoB_full_2.mp3"}
SB = json.load(open(M + "promo_beats.json"))
# clip, prior BPM (clip audio), song, bars, lyric target (song time where the block starts; None = continue)
PLAN = [("05_prime_thecoach", 107.7, "C", 3, 0.40), ("03_prime_cartman1", 103.4, "C", 3, None), ("08_prime_banwavebarry", 99.4, "C", 3, None),
        ("01_prime_texas_guy", 123.0, "A", 3, 23.60), ("02_prime_leopold", 136.0, "A", 3, None), ("04_prime_oliviaa", 129.2, "A", 3, None), ("09_prime_scotty", 117.5, "A", 3, None),
        ("07_prime_roshi", 86.1, "B", 2, 35.20), ("06_prime_jacked", 73.8, "B", 3, None)]
FPS, SR = 24, 48000
pos = {}
vids, auds, log = [], [], []
for i, (clip, prior, song, bars, target) in enumerate(PLAN):
    y, sr = librosa.load(clip + ".wav", sr=22050)
    _, cb = librosa.beat.beat_track(y=y, sr=sr, bpm=prior, tightness=400, units="time")
    n = 4 * bars
    b0 = next(k for k, t in enumerate(cb) if t >= 0.3)
    step = np.median(np.diff(cb))
    ext = list(cb) + [cb[-1] + step * (j + 1) for j in range(n + 2)]
    c0, c1 = round(ext[b0] * FPS) / FPS, round(ext[b0 + n] * FPS) / FPS
    sbeats = list(SB[SONGS[song].split("/")[-1]]["beats"])
    sst = np.median(np.diff(sbeats)); sbeats += [sbeats[-1] + sst * (j + 1) for j in range(16)]
    j0 = max(k for k, t in enumerate(sbeats) if t <= target - 0.02) if target is not None else pos[song]
    pos[song] = j0 + n
    s0, s1 = sbeats[j0], sbeats[j0 + n]
    f = (s1 - s0) / (c1 - c0)
    log.append(f"{clip:24s} clip {60/step:6.1f} BPM  {c0:5.2f}-{c1:5.2f}s ({c1-c0:.2f}s)  song {song} {s0:5.2f}-{s1:5.2f}  stretch x{f:.3f}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s0:.4f}", "-t", f"{s1-s0+0.3:.4f}", "-i", SONGS[song],
                    "-af", f"atempo={f:.5f}", "-ar", str(SR), "-ac", "2", f"seg{i}.wav"], check=True)
    a, _ = sf.read(f"seg{i}.wav")
    N = int(round((c1 - c0) * SR)); a = a[:N] if len(a) >= N else np.vstack([a, np.zeros((N - len(a), 2))])
    fl = int(0.008 * SR); r = np.linspace(0, 1, fl)[:, None]; a[:fl] *= r; a[-fl:] *= r[::-1]
    auds.append(a)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip + ".mp4", "-vf",
                    f"trim={c0:.4f}:{c1:.4f},setpts=PTS-STARTPTS,fps={FPS},scale=1080:1920:flags=lanczos,setsar=1",
                    "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", f"seg{i}.mp4"], check=True)
sf.write("music_track.wav", np.vstack(auds), SR)
open("list.txt", "w").write("".join(f"file 'seg{i}.mp4'\n" for i in range(len(PLAN))))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-i", "music_track.wav",
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "256k",
                "-shortest", "-movflags", "+faststart", "prime_ads_compil.mp4"], check=True)
print("\n".join(log))
