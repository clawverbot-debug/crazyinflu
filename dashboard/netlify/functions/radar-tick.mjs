// Radar tick (every 30 min): collects finished scans; starts a new scan ONLY while the radar is active
// (settings.activeUntil in the future) or when "scan now" was requested and could not start immediately.
// Env: APIFY_TOKEN, RADAR_EVERY_MIN (default 120), RADAR_MAX_USD (default 380: no scan once the Apify month reaches it).
import { getStore } from "@netlify/blobs";
import { collect, startScan, monthSpent } from "../lib/radar-core.mjs";

export const config = { schedule: "*/30 * * * *" };

export default async () => {
  const token = process.env.APIFY_TOKEN;
  if (!token) return new Response("APIFY_TOKEN missing", { status: 500 });
  const store = getStore({ name: "radar", consistency: "strong" });
  const state = (await store.get("state", { type: "json" })) || { runs: [], lastStart: 0, log: [] };
  const settings = (await store.get("settings", { type: "json" })) || {};
  const cands = (await store.get("candidates", { type: "json" })) || {};
  const hadRuns = (state.runs || []).length;
  if (hadRuns) await collect(state, cands, token);

  const active = settings.activeUntil && Date.now() < new Date(settings.activeUntil).getTime();
  const every = Number(process.env.RADAR_EVERY_MIN || 120) * 60e3;
  const due = (active && Date.now() - (state.lastStart || 0) > every) || settings.scanNow;
  if (due && !(state.runs || []).length) {
    const spent = await monthSpent(token);
    state.spent = spent;
    if (spent != null && spent >= Number(process.env.RADAR_MAX_USD || 380)) state.stopped = `budget (${spent.toFixed(2)} $)`;
    else { state.stopped = null; await startScan(state, settings, token); }
    if (settings.scanNow) await store.setJSON("settings", { ...settings, scanNow: false });
  }
  if (!hadRuns && !due) return new Response("idle (radar off)"); // nothing to do: no write, no cost

  for (const [k, c] of Object.entries(cands)) if ((Date.now() - new Date(c.created)) / 3.6e6 > 96 && c.status !== "done") delete cands[k];
  state.updated = new Date().toISOString();
  await store.setJSON("candidates", cands);
  await store.setJSON("state", state);
  return new Response(`ok: ${Object.keys(cands).length} candidates, ${(state.runs || []).length} runs pending`);
};
