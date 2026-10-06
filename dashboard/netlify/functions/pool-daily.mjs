// Daily automatic refresh of the account pool (07:00 UTC), on top of the manual "Refresh" button.
// Starts the same Apify scrapes as POST /api/pool {action:"refresh"}; the next page load or GET collects them.
// Skipped when the Apify month has reached RADAR_MAX_USD (default 380 $).
export const config = { schedule: "0 7 * * *" };

export default async (req) => {
  const token = process.env.APIFY_TOKEN, key = process.env.RADAR_KEY;
  if (!token || !key) return new Response("not configured", { status: 503 });
  try {
    const spent = (await (await fetch(`https://api.apify.com/v2/users/me/limits?token=${token}`)).json()).data.current.monthlyUsageUsd;
    if (spent >= Number(process.env.RADAR_MAX_USD || 380)) return new Response(`skipped: budget ${spent}`);
  } catch (e) {}
  const base = process.env.URL || "https://character-lab-research.netlify.app";
  const post = (body) => fetch(`${base}/api/pool`, { method: "POST", headers: { "Content-Type": "application/json", "x-radar-key": key }, body: JSON.stringify(body) });
  const r = await post({ action: "refresh" });
  return new Response(`refresh: ${r.status}`);
};
