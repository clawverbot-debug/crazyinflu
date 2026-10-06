"""Album page: dashboard/dist/music/album/index.html + copies of cover, full songs and loops (served by Netlify)."""
import json, os, shutil, html
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "../../dashboard/dist/music/album")
os.makedirs(f"{OUT}/final", exist_ok=True); os.makedirs(f"{OUT}/loops", exist_ok=True)
R = sorted(json.load(open(f"{H}/release.json")), key=lambda r: r["n"])
from PIL import Image
Image.open(f"{H}/cover.png").convert("RGB").resize((1200, 1200)).save(f"{OUT}/cover.jpg", quality=88)
rows = []
for r in R:
    shutil.copy(f"{H}/{r['full']}", f"{OUT}/{r['full']}")
    loops = ""
    for key, label in (("hook", "Hook loop"), ("break", "Dance break loop")):
        if r.get(key):
            shutil.copy(f"{H}/{r[key]['file']}", f"{OUT}/{r[key]['file']}")
            loops += f'<div class="loop"><span>{label} · {r[key]["length"]:.1f} s</span><audio controls loop preload="none" src="{r[key]["file"]}"></audio><a href="{r[key]["file"]}" download>↓</a></div>'
    rows.append(f'''<li><div class="head"><b>{r["n"]:02d}</b><div><h3>{html.escape(r["title"])}</h3><p>{r["bpm"]:.0f} BPM · {int(r["duration"]//60)}:{int(r["duration"]%60):02d}</p></div></div>
<div class="loop full"><span>Full song</span><audio controls preload="none" src="{r["full"]}"></audio><a href="{r["full"]}" download>↓</a></div>{loops}</li>''')
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prime Ads Dance Album</title><meta name="robots" content="noindex">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,800..900&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#07080c;--card:#11131b;--line:#232736;--text:#f4f5f8;--muted:#9aa0b4;--cobalt:#4f74ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:32px 16px 80px}}
.hero{{display:grid;grid-template-columns:260px 1fr;gap:28px;align-items:end;margin-bottom:34px}}
.hero img{{width:100%;border-radius:18px;box-shadow:0 30px 80px rgba(31,72,255,.35)}}
.eyebrow{{color:var(--cobalt);font-weight:600;letter-spacing:.14em;text-transform:uppercase;font-size:13px}}
h1{{font-family:Archivo,sans-serif;font-stretch:70%;font-weight:900;text-transform:uppercase;font-size:clamp(44px,8vw,78px);line-height:.9;margin:8px 0 10px}}
.sub{{color:var(--muted);line-height:1.5;margin:0}}
ol{{list-style:none;padding:0;margin:0;display:grid;gap:12px}}
li{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px}}
.head{{display:flex;gap:14px;align-items:center;margin-bottom:10px}} .head b{{font-family:Archivo,sans-serif;font-stretch:70%;font-size:30px;color:var(--cobalt);width:38px}}
h3{{margin:0;font-size:19px}} .head p{{margin:2px 0 0;color:var(--muted);font-size:13px}}
.loop{{display:grid;grid-template-columns:150px 1fr 28px;gap:10px;align-items:center;margin-top:6px}}
.loop span{{font-size:13px;color:var(--muted)}} .loop.full span{{color:var(--text);font-weight:600}}
audio{{width:100%;height:36px}} .loop a{{color:var(--muted);text-decoration:none;font-size:18px;text-align:center}}
@media (max-width:640px){{.hero{{grid-template-columns:1fr}} .hero img{{max-width:320px}} .loop{{grid-template-columns:1fr 28px}} .loop span{{grid-column:1/-1}}}}
</style></head><body><main>
<section class="hero"><img src="cover.jpg" alt="Prime Ads dance album cover"><div><p class="eyebrow">The dance album</p><h1>Prime Ads<br>Built to stay live</h1>
<p class="sub">{len(R)} original tracks made to dance on. Every song has a chant hook and loops cut on whole bars, so they repeat without a jump. Loops play on repeat.</p></div></section>
<ol>{"".join(rows)}</ol></main></body></html>'''
open(f"{OUT}/index.html", "w").write(page); print("page", len(R), "tracks →", OUT)
