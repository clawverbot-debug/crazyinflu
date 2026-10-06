// Radar enrichment (runs at :15 and :45, between radar-tick scans). Never triggers a generation.
// 1. Vision: one factual sentence per new clip from its cover image (kie.ai Gemini 3.8 Flash, env KIE_API_KEY).
// 2. Jev shadow decision on clips that have a description (see the notes below), then character fit for the best ones.
// 3. Outcome tracking: views of every rated clip at each scan, so Jev's scores can be checked against what happened.
// Results live in the Blobs key "enrich" ({id: {desc, jev, fit, track}}), merged into the queue by radar-api.
import { getStore } from "@netlify/blobs";

export const config = { schedule: "15,45 * * * *" };
const MAX_AGE_H = 48;

const VISION_PROMPT = "Describe this video cover in one factual sentence for a motion-transfer source finder: how many people, is one main person fully visible and moving or dancing, the setting (wedding, street, office, luxury car, beach…), real phone footage or AI/cartoon/edited, big text overlay or not.";
// Vision through kie.ai (Gemini 3.8 Flash, ~0.06 kie credit per clip, 10-12 s), env KIE_API_KEY.
let LAST_ERR = null;
async function describeOpenAI(c, img) {
  const r = await fetch("https://api.openai.com/v1/responses", { method: "POST", signal: AbortSignal.timeout(15000),
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gpt-5.4-nano", reasoning: { effort: "none" }, max_output_tokens: 160,
      input: [{ role: "user", content: [{ type: "input_text", text: VISION_PROMPT }, { type: "input_image", image_url: img }] }] }) });
  const j = await r.json();
  if (j.error) LAST_ERR = `openai ${r.status}: ${String(j.error.message || "").slice(0, 120)}`;
  return (j.output_text || (j.output || []).flatMap((o) => o.content || []).map((x) => x.text).filter(Boolean).join(" ") || "").trim() || null;
}
// kie.ai first (Thibault's choice), OpenAI gpt-5.4-nano as fallback when only OPENAI_API_KEY is set.
async function describe(c) {
  const key = process.env.KIE_API_KEY;
  if (!c.thumb) return null;
  if (!key && process.env.OPENAI_API_KEY) {
    try {
      const b = await fetch(c.thumb, { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(4000) });
      if (!b.ok) { LAST_ERR = `thumb ${b.status}`; return null; }
      const d = await describeOpenAI(c, `data:${b.headers.get("content-type") || "image/jpeg"};base64,${Buffer.from(await b.arrayBuffer()).toString("base64")}`);
      return d ? d.slice(0, 400) : null;
    } catch (e) { LAST_ERR = `exception ${String(e.message || e).slice(0, 100)}`; return null; }
  }
  if (!key) return null;
  try {
    const b = await fetch(c.thumb, { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(4000) });
    if (!b.ok) return null;
    const data = Buffer.from(await b.arrayBuffer()).toString("base64");
    const r = await fetch("https://api.kie.ai/gemini/v1/models/gemini-3-8-flash:streamGenerateContent", { method: "POST", signal: AbortSignal.timeout(17000),
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ stream: false, contents: [{ role: "user", parts: [{ text: VISION_PROMPT }, { inline_data: { mime_type: b.headers.get("content-type") || "image/jpeg", data } }] }],
        generationConfig: { maxOutputTokens: 1024, thinkingConfig: { thinkingBudget: 0 } } }) });
    const j = await r.json();
    const out = (Array.isArray(j) ? j : [j]).flatMap((x) => x.candidates || []).flatMap((x) => x.content?.parts || []).map((p) => p.text).filter(Boolean).join("").trim();
    return out ? out.slice(0, 400) : null;
  } catch (e) { return null; }
}

