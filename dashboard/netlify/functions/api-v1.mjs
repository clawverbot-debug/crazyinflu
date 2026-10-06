// Private data API + MCP server for the Character Lab.
// REST:  GET /api/v1 (index) · /characters · /characters/:id · /videos · /sources · /radar · /data · /data/:block
//        · /playbook · /schedule · /knowledge · /posts   and   POST /api/v1/posts (the posting tool logs what it posted)
// MCP:   POST /mcp  (Streamable HTTP, JSON-RPC 2.0: initialize, tools/list, tools/call, ping)
// Auth:  fail-closed. Every call needs "Authorization: Bearer <API_KEY>" or "x-api-key: <API_KEY>".
//        If the API_KEY env var is not set, every call is refused (503).
import { getStore } from "@netlify/blobs";
import { timingSafeEqual } from "node:crypto";
import { KNOWLEDGE_MD } from "../lib/knowledge.mjs";

export const config = { path: ["/api/v1", "/api/v1/*", "/mcp"] };

const SITE = "https://character-lab-research.netlify.app";
const json = (o, s = 200) => new Response(JSON.stringify(o, null, 1), { status: s, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });

function authorized(req) {
  const key = process.env.API_KEY;
  if (!key || key.length < 24) return null; // not configured → refuse everything
  const got = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "") || req.headers.get("x-api-key") || "";
  const a = Buffer.from(got), b = Buffer.from(key);
  return a.length === b.length && timingSafeEqual(a, b);
}

let cache = null;
async function load() {
  if (cache && Date.now() - cache.t < 60e3) return cache;
  const [chars, data] = await Promise.all([
    fetch(`${SITE}/characters.json`).then((r) => r.json()),
    fetch(`${SITE}/data.json`).then((r) => r.json()),
  ]);
  cache = { t: Date.now(), chars: chars.characters, data };
  return cache;
}
async function radar() {
  try {
    const store = getStore("radar");
    const c = (await store.get("candidates", { type: "json" })) || {};
    const st = (await store.get("state", { type: "json" })) || {};
    return { updated: st.updated || null, stopped: st.stopped || null, candidates: Object.values(c).sort((x, y) => y.score - x.score) };
  } catch (e) { return { updated: null, candidates: [], error: "radar store unavailable" }; }
}

