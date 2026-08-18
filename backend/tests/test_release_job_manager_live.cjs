const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('../electron/release-job-manager.cjs');

async function main() {
  const response = await fetch('https://api.github.com/repos/MarcValls/BAGO/releases?per_page=20', {
    headers: { Accept: 'application/vnd.github+json' }
  });
  assert.strictEqual(response.ok, true);
  const releases = await response.json();
  const release = releases
    .filter(item => !item.draft && !item.prerelease)
    .map(item => ({
      tag_name: item.tag_name,
      prerelease: !!item.prerelease,
      published_at: item.published_at,
      assets: item.assets.map(asset => ({
        name: asset.name,
        browser_download_url: asset.browser_download_url,
        size: asset.size,
        digest: asset.digest || ''
      }))
    }))
    .find(item => {
      const names = new Set(item.assets.map(asset => asset.name.toLowerCase()));
      return item.assets.some(asset => /\.zip$/i.test(asset.name) && names.has(`${asset.name}.sha256`.toLowerCase()));
    });
  assert.ok(release);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-release-live-'));
  const manager = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
  try {
    const job = manager.startPrepare({
      release,
      target: path.join(root, 'target'),
      action: 'separate'
    });
    const ready = await manager.waitFor(job.id, ['ready', 'failed'], 120000);
    assert.strictEqual(ready.state, 'ready', ready.error);
    assert.strictEqual(ready.compatibility.ok, true);
    assert.strictEqual(ready.verification.expected_sha256, ready.verification.actual_sha256);
    if (ready.verification.github_digest) {
      assert.strictEqual(ready.verification.github_digest, ready.verification.actual_sha256);
    }
    console.log(JSON.stringify({
      ok: true,
      tag: ready.release.tag_name,
      bundle: path.basename(ready.bundle_path),
      sha256: ready.verification.actual_sha256,
      signature: ready.verification.signature.status,
      compatible: ready.compatibility.ok
    }));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
