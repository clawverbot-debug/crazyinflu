#!/usr/bin/env python3
"""Spy on a watchlist of Instagram character accounts: catch every new reel and record its first hours.

Adaptive cadence (run `tick` every 5 min from launchd/cron):
  - cold account: checked every COLD_MIN minutes (latest 3 reels → new post detection)
  - hot account (a reel younger than HOT_MIN): checked every tick → views/likes/comments curve
  - comments of each new reel captured at +15 min and +60 min (bursts, generic texts, pod overlap)
  - events logged when a reel runs far above the account's own baseline at the same age
A daily budget guard stops all Apify calls once DAILY_BUDGET_USD is reached.

Usage:
  python3 spy.py tick              one cycle (what cron runs)
  python3 spy.py status            watchlist, hot posts, today's spend
Token: env APIFY_TOKEN or ~/.config/viral-spy/apify_token (chmod 600, never in the repo).
"""
import json, os, sqlite3, sys, time, datetime as dt, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(f"{HERE}/config.json"))
DB = f"{HERE}/spy.db"
API = "https://api.apify.com/v2"
PRICE = {"reel": 0.0026, "comment": 0.0026, "start": 0.001}


def token():
    t = os.environ.get("APIFY_TOKEN")
    if not t:
        with open(os.path.expanduser("~/.config/viral-spy/apify_token")) as f:
            t = f.read().strip()
    return t


def now():
    return dt.datetime.now(dt.timezone.utc)


