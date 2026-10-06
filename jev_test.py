#!/usr/bin/env python3
"""Shadow test of Jev on decisions already made by hand in batch 1:
 A) copy / watch / skip for the 132 kept sources (text + metadata only, no frames) vs the 50 picked by eye
 B) best character among the 10 batch-1 characters for each picked source vs the manual assignment."""
import json, os, time, urllib.request, concurrent.futures as cf
KEY = open(os.path.expanduser("~/.config/viral-spy/typesafe_key")).read().strip()
def ask(state, questions):
    body = json.dumps({"state": state, "model": "jev-latest", "questions": questions}).encode()
    for i in range(3):
        try:
            r = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            t = time.time(); d = json.load(urllib.request.urlopen(r, timeout=30)); d["_ms"] = int((time.time() - t) * 1000); return d
        except Exception as e: err = str(e); time.sleep(2)
    return {"error": err}
items = json.load(open("analysis/live_sources.json"))["items"]
plan = json.load(open("output/batch1/plan.json"))
picked = {p["src"]: p["char"] for p in plan}
chars = {c["id"]: c for c in json.load(open("dashboard/dist/characters.json"))["characters"]}
Q_A = {
 "decision": {"type": "choice", "instructions": "We turn real viral phone videos into AI-character videos by motion transfer (the main person is replaced by a caricature that does the same moves). Should we copy this clip now?",
   "criteria": {"copy_now": "Fresh, already viral or rising fast, one real person clearly dancing or moving in a fun way, full body, no heavy text, not an AI or cartoon video", "watch": "Promising but not proven yet, or unclear content", "skip": "Talking, static, crowd with no main person, AI/cartoon, edited montage, or weak numbers"}},
 "solo": {"type": "noul", "instructions": "Is there likely one real person clearly visible and dancing or moving for most of the clip?"},
}
def stA(c):
    return {k: c.get(k) for k in ["platform", "owner", "views", "likes", "shares", "comments", "ageH", "vph", "duration", "caption", "sound", "scene", "bucket"]}
def runA(c):
    return c["id"], ask(stA(c), Q_A)
with cf.ThreadPoolExecutor(8) as ex: resA = dict(ex.map(runA, items))
crit = {cid: f"{chars[cid]['name']}: {chars[cid]['tagline']['en']}; {chars[cid]['role']}; traits {chars[cid]['traits'].get('outfit')}, {chars[cid]['traits'].get('body')}; target media buyers={chars[cid]['flags']['media_buyer']}" for cid in dict.fromkeys(picked.values())}
Q_B = {"character": {"type": "choice", "instructions": "Which AI character fits this source scene best? Business scenes (office, conference, luxury car, jet, Dubai) go to media-buyer characters; beach and travel scenes to nomads; weddings and parties to the most extravagant looks.", "criteria": crit}}
src = {c["id"]: c for c in items}
def runB(s):
    return s, ask(stA(src[s]), Q_B)
with cf.ThreadPoolExecutor(8) as ex: resB = dict(ex.map(runB, [s for s in picked if s in src]))
json.dump({"A": resA, "B": resB}, open("analysis/jev_test.json", "w"), indent=1)
# report
ms = [r["_ms"] for r in list(resA.values()) + list(resB.values()) if "_ms" in r]
errs = sum(1 for r in list(resA.values()) + list(resB.values()) if "error" in r)
print(f"calls {len(ms)} ok, {errs} errors, median {sorted(ms)[len(ms)//2]} ms, max {max(ms)} ms")
rows = []
for cid, r in resA.items():
    if "answers" not in r: continue
    a = r["answers"]; rows.append((cid in picked, a["decision"]["choice"], a["decision"].get("probabilities", {}).get("copy_now", 0), a["solo"]["noul"]))
import statistics as st
for lab, sel in (("picked by eye", True), ("not picked", False)):
    g = [x for x in rows if x[0] == sel]
    print(f"{lab:14} n={len(g):3}  copy_now={sum(1 for x in g if x[1]=='copy_now'):3}  watch={sum(1 for x in g if x[1]=='watch'):3}  skip={sum(1 for x in g if x[1]=='skip'):3}  mean P(copy)={st.mean(x[2] for x in g):.2f}  mean P(solo)={st.mean(x[3] for x in g):.2f}")
# ranking quality: top-50 by P(copy) vs picked
top = sorted(rows, key=lambda x: -x[2])[:50]
print("overlap of Jev top-50 with the 50 picked:", sum(1 for x in top if x[0]))
agree = [(picked[s], r["answers"]["character"]["choice"], r["answers"]["character"].get("confidence")) for s, r in resB.items() if "answers" in r]
print(f"character match: {sum(1 for a,b,_ in agree if a==b)}/{len(agree)} same as manual; chance = {len(agree)//10}/{len(agree)}")
from collections import Counter
print("Jev character picks:", Counter(b for _,b,_ in agree).most_common())
