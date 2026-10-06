#!/usr/bin/env python3
"""Source finder for the studio: raw dance clips to copy with Genjutsu, ranked, checked, trimmed, ready to import.

1. Apify: latest clips of known raw-dance TikTok accounts + TikTok hashtags + TikTok searches (incl. business
   scenes: office, conference, Dubai, yacht…) + Instagram hashtag reels. Only clips under 7 days old.
2. Two buckets: "buzz" = under 48 h, ranked by views per hour; "hit" = 2 to 7 days, at least 300k views.
3. Top clips downloaded (yt-dlp), then CLIP on 3 frames: real phone footage vs AI/cartoon, one person vs crowd,
   scene label (wedding, office, conference…), business fit, and "already used" by a character account
   (background embedding ≥ 0.90 against every reel of the wave, same method as scenes.py).
4. Keepers trimmed to 15 s max (Genjutsu bills per second), re-encoded ≤ 720p, saved to dashboard/dist/clips/<id>.mp4
   (public on Netlify so Higgsfield can import them) + thumbnails in dashboard/img/src/<id>.jpg.
Output: analysis/live_sources.json (read by dashboard/build_data.py).
Usage: APIFY_TOKEN=... /usr/bin/python3 sources_live.py [--no-scrape]
"""
import datetime as dt, glob, json, os, re, subprocess, sys
import numpy as np, torch, open_clip
from PIL import Image
from scrape import ROOT
from collect import guarded, TT
from scenes import embed, border

OUT = f"{ROOT}/analysis/live_sources.json"
RAW = f"{ROOT}/radar/live_raw.json"
DL = f"{ROOT}/radar/src"
CLIPS = f"{ROOT}/dashboard/dist/clips"
THUMBS = f"{ROOT}/dashboard/img/src"
YTDLP = ["/opt/homebrew/bin/python3", "-m", "yt_dlp"]
NOW = dt.datetime.now(dt.timezone.utc)
MAX_DL, KEEP, MAX_SEC = 220, 160, 15

TT_PROFILES = ["much", "maganga_officialtz2", "baloosilly", "youngdavid027", "ali.alsheikh.fans", "_walkinwalkin",
               "hardcoreitalians", "wecklyjay1", "umor.romaneste", "official_small02", "officialtv.247",
               "djcaptaincon_official", "t.herzallah", "wedstory", "eddie_11king", "we.are.america24",
               "subhanayyaz12", "nad83nad", "haveahappyday2024", "formaluncles", "natekingakadukepritchard",
               "officialoboydignitygh124"]
TT_TAGS = ["weddingdance", "oldmandancing", "uncledance", "dancingdad", "grandpadance", "partydance", "dabke",
           "habibidance", "officeparty", "dancechallenge"]
# audience = men with an online business first (status, money, cars, sport), dance second
TT_SEARCH = ["media buyer life", "facebook ads account banned reaction", "roas celebration", "shopify sale notification reaction",
             "dropshipping winning product", "marketing agency office dance", "billionaire walking to his car", "ceo entrance", "gym motivation man", "boxing training funny", "golf swing funny",
             "goal celebration", "supercar driver reaction", "private jet entrance", "man showing off watch",
             "wedding dance uncle", "old man dancing party", "dad dancing wedding", "man dancing street",
             "office party dance", "boss dancing office", "ceo dancing", "conference dance", "networking event dance",
             "dubai party dance", "yacht party dance", "rooftop party dance", "airport dance", "gala dance man",
             "bali beach club dance", "las vegas dance man", "restaurant dance man", "crowd cheering man dancing",
             "businessman dancing", "rich man dancing private jet", "millionaire dancing", "dancing next to rolls royce",
             "wicknell chivayo dance", "arab wedding dance man", "indian wedding uncle dance", "grandpa dancing",
             "man dancing supermarket", "security guard dancing", "waiter dancing", "pilot dancing", "dad dance kitchen",
             "uncle dance", "auntie dance wedding", "grandma dancing", "old lady dancing", "man dancing in public",
             "funny dance video", "viral dance man", "dance battle wedding", "crowd goes crazy dance", "dancing at work",
             "dancing in the office", "boss dance", "dancing at the mall", "dancing in the street funny", "groom dance",
             "father of the bride dance", "best man dance", "nigerian wedding dance", "arabic dance man", "turkish wedding dance",
             "greek dance wedding", "italian wedding dance", "dancing waiter restaurant", "dancing on yacht", "dancing in dubai",
             "dancing at the airport", "dancing at the gym", "trend dance 2026", "new dance trend", "shuffle dance man",
             "dubai rich lifestyle", "billionaire walking to his car", "rich man leaving luxury store", "dubai luxury walk",
             "arab billionaire lifestyle", "rolls royce dubai", "luxury lifestyle dubai mall", "rich kid dubai"]
