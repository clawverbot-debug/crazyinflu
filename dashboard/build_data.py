#!/usr/bin/env python3
"""Build dashboard/data.json from every analysis output + the live spy database.

Run by hand or at the end of each spy tick (spy.py calls it). Pure local work, no Apify calls.
"""
import glob, collections, json, os, re, sqlite3, statistics as st, datetime as dt
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEEDS = ["abu.shalab", "dahab.daddy", "haroldpuddington", "abu.yalla"]

# same source clip, different character (checked by eye on the contact sheets)
SHARED_SOURCES = [
    {"scene": "Dîner, fenêtres en arc", "scene_en": "Dinner party, arched windows", "items": [("abu.shalab", "Dd4WBQrt48X"), ("dahab.daddy", "Dd_qcXdgsdb"),
                                                  ("abu.yalla", "Dd62X7dJbCD")]},
    {"scene": "Selfie devant le Burj Khalifa", "scene_en": "Selfie in front of the Burj Khalifa", "items": [("abu.shalab", "DdxCLS5NMRz"), ("dahab.daddy", "DdzgbbAR4VM")]},
    {"scene": "Micro-voiture sur l'autoroute", "scene_en": "Micro car on the highway", "items": [("abu.shalab", "DeCCJ4fNAvB"), ("dahab.daddy", "Dd8iR7XAS9H")]},
]
HITS_FLOPS = [
    ("haroldpuddington", "Dd8vDnQxKt_", "hit", "Piste de danse d'un mariage, foule autour", "Wedding dance floor, crowd around"),
    ("dahab.daddy", "Dd_qcXdgsdb", "hit", "Danse au dîner, invités qui tapent des mains", "Dancing at a dinner, guests clapping"),
    ("abu.shalab", "DdxCLS5NMRz", "hit", "Selfie qui part en danse devant le Burj", "Selfie turning into a dance at the Burj"),
    ("haroldpuddington", "DeGEgEBAdZD", "flop", "Selfie statique en voiture, il chante", "Static car selfie, singing"),
    ("dahab.daddy", "DeE5JStg3Ni", "flop", "Personnage minuscule, loin dans l'image", "Tiny character, far away in the frame"),
    ("abu.shalab", "DeFRf5RqU4I", "flop", "Post « merci pour 500k »", "Thank-you-for-500k post"),
]
# algo tricks, ranked (analysis/algo_tricks_research.md, tested against our scrape)
TRICKS = [
    {"v": "no", "label": "CONTREDIT", "label_en": "CONTRADICTED", "trick_en": "Upload without music, add it inside Instagram",
     "evidence_en": "No official source says it boosts reach. A recognized track inside the file gets the same audio page. Our data: 1.00x vs 1.07x, mixed account by account. Only real reason: copyright muting.",
     "trick": "Poster sans musique et l'ajouter dans Instagram",
     "evidence": "Aucune source officielle ne dit que ça booste. Un titre reconnu dans le fichier a la même page audio. Nos données : 1,00× contre 1,07×, partagé selon les comptes. Seule vraie raison : éviter la coupure pour droits d'auteur."},
    {"v": "ok", "label": "OBSERVÉ", "label_en": "OBSERVED", "trick_en": "Burst variants and repost winners", "evidence_en": "dahab.daddy: 14 posts less than 5 min apart. A quick repost works once (23.3M to 12.9M), then collapses (50k).",
     "trick": "Rafales de variantes et repost des gagnants",
     "evidence": "dahab.daddy : 14 posts à moins de 5 min d'écart. Le repost rapproché marche une fois (23,3 M → 12,9 M), puis s'effondre (50k)."},
    {"v": "ok", "label": "VÉRIFIÉ", "label_en": "VERIFIED", "trick_en": "Flops and reposts pulled off the grid", "evidence_en": "Verified: on 6 accounts with a full grid, visible reels median 1.3M, the 28 hidden reels 50k. Only one true deletion (Abu Shalab, \"thank you 500k\" post).",
     "trick": "Flops et reposts sortis de la grille",
     "evidence": "Vérifié : sur 6 comptes à grille complète, les réels visibles font 1,3 M de médiane, les 28 réels cachés 50k. Une seule vraie suppression (Abu Shalab, post « merci 500k »)."},
    {"v": "ok", "label": "PROBABLE", "label_en": "LIKELY", "trick_en": "Network of accounts sharing scenes", "evidence_en": "Same source clips across accounts; abu.yalla reuses abu.shalab's bio and a caption.",
     "trick": "Réseau de comptes qui se partagent les scènes",
     "evidence": "Mêmes vidéos sources d'un compte à l'autre ; abu.yalla reprend la bio et une légende d'abu.shalab."},
    {"v": "q", "label": "POSSIBLE", "label_en": "POSSIBLE", "trick_en": "Trial Reels (shown to non-followers first)", "evidence_en": "Impossible at launch (follower threshold), plausible since Oct 3-4.",
     "trick": "Trial Reels (montrés d'abord aux non-abonnés)",
     "evidence": "Impossible au lancement (seuil d'abonnés), plausible depuis le 3–4 oct."},
    {"v": "q", "label": "NEUTRE", "label_en": "NEUTRAL", "trick_en": "No hashtags, original audio", "evidence_en": "Observed, but no measurable effect on views across 2,593 videos.",
     "trick": "Pas de hashtag, audio original",
     "evidence": "Observé, mais sans effet mesurable sur les vues sur 2 593 vidéos."},
    {"v": "q", "label": "INCONNU", "label_en": "UNKNOWN", "trick_en": "Avoiding the AI label", "evidence_en": "Counter-productive since Aug 31: an unlabeled account may stop being recommended.",
     "trick": "Éviter le label « IA »",
     "evidence": "Contre-productif depuis le 31 août : un compte non labellisé risque de ne plus être recommandé."},
    {"v": "q", "label": "AUCUN INDICE", "label_en": "NO SIGN", "trick_en": "Paid Meta boost on first posts", "evidence_en": "To check in the Meta Ad Library.",
     "trick": "Boost payant Meta sur les premiers posts",
     "evidence": "À vérifier dans la Bibliothèque publicitaire de Meta."},
    {"v": "no", "label": "CONTREDIT", "label_en": "CONTRADICTED", "trick_en": "Warming up an account, aged accounts", "evidence_en": "Abu's TikTok was created 2.5 h before its first video (716k views). dahab's and Harold's old TikToks fail.",
     "trick": "Préchauffer un compte, compte vieilli",
     "evidence": "Le TikTok d'Abu a été créé 2 h 30 avant sa 1re vidéo (716k vues). Les vieux TikTok de dahab et Harold échouent."},
    {"v": "no", "label": "CONTREDIT", "label_en": "CONTRADICTED", "trick_en": "Buying views, likes or comments", "evidence_en": "Likes/views between 0.3 and 3.5%, no outlier. No comment burst in the first 30 minutes.",
     "trick": "Achat de vues, likes ou commentaires",
     "evidence": "Likes/vues entre 0,3 et 3,5 %, sans valeur aberrante. Pas de rafale de commentaires dans les 30 premières minutes."},
    {"v": "no", "label": "CONTREDIT", "label_en": "CONTRADICTED", "trick_en": "Pods, powerlike and comment groups", "evidence_en": "Only 6 of 1,320 commenters shared across accounts, in 15 languages.",
     "trick": "Pods, groupes de powerlike et de commentaires",
     "evidence": "Seulement 6 commentateurs sur 1 320 en commun entre comptes, en 15 langues. L'espionnage live continue de vérifier."},
]
GENERIC = re.compile(r"^[\W_\s]*$|^(nice|wow|lol|haha+|love|amazing|great|cool|fire|so good|omg)[\W\s]*$", re.I)


