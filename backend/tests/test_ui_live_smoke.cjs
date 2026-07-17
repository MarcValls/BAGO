const assert = require('assert');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'ui-react', 'dist');

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
  }[ext] || 'application/octet-stream';
}

function startServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const rawUrl = new URL(req.url || '/', 'http://127.0.0.1');
        let rel = decodeURIComponent(rawUrl.pathname);
        if (rel === '/' || rel === '') {
          rel = '/index.html';
        }
        const filePath = path.join(DIST, rel);
        if (!filePath.startsWith(DIST)) {
          res.statusCode = 403;
          res.end('forbidden');
          return;
        }
        const target = fs.existsSync(filePath) && fs.statSync(filePath).isFile()
          ? filePath
          : path.join(DIST, 'index.html');
        const body = fs.readFileSync(target);
        res.statusCode = 200;
        res.setHeader('Content-Type', contentType(target));
        res.end(body);
      } catch (error) {
        res.statusCode = 500;
        res.end(String(error && error.message ? error.message : error));
      }
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

async function main() {
  assert.ok(fs.existsSync(path.join(DIST, 'index.html')), 'ui-react/dist/index.html missing');
  const server = await startServer();
  const port = server.address().port;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });
    const title = await page.title();
    assert.ok(title.includes('BAGO'), `unexpected title: ${title}`);

    const rootText = await page.locator('#root').innerText();
    assert.ok(rootText.trim().length > 0, 'root rendered empty content');
    assert.ok(/bago|manager|chat|workspace/i.test(rootText), 'root content does not look like the manager UI');
    console.log(`UI smoke ok: ${title} (${rootText.trim().slice(0, 80)})`);
  } finally {
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