// ---- posting playbook: everything learned, in a form a posting tool can apply ----
const PLAYBOOK = {
  version: "2026-10-06",
  windows_utc: [{ from: "14:00", to: "15:00" }, { from: "20:00", to: "22:00" }],
  before_launch: "prepare at least 10 videos before the first post",
  cadence: {
    day0: { posts: "3-4", min_gap_hours: 3, note: "best 2 scenes first: the first reels of a new account get the biggest push" },
    day1: { posts: 3, min_gap_hours: 4 },
    day2_4: { posts: 2, min_gap_hours: 8, max_gap_hours: 14 },
    after_day4: { posts: 1, note: "D5: flops off the grid, monetize at the peak, start the next character" },
    too_much: "7-9 posts a day (mr_twirlo) → 135k median; best accounts keep 8 to 19 h between posts",
  },
  flops: "archive flops off the grid, never delete (visible reels median 1.3M vs hidden 50k on 6 accounts)",
  captions: { rule: "use the caption attached to the video (one variant picked at random per post); never ask people to comment; @primeads_ai for Q4 scaling", variants: "V1 hook only · V2 +2-3 tags · V3 +Prime Ads line · V4 +3-5 tags · V5 mini story · V6 one lowercase line", hashtags: "0 to 5 (Instagram caps posts at 5 since Dec 2025), rotating" },
  bios: { rule: "one bio per account (B1-B5 shapes), @primeads_ai in the first lines, never write 'AI character'", max_chars: 150 },
  ai_label: "label the AI content when posting (Instagram AI label / 'AI-generated profile'): since 31 Aug 2026 unlabelled AI-person profiles stop being recommended to non-followers; with the label reach is not penalised",
  one_video_one_account: "never post the same video on two accounts (Instagram only recommends the original of identical content)",
  video: { min_seconds: 15, format: "9:16, upload the 4K file", music: "keep the sound in the file; adding it inside Instagram is not proven to help (1.00x vs 1.07x)" },
  observed_on_our_accounts: [
    "prime_leopold: 437k on the first post, then decay → the new-account window is real",
    "prime_thecoach: 1.68M on reel DeGcD2ktILE",
    "the 3 accounts created on Thibault's phone stayed near 0 views on their first posts (cause unknown, under watch)",
  ],
};
const DAY = 864e5;
const postsStore = () => getStore({ name: "posts", consistency: "strong" });
async function loggedPosts() { try { return (await postsStore().get("log", { type: "json" })) || []; } catch (e) { return []; } }
async function logPost(D, b) {
  const account = String(b.account || "").trim().replace(/^@/, "").toLowerCase();
  if (!/^[a-z0-9._]{1,30}$/.test(account)) throw { status: 400, message: "account (instagram handle) is required" };
  const v = b.video_4k ? Q.videos(D, {}).find((x) => x.video_4k === b.video_4k) : null;
  const t = b.posted_at ? new Date(b.posted_at) : new Date();
  if (isNaN(t)) throw { status: 400, message: "posted_at must be an ISO date" };
  const code = (String(b.reel_url || "").match(/\/(?:reel|p)\/([A-Za-z0-9_-]+)/) || [])[1] || null;
  const row = { account, posted_at: t.toISOString(), reel_url: b.reel_url || null, code, video_4k: b.video_4k || null,
    character: v?.character || b.character || null, video_n: v?.n ?? null, caption: String(b.caption || "").slice(0, 2200),
    caption_variant: v?.caption_variant || null, trial_reel: !!b.trial_reel, phone: b.phone ? String(b.phone).slice(0, 40) : null, logged_at: new Date().toISOString() };
  const log = await loggedPosts(); log.push(row); await postsStore().setJSON("log", log.slice(-5000));
  return { ok: true, post: row };
}
function nextSlot(fromMs) {
  for (let d = 0; d < 3; d++) for (const w of PLAYBOOK.windows_utc) {
    const [h, m] = w.from.split(":").map(Number);
    const t = Date.UTC(new Date(fromMs).getUTCFullYear(), new Date(fromMs).getUTCMonth(), new Date(fromMs).getUTCDate() + d, h, m);
    if (t >= fromMs) return new Date(t).toISOString();
  }
  return new Date(fromMs).toISOString();
}
const norm = (x) => String(x || "").toLowerCase().replace(/[^a-z0-9@ ]+/g, " ").replace(/\s+/g, " ").trim();
async function pool() {
  try { const st = getStore({ name: "pool", consistency: "strong" });
    return { accounts: (await st.get("accounts", { type: "json" })) || [], snaps: (await st.get("snaps", { type: "json" })) || {}, reels: (await st.get("reels", { type: "json" })) || {} };
  } catch (e) { return { accounts: [], snaps: {}, reels: {} }; }
}
const med = (xs) => { if (!xs.length) return null; const v = [...xs].sort((x, y) => x - y), m = v.length >> 1; return v.length % 2 ? v[m] : Math.round((v[m - 1] + v[m]) / 2); };
function group(rows, keyFn) {
  const g = {};
  for (const r of rows) { const k = keyFn(r); if (k != null) (g[k] ||= []).push(r.views); }
  return Object.entries(g).map(([k, v]) => ({ key: k, reels: v.length, median_views: med(v), best: Math.max(...v) })).sort((x, y) => (y.median_views || 0) - (x.median_views || 0));
}
async function learnings(D) {
  const P = await pool(), now = Date.now(), rows = [];
  const variantOf = {};
  for (const c of D.chars) for (const v of c.videos || []) if (v.caption) variantOf[norm(v.caption).slice(0, 30)] = v.caption_variant || null;
  const byCode = Object.fromEntries((await loggedPosts()).filter((p) => p.code).map((p) => [p.code, p]));
  for (const a of P.accounts) {
    const rs = (P.reels[a.handle] || []).filter((r) => r.t);
    const first = rs.length ? Math.min(...rs.map((r) => new Date(r.t).getTime())) : 0;
    for (const r of rs) {
      const t = new Date(r.t);
      if (now - t < 864e5) continue; // too young to judge
      rows.push({ account: a.handle, views: r.views || 0, hour: t.getUTCHours(), day: Math.floor((t - first) / 864e5), variant: byCode[r.code]?.caption_variant || variantOf[norm(r.caption).slice(0, 30)] || null, trial: !!byCode[r.code]?.trial_reel, dur: r.dur || 0 });
    }
  }
  const accounts = P.accounts.map((a) => { const h = P.snaps[a.handle] || [], s = h[h.length - 1] || {}, p = h[h.length - 2];
    return { account: a.handle, phone: a.phone || null, character: a.char || null, followers: s.followers ?? null, followers_change: p ? (s.followers || 0) - (p.followers || 0) : null,
      reels: s.reels ?? null, total_views: s.views ?? null, avg_last5: s.avg5 ?? null, best: s.best || null, last_post: s.last || null, measured_at: s.t || null }; });
  return {
    note: "computed live from the account pool (reels older than 24 h); refresh the pool for fresh numbers",
    reels_counted: rows.length,
    by_post_hour_utc: group(rows, (r) => r.hour),
    by_account_age_day: group(rows, (r) => (r.day > 6 ? "D6+" : "D" + r.day)),
    by_caption_variant: group(rows.filter((r) => r.variant), (r) => r.variant),
    by_duration: group(rows, (r) => (r.dur < 15 ? "<15s" : r.dur <= 20 ? "15-20s" : r.dur <= 30 ? "21-30s" : ">30s")),
    by_phone: group(rows.map((r) => ({ ...r, phone: (P.accounts.find((a) => a.handle === r.account) || {}).phone || "?" })), (r) => r.phone),
    accounts,
  };
}
async function schedule(D, handle) {
  const P = await pool(), now = Date.now(), L = await loggedPosts();
  return P.accounts.filter((a) => !handle || a.handle === handle).map((a) => {
    const reels = (P.reels[a.handle] || []).filter((r) => r.t).sort((x, y) => String(x.t).localeCompare(String(y.t)));
    const first = reels.length ? new Date(reels[0].t).getTime() : null, last = reels.length ? new Date(reels[reels.length - 1].t).getTime() : null;
    const ageDays = first ? Math.floor((now - first) / DAY) : null;
    const in24 = reels.filter((r) => now - new Date(r.t) < DAY).length;
    const rule = ageDays == null || ageDays === 0 ? PLAYBOOK.cadence.day0 : ageDays === 1 ? PLAYBOOK.cadence.day1 : ageDays <= 4 ? PLAYBOOK.cadence.day2_4 : PLAYBOOK.cadence.after_day4;
    const maxPosts = typeof rule.posts === "number" ? rule.posts : 4, gap = (rule.min_gap_hours || 20) * 3.6e6;
    const earliest = Math.max(now, last ? last + gap : now, in24 >= maxPosts && reels.length ? new Date(reels[reels.length - maxPosts].t).getTime() + DAY : now);
    const c = a.char ? D.chars.find((x) => x.id === a.char) : null;
    const posted = new Set(reels.map((r) => norm(r.caption).slice(0, 30)));
    const usedVideos = new Set(L.map((p) => p.video_4k).filter(Boolean));
    const nextVideo = c ? c.videos.find((v) => v.video_4k && !usedVideos.has(v.video_4k) && !(v.caption && posted.has(norm(v.caption).slice(0, 30)))) || null : null;
    return { account: a.handle, phone: a.phone || null, character: a.char || null, account_age_days: ageDays, posts_last_24h: in24,
      rule_today: rule, next_post_at_utc: nextSlot(earliest),
      next_video: nextVideo ? { video_4k: nextVideo.video_4k, character: c.id, n: nextVideo.n, caption: nextVideo.caption, caption_variant: nextVideo.caption_variant } : null,
      note: !a.char ? "link this account to a character in the Accounts tab to get its next video" : (!nextVideo ? "no unposted video left for this character: generate more" : null) };
  });
}