def db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS posts(code TEXT PRIMARY KEY, account TEXT, posted_at TEXT, first_seen TEXT,
        caption TEXT, url TEXT, duration REAL, sound TEXT);
    CREATE TABLE IF NOT EXISTS snaps(code TEXT, account TEXT, ts TEXT, age_min REAL, views INT, likes INT, comments INT);
    CREATE TABLE IF NOT EXISTS comments(code TEXT, fetched_at TEXT, label TEXT, cid TEXT, username TEXT, text TEXT,
        created_at TEXT, likes INT, PRIMARY KEY(code, cid));
    CREATE TABLE IF NOT EXISTS checks(account TEXT PRIMARY KEY, last_check TEXT);
    CREATE TABLE IF NOT EXISTS spend(day TEXT PRIMARY KEY, usd REAL);
    CREATE TABLE IF NOT EXISTS events(ts TEXT, account TEXT, code TEXT, kind TEXT, detail TEXT);
    CREATE TABLE IF NOT EXISTS comment_jobs(code TEXT, label TEXT, PRIMARY KEY(code, label));
    CREATE TABLE IF NOT EXISTS pins(account TEXT PRIMARY KEY, n INT);
    """)
    return c


def spent(c, add=0.0):
    day = now().date().isoformat()
    cur = (c.execute("SELECT usd FROM spend WHERE day=?", (day,)).fetchone() or [0.0])[0]
    if add:
        c.execute("INSERT OR REPLACE INTO spend VALUES(?,?)", (day, cur + add))
        c.commit()
    return cur + add


def run_actor(actor, payload, timeout=600):
    tk = token()
    req = urllib.request.Request(f"{API}/acts/{actor}/runs?token={tk}&timeout={timeout}",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        run = json.load(r)["data"]
    while run["status"] in ("READY", "RUNNING"):
        time.sleep(5)
        with urllib.request.urlopen(f"{API}/actor-runs/{run['id']}?token={tk}", timeout=60) as r:
            run = json.load(r)["data"]
    with urllib.request.urlopen(f"{API}/datasets/{run['defaultDatasetId']}/items?token={tk}&clean=1", timeout=120) as r:
        return json.load(r)


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def baseline(c, account, age_min):
    """Median views of this account's previous reels at a similar age (±25%)."""
    rows = c.execute("""SELECT s.views FROM snaps s JOIN posts p ON p.code=s.code
                        WHERE s.account=? AND s.age_min BETWEEN ? AND ? AND p.posted_at < ?""",
                     (account, age_min * 0.75, age_min * 1.25,
                      (now() - dt.timedelta(minutes=age_min)).isoformat())).fetchall()
    v = sorted(r[0] for r in rows if r[0] is not None)
    return v[len(v) // 2] if len(v) >= 3 else None


def detect_events(c, code, account, age, views, likes, comments):
    base = baseline(c, account, age)
    ts = now().isoformat()

    def log(kind, detail):
        if not c.execute("SELECT 1 FROM events WHERE code=? AND kind=?", (code, kind)).fetchone():
            c.execute("INSERT INTO events VALUES(?,?,?,?,?)", (ts, account, code, kind, detail))
            print(f"  EVENT {account} {code} {kind}: {detail}", flush=True)

    if base and views and views > CFG["push_ratio"] * base:
        log("push", f"{views} views at {age:.0f} min = {views/base:.1f}x baseline {base}")
    if views and age <= 30 and likes and likes / views > CFG["early_like_rate"]:
        log("early_like_rate", f"likes/views {likes/views:.1%} at {age:.0f} min")
    if likes and age <= 30 and comments and comments / likes > CFG["early_comment_rate"]:
        log("comment_burst", f"comments/likes {comments/likes:.1%} at {age:.0f} min")


def fetch_reels(c, accounts, extra):
    """Latest reels per account; pinned reels come back too, so ask for (pinned count + extra)."""
    groups = {}
    for a in accounts:
        n = (c.execute("SELECT n FROM pins WHERE account=?", (a,)).fetchone() or [3])[0]
        groups.setdefault(n + extra, []).append(a)
    items = []
    for limit, accs in groups.items():
        est = len(accs) * limit * PRICE["reel"] + PRICE["start"]
        if spent(c) + est > CFG["daily_budget_usd"]:
            print(f"  budget guard: skip reels ({spent(c):.2f}$ spent today)", flush=True)
            continue
        got = run_actor("apify~instagram-reel-scraper", {"username": accs, "resultsLimit": limit})
        spent(c, len(got) * PRICE["reel"] + PRICE["start"])
        for a in accs:
            pinned = sum(1 for r in got if r.get("ownerUsername") == a and r.get("isPinned"))
            if pinned >= limit - extra:  # maybe more pinned than we assumed: learn it
                c.execute("INSERT OR REPLACE INTO pins VALUES(?,?)", (a, pinned + (1 if pinned == limit else 0)))
            else:
                c.execute("INSERT OR REPLACE INTO pins VALUES(?,?)", (a, pinned))
        items += got
    c.commit()
    return items


def fetch_comments(c, code, url, label):
    n = CFG["comments_per_capture"]
    if spent(c) + n * PRICE["comment"] + PRICE["start"] > CFG["daily_budget_usd"]:
        return
    items = run_actor("apify~instagram-comment-scraper", {"directUrls": [url], "resultsLimit": n})
    spent(c, len(items) * PRICE["comment"] + PRICE["start"])
    ts = now().isoformat()
    for x in items:
        c.execute("INSERT OR IGNORE INTO comments VALUES(?,?,?,?,?,?,?,?)",
                  (code, ts, label, x.get("id"), x.get("ownerUsername"), x.get("text"), x.get("timestamp"),
                   x.get("likesCount")))
    c.execute("INSERT OR IGNORE INTO comment_jobs VALUES(?,?)", (code, label))
    c.commit()
    print(f"  comments {code} {label}: {len(items)}", flush=True)


def tick():
    c = db()
    t = now()
    if t > iso(CFG["end_date"]):
        print(f"{t:%Y-%m-%d %H:%M} spy period over (end_date {CFG['end_date']}), nothing to do", flush=True)
        return
    hot, due = [], []
    for a in CFG["watchlist"]:
        last_post = c.execute("SELECT max(posted_at) FROM posts WHERE account=?", (a,)).fetchone()[0]
        last_check = (c.execute("SELECT last_check FROM checks WHERE account=?", (a,)).fetchone() or [None])[0]
        if last_post and (t - iso(last_post)).total_seconds() / 60 < CFG["hot_minutes"]:
            hot.append(a)
        elif not last_check or (t - iso(last_check)).total_seconds() / 60 >= CFG["cold_minutes"] - 1:
            due.append(a)
    print(f"{t:%Y-%m-%d %H:%M} hot={hot} due={due}", flush=True)
    items = []
    if hot:
        items += fetch_reels(c, hot, 1)
    if due:
        items += fetch_reels(c, due, 2)
    for a in hot + due:
        c.execute("INSERT OR REPLACE INTO checks VALUES(?,?)", (a, t.isoformat()))
    for r in items:
        if r.get("isPinned") or not r.get("timestamp") or not r.get("shortCode"):
            continue
        code, a = r["shortCode"], r.get("ownerUsername")
        posted = iso(r["timestamp"])
        age = (t - posted).total_seconds() / 60
        if age > CFG["track_hours"] * 60:
            continue
        if not c.execute("SELECT 1 FROM posts WHERE code=?", (code,)).fetchone():
            m = r.get("musicInfo") or {}
            c.execute("INSERT INTO posts VALUES(?,?,?,?,?,?,?,?)",
                      (code, a, posted.isoformat(), t.isoformat(), r.get("caption"), r.get("url"),
                       r.get("videoDuration"), f"{m.get('artist_name','')} - {m.get('song_name','')}"))
            kind = "new_post" if age <= 2 * CFG["cold_minutes"] else "backfill"
            c.execute("INSERT INTO events VALUES(?,?,?,?,?)", (t.isoformat(), a, code, kind,
                                                               f"seen {age:.0f} min after posting"))
            print(f"  NEW {a} {code} ({age:.0f} min old) {(r.get('caption') or '')[:40]!r}", flush=True)
        v, l, cm = r.get("videoPlayCount") or r.get("videoViewCount"), r.get("likesCount"), r.get("commentsCount")
        c.execute("INSERT INTO snaps VALUES(?,?,?,?,?,?,?)", (code, a, t.isoformat(), round(age, 1), v, l, cm))
        detect_events(c, code, a, age, v, l, cm)
        for label, at in (("t15", 15), ("t60", 60)):
            if at <= age < at + CFG["hot_minutes"] and not c.execute(
                    "SELECT 1 FROM comment_jobs WHERE code=? AND label=?", (code, label)).fetchone():
                fetch_comments(c, code, r.get("url"), label)
    c.commit()
    print(f"  spent today: ${spent(c):.2f} / ${CFG['daily_budget_usd']}", flush=True)
    try:  # refresh the dashboard data (local, free)
        import subprocess
        subprocess.run([sys.executable, f"{os.path.dirname(HERE)}/dashboard/build_data.py"], timeout=120)
    except Exception as e:
        print("  dashboard refresh failed:", e, flush=True)


def status():
    c = db()
    print("watchlist:", ", ".join(CFG["watchlist"]))
    print(f"today: ${spent(c):.2f} / ${CFG['daily_budget_usd']}")
    for row in c.execute("""SELECT p.account, p.code, p.posted_at, max(s.age_min), max(s.views), max(s.likes),
                            max(s.comments), count(*) FROM posts p JOIN snaps s ON s.code=p.code
                            GROUP BY p.code ORDER BY p.posted_at DESC LIMIT 20"""):
        print("  ", row)
    for row in c.execute("SELECT * FROM events ORDER BY ts DESC LIMIT 20"):
        print("  ", row)


if __name__ == "__main__":
    {"tick": tick, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
