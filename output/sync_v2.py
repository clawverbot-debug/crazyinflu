"""sync v2: lock a song onto the CHOREOGRAPHY's own music, beat by beat.
The source dancer moved to the source track, so its beat grid (and its bar accents) IS the rhythm of the steps.
1. track the source track's beats (prior BPM) and find its downbeat phase (strongest accent every 4 beats);
2. same on our song, from the chorus; 3. rubberband --timemap: song beat i -> source beat k0+i (exact, beat by beat);
4. cut the generated video (same timeline as the source) on those beats, >= 15 s of whole bars.
Usage: SRC_AUDIO=<wav of source, video timeline> SRC_BPM=… SONG=<mp3> SONG_BPM=… HOOK=<chorus s> python3 sync_v2.py <gen video> <out.mp4>"""
import os, sys, subprocess, numpy as np, librosa, soundfile as sf
VID, OUT = sys.argv[1], sys.argv[2]; FPS, SR = 24, 44100
def beats(path, bpm, dur=None):
    y, sr = librosa.load(path, sr=22050, duration=dur)
    oe = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    _, b = librosa.beat.beat_track(onset_envelope=oe, sr=sr, bpm=bpm, tightness=800, units="time")
    # accent per beat = low-frequency energy around the beat (kick / stomp)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)); low = S[:12].sum(0); tt = librosa.frames_to_time(np.arange(len(low)), sr=sr, hop_length=512)
    acc = np.array([low[(tt > x - 0.05) & (tt < x + 0.07)].max(initial=0) for x in b])
    return b, acc
def downbeat_phase(acc):
    return int(np.argmax([acc[r::4].mean() for r in range(4)]))
vdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", VID], capture_output=True, text=True).stdout)
ob, oacc = beats(os.environ["SRC_AUDIO"], float(os.environ["SRC_BPM"])); ob = ob[ob < vdur - 0.1]
op = downbeat_phase(oacc[:len(ob)])
sb, sacc = beats(os.environ["SONG"], float(os.environ["SONG_BPM"]))
hook = float(os.environ["HOOK"]); sp = downbeat_phase(sacc)
j0 = next(j for j in range(len(sb)) if sb[j] >= hook - 0.15 and (j - sp) % 4 == 0)   # first song downbeat at/after the chorus
N = 4 * int(np.ceil(15.0 / (4 * np.median(np.diff(ob)))))                            # whole bars, >= 15 s
starts = [k for k in range(len(ob) - N) if (k - op) % 4 == 0 and ob[k] >= 0.3]
k0 = starts[0] if starts else 0
if k0 + N >= len(ob): raise SystemExit("video too short for the bars needed")
tgt = ob[k0:k0 + N + 1] - ob[k0]; src = sb[j0:j0 + N + 1] - sb[j0]
a0 = sb[j0]; L = src[-1]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a0:.4f}", "-t", f"{L + 0.05:.4f}", "-i", os.environ["SONG"], "-ar", str(SR), "-ac", "2", "seg_src.wav"], check=True)
with open("timemap.txt", "w") as f:
    for s, t in zip(src, tgt): f.write(f"{int(round(s * SR))} {int(round(t * SR))}\n")
subprocess.run(["rubberband", "-3", "-q", "-M", "timemap.txt", "-D", f"{tgt[-1]:.5f}", "seg_src.wav", "seg_fit.wav"], check=True, capture_output=True)
v0 = ob[k0]; v1 = ob[k0 + N]
a, sr = sf.read("seg_fit.wav"); n = int(round((v1 - v0) * sr)); a = a[:n] if len(a) >= n else np.vstack([a, np.zeros((n - len(a), 2))])
fl = int(0.35 * sr); a[-fl:] *= np.linspace(1, 0, fl)[:, None]; sf.write("seg_fit.wav", a, sr)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{v0:.4f}", "-t", f"{v1 - v0:.4f}", "-i", VID, "-i", "seg_fit.wav",
                "-map", "0:v", "-map", "1:a", "-vf", f"fps={FPS},scale=1080:1920:flags=lanczos,setsar=1", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", OUT], check=True)
ratios = np.diff(tgt) / np.diff(src)
print(f"source track {60/np.median(np.diff(ob)):.1f} BPM (downbeat phase {op}), song {60/np.median(np.diff(sb)):.1f} BPM; {N} beats = {N//4} bars; "
      f"video {v0:.2f}-{v1:.2f}s ({v1-v0:.2f}s); song from {a0:.2f}s; per-beat stretch {ratios.min():.3f}-{ratios.max():.3f}")