// ---- shared queries (REST and MCP use the same functions) ----
const Q = {
  characters: (D, a = {}) => D.chars
    .filter((c) => (a.min_score == null || c.breakout_score >= +a.min_score) && (!a.media_buyer_only || c.flags.media_buyer) && (!a.with_videos || c.videos.length))
    .map(({ id, name, handle, profile_name, tagline, breakout_score, flags, images, videos, bio }) => ({ id, name, handle, profile_name, tagline, breakout_score, flags, bio, profile_picture: images.profile_picture, hd_image: images.hd_1080x1920, videos: videos.length })),
  character: (D, a) => D.chars.find((c) => c.id === a.id || c.handle === a.id) || null,
  videos: (D, a = {}) => D.chars.filter((c) => !a.character || c.id === a.character)
    .flatMap((c) => c.videos.map((v) => ({ character: c.id, name: c.name, handle: c.handle, ...v }))),
  sources: (D, a = {}) => ((D.data.live_sources || {}).items || [])
    .filter((s) => (!a.bucket || s.bucket === a.bucket) && (!a.business_only || s.biz))
    .map((s) => ({ ...s, clip: `${SITE}/clips/${s.id}.mp4`, thumb: `${SITE}/img/src/${s.id}.jpg` })),
  blocks: (D) => Object.keys(D.data),
  block: (D, a) => (a.block in D.data ? D.data[a.block] : null),
};

