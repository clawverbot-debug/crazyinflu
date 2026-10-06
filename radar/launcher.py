#!/usr/bin/env python3
"""Radar launcher (runs on the Mac): turn approved / top radar clips into character videos with Higgsfield Genjutsu.

Each run: read the radar queue from Netlify, pick approved clips (then, in auto mode, the best new clips above
the minimum score) within the daily cap, download the source clip, run hf_mult_motion_control with the character's
HD image, save the result in output/<date>/ and mark the clip done on the radar.

Config: ~/.config/viral-spy/radar.json  {"url": "https://character-lab-research.netlify.app", "key": "<RADAR_KEY>"}
Needs: higgsfield CLI logged into the account that holds the credits, yt-dlp, ffmpeg.
Usage: python3 launcher.py [--dry-run]
"""
import datetime as dt, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = json.load(open(os.path.expanduser("~/.config/viral-spy/radar.json")))
STATE_P = f"{HERE}/launcher_state.json"
DRY = "--dry-run" in sys.argv


def characters():
    """id -> HD image path, read from the Lab archetypes in the dashboard page."""
    html = open(f"{ROOT}/dashboard/index.html").read()
    out = {}
    for m in re.finditer(r"\{id:'([a-z0-9]+)'[^}]*?img:'img/(lab_[a-z0-9]+)\.jpg'", html):
        out[m.group(1)] = f"{ROOT}/dashboard/img/hd/{m.group(2)}.jpg"
    return out


def api(method="GET", body=None):
    req = urllib.request.Request(f"{CFG['url']}/api/radar", method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "x-radar-key": CFG["key"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def sh(cmd, timeout=3600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[-400:])
    return p.stdout


def hf_upload(path):
    return json.loads(sh(["higgsfield", "upload", "create", path, "--json"]))["id"]


def main():
    today = dt.date.today().isoformat()
    state = json.load(open(STATE_P)) if os.path.exists(STATE_P) else {}
    if state.get("day") != today:
        state.update(day=today, count=0)
    state.setdefault("uploads", {})
    q = api()
    s = q["settings"]
    left = int(s.get("dailyCap", 6)) - state["count"]
    if left <= 0:
        print("daily cap reached")
        return
    approved = [c for c in q["candidates"] if c["status"] == "approved"]
    auto = [c for c in q["candidates"] if s.get("auto") and c["status"] == "new" and c["score"] >= s.get("minScore", 0)]
    todo = (approved + auto)[:left]
    chars = characters()
    rot = [c for c in s.get("characters") or ["barry"] if c in chars] or ["barry"]
    for i, c in enumerate(todo):
        ch = c.get("character") if c.get("character") in chars else rot[(state["count"] + i) % len(rot)]
        print(f"{c['id']} ({c['views']} views, score {c['score']}) -> {ch}", flush=True)
        if DRY:
            continue
        api("POST", {"action": "running", "id": c["id"], "character": ch})
        try:
            os.makedirs(f"{HERE}/src", exist_ok=True)
            raw = f"{HERE}/src/{c['id'].replace(':', '_')}.mp4"
            sh([sys.executable, "-m", "yt_dlp", "-q", "-f", "mp4/best", "-o", raw, "--force-overwrites", c["url"]], 600)
            clip = raw.replace(".mp4", "_30s.mp4")
            sh(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-t", "30", "-c", "copy", clip], 300)
            if ch not in state["uploads"]:
                state["uploads"][ch] = hf_upload(chars[ch])
            vid = hf_upload(clip)
            out = sh(["higgsfield", "generate", "create", "hf_mult_motion_control",
                      "--image-references", state["uploads"][ch], "--video-references", vid,
                      "--resolution", "720p", "--wait", "--wait-timeout", "30m", "--wait-interval", "10s", "--json"], 2400)
            urls = re.findall(r"https://[^\"\s]+\.mp4", out)
            if not urls:
                raise RuntimeError("no video url in: " + out[-300:])
            day_dir = f"{ROOT}/output/{today}"
            os.makedirs(day_dir, exist_ok=True)
            dest = f"{day_dir}/{ch}__{c['id'].replace(':', '_')}.mp4"
            urllib.request.urlretrieve(urls[-1], dest)
            api("POST", {"action": "done", "id": c["id"], "result": urls[-1]})
            state["count"] += 1
            print("  done ->", dest, flush=True)
        except Exception as e:
            api("POST", {"action": "fail", "id": c["id"], "error": str(e)[:300]})
            print("  failed:", e, flush=True)
        json.dump(state, open(STATE_P, "w"), indent=1)
    json.dump(state, open(STATE_P, "w"), indent=1)


if __name__ == "__main__":
    main()
