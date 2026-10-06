"""YouTube-style subtitles (Roboto Medium, white on a 75% black box) centred in the middle of prime_ads_compil_v3.mp4.
Lyric lines come from the Suno word timings of each take, mapped through each segment's song window (a0, r)."""
import json, re, subprocess, os
from PIL import Image, ImageDraw, ImageFont
M = "../../music/"; LY = json.load(open(M + "promo_lyrics.json")); plan = json.load(open("plan_v3.json"))
W, H, FS, PADX, PADY, GAP = 1080, 1920, 56, 14, 6, 6
font = ImageFont.truetype("fonts/Roboto.ttf", FS); font.set_variation_by_axes([500, 100])
# cues = what is actually sung in the final track (ElevenLabs STT word timings of music_track_v3), not Suno's approximate alignment
STT = json.load(open("stt_v3_words.json"))
FILLER = {"oh", "hey", "yeah", "ah", "uh", "ooh", "whoa"}
FIX = [(r"\bmeta media\b", "Meta media"), (r"\bprime ads\b", "Prime Ads"), (r"\bq4\b", "Q4"), (r"\bmeta\b", "Meta")]
bounds, off = [], 0.0
for p in plan: off += p["v1"] - p["v0"]; bounds.append(off)
seg_of = lambda t: next(i for i, x in enumerate(bounds + [1e9]) if t < x)
groups, cur = [], []
for w in STT:
    if cur and (w["s"] - cur[-1]["e"] > 0.7 or cur[-1]["w"][-1] in ".?!" or len(cur) >= 8 or seg_of(w["s"]) != seg_of(cur[0]["s"])):
        groups.append(cur); cur = []
    cur.append(w)
if cur: groups.append(cur)
groups = [g for g in groups if not all(re.sub(r"[^a-z]", "", x["w"].lower()) in FILLER for x in g)]
merged = []
for g in groups:   # a lone stutter word ("Contact.") joins the next line when it follows right away
    tk = lambda x: re.sub(r"[^a-z]", "", x["w"].lower())
    lone = merged and len(merged[-1]) == 1 and seg_of(g[0]["s"]) == seg_of(merged[-1][0]["s"])
    stutter = lone and tk(g[0]) == tk(merged[-1][0]) and g[0]["s"] - merged[-1][-1]["e"] < 0.8
    dangling = lone and merged[-1][-1]["w"][-1] not in ".?!," and g[0]["s"] - merged[-1][-1]["e"] < 1.3
    if stutter or dangling: merged[-1] = merged[-1] + g
    else: merged.append(g)
cues = []
for i, g in enumerate(merged):
    text = " ".join(x["w"] for x in g if re.sub(r"[^a-z]", "", x["w"].lower()) not in FILLER).strip()
    for pat, rep in FIX: text = re.sub(pat, rep, text, flags=re.I)
    text = text[:1].upper() + text[1:]
    a = max(g[0]["s"] - 0.05, bounds[seg_of(g[0]["s"]) - 1] if seg_of(g[0]["s"]) else 0)
    b = min(g[-1]["e"] + 0.3, bounds[seg_of(g[0]["s"])])
    if i + 1 < len(merged): b = min(b, merged[i + 1][0]["s"] - 0.05)
    if text: cues.append((text, a, b))
def wrap(text, maxw=W - 140):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines = lines + [cur]
    if len(lines) == 2:   # balance: split where both lines are closest in width
        ws = text.split()
        k = min(range(1, len(ws)), key=lambda i: max(font.getlength(" ".join(ws[:i])), font.getlength(" ".join(ws[i:]))))
        lines = [" ".join(ws[:k]), " ".join(ws[k:])]
    return lines
os.makedirs("subs", exist_ok=True)
for k, (text, a, b) in enumerate(cues):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lines = wrap(text); lh = FS + 2 * PADY
    y = H // 2 - (len(lines) * lh + (len(lines) - 1) * GAP) // 2
    for ln in lines:
        tw = font.getlength(ln); x = (W - tw) / 2
        d.rounded_rectangle([x - PADX, y, x + tw + PADX, y + lh], radius=4, fill=(8, 8, 8, 191))
        d.text((x, y + PADY - 4), ln, font=font, fill=(255, 255, 255, 255))
        y += lh + GAP
    img.save(f"subs/c{k:02d}.png")
    print(f"{a:6.2f}-{b:6.2f}  {text}")
inp, f, last = ["-i", "prime_ads_compil_v3.mp4"], [], "[0:v]"
for k, (text, a, b) in enumerate(cues):
    inp += ["-i", f"subs/c{k:02d}.png"]
    f.append(f"{last}[{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{k}]"); last = f"[v{k}]"
subprocess.run(["ffmpeg", "-v", "error", "-y"] + inp + ["-filter_complex", ";".join(f), "-map", last, "-map", "0:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "prime_ads_compil_v3_subs.mp4"], check=True)
print(len(cues), "cues → prime_ads_compil_v3_subs.mp4")
