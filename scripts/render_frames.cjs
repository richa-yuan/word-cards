#!/usr/bin/env node
/* Frame-accurate capture of a deterministic scene page.

   The page must expose  window.seek(seconds)  and  window.SCENE.TOTAL .

   node render_frames.cjs --url URL --out DIR [--fps 30] [--size 1080x1920]
                          [--q 92] [--chrome PATH] [--duration SECONDS]
                          [--preview 1.5,4.6,78]

   --preview captures those timestamps as PNGs and exits (layout proofing).
   Without it, every frame of the timeline is written as f-00000.jpg.
*/
const fs = require('fs');
const path = require('path');
const { chromium } = require('./_pw.cjs');

const argv = process.argv.slice(2);
const flag = (k, d) => { const i = argv.indexOf('--' + k); return i < 0 ? d : argv[i + 1]; };
const has = k => argv.includes('--' + k);

const URL_ = flag('url', null);
const OUT = flag('out', '/tmp/frames');
const FPS = Number(flag('fps', 30));
const [VW, VH] = flag('size', '1080x1920').split('x').map(Number);
const Q = Number(flag('q', 92));
const CHROME = flag('chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
const PREVIEW = has('preview') ? flag('preview').split(',').map(Number) : null;

if (!URL_) { console.log('error: --url is required'); process.exit(1); }
if (!fs.existsSync(CHROME)) { console.log('error: Chrome not found at ' + CHROME + ' (pass --chrome)'); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ['--force-device-scale-factor=1', '--hide-scrollbars', '--disable-lcd-text',
           '--font-render-hinting=none', '--disable-gpu'],
  });
  const page = await browser.newPage({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 });
  const problems = [];
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
  page.on('requestfailed', r => problems.push('requestfailed: ' + r.url()));

  await page.goto(URL_, { waitUntil: 'load' });
  const scene = await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(i =>
      i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })));
    if (window.__fit) window.__fit();
    return window.SCENE || {};
  });
  const total = Number(flag('duration', scene.TOTAL));
  if (!total) { console.log('error: page exposes no window.SCENE.TOTAL; pass --duration'); await browser.close(); process.exit(1); }
  console.log('scene total=' + total.toFixed(2) + 's  fps=' + FPS + '  ' + VW + 'x' + VH);

  if (PREVIEW) {
    for (const t of PREVIEW) {
      await page.evaluate(x => window.seek(x), t);
      await page.waitForTimeout(30);
      const f = path.join(OUT, 'preview-' + String(Math.round(t * 100)).padStart(5, '0') + '.png');
      await page.screenshot({ path: f });
      console.log(f);
    }
  } else {
    const frames = Math.round(total * FPS);
    const t0 = Date.now();
    for (let i = 0; i < frames; i++) {
      await page.evaluate(x => window.seek(x), i / FPS);
      await page.screenshot({ path: path.join(OUT, 'f-' + String(i).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: Q });
      if (i % 300 === 0) console.log('frame ' + i + '/' + frames + '  ' + ((Date.now() - t0) / 1000).toFixed(0) + 's');
    }
    console.log('captured ' + frames + ' frames in ' + ((Date.now() - t0) / 1000).toFixed(0) + 's -> ' + OUT);
  }

  if (problems.length) console.log('problems:\n  ' + [...new Set(problems)].join('\n  '));
  else console.log('no console/network problems');
  await browser.close();
})();
