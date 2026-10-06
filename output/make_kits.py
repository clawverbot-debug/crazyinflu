#!/usr/bin/env python3
"""Posting kit per batch (POSTING.md) from dashboard/dist/characters.json: bio, link, location, and per video the
file, slot, caption and caption variant (to compare variants later from the account pool snapshots)."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
chars = {c["id"]: c for c in json.load(open(f"{H}/../dashboard/dist/characters.json"))["characters"]}
PARIS = {"D0 14:00 UTC": "J0 · 16:00 Paris", "D0 17:00 UTC": "J0 · 19:00 Paris", "D0 21:00 UTC": "J0 · 23:00 Paris", "D1 14:00 UTC": "J1 · 16:00 Paris", "D1 21:00 UTC": "J1 · 23:00 Paris"}
for b in sorted(d for d in os.listdir(H) if d.startswith("batch")):
    plan = json.load(open(f"{H}/{b}/plan.json"))
    mb = b != "batch1"
    out = [f"# Kit de publication · {b}{' · 💼 comptes cible media buyers' if mb else ''}", "",
           "Légendes toutes différentes (variantes V1 à V6 notées pour comparer ensuite). Ne pas demander de commenter. Bio sans « AI character » ; activer l'étiquette IA d'Instagram en postant.", ""]
    for ch in dict.fromkeys(p["char"] for p in plan):
        c = chars[ch]; pre = "MB_" if mb else ""
        vids = [v for v in c["videos"] if v.get("batch", b) == b] or c["videos"]
        out += [f"## {'💼 ' if mb else ''}{c['name']} · @{c['handle']}", "", f"- Nom de profil : `{c['profile_name']}`", "- Bio :", "```", c["bio"], "```",
                f"- Lien : {c['link']}", f"- Photo de profil : `dashboard/img/pfp/hd/{ch}.jpg`", f"- Lieu à taguer : {c['location_tag']}", "",
                "| Créneau | Fichier | Variante | Légende |", "|---|---|---|---|"]
        n = 0
        for i, p in enumerate(plan):
            if p["char"] != ch: continue
            n += 1
            v = next((x for x in c["videos"] if x.get("source_clip", "").endswith(p["src"] + ".mp4")), None) or {}
            cap = (v.get("caption") or "").replace("\n", " ⏎ ")
            out.append(f"| {PARIS.get(v.get('slot'), v.get('slot', ''))} | `4k/{pre}{ch}/{pre}{ch}_{n}_4k.mp4` | {v.get('caption_variant', '')} | {cap} |")
        out.append("")
    open(f"{H}/{b}/POSTING.md", "w").write("\n".join(out))
    print(b, "kit written")
