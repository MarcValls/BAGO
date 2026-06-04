const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const { ReleaseJobManager } = require('../electron/release-job-manager.cjs');

function waitUntil(manager, predicate, timeoutMs = 20000) {
  const current = manager.listJobs().find(predicate);
  if (current) return Promise.resolve(current);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      manager.removeListener('changed', listener);
      reject(new Error('timeout'));
    }, timeoutMs);
    const listener = job => {
      if (predicate(job)) {
        clearTimeout(timer);
        manager.removeListener('changed', listener);
        resolve(job);
      }
    };
    manager.on('changed', listener);
  });
}

function writeFixture(source) {
  fs.mkdirSync(path.join(source, 'bago_core'), { recursive: true });
  fs.writeFileSync(path.join(source, 'release_version.txt'), 'v9.9.9\n');
  fs.writeFileSync(path.join(source, 'bago_core', 'launcher.py'), 'print("ok")\n');
  fs.writeFileSync(path.join(source, 'payload.bin'), crypto.randomBytes(1024 * 1024));
  fs.writeFileSync(path.join(source, 'install-v4.ps1'), [
    'param(',
    '  [string]$SourceRoot,',
    '  [string]$InstallDir,',
    '  [string]$Mode,',
    '  [switch]$NoPathUpdate',
    ')',
    'New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null',
    'Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {',
    '  Copy-Item -LiteralPath $_.FullName -Destination $InstallDir -Recurse -Force',
    '}',
    '@{ ok = $true; installed_to = $InstallDir } | ConvertTo-Json'
  ].join('\r\n') + '\r\n');
}

function createServer(bundle, checksum) {
  return http.createServer((req, res) => {
    if (req.url === '/bundle.zip.sha256') {
      res.writeHead(200, { 'Content-Length': Buffer.byteLength(checksum) });
      res.end(checksum);
      return;
    }
    if (req.url !== '/bundle.zip') {
      res.writeHead(404);
      res.end();
      return;
    }
    const range = req.headers.range || '';
    const match = range.match(/bytes=(\d+)-/);
    const start = match ? Number(match[1]) : 0;
    const body = bundle.subarray(start);
    res.writeHead(start ? 206 : 200, {
      'Content-Length': body.length,
      ...(start ? { 'Content-Range': `bytes ${start}-${bundle.length - 1}/${bundle.length}` } : {})
    });
    let offset = 0;
    const timer = setInterval(() => {
      if (offset >= body.length) {
        clearInterval(timer);
        res.end();
        return;
      }
      const end = Math.min(offset + 16384, body.length);
      res.write(body.subarray(offset, end));
      offset = end;
    }, 3);
    res.on('close', () => clearInterval(timer));
  });
}

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-release-jobs-'));
  const source = path.join(root, 'source');
  const bundlePath = path.join(root, 'bundle.zip');
  const target = path.join(root, 'target');
  writeFixture(source);
  fs.mkdirSync(target, { recursive: true });
  fs.writeFileSync(path.join(target, 'old.txt'), 'old runtime\n');
  execFileSync('powershell.exe', [
    '-NoProfile',
    '-Command',
    `Compress-Archive -Path '${source.replace(/'/g, "''")}\\*' -DestinationPath '${bundlePath.replace(/'/g, "''")}' -Force`
  ]);
  const bundle = fs.readFileSync(bundlePath);
  const sha256 = crypto.createHash('sha256').update(bundle).digest('hex');
  const checksum = `${sha256}  bundle.zip\n`;
  const server = createServer(bundle, checksum);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const release = {
    tag_name: 'v9.9.9',
    prerelease: false,
    assets: [
      {
        name: 'bundle.zip',
        browser_download_url: `http://127.0.0.1:${port}/bundle.zip`,
        size: bundle.length,
        digest: `sha256:${sha256}`
      },
      {
        name: 'bundle.zip.sha256',
        browser_download_url: `http://127.0.0.1:${port}/bundle.zip.sha256`,
        size: Buffer.byteLength(checksum)
      }
    ]
  };
  const manager = new ReleaseJobManager({
    rootDir: path.join(root, 'jobs-root'),
    allowedHosts: ['127.0.0.1'],
    allowInsecureHosts: ['127.0.0.1']
  });
  try {
    const preflight = manager.preflight({ release, target, action: 'update' });
    assert.strictEqual(preflight.ok, true);
    assert.strictEqual(preflight.impact.backup_required, true);
    assert.strictEqual(manager.preflight({ release, target, action: 'update', require_signature: true }).ok, false);
    const uninstallPreflight = manager.preflight({ target, action: 'uninstall' });
    assert.strictEqual(uninstallPreflight.ok, true);
    assert.strictEqual(uninstallPreflight.impact.remove_runtime_only, true);
    assert.strictEqual(manager.preflight({ target: path.join(root, 'missing'), action: 'uninstall' }).ok, false);

    const created = manager.startPrepare({ release, target, action: 'update' });
    await waitUntil(manager, job => job.id === created.id && job.state === 'downloading' && job.progress.transferred > 0);
    manager.cancel(created.id);
    const cancelled = await manager.waitFor(created.id, ['cancelled']);
    assert.strictEqual(cancelled.state, 'cancelled');

    manager.resume(created.id);
    const ready = await manager.waitFor(created.id, ['ready'], 60000);
    assert.strictEqual(ready.verification.actual_sha256, sha256);
    assert.strictEqual(ready.compatibility.ok, true);
    assert.strictEqual(ready.verification.signature.status, 'not-published');

    const installed = await manager.install(created.id);
    assert.strictEqual(installed.state, 'completed');
    assert.strictEqual(fs.existsSync(path.join(target, 'bago_core', 'launcher.py')), true);
    assert.strictEqual(fs.existsSync(path.join(target, 'old.txt')), false);
    assert.strictEqual(installed.rollback_available, true);

    const rolledBack = await manager.rollback(created.id);
    assert.strictEqual(rolledBack.state, 'rolled-back');
    assert.strictEqual(fs.readFileSync(path.join(target, 'old.txt'), 'utf8'), 'old runtime\n');
    assert.ok(manager.getLogs(created.id).length > 0);
    console.log(JSON.stringify({
      ok: true,
      cancel_resume: true,
      sha256_verified: true,
      installed: true,
      rollback: true
    }));
  } finally {
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
