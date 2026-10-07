// Browser regression tests. Every provider/API/media response is simulated.
// Run: npm run test:ux (install Chromium with npx playwright install chromium).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const artifacts = process.env.UX_ARTIFACT_DIR || path.join(os.tmpdir(), 'character-lab-ux-results');
fs.mkdirSync(artifacts, { recursive: true });
const source = id => ({ id, owner: 'demo_' + id, url: 'https://example.test/' + id, sec: 15, views: 120000, vph: 5000, ageH: 12, bucket: 'buzz', solo: 1, scene: 'wedding', cost480: 45 });
const fixture = { updated: '2026-10-07T00:00:00Z', accounts: [], live_sources: { items: [source('source1'), source('source2')] } };
const radar = { settings: {}, candidates: [], costs: [], runs: [] };
const errors = [];
let mutations = 0;
let browser;
const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(fs.readFileSync(path.join(root, 'index.html')));
});
const check = (name, fn) => fn().then(() => console.log('PASS ' + name));
async function setup({ connector = false, data = fixture, mobile = false, radarData = radar, poolData = { state: {}, accounts: [] }, authenticated = false } = {}) {
  const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, locale: 'fr-FR', permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.stack));
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname === '/data.json') return route.fulfill(data === null ? { status: 503, json: {} } : { json: data });
    if (url.pathname.startsWith('/api/')) {
      if (req.method() !== 'GET') mutations++;
      return route.fulfill({ json: url.pathname === '/api/radar' ? radarData : poolData });
    }
    if (req.resourceType() === 'image') return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="180" height="280"><rect width="180" height="280" fill="#ece6fb"/><text x="90" y="130" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#5b21b6">APERÇU TEST</text><text x="90" y="150" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#5a5f6e">Média simulé</text></svg>' });
    if (url.hostname === '127.0.0.1') return route.continue();
    return route.fulfill({ status: 200, body: '' });
  });
  if (authenticated) await page.addInitScript(() => localStorage.setItem('radarKey', 'test-only-key'));
  if (connector) await page.addInitScript(() => {
    window.__calls = []; window.__jobStatus = 'running'; window.__failGeneration = false; window.__downloads = [];
    window.claude = { use: async kind => {
      if (kind === 'downloads') return { save: async file => window.__downloads.push(file.filename) };
      if (kind !== 'mcp') return null;
      return { callTool: async (provider, tool, args) => {
        window.__calls.push({ tool, args });
        if (tool === 'media_import_url') return { payload: { media_id: 'fixture-media' } };
        if (tool === 'generate_video') { if (window.__failGeneration) throw { code: 'tool_error', message: 'Simulated failure' }; return { payload: { results: [{ id: 'fixture-job' }] } }; }
        if (tool === 'upscale_video') return { payload: { results: [{ id: 'fixture-upscale' }] } };
        if (tool === 'jobs_wait') return { payload: { jobs: args.jobs.map(j => ({ index: j.index, status: window.__jobStatus, result_url: window.__jobStatus === 'completed' ? 'https://example.test/result.mp4' : null })) } };
        throw Error('Unexpected mock tool: ' + tool);
      } };
    } };
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(() => document.querySelector('#fiche .ux-character-heading'));
  await page.waitForFunction(() => UX.connector !== null);
  return page;
}
async function navigate(page, hash, id) {
  await page.evaluate(hash => { location.hash = hash; }, hash);
  await page.locator(id).waitFor({ state: 'visible' });
  await page.waitForFunction(hash => UX.space === ({ '#characters': 'characters', '#lab': 'characters', '#radar': 'radar', '#pool': 'accounts', '#accounts': 'accounts', '#sources': 'sources', '#srcs': 'sources', '#studio': 'videos', '#videos': 'videos', '#create': 'create' }[hash] || 'resources'), hash);
}
async function wizard(page) {
  await page.locator('[data-create]').first().click();
  await page.locator('[data-wchar]').first().waitFor({ state: 'visible' });
  await page.locator('[data-wchar]').first().click();
  await page.locator('#w-next').click();
  await page.locator('[data-wsrc]').first().click();
  await page.locator('#w-next').click();
}
async function openCharacter(page, id = 'mila') {
  await page.locator(`#arch button[data-id="${id}"]`).click();
  await page.locator('#character-dialog').waitFor({ state: 'visible' });
}
async function assertFooterVisible(page) {
  const viewport = page.viewportSize();
  for (const id of ['#w-back', '#w-next']) {
    const box = await page.locator(id).boundingBox();
    assert.ok(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width && box.y + box.height <= viewport.height, `${id} must stay in the viewport without scrolling to the end of the catalog`);
    assert.equal(await page.locator(id).evaluate(button => {
      const r = button.getBoundingClientRect();
      return button.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
    }), true, `${id} must not be covered by another control`);
  }
}
// Unlike locator.click(), a coordinate click cannot scroll a hidden footer into view.
async function clickWithoutScrolling(page, selector) {
  const box = await page.locator(selector).boundingBox();
  assert.ok(box, `${selector} must have a visible bounding box`);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}
async function scrollCatalog(page, fraction) {
  await page.evaluate(async fraction => {
    window.scrollTo({ top: fraction * (document.documentElement.scrollHeight - innerHeight), behavior: 'instant' });
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, fraction);
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  browser = await chromium.launch({ headless: true });
  await check('navigation, legacy anchors, browser history and unique IDs', async () => {
    const page = await setup();
    assert.deepEqual(await page.locator('main>section:visible').evaluateAll(ns => ns.map(n => n.id)), ['studio']);
    assert.deepEqual(await page.locator('[id]').evaluateAll(ns => ns.map(n => n.id).filter((id, i, ids) => ids.indexOf(id) !== i)), []);
    await page.screenshot({ path: path.join(artifacts, 'videos-desktop.png') });
    for (const [hash, id] of [['#characters', '#lab'], ['#sources', '#source-library'], ['#radar', '#radar'], ['#accounts', '#pool'], ['#resources', '#findings']]) {
      await navigate(page, hash, id);
      await page.screenshot({ path: path.join(artifacts, hash.slice(1) + '-desktop.png') });
    }
    for (const [hash, id] of [['#studio', '#studio'], ['#lab', '#lab'], ['#srcs', '#source-library'], ['#pool', '#pool'], ['#look', '#look'], ['#web', '#web'], ['#protocol', '#protocol'], ['#data', '#data'], ['#wave', '#wave']]) await navigate(page, hash, id);
    await navigate(page, '#videos', '#studio'); await navigate(page, '#sources', '#source-library');
    await page.goBack(); await page.locator('#studio').waitFor({ state: 'visible' });
    await page.goForward(); await page.locator('#source-library').waitFor({ state: 'visible' });
    await page.locator('.skip-link').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => UX.space), 'sources');
    await page.close();
  });
  await check('gallery search, collection filters and accessible character details', async () => {
    const page = await setup();
    await navigate(page, '#characters', '#lab');
    assert.equal(await page.locator('#character-dialog').isVisible(), false);
    const allCount = await page.locator('#arch button[data-id]').count();
    assert.ok(allCount > 30, 'full production catalog remains available');
    const cards = await page.locator('#arch button[data-id]').evaluateAll(ns => ns.slice(0, 2).map(n => ({ x: n.getBoundingClientRect().x, y: n.getBoundingClientRect().y })));
    assert.equal(cards[0].y, cards[1].y); assert.ok(cards[1].x > cards[0].x, 'desktop catalog has multiple columns');
    assert.equal(await page.locator('#arch').evaluate(n => n.scrollWidth <= n.clientWidth), true, 'catalog must not become a horizontal strip');
    await page.locator('#character-search').fill('mila.margin');
    assert.equal(await page.locator('#arch button[data-id]').count(), 1);
    assert.equal(await page.locator('#arch button[data-id]').getAttribute('data-id'), 'mila');
    assert.equal(await page.locator('#character-count').textContent(), '1');
    await page.locator('[data-collection=buyers]').click();
    assert.equal(await page.locator('#arch button[data-id]').count(), 0);
    assert.equal(await page.locator('#catalog-empty').isVisible(), true);
    await page.locator('[data-collection=prime]').click();
    assert.equal(await page.locator('#arch button[data-id]').count(), 1);
    await page.locator('#lang-en').click();
    assert.equal(await page.locator('#character-search').inputValue(), 'mila.margin');
    assert.equal(await page.locator('#character-search').getAttribute('placeholder'), 'Search characters');
    await page.locator('#arch button[data-id=mila]').focus(); await page.keyboard.press('Enter');
    await page.locator('#character-dialog').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#character-dialog .cname').textContent(), 'Mila Margin');
    assert.equal(await page.evaluate(() => ST.char), 'mila');
    assert.equal(await page.locator('#character-dialog .card-top img').getAttribute('src'), 'img/lab_f0.jpg');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#character-dialog').isVisible(), false);
    assert.equal(await page.locator('#arch button[data-id=mila]').evaluate(n => n === document.activeElement), true);
    await page.locator('#character-search').fill(''); await page.locator('[data-collection=all]').click();
    assert.equal(await page.locator('#arch button[data-id]').count(), allCount);
    await openCharacter(page); await page.locator('#character-close').click();
    assert.equal(await page.locator('#character-dialog').isVisible(), false);
    await page.close();
  });
  await check('assistant selections survive navigation, refresh and language changes; no connector', async () => {
    const page = await setup(); await wizard(page);
    assert.equal(await page.locator('#w-generate').isDisabled(), true);
    const before = await page.evaluate(() => ({ char: WIZ.char, src: WIZ.src, step: WIZ.step }));
    await page.screenshot({ path: path.join(artifacts, 'wizard-desktop.png') });
    await navigate(page, '#sources', '#source-library'); await navigate(page, '#create', '#create');
    await page.evaluate(() => { studioRefresh(); renderRadar(); });
    await page.locator('#lang-en').click();
    assert.equal(await page.locator('#w-generate').textContent(), 'Generate video');
    assert.deepEqual(await page.evaluate(() => ({ char: WIZ.char, src: WIZ.src, step: WIZ.step })), before);
    await page.locator('#w-back').click(); assert.equal(await page.locator('[data-wsrc][aria-pressed=true]').count(), 1);
    await page.locator('#w-back').click(); assert.equal(await page.locator('[data-wchar][aria-pressed=true]').count(), 1);
    await navigate(page, '#characters', '#lab'); await openCharacter(page); await page.locator('#lab-create').click();
    await page.waitForFunction(() => UX.space === 'create');
    assert.equal(await page.locator('#character-dialog').isVisible(), false);
    assert.equal(await page.evaluate(() => WIZ.char === LAB.arch.id), true);
    await navigate(page, '#sources', '#source-library'); await page.locator('[data-use-source=source2]').click();
    await page.waitForFunction(() => UX.space === 'create'); assert.equal(await page.evaluate(() => WIZ.src), 'source2');
    await page.close();
  });
  await check('source direct generation uses the explicitly selected character', async () => {
    const page = await setup({ connector: true });
    await navigate(page, '#characters', '#lab'); await openCharacter(page, 'mila');
    await page.locator('#character-close').click();
    await navigate(page, '#sources', '#source-library');
    assert.equal(await page.locator('#source-character').inputValue(), 'mila');
    await page.locator('#source-character').selectOption('tony');
    assert.equal(await page.locator('#source-character').inputValue(), 'tony');
    assert.equal(await page.evaluate(() => window.__calls.length), 0, 'character selection must not submit a job');
    await page.locator('[data-gen=source1]').click();
    await page.waitForFunction(() => VIDS.tony__source1?.status === 'running');
    assert.equal(await page.evaluate(() => !!VIDS.mila__source1), false);
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 1);
    await navigate(page, '#videos', '#studio');
    assert.equal(await page.locator('.ux-character-heading h3').textContent(), 'Tattoo Tony');
    await navigate(page, '#characters', '#lab'); await openCharacter(page, 'mila');
    await page.locator('#lab-create').click(); await page.waitForFunction(() => UX.space === 'create');
    assert.equal(await page.evaluate(() => WIZ.char), 'mila');
    await navigate(page, '#sources', '#source-library');
    await page.locator('#source-character').selectOption('tony');
    await page.locator('[data-use-source=source2]').click();
    await page.waitForFunction(() => UX.space === 'create');
    assert.deepEqual(await page.evaluate(() => ({ char: WIZ.char, src: WIZ.src, step: WIZ.step })), { char: 'tony', src: 'source2', step: 2 });
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 1, 'opening the assistant must not submit another job');
    await page.close();
  });
  await check('generation, existing job recovery, 4K, copy, download, manual posted state and no duplicate submissions', async () => {
    const page = await setup({ connector: true }); await wizard(page);
    assert.equal(await page.evaluate(() => window.__calls.length), 0);
    await page.locator('#w-generate').click(); await page.waitForFunction(() => WIZ.step === 3);
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 1);
    await navigate(page, '#videos', '#studio'); await navigate(page, '#create', '#create');
    await page.locator('[data-step="2"]').click(); await page.locator('#w-existing').click();
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 1);
    await page.evaluate(async () => { window.__jobStatus = 'completed'; await poll(); });
    await page.locator('#w-upscale').click(); await page.evaluate(async () => { await poll(); });
    await page.locator('#w-download4k').waitFor();
    await page.locator('#w-copy').click(); assert.ok((await page.evaluate(() => navigator.clipboard.readText())).length > 10);
    await page.locator('#w-download4k').click(); await page.waitForFunction(() => window.__downloads.length === 1);
    await page.locator('#w-posted').click(); assert.equal(await page.evaluate(() => VIDS[`${WIZ.char}__${WIZ.src}`].posted), true);
    const oldId = await page.evaluate(() => `${WIZ.char}__${WIZ.src}`);
    await page.locator('[data-step="1"]').click(); await page.locator('[data-wsrc=source2]').click(); await page.locator('#w-next').click();
    assert.equal(await page.locator('#w-generate').isEnabled(), true);
    assert.equal(await page.evaluate(id => VIDS[id].status, oldId), 'done4k');
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 1);
    await page.close();
  });
  await check('failed generation can be retried explicitly', async () => {
    const page = await setup({ connector: true }); await wizard(page);
    await page.evaluate(() => { window.__failGeneration = true; }); await page.locator('#w-generate').click();
    await page.locator('#w-retry').waitFor(); assert.match(await page.locator('[role=alert]').innerText(), /Simulated failure/);
    await page.evaluate(() => { window.__failGeneration = false; }); await page.locator('#w-retry').click();
    await page.waitForFunction(() => VIDS[`${WIZ.char}__${WIZ.src}`].status === 'running');
    assert.equal(await page.evaluate(() => window.__calls.filter(c => c.tool === 'generate_video').length), 2);
    await page.close();
  });
  await check('missing data, empty sources, and dynamic FR/EN without data', async () => {
    const page = await setup({ data: null }); await page.locator('#retry-data').waitFor();
    await page.locator('#lang-en').click(); await navigate(page, '#characters', '#lab');
    await openCharacter(page);
    assert.match(await page.locator('#lab-create').innerText(), /Create a video/);
    await page.locator('#lab-create').click(); await page.locator('#wizard .empty').waitFor();
    assert.equal(await page.locator('#w-next').isDisabled(), true);
    await page.close();
  });
  await check('mobile spaces, collapsible menu, keyboard use and no page overflow', async () => {
    const page = await setup({ mobile: true });
    await page.locator('#menu-toggle').click(); assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true');
    await page.keyboard.press('Escape'); assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
    await page.locator('#menu-toggle').click(); await page.locator('[data-nav=characters]').click();
    await page.locator('#lab').waitFor({ state: 'visible' }); assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
    for (const [hash, id] of [['#videos', '#studio'], ['#characters', '#lab'], ['#sources', '#source-library'], ['#radar', '#radar'], ['#accounts', '#pool'], ['#resources', '#findings']]) {
      await navigate(page, hash, id);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'overflow on ' + hash);
      await page.screenshot({ path: path.join(artifacts, hash.slice(1) + '-mobile.png') });
    }
    await page.locator('.mobile-create').click(); await page.locator('[data-wchar]').first().waitFor();
    await assertFooterVisible(page);
    await page.locator('[data-wchar]').first().focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#w-next').isEnabled(), true);
    await assertFooterVisible(page);
    await page.locator('[data-wchar]').last().focus(); await page.keyboard.press('Enter');
    await assertFooterVisible(page);
    await page.locator('#w-next').click(); await page.locator('[data-wsrc]').first().click(); await page.locator('#w-next').click();
    await page.screenshot({ path: path.join(artifacts, 'wizard-mobile.png') });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.close();
  });
  for (const mobile of [false, true]) await check(`persistent wizard actions with 132 sources on ${mobile ? 'mobile' : 'desktop'}`, async () => {
    const data = { ...fixture, live_sources: { items: Array.from({ length: 132 }, (_, i) => source('long-source-' + i)) } };
    const page = await setup({ mobile, connector: true, data });
    await navigate(page, '#create', '#create');
    await scrollCatalog(page, 0); await assertFooterVisible(page);
    await page.locator('[data-wchar]').first().click();
    await assertFooterVisible(page);
    await clickWithoutScrolling(page, '#w-next');
    await page.waitForFunction(() => WIZ.step === 1);
    assert.equal(await page.locator('[data-wsrc]').count(), 132);
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight > innerHeight * 5), 'fixture must reproduce a catalog much taller than the viewport');
    for (const fraction of [0, 0.5, 1]) {
      await scrollCatalog(page, fraction);
      await assertFooterVisible(page);
    }
    // Select a source in the middle of the list by coordinates, then verify the
    // rerender preserves the position and leaves both actions accessible.
    await scrollCatalog(page, 0.5);
    const choice = await page.locator('[data-wsrc]').evaluateAll(cards => {
      const footerTop = document.querySelector('.wizard-foot').getBoundingClientRect().top;
      const card = cards.find(card => {
        const r = card.getBoundingClientRect();
        return r.top >= 80 && r.bottom <= footerTop;
      });
      if (!card) return null;
      const r = card.getBoundingClientRect();
      return { id: card.dataset.wsrc, x: r.x + r.width / 2, y: r.y + r.height / 2 };
    });
    assert.ok(choice, 'a source card must be available to select in the middle of the catalog');
    const scrollBeforeSelection = await page.evaluate(() => scrollY);
    await page.mouse.click(choice.x, choice.y);
    assert.equal(await page.evaluate(() => WIZ.src), choice.id);
    assert.equal(await page.locator('#w-next').isEnabled(), true);
    assert.ok(Math.abs(await page.evaluate(() => scrollY) - scrollBeforeSelection) < 2, 'selection must preserve the reading position');
    await assertFooterVisible(page);
    await scrollCatalog(page, 1);
    const end = await page.evaluate(() => ({
      lastCard: document.querySelector('[data-wsrc]:last-child').getBoundingClientRect().bottom,
      sourceLink: document.querySelector('#wizard > a').getBoundingClientRect().bottom,
      footer: document.querySelector('.wizard-foot').getBoundingClientRect().top,
    }));
    assert.ok(end.lastCard <= end.footer && end.sourceLink <= end.footer, 'bottom padding must keep the last source and its preview link above the footer');
    await assertFooterVisible(page);
    await scrollCatalog(page, 0);
    await assertFooterVisible(page);
    await page.screenshot({ path: path.join(artifacts, `wizard-long-sources-${mobile ? 'mobile' : 'desktop'}.png`) });
    await clickWithoutScrolling(page, '#w-next');
    await page.waitForFunction(() => WIZ.step === 2);
    await clickWithoutScrolling(page, '#w-back');
    await page.waitForFunction(() => WIZ.step === 1);
    await assertFooterVisible(page);
    await clickWithoutScrolling(page, '#w-back');
    await page.waitForFunction(() => WIZ.step === 0);
    assert.equal(await page.locator('[data-wchar][aria-pressed=true]').count(), 1);
    assert.equal(await page.evaluate(() => window.__calls.length), 0, 'navigation and selection must not start a generation');
    await navigate(page, '#sources', '#source-library');
    assert.equal(await page.locator('.wizard-foot').isVisible(), false, 'fixed actions must disappear outside the assistant');
    await page.close();
  });
  await check('disclosures preserve actions, controls and Radar results', async () => {
    const page = await setup({ authenticated: true, radarData: { ...radar, active: true, spent: 3, calibration: [{ label: 'test', n: 1 }], candidates: [{ id: 'radar:1', owner: 'demo', platform: 'instagram', video: 'https://example.test/source.mp4', url: 'https://example.test/source', thumb: 'img/fixture.jpg', duration: 15, ageH: 2, views: 5000, vph: 2500, status: 'new' }] } });
    await navigate(page, '#radar', '#radar');
    assert.equal(await page.locator('#radar .rq').isVisible(), true);
    assert.equal(await page.locator('#radarBox').getByText('VEILLE ACTIVE', { exact: false }).isVisible(), true);
    const settings = page.locator('details').filter({ has: page.locator('#rKey') });
    assert.equal(await settings.getAttribute('open'), null); await settings.locator('summary').click();
    assert.equal(await page.locator('#rSave').isVisible(), true);
    assert.equal(await page.locator('[data-rad=scan]').isVisible(), true);
    await navigate(page, '#characters', '#lab');
    await openCharacter(page);
    await page.locator('#lab-customize').click();
    await page.locator('#c-place').selectOption('none');
    assert.equal(await page.evaluate(() => BRAND.place), 'none');
    assert.equal(await page.evaluate(() => Object.hasOwn(LAB.s, 'undefined')), false);
    const prompt = page.locator('details').filter({ has: page.locator('#prompt') });
    await prompt.locator('summary').click(); assert.equal(await page.locator('#b-copy').isVisible(), true);
    await page.locator('#b-copy').click(); assert.ok((await page.evaluate(() => navigator.clipboard.readText())).length > 100);
    await page.close();
  });
  await check('character export stays byte-for-byte compatible', async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'character-export-'));
    try {
      fs.mkdirSync(path.join(dir, 'dist'));
      fs.copyFileSync(path.join(root, 'export_characters.mjs'), path.join(dir, 'export_characters.mjs'));
      fs.writeFileSync(path.join(dir, 'data.json'), JSON.stringify(fixture));
      const outputs = [];
      for (const html of [execFileSync('git', ['show', 'HEAD:dashboard/index.html'], { cwd: root, encoding: 'utf8' }), fs.readFileSync(path.join(root, 'index.html'), 'utf8')]) {
        fs.writeFileSync(path.join(dir, 'index.html'), html);
        execFileSync(process.execPath, [path.join(dir, 'export_characters.mjs')]);
        outputs.push(fs.readFileSync(path.join(dir, 'dist/characters.json'), 'utf8'));
      }
      assert.equal(outputs[0], outputs[1]);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  });
  assert.deepEqual(errors, [], 'browser errors'); assert.equal(mutations, 0, 'unexpected API mutations');
  console.log('All UX checks passed. Screenshots: ' + artifacts);
})().catch(e => { console.error(e); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); server.close(); });
