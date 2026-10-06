// Export every Lab character (traits, image prompt, bio, captions, scores, images, generated videos) to dist/characters.json.
// Runs the page's own script in a sandbox with a stub DOM, so the export always matches what the Lab shows.
// Usage: node export_characters.mjs   (after build_data.py, which writes data.json)
import fs from "node:fs";
import vm from "node:vm";

const HERE = new URL(".", import.meta.url).pathname;
const SITE = "https://character-lab-research.netlify.app";
const html = fs.readFileSync(`${HERE}index.html`, "utf8");
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const data = JSON.parse(fs.readFileSync(`${HERE}data.json`, "utf8"));

const dummy = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => "" : dummy), apply: () => dummy, set: () => true });
const sandbox = {
  document: dummy, window: {}, localStorage: { getItem: () => null, setItem() {} }, navigator: {}, location: { hash: "" },
  setInterval() {}, setTimeout() {}, fetch: async () => ({ ok: false }), console, CSS: { escape: (s) => s },
  getComputedStyle: () => dummy, matchMedia: () => ({ matches: false, addEventListener() {} }),
};
vm.createContext(sandbox);
vm.runInContext(js + `
;LANG='en';
globalThis.__export = (DATA_IN) => { DATA = DATA_IN; return ARCH.map(a => {
  const bo = breakout(a.s), mb = MB_BIO[a.id] || a.mb || [a.role, a.tics[0]];
  const handle = a.handle.replace(/[^a-z0-9._]/gi, '');
  return { id: a.id, name: a.name, handle, profile_name: a.name + ' | Meta Ads', tagline: { fr: a.fr, en: a.en }, role: a.role,
    traits: a.s, breakout_score: bo.val, breakout_parts: bo.parts, clone_of: bo.clone, tips: bo.tips,
    bio: Q4_COPY[a.id] ? Q4_COPY[a.id].bio : mb[0] + '\\n' + mb[1] + '\\nRuns on Prime Ads ⚡ Built to stay live 👇',
    link: LANDING + '?utm_source=instagram&utm_medium=bio&utm_campaign=' + handle.replace(/[^a-z0-9]/gi, ''),
    bio_variant: Q4_COPY[a.id] ? Q4_COPY[a.id].bio_variant : null, location_tag: CITY[a.id] || 'Business Bay, Dubai', hashtags: HASHTAGS,
    captions: { character: a.tics, media_buyer: (Q4_COPY[a.id] || {}).captions || MB_TICS }, promo_handle: '@primeads_ai',
    image_prompt: buildPrompt(a.s), image_model: 'gpt_image_2 · 9:16 · 2k · high',
    flags: { prime_ads: !!a.pa, media_buyer: !!a.mbs, test: !!a.test, mb_target: MB_TARGET.includes(a.id) } };
}); };`, sandbox);

const chars = sandbox.__export(data);
const vids = data.studio_videos || [];
for (const c of chars) {
  const img = (html.match(new RegExp(`\\{id:'${c.id}'[^}]*?img:'img/(lab_[a-z0-9]+)\\.jpg'`)) || [])[1];
  c.images = {
    card: `${SITE}/img/${img}.jpg`, hd_1080x1920: `${SITE}/img/hd/${img}.jpg`,
    profile_picture: fs.existsSync(`${HERE}img/pfp/hd/${c.id}.jpg`) ? `${SITE}/img/pfp/hd/${c.id}.jpg` : null,
  };
  c.videos = vids.filter((v) => v.char === c.id).map((v, i) => ({
    n: i + 1, status: v.status, video_4k: v.url4k, video_480p: v.url, source_clip: `${SITE}/clips/${v.src}.mp4`,
    source_post: v.srcUrl, higgsfield_job: v.job, aspect: v.w && v.h && Math.abs(v.w / v.h - 9 / 16) > 0.02 ? "3:4" : "9:16",
  }));
}
// posting plan: biggest source first (the first reel of a new account matters most), captions alternate tic / media-buyer line
const SLOTS = ["D0 14:00 UTC", "D0 17:00 UTC", "D0 21:00 UTC", "D1 14:00 UTC", "D1 21:00 UTC", "D2 14:00 UTC", "D2 22:00 UTC", "D3 14:00 UTC", "D3 22:00 UTC", "D4 14:00 UTC"];
const srcViews = Object.fromEntries(((data.live_sources || {}).items || []).map((s) => [s.id, s.views]));
for (const c of chars) {
  const vs = vids.filter((v) => v.char === c.id);
  c.videos.forEach((v, i) => { v.source_views = srcViews[vs[i].src] ?? null; });
  [...c.videos].sort((x, y) => (y.source_views || 0) - (x.source_views || 0)).forEach((v, k) => {
    v.slot = SLOTS[k] || `D${4 + Math.ceil((k - 9) / 2)}`;
    // every caption points to @primeads_ai: the 3 Q4 lines first, then the character's tics with the handle
    const q = c.captions.media_buyer, tics = c.captions.character;
    const P = (vm.runInContext("Q4_COPY", sandbox)[c.id] || {}).posts || [];
    v.caption = P.length ? P[k % P.length].text : tics[k % tics.length];
    v.caption_variant = P.length ? P[k % P.length].variant : null;
  });
}
chars.sort((a, b) => b.breakout_score - a.breakout_score);
fs.writeFileSync(`${HERE}dist/characters.json`, JSON.stringify({ updated: data.updated, count: chars.length, characters: chars }));
console.log(`characters.json: ${chars.length} characters, ${chars.reduce((n, c) => n + c.videos.length, 0)} videos`);