// Jev (TypeSafe) in shadow mode: ranks each new clip and logs its decision; it never triggers a generation.
// Built on the documented weak spots of jev-1.13 (docs.typesafe.ai/model-jaggedness, AnthusAI/Jev-Calibration):
// - numbers are bucketed in code (Jev is weak at arithmetic), only text it can judge goes in the state;
// - several narrow yes/no questions (Noul is the best-calibrated primitive) instead of one broad verdict, combined in code;
// - the verdict defaults to skip and has a "not enough info" exit; Choice leans to the first option, so skip comes first;
// - character fit = one Noul per character (a single Choice collapsed onto 2 characters), ranked in code;
// - model pinned so thresholds stay valid. Every answer is logged to tune thresholds against real outcomes.
const JEV_MODEL = "jev-1.13.0";
const JEV_SCHEMA = 3; // bump to re-rate clips when the questions change
const Q_CLIP = {
  transferable: { type: "noul", instructions: "Does `clip` (see `clip.description`) show one performer whose body movement is the hook, so it would still work if that person were replaced by a different character doing the same moves?",
    criteria: { true: "Single main performer; a dance, gesture or physical gag carries the clip", false: "The hook is speech, text overlay, a famous person, a group, a product, scenery or editing" } },
  talking: { type: "noul", instructions: "Is `clip` mainly someone talking to the camera or explaining something?" },
  synthetic: { type: "noul", instructions: "Is `clip` an AI-generated, CGI, cartoon or animated video rather than real phone footage of real people?" },
  audio_dependent: { type: "noul", instructions: "Does `clip` only work because of its spoken audio or lyrics, so it would lose its point with another character?" },
  male_business: { type: "noul", instructions: "Would `clip` mainly appeal to men who run an online business (media buyers, Meta/Facebook advertisers, e-commerce and dropshipping founders) or men interested in money, luxury, cars or sport, rather than to a mostly female audience?",
    criteria: { true: "Media buying, Meta ads, ROAS, ad accounts, e-commerce sales, agency or office life, laptop lifestyle, status, money, luxury cars, private jets, gym, boxing, golf, football, a man showing off", false: "Mostly beauty, fashion for women, girl dance trends, babies, romance, pets" } },
  verdict: { type: "choice", instructions: { question: "What should we do with `clip` as a source for an AI-character motion-transfer video?", rule: "Default to skip unless the movement alone would make a stranger stop scrolling." },
    criteria: { skip: { what: "Typical or weak clip", examples: ["talking head", "meme text", "slideshow", "group with no main person"] }, not_enough_info: "The caption and sound are too vague to judge",
      watch: "Promising but unproven", copy_now: { what: "Exceptional, movement-driven, easy to transfer, already spreading fast", not_for: "Merely good clips" } } },
};
const bucket = (c, all) => {
  const rank = all.filter((x) => x.vph > c.vph).length / Math.max(all.length, 1);
  return { velocity: rank < 0.05 ? "top 5% of today's clips" : rank < 0.2 ? "top 20% of today's clips" : rank < 0.5 ? "above median" : "below median",
    age: c.ageH < 6 ? "under 6 hours" : c.ageH < 24 ? "under a day" : "1 to 2 days", platform: c.platform };
};
async function jevCall(state, questions) {
  const key = process.env.TYPESAFE_API_KEY;
  if (!key) return null;
  const r = await fetch("https://api.typesafe.ai/v1/systemone", { method: "POST", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ state, model: JEV_MODEL, questions }), signal: AbortSignal.timeout(9000) });
  return (await r.json()).answers || null;
}
let CHARS = null;
async function characters() {
  if (CHARS) return CHARS;
  try {
    const d = await (await fetch("https://character-lab-research.netlify.app/characters.json")).json();
    CHARS = d.characters.map((c) => ({ id: c.id, name: c.name, look: `${c.tagline.en}; ${c.traits.body || ""} ${c.traits.outfit || ""}`.trim(), role: c.role, media_buyer: c.flags.media_buyer }));
  } catch (e) { CHARS = []; }
  return CHARS;
}
async function jev(c, all) {
  const t = Date.now();
  const state = { clip: { description: c.desc || "unknown", caption: c.caption, sound: c.sound, owner: c.owner, duration_s: Math.round(c.duration), ...bucket(c, all) } };
  try {
    const a = await jevCall(state, Q_CLIP);
    if (!a) return null;
    const p = (k) => a[k]?.noul ?? 0;
    const vel = { "top 5% of today's clips": 1, "top 20% of today's clips": 0.75, "above median": 0.45, "below median": 0.2 }[state.clip.velocity];
    // composite in code: movement-transferable × not talking × real footage × not audio-led × speed
    // audience weight: Thibault targets men with an online business, so clips that appeal to them count up to 2x more
    const composite = Math.round(Math.min(1, p("transferable") * (1 - p("talking")) * (1 - p("synthetic")) * (1 - 0.5 * p("audio_dependent")) * vel * (0.5 + p("male_business"))) * 100) / 100;
    return { model: JEV_MODEL, schema: JEV_SCHEMA, verdict: a.verdict?.choice, p_copy: a.verdict?.probabilities?.copy_now ?? 0, confidence: a.verdict?.confidence ?? null,
      transferable: p("transferable"), male_business: p("male_business"), talking: p("talking"), synthetic: p("synthetic"), audio_dependent: p("audio_dependent"), composite, ms: Date.now() - t, at: new Date().toISOString() };
  } catch (e) { return null; }
}
async function jevFit(c) {
  const cs = await characters();
  if (!cs.length) return null;
  const q = Object.fromEntries(cs.map((x) => [`fit_${x.id}`, { type: "noul", instructions: { character: { name: x.name, look: x.look, role: x.role, targets_media_buyers: x.media_buyer },
    question: "Would `character` be a believable, funny replacement for the main performer of `clip`, given the scene and audience implied by the caption?" } }]));
  try {
    const a = await jevCall({ clip: { description: c.desc || "unknown", caption: c.caption, sound: c.sound } }, q);
    if (!a) return null;
    const ranked = cs.map((x) => ({ id: x.id, p: a[`fit_${x.id}`]?.noul ?? 0 })).sort((x, y) => y.p - x.p);
    return ranked[0].p < 0.3 ? [] : ranked.slice(0, 3);
  } catch (e) { return null; }
}


