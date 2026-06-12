const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function extractFunction(source, name, nextName) {
  const start = source.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`missing ${name}`);
  const end = nextName ? source.indexOf(`function ${nextName}(`, start + 1) : -1;
  if (nextName && end < 0) throw new Error(`missing ${nextName}`);
  return source.slice(start, nextName ? end : source.length);
}

function runHelper(source, helperName, nextName, sandbox) {
  const code = extractFunction(source, helperName, nextName);
  const context = vm.createContext({ ...sandbox });
  vm.runInContext(`${code}; result = ${helperName}(arg);`, context);
  return context.result;
}

function main() {
  const legacySource = fs.readFileSync(path.join(__dirname, '..', 'manager', 'js', 'legacy-manager.js'), 'utf8');
  const patchSource = fs.readFileSync(path.join(__dirname, '..', 'manager', 'js', 'patch-manager.js'), 'utf8');

  const release = {
    assets: [
      { name: 'BAGO-Installation-Manager-4.5.2-win-x64.zip', browser_download_url: 'manager', size: 1 },
      { name: 'BAGO-Installation-Manager-4.5.2-win-x64.zip.sha256', browser_download_url: 'manager-sha', size: 1 },
      { name: 'bago-v4-local-20260610T024315Z.zip', browser_download_url: 'runtime', size: 1 },
      { name: 'bago-v4-local-20260610T024315Z.zip.sha256', browser_download_url: 'runtime-sha', size: 1 }
    ]
  };

  const latest = runHelper(legacySource, 'latestZipAsset', 'psSingle', { latestRelease: release, arg: undefined });
  assert.strictEqual(latest && latest.name, 'bago-v4-local-20260610T024315Z.zip');

  const contract = runHelper(patchSource, 'pmReleaseContract', 'pmMatrixCell', { arg: release });
  assert.strictEqual(contract.bundle && contract.bundle.name, 'bago-v4-local-20260610T024315Z.zip');
  assert.strictEqual(contract.ok, true);

  console.log(JSON.stringify({ ok: true, legacy: latest.name, patch: contract.bundle.name }));
}

main();
