#!/usr/bin/env node
/* Prove the card app actually works before shipping it or rendering a video.

   node verify_app.cjs --url http://127.0.0.1:4317/ [--vertical URL]
                       [--expect 24] [--cols 4] [--chrome PATH] [--shots DIR]

   Checks the grid shape, every illustration, the modal + speech, autoplay, and
   (when given --vertical) sweeps the whole video timeline for NaN states.
   Prints a short PASS/FAIL report and exits non-zero on failure.
*/
const fs = require('fs');
const path = require('path');
const { chromium } = require('./_pw.cjs');

const argv = process.argv.slice(2);
const flag = (k, d) => { const i = argv.indexOf('--' + k); return i < 0 ? d : argv[i + 1]; };

const URL_ = flag('url', 'http://127.0.0.1:4317/');
const VERTICAL = flag('vertical', null);
const EXPECT = Number(flag('expect', 24));
const COLS = Number(flag('cols', 4));
const CHROME = flag('chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
const SHOTS = flag('shots', null);

const results = [];
const check = (name, ok, detail) => { results.push({ name, ok: !!ok, detail }); };

(async () => {
  if (!fs.existsSync(CHROME)) { console.log('FAIL  Chrome not found at ' + CHROME); process.exit(1); }
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--force-device-scale-factor=1', '--hide-scrollbars'] });

  /* ---- the card grid ---- */
  let page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const problems = [];
  page.on('pageerror', e => problems.push('pageerror ' + e.message));
  page.on('console', m => { if (m.type() === 'error') problems.push('console ' + m.text()); });
  page.on('requestfailed', r => problems.push('404 ' + path.basename(r.url())));
  await page.goto(URL_, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);

  const grid = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('.card')];
    return {
      n: cards.length,
      cols: new Set(cards.map(c => Math.round(c.getBoundingClientRect().left))).size,
      rows: new Set(cards.map(c => Math.round(c.getBoundingClientRect().top))).size,
      loaded: [...document.images].filter(i => i.complete && i.naturalWidth > 0).length,
      totalImgs: document.images.length,
      dataLen: typeof DATA !== 'undefined' ? DATA.length : -1,
      font: getComputedStyle(document.querySelector('.card-word')).fontFamily,
    };
  });
  check('card count = ' + EXPECT, grid.n === EXPECT, grid.n + ' cards, DATA=' + grid.dataLen);
  check(COLS + '-column grid', grid.cols === COLS, grid.cols + ' cols x ' + grid.rows + ' rows');
  check('all images decoded', grid.loaded === grid.totalImgs, grid.loaded + '/' + grid.totalImgs);
  check('self-hosted font applied', /Nunito/.test(grid.font), grid.font.split(',')[0]);

  await page.click('.card');
  await page.waitForTimeout(700);
  const modal = await page.evaluate(() => ({
    open: !document.getElementById('overlay').hidden,
    word: document.getElementById('modalWord').textContent,
    ipa: document.getElementById('modalIpa').textContent,
    zh: document.getElementById('modalZh').textContent,
    ex: document.getElementById('modalExample').textContent,
  }));
  check('modal opens with word/ipa/zh/example', modal.open && modal.word && modal.ipa && modal.zh && modal.ex,
    [modal.word, modal.ipa, modal.zh].join(' | '));
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, 'modal.png') });

  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  const moved = await page.evaluate(() => document.getElementById('modalWord').textContent);
  check('arrow navigates', moved !== modal.word, modal.word + ' -> ' + moved);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  check('escape closes', await page.evaluate(() => document.getElementById('overlay').hidden));

  /* ---- autoplay ---- */
  await page.goto(URL_.split('?')[0] + '?autoplay=1&dwell=1200', { waitUntil: 'load' });
  const a1 = await page.evaluate(() => document.getElementById('modalWord').textContent);
  await page.waitForTimeout(2000);
  const a2 = await page.evaluate(() => document.getElementById('modalWord').textContent);
  check('autoplay advances', a1 !== a2, a1 + ' -> ' + a2);
  await page.mouse.click(720, 900);
  await page.waitForTimeout(300);
  const stopped = await page.evaluate(() => !document.querySelector('.autoplay-banner'));
  await page.waitForTimeout(1800);
  const held = await page.evaluate(() => document.getElementById('modalWord').textContent);
  check('interaction stops autoplay', stopped, 'banner gone, word held at ' + held);
  await page.close();

  /* ---- vertical scene ---- */
  if (VERTICAL) {
    page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    page.on('pageerror', e => problems.push('vertical pageerror ' + e.message));
    page.on('console', m => { if (m.type() === 'error') problems.push('vertical console ' + m.text()); });
    page.on('requestfailed', r => problems.push('vertical 404 ' + path.basename(r.url())));
    await page.goto(VERTICAL, { waitUntil: 'load' });
    const v = await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })));
      if (window.__fit) window.__fit();
      const bad = [];
      for (let t = 0; t <= window.SCENE.TOTAL; t += 0.11) {
        window.seek(t);
        const c = document.getElementById('card');
        if (/NaN/.test(c.style.transform + '|' + c.style.opacity + '|' + document.getElementById('strip').style.transform)) bad.push(+t.toFixed(2));
      }
      window.seek(window.SCENE.INTRO + window.SCENE.DWELL * 0.5 + 0.6);
      const r = document.getElementById('card').getBoundingClientRect();
      return {
        total: +window.SCENE.TOTAL.toFixed(1), bad,
        slots: document.querySelectorAll('.mini').length,
        ticks: document.querySelectorAll('.tick').length,
        onStage: Math.round(r.width) > 900,
        overflow: document.documentElement.scrollWidth,
      };
    });
    check('scene exposes TOTAL', v.total > 10, v.total + 's timeline');
    check('no NaN states across timeline', v.bad.length === 0, v.bad.length ? 'first bad t=' + v.bad[0] : 'swept at 0.11s steps');
    check('card lands on stage', v.onStage, 'strip slots=' + v.slots + ', ticks=' + v.ticks);
    check('no horizontal overflow', v.overflow === 1080, 'scrollWidth ' + v.overflow);
    if (SHOTS) { await page.screenshot({ path: path.join(SHOTS, 'vertical.png') }); }
    await page.close();
  }

  await browser.close();
  const bad = results.filter(r => !r.ok);
  for (const r of results) console.log((r.ok ? 'PASS  ' : 'FAIL  ') + r.name + (r.detail ? '   (' + r.detail + ')' : ''));
  if (problems.length) console.log('page problems:\n  ' + [...new Set(problems)].join('\n  '));
  console.log(bad.length || problems.length ? '\n' + bad.length + ' failed checks, ' + problems.length + ' page problems'
                                             : '\nall ' + results.length + ' checks passed');
  process.exit(bad.length || problems.length ? 1 : 0);
})();
