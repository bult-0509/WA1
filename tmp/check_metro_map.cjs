const {chromium} = require('C:/Users/20152/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1150}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:8517');
    await page.getByText('动态客流地图', {exact:true}).click();
    const frame = page.frameLocator('iframe').first();
    await frame.locator('#loading').waitFor({state:'hidden'});
    await frame.locator('#btnPlay').click();
    assert.match(await frame.locator('#btnPlay').innerText(), /播放/);
    const dateCount = await frame.locator('#dateSel option').count();
    assert.ok(dateCount > 1);
    await frame.locator('#dateSel').selectOption({index:1});
    assert.equal(await frame.locator('#clock').innerText(), '06:00');
    await frame.locator('#btnNext').click();
    assert.equal(await frame.locator('#clock').innerText(), '06:10');
    await frame.locator('#btnPrev').click();
    assert.equal(await frame.locator('#clock').innerText(), '06:00');
    await frame.locator('#slider').fill('12');
    assert.equal(await frame.locator('#clock').innerText(), '08:00');
    await frame.locator('#speed').fill('12');
    await frame.locator('#btnPlay').click();
    await frame.locator('#clock').filter({hasText:'08:00'}).waitFor({state:'hidden'});
    await frame.locator('#btnPlay').click();
    assert.ok(await frame.locator('canvas').count() > 0);
    assert.equal(await frame.locator('img.leaflet-tile').count(), 0);
    await frame.locator('.leaflet-control-zoom-in').click();
    await page.screenshot({path:'tmp/metro-map-desktop.png',fullPage:true});
    await page.setViewportSize({width:760,height:1100});
    await page.screenshot({path:'tmp/metro-map-narrow.png',fullPage:true});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({dateCount,errors,checks:'navigation, render, date, playback, speed, timeline, step, zoom, offline'},null,2));
  } finally { await browser.close(); }
})().catch(error=>{ console.error(error);process.exit(1); });
