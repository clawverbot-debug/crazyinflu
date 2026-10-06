// Radar API. GET /api/radar → queue + settings + cost/yield report (also collects finished scans, so results show up fast).
// POST /api/radar (header x-radar-key = env RADAR_KEY):
//   {action:"scan"} one scan now · {action:"activate", hours} scan every 2 h for N hours · {action:"stop"}
//   {action:"approve"|"skip"|"reset", id, character} · {action:"done"|"fail", id, result, error} · {action:"settings", settings}
import { getStore } from "@netlify/blobs";
import { collect, startScan, monthSpent, activeTags, IG_TAGS, IG_PER_TAG } from "../lib/radar-core.mjs";

export const config = { path: "/api/radar" };

const DEFAULTS = { auto: false, dailyCap: 6, minScore: 20000, characters: ["barry", "nico"], activeUntil: null, tiktok: false, audience: "men_business" };
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

export default async (req) => {
  const store = getStore({ name: "radar", consistency: "strong" });
  const cands = (await store.get("candidates", { type: "json" })) || {};
  const state = (await store.get("state", { type: "json" })) || {};
  const settings = { ...DEFAULTS, ...((await store.get("settings", { type: "json" })) || {}) };

  if (req.method === "GET") {
    if ((state.runs || []).length && process.env.APIFY_TOKEN) {
      await collect(state, cands, process.env.APIFY_TOKEN);
      if (!state.runs.length) { state.updated = new Date().toISOString(); await store.setJSON("candidates", cands); await store.setJSON("state", state); }
    }
    const E = (await store.get("enrich", { type: "json" })) || {};
    const list = Object.values(cands).map((c) => ({ ...c, desc: E[c.id]?.desc, jev: E[c.id]?.jev, fit: E[c.id]?.fit, track: E[c.id]?.track })).sort((a, b) => b.score - a.score);
    // calibration: rated clips (also those gone from the queue) bucketed by Jev composite → what happened next
    const rated = Object.entries(E).filter(([k, e]) => k !== "__run" && e.jev && e.track?.length).map(([, e]) => e);
    const B = [[0.5, 1.01, "≥ 50"], [0.25, 0.5, "25–49"], [0, 0.25, "< 25"]].map(([lo, hi, label]) => {
      const g = rated.filter((e) => e.jev.composite >= lo && e.jev.composite < hi);
      const growth = g.map((e) => e.track[e.track.length - 1].views / Math.max(e.jev.views, 1)).sort((x, y) => x - y);
      return { label, n: g.length, median_growth: growth.length ? Math.round(growth[growth.length >> 1] * 100) / 100 : null,
        hit_rate: g.length ? Math.round(g.filter((e) => e.track[e.track.length - 1].views >= 500000).length / g.length * 100) : null };
    });
    return json({ updated: state.updated || null, stopped: state.stopped || null, spent: state.spent ?? null, runs: state.runs || [], log: state.log || [], settings, candidates: list, calibration: B, enrich: E.__run || null,
      active: !!(settings.activeUntil && Date.now() < new Date(settings.activeUntil)), costs: state.costs || [], yield: state.yield || {},
      next_scan: { tags: activeTags(state.yield || {}, settings.audience), est_usd: Math.round(activeTags(state.yield || {}, settings.audience).length * IG_PER_TAG * 0.0021 * 100) / 100 + (settings.tiktok ? 0.25 : 0) } });
  }
  if (req.method !== "POST") return json({ error: "method" }, 405);
  if (!process.env.RADAR_KEY || req.headers.get("x-radar-key") !== process.env.RADAR_KEY) return json({ error: "bad key" }, 401);
  const body = await req.json().catch(() => ({}));
  if (body.action === "scan" || body.action === "activate" || body.action === "stop") {
    const s = { ...settings };
    if (body.action === "stop") { s.activeUntil = null; s.scanNow = false; }
    if (body.action === "activate") s.activeUntil = new Date(Date.now() + Math.min(Math.max(Number(body.hours) || 6, 1), 72) * 3.6e6).toISOString();
    let started = false, why = null;
    if (body.action !== "stop" && process.env.APIFY_TOKEN) {
      const spent = await monthSpent(process.env.APIFY_TOKEN);
      if (spent != null && spent >= Number(process.env.RADAR_MAX_USD || 380)) why = `budget (${spent.toFixed(2)} $)`;
      else if ((state.runs || []).length) why = "a scan is already running";
      else { await startScan(state, s, process.env.APIFY_TOKEN); started = true; state.spent = spent; await store.setJSON("state", state); }
    }
    await store.setJSON("settings", s);
    return json({ ok: true, started, why, settings: s });
  }
  if (body.action === "settings") {
    const s = { ...settings, ...(body.settings || {}) };
    await store.setJSON("settings", s);
    return json({ ok: true, settings: s });
  }
  const c = cands[body.id];
  if (!c) return json({ error: "unknown id" }, 404);
  if (body.action === "approve") Object.assign(c, { status: "approved", character: body.character || c.character });
  else if (body.action === "skip") c.status = "skipped";
  else if (body.action === "reset") Object.assign(c, { status: "new", result: null, error: null });
  else if (body.action === "running") Object.assign(c, { status: "running", character: body.character || c.character });
  else if (body.action === "done") Object.assign(c, { status: "done", result: body.result, done_at: new Date().toISOString() });
  else if (body.action === "fail") Object.assign(c, { status: "failed", error: body.error });
  else return json({ error: "unknown action" }, 400);
  await store.setJSON("candidates", cands);
  return json({ ok: true, candidate: c });
};
