#!/usr/bin/env python3
"""Build Instagram profile-picture prompts for every Lab character (edit of its HD image, same identity).
Usage: python3 pfp.py [id ...] > prompts.json   then   python3 gen_fal.py prompts.json  -> gallery/pfp_<id>.png"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
html = open(f"{HERE}/../dashboard/index.html").read()
arch = []
block = html[html.find("const ARCH=["):html.find("const SCENES=[")]
for line in block.split("{id:'")[1:]:
    line = "id:'" + line
    g = lambda k: (re.search(k + r":'((?:[^'\\]|\\.)*)'", line) or [None, ""])[1]
    arch.append((g("id"), g("img")[4:-4], g("name"), g("en")))
BG = ["sunny yellow", "hot pink", "electric blue", "lime green", "tangerine orange", "turquoise", "violet purple", "cherry red"]
VIBE = ["laughing out loud with pure joy", "a huge proud grin, eyebrows raised", "a cheeky wink and a big smile",
        "mid-dance, shoulders up, beaming with joy", "a confident delighted smile, chin up like a winner"]
want = set(sys.argv[1:])
out = {}
for i, (cid, img, name, en) in enumerate(arch):
    if want and cid not in want:
        continue
    out[f"pfp_{cid}"] = {"ref": f"{HERE}/../dashboard/img/hd/{img}.jpg", "size": {"width": 1024, "height": 1024}, "prompt": (
        f"Turn this exact character into a square Instagram profile picture. Keep the SAME face, same nose, same eyes, same hair, "
        f"same facial hair, same body type and the same outfit: it must be instantly recognizable as the same character ({en.replace(chr(92), '')}), "
        f"with every signature trait slightly emphasized. Framing: tight portrait from mid-chest up, face large and centered, "
        f"the image must fill the whole square edge to edge (no circle, no border, no frame drawn), and everything important sits inside the central 70% because Instagram crops it round. Expression: {VIBE[i % len(VIBE)]}, "
        f"radiating good vibes and fun energy. The words \"PRIME ADS\" must be large, sharp and perfectly readable on the chest of the "
        f"outfit, high on the chest just under the chin, both words fully visible inside the central 70% of the image, never cut by the edge. Background: clean solid {BG[i % len(BG)]} studio backdrop with a soft glow. "
        f"Bright flattering light, crisp, high contrast, photorealistic (or keep the original style if the character is 3D), "
        f"reads clearly at very small size. Both hands out of frame. No other text, no logos.")}
print(json.dumps(out, indent=1))