IG_TAGS = ["mediabuyer", "facebookads", "metaads", "ecommerce", "dropshipping", "shopify", "affiliatemarketing", "entrepreneurlife", "ceolife", "supercars", "privatejet", "gymmotivation", "boxingtraining", "golfswing",
           "footballskills", "goalcelebration", "padel", "sigmamale", "moneymotivation", "weddingdance", "uncledance", "oldmandancing", "dancingdad", "partydance", "officeparty",
           "dubainightlife", "yachtparty", "conferencelife", "dancingman", "funnydance", "dancevideo", "weddingvibes",
           "grandpadance", "dancingqueen", "dancetrend", "viraldance", "dancechallenge", "groomdance", "shaadi",
           "dubailifestyle", "richlifestyle", "luxurylifestyle", "billionairelifestyle"]
AI_WORDS = re.compile(r"\b(ai|higgsfield|kling|aicharacter|aiinfluencer|aiart|aivideo|aigenerated|cgi|animation)\b", re.I)
WAVE = {p.split("/")[-1] for p in glob.glob(f"{ROOT}/data/*")}

SCENES = {"wedding": "a wedding party with guests", "party": "a night club or house party", "street": "a city street",
          "office": "an office with desks and computers", "conference": "a conference stage or business event hall",
          "dubai": "a luxury skyline at night like Dubai", "pool": "a beach, pool or beach club", "yacht": "a yacht or boat deck",
          "car": "inside or next to a luxury car", "home": "a living room at home", "restaurant": "a restaurant or cafe",
          "airport": "an airport terminal", "stage": "a concert stage with a crowd", "gym": "a gym", "market": "a market or bazaar"}
BIZ = {"office", "conference", "dubai", "yacht", "car", "airport", "restaurant", "pool"}
REAL = ["a real amateur phone video of a real person", "an AI generated or cartoon character", "a 3D animated character",
        "a screenshot or text on a plain background"]
WHO = ["one person dancing, full body visible", "a group of people dancing together", "a person talking to the camera",
       "no person, only a place or an object"]


def age_h(ts):
    t = dt.datetime.fromtimestamp(ts, dt.timezone.utc) if isinstance(ts, (int, float)) else dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return max((NOW - t).total_seconds() / 3600, 1)


def tt_item(v):
    m = v.get("videoMeta") or {}
    return {"id": "tt_" + str(v.get("id")), "platform": "tiktok", "owner": (v.get("authorMeta") or {}).get("name"),
            "url": v.get("webVideoUrl"), "views": v.get("playCount") or 0, "likes": v.get("diggCount") or 0,
            "shares": v.get("shareCount") or 0, "comments": v.get("commentCount") or 0,
            "created": v.get("createTimeISO"), "duration": m.get("duration") or 0, "w": m.get("width"), "h": m.get("height"),
            "caption": (v.get("text") or "")[:160],
            "sound": " - ".join(x for x in [(v.get("musicMeta") or {}).get("musicAuthor"), (v.get("musicMeta") or {}).get("musicName")] if x)}


def ig_item(r):
    return {"id": "ig_" + str(r.get("shortCode")), "platform": "instagram", "owner": r.get("ownerUsername"),
            "url": r.get("url"), "video_url": r.get("videoUrl"), "views": r.get("videoPlayCount") or r.get("videoViewCount") or 0,
            "likes": max(r.get("likesCount") or 0, 0), "shares": 0, "comments": r.get("commentsCount") or 0,
            "created": r.get("timestamp"), "duration": r.get("videoDuration") or 0, "w": None, "h": None,
            "caption": (r.get("caption") or "")[:160],
            "sound": " - ".join(x for x in [(r.get("musicInfo") or {}).get("artist_name"), (r.get("musicInfo") or {}).get("song_name")] if x)}