def frame(user, code, out, col=2):
    """Crop one frame of a contact sheet into dashboard/img (published next to the page)."""
    src = f"{ROOT}/data/{user}/sheets/{code}.jpg"
    if not os.path.exists(src):
        return None
    os.makedirs(f"{HERE}/img", exist_ok=True)
    if not os.path.exists(f"{HERE}/img/{out}"):
        im = Image.open(src)
        w = im.width // 6
        im.crop((col * w, 0, (col + 1) * w, im.height)).save(f"{HERE}/img/{out}", quality=78)
    return f"img/{out}"


def seed_reels():
    out = {}
    for u in SEEDS:
        p = f"{ROOT}/data/{u}/reels.json"
        if os.path.exists(p):
            for r in json.load(open(p)):
                if r["ownerUsername"] == u:
                    out[r["shortCode"]] = r
    return out


def seeds_block(reels):
    rows = []
    for u in SEEDS:
        prof = json.load(open(f"{ROOT}/data/{u}/profile.json"))
        R = [r for r in reels.values() if r["ownerUsername"] == u]
        v = sorted((r.get("videoPlayCount") or 0 for r in R), reverse=True)
        ts = sorted(r["timestamp"] for r in R)
        days = max((dt.datetime.fromisoformat(ts[-1][:19]) - dt.datetime.fromisoformat(ts[0][:19])).days, 1)
        rows.append({"handle": u, "followers": prof["followersCount"], "posts_profile": prof.get("postsCount"),
                     "reels": len(R), "first_post": ts[0][:10], "per_day": round(len(R) / days, 1),
                     "median_views": int(st.median(v)), "max_views": v[0],
                     "bio": prof.get("biography", ""), "link": prof.get("externalUrl")})
    return rows


