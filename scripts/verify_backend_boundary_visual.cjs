const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(path.resolve(__dirname, '..', 'backend', 'node_modules', 'playwright'));

async function main() {
  const htmlPath = path.resolve(process.argv[2]);
  assert.ok(fs.existsSync(htmlPath), `Map HTML does not exist: ${htmlPath}`);
  const html = fs.readFileSync(htmlPath, 'utf8');
  const embeddedMatch = html.match(/<script id="boundary-graph-data" type="application\/json">([\s\S]*?)<\/script>/);
  assert.ok(embeddedMatch, 'Embedded graph data is missing');
  const graph = JSON.parse(embeddedMatch[1]);
  const views = graph.views;
  assert.ok(Array.isArray(views) && views.length > 0, 'Graph views are missing');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1 });
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  try {
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' });
    const selector = page.locator('#path-choice');
    await selector.waitFor({ state: 'visible' });
    assert.equal(await selector.locator('option').count(), views.length, 'Path selector count differs from graph data');

    for (const view of views) {
      await selector.selectOption(view.id);
      const svg = page.locator('#funnel');
      const nodes = svg.locator('[data-node-id]');
      await nodes.first().waitFor({ state: 'attached' });
      assert.equal(await nodes.count(), view.nodes.length, `${view.id}: rendered node count differs from selected path`);
      const svgBox = await svg.boundingBox();
      assert.ok(svgBox && svgBox.width > 0 && svgBox.height > 0, `${view.id}: graph SVG has no visible layout box`);
      const firstNode = nodes.first();
      const style = await firstNode.evaluate(el => {
        const css = getComputedStyle(el);
        const rect = el.querySelector('rect');
        return {
          display: css.display,
          visibility: css.visibility,
          opacity: Number(css.opacity),
          width: Number(rect?.getAttribute('width') || 0),
          height: Number(rect?.getAttribute('height') || 0),
        };
      });
      assert.notEqual(style.display, 'none', `${view.id}: nodes are display:none`);
      assert.equal(style.visibility, 'visible', `${view.id}: nodes are hidden`);
      assert.ok(style.opacity > 0 && style.width > 0 && style.height > 0, `${view.id}: nodes have no visible geometry ${JSON.stringify(style)}`);
      const title = await page.locator('#path-title').textContent();
      assert.ok(title.includes(view.label), `${view.id}: selected path title did not update`);
      assert.ok((await page.locator('#road-paved-count').textContent()).includes('relaciones con fuente'), `${view.id}: source-traced road summary did not update`);
      assert.ok((await page.locator('#road-work-start').textContent()).trim(), `${view.id}: work boundary is missing`);
      assert.ok((await page.locator('#road-work-detail').textContent()).trim(), `${view.id}: work boundary detail is missing`);
      assert.ok((await page.locator('#road-target').textContent()).includes('objetivo'), `${view.id}: expected end state is not labeled as a target`);
      assert.equal(await page.locator('.road-node').count(), 3, `${view.id}: territory graph must have three milestone nodes`);
      if (view.id === 'evidence' || view.id === 'claim') {
        assert.match(await page.locator('#road-work-node').getAttribute('class'), /owner-open/, `${view.id}: unresolved owner frontier must be marked red`);
      }
      if (view.id === 'hypothesis') {
        assert.ok((await page.locator('#path-legend').innerText()).includes('HIPÓTESIS'), 'Proposal path must retain its hypothesis legend');
        assert.match(await page.locator('#road-work-start').textContent(), /decisión de arquitectura abierta/, 'Hypothesis path must start at an explicit architecture decision');
      }
    }

    assert.deepEqual(pageErrors, [], `Browser runtime errors: ${pageErrors.join('; ')}`);
    await selector.selectOption(views[0].id);
    const screenshotPath = path.resolve(path.dirname(htmlPath), '..', '..', '.run', 'backend-boundary-map-visual.png');
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    await page.screenshot({
      path: screenshotPath,
      fullPage: true,
    });
    console.log(`PASS: Chromium rendered ${views.length} paths; every path shows its expected node count and visible layout; no page errors.`);
    console.log('SCREENSHOT: .run/backend-boundary-map-visual.png (full page, default path)');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
