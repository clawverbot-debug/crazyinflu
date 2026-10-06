// Shared radar logic (used by radar-tick and radar-api). The radar is OFF by default and only scrapes on demand:
// "scan now" (one scan) or "active for N hours" (one scan every RADAR_EVERY_MIN while active).
// Cost control, measured on 5 Oct 2026: TikTok profiles + hashtags = 2 useful clips out of 204 paid results ($0.47),
// Instagram hashtags = 35 / 275 ($0.58), with 5 tags at 0. So: Instagram tags only by default, each tag's yield is
// tracked, a tag with 0 useful clip over 2 scans is paused, and paused tags get one retry a day.
export const API = "https://api.apify.com/v2";
export const MAX_AGE_H = 48;
const ROCKET = { maxAgeH: 6, minViewsPerHour: 5000 };
// Audience = men with an online business (5 Oct: dance clips pull a mostly female audience). Clips where ONE man moves
// in a status / money / sport setting: luxury walks, supercars, private jets, gym, boxing, golf, football, padel, CEO entrances.
// The 6 tags that already produced clips stay first; yield tracking pauses whatever brings nothing.
export const AUDIENCES = {
  men_business: ["luxurylifestyle", "dubailife", "richlifestyle", "dubailifestyle", "billionairelifestyle", "habibi",
    "entrepreneurlife", "ceolife", "supercars", "privatejet", "gymmotivation", "boxingtraining", "golfswing",
    "footballskills", "goalcelebration", "padel", "sigmamale", "moneymotivation"],
  // media buying / Meta ads / e-commerce: marketer skits and reactions (ROAS up, ad account banned, sale notifications),
  // office and laptop-lifestyle scenes — the exact world of the Prime Ads audience
  media_buying: ["mediabuyer", "facebookads", "metaads", "adsmanager", "performancemarketing", "digitalmarketing",
    "ecommerce", "dropshipping", "shopify", "affiliatemarketing", "marketingagency", "agencylife",
    // scenes of that world where one man moves: affiliate conferences, sales floors, office pranks, trading desks, laptop life
    "fbads", "mediabuying", "clickbank", "clickfunnels", "metaadsexpert",
    "affiliateworld", "salesteam", "officeprank", "tradinglife", "laptoplifestyle", "businessconference", "startuplife"],
  dance: ["weddingdance", "dancingdad", "oldmandancing", "partydance", "uncledance", "dancechallenge", "weddingvibes", "funnydance"],
};
AUDIENCES.men_business = [...AUDIENCES.men_business, ...AUDIENCES.media_buying];
export const IG_TAGS = [...AUDIENCES.men_business, ...AUDIENCES.dance];
export const IG_PER_TAG = 20;
// TikTok search (opt-in): recent results are rare, so a few targeted queries only
export const TT_QUERIES = { men_business: ["dubai rich lifestyle", "billionaire walking to his car", "gym motivation man", "golf swing funny",
    "media buyer life", "facebook ads account banned reaction", "roas celebration", "shopify sale notification reaction", "dropshipping winning product"],
  dance: ["wedding dance uncle", "dancing in public funny", "office party dance"] };

const igItem = (r) => ({
  id: "ig:" + r.shortCode, platform: "instagram", owner: r.ownerUsername, url: r.url, thumb: r.displayUrl, video: r.videoUrl || null,
  views: r.videoPlayCount || r.videoViewCount || 0, likes: r.likesCount || 0, shares: 0, comments: r.commentsCount || 0,
  created: r.timestamp, duration: r.videoDuration || 0, caption: (r.caption || "").slice(0, 140),
  sound: [r.musicInfo?.artist_name, r.musicInfo?.song_name].filter(Boolean).join(" - "),
  src: "#" + String(r.inputUrl || "").replace(/\/$/, "").split("/").pop(),
});
const ttItem = (v) => ({
  id: "tt:" + v.id, platform: "tiktok", owner: v.authorMeta?.name, url: v.webVideoUrl,
  thumb: v.videoMeta?.coverUrl, views: v.playCount || 0, likes: v.diggCount || 0, shares: v.shareCount || 0,
  comments: v.commentCount || 0, created: v.createTimeISO, duration: v.videoMeta?.duration || 0,
  caption: (v.text || "").slice(0, 140), sound: [v.musicMeta?.musicAuthor, v.musicMeta?.musicName].filter(Boolean).join(" - "),
  src: "tt:" + (v.input || v.searchQuery || "?"),
});