def accounts_block():
    p = f"{ROOT}/analysis/accounts.json"
    if not os.path.exists(p):
        return [], {}
    d = json.load(open(p))
    keep = ["platform", "handle", "category", "note", "followers", "median_views", "max_views", "posts_per_day",
            "median_duration_s", "pct_original_sound", "median_views_per_follower", "hit_rate_1M", "url", "new_badge"]
    rows = [{k: a.get(k) for k in keep} for a in d["accounts"]]
    # does packaging matter? views relative to the account's own median, by bucket
    rel = collections.defaultdict(list)
    for vs in d["videos"].values():
        vv = [v["views"] for v in vs if v["views"]]
        if len(vv) < 5:
            continue
        m = st.median(vv)
        for v in vs:
            if not v["views"] or not v["duration"]:
                continue
            dur = float(v["duration"])
            b = "≤12 s" if dur <= 12 else "12–20 s" if dur <= 20 else "20–60 s" if dur <= 60 else "> 60 s"
            rel[("Durée", b)].append(v["views"] / m)
            rel[("Son", "original" if v["original_sound"] else "tendance")].append(v["views"] / m)
            w = len((v["caption"] or "").split())
            rel[("Légende", "0–3 mots" if w <= 3 else "4–15 mots" if w <= 15 else "> 15 mots")].append(v["views"] / m)
    packaging = [{"factor": f, "bucket": b, "n": len(x), "rel": round(st.median(x), 2)} for (f, b), x in rel.items()]
    packaging.sort(key=lambda r: (r["factor"], r["bucket"]))
    return rows, {"packaging": packaging, "videos": sum(len(v) for v in d["videos"].values())}


def sources_block(reels):
    out = []
    for s in SHARED_SOURCES:
        items = []
        for u, code in s["items"]:
            r = reels.get(code)
            if r:
                items.append({"handle": u, "code": code, "date": r["timestamp"][:10],
                              "views": r.get("videoPlayCount") or 0, "img": frame(u, code, f"src_{code}.jpg"),
                              "url": r["url"]})
        out.append({"scene": s["scene"], "scene_en": s.get("scene_en"), "items": sorted(items, key=lambda i: i["date"])})
    return out


