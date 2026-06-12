// P0-01 / P0-02 / P0-05 regression tests for the BAGO Installation Manager.
// These exercise the pure (no-Electron) helpers we exposed from main.cjs
// by reading the source, slicing the function bodies out and running them
// in a Node `vm` sandbox. We do NOT spawn the actual installer.
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'electron', 'main.cjs'), 'utf8');

function extractBetween(startMarker, endMarker) {
  const i = SRC.indexOf(startMarker);
  if (i < 0) throw new Error('start marker not found: ' + startMarker);
  const j = endMarker ? SRC.indexOf(endMarker, i + 1) : -1;
  if (endMarker && j < 0) throw new Error('end marker not found: ' + endMarker);
  return SRC.slice(i, endMarker ? j : SRC.length);
}

const SNIPPET = `
${extractBetween('function hasBagoRuntime(', 'function resolveBundledRuntimeRoot(')}
${extractBetween('function hasInstallManifest(', 'function resolveInstalledRuntimeRoot(')}
${extractBetween('function resolveBundledRuntimeRoot(', 'function resolveInstalledRuntimeRoot(')}
${extractBetween('function resolveInstalledRuntimeRoot(', 'function isUserOwnedLocation(')}
${extractBetween('function isUserOwnedLocation(', 'function resolveBagoRuntimeRoot(')}
${extractBetween('function resolveBagoRuntimeRoot(', 'function resolveUiDist(')}
`;

function fakeApp({ isPackaged = false } = {}) {
  return {
    isPackaged,
    getPath: () => os.tmpdir(),
    whenReady: () => Promise.resolve()
  };
}

function makeTree() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-p0-'));
  fs.mkdirSync(path.join(root, 'bago_core'), { recursive: true });
  fs.mkdirSync(path.join(root, '.bago', 'core'), { recursive: true });
  fs.writeFileSync(path.join(root, 'bago_core', 'launcher.py'), '');
  fs.writeFileSync(path.join(root, 'bago_core', 'session_control.py'), '');
  fs.writeFileSync(path.join(root, '.bago', 'core', 'version.py'), '');
  fs.writeFileSync(path.join(root, '.bago', 'core', 'context_store.py'), '');
  return root;
}

function buildContext(opts = {}, envOverrides = {}) {
  const root = makeTree();
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-home-'));
  const programFiles = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-pf-'));
  const localAppData = path.join(home, 'AppData', 'Local');

  const bundleRuntime = makeTree();
  const devBundle = makeTree();
  const realInstall = path.join(programFiles, 'BAGO');
  fs.mkdirSync(realInstall, { recursive: true });
  fs.cpSync(root, realInstall, { recursive: true });
  fs.writeFileSync(path.join(realInstall, 'install_manifest.json'), JSON.stringify({
    schema_version: 1, profile: 'stable', install_dir: realInstall
  }));

  const app = fakeApp({ isPackaged: !!opts.isPackaged });
  return {
    ctx: {
      require, path, fs, os: { ...os, homedir: () => home },
      process: { env: { ...process.env, USERPROFILE: home, HOME: home, LOCALAPPDATA: localAppData, ProgramFiles: programFiles, ...envOverrides } },
      app,
      ROOT_DIR: root, PACKAGED_RUNTIME_ROOT: bundleRuntime, DEV_PACKAGED_RUNTIME_ROOT: devBundle
    },
    meta: { root, home, programFiles, localAppData, bundleRuntime, devBundle, realInstall, app }
  };
}

function runHelpers(ctx, expression) {
  const sandbox = vm.createContext({ ...ctx, console, result: undefined });
  vm.runInContext(SNIPPET + '\n' + expression, sandbox);
  return sandbox.result;
}

// --- P0-01 ---------------------------------------------------------------

function test_install_root_does_not_pick_bundled() {
  const { ctx, meta } = buildContext({ isPackaged: true });
  const installed = runHelpers(ctx, 'result = resolveInstalledRuntimeRoot();');
  assert.strictEqual(path.resolve(installed), path.resolve(meta.realInstall),
    'installed root must be the real install, not the bundled tree');
}

function test_bago_root_override_wins() {
  const override = makeTree();
  const { ctx } = buildContext({ isPackaged: false }, { BAGO_ROOT: override });
  const installed = runHelpers(ctx, 'result = resolveInstalledRuntimeRoot();');
  assert.strictEqual(path.resolve(installed), path.resolve(override));
}

function test_no_real_install_throws_when_packaged() {
  const { ctx, meta } = buildContext({ isPackaged: true });
  fs.rmSync(meta.realInstall, { recursive: true, force: true });
  assert.throws(() => runHelpers(ctx, 'result = resolveBagoRuntimeRoot();'),
    /No se encontro una instalacion real de BAGO/);
}

function test_no_real_install_falls_back_to_dev_in_dev_mode() {
  const { ctx, meta } = buildContext({ isPackaged: false });
  fs.rmSync(meta.realInstall, { recursive: true, force: true });
  const out = runHelpers(ctx, 'result = resolveBagoRuntimeRoot();');
  assert.ok(out, 'dev mode should fall back to the dev tree');
}

function test_localappdata_path_is_accepted_as_install() {
  // A user-writable install (LOCALAPPDATA) must be picked up even without
  // an install_manifest.json because the location is user-owned.
  const { ctx, meta } = buildContext({ isPackaged: true });
  fs.rmSync(meta.realInstall, { recursive: true, force: true });
  const userInstall = path.join(meta.localAppData, 'BAGO');
  fs.mkdirSync(userInstall, { recursive: true });
  // copy a runtime tree
  const src = makeTree();
  fs.cpSync(src, userInstall, { recursive: true });
  const out = runHelpers(ctx, 'result = resolveInstalledRuntimeRoot();');
  assert.strictEqual(path.resolve(out), path.resolve(userInstall));
}

function run() {
  const cases = [
    ['P0-01 installed != bundled', test_install_root_does_not_pick_bundled],
    ['P0-01 BAGO_ROOT override wins', test_bago_root_override_wins],
    ['P0-01 packaged throws without install', test_no_real_install_throws_when_packaged],
    ['P0-01 dev mode falls back to dev tree', test_no_real_install_falls_back_to_dev_in_dev_mode],
    ['P0-01 LOCALAPPDATA install accepted', test_localappdata_path_is_accepted_as_install]
  ];
  let failed = 0;
  for (const [name, fn] of cases) {
    try { fn(); console.log('ok  -', name); }
    catch (e) { failed += 1; console.error('FAIL-', name, '\n  ', e && e.stack || e); }
  }
  if (failed) {
    console.error(`\n${failed} test(s) failed`);
    process.exit(1);
  } else {
    console.log('\nall P0-01 helper tests passed');
  }
}

if (require.main === module) run();
module.exports = { run };
