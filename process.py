#!/usr/bin/env python3
"""Per-video processing: duration, scene cuts, contact sheet, whisper transcript.

Usage: python3 process.py [username ...]
Outputs next to each video in data/<user>/:
  sheets/<code>.jpg   6 frames (0s, 1s, 2s, 4s, 50%, 90%) side by side
  meta/<code>.json    duration, cuts, cuts_per_sec, cut times
  transcripts/<code>.json  whisper output
"""
import json, os, re, subprocess, sys, glob, concurrent.futures as cf

ROOT = os.path.dirname(os.path.abspath(__file__))
USERS = sys.argv[1:] or sorted(os.listdir(f"{ROOT}/data"))
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(path):
    out = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout
    return float(out.strip() or 0)


def scene_cuts(path):
    err = sh(["ffmpeg", "-i", path, "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"]).stderr
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", err)]


def sheet(path, dur, out):
    tmp = out + ".d"
    os.makedirs(tmp, exist_ok=True)
    times = [0.05, 1, 2, 4, dur * 0.5, dur * 0.9]
    for i, t in enumerate(times):
        sh(["ffmpeg", "-y", "-ss", f"{min(t, max(dur - 0.1, 0)):.2f}", "-i", path, "-frames:v", "1",
            "-vf", "scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2",
            f"{tmp}/{i}.jpg"])
    sh(["ffmpeg", "-y", "-i", f"{tmp}/%d.jpg", "-vf", "tile=6x1", "-frames:v", "1", out])
    for f in glob.glob(f"{tmp}/*"):
        os.remove(f)
    os.rmdir(tmp)


def visual(path):
    d = os.path.dirname(os.path.dirname(path))
    code = os.path.basename(path)[:-4]
    for sub in ("sheets", "meta"):
        os.makedirs(f"{d}/{sub}", exist_ok=True)
    meta_p = f"{d}/meta/{code}.json"
    if os.path.exists(meta_p):
        return
    dur = duration(path)
    cuts = scene_cuts(path)
    sheet(path, dur, f"{d}/sheets/{code}.jpg")
    json.dump({"duration": round(dur, 2), "cuts": len(cuts), "cuts_per_sec": round(len(cuts) / dur, 3) if dur else 0,
               "cut_times": cuts}, open(meta_p, "w"))


def transcribe(paths):
    import whisper
    model = whisper.load_model(WHISPER_MODEL)
    for p in paths:
        d = os.path.dirname(os.path.dirname(p))
        code = os.path.basename(p)[:-4]
        os.makedirs(f"{d}/transcripts", exist_ok=True)
        out = f"{d}/transcripts/{code}.json"
        if os.path.exists(out):
            continue
        if not sh(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                   "-of", "csv=p=0", p]).stdout.strip():
            json.dump({"language": None, "text": "", "segments": [], "no_audio": True}, open(out, "w"))
            continue
        r = model.transcribe(p, fp16=False)
        json.dump({"language": r["language"], "text": r["text"].strip(),
                   "segments": [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip(),
                                 "no_speech_prob": round(s["no_speech_prob"], 2)} for s in r["segments"]]},
                  open(out, "w"), ensure_ascii=False)
        print("  tr", code, flush=True)


def main():
    vids = [v for u in USERS for v in sorted(glob.glob(f"{ROOT}/data/{u}/videos/*.mp4"))]
    print(f"{len(vids)} videos", flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(visual, vids))
    print("visual done", flush=True)
    if os.environ.get("SKIP_WHISPER") != "1":
        transcribe(vids)
    print("done", flush=True)


if __name__ == "__main__":
    main()