def hitflop_block(reels):
    out = []
    for u, code, kind, why, why_en in HITS_FLOPS:
        r = reels.get(code)
        if r:
            out.append({"handle": u, "kind": kind, "why": why, "why_en": why_en, "views": r.get("videoPlayCount") or 0,
                        "img": frame(u, code, f"hf_{code}.jpg"), "url": r["url"]})
    return out


def motion_sources():
    p = f"{ROOT}/analysis/motion_sources.csv"
    if not os.path.exists(p):
        return []
    import csv
    return [{"platform": r["platform"], "handle": r["handle"], "followers": int(r["followers"] or 0),
             "note": r["note"], "url": r["url"]} for r in csv.DictReader(open(p))]


def spy_block():
    p = f"{ROOT}/spy/spy.db"
    cfg = json.load(open(f"{ROOT}/spy/config.json"))
    if not os.path.exists(p):
        return {"watchlist": cfg["watchlist"], "posts": [], "events": []}
    c = sqlite3.connect(p)
    posts = []
    for code, acc, posted, caption, url in c.execute(
            "SELECT code, account, posted_at, caption, url FROM posts ORDER BY posted_at DESC LIMIT 60"):
        snaps = [{"age": a, "views": v, "likes": l, "comments": cm} for a, v, l, cm in
                 c.execute("SELECT age_min, views, likes, comments FROM snaps WHERE code=? ORDER BY age_min", (code,))]
        com = [{"user": u, "text": t, "at": at} for u, t, at in
               c.execute("SELECT username, text, created_at FROM comments WHERE code=?", (code,))]
        generic = sum(1 for x in com if GENERIC.match(x["text"] or ""))
        posts.append({"code": code, "account": acc, "posted_at": posted, "caption": (caption or "")[:80], "url": url,
                      "snaps": snaps, "comments_captured": len(com),
                      "generic_comment_pct": round(generic / len(com), 2) if com else None})
    # commenters seen under several watched accounts = possible engagement group
    who = collections.defaultdict(set)
    for u, acc in c.execute("SELECT c.username, p.account FROM comments c JOIN posts p ON p.code=c.code"):
        who[u].add(acc)
    overlap = sorted(([u, sorted(a)] for u, a in who.items() if len(a) >= 2), key=lambda x: -len(x[1]))[:30]
    events = [{"ts": t, "account": a, "code": cd, "kind": k, "detail": d} for t, a, cd, k, d in
              c.execute("SELECT * FROM events WHERE kind!='backfill' ORDER BY ts DESC LIMIT 80")]
    spend = [{"day": d, "usd": round(u, 2)} for d, u in c.execute("SELECT day, usd FROM spend ORDER BY day")]
    last = c.execute("SELECT max(last_check) FROM checks").fetchone()[0]
    return {"watchlist": cfg["watchlist"], "end_date": cfg["end_date"], "posts": posts, "events": events,
            "commenter_overlap": overlap, "commenters_total": len(who), "spend": spend, "last_check": last,
            "daily_budget": cfg["daily_budget_usd"]}


WAVE = ["jean_philanthrope", "benjamin_stachio", "don_nuger", "sebastianperfill", "edmond_lebon", "mr_twirlo",
        "abu.shalab", "abu.yalla", "dahab.daddy", "haroldpuddington", "monique.liconique"]


def honeymoon_block(reels):
    """Views by account age (days since its first reel) at posting time, posts exposed >= ~2 days."""
    allr = list(reels.values())
    p = f"{ROOT}/pool/deep_ig.json"
    if os.path.exists(p):
        allr += [r for r in json.load(open(p)) if r.get("shortCode") not in reels]
    T = lambda r: dt.datetime.fromisoformat(r["timestamp"][:19])
    cut = dt.datetime(2026, 10, 3, 12)
    by = collections.defaultdict(list)
    for u in WAVE:
        ru = sorted((r for r in allr if r.get("ownerUsername") == u), key=T)
        if not ru:
            continue
        birth = T(ru[0])
        for r in ru:
            if T(r) <= cut:
                d = (T(r) - birth).days
                by["J" + str(d) if d <= 5 else "J6+"].append(r.get("videoPlayCount") or 0)
    order = ["J0", "J1", "J2", "J3", "J4", "J5", "J6+"]
    return [{"day": k, "n": len(by[k]), "median": int(st.median(by[k])),
             "over1m": sum(v >= 1e6 for v in by[k])} for k in order if by[k]]