const TOOLS = [
  { name: "list_characters", description: "List all AI characters with breakout score, bio, profile picture, HD image and number of ready videos. Sorted by breakout score.",
    inputSchema: { type: "object", properties: { min_score: { type: "number", description: "Only characters with a breakout score >= this (0-100)" }, media_buyer_only: { type: "boolean" }, with_videos: { type: "boolean", description: "Only characters that already have generated videos" } } } },
  { name: "get_character", description: "Everything about one character: traits, GPT Image 2 prompt, bio, profile name, tracked bio link, location tag, captions, hashtags, images, profile picture, and every generated video (4K + 480p URLs, source clip, posting slot, caption).",
    inputSchema: { type: "object", properties: { id: { type: "string", description: "Character id (e.g. otto) or handle (e.g. herr.otto)" } }, required: ["id"] } },
  { name: "list_videos", description: "All generated videos ready to post (4K and 480p URLs, caption, posting slot, source), optionally for one character.",
    inputSchema: { type: "object", properties: { character: { type: "string", description: "Character id" } } } },
  { name: "list_sources", description: "Fresh source clips to copy with motion transfer: 'buzz' = under 48 h and rising, 'hit' = 2 to 7 days and already viral. Views, views per hour, scene, business fit, trimmed clip URL.",
    inputSchema: { type: "object", properties: { bucket: { type: "string", enum: ["buzz", "hit"] }, business_only: { type: "boolean" } } } },
  { name: "get_playbook", description: "Everything learned for posting: rules (UTC windows, cadence by account age, flops, captions, bios, video), live learnings from our own accounts (median views by post hour, account age, caption variant, duration, phone; per-account stats) and the research (honeymoon curve, cadence of top accounts).",
    inputSchema: { type: "object", properties: {} } },
  { name: "get_schedule", description: "For each Instagram account in the pool (or one handle): age in days, posts in the last 24 h, today's rule, next recommended post time (UTC) and the next unposted video with its caption.",
    inputSchema: { type: "object", properties: { account: { type: "string", description: "Instagram handle, e.g. prime_banwavebarry" } } } },
  { name: "get_knowledge", description: "The full posting knowledge pack (markdown): mission, golden rules, cadence, timing, video choice, captions, Instagram settings, monitoring, what never to do, research evidence, our results. Read it before planning posts.",
    inputSchema: { type: "object", properties: {} } },
  { name: "log_post", description: "Record a reel that was just posted, so the learnings and the schedule use real data. Call it after every post.",
    inputSchema: { type: "object", required: ["account"], properties: { account: { type: "string", description: "Instagram handle" }, video_4k: { type: "string", description: "the video_4k URL that was posted" },
      reel_url: { type: "string", description: "URL of the published reel" }, caption: { type: "string" }, posted_at: { type: "string", description: "ISO date, default now" }, trial_reel: { type: "boolean" }, phone: { type: "string" } } } },
  { name: "list_posts", description: "Posts logged by the posting tool (optionally for one account).", inputSchema: { type: "object", properties: { account: { type: "string" } } } },
  { name: "get_radar", description: "Live radar queue (clips scanned every 2 hours on TikTok and Instagram, ranked by velocity).", inputSchema: { type: "object", properties: {} } },
  { name: "get_insights", description: "Research data behind the system. Without 'block', returns the list of blocks (cadence, traits, scenes, honeymoon, tricks, wave, hitflop, accounts…). With 'block', returns that block.",
    inputSchema: { type: "object", properties: { block: { type: "string" } } } },
];

async function callTool(name, a) {
  const D = await load();
  switch (name) {
    case "list_characters": return Q.characters(D, a);
    case "get_character": return Q.character(D, a) || { error: `unknown character ${a.id}` };
    case "list_videos": return Q.videos(D, a);
    case "list_sources": return Q.sources(D, a);
    case "get_radar": return radar();
    case "get_playbook": return { rules: PLAYBOOK, learned: await learnings(D), research: { honeymoon: Q.block(D, { block: "honeymoon" }), cadence: Q.block(D, { block: "cadence" }) } };
    case "get_schedule": return schedule(D, a.account);
    case "get_knowledge": return { markdown: KNOWLEDGE_MD };
    case "log_post": return logPost(D, a);
    case "list_posts": return (await loggedPosts()).filter((p) => !a.account || p.account === String(a.account).replace(/^@/, "").toLowerCase());
    case "get_insights": return a.block ? (Q.block(D, a) ?? { error: `unknown block ${a.block}`, blocks: Q.blocks(D) }) : { blocks: Q.blocks(D) };
    default: throw { code: -32601, message: `unknown tool ${name}` };
  }
}