function score(c) {
  const ageH = Math.max((Date.now() - new Date(c.created)) / 3.6e6, 1);
  const vel = c.views / Math.pow(ageH, 0.8);
  const eng = c.views ? (c.likes + 3 * c.shares + 2 * c.comments) / c.views : 0;
  return { ageH: Math.round(ageH * 10) / 10, score: Math.round(vel * (1 + Math.min(eng * 5, 1))) };
}

export function ingest(items, kind, cands, yieldStats) {
  const scan = {};
  for (const raw of items || []) {
    const c = kind === "ig" ? igItem(raw) : ttItem(raw);
    const y = (scan[c.src] ||= { items: 0, kept: 0 });
    y.items++;
    if (!c.url || !c.created) continue;
    const { ageH, score: s } = score(c);
    if (ageH > MAX_AGE_H || c.duration < 5 || c.duration > 45 || c.views < 10000) continue;
    y.kept++;
    c.vph = Math.round(c.views / ageH);
    c.rocket = ageH <= ROCKET.maxAgeH && c.vph >= ROCKET.minViewsPerHour;
    const prev = cands[c.id];
    cands[c.id] = { ...(prev || { status: "new", first_seen: new Date().toISOString() }), ...c, ageH, score: s,
      status: prev?.status || "new", character: prev?.character, result: prev?.result };
  }
  for (const [src, y] of Object.entries(scan)) {
    const Y = (yieldStats[src] ||= { scans: 0, items: 0, kept: 0, zeroStreak: 0 });
    Y.scans++; Y.items += y.items; Y.kept += y.kept; Y.zeroStreak = y.kept ? 0 : Y.zeroStreak + 1; Y.last = new Date().toISOString();
  }
}

async function startRun(actor, input, token) {
  const r = await fetch(`${API}/acts/${actor}/runs?token=${token}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
  return (await r.json()).data?.id;
}

// tags to scrape now: productive tags, plus paused ones once a day (a tag can come back)
export function activeTags(yieldStats, audience = "men_business") {
  const day = 864e5;
  const pool = audience === "both" ? IG_TAGS : AUDIENCES[audience] || AUDIENCES.men_business;
  return pool.filter((t) => { const Y = yieldStats["#" + t]; return !Y || Y.zeroStreak < 2 || Date.now() - new Date(Y.last) > day; });
}

export async function startScan(state, settings, token) {
  const tags = activeTags(state.yield || {}, settings.audience);
  const runs = [];
  if (tags.length) { const ig = await startRun("apify~instagram-hashtag-scraper", { hashtags: tags, resultsLimit: IG_PER_TAG, resultsType: "reels" }, token); if (ig) runs.push({ id: ig, kind: "ig", tags: tags.length }); }
  if (settings.tiktok) { const tt = await startRun("clockworks~tiktok-scraper", { searchQueries: settings.audience === "dance" ? TT_QUERIES.dance : TT_QUERIES.men_business, resultsPerPage: 10, shouldDownloadVideos: false, shouldDownloadCovers: false }, token); if (tt) runs.push({ id: tt, kind: "tt" }); }
  state.runs = [...(state.runs || []), ...runs];
  state.lastStart = Date.now();
  return runs;
}

export async function collect(state, cands, token) {
  const pending = [];
  state.yield ||= {}; state.costs ||= [];
  for (const run of state.runs || []) {
    const j = await (await fetch(`${API}/actor-runs/${run.id}?token=${token}`)).json();
    const st = j.data?.status;
    if (st === "SUCCEEDED") {
      const items = await (await fetch(`${API}/datasets/${j.data.defaultDatasetId}/items?token=${token}&clean=1`)).json();
      const before = Object.keys(cands).length;
      ingest(items, run.kind, cands, state.yield);
      state.costs.unshift({ t: new Date().toISOString(), kind: run.kind, usd: Math.round((j.data.usageTotalUsd || 0) * 1000) / 1000, items: items.length, added: Object.keys(cands).length - before });
      state.log = [{ t: new Date().toISOString(), kind: run.kind, items: items.length }, ...(state.log || [])].slice(0, 30);
    } else if (st === "READY" || st === "RUNNING") pending.push(run);
  }
  state.runs = pending;
  state.costs = state.costs.slice(0, 40);
}

export async function monthSpent(token) {
  try { return (await (await fetch(`${API}/users/me/limits?token=${token}`)).json()).data.current.monthlyUsageUsd; } catch (e) { return null; }
}