def wave_block(reels):
    """The whole Jean Phil wave: per account birth, cadence, day 0-3 vs day 4+ medians."""
    allr = list(reels.values())
    p = f"{ROOT}/pool/deep_ig.json"
    if os.path.exists(p):
        allr += [r for r in json.load(open(p)) if r.get("shortCode") not in reels]
    fol = {a["handle"]: a["followers"] for a in json.load(open(f"{ROOT}/analysis/accounts.json"))["accounts"]
           if a["platform"] == "instagram"}
    T = lambda r: dt.datetime.fromisoformat(r["timestamp"][:19])
    cut = dt.datetime(2026, 10, 3, 12)
    rows = []
    for u in WAVE:
        ru = sorted((r for r in allr if r.get("ownerUsername") == u), key=T)
        if not ru:
            continue
        birth = T(ru[0])
        v = [r.get("videoPlayCount") or 0 for r in ru]
        early = [r.get("videoPlayCount") or 0 for r in ru if (T(r) - birth).days <= 3 and T(r) <= cut]
        late = [r.get("videoPlayCount") or 0 for r in ru if (T(r) - birth).days > 3 and T(r) <= cut]
        span = max((T(ru[-1]) - birth).total_seconds() / 86400, 1)
        rows.append({"handle": u, "followers": fol.get(u), "birth": birth.date().isoformat(), "reels": len(ru),
                     "per_day": round(len(ru) / span, 1), "max_views": max(v),
                     "early": int(st.median(early)) if early else None, "late": int(st.median(late)) if late else None})
    return sorted(rows, key=lambda r: r["birth"])


VERIFIED_SCENES = {  # cross-account clusters checked by eye (analysis/scene_clusters.jpg), index in that list
    0: ("Selfie devant le Burj Khalifa", "Selfie at the Burj Khalifa"),
    1: ("Scène de concert, la nuit", "Night concert stage"),
    3: ("Dîner, fenêtres en arc", "Dinner party, arched windows"),
    4: ("Micro-voiture sur l'autoroute", "Micro car on the highway"),
    5: ("Scène violette, public", "Purple stage, audience"),
    6: ("Piscine", "Swimming pool"),
    8: ("Intérieur de voiture", "Inside a car"),
    9: ("Voiture-jouet rose, désert", "Pink toy car, desert"),
}


def scenes_block():
    p = f"{ROOT}/analysis/scene_clusters.json"
    if not os.path.exists(p):
        return []
    cross = [c for c in json.load(open(p)) if len(c["accounts"]) > 1]
    out = []
    for i, (fr, en) in VERIFIED_SCENES.items():
        if i >= len(cross):
            continue
        items = []
        seen = set()
        for x in cross[i]["items"]:
            u, code = x["key"].split("/")
            items.append({"handle": u, "views": x["views"], "date": x["date"][:10], "repost": u in seen,
                          "img": frame(u, code, f"sc_{code}.jpg")})
            seen.add(u)
        orig = items[0]["views"] or 1
        copies = [it["views"] for it in items[1:] if it["handle"] != items[0]["handle"]]
        out.append({"scene": fr, "scene_en": en, "items": items,
                    "copy_ratio": round(st.median(copies) / orig, 3) if copies else None})
    return out