async function mcp(req) {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const msg = await req.json().catch(() => null);
  if (!msg) return json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } }, 400);
  const batch = Array.isArray(msg) ? msg : [msg];
  const out = [];
  for (const m of batch) {
    if (m.id === undefined) continue; // notifications
    try {
      let result;
      if (m.method === "initialize") result = { protocolVersion: m.params?.protocolVersion || "2025-06-18", capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "character-lab", version: "1.0.0" }, instructions: "AI character farm data: characters (bios, prompts, images, profile pictures), generated 4K videos, fresh source clips and research insights." };
      else if (m.method === "ping") result = {};
      else if (m.method === "tools/list") result = { tools: TOOLS };
      else if (m.method === "tools/call") {
        const r = await callTool(m.params?.name, m.params?.arguments || {});
        result = { content: [{ type: "text", text: JSON.stringify(r, null, 1) }], structuredContent: Array.isArray(r) ? { items: r } : r };
      } else throw { code: -32601, message: `unknown method ${m.method}` };
      out.push({ jsonrpc: "2.0", id: m.id, result });
    } catch (e) { out.push({ jsonrpc: "2.0", id: m.id, error: { code: e.code || -32603, message: e.message || String(e) } }); }
  }
  if (!out.length) return new Response(null, { status: 202 });
  return json(Array.isArray(msg) ? out : out[0]);
}

export default async (req) => {
  const ok = authorized(req);
  if (ok === null) return json({ error: "API disabled: API_KEY is not configured" }, 503);
  if (!ok) return json({ error: "missing or wrong API key" }, 401);
  const url = new URL(req.url);
  if (url.pathname === "/mcp") return mcp(req);
  const parts = url.pathname.replace(/^\/api\/v1\/?/, "").split("/").filter(Boolean);
  if (req.method === "POST" && parts[0] === "posts") {
    const body = await req.json().catch(() => null);
    if (!body) return json({ error: "JSON body required" }, 400);
    try { return json(await logPost(await load(), body)); } catch (e) { return json({ error: e.message || String(e) }, e.status || 500); }
  }
  if (req.method !== "GET") return json({ error: "method not allowed" }, 405);
  const a = Object.fromEntries(url.searchParams);
  for (const k of ["media_buyer_only", "with_videos", "business_only"]) if (k in a) a[k] = a[k] !== "false";
  const D = await load();
  const [r0, r1] = parts;
  if (!r0) return json({ name: "Character Lab API", version: 1,
    endpoints: { "GET /api/v1/characters": "?min_score=&media_buyer_only=&with_videos=", "GET /api/v1/characters/:id": "full character", "GET /api/v1/videos": "?character=",
      "GET /api/v1/sources": "?bucket=buzz|hit&business_only=", "GET /api/v1/radar": "live radar queue", "GET /api/v1/playbook": "posting rules learned", "GET /api/v1/schedule": "?account= next post time + next video per account", "GET /api/v1/knowledge": "full posting knowledge pack (markdown; ?format=md for raw text)", "POST /api/v1/posts": "log a post {account, video_4k, reel_url, caption, posted_at, trial_reel, phone}", "GET /api/v1/posts": "?account= logged posts", "GET /api/v1/data": "list of research blocks", "GET /api/v1/data/:block": "one block",
      "POST /mcp": "MCP server (tools: " + TOOLS.map((t) => t.name).join(", ") + ")" } });
  if (r0 === "characters") { if (!r1) return json(Q.characters(D, a)); const c = Q.character(D, { id: r1 }); return c ? json(c) : json({ error: "not found" }, 404); }
  if (r0 === "videos") return json(Q.videos(D, a));
  if (r0 === "sources") return json(Q.sources(D, a));
  if (r0 === "radar") return json(await radar());
  if (r0 === "playbook") return json({ rules: PLAYBOOK, learned: await learnings(D), research: { honeymoon: Q.block(D, { block: "honeymoon" }), cadence: Q.block(D, { block: "cadence" }) } });
  if (r0 === "schedule") return json(await schedule(D, a.account));
  if (r0 === "knowledge") return a.format === "md" ? new Response(KNOWLEDGE_MD, { headers: { "Content-Type": "text/markdown; charset=utf-8", "Cache-Control": "no-store" } }) : json({ markdown: KNOWLEDGE_MD });
  if (r0 === "posts") return json((await loggedPosts()).filter((p) => !a.account || p.account === a.account.replace(/^@/, "").toLowerCase()));
  if (r0 === "data") { if (!r1) return json({ blocks: Q.blocks(D) }); const b = Q.block(D, { block: r1 }); return b != null ? json(b) : json({ error: "not found", blocks: Q.blocks(D) }, 404); }
  return json({ error: "not found" }, 404);
};