export default async () => {
  const started = Date.now();
  const left = () => 26000 - (Date.now() - started);
  const store = getStore({ name: "radar", consistency: "strong" });
  const cands = (await store.get("candidates", { type: "json" })) || {};
  const E = (await store.get("enrich", { type: "json" })) || {};
  const fresh = Object.values(cands).filter((c) => c.ageH <= MAX_AGE_H).sort((a, b) => b.score - a.score);
  const now = new Date().toISOString();
  // outcome tracking for everything already rated (cheap: no API call)
  for (const c of Object.values(cands)) if (E[c.id]?.jev) {
    const tr = (E[c.id].track ||= []);
    if (!tr.length || tr[tr.length - 1].views !== c.views) tr.push({ t: now, views: c.views, ageH: c.ageH });
    E[c.id].track = tr.slice(-40);
  }
  // 1. vision descriptions, 8 at a time, best clips first
  const vision = !!(process.env.KIE_API_KEY || process.env.OPENAI_API_KEY);
  const provider = vision ? (process.env.KIE_API_KEY ? "kie" : "openai") : "off";
  // a new vision provider gets a fresh try on clips the previous one could not describe
  if (E.__run && E.__run.vision !== provider) for (const [k, e] of Object.entries(E)) if (k !== "__run") { delete e.descFailed; delete e.descTry; }
  const needDesc = vision ? fresh.filter((c) => !E[c.id]?.desc && !E[c.id]?.descFailed).slice(0, 12) : [];
  for (let i = 0; i < needDesc.length && left() > 20000; i += 12) {
    const res = await Promise.all(needDesc.slice(i, i + 12).map(describe));
    res.forEach((d, k) => { const id = needDesc[i + k].id; E[id] = { ...(E[id] || {}), ...(d ? { desc: d } : (E[id]?.descTry ? { descFailed: true } : { descTry: 1 })) }; });
  }
  // 2. Jev on described clips
  for (const c of fresh) c.desc = E[c.id]?.desc;
  // without vision, Jev rates on caption + numbers only; once vision is on, clips described later are re-rated with their description
  const needJev = fresh.filter((c) => (!vision || E[c.id]?.desc || E[c.id]?.descFailed) && (E[c.id]?.jev?.model !== JEV_MODEL || E[c.id]?.jev?.schema !== JEV_SCHEMA || (E[c.id]?.desc && !E[c.id]?.jev?.withDesc))).slice(0, 16);
  for (let i = 0; i < needJev.length && left() > 7000; i += 8) {
    const res = await Promise.all(needJev.slice(i, i + 8).map((c) => jev(c, fresh)));
    res.forEach((j, k) => { const c = needJev[i + k]; if (j) E[c.id] = { ...E[c.id], jev: { ...j, withDesc: !!c.desc, views: c.views, ageH: c.ageH }, track: E[c.id]?.track?.length ? E[c.id].track : [{ t: now, views: c.views, ageH: c.ageH }] }; });
  }
  // 3. character fit for the best composites
  if (left() > 4000) {
    const needFit = fresh.filter((c) => E[c.id]?.jev?.transferable >= 0.6 && !E[c.id]?.fit).sort((a, b) => E[b.id].jev.composite - E[a.id].jev.composite).slice(0, 4);
    const fits = await Promise.all(needFit.map((c) => jevFit(c)));
    fits.forEach((f, k) => { if (f) E[needFit[k].id].fit = f; });
  }
  // forget clips gone from the queue for more than 7 days
  for (const [id, e] of Object.entries(E)) if (id !== "__run" && !cands[id] && e.track?.length && Date.now() - new Date(e.track[e.track.length - 1].t) > 7 * 864e5) delete E[id];
  E.__run = { t: now, ms: Date.now() - started, described: needDesc.length, lastErr: LAST_ERR, vision: provider };
  await store.setJSON("enrich", E);
  return new Response(`enriched in ${Date.now() - started} ms`);
};