def traits_block():
    p = f"{ROOT}/analysis/visual/traits_recent.json"
    if not os.path.exists(p):
        return []
    rows = json.load(open(p))
    med = lambda xs: int(st.median(xs)) if xs else None
    tests = [
        ("Moustache", "Mustache", lambda r: r["facial_hair"] == "mustache", lambda r: r["facial_hair"] in ("none", "beard")),
        ("Foule qui réagit", "Crowd reacting", lambda r: r["crowd_reacting"] is True, lambda r: r["crowd_reacting"] is False),
        ("Nez long ou gros", "Long or big nose", lambda r: r["nose"] in ("long", "big"), lambda r: r["nose"] in ("normal", "button")),
        ("Petits yeux", "Small eyes", lambda r: r["eyes"] == "small", lambda r: r["eyes"] in ("big cartoon", "normal")),
        ("Exagération 3/3", "Exaggeration 3/3", lambda r: r["exaggeration"] == 3, lambda r: r["exaggeration"] in (0, 1)),
        ("Mariage, fête, scène, rue", "Wedding, party, stage, street", lambda r: r["setting"] in ("party_wedding", "stage_concert", "street_tourist", "real_amateur_footage"), lambda r: r["setting"] in ("home", "fantasy", "studio")),
        ("Filmé au téléphone", "Shot on a phone", lambda r: r["camera"] == "phone_amateur", lambda r: r["camera"] == "3d_render"),
        ("Photoréaliste", "Photoreal", lambda r: r["realism"] == "photoreal", lambda r: r["realism"] in ("3d_cartoon", "clay_toy")),
        ("Un seul personnage récurrent", "One recurring character", lambda r: r["single_recurring_character"] is True, lambda r: r["single_recurring_character"] is False),
        ("Pas de texte à l'écran", "No on-screen text", lambda r: r["text_overlay"] is False, lambda r: r["text_overlay"] is True),
    ]
    out = []
    for fr, en, yes, no in tests:
        a = [r["med7"] for r in rows if yes(r)]
        b = [r["med7"] for r in rows if no(r)]
        if a and b:
            out.append({"trait": fr, "trait_en": en, "with": med(a), "without": med(b), "n_with": len(a), "n_without": len(b)})
    return sorted(out, key=lambda x: -(x["with"] / max(x["without"], 1)))


def dead_block():
    rec = json.load(open(f"{ROOT}/analysis/recent7.json")) if os.path.exists(f"{ROOT}/analysis/recent7.json") else {}
    acc = json.load(open(f"{ROOT}/analysis/accounts.json"))
    out = []
    for a in acc["accounts"]:
        k = f"{a['platform']}:{a['handle']}"
        r = rec.get(k, {})
        vs = [v for v in acc["videos"].get(k, []) if v["date"]]
        if a["category"] == "A" and a["handle"] not in WAVE and a["max_views"] >= 20e6 and r.get("recent_median") is not None and r["recent_median"] < 300e3 and vs:
            peak = max(vs, key=lambda v: v["views"])
            out.append({"handle": a["handle"], "platform": a["platform"], "peak": a["max_views"],
                        "peak_date": peak["date"][:7], "now": r["recent_median"], "note": a["note"]})
    return sorted(out, key=lambda x: -x["peak"])[:6]


def radar_block():
    p = f"{ROOT}/radar/new_accounts.json"
    if not os.path.exists(p):
        return {}
    rows = json.load(open(p))
    farm = sum(1 for r in rows if "トムとジェリー" in r["bio"])
    return {"ig_scanned": 1551, "tt_videos": 2755, "found": len(rows), "farm_accounts": 26,
            "farm_followers": 970536, "tiktok_new": [r for r in rows if r["platform"] == "tiktok"]}


def cadence_block():
    p = f"{ROOT}/analysis/cadence.json"
    if not os.path.exists(p):
        return {}
    c = json.load(open(p))
    rows = [{"handle": u, "birth": o["birth"][:10], "per_day": o["per_day"][:8], "gap": o["median_gap_h"],
             "first": o["first3"][0][1]} for u, o in c.items()]
    rows.sort(key=lambda r: r["birth"])
    return {"rows": rows, "first_median": int(st.median([r["first"] for r in rows]))}


