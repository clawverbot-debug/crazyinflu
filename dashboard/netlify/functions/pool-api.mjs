// Account pool tracker: the team's own Instagram accounts, grouped by phone, with stats history.
// GET  /api/pool  → accounts, latest snapshot + history per account, last reels, refresh status
//                   (also collects finished Apify runs and stores a new snapshot when they are done)
// POST /api/pool  → {action:"add", handle, phone, note} · {action:"update", handle, phone, note} · {action:"remove", handle}
//                   · {action:"refresh"} (starts Apify profile + reel scrapes for every account, ~1-3 min)
// Auth: header x-radar-key must equal env RADAR_KEY (fail-closed when RADAR_KEY is not set).
import { getStore } from "@netlify/blobs";

export const config = { path: "/api/pool" };

const API = "https://api.apify.com/v2";
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
const norm = (h) => String(h || "").trim().replace(/^@/, "").replace(/^https?:\/\/(www\.)?instagram\.com\//, "").split(/[/?\s]/)[0].toLowerCase();

async function startRun(actor, input, token) {
  const r = await fetch(`${API}/acts/${actor}/runs?token=${token}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
  return (await r.json()).data?.id;
}

async function collect(store, state, token) {
  if (!state.runs?.length) return state;
  const done = {};
  for (const run of state.runs) {
    const j = await (await fetch(`${API}/actor-runs/${run.id}?token=${token}`)).json();
    const st = j.data?.status;
    if (st === "READY" || st === "RUNNING") return state; // wait until both runs finish
    done[run.kind] = st === "SUCCEEDED" ? await (await fetch(`${API}/datasets/${j.data.defaultDatasetId}/items?token=${token}&clean=1`)).json() : [];
  }
  const accounts = (await store.get("accounts", { type: "json" })) || [];
  const snaps = (await store.get("snaps", { type: "json" })) || {};
  const reels = (await store.get("reels", { type: "json" })) || {};
  const now = new Date().toISOString();
  const prof = Object.fromEntries((done.prof || []).filter((p) => p.username).map((p) => [p.username.toLowerCase(), p]));
  const byOwner = {};
  for (const r of done.reels || []) {
    const o = (r.ownerUsername || "").toLowerCase();
    if (!o || !r.shortCode) continue;
    (byOwner[o] ||= []).push({ code: r.shortCode, url: r.url || `https://www.instagram.com/reel/${r.shortCode}/`, t: r.timestamp,
      views: r.videoPlayCount || r.videoViewCount || 0, likes: Math.max(r.likesCount || 0, 0), comments: r.commentsCount || 0,
      dur: Math.round(r.videoDuration || 0), caption: (r.caption || "").slice(0, 90) });
  }
  for (const a of accounts) {
    const p = prof[a.handle], rs = (byOwner[a.handle] || []).sort((x, y) => String(y.t).localeCompare(String(x.t)));
    if (!p) { a.status = "introuvable"; continue; }
    a.status = p.private ? "privé" : "ok";
    a.name = p.fullName || ""; a.isNew = !!p.joinedRecently; a.bio = p.biography || "";
    if (rs.length) reels[a.handle] = rs.slice(0, 40);
    const views = rs.reduce((n, r) => n + r.views, 0), best = rs.reduce((b, r) => (r.views > (b?.views || 0) ? r : b), null);
    const snap = { t: now, followers: p.followersCount || 0, following: p.followsCount || 0, posts: p.postsCount || 0,
      reels: rs.length, views, best: best ? { views: best.views, url: best.url } : null, last: rs[0]?.t || null,
      avg5: rs.length ? Math.round(rs.slice(0, 5).reduce((n, r) => n + r.views, 0) / Math.min(5, rs.length)) : 0 };
    (snaps[a.handle] ||= []).push(snap);
    snaps[a.handle] = snaps[a.handle].slice(-120);
  }
  await store.setJSON("accounts", accounts);
  await store.setJSON("snaps", snaps);
  await store.setJSON("reels", reels);
  state = { runs: [], lastRefresh: now, startedAt: null, error: null };
  await store.setJSON("state", state);
  return state;
}

export default async (req) => {
  const key = process.env.RADAR_KEY;
  if (!key) return json({ error: "RADAR_KEY not configured" }, 503);
  if (req.headers.get("x-radar-key") !== key) return json({ error: "bad key" }, 401);
  const token = process.env.APIFY_TOKEN;
  const store = getStore({ name: "pool", consistency: "strong" });
  let state = (await store.get("state", { type: "json" })) || { runs: [] };

  if (req.method === "GET") {
    if (token) state = await collect(store, state, token);
    const accounts = (await store.get("accounts", { type: "json" })) || [];
    const snaps = (await store.get("snaps", { type: "json" })) || {};
    const reels = (await store.get("reels", { type: "json" })) || {};
    return json({ state: { pending: !!state.runs?.length, startedAt: state.startedAt || null, lastRefresh: state.lastRefresh || null },
      accounts: accounts.map((a) => ({ ...a, history: snaps[a.handle] || [], reels: (reels[a.handle] || []).slice(0, 12) })) });
  }
  if (req.method !== "POST") return json({ error: "method" }, 405);
  const body = await req.json().catch(() => ({}));
  let accounts = (await store.get("accounts", { type: "json" })) || [];
  if (body.action === "add" || body.action === "update") {
    const handle = norm(body.handle);
    if (!/^[a-z0-9._]{1,30}$/.test(handle)) return json({ error: "pseudo invalide" }, 400);
    const a = accounts.find((x) => x.handle === handle);
    const char = body.char === undefined ? undefined : String(body.char || "").replace(/[^a-z0-9]/g, "").slice(0, 30);
    if (a) Object.assign(a, { phone: body.phone ?? a.phone, note: body.note ?? a.note, char: char ?? a.char });
    else if (body.action === "add") accounts.push({ handle, phone: String(body.phone || "").slice(0, 40), note: String(body.note || "").slice(0, 200), char: char || "", added: new Date().toISOString(), status: "à relever" });
    else return json({ error: "unknown handle" }, 404);
    await store.setJSON("accounts", accounts);
    return json({ ok: true, accounts });
  }
  if (body.action === "remove") {
    accounts = accounts.filter((x) => x.handle !== norm(body.handle));
    await store.setJSON("accounts", accounts);
    return json({ ok: true, accounts });
  }
  if (body.action === "refresh") {
    if (!token) return json({ error: "APIFY_TOKEN not configured" }, 503);
    if (state.runs?.length && Date.now() - new Date(state.startedAt) < 15 * 60e3) return json({ ok: true, pending: true });
    const users = accounts.map((a) => a.handle);
    if (!users.length) return json({ error: "aucun compte" }, 400);
    const prof = await startRun("apify~instagram-profile-scraper", { usernames: users }, token);
    const reels = await startRun("apify~instagram-reel-scraper", { username: users, resultsLimit: 30 }, token);
    state = { ...state, runs: [prof && { id: prof, kind: "prof" }, reels && { id: reels, kind: "reels" }].filter(Boolean), startedAt: new Date().toISOString() };
    await store.setJSON("state", state);
    return json({ ok: true, pending: true });
  }
  return json({ error: "unknown action" }, 400);
};
