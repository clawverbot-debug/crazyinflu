// On-demand generation for the team: GPT Image 2 (kie.ai) and Apify Instagram scans, paid with the owner's keys
// (KIE_API_KEY, APIFY_TOKEN stay on the server). Every call is logged per person with daily quotas.
// Higgsfield videos are NOT here: Higgsfield has no API key (personal OAuth login) -> share a Higgsfield team workspace instead.
import { getStore } from "@netlify/blobs";
import { monthSpent } from "./radar-core.mjs";

const KIE = "https://api.kie.ai/api/v1/jobs";
const APIFY = "https://api.apify.com/v2";
const LIMITS = { image: Number(process.env.GEN_IMG_DAILY || 40), scan: Number(process.env.GEN_SCAN_DAILY || 3) };
const store = () => getStore({ name: "usage", consistency: "strong" });
const today = () => new Date().toISOString().slice(0, 10);
const err = (status, message) => ({ status, message });

async function spend(who, kind, detail) {
  const s = store(), k = `${today()}:${who}`;
  const u = (await s.get(k, { type: "json" })) || { image: 0, scan: 0 };
  if (who !== "owner" && (u[kind] || 0) >= LIMITS[kind]) throw err(429, `daily ${kind} quota reached for ${who} (${LIMITS[kind]}/day)`);
  u[kind] = (u[kind] || 0) + 1; await s.setJSON(k, u);
  const log = (await s.get("log", { type: "json" })) || [];
  log.push({ t: new Date().toISOString(), who, kind, ...detail }); await s.setJSON("log", log.slice(-3000));
}
export async function usage(who) {
  const s = store(); const mine = (await s.get(`${today()}:${who}`, { type: "json" })) || { image: 0, scan: 0 };
  const log = (await s.get("log", { type: "json" })) || [];
  return { who, today: mine, limits: who === "owner" ? "unlimited" : LIMITS, recent: (who === "owner" ? log : log.filter((x) => x.who === who)).slice(-50) };
}
async function kie(path, body) {
  const key = process.env.KIE_API_KEY; if (!key) throw err(503, "KIE_API_KEY not configured");
  const r = await fetch(`${KIE}/${path}`, { method: body ? "POST" : "GET", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  return r.json();
}
export async function generateImage(who, b) {
  const prompt = String(b.prompt || "").trim(); if (prompt.length < 3) throw err(400, "prompt is required");
  const refs = (Array.isArray(b.ref_urls) ? b.ref_urls : b.ref_url ? [b.ref_url] : []).filter((u) => /^https:\/\//.test(u)).slice(0, 4);
  const input = { prompt: prompt.slice(0, 4000), aspect_ratio: ["1:1", "9:16", "16:9", "3:4", "4:3"].includes(b.aspect_ratio) ? b.aspect_ratio : "9:16", resolution: ["1K", "2K"].includes(b.resolution) ? b.resolution : "2K" };
  if (refs.length) input.input_urls = refs;
  await spend(who, "image", { prompt: prompt.slice(0, 120), refs: refs.length });
  const d = await kie("createTask", { model: refs.length ? "gpt-image-2-image-to-image" : "gpt-image-2-text-to-image", input });
  if (d.code !== 200) throw err(502, `kie: ${d.msg || "create failed"}`);
  return { task_id: d.data.taskId, status_url: `/api/v1/generate/image/${d.data.taskId}`, note: "poll the status_url every ~6 s (1-3 min)" };
}
export async function imageStatus(id) {
  if (!/^[a-zA-Z0-9]{8,64}$/.test(id)) throw err(400, "bad task id");
  const d = (await kie(`recordInfo?taskId=${id}`)).data || {};
  const urls = d.state === "success" ? (JSON.parse(d.resultJson || "{}").resultUrls || []) : [];
  return { task_id: id, state: d.state || "unknown", urls, error: d.failMsg || null };
}
export async function startScan(who, b) {
  const token = process.env.APIFY_TOKEN; if (!token) throw err(503, "APIFY_TOKEN not configured");
  const tags = (Array.isArray(b.hashtags) ? b.hashtags : String(b.hashtags || "").split(",")).map((t) => String(t).replace(/^#/, "").trim().toLowerCase()).filter((t) => /^[a-z0-9_]{2,40}$/.test(t)).slice(0, 12);
  if (!tags.length) throw err(400, "hashtags is required (array, max 12)");
  const per = Math.min(30, Math.max(5, Number(b.per_tag) || 20));
  const spent = await monthSpent(token).catch(() => null);
  if (spent != null && spent >= Number(process.env.RADAR_MAX_USD || 380)) throw err(402, `Apify budget reached this month (${spent.toFixed(2)} $)`);
  const maxUsd = Math.min(2, tags.length * per * 0.0025 + 0.1);
  await spend(who, "scan", { tags, per_tag: per, max_usd: +maxUsd.toFixed(2) });
  const r = await fetch(`${APIFY}/acts/apify~instagram-hashtag-scraper/runs?token=${token}&maxTotalChargeUsd=${maxUsd.toFixed(2)}`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hashtags: tags, resultsLimit: per, resultsType: "reels" }) });
  const run = (await r.json()).data; if (!run?.id) throw err(502, "Apify run did not start");
  return { scan_id: run.id, tags, per_tag: per, max_cost_usd: +maxUsd.toFixed(2), status_url: `/api/v1/scan/${run.id}`, note: "poll the status_url every ~15 s (1-3 min)" };
}
export async function scanStatus(id, b = {}) {
  const token = process.env.APIFY_TOKEN; if (!token) throw err(503, "APIFY_TOKEN not configured");
  if (!/^[a-zA-Z0-9]{8,32}$/.test(id)) throw err(400, "bad scan id");
  const run = (await (await fetch(`${APIFY}/actor-runs/${id}?token=${token}`)).json()).data;
  if (!run) throw err(404, "unknown scan");
  if (run.status === "READY" || run.status === "RUNNING") return { scan_id: id, status: run.status };
  const items = run.status === "SUCCEEDED" ? await (await fetch(`${APIFY}/datasets/${run.defaultDatasetId}/items?token=${token}&clean=1`)).json() : [];
  const maxAge = Number(b.max_age_hours) || 72, now = Date.now();
  const out = items.filter((x) => x.shortCode && x.timestamp).map((x) => {
    const age = (now - Date.parse(x.timestamp)) / 3.6e6, v = x.videoPlayCount || x.videoViewCount || 0;
    return { url: x.url, owner: x.ownerUsername, views: v, age_h: +age.toFixed(1), views_per_hour: Math.round(v / Math.max(age, 1)), duration_s: Math.round(x.videoDuration || 0), caption: (x.caption || "").slice(0, 140), video: x.videoUrl || null, thumb: x.displayUrl || null };
  }).filter((x) => x.age_h <= maxAge).sort((a, b) => b.views_per_hour - a.views_per_hour);
  return { scan_id: id, status: run.status, cost_usd: run.usageTotalUsd ?? null, results: out.slice(0, 60) };
}