def studio_videos_block():
    """Videos generated in batches from this machine (output/batch*/plan.json + results.json)."""
    out = []
    for d in sorted(glob.glob(f"{ROOT}/output/batch*")):
        if not os.path.exists(f"{d}/plan.json"):
            continue
        plan = json.load(open(f"{d}/plan.json"))
        res = json.load(open(f"{d}/results.json")) if os.path.exists(f"{d}/results.json") else {}
        for i, p in enumerate(plan):
            r = res.get(str(i), {})
            st = "done4k" if r.get("url4k") else "upscaling" if r.get("up") else "ready" if r.get("url") else "failed" if r.get("error") else "running"
            out.append({"char": p["char"], "src": p["src"], "srcUrl": p["url"], "w": p["w"], "h": p["h"], "sec": p["sec"], "job": p.get("job"),
                        "status": st, "url": r.get("flux_url") or r.get("url"), "url4k": r.get("url4k"), "mb": "batch2" in d or bool(p.get("flux")), "error": r.get("error"), "created": i, "posted": False})
    return out


def live_sources_block():
    """Source clips found by sources_live.py (trimmed copies served from dist/clips/ for Higgsfield to import)."""
    p = f"{ROOT}/analysis/live_sources.json"
    if not os.path.exists(p):
        return {"updated": None, "items": []}
    d = json.load(open(p))
    d["items"] = [c for c in d["items"] if os.path.exists(f"{HERE}/dist/clips/{c['id']}.mp4")]
    return d


def main():
    reels = seed_reels()
    accounts, cross = accounts_block()
    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "seeds": seeds_block(reels), "accounts": accounts, "cross": cross,
            "sources": sources_block(reels), "hitflop": hitflop_block(reels),
            "motion_sources": motion_sources(), "spy": spy_block(), "tricks": TRICKS, "honeymoon": honeymoon_block(reels), "wave": wave_block(reels), "scenes": scenes_block(), "traits": traits_block(), "dead": dead_block(), "radar": radar_block(), "cadence": cadence_block(), "live_sources": live_sources_block(), "studio_videos": studio_videos_block(), "hero_lineup": [frame(u, c, f"hero_{c}.jpg") for u, c in [("abu.shalab", "DdxCLS5NMRz"), ("dahab.daddy", "DdzgbbAR4VM"), ("abu.yalla", "Dd1Xfl4xczS"), ("mr_twirlo", "DdzqQqDsm7R")]]}
    tmp = f"{HERE}/data.json.tmp"
    json.dump(data, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, f"{HERE}/data.json")
    # public build for Netlify: same page with a skeleton, no commenter usernames
    import shutil
    os.makedirs(f"{HERE}/dist/img", exist_ok=True)
    pub = dict(data, spy={**data["spy"], "last_check": None, "commenter_overlap": [[None, a] for _, a in data["spy"].get("commenter_overlap", [])]})
    json.dump(pub, open(f"{HERE}/dist/data.json", "w"), ensure_ascii=False)
    for f in os.listdir(f"{HERE}/img"):
        if os.path.isdir(f"{HERE}/img/{f}"):
            shutil.copytree(f"{HERE}/img/{f}", f"{HERE}/dist/img/{f}", dirs_exist_ok=True)
        else:
            shutil.copy(f"{HERE}/img/{f}", f"{HERE}/dist/img/{f}")
    # characters.json for the API / MCP server (runs the page's own code, so it always matches the Lab)
    import subprocess
    subprocess.run(["node", f"{HERE}/export_characters.mjs"], check=False)
    # local copy of the page with a real document skeleton (the artifact adds its own at publish time)
    page = open(f"{HERE}/index.html").read()
    open(f"{HERE}/live.html", "w").write(
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
        + page + "</body></html>")
    open(f"{HERE}/dist/index.html", "w").write(
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="description" content="Reverse engineering the AI characters that gain 100k+ Instagram followers in a week.">'
        '</head><body>' + page + "</body></html>")
    print(f"data.json: {len(accounts)} accounts, {len(data['spy']['posts'])} spied posts")


if __name__ == "__main__":
    main()
