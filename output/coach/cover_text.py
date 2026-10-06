"""Hides the garbled source caption (0.5-3 s, band 57-67 % of height) under a native-style Instagram text box.
Usage: python3 cover_text.py <in.mp4> <out.mp4>"""
import sys, subprocess, json
from PIL import Image, ImageDraw, ImageFont
IN, OUT = sys.argv[1], sys.argv[2]
w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", IN], capture_output=True, text=True).stdout.strip().split(","))
k = w / 1080; f = ImageFont.truetype("../../lab/fonts/Inter.ttf", int(58 * k)); f.set_variation_by_axes([32, 650])
lines = ["POV: your media buyer", "teaches the Q4 class"]
img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
lh = int(78 * k); tw = max(d.textlength(l, font=f) for l in lines)
bw = max(tw + int(70 * k), int(0.94 * w)); y0, y1 = int(0.553 * h), int(0.705 * h); bh = y1 - y0; x0 = (w - bw) // 2
d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(26 * k), fill=(255, 255, 255, 255))
for i, l in enumerate(lines):
    d.text(((w - d.textlength(l, font=f)) / 2, y0 + (bh - lh * len(lines)) / 2 + i * lh), l, font=f, fill=(10, 10, 12, 255))
img.save("textbox.png")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", IN, "-i", "textbox.png", "-filter_complex", "[0:v][1:v]overlay=0:0:enable='between(t,0.30,3.15)'[v]",
                "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", OUT], check=True)
print("ok", w, h, "box", bw, bh)