def scrape():
    tt = guarded(TT, {"profiles": TT_PROFILES, "hashtags": TT_TAGS, "searchQueries": TT_SEARCH, "resultsPerPage": 50,
                      "profileSorting": "latest",
                      "shouldDownloadVideos": False, "shouldDownloadCovers": False})
    ig = guarded("apify~instagram-hashtag-scraper", {"hashtags": IG_TAGS, "resultsLimit": 50, "resultsType": "reels"})
    raw = {"tt": tt, "ig": ig, "at": NOW.isoformat()}
    if os.path.exists(RAW):  # keep the previous scrape too: still fresh, already paid for
        old = json.load(open(RAW))
        raw["tt"] = (tt or []) + [x for x in old.get("tt", []) if x.get("id") not in {y.get("id") for y in tt or []}]
        raw["ig"] = (ig or []) + [x for x in old.get("ig", []) if x.get("shortCode") not in {y.get("shortCode") for y in ig or []}]
    json.dump(raw, open(RAW, "w"))
    return raw


def candidates(raw):
    seen = {}
    for kind, items in (("tt", raw["tt"]), ("ig", raw["ig"])):
        for r in items or []:
            if r.get("error") or (kind == "tt" and not r.get("id")) or (kind == "ig" and r.get("type") not in (None, "Video")):
                continue
            c = tt_item(r) if kind == "tt" else ig_item(r)
            if not c["url"] or not c["created"] or c["owner"] in WAVE:
                continue
            if not 5 <= (c["duration"] or 0) <= 60 or AI_WORDS.search(c["caption"] or ""):
                continue
            c["ageH"] = round(age_h(c["created"]), 1)
            if c["ageH"] > 24 * 7:
                continue
            eng = (c["likes"] + 3 * c["shares"] + 2 * c["comments"]) / max(c["views"], 1)
            c["vph"] = round(c["views"] / c["ageH"])
            c["score"] = round(c["views"] / c["ageH"] ** 0.8 * (1 + min(eng * 5, 1)))
            c["bucket"] = "buzz" if c["ageH"] <= 48 else "hit"
            if c["bucket"] == "hit" and c["views"] < 150_000:
                continue
            if c["bucket"] == "buzz" and c["views"] < 10_000:
                continue
            if c["id"] not in seen or seen[c["id"]]["views"] < c["views"]:
                seen[c["id"]] = c
    cs = list(seen.values())
    buzz = sorted([c for c in cs if c["bucket"] == "buzz"], key=lambda c: -c["score"])
    hit = sorted([c for c in cs if c["bucket"] == "hit"], key=lambda c: -c["views"])
    print(f"candidates: {len(buzz)} buzz, {len(hit)} hit", flush=True)
    return buzz[:MAX_DL // 2] + hit[:MAX_DL - min(len(buzz), MAX_DL // 2)]


def download(c):
    os.makedirs(DL, exist_ok=True)
    p = f"{DL}/{c['id']}.mp4"
    if os.path.exists(p) and os.path.getsize(p) > 50_000:
        return p
    try:
        if c.get("video_url"):
            subprocess.run(["curl", "-sL", "-m", "120", "-o", p, c["video_url"]], check=True)
        else:
            subprocess.run(YTDLP + ["-q", "--no-warnings", "-f", "mp4/best", "-o", p, "--force-overwrites", c["url"]],
                           check=True, timeout=300, capture_output=True)
        return p if os.path.getsize(p) > 50_000 else None
    except Exception as e:
        print("  download failed", c["id"], str(e)[:120], flush=True)
        return None


def probe(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", p], capture_output=True, text=True).stdout
    j = json.loads(o or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("width"), s.get("height"), float((j.get("format") or {}).get("duration") or 0)


def grab_frames(p, dur):
    out = []
    for t in (0.8, dur * 0.35, dur * 0.7):
        f = f"{DL}/_f.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", "scale=360:-2", f])
        if os.path.exists(f):
            out.append(Image.open(f).convert("RGB").copy())
    return out


def main():
    raw = json.load(open(RAW)) if "--no-scrape" in sys.argv and os.path.exists(RAW) else scrape()
    picks = candidates(raw)
    model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    tok = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    with torch.no_grad():
        def txt(xs):
            e = model.encode_text(tok(xs)); return e / e.norm(dim=-1, keepdim=True)
        T_real, T_who = txt(REAL), txt(WHO)
        T_scene = txt([f"a phone video filmed at {v}" for v in SCENES.values()])
    keys, _, bord = embed()
    wave_owner = [k.split("/")[0] for k in keys]
    bflat = bord.reshape(-1, bord.shape[-1]).astype(np.float32)
    os.makedirs(CLIPS, exist_ok=True); os.makedirs(THUMBS, exist_ok=True)
    kept = []
    for c in picks:
        p = download(c)
        if not p:
            continue
        w, h, dur = probe(p)
        if not w or dur < 3:
            continue
        fr = grab_frames(p, dur)
        if len(fr) < 2:
            continue
        with torch.no_grad():
            x = torch.stack([pre(f) for f in fr] + [pre(border(f)) for f in fr])
            e = model.encode_image(x); e = e / e.norm(dim=-1, keepdim=True)
            full, bd = e[:len(fr)], e[len(fr):]
            pr = (100 * full @ T_real.T).softmax(-1).mean(0).numpy()
            pw = (100 * full @ T_who.T).softmax(-1).mean(0).numpy()
            ps = (100 * full @ T_scene.T).softmax(-1).mean(0).numpy()
        sims = (bd.numpy().astype(np.float32) @ bflat.T).max(0)
        best = int(sims.argmax())
        used_by = wave_owner[best // bord.shape[1]] if sims[best] >= 0.90 else None
        scene = list(SCENES)[int(ps.argmax())]
        c.update(w=w, h=h, vertical=h > w, real=round(float(pr[0]), 2), solo=round(float(pw[0]), 2),
                 crowd=round(float(pw[1]), 2), talk=round(float(pw[2]), 2), scene=scene, biz=scene in BIZ,
                 used_by=used_by, used_sim=round(float(sims[best]), 3))
        # CLIP's real-vs-AI guess is unreliable on phone clips with text overlays (calibrated by eye on 30 clips):
        # it only ranks; we drop clips that are clearly a talking head or have nobody in them.
        ok = c["talk"] < 0.6 and pw[3] < 0.5
        print(f"  {'OK ' if ok else 'no '} {c['id']:<24} {c['bucket']:<4} {c['views']:>10,} {scene:<10} real={c['real']} solo={c['solo']} "
              f"vert={c['vertical']} used={used_by}", flush=True)
        if not ok:
            continue
        clip = f"{CLIPS}/{c['id']}.mp4"
        sec = min(dur, MAX_SEC)
        vf = "scale='min(720,iw)':-2" if c["vertical"] else "scale=-2:'min(720,ih)'"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", p, "-t", f"{sec:.2f}", "-vf", vf, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", clip], check=True)
        fr[0].resize((270, int(270 * fr[0].height / fr[0].width))).save(f"{THUMBS}/{c['id']}.jpg", quality=80)
        c["sec"] = round(sec, 1)
        c["cost480"] = int(round(sec * 3))
        kept.append(c)
    # rank: vertical, not used, real & solo first; buzz by score, hit by views
    def rank(c):
        return (c["used_by"] is not None, not c["vertical"], -(0.4 + c["solo"] + 0.3 * c["biz"]) * (c["score"] if c["bucket"] == "buzz" else c["views"] / 50))
    kept.sort(key=rank)
    kept = kept[:KEEP]
    for c in kept:
        c.pop("video_url", None)
    json.dump({"updated": NOW.isoformat(), "items": kept}, open(OUT, "w"), indent=1, ensure_ascii=False)
    keep_ids = {c["id"] for c in kept}
    for f in glob.glob(f"{CLIPS}/*.mp4"):
        if os.path.basename(f)[:-4] not in keep_ids and os.path.getmtime(f) < NOW.timestamp() - 8 * 86400:
            os.remove(f)
    print(f"kept {len(kept)} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
